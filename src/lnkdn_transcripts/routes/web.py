from fastapi import APIRouter, Form, HTTPException, Request, Response, status
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from lnkdn_transcripts.services.exporters import IncompleteTranscriptError, UnsupportedExportFormatError
from lnkdn_transcripts.services.jobs import InvalidVideoUrlError

templates = Jinja2Templates(directory="src/lnkdn_transcripts/templates")
router = APIRouter(tags=["web"])


@router.get("/", response_class=HTMLResponse)
def index(request: Request) -> HTMLResponse:
    recent_jobs = request.app.state.job_service.list_recent_jobs(limit=5)
    return templates.TemplateResponse(
        request,
        "index.html",
        {
            "request": request,
            "page_title": request.app.state.settings.app_name,
            "status": "Submit a URL to fetch media locally and transcribe it with Whisper.",
            "recent_jobs": recent_jobs,
        },
    )


@router.get("/history", response_class=HTMLResponse)
def history(request: Request) -> HTMLResponse:
    recent_jobs = request.app.state.job_service.list_recent_jobs(limit=50)
    return templates.TemplateResponse(
        request,
        "history.html",
        {
            "request": request,
            "page_title": "Transcript History",
            "jobs": recent_jobs,
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


@router.get("/jobs/{job_id}/exports/{format_name}")
def export_job(request: Request, job_id: str, format_name: str) -> Response:
    job = request.app.state.job_service.get_job(job_id)
    if job is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Job not found")

    try:
        exported = request.app.state.transcript_exporter.export(job, format_name)
    except UnsupportedExportFormatError as exc:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Unsupported export format") from exc
    except IncompleteTranscriptError as exc:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(exc)) from exc

    return Response(
        content=exported.content,
        media_type=exported.media_type,
        headers={"Content-Disposition": f'attachment; filename=\"{exported.filename}\"'},
    )
