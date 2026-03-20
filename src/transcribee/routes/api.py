import csv
from io import StringIO

from fastapi import APIRouter, HTTPException, Query, Request, status
from fastapi.responses import Response
from pydantic import BaseModel

from transcribee.routes.dependencies import require_admin
from transcribee.services.provider_urls import InvalidVideoUrlError
from transcribee.services.jobs import InvalidRetryError
from transcribee.storage.models import (
    AccessAccountRead,
    AccessAuditAction,
    AccessAuditCleanupSummary,
    AccessAuditEventRead,
    AccessRole,
    AccessStatus,
    CleanupSummary,
    DashboardCounts,
    JobRead,
)

router = APIRouter(prefix="/api", tags=["api"])


class JobSubmission(BaseModel):
    video_url: str


class BatchJobSubmission(BaseModel):
    video_urls: list[str]


class AccessApprovalPayload(BaseModel):
    role: AccessRole = AccessRole.MEMBER


def _job_service(request: Request):
    return request.app.state.job_service


@router.post("/jobs", response_model=JobRead, status_code=status.HTTP_202_ACCEPTED)
def create_job(payload: JobSubmission, request: Request) -> JobRead:
    try:
        job = _job_service(request).create_job(payload.video_url)
        request.app.state.job_runner.enqueue(job.id)
    except InvalidVideoUrlError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    current_job = _job_service(request).get_job(job.id)
    return JobRead.model_validate(current_job)


@router.post("/jobs/batch", response_model=list[JobRead], status_code=status.HTTP_202_ACCEPTED)
def create_batch_jobs(payload: BatchJobSubmission, request: Request) -> list[JobRead]:
    if len(payload.video_urls) > 20:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Batch limit is 20 URLs per request",
        )
    results: list[JobRead] = []
    for url in payload.video_urls:
        try:
            job = _job_service(request).create_job(url)
            request.app.state.job_runner.enqueue(job.id)
            current_job = _job_service(request).get_job(job.id)
            results.append(JobRead.model_validate(current_job))
        except InvalidVideoUrlError:
            continue
    if not results:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="No valid URLs were submitted",
        )
    return results


@router.get("/jobs", response_model=list[JobRead])
def list_jobs(request: Request) -> list[JobRead]:
    jobs = _job_service(request).list_recent_jobs()
    return [JobRead.model_validate(job) for job in jobs]


@router.get("/dashboard", response_model=DashboardCounts)
def dashboard(request: Request) -> DashboardCounts:
    return _job_service(request).dashboard_counts()


@router.get("/jobs/{job_id}", response_model=JobRead)
def get_job(job_id: str, request: Request) -> JobRead:
    job = _job_service(request).get_job(job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    return JobRead.model_validate(job)


@router.post("/jobs/{job_id}/retry", response_model=JobRead, status_code=status.HTTP_202_ACCEPTED)
def retry_job(job_id: str, request: Request) -> JobRead:
    try:
        job = _job_service(request).retry_job(job_id)
        request.app.state.job_runner.enqueue(job.id)
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found") from exc
    except InvalidRetryError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc
    refreshed = _job_service(request).get_job(job.id)
    return JobRead.model_validate(refreshed)


@router.post("/maintenance/cleanup-artifacts", response_model=CleanupSummary)
def cleanup_artifacts(request: Request) -> CleanupSummary:
    return _job_service(request).cleanup_expired_artifacts()


@router.get("/access/accounts", response_model=list[AccessAccountRead])
def list_access_accounts(
    request: Request,
    status_filters: list[AccessStatus] | None = Query(None, alias="status"),
) -> list[AccessAccountRead]:
    require_admin(request)
    statuses = status_filters or [AccessStatus.PENDING, AccessStatus.APPROVED, AccessStatus.REVOKED]
    accounts = request.app.state.access_repository.list_accounts(statuses=statuses)
    return [AccessAccountRead.model_validate(account) for account in accounts]


@router.get("/access/audit", response_model=list[AccessAuditEventRead])
def list_access_audit_events(
    request: Request,
    account_email: str | None = Query(None),
    actions: list[AccessAuditAction] | None = Query(None, alias="action"),
    search: str | None = Query(None),
    limit: int = Query(100, ge=1, le=500),
) -> list[AccessAuditEventRead]:
    require_admin(request)
    events = request.app.state.access_repository.list_audit_events(
        account_email=account_email,
        actions=actions,
        query=search,
        limit=limit,
    )
    return [AccessAuditEventRead.model_validate(event) for event in events]


@router.get("/access/audit/export.csv")
def export_access_audit_events(
    request: Request,
    account_email: str | None = Query(None),
    actions: list[AccessAuditAction] | None = Query(None, alias="action"),
    search: str | None = Query(None),
    limit: int = Query(500, ge=1, le=1000),
) -> Response:
    require_admin(request)
    events = request.app.state.access_repository.list_audit_events(
        account_email=account_email,
        actions=actions,
        query=search,
        limit=limit,
    )
    buffer = StringIO()
    writer = csv.writer(buffer)
    writer.writerow(
        [
            "created_at",
            "account_email",
            "action",
            "actor_email",
            "resulting_status",
            "resulting_role",
            "note",
        ]
    )
    for event in events:
        writer.writerow(
            [
                event.created_at.isoformat(),
                event.account_email,
                event.action.value,
                event.actor_email or "",
                event.resulting_status.value if event.resulting_status else "",
                event.resulting_role.value if event.resulting_role else "",
                event.note or "",
            ]
        )
    return Response(
        content=buffer.getvalue(),
        media_type="text/csv; charset=utf-8",
        headers={"Content-Disposition": 'attachment; filename="access-audit.csv"'},
    )


@router.post("/access/audit/cleanup", response_model=AccessAuditCleanupSummary)
def cleanup_access_audit_events(request: Request) -> AccessAuditCleanupSummary:
    require_admin(request)
    retention_days = request.app.state.settings.access_audit_retention_days
    return request.app.state.access_repository.cleanup_audit_events(retention_days=retention_days)


@router.post("/access/accounts/{account_email}/approve", response_model=AccessAccountRead)
def approve_access_account(
    account_email: str,
    payload: AccessApprovalPayload,
    request: Request,
) -> AccessAccountRead:
    current_user = require_admin(request)
    account = request.app.state.access_repository.approve_account(
        email=account_email,
        approved_by_email=current_user.email,
        role=payload.role,
    )
    return AccessAccountRead.model_validate(account)


@router.post("/access/accounts/{account_email}/revoke", response_model=AccessAccountRead)
def revoke_access_account(account_email: str, request: Request) -> AccessAccountRead:
    current_user = require_admin(request)
    try:
        account = request.app.state.access_repository.revoke_account(
            account_email,
            actor_email=current_user.email,
        )
    except LookupError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Access account not found") from exc
    return AccessAccountRead.model_validate(account)
