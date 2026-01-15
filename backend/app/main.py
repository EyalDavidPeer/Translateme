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
from .fix_suggestions import generate_fix_suggestions, apply_fix, calculate_cps, calculate_max_line_length
from .qc import run_qc_checks


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


# =============================================================================
# Fix Suggestion Endpoints
# =============================================================================

@app.get("/api/jobs/{job_id}/suggest-fixes/{cue_index}")
async def suggest_fixes(job_id: str, cue_index: int):
    """
    Get fix suggestions for a specific cue with QC issues.
    
    Returns multiple fix options:
    - Auto-compressed version (AI-powered)
    - Timing-adjusted version (if slack available)
    - Split suggestion (if applicable)
    - Reflow option (for line issues)
    """
    job = await job_runner.get_job(job_id)
    
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    if not job.qc_report:
        raise HTTPException(status_code=400, detail="No QC report available")
    
    # Find the segment
    segment = None
    segment_idx = None
    for i, seg in enumerate(job.translated_segments):
        if seg.index == cue_index:
            segment = seg
            segment_idx = i
            break
    
    if not segment:
        raise HTTPException(status_code=404, detail=f"Cue {cue_index} not found")
    
    # Get next segment for timing calculations
    next_segment = None
    if segment_idx is not None and segment_idx + 1 < len(job.translated_segments):
        next_segment = job.translated_segments[segment_idx + 1]
    
    # Get issues for this cue
    cue_issues = [issue for issue in job.qc_report.issues if issue.cue_index == cue_index]
    
    if not cue_issues:
        return {
            "cue_index": cue_index,
            "message": "No QC issues for this cue",
            "options": []
        }
    
    # Get provider for AI-powered compression
    provider = job_runner.get_provider()
    
    # Generate suggestions
    suggestions = await generate_fix_suggestions(
        segment=segment,
        next_segment=next_segment,
        issues=cue_issues,
        constraints=job.request.constraints,
        target_lang=job.request.target_lang,
        provider=provider
    )
    
    return {
        "cue_index": suggestions.cue_index,
        "original_text": suggestions.original_text,
        "current_cps": suggestions.current_cps,
        "current_max_line_length": suggestions.current_max_line_length,
        "current_line_count": suggestions.current_line_count,
        "issues": suggestions.issues,
        "options": suggestions.options,
        "constraints": suggestions.constraints
    }


@app.patch("/api/jobs/{job_id}/segments/{cue_index}")
async def apply_segment_fix(
    job_id: str,
    cue_index: int,
    fix_type: str = Form(...),
    new_text: Optional[str] = Form(default=None),
    new_start_ms: Optional[int] = Form(default=None),
    new_end_ms: Optional[int] = Form(default=None)
):
    """
    Apply a fix to a specific segment.
    
    Args:
        job_id: The job ID
        cue_index: The cue index to fix
        fix_type: Type of fix (compress, extend_timing, reflow, manual, split_cue)
        new_text: New text content (for text-based fixes)
        new_start_ms: New start time (for timing fixes)
        new_end_ms: New end time (for timing fixes)
    """
    job = await job_runner.get_job(job_id)
    
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    # Find the segment
    segment = None
    for seg in job.translated_segments:
        if seg.index == cue_index:
            segment = seg
            break
    
    if not segment:
        raise HTTPException(status_code=404, detail=f"Cue {cue_index} not found")
    
    # Apply the fix
    apply_fix(
        segment=segment,
        fix_type=fix_type,
        new_text=new_text,
        new_start_ms=new_start_ms,
        new_end_ms=new_end_ms
    )
    
    # Re-run QC on all segments
    job.qc_report = run_qc_checks(
        segments=job.translated_segments,
        constraints=job.request.constraints,
        use_translated=True
    )
    
    # Update review status if all issues are fixed
    if job.qc_report.summary.passed:
        job.review_status = ReviewStatus.AUTO
    
    # Calculate new metrics for the fixed segment
    text = segment.translated_text or segment.text
    new_cps = calculate_cps(text, segment.duration_ms)
    new_max_line = calculate_max_line_length(text)
    
    return {
        "status": "ok",
        "cue_index": cue_index,
        "fix_applied": fix_type,
        "new_text": segment.translated_text,
        "new_start_ms": segment.start_ms,
        "new_end_ms": segment.end_ms,
        "new_cps": round(new_cps, 1),
        "new_max_line_length": new_max_line,
        "qc_summary": job.qc_report.summary.model_dump()
    }


@app.post("/api/jobs/{job_id}/auto-fix")
async def batch_auto_fix(
    job_id: str,
    issue_type: Optional[str] = Form(default=None),
    max_fixes: int = Form(default=50)
):
    """
    Automatically apply the best fix to all issues of a specific type.
    
    Args:
        job_id: The job ID
        issue_type: Type of issues to fix (e.g., "cps_exceeded", "line_too_long")
                   If None, fixes all issue types
        max_fixes: Maximum number of fixes to apply (default 50)
    """
    job = await job_runner.get_job(job_id)
    
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    if not job.qc_report:
        raise HTTPException(status_code=400, detail="No QC report available")
    
    # Filter issues
    issues_to_fix = job.qc_report.issues
    if issue_type:
        issues_to_fix = [i for i in issues_to_fix if i.issue_type.value == issue_type]
    
    # Group issues by cue_index
    issues_by_cue = {}
    for issue in issues_to_fix:
        if issue.cue_index not in issues_by_cue:
            issues_by_cue[issue.cue_index] = []
        issues_by_cue[issue.cue_index].append(issue)
    
    # Get provider for AI fixes
    provider = job_runner.get_provider()
    
    # Apply fixes
    fixed_count = 0
    failed_count = 0
    fixed_cues = []
    
    # Build segment lookup
    segment_map = {seg.index: (i, seg) for i, seg in enumerate(job.translated_segments)}
    
    for cue_index, cue_issues in list(issues_by_cue.items())[:max_fixes]:
        if cue_index not in segment_map:
            continue
        
        seg_idx, segment = segment_map[cue_index]
        
        # Get next segment
        next_segment = None
        if seg_idx + 1 < len(job.translated_segments):
            next_segment = job.translated_segments[seg_idx + 1]
        
        try:
            # Generate suggestions
            suggestions = await generate_fix_suggestions(
                segment=segment,
                next_segment=next_segment,
                issues=cue_issues,
                constraints=job.request.constraints,
                target_lang=job.request.target_lang,
                provider=provider
            )
            
            # Find best applicable option
            best_option = None
            for opt in suggestions.options:
                if opt.get("is_applicable", False):
                    best_option = opt
                    break
            
            if best_option:
                # Apply the fix
                apply_fix(
                    segment=segment,
                    fix_type=best_option["fix_type"],
                    new_text=best_option.get("preview_text"),
                    new_start_ms=best_option.get("new_start_ms"),
                    new_end_ms=best_option.get("new_end_ms")
                )
                fixed_count += 1
                fixed_cues.append({
                    "cue_index": cue_index,
                    "fix_type": best_option["fix_type"],
                    "description": best_option["description"]
                })
            else:
                failed_count += 1
                
        except Exception as e:
            print(f"[WARN] Failed to fix cue {cue_index}: {e}")
            failed_count += 1
    
    # Re-run QC
    job.qc_report = run_qc_checks(
        segments=job.translated_segments,
        constraints=job.request.constraints,
        use_translated=True
    )
    
    # Update review status
    if job.qc_report.summary.passed:
        job.review_status = ReviewStatus.AUTO
    
    return {
        "status": "ok",
        "fixed_count": fixed_count,
        "failed_count": failed_count,
        "fixed_cues": fixed_cues,
        "remaining_issues": job.qc_report.summary.issues_count,
        "qc_summary": job.qc_report.summary.model_dump()
    }


@app.get("/api/jobs/{job_id}/calculate-metrics")
async def calculate_segment_metrics(
    job_id: str,
    cue_index: int,
    text: str
):
    """
    Calculate CPS and line metrics for given text in a segment's timing.
    Used for real-time validation in the frontend editor.
    """
    job = await job_runner.get_job(job_id)
    
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    # Find the segment
    segment = None
    for seg in job.translated_segments:
        if seg.index == cue_index:
            segment = seg
            break
    
    if not segment:
        raise HTTPException(status_code=404, detail=f"Cue {cue_index} not found")
    
    # Calculate metrics
    cps = calculate_cps(text, segment.duration_ms)
    max_line_length = calculate_max_line_length(text)
    line_count = len(text.split('\n'))
    char_count = len(text.replace('\n', ''))
    
    # Check against constraints
    constraints = job.request.constraints
    violations = []
    
    if cps > constraints.max_cps:
        violations.append(f"CPS {cps:.1f} exceeds max {constraints.max_cps}")
    if max_line_length > constraints.max_chars_per_line:
        violations.append(f"Line length {max_line_length} exceeds max {constraints.max_chars_per_line}")
    if line_count > constraints.max_lines:
        violations.append(f"Line count {line_count} exceeds max {constraints.max_lines}")
    
    return {
        "cue_index": cue_index,
        "text": text,
        "metrics": {
            "cps": round(cps, 1),
            "max_line_length": max_line_length,
            "line_count": line_count,
            "char_count": char_count,
            "duration_ms": segment.duration_ms
        },
        "constraints": {
            "max_cps": constraints.max_cps,
            "max_chars_per_line": constraints.max_chars_per_line,
            "max_lines": constraints.max_lines
        },
        "is_valid": len(violations) == 0,
        "violations": violations
    }


# =============================================================================
# Gender Toggle Endpoints
# =============================================================================

@app.get("/api/jobs/{job_id}/segments/{cue_index}/gender-alternatives")
async def get_gender_alternatives(job_id: str, cue_index: int):
    """
    Get gender alternatives for a specific segment.
    
    Returns available gender forms and the currently selected one.
    """
    job = await job_runner.get_job(job_id)
    
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    # Find the segment
    segment = None
    for seg in job.translated_segments:
        if seg.index == cue_index:
            segment = seg
            break
    
    if not segment:
        raise HTTPException(status_code=404, detail=f"Cue {cue_index} not found")
    
    return {
        "cue_index": cue_index,
        "current_text": segment.translated_text,
        "active_gender": segment.active_gender.value,
        "confidence": segment.gender_confidence,
        "alternatives": [
            {
                "gender": alt.gender.value,
                "text": alt.text,
                "confidence": alt.confidence
            }
            for alt in segment.gender_alternatives
        ],
        "has_alternatives": len(segment.gender_alternatives) > 1
    }


@app.patch("/api/jobs/{job_id}/segments/{cue_index}/gender")
async def set_segment_gender(
    job_id: str,
    cue_index: int,
    gender: str = Form(...)
):
    """
    Set the grammatical gender for a segment's translation.
    
    Args:
        job_id: The job ID
        cue_index: The cue index
        gender: The gender to set ('masculine' or 'feminine')
    """
    from .models import GenderForm
    
    job = await job_runner.get_job(job_id)
    
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    # Find the segment
    segment = None
    for seg in job.translated_segments:
        if seg.index == cue_index:
            segment = seg
            break
    
    if not segment:
        raise HTTPException(status_code=404, detail=f"Cue {cue_index} not found")
    
    # Validate gender
    try:
        new_gender = GenderForm(gender.lower())
    except ValueError:
        raise HTTPException(
            status_code=400, 
            detail=f"Invalid gender: {gender}. Must be 'masculine', 'feminine', 'neutral', or 'unknown'"
        )
    
    # Find the alternative with matching gender
    matching_alt = None
    for alt in segment.gender_alternatives:
        if alt.gender == new_gender:
            matching_alt = alt
            break
    
    if not matching_alt and segment.gender_alternatives:
        raise HTTPException(
            status_code=400,
            detail=f"No {gender} alternative available for this segment"
        )
    
    # Update the segment
    if matching_alt:
        segment.translated_text = matching_alt.text
        segment.active_gender = new_gender
        segment.gender_confidence = 1.0  # User made explicit choice
        
        # Add flag indicating manual gender selection
        if "GENDER_SET" not in segment.qc_flags:
            segment.qc_flags.append("GENDER_SET")
    
    # Re-run QC
    job.qc_report = run_qc_checks(
        segments=job.translated_segments,
        constraints=job.request.constraints,
        use_translated=True
    )
    
    return {
        "status": "ok",
        "cue_index": cue_index,
        "new_gender": new_gender.value,
        "new_text": segment.translated_text,
        "qc_summary": job.qc_report.summary.model_dump()
    }


@app.post("/api/jobs/{job_id}/batch-set-gender")
async def batch_set_gender(
    job_id: str,
    gender: str = Form(...),
    cue_indices: Optional[str] = Form(default=None)
):
    """
    Set gender for multiple segments at once.
    
    Args:
        job_id: The job ID
        gender: The gender to set ('masculine' or 'feminine')
        cue_indices: Comma-separated list of cue indices. If None, applies to all ambiguous segments.
    """
    from .models import GenderForm
    
    job = await job_runner.get_job(job_id)
    
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")
    
    # Validate gender
    try:
        new_gender = GenderForm(gender.lower())
    except ValueError:
        raise HTTPException(
            status_code=400,
            detail=f"Invalid gender: {gender}. Must be 'masculine', 'feminine', 'neutral', or 'unknown'"
        )
    
    # Parse cue indices
    target_indices = None
    if cue_indices:
        try:
            target_indices = set(int(i.strip()) for i in cue_indices.split(','))
        except ValueError:
            raise HTTPException(status_code=400, detail="Invalid cue_indices format")
    
    # Apply gender to segments
    updated_count = 0
    for segment in job.translated_segments:
        # Skip if specific indices provided and this isn't one of them
        if target_indices and segment.index not in target_indices:
            continue
        
        # Skip if no alternatives
        if not segment.gender_alternatives or len(segment.gender_alternatives) < 2:
            continue
        
        # Find matching alternative
        for alt in segment.gender_alternatives:
            if alt.gender == new_gender:
                segment.translated_text = alt.text
                segment.active_gender = new_gender
                segment.gender_confidence = 1.0
                if "GENDER_SET" not in segment.qc_flags:
                    segment.qc_flags.append("GENDER_SET")
                updated_count += 1
                break
    
    # Re-run QC
    job.qc_report = run_qc_checks(
        segments=job.translated_segments,
        constraints=job.request.constraints,
        use_translated=True
    )
    
    return {
        "status": "ok",
        "updated_count": updated_count,
        "gender": new_gender.value,
        "qc_summary": job.qc_report.summary.model_dump()
    }


if __name__ == "__main__":
    import uvicorn
    uvicorn.run(app, host="0.0.0.0", port=8000)
