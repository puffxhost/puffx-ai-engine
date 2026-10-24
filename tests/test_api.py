import os
os.environ.update(INFERENCE_BACKEND='mock',API_KEY='test-secret',ADMIN_PASSWORD='admin-secret',DATABASE_URL='sqlite:///./test-puffx.db')
from fastapi.testclient import TestClient
from api.app import app
from core.security import revoke_key

c=TestClient(app)

def test_health():
    assert c.get('/health').json()['status']=='ok'

def test_auth():
    assert c.get('/v1/models').status_code==401

def test_chat():
    r=c.post('/v1/chat/completions',headers={'Authorization':'Bearer test-secret'},json={'messages':[{'role':'user','content':'hello'}]})
    assert r.status_code==200 and r.json()['object']=='chat.completion'

def test_invalid():
    assert c.post('/v1/chat/completions',headers={'Authorization':'Bearer test-secret'},json={'messages':[]}).status_code==422

def test_admin_auth():
    assert c.get('/admin/usage').status_code==401

def test_oversized_request_is_rejected():
    body=b'{"x":"'+b'a'*(1024*1024)+b'"}'
    r=c.post('/v1/chat/completions',headers={'Authorization':'Bearer test-secret','Content-Type':'application/json'},content=body)
    assert r.status_code==413

def test_revocation_rejects_wildcards():
    assert revoke_key('%') is False
    assert revoke_key('___________%') is False
