import httpx
from core.config import get_settings
class OllamaProvider:
 def __init__(self):self.s=get_settings();self.base=self.s.ollama_base_url.rstrip('/')
 def models(self):
  try:
   r=httpx.get(self.base+'/api/tags',timeout=3);r.raise_for_status();return [{'id':x['name'],'object':'model'} for x in r.json().get('models',[])]
  except httpx.HTTPError:return []
 async def chat(self,p):
  q={'model':p.get('model') or self.s.model_name,'messages':p['messages'],'stream':False,'options':{'temperature':p.get('temperature',.7),'num_predict':p.get('max_tokens',self.s.max_tokens)}}
  async with httpx.AsyncClient(timeout=self.s.request_timeout) as c:r=await c.post(self.base+'/api/chat',json=q);r.raise_for_status()
  j=r.json();return {'id':'chatcmpl-puffx','object':'chat.completion','created':0,'model':q['model'],'choices':[{'index':0,'message':j['message'],'finish_reason':'stop'}],'usage':{'prompt_tokens':0,'completion_tokens':0,'total_tokens':0}}

