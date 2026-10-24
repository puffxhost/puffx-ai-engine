from functools import lru_cache
from pydantic_settings import BaseSettings,SettingsConfigDict
class Settings(BaseSettings):
 model_config=SettingsConfigDict(env_file='.env',extra='ignore')
 api_host:str='127.0.0.1';api_port:int=8000;api_key:str='';admin_username:str='admin';admin_password:str=''
 database_url:str='sqlite:///./puffx.db';inference_backend:str='ollama';model_name:str='qwen2.5:3b';model_path:str='./models';ollama_base_url:str='http://127.0.0.1:11434';remote_inference_url:str='';remote_api_key:str='';rate_limit:str='60/minute';admin_rate_limit:str='10/minute';request_timeout:float=120;max_tokens:int=2048;max_request_bytes:int=1048576;log_level:str='INFO';allowed_origins:str='http://127.0.0.1:8000'
@lru_cache
def get_settings():return Settings()


