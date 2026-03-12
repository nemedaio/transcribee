from fastapi import APIRouter, Form, HTTPException, Query, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse, Response

from lnkdn_transcripts.logging import get_logger
from lnkdn_transcripts.services.auth import (
    AccessApprovalRequiredError,
    GoogleAuthConfigurationError,
    UnauthorizedGoogleAccountError,
)
from lnkdn_transcripts.storage.models import AccessAuditAction, AccessRole, AccessStatus
from lnkdn_transcripts.templates import templates

logger = get_logger(__name__)

router = APIRouter(prefix="/auth", tags=["auth"])


def _require_admin(request: Request):
    current_user = request.app.state.auth_service.current_user(request)
    if current_user is None or not current_user.is_admin:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Admin access required")
    return current_user


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
    except AccessApprovalRequiredError as exc:
        auth_service.logout(request)
        logger.info("auth.access.denied error=%s", exc)
        return templates.TemplateResponse(
            request,
            "access_requested.html",
            {
                "request": request,
                "page_title": "Access pending",
                "message": str(exc),
            },
            status_code=status.HTTP_403_FORBIDDEN,
        )
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
    except AccessApprovalRequiredError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    except UnauthorizedGoogleAccountError as exc:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(exc)) from exc
    return RedirectResponse(
        url=auth_service.normalize_next_url(next),
        status_code=status.HTTP_303_SEE_OTHER,
    )


@router.get("/access", response_class=HTMLResponse)
def access_admin(
    request: Request,
    audit_account_email: str | None = Query(None),
    audit_action: AccessAuditAction | None = Query(None),
    audit_search: str | None = Query(None),
) -> HTMLResponse:
    current_user = _require_admin(request)
    access_repository = request.app.state.access_repository
    return templates.TemplateResponse(
        request,
        "access_admin.html",
        {
            "request": request,
            "page_title": "Access control",
            "pending_accounts": access_repository.list_accounts([AccessStatus.PENDING]),
            "approved_accounts": access_repository.list_accounts([AccessStatus.APPROVED]),
            "revoked_accounts": access_repository.list_accounts([AccessStatus.REVOKED]),
            "recent_audit_events": access_repository.list_audit_events(
                limit=25,
                account_email=audit_account_email,
                actions=[audit_action] if audit_action else None,
                query=audit_search,
            ),
            "audit_action_options": list(AccessAuditAction),
            "audit_account_email": audit_account_email or "",
            "audit_action": audit_action.value if audit_action else "",
            "audit_search": audit_search or "",
            "bootstrap_admin_emails": sorted(request.app.state.auth_service.admin_emails),
            "current_admin_email": current_user.email,
        },
    )


@router.post("/access/approve")
def approve_access(
    request: Request,
    email: str = Form(...),
    role: AccessRole = Form(AccessRole.MEMBER),
) -> RedirectResponse:
    current_user = _require_admin(request)
    approved = request.app.state.access_repository.approve_account(
        email=email,
        approved_by_email=current_user.email,
        role=role,
    )
    logger.info("auth.access.approved email=%s role=%s by=%s", approved.email, approved.role.value, current_user.email)
    return RedirectResponse(url="/auth/access", status_code=status.HTTP_303_SEE_OTHER)


@router.post("/access/revoke")
def revoke_access(request: Request, email: str = Form(...)) -> RedirectResponse:
    current_user = _require_admin(request)
    revoked = request.app.state.access_repository.revoke_account(
        email=email,
        actor_email=current_user.email,
    )
    logger.info("auth.access.revoked email=%s by=%s", revoked.email, current_user.email)
    return RedirectResponse(url="/auth/access", status_code=status.HTTP_303_SEE_OTHER)
