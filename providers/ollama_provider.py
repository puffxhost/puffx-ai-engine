import time,uuid
import httpx
from core.config import get_settings
class OllamaProvider:
 def __init__(self):self.s=get_settings();self.base=self.s.ollama_base_url.rstrip('/')
 async def models(self):
  try:
   async with httpx.AsyncClient(timeout=3) as c:r=await c.get(self.base+'/api/tags');r.raise_for_status();return [{'id':x['name'],'object':'model'} for x in r.json().get('models',[]) if isinstance(x,dict) and isinstance(x.get('name'),str)]
  except (httpx.HTTPError,ValueError,TypeError,KeyError,AttributeError):return []
 async def chat(self,p):
  q={'model':p.get('model') or self.s.model_name,'messages':p['messages'],'stream':False,'options':{'temperature':p.get('temperature',.7),'num_predict':p.get('max_tokens',self.s.max_tokens)}}
  async with httpx.AsyncClient(timeout=self.s.request_timeout) as c:r=await c.post(self.base+'/api/chat',json=q);r.raise_for_status()
  j=r.json();message=j.get('message')
  if not isinstance(message,dict) or not isinstance(message.get('content'),str):raise RuntimeError('Invalid Ollama chat response')
  prompt=int(j.get('prompt_eval_count') or 0);completion=int(j.get('eval_count') or 0)
  return {'id':'chatcmpl-'+uuid.uuid4().hex,'object':'chat.completion','created':int(time.time()),'model':q['model'],'choices':[{'index':0,'message':message,'finish_reason':j.get('done_reason') or 'stop'}],'usage':{'prompt_tokens':prompt,'completion_tokens':completion,'total_tokens':prompt+completion}}

