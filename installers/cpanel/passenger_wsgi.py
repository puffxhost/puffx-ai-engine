import sys
from pathlib import Path
APP=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(APP))
from a2wsgi import ASGIMiddleware
from api.app import app as asgi_application
application=ASGIMiddleware(asgi_application)
