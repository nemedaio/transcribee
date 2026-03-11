from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from lnkdn_transcripts.config import settings
from lnkdn_transcripts.routes.health import router as health_router
from lnkdn_transcripts.routes.web import router as web_router

app = FastAPI(title=settings.app_name)
app.include_router(health_router)
app.include_router(web_router)
app.mount("/static", StaticFiles(directory="src/lnkdn_transcripts/static"), name="static")
