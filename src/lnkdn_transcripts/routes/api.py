from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel

from lnkdn_transcripts.services.provider_urls import InvalidVideoUrlError
from lnkdn_transcripts.storage.models import JobRead

router = APIRouter(prefix="/api", tags=["api"])


class JobSubmission(BaseModel):
    video_url: str


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


@router.get("/jobs", response_model=list[JobRead])
def list_jobs(request: Request) -> list[JobRead]:
    jobs = _job_service(request).list_recent_jobs()
    return [JobRead.model_validate(job) for job in jobs]


@router.get("/jobs/{job_id}", response_model=JobRead)
def get_job(job_id: str, request: Request) -> JobRead:
    job = _job_service(request).get_job(job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")
    return JobRead.model_validate(job)
