import httpx

from core.config import get_settings


class RemoteProvider:
    def __init__(self):
        self.settings = get_settings()

    async def models(self):
        if not self.settings.remote_inference_url:
            return []
        headers = (
            {"Authorization": "Bearer " + self.settings.remote_api_key}
            if self.settings.remote_api_key
            else {}
        )
        url = self.settings.remote_inference_url.rstrip("/") + "/v1/models"
        try:
            async with httpx.AsyncClient(timeout=3) as client:
                response = await client.get(url, headers=headers)
                response.raise_for_status()
                data = response.json().get("data", [])
            return [
                {"id": model["id"], "object": "model"}
                for model in data
                if isinstance(model, dict) and isinstance(model.get("id"), str)
            ]
        except (httpx.HTTPError, ValueError, TypeError, KeyError, AttributeError):
            return []

    async def chat(self, payload):
        if not self.settings.remote_inference_url:
            raise RuntimeError("Remote URL not configured")

        # OpenAI-compatible services generally require a model name. Use the
        # configured default when clients omit one, as the local Ollama adapter does.
        request_payload = dict(payload)
        request_payload["model"] = request_payload.get("model") or self.settings.model_name

        # The gateway buffers provider responses and emits its own SSE chunks.
        # Asking upstream for stream=True would return SSE instead of JSON.
        request_payload["stream"] = False

        headers = (
            {"Authorization": "Bearer " + self.settings.remote_api_key}
            if self.settings.remote_api_key
            else {}
        )
        url = self.settings.remote_inference_url.rstrip("/") + "/v1/chat/completions"
        async with httpx.AsyncClient(timeout=self.settings.request_timeout) as client:
            response = await client.post(url, json=request_payload, headers=headers)
            response.raise_for_status()
            return response.json()
