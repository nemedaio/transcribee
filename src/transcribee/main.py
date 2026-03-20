from contextlib import asynccontextmanager
from collections.abc import Callable
from urllib.parse import urlencode

from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.middleware.sessions import SessionMiddleware
from starlette.responses import JSONResponse, RedirectResponse, Response

from transcribee.config import Settings, settings
from transcribee.logging import configure_logging, get_logger
from transcribee.routes.auth import router as auth_router
from transcribee.routes.api import router as api_router
from transcribee.routes.health import router as health_router
from transcribee.routes.web import router as web_router
from transcribee.services.artifacts import ArtifactCleanupService
from transcribee.services.auth import GoogleAuthService
from transcribee.services.audio import AudioPreparer, FfmpegAudioPreparer
from transcribee.services.background_jobs import JobRunner, ThreadedJobRunner
from transcribee.services.exporters import TranscriptExporter
from transcribee.services.fetcher import MediaFetcher, YtDlpMediaFetcher
from transcribee.services.transcriber import MediaTranscriber, create_transcriber
from transcribee.services.jobs import JobService
from transcribee.storage.repo import (
    AccessRepository,
    JobRepository,
    create_db_and_tables,
    create_engine,
)

logger = get_logger(__name__)


class AuthenticationMiddleware(BaseHTTPMiddleware):
    def __init__(self, app, auth_service: GoogleAuthService):
        super().__init__(app)
        self.auth_service = auth_service

    async def dispatch(self, request: Request, call_next) -> Response:
        current_user = self.auth_service.current_user(request)
        request.state.current_user = current_user
        if not self.auth_service.requires_auth(request.url.path):
            return await call_next(request)
        if current_user is not None:
            return await call_next(request)

        logger.info("auth.required path=%s", request.url.path)
        if request.url.path.startswith("/api/"):
            return JSONResponse({"detail": "Authentication required"}, status_code=401)

        next_path = request.url.path
        if request.url.query:
            next_path = f"{next_path}?{request.url.query}"
        return RedirectResponse(
            url=f"/auth/login?{urlencode({'next': next_path})}",
            status_code=303,
        )


def create_app(
    app_settings: Settings | None = None,
    media_fetcher: MediaFetcher | None = None,
    audio_preparer: AudioPreparer | None = None,
    media_transcriber: MediaTranscriber | None = None,
    job_runner_factory: Callable[[Callable[[str], None]], JobRunner] | None = None,
) -> FastAPI:
    resolved_settings = app_settings or settings
    configure_logging(resolved_settings.log_level)
    auth_service = GoogleAuthService(resolved_settings)
    engine = create_engine(resolved_settings)
    resolved_media_fetcher = media_fetcher or YtDlpMediaFetcher(resolved_settings)
    resolved_audio_preparer = audio_preparer or FfmpegAudioPreparer(resolved_settings)
    resolved_media_transcriber = media_transcriber or create_transcriber(resolved_settings)

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        create_db_and_tables(engine)
        logger.info(
            "app.startup database_ready=%s auth_enabled=%s",
            resolved_settings.database_url or resolved_settings.data_dir,
            resolved_settings.auth_enabled,
        )
        yield
        app.state.job_runner.close()

    app = FastAPI(title=resolved_settings.app_name, lifespan=lifespan)
    app.add_middleware(AuthenticationMiddleware, auth_service=auth_service)
    if resolved_settings.auth_enabled:
        app.add_middleware(
            SessionMiddleware,
            secret_key=resolved_settings.session_secret_key,
            session_cookie=resolved_settings.session_cookie_name,
            same_site="lax",
            https_only=resolved_settings.session_https_only,
        )
    app.state.settings = resolved_settings
    app.state.auth_service = auth_service
    app.state.access_repository = AccessRepository(engine)
    app.state.job_repository = JobRepository(engine)
    app.state.media_fetcher = resolved_media_fetcher
    app.state.audio_preparer = resolved_audio_preparer
    app.state.media_transcriber = resolved_media_transcriber
    app.state.artifact_cleanup_service = ArtifactCleanupService(resolved_settings)
    app.state.transcript_exporter = TranscriptExporter()
    app.state.job_service = JobService(
        app.state.job_repository,
        resolved_media_fetcher,
        resolved_audio_preparer,
        resolved_media_transcriber,
        app.state.artifact_cleanup_service,
    )
    app.state.job_runner = (
        job_runner_factory(app.state.job_service.process_job)
        if job_runner_factory is not None
        else ThreadedJobRunner(app.state.job_service.process_job)
    )

    app.include_router(health_router)
    app.include_router(auth_router)
    app.include_router(api_router)
    app.include_router(web_router)
    app.mount("/static", StaticFiles(directory="src/transcribee/static"), name="static")
    return app


app = create_app()
