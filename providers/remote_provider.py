import httpx
from core.config import get_settings
class RemoteProvider:
 def __init__(self):self.s=get_settings()
 async def models(self):
  if not self.s.remote_inference_url:return []
  h={'Authorization':'Bearer '+self.s.remote_api_key} if self.s.remote_api_key else {}
  try:
   async with httpx.AsyncClient(timeout=3) as c:r=await c.get(self.s.remote_inference_url.rstrip('/')+'/v1/models',headers=h);r.raise_for_status();data=r.json().get('data',[])
   return [{'id':x['id'],'object':'model'} for x in data if isinstance(x,dict) and isinstance(x.get('id'),str)]
  except (httpx.HTTPError,ValueError,TypeError,KeyError,AttributeError):return []
 async def chat(self,p):
  if not self.s.remote_inference_url:raise RuntimeError('Remote URL not configured')
  h={'Authorization':'Bearer '+self.s.remote_api_key} if self.s.remote_api_key else {}
  async with httpx.AsyncClient(timeout=self.s.request_timeout) as c:r=await c.post(self.s.remote_inference_url.rstrip('/')+'/v1/chat/completions',json=p,headers=h);r.raise_for_status();return r.json()
