import secrets,logging,json
from fastapi import FastAPI,Depends,HTTPException,Header,Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pathlib import Path
from slowapi import Limiter,_rate_limit_exceeded_handler
from slowapi.util import get_remote_address
from slowapi.errors import RateLimitExceeded
from core.config import get_settings
from core.model_manager import get_provider
from core.security import valid_key,create_key,revoke_key,record_usage,usage_summary
from api.schemas import ChatRequest
s=get_settings();logging.basicConfig(level=s.log_level);limiter=Limiter(key_func=get_remote_address)
app=FastAPI(title='Puffx AI Engine',version='1.0.0');app.state.limiter=limiter;app.add_exception_handler(RateLimitExceeded,_rate_limit_exceeded_handler)
app.mount('/admin/ui',StaticFiles(directory=Path(__file__).resolve().parents[1]/'dashboard',html=True),name='dashboard')
app.add_middleware(CORSMiddleware,allow_origins=[x.strip() for x in s.allowed_origins.split(',') if x.strip()],allow_credentials=False,allow_methods=['GET','POST','DELETE'],allow_headers=['Authorization','Content-Type'])
def auth(authorization:str|None=Header(default=None)):
 k=authorization.removeprefix('Bearer ').strip() if authorization else ''
 if not valid_key(k):raise HTTPException(401,'Invalid or missing API key')
 return k
def admin(authorization:str|None=Header(default=None)):
 k=authorization.removeprefix('Bearer ').strip() if authorization else ''
 if not s.admin_password or not secrets.compare_digest(k,s.admin_password):raise HTTPException(401,'Admin authentication required')
 return True
@app.get('/health')
async def health():
 m=get_provider().models();return {'status':'ok','backend':s.inference_backend,'model_available':any(x['id']==s.model_name for x in m),'available_models':m}
@app.get('/v1/models')
async def models(_=Depends(auth)):return {'object':'list','data':get_provider().models()}
@app.post('/v1/chat/completions')
@limiter.limit(s.rate_limit)
async def chat(request:Request,body:ChatRequest,key=Depends(auth)):
 if body.max_tokens>s.max_tokens:raise HTTPException(400,'max_tokens exceeds configured limit')
 record_usage(key,'/v1/chat/completions')
 try:r=await get_provider().chat(body.model_dump(exclude_none=True))
 except Exception as e:logging.warning('Inference failed (%s)',type(e).__name__);raise HTTPException(503,'Inference backend unavailable or request failed')
 if body.stream:
  q=r['choices'][0];chunk={'id':r['id'],'object':'chat.completion.chunk','created':r['created'],'model':r['model'],'choices':[{'index':0,'delta':{'role':'assistant','content':q['message']['content']},'finish_reason':None}]}
  async def events():yield 'data: '+json.dumps(chunk)+'\n\n';yield 'data: [DONE]\n\n'
  return StreamingResponse(events(),media_type='text/event-stream')
 return r
@app.get('/admin/usage')
async def usage(_=Depends(admin)):return usage_summary()
@app.post('/admin/keys')
async def new_key(label:str='API key',_=Depends(admin)):return create_key(label)
@app.delete('/admin/keys/{key_id}')
async def delete_key(key_id:str,_=Depends(admin)):
 if not revoke_key(key_id):raise HTTPException(404,'Key not found')
 return {'revoked':True}
@app.get('/admin/status')
async def status(_=Depends(admin)):return {'backend':s.inference_backend,'model':s.model_name,'models':get_provider().models()}


