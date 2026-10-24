import sys
from pathlib import Path
APP=Path(__file__).resolve().parents[2]
sys.path.insert(0,str(APP))
from api.app import app as application
