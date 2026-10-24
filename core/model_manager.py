from core.config import get_settings
from providers.ollama_provider import OllamaProvider
from providers.remote_provider import RemoteProvider
from providers.mock_provider import MockProvider
def get_provider():
 n=get_settings().inference_backend.lower()
 if n=='ollama':return OllamaProvider()
 if n=='remote':return RemoteProvider()
 if n=='mock':return MockProvider()
 raise RuntimeError('Unsupported backend '+n)
