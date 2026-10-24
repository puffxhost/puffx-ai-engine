import json
import time
import uuid

import httpx

from core.config import get_settings
from core.provider_errors import ProviderCapabilityError


class RemoteProvider:
    def __init__(self):
        self.settings = get_settings()

    def _headers(self):
        return {"Authorization": "Bearer " + self.settings.remote_api_key} if self.settings.remote_api_key else {}

    def _url(self, path):
        if not self.settings.remote_inference_url:
            raise RuntimeError("Remote inference URL not configured")
        return self.settings.remote_inference_url.rstrip("/") + path

    def _provider_error(self, response):
        if 400 <= response.status_code < 500:
            raise ProviderCapabilityError("Remote provider rejected the model or requested response format")
        response.raise_for_status()

    async def models(self):
        if not self.settings.remote_inference_url:
            return []
        try:
            async with httpx.AsyncClient(timeout=3) as client:
                response = await client.get(self._url("/v1/models"), headers=self._headers())
                response.raise_for_status()
                data = response.json().get("data", [])
            return [{"id": model["id"], "object": "model"} for model in data
                    if isinstance(model, dict) and isinstance(model.get("id"), str)]
        except (httpx.HTTPError, ValueError, TypeError, KeyError, AttributeError):
            return []

    def _chat_payload(self, payload, stream):
        request_payload = dict(payload)
        request_payload["model"] = request_payload.get("model") or self.settings.model_name
        request_payload["stream"] = stream
        response_format = request_payload.get("response_format")
        if response_format and response_format.get("type") == "text":
            request_payload.pop("response_format", None)
        return request_payload

    async def chat(self, payload):
        request_payload = self._chat_payload(payload, stream=False)
        async with httpx.AsyncClient(timeout=self.settings.request_timeout) as client:
            response = await client.post(self._url("/v1/chat/completions"), json=request_payload, headers=self._headers())
        self._provider_error(response)
        return response.json()

    async def chat_stream(self, payload):
        request_payload = self._chat_payload(payload, stream=True)
        base_chunk = {"id": "chatcmpl-" + uuid.uuid4().hex, "object": "chat.completion.chunk",
                      "created": int(time.time()), "model": request_payload["model"]}
        async with httpx.AsyncClient(timeout=self.settings.request_timeout) as client:
            async with client.stream("POST", self._url("/v1/chat/completions"),
                                     json=request_payload, headers=self._headers()) as response:
                self._provider_error(response)
                content_type = response.headers.get("content-type", "").lower()
                if "text/event-stream" not in content_type:
                    result = json.loads(await response.aread())
                    choice = result["choices"][0]
                    content = (choice.get("message") or {}).get("content") or ""
                    yield {**base_chunk, "choices": [{"index": 0, "delta": {"role": "assistant"}, "finish_reason": None}]}
                    if content:
                        yield {**base_chunk, "choices": [{"index": 0, "delta": {"content": content}, "finish_reason": None}]}
                    yield {**base_chunk, "choices": [{"index": 0, "delta": {},
                          "finish_reason": choice.get("finish_reason") or "stop"}]}
                    return
                yield {**base_chunk, "choices": [{"index": 0, "delta": {"role": "assistant"}, "finish_reason": None}]}
                async for line in response.aiter_lines():
                    if not line.startswith("data:"):
                        continue
                    data = line[5:].strip()
                    if not data:
                        continue
                    if data == "[DONE]":
                        break
                    try:
                        item = json.loads(data)
                    except ValueError as exc:
                        raise RuntimeError("Remote provider returned invalid stream data") from exc
                    choices = item.get("choices") or []
                    if not choices:
                        continue
                    choice = choices[0]
                    content = (choice.get("delta") or {}).get("content")
                    if content:
                        yield {**base_chunk, "choices": [{"index": 0, "delta": {"content": content}, "finish_reason": None}]}
                    if choice.get("finish_reason") is not None:
                        yield {**base_chunk, "choices": [{"index": 0, "delta": {},
                              "finish_reason": choice["finish_reason"]}]}

    async def embeddings(self, payload):
        request_payload = dict(payload)
        request_payload["model"] = request_payload.get("model") or self.settings.model_name
        async with httpx.AsyncClient(timeout=self.settings.request_timeout) as client:
            response = await client.post(self._url("/v1/embeddings"), json=request_payload, headers=self._headers())
        self._provider_error(response)
        result = response.json()
        if not isinstance(result, dict) or not isinstance(result.get("data"), list):
            raise RuntimeError("Invalid remote embeddings response")
        if not isinstance(result.get("usage"), dict):
            result["usage"] = {"prompt_tokens": 0, "total_tokens": 0}
        result["model"] = request_payload["model"]
        return result

