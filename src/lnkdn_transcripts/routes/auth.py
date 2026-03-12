from fastapi import APIRouter, HTTPException, Query, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse, Response

from lnkdn_transcripts.logging import get_logger
from lnkdn_transcripts.services.auth import (
    GoogleAuthConfigurationError,
    UnauthorizedGoogleAccountError,
)
from lnkdn_transcripts.templates import templates

logger = get_logger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])


@router.get("/login", response_class=HTMLResponse)
def login_page(request: Request, next: str = Query("/", alias="next")) -> Response:
    auth_service = request.app.state.auth_service
    if not request.app.state.settings.auth_enabled:
        return RedirectResponse(url="/", status_code=status.HTTP_303_SEE_OTHER)

    current_user = auth_service.current_user(request)
    if current_user is not None:
        return RedirectResponse(
            url=auth_service.normalize_next_url(next),
            status_code=status.HTTP_303_SEE_OTHER,
        )

    return templates.TemplateResponse(
        request,
        "login.html",
        {
            "request": request,
            **auth_service.build_login_context(next),
        },
    )


@router.get("/google")
async def login_with_google(
    request: Request,
    next: str = Query("/", alias="next"),
) -> Response:
    if not request.app.state.settings.auth_enabled:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    auth_service = request.app.state.auth_service
    try:
        return await auth_service.begin_google_login(request, next)
    except GoogleAuthConfigurationError as exc:
        logger.warning("auth.google.misconfigured error=%s", exc)
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc


@router.get("/callback", name="auth_callback", response_class=HTMLResponse)
async def auth_callback(request: Request) -> Response:
    if not request.app.state.settings.auth_enabled:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    auth_service = request.app.state.auth_service
    try:
        await auth_service.complete_google_login(request)
    except UnauthorizedGoogleAccountError as exc:
        auth_service.logout(request)
        logger.warning("auth.google.rejected error=%s", exc)
        return templates.TemplateResponse(
            request,
            "login.html",
            {
                "request": request,
                **auth_service.build_login_context("/", error_message=str(exc)),
            },
            status_code=status.HTTP_403_FORBIDDEN,
        )
    except GoogleAuthConfigurationError as exc:
        logger.warning("auth.google.callback_misconfigured error=%s", exc)
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail=str(exc)) from exc

    return RedirectResponse(
        url=auth_service.consume_next_url(request, fallback="/"),
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.get("/logout")
def logout(request: Request) -> RedirectResponse:
    if not request.app.state.settings.auth_enabled:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    request.app.state.auth_service.logout(request)
    return RedirectResponse(url="/auth/login", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/test-login")
def test_login(
    request: Request,
    email: str = Query("tester@example.com"),
    name: str | None = Query(None),
    next: str = Query("/", alias="next"),
) -> RedirectResponse:
    auth_service = request.app.state.auth_service
    if not request.app.state.settings.auth_enabled or not request.app.state.settings.auth_test_mode:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Not found")
    try:
        auth_service.test_login(request, email=email, name=name)
    except UnauthorizedGoogleAccountError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    return RedirectResponse(
        url=auth_service.normalize_next_url(next),
        status_code=status.HTTP_303_SEE_OTHER,
    )
