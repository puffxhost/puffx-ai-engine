import json
import logging
import math
import secrets
from pathlib import Path

import httpx
from fastapi import Depends, FastAPI, Header, HTTPException, Query, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from jsonschema import ValidationError as JSONSchemaValidationError
from slowapi import Limiter, _rate_limit_exceeded_handler
from slowapi.errors import RateLimitExceeded
from slowapi.util import get_remote_address

from api.schemas import ChatRequest, EmbeddingRequest
from core.config import get_settings
from core.model_manager import get_provider
from core.provider_errors import ProviderCapabilityError
from core.request_limits import ClientRateLimitMiddleware, RequestBodyLimitMiddleware
from core.security import create_key, record_usage, revoke_key, usage_summary, valid_key

settings = get_settings()
logging.basicConfig(level=settings.log_level)
limiter = Limiter(key_func=get_remote_address)

app = FastAPI(title="Puffx AI Engine", version="1.1.0")
app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, _rate_limit_exceeded_handler)
app.add_middleware(RequestBodyLimitMiddleware, max_bytes=settings.max_request_bytes)
app.add_middleware(ClientRateLimitMiddleware, limit=settings.rate_limit)
app.mount(
    "/admin/ui",
    StaticFiles(directory=Path(__file__).resolve().parents[1] / "dashboard", html=True),
    name="dashboard",
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in settings.allowed_origins.split(",") if origin.strip()],
    allow_credentials=False,
    allow_methods=["GET", "POST", "DELETE"],
    allow_headers=["Authorization", "Content-Type"],
)


def auth(authorization: str | None = Header(default=None)):
    key = authorization.removeprefix("Bearer ").strip() if authorization else ""
    if not valid_key(key):
        raise HTTPException(401, "Invalid or missing API key")
    return key


def admin(authorization: str | None = Header(default=None)):
    key = authorization.removeprefix("Bearer ").strip() if authorization else ""
    if not settings.admin_password or not secrets.compare_digest(key, settings.admin_password):
        raise HTTPException(401, "Admin authentication required")
    return True


def _validate_response_format(result, response_format):
    if not response_format or response_format.type == "text":
        return
    try:
        content = result["choices"][0]["message"]["content"]
        if not isinstance(content, str):
            raise ValueError
        value = json.loads(content)
        if response_format.type == "json_object":
            if not isinstance(value, dict):
                raise ValueError
        else:
            from jsonschema import validate

            validate(value, response_format.json_schema["schema"])
    except (KeyError, IndexError, TypeError, ValueError, JSONSchemaValidationError) as exc:
        raise HTTPException(
            502,
            "Inference provider returned output that does not match response_format",
        ) from exc


def _validate_embeddings(result, body):
    expected_inputs = [body.input] if isinstance(body.input, str) else body.input
    try:
        entries = result["data"]
        usage = result["usage"]
        if result.get("object") != "list" or not isinstance(entries, list):
            raise ValueError
        if len(entries) != len(expected_inputs):
            raise ValueError
        normalized = []
        for expected_index, entry in enumerate(entries):
            vector = entry["embedding"]
            if (
                entry.get("object") != "embedding"
                or entry.get("index") != expected_index
                or not isinstance(vector, list)
                or not vector
                or any(
                    not isinstance(value, (int, float))
                    or isinstance(value, bool)
                    or not math.isfinite(value)
                    for value in vector
                )
            ):
                raise ValueError
            if body.dimensions and len(vector) != body.dimensions:
                raise ValueError
            normalized.append({"object": "embedding", "index": expected_index, "embedding": vector})
        prompt_tokens = usage.get("prompt_tokens", 0)
        total_tokens = usage.get("total_tokens", prompt_tokens)
        if not isinstance(prompt_tokens, int) or prompt_tokens < 0:
            raise ValueError
        if not isinstance(total_tokens, int) or total_tokens < 0:
            raise ValueError
        return {
            "object": "list",
            "data": normalized,
            "model": result.get("model") or body.model or settings.embedding_model or settings.model_name,
            "usage": {"prompt_tokens": prompt_tokens, "total_tokens": total_tokens},
        }
    except (KeyError, TypeError, ValueError) as exc:
        raise HTTPException(502, "Inference provider returned an invalid embeddings response") from exc


@app.get("/health")
async def health():
    models = await get_provider().models()
    return {
        "status": "ok",
        "backend": settings.inference_backend,
        "model_available": any(model["id"] == settings.model_name for model in models),
        "available_models": models,
    }


@app.get("/v1/models")
async def models(request: Request, _=Depends(auth)):
    return {"object": "list", "data": await get_provider().models()}


@app.post("/v1/chat/completions")
async def chat(request: Request, body: ChatRequest, key=Depends(auth)):
    if body.max_tokens > settings.max_tokens:
        raise HTTPException(400, "max_tokens exceeds configured limit")
    if body.stream and body.response_format and body.response_format.type != "text":
        raise HTTPException(
            400,
            "stream=true cannot be combined with json_object or json_schema because the complete output must be validated",
        )

    payload = body.model_dump(exclude_none=True)
    provider = get_provider()
    if body.stream:
        async def events():
            try:
                async for chunk in provider.chat_stream(payload):
                    yield "data: " + json.dumps(chunk, separators=(",", ":")) + "\n\n"
                record_usage(key, "/v1/chat/completions")
            except ProviderCapabilityError:
                logging.warning("Streaming inference provider rejected the requested capability")
                yield 'event: error\ndata: {"error":{"message":"Inference provider does not support this request","type":"server_error"}}\n\n'
            except Exception as exc:
                logging.warning("Streaming inference failed (%s)", type(exc).__name__)
                yield 'event: error\ndata: {"error":{"message":"Inference backend unavailable or stream interrupted","type":"server_error"}}\n\n'
            yield "data: [DONE]\n\n"

        return StreamingResponse(
            events(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
        )

    try:
        result = await provider.chat(payload)
    except ProviderCapabilityError as exc:
        raise HTTPException(
            422,
            "Inference provider does not support the requested model or response format",
        ) from exc
    except Exception as exc:
        logging.warning("Inference failed (%s)", type(exc).__name__)
        raise HTTPException(503, "Inference backend unavailable or request failed") from exc

    _validate_response_format(result, body.response_format)
    record_usage(key, "/v1/chat/completions")
    return result


@app.post("/v1/embeddings")
async def embeddings(request: Request, body: EmbeddingRequest, key=Depends(auth)):
    payload = body.model_dump(exclude_none=True)
    if not payload.get("model"):
        payload["model"] = settings.embedding_model or settings.model_name
    try:
        result = await get_provider().embeddings(payload)
    except ProviderCapabilityError as exc:
        raise HTTPException(
            422,
            "Inference provider does not support the requested embedding model or dimensions",
        ) from exc
    except Exception as exc:
        logging.warning("Embedding inference failed (%s)", type(exc).__name__)
        raise HTTPException(503, "Inference backend unavailable or request failed") from exc

    response = _validate_embeddings(result, body)
    record_usage(key, "/v1/embeddings")
    return response


@app.get("/admin/usage")
@limiter.limit(settings.admin_rate_limit)
async def usage(request: Request, _=Depends(admin)):
    return usage_summary()


@app.post("/admin/keys")
@limiter.limit(settings.admin_rate_limit)
async def new_key(
    request: Request,
    label: str = Query(default="API key", min_length=1, max_length=80),
    _=Depends(admin),
):
    label = label.strip()
    if not label:
        raise HTTPException(400, "Key label cannot be empty")
    return create_key(label)


@app.delete("/admin/keys/{key_id}")
@limiter.limit(settings.admin_rate_limit)
async def delete_key(request: Request, key_id: str, _=Depends(admin)):
    if not revoke_key(key_id):
        raise HTTPException(404, "Key not found")
    return {"revoked": True}


@app.get("/admin/status")
@limiter.limit(settings.admin_rate_limit)
async def status(request: Request, _=Depends(admin)):
    return {
        "backend": settings.inference_backend,
        "model": settings.model_name,
        "models": await get_provider().models(),
    }

