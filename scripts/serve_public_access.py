"""Local verification server, same-origin built frontend and API."""
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[1]))
from fastapi.staticfiles import StaticFiles
from api.app.main import app
app.mount('/',StaticFiles(directory=Path(__file__).resolve().parents[1]/'web/dist',html=True),name='frontend')
