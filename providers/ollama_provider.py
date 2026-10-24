import json
import time
import uuid

import httpx

from core.config import get_settings
from core.provider_errors import ProviderCapabilityError


class OllamaProvider:
    def __init__(self):
        self.settings = get_settings()
        self.base = self.settings.ollama_base_url.rstrip("/")

    async def models(self):
        try:
            async with httpx.AsyncClient(timeout=3) as client:
                response = await client.get(self.base + "/api/tags")
                response.raise_for_status()
                data = response.json()
            return [{"id": item["name"], "object": "model"} for item in data.get("models", [])
                    if isinstance(item, dict) and isinstance(item.get("name"), str)]
        except (httpx.HTTPError, ValueError, TypeError, KeyError, AttributeError):
            return []

    def _chat_payload(self, payload, stream):
        request = {
            "model": payload.get("model") or self.settings.model_name,
            "messages": payload["messages"],
            "stream": stream,
            "options": {
                "temperature": payload.get("temperature", 0.7),
                "num_predict": payload.get("max_tokens", self.settings.max_tokens),
            },
        }
        response_format = payload.get("response_format")
        if response_format:
            if response_format["type"] == "json_object":
                request["format"] = "json"
            elif response_format["type"] == "json_schema":
                request["format"] = response_format["json_schema"]["schema"]
        return request

    async def chat(self, payload):
        request = self._chat_payload(payload, stream=False)
        try:
            async with httpx.AsyncClient(timeout=self.settings.request_timeout) as client:
                response = await client.post(self.base + "/api/chat", json=request)
                if 400 <= response.status_code < 500:
                    raise ProviderCapabilityError("Ollama rejected the model or requested response format")
                response.raise_for_status()
                data = response.json()
        except ProviderCapabilityError:
            raise
        message = data.get("message")
        if not isinstance(message, dict) or not isinstance(message.get("content"), str):
            raise RuntimeError("Invalid Ollama chat response")
        prompt_tokens = int(data.get("prompt_eval_count") or 0)
        completion_tokens = int(data.get("eval_count") or 0)
        return {
            "id": "chatcmpl-" + uuid.uuid4().hex,
            "object": "chat.completion",
            "created": int(time.time()),
            "model": request["model"],
            "choices": [{"index": 0, "message": {"role": "assistant", "content": message["content"]},
                         "finish_reason": data.get("done_reason") or "stop"}],
            "usage": {"prompt_tokens": prompt_tokens, "completion_tokens": completion_tokens,
                      "total_tokens": prompt_tokens + completion_tokens},
        }

    async def chat_stream(self, payload):
        request = self._chat_payload(payload, stream=True)
        base_chunk = {"id": "chatcmpl-" + uuid.uuid4().hex, "object": "chat.completion.chunk",
                      "created": int(time.time()), "model": request["model"]}
        try:
            async with httpx.AsyncClient(timeout=self.settings.request_timeout) as client:
                async with client.stream("POST", self.base + "/api/chat", json=request) as response:
                    if 400 <= response.status_code < 500:
                        raise ProviderCapabilityError("Ollama rejected the model or requested response format")
                    response.raise_for_status()
                    yield {**base_chunk, "choices": [{"index": 0, "delta": {"role": "assistant"}, "finish_reason": None}]}
                    async for line in response.aiter_lines():
                        if not line.strip():
                            continue
                        item = json.loads(line)
                        content = (item.get("message") or {}).get("content")
                        if content:
                            yield {**base_chunk, "choices": [{"index": 0, "delta": {"content": content}, "finish_reason": None}]}
                        if item.get("done"):
                            yield {**base_chunk, "choices": [{"index": 0, "delta": {},
                                  "finish_reason": item.get("done_reason") or "stop"}]}
        except ProviderCapabilityError:
            raise

    async def embeddings(self, payload):
        request = {"model": payload.get("model") or self.settings.model_name, "input": payload["input"]}
        if payload.get("dimensions") is not None:
            request["dimensions"] = payload["dimensions"]
        try:
            async with httpx.AsyncClient(timeout=self.settings.request_timeout) as client:
                response = await client.post(self.base + "/api/embed", json=request)
                if 400 <= response.status_code < 500:
                    raise ProviderCapabilityError("Ollama rejected the embedding model or dimensions")
                response.raise_for_status()
                result = response.json()
        except ProviderCapabilityError:
            raise
        vectors = result.get("embeddings")
        if not isinstance(vectors, list):
            raise RuntimeError("Invalid Ollama embeddings response")
        data = []
        for index, vector in enumerate(vectors):
            if not isinstance(vector, list) or any(not isinstance(value, (int, float)) or isinstance(value, bool)
                                                   for value in vector):
                raise RuntimeError("Invalid Ollama embedding vector")
            data.append({"object": "embedding", "index": index, "embedding": vector})
        prompt_tokens = int(result.get("prompt_eval_count") or 0)
        return {"object": "list", "data": data, "model": request["model"],
                "usage": {"prompt_tokens": prompt_tokens, "total_tokens": prompt_tokens}}

