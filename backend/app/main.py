"""FastAPI application for subtitle localization."""

import os
import json
from typing import Optional

# Load environment variables from .env file
from pathlib import Path

def _load_env_file():
    """Load environment variables from .env file."""
    env_path = Path(__file__).parent.parent / ".env"
    if env_path.exists():
        with open(env_path) as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    os.environ.setdefault(key.strip(), value.strip())

_load_env_file()

from fastapi import FastAPI, File, Form, UploadFile, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import PlainTextResponse, JSONResponse

from .models import (
    JobRequest,
    JobStatusResponse,
    JobResultResponse,
    JobConstraints,
    SubtitleFormat,
    MultiTargetJobState,
    MultiTargetJobStatusResponse,
    JobStatus,
    ReviewStatus,
)
from .database import get_repository, init_db
from .translation_memory import get_translation_memory
from .job_runner import job_runner
from .export import export_srt, export_vtt


app = FastAPI(
    title="Auto Subtitle Localization API",
    description="API for translating and localizing subtitle files",
    version="1.0.0"
)

@app.on_event("startup")
async def startup_event():
    """Reset the translation provider on startup to pick up env vars."""
    print("=" * 60)
    print("SUBTITLE TRANSLATION API - Starting up...")
    print("=" * 60)
    
    # Initialize database
    try:
        init_db()
        print("[STARTUP] Database initialized")
    except Exception as e:
        print(f"[WARN] Database initialization failed: {e}")
    
    job_runner._provider = None  # Force re-initialization
    provider = job_runner.get_provider()
    print(f"[STARTUP] Active provider: {provider.get_provider_name()}")
    if "Mock" in provider.get_provider_name():
        print("")
        print("⚠️  WARNING: Using Mock provider - NO ACTUAL TRANSLATION!")
        print("   To enable real translation, create backend/.env with:")
        print("   OPENAI_API_KEY=sk-your-key-here")
        print("")
    print("=" * 60)

# CORS middleware for frontend
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:5174", "http://localhost:3000", "http://127.0.0.1:5173", "http://127.0.0.1:5174"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/")
async def root():
    """Health check endpoint."""
    return {"status": "ok", "service": "subtitle-localization"}


@app.post("/api/jobs")
async def create_job(
    file: UploadFile = File(...),
    source_lang: str = Form(default="en"),
    target_lang: str = Form(default="he"),
    format: str = Form(default="srt"),
    max_lines: int = Form(default=2),
    max_chars_per_line: int = Form(default=42),
    max_cps: float = Form(default=17.0),
    min_duration_ms: int = Form(default=500),
    glossary: Optional[str] = Form(default=None),
    dry_run: bool = Form(default=False),
):
    """
    Create a new translation job.
    
    Accepts multipart form data with the subtitle file and configuration.
    """
    # Validate file extension
    filename = file.filename or "subtitle.srt"
    ext = filename.lower().split('.')[-1]
    
    if ext not in ['srt', 'vtt']:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file format: {ext}. Supported: srt, vtt"
        )
    
    # Read file content
    content = await file.read()
    try:
        file_content = content.decode('utf-8')
    except UnicodeDecodeError:
        try:
            file_content = content.decode('latin-1')
        except UnicodeDecodeError:
            raise HTTPException(
                status_code=400,
                detail="Could not decode file. Please use UTF-8 encoding."
            )
    
    # Parse glossary if provided
    glossary_dict = {}
    if glossary:
        try:
            glossary_dict = json.loads(glossary)
        except json.JSONDecodeError:
            raise HTTPException(
                status_code=400,
                detail="Invalid glossary JSON format"
            )
    
    # Create constraints
    constraints = JobConstraints(
        max_lines=max_lines,
        max_chars_per_line=max_chars_per_line,
        max_cps=max_cps,
        min_duration_ms=min_duration_ms
    )
    
    # Create job request
    request = JobRequest(
        source_lang=source_lang,
        target_lang=target_lang,
        format=SubtitleFormat(ext),
        constraints=constraints,
        glossary=glossary_dict,
        dry_run=dry_run
    )
    
    # Create and start job
    job_id = await job_runner.create_job(
        request=request,
        file_content=file_content,
        filename=filename
    )
    
    return {"job_id": job_id}


@app.post("/api/jobs/multi")
async def create_multi_target_job(
    file: UploadFile = File(...),
    source_lang: str = Form(default="en"),
    target_langs: str = Form(...),  # Comma-separated: "he,es,fr"
    format: str = Form(default="srt"),
    max_lines: int = Form(default=2),
    max_chars_per_line: int = Form(default=42),
    max_cps: float = Form(default=17.0),
    min_duration_ms: int = Form(default=500),
    glossary: Optional[str] = Form(default=None),
    dry_run: bool = Form(default=False),
):
    """
    Create translation jobs for multiple target languages.
    
    Accepts a comma-separated list of target languages (e.g., "he,es,fr").
    Creates a child job for each target language.
    """
    # Parse target languages
    langs = [l.strip() for l in target_langs.split(",") if l.strip()]
    if not langs:
        raise HTTPException(
            status_code=400,
            detail="At least one target language is required"
        )
    
    # Validate file extension
    filename = file.filename or "subtitle.srt"
    ext = filename.lower().split('.')[-1]
    
    if ext not in ['srt', 'vtt']:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported file format: {ext}. Supported: srt, vtt"
        )
    
    # Read file content
    content = await file.read()
    try:
        file_content = content.decode('utf-8')
    except UnicodeDecodeError:
        try:
            file_content = content.decode('latin-1')
        except UnicodeDecodeError:
            raise HTTPException(
                status_code=400,
                detail="Could not decode file. Please use UTF-8 encoding."
            )
    
    # Parse glossary if provided (per-language format: {"he": {...}, "es": {...}})
    glossary_dict = {}
    if glossary:
        try:
            glossary_dict = json.loads(glossary)
        except json.JSONDecodeError:
            raise HTTPException(
                status_code=400,
                detail="Invalid glossary JSON format"
            )
    
    # Create constraints
    constraints = JobConstraints(
        max_lines=max_lines,
        max_chars_per_line=max_chars_per_line,
        max_cps=max_cps,
        min_duration_ms=min_duration_ms
    )
    
    # Create parent job ID
    import uuid
    parent_job_id = str(uuid.uuid4())
    
    # Create child job for each target language
    child_jobs = {}
    for lang in langs:
        # Get language-specific glossary if available
        lang_glossary = glossary_dict.get(lang, {})
        
        request = JobRequest(
            source_lang=source_lang,
            target_lang=lang,
            format=SubtitleFormat(ext),
            constraints=constraints,
            glossary=lang_glossary,
            dry_run=dry_run
        )
        
        job_id = await job_runner.create_job(
            request=request,
            file_content=file_content,
            filename=filename
        )
        child_jobs[lang] = job_id
    
    # Store multi-target job state
    multi_job = MultiTargetJobState(
        parent_job_id=parent_job_id,
        child_jobs=child_jobs,
        status=JobStatus.PROCESSING,
        progress=0.0,
        source_filename=filename
    )
    job_runner.multi_jobs[parent_job_id] = multi_job
    
    return {
        "parent_job_id": parent_job_id,
        "child_jobs": child_jobs,
        "target_langs": langs
    }


@app.get("/api/jobs/multi/{parent_job_id}")
async def get_multi_target_job_status(parent_job_id: str) -> MultiTargetJobStatusResponse:
    """Get the status of a multi-target translation job."""
    multi_job = job_runner.multi_jobs.get(parent_job_id)
    
    if not multi_job:
        raise HTTPException(status_code=404, detail="Multi-target job not found")
    
    # Get status of each child job
    child_statuses = {}
    total_progress = 0.0
    all_completed = True
    any_failed = False
    
    for lang, job_id in multi_job.child_jobs.items():
        child_job = await job_runner.get_job(job_id)
        if child_job:
            child_statuses[lang] = JobStatusResponse(
                job_id=child_job.job_id,
                status=child_job.status,
                progress=child_job.progress,
                error=child_job.error,
                qc_summary=child_job.qc_report.summary if child_job.qc_report else None
            )
            total_progress += child_job.progress
            if child_job.status != JobStatus.COMPLETED:
                all_completed = False
            if child_job.status == JobStatus.FAILED:
                any_failed = True
    
    # Calculate overall status
    num_jobs = len(multi_job.child_jobs)
    avg_progress = total_progress / num_jobs if num_jobs > 0 else 0.0
    
    if any_failed:
        overall_status = JobStatus.FAILED
    elif all_completed:
        overall_status = JobStatus.COMPLETED
    else:
        overall_status = JobStatus.PROCESSING
    
    return MultiTargetJobStatusResponse(
        parent_job_id=parent_job_id,
        status=overall_status,
        progress=avg_progress,
        child_jobs=child_statuses
    )


@app.get("/api/jobs/{job_id}")
async def get_job_status(job_id: str) -> JobStatusResponse:
    """Get the status and progress of a job."""
    job = await job_runner.get_job(job_id)
    
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    return JobStatusResponse(
        job_id=job.job_id,
        status=job.status,
        progress=job.progress,
        error=job.error,
        qc_summary=job.qc_report.summary if job.qc_report else None
    )


@app.get("/api/jobs/{job_id}/result")
async def get_job_result(job_id: str) -> JobResultResponse:
    """Get the full result of a completed job."""
    job = await job_runner.get_job(job_id)
    
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    if job.status.value != "completed":
        raise HTTPException(
            status_code=400,
            detail=f"Job not completed. Status: {job.status.value}"
        )
    
    if not job.qc_report:
        raise HTTPException(status_code=500, detail="QC report not available")
    
    return JobResultResponse(
        job_id=job.job_id,
        segments=job.translated_segments,
        qc_report=job.qc_report
    )


@app.get("/api/jobs/{job_id}/download/{format}")
async def download_subtitle(job_id: str, format: str):
    """Download the translated subtitle file in specified format."""
    job = await job_runner.get_job(job_id)
    
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    if job.status.value != "completed":
        raise HTTPException(
            status_code=400,
            detail=f"Job not completed. Status: {job.status.value}"
        )
    
    format = format.lower()
    if format not in ['srt', 'vtt']:
        raise HTTPException(
            status_code=400,
            detail=f"Unsupported format: {format}. Supported: srt, vtt"
        )
    
    # Generate subtitle content
    segments = job.translated_segments
    if format == 'srt':
        content = export_srt(segments, use_translated=True)
        media_type = "text/plain"
    else:
        content = export_vtt(segments, use_translated=True)
        media_type = "text/vtt"
    
    # Generate filename
    base_name = job.source_filename.rsplit('.', 1)[0]
    target_lang = job.request.target_lang
    filename = f"{base_name}_{target_lang}.{format}"
    
    return PlainTextResponse(
        content=content,
        media_type=media_type,
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"'
        }
    )


@app.get("/api/jobs/{job_id}/qc-report")
async def download_qc_report(job_id: str):
    """Download the QC report as JSON."""
    job = await job_runner.get_job(job_id)
    
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    if job.status.value != "completed":
        raise HTTPException(
            status_code=400,
            detail=f"Job not completed. Status: {job.status.value}"
        )
    
    if not job.qc_report:
        raise HTTPException(status_code=500, detail="QC report not available")
    
    # Generate filename
    base_name = job.source_filename.rsplit('.', 1)[0]
    filename = f"{base_name}_qc_report.json"
    
    return JSONResponse(
        content=job.qc_report.model_dump(),
        headers={
            "Content-Disposition": f'attachment; filename="{filename}"'
        }
    )


@app.get("/api/jobs/{job_id}/segments")
async def get_job_segments(job_id: str):
    """Get source and translated segments for preview."""
    job = await job_runner.get_job(job_id)
    
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    # Return whatever segments are available
    return {
        "source_segments": [s.model_dump() for s in job.source_segments],
        "translated_segments": [s.model_dump() for s in job.translated_segments],
        "status": job.status.value,
        "progress": job.progress
    }


# =============================================================================
# Human Review Endpoints
# =============================================================================

@app.get("/api/reviews/pending")
async def get_pending_reviews():
    """Get all jobs waiting for human review."""
    try:
        repo = get_repository()
        pending_jobs = repo.get_pending_reviews()
        
        # Also check in-memory jobs
        in_memory_pending = [
            {
                "job_id": job.job_id,
                "status": job.status.value,
                "review_status": job.review_status.value,
                "source_filename": job.source_filename,
                "source_lang": job.request.source_lang,
                "target_lang": job.request.target_lang,
                "qc_summary": job.qc_report.summary.model_dump() if job.qc_report else None
            }
            for job in job_runner.jobs.values()
            if job.review_status == ReviewStatus.PENDING_REVIEW
        ]
        
        # Merge results (in-memory takes precedence for active jobs)
        in_memory_ids = {j["job_id"] for j in in_memory_pending}
        db_only = [j for j in pending_jobs if j["job_id"] not in in_memory_ids]
        
        return {
            "pending_jobs": in_memory_pending + db_only,
            "count": len(in_memory_pending) + len(db_only)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get pending reviews: {str(e)}")


@app.post("/api/jobs/{job_id}/review")
async def review_job(
    job_id: str,
    action: str = Form(...),  # "approve" or "reject"
    notes: str = Form(default="")
):
    """
    Submit a human review for a job.
    
    Args:
        job_id: The job to review
        action: "approve" or "reject"
        notes: Optional reviewer notes
        
    When approved, translations are marked as approved in Translation Memory.
    When rejected, unapproved translations from this job are removed from TM.
    """
    if action not in ["approve", "reject"]:
        raise HTTPException(
            status_code=400,
            detail="Action must be 'approve' or 'reject'"
        )
    
    tm = get_translation_memory()
    tm_count = 0
    
    # Check in-memory first
    job = await job_runner.get_job(job_id)
    
    if job:
        # Update in-memory job
        if action == "approve":
            job.review_status = ReviewStatus.APPROVED
            # Approve translations in TM
            tm_count = tm.approve_job_translations(job_id)
        else:
            job.review_status = ReviewStatus.REJECTED
            # Remove unapproved translations from TM
            tm_count = tm.reject_job_translations(job_id)
        job.reviewer_notes = notes
        
        # Also update database
        try:
            repo = get_repository()
            repo.update_review_status(
                job_id=job_id,
                review_status=job.review_status.value,
                reviewer_notes=notes
            )
        except Exception as e:
            print(f"[WARN] Failed to update review in database: {e}")
        
        return {
            "status": "ok",
            "job_id": job_id,
            "review_status": job.review_status.value,
            "message": f"Job {action}d successfully",
            "tm_updated": tm_count
        }
    
    # If not in memory, try database only
    try:
        repo = get_repository()
        db_job = repo.get_job(job_id)
        if not db_job:
            raise HTTPException(status_code=404, detail="Job not found")
        
        new_status = "approved" if action == "approve" else "rejected"
        
        # Update TM
        if action == "approve":
            tm_count = tm.approve_job_translations(job_id)
        else:
            tm_count = tm.reject_job_translations(job_id)
        
        repo.update_review_status(
            job_id=job_id,
            review_status=new_status,
            reviewer_notes=notes
        )
        
        return {
            "status": "ok",
            "job_id": job_id,
            "review_status": new_status,
            "message": f"Job {action}d successfully",
            "tm_updated": tm_count
        }
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to update review: {str(e)}")


@app.get("/api/translation-memory/stats")
async def get_tm_stats():
    """Get statistics about the Translation Memory."""
    try:
        tm = get_translation_memory()
        stats = tm.get_stats()
        language_pairs = tm.get_language_pairs()
        return {
            "stats": stats,
            "language_pairs": language_pairs
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Failed to get TM stats: {str(e)}")


@app.get("/api/jobs/{job_id}/review-status")
async def get_job_review_status(job_id: str):
    """Get the review status of a job."""
    job = await job_runner.get_job(job_id)
    
    if job:
        return {
            "job_id": job_id,
            "review_status": job.review_status.value,
            "reviewer_notes": job.reviewer_notes,
            "qc_passed": job.qc_report.summary.passed if job.qc_report else None
        }
    
    # Check database
    try:
        repo = get_repository()
        db_job = repo.get_job(job_id)
        if db_job:
            return {
                "job_id": job_id,
                "review_status": db_job.get("review_status", "unknown"),
                "reviewer_notes": db_job.get("reviewer_notes"),
                "qc_passed": db_job.get("data", {}).get("qc_summary", {}).get("passed") if db_job.get("data") else None
            }
    except Exception as e:
        print(f"[WARN] Database lookup failed: {e}")
    
    raise HTTPException(status_code=404, detail="Job not found")


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
