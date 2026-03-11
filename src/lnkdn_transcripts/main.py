from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles

from lnkdn_transcripts.config import Settings, settings
from lnkdn_transcripts.logging import configure_logging, get_logger
from lnkdn_transcripts.routes.api import router as api_router
from lnkdn_transcripts.routes.health import router as health_router
from lnkdn_transcripts.routes.web import router as web_router
from lnkdn_transcripts.services.jobs import JobService
from lnkdn_transcripts.storage.repo import JobRepository, create_db_and_tables, create_engine

logger = get_logger(__name__)


def create_app(app_settings: Settings | None = None) -> FastAPI:
    resolved_settings = app_settings or settings
    configure_logging(resolved_settings.log_level)
    engine = create_engine(resolved_settings)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        create_db_and_tables(engine)
        logger.info("app.startup database_ready=%s", resolved_settings.database_url or resolved_settings.data_dir)
        yield

    app = FastAPI(title=resolved_settings.app_name, lifespan=lifespan)
    app.state.settings = resolved_settings
    app.state.job_repository = JobRepository(engine)
    app.state.job_service = JobService(app.state.job_repository)
    app.include_router(health_router)
    app.include_router(api_router)
    app.include_router(web_router)
    app.mount("/static", StaticFiles(directory="src/lnkdn_transcripts/static"), name="static")
    return app


app = create_app()
