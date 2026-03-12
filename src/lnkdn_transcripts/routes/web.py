from fastapi import APIRouter, Form, HTTPException, Request, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from lnkdn_transcripts.services.jobs import InvalidVideoUrlError

templates = Jinja2Templates(directory="src/lnkdn_transcripts/templates")
router = APIRouter(tags=["web"])


@router.get("/", response_class=HTMLResponse)
def index(request: Request) -> HTMLResponse:
    recent_jobs = request.app.state.job_service.list_recent_jobs()
    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "request": request,
            "page_title": request.app.state.settings.app_name,
            "status": "Submit a URL to fetch media locally and prepare it for transcription.",
            "recent_jobs": recent_jobs,
        },
    )


@router.post("/jobs")
def submit_job(request: Request, video_url: str = Form(...)) -> RedirectResponse:
    try:
        job = request.app.state.job_service.create_job(video_url)
    except InvalidVideoUrlError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc)) from exc
    return RedirectResponse(url=f"/jobs/{job.id}", status_code=status.HTTP_303_SEE_OTHER)


@router.get("/jobs/{job_id}", response_class=HTMLResponse)
def job_detail(request: Request, job_id: str) -> HTMLResponse:
    job = request.app.state.job_service.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")

    return templates.TemplateResponse(
        request,
        "job.html",
        {
            "request": request,
            "page_title": f"Job {job.id}",
            "job": job,
        },
    )
