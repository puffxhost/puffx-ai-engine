import hashlib,secrets,sqlite3,time
from pathlib import Path
from core.config import get_settings
def _db():
 d=get_settings().database_url
 if not d.startswith('sqlite:///'):raise RuntimeError('Only SQLite DATABASE_URL values are supported; configure sqlite:///...')
 p=d.removeprefix('sqlite:///');Path(p).parent.mkdir(parents=True,exist_ok=True);c=sqlite3.connect(p);c.execute('CREATE TABLE IF NOT EXISTS keys(hash TEXT PRIMARY KEY,label TEXT,created REAL,revoked INTEGER DEFAULT 0)');c.execute('CREATE TABLE IF NOT EXISTS usage(id INTEGER PRIMARY KEY,key_hash TEXT,endpoint TEXT,created REAL)');c.commit();return c
def digest(k):return hashlib.sha256(k.encode()).hexdigest()
def valid_key(k):
 if not k:return False
 s=get_settings()
 if s.api_key and secrets.compare_digest(k,s.api_key):return True
 with _db() as c:return c.execute('SELECT 1 FROM keys WHERE hash=? AND revoked=0',(digest(k),)).fetchone() is not None
def create_key(label='API key'):
 k='pfx_'+secrets.token_urlsafe(32);h=digest(k)
 with _db() as c:c.execute('INSERT INTO keys(hash,label,created) VALUES(?,?,?)',(h,label,time.time()))
 return {'id':h[:12],'key':k,'label':label}
def revoke_key(kid):
 if not isinstance(kid,str) or len(kid)!=12 or any(ch not in '0123456789abcdef' for ch in kid):return False
 with _db() as c:return c.execute('UPDATE keys SET revoked=1 WHERE substr(hash,1,12)=?',(kid,)).rowcount>0
def record_usage(k,e):
 with _db() as c:c.execute('INSERT INTO usage(key_hash,endpoint,created) VALUES(?,?,?)',(digest(k),e,time.time()))
def usage_summary():
 with _db() as c:n=c.execute('SELECT COUNT(*) FROM usage').fetchone()[0];r=c.execute('SELECT endpoint,created FROM usage ORDER BY id DESC LIMIT 20').fetchall();ks=c.execute('SELECT substr(hash,1,12),label,created,revoked FROM keys').fetchall()
 return {'total_requests':n,'recent':[{'endpoint':e,'created':t} for e,t in r],'keys':[{'id':i,'label':l,'created':t,'revoked':bool(x)} for i,l,t,x in ks]}
