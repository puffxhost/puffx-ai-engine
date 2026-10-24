import json
import time

from core.provider_errors import ProviderCapabilityError


class MockProvider:
    async def models(self):
        return [{"id": "mock", "object": "model"}]

    async def chat(self, payload):
        response_format = payload.get("response_format")
        if response_format and response_format.get("type") in {"json_object", "json_schema"}:
            content = json.dumps({"response": payload["messages"][-1]["content"]})
        else:
            content = "Mock response: " + payload["messages"][-1]["content"]
        return {
            "id": "chatcmpl-mock",
            "object": "chat.completion",
            "created": int(time.time()),
            "model": payload.get("model") or "mock",
            "choices": [{"index": 0, "message": {"role": "assistant", "content": content}, "finish_reason": "stop"}],
            "usage": {"prompt_tokens": 0, "completion_tokens": 0, "total_tokens": 0},
        }

    async def chat_stream(self, payload):
        result = await self.chat(payload)
        choice = result["choices"][0]
        base = {"id": result["id"], "object": "chat.completion.chunk", "created": result["created"], "model": result["model"]}
        yield {**base, "choices": [{"index": 0, "delta": {"role": "assistant"}, "finish_reason": None}]}
        content = choice["message"]["content"]
        for offset in range(0, len(content), 12):
            yield {**base, "choices": [{"index": 0, "delta": {"content": content[offset:offset + 12]}, "finish_reason": None}]}
        yield {**base, "choices": [{"index": 0, "delta": {}, "finish_reason": choice.get("finish_reason") or "stop"}]}

    async def embeddings(self, payload):
        raise ProviderCapabilityError("The mock provider does not generate embeddings")

