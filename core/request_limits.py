import math
import re

from starlette.responses import JSONResponse

from core.security import consume_rate_limit, digest, valid_key


_RATE_LIMIT = re.compile(r"^\s*(\d+)\s*/\s*(second|minute|hour|day)s?\s*$", re.IGNORECASE)
_WINDOWS = {"second": 1, "minute": 60, "hour": 3600, "day": 86400}
_CLIENT_ENDPOINTS = {"/v1/models", "/v1/chat/completions", "/v1/embeddings"}


def parse_rate_limit(value: str):
    match = _RATE_LIMIT.fullmatch(value)
    if not match:
        raise ValueError("RATE_LIMIT must use the format '<count>/<second|minute|hour|day>'")
    limit = int(match.group(1))
    if limit < 1:
        raise ValueError("RATE_LIMIT must allow at least one request")
    unit = match.group(2).lower()
    return limit, _WINDOWS[unit]


class RequestBodyLimitMiddleware:
    """Bound request-body memory use, including chunked requests without Content-Length."""

    def __init__(self, app, max_bytes: int):
        self.app = app
        self.max_bytes = max(1, int(max_bytes))

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        headers = dict(scope.get("headers", []))
        raw_length = headers.get(b"content-length")
        if raw_length is not None:
            try:
                length = int(raw_length)
                if length < 0:
                    raise ValueError
            except ValueError:
                await JSONResponse({"detail": "Invalid Content-Length"}, status_code=400)(scope, receive, send)
                return
            if length > self.max_bytes:
                await JSONResponse({"detail": "Request body too large"}, status_code=413)(scope, receive, send)
                return

        messages = []
        total = 0
        while True:
            message = await receive()
            messages.append(message)
            if message["type"] == "http.request":
                total += len(message.get("body", b""))
                if total > self.max_bytes:
                    await JSONResponse({"detail": "Request body too large"}, status_code=413)(scope, receive, send)
                    return
                if not message.get("more_body", False):
                    break
            elif message["type"] == "http.disconnect":
                return

        async def replay():
            if messages:
                return messages.pop(0)
            return {"type": "http.request", "body": b"", "more_body": False}

        await self.app(scope, replay, send)


class ClientRateLimitMiddleware:
    """Apply a SQLite-backed quota per valid API key, or per client IP for invalid/no keys."""

    def __init__(self, app, limit: str):
        self.app = app
        self.limit, self.window_seconds = parse_rate_limit(limit)

    def _bucket(self, scope):
        headers = dict(scope.get("headers", []))
        authorization = headers.get(b"authorization", b"").decode("latin-1")
        scheme, separator, token = authorization.partition(" ")
        token = token.strip() if separator and scheme.lower() == "bearer" else ""
        if token and valid_key(token):
            return "key:" + digest(token)
        client = scope.get("client")
        client_ip = client[0] if client else "unknown"
        return "ip:" + client_ip

    async def __call__(self, scope, receive, send):
        if (
            scope["type"] != "http"
            or scope.get("method") not in {"GET", "POST"}
            or scope.get("path") not in _CLIENT_ENDPOINTS
        ):
            await self.app(scope, receive, send)
            return

        bucket = self._bucket(scope)
        allowed, count, reset_at = consume_rate_limit(
            bucket, self.limit, self.window_seconds
        )
        remaining = max(self.limit - count, 0)
        rate_headers = [
            (b"x-ratelimit-limit", str(self.limit).encode()),
            (b"x-ratelimit-remaining", str(remaining).encode()),
            (b"x-ratelimit-reset", str(reset_at).encode()),
        ]
        if not allowed:
            retry_after = max(1, math.ceil(reset_at - __import__("time").time()))
            headers = rate_headers + [(b"retry-after", str(retry_after).encode())]
            await JSONResponse(
                {"detail": "Rate limit exceeded"}, status_code=429, headers=dict(
                    (key.decode(), value.decode()) for key, value in headers
                )
            )(scope, receive, send)
            return

        async def send_with_rate_headers(message):
            if message["type"] == "http.response.start":
                existing = list(message.get("headers", []))
                existing.extend(rate_headers)
                message["headers"] = existing
            await send(message)

        await self.app(scope, receive, send_with_rate_headers)

