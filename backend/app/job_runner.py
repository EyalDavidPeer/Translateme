"""Async job runner for subtitle translation jobs."""

import asyncio
import os
import uuid
from typing import Dict, Optional, Callable, List, Tuple
from pathlib import Path

# Load .env file if it exists
def _load_env_file():
    """Load environment variables from .env file."""
    env_path = Path(__file__).parent.parent / ".env"
    if env_path.exists():
        with open(env_path, encoding='utf-8') as f:
            for line in f:
                line = line.strip()
                if line and not line.startswith("#") and "=" in line:
                    key, value = line.split("=", 1)
                    os.environ.setdefault(key.strip(), value.strip())

_load_env_file()

from .models import (
    JobState,
    JobStatus,
    JobRequest,
    JobConstraints,
    SubtitleSegment,
    SubtitleFormat,
    QCReport,
    QCIssueSeverity,
    MultiTargetJobState,
    ReviewStatus,
)
from .parsing import parse_srt, parse_vtt
from .translation import TranslationProvider, MockProvider, OpenAIProvider
from .postprocess.condenser import postprocess_segments
from .conformance import conform_subtitles
from .translation.prompts import get_language_name
from .qc import run_qc_checks
from .database import get_repository


class JobRunner:
    """
    Manages subtitle translation jobs with async processing.
    
    Uses in-memory storage for MVP. Production would use Redis/PostgreSQL.
    """
    
    def __init__(self):
        self.jobs: Dict[str, JobState] = {}
        self.multi_jobs: Dict[str, MultiTargetJobState] = {}
        self._lock = asyncio.Lock()
        self._provider: Optional[TranslationProvider] = None
    
    def get_provider(self) -> TranslationProvider:
        """Get or create the translation provider based on configuration."""
        # Check if we should use OpenAI (either explicitly set or API key is present)
        provider_type = os.getenv("TRANSLATION_PROVIDER", "openai").lower()
        api_key = os.getenv("OPENAI_API_KEY")
        
        # Validate API key format
        if api_key:
            api_key = api_key.strip()
            if api_key.startswith('"') or api_key.startswith("'"):
                api_key = api_key[1:-1]  # Remove quotes if present
        
        # Debug logging
        print(f"[INFO] TRANSLATION_PROVIDER={provider_type}")
        
        if not api_key:
            print("[ERROR] OPENAI_API_KEY is not set!")
            print("[ERROR] Please create a .env file in the backend folder with:")
            print("[ERROR]   OPENAI_API_KEY=sk-your-api-key-here")
            print("[ERROR] Get your API key from: https://platform.openai.com/api-keys")
            print("[WARN] Falling back to Mock provider (no actual translation)")
            self._provider = MockProvider()
            return self._provider
        
        if provider_type == "mock":
            print("[INFO] Using Mock provider (as configured)")
            self._provider = MockProvider()
            return self._provider
        
        # Try to use OpenAI
        try:
            self._provider = OpenAIProvider(api_key=api_key)
            print(f"[INFO] Using OpenAI provider with model: {self._provider.model}")
        except ValueError as e:
            print(f"[ERROR] Failed to initialize OpenAI: {e}")
            print("[WARN] Falling back to Mock provider (no actual translation)")
            self._provider = MockProvider()
        
        return self._provider
    
    async def create_job(
        self,
        request: JobRequest,
        file_content: str,
        filename: str
    ) -> str:
        """
        Create a new translation job.
        
        Args:
            request: Job configuration
            file_content: Raw subtitle file content
            filename: Original filename
            
        Returns:
            Job ID
        """
        job_id = str(uuid.uuid4())
        
        job = JobState(
            job_id=job_id,
            status=JobStatus.PENDING,
            progress=0.0,
            request=request,
            source_filename=filename
        )
        
        async with self._lock:
            self.jobs[job_id] = job
        
        # Start processing in background
        asyncio.create_task(self._process_job(job_id, file_content))
        
        return job_id
    
    async def get_job(self, job_id: str) -> Optional[JobState]:
        """Get job state by ID."""
        return self.jobs.get(job_id)
    
    async def _update_progress(
        self,
        job_id: str,
        progress: float,
        status: Optional[JobStatus] = None
    ):
        """Update job progress."""
        if job_id in self.jobs:
            self.jobs[job_id].progress = progress
            if status:
                self.jobs[job_id].status = status
    
    async def _save_job_to_db(self, job: JobState) -> None:
        """Save job state to the database."""
        try:
            repo = get_repository()
            repo.save_job(
                job_id=job.job_id,
                status=job.status.value,
                review_status=job.review_status.value,
                source_filename=job.source_filename,
                source_lang=job.request.source_lang,
                target_lang=job.request.target_lang,
                data={
                    "error": job.error,
                    "qc_summary": job.qc_report.summary.model_dump() if job.qc_report else None
                }
            )
            if job.status == JobStatus.COMPLETED:
                repo.mark_completed(job.job_id)
        except Exception as e:
            print(f"[WARN] Failed to save job to database: {e}")
    
    async def _retry_failed_cues(
        self,
        segments: List[SubtitleSegment],
        qc_report: QCReport,
        constraints: JobConstraints,
        language: str,
        provider: TranslationProvider,
        max_retries: int = 3
    ) -> Tuple[List[SubtitleSegment], QCReport]:
        """
        Retry conformance for cues that failed QC.
        
        Args:
            segments: All subtitle segments
            qc_report: Current QC report with errors
            constraints: Job constraints
            language: Target language name
            provider: Translation provider
            max_retries: Maximum retry attempts
            
        Returns:
            Tuple of (updated segments, final QC report)
        """
        for attempt in range(max_retries):
            # Extract indices of cues with errors
            error_indices = {
                issue.cue_index for issue in qc_report.issues 
                if issue.severity == QCIssueSeverity.ERROR
            }
            
            if not error_indices:
                print(f"[INFO] All QC errors resolved after {attempt} retries")
                break
            
            print(f"[INFO] Retry attempt {attempt + 1}/{max_retries}: {len(error_indices)} cues with errors")
            
            # Get failed segments
            failed_segments = [s for s in segments if s.index in error_indices]
            
            if not failed_segments:
                break
            
            # Re-conform only failed cues
            await conform_subtitles(
                segments=failed_segments,
                constraints=constraints,
                language=language,
                provider=provider,
                batch_size=len(failed_segments)  # Process all failed in one batch
            )
            
            # Re-run QC on all segments
            qc_report = run_qc_checks(segments, constraints, use_translated=True)
            
            if qc_report.summary.errors_count == 0:
                print(f"[INFO] All QC errors resolved after {attempt + 1} retries")
                break
        
        # Mark remaining errors as unfixable
        if qc_report.summary.errors_count > 0:
            unfixable_indices = {
                issue.cue_index for issue in qc_report.issues 
                if issue.severity == QCIssueSeverity.ERROR
            }
            for seg in segments:
                if seg.index in unfixable_indices:
                    if "UNFIXABLE" not in seg.qc_flags:
                        seg.qc_flags.append("UNFIXABLE")
            print(f"[WARN] {len(unfixable_indices)} cues marked as unfixable after {max_retries} retries")
        
        return segments, qc_report
    
    async def _process_job(self, job_id: str, file_content: str):
        """
        Process a translation job.
        
        Pipeline:
        1. Parse input file (0-10%)
        2. Translate segments (10-80%)
        3. Post-process (80-90%)
        4. Run QC (90-100%)
        """
        job = self.jobs.get(job_id)
        if not job:
            return
        
        try:
            job.status = JobStatus.PROCESSING
            
            # Step 1: Parse input file
            await self._update_progress(job_id, 5)
            segments = await self._parse_file(
                file_content,
                job.request.format
            )
            job.source_segments = segments
            await self._update_progress(job_id, 10)
            
            # Step 2: Translate (skip if dry run)
            if job.request.dry_run:
                # For dry run, just copy original to translated
                for seg in segments:
                    seg.translated_text = seg.text
                translated_segments = segments
            else:
                translated_segments = await self._translate_segments(
                    job_id=job_id,
                    segments=segments,
                    request=job.request
                )
            
            await self._update_progress(job_id, 80)
            
            # Step 3: Conformance - ensure subtitles meet platform constraints
            provider = self.get_provider()
            language_name = get_language_name(job.request.target_lang)
            
            # Use LLM-based conformance engine for intelligent reflow/compression
            processed_segments = await conform_subtitles(
                segments=translated_segments,
                constraints=job.request.constraints,
                language=language_name,
                provider=provider,
                batch_size=10
            )
            job.translated_segments = processed_segments
            await self._update_progress(job_id, 90)
            
            # Step 4: Run QC
            qc_report = run_qc_checks(
                segments=processed_segments,
                constraints=job.request.constraints,
                use_translated=True
            )
            
            # Step 5: Retry loop for failed cues
            if qc_report.summary.errors_count > 0:
                print(f"[INFO] QC found {qc_report.summary.errors_count} errors, starting retry loop...")
                processed_segments, qc_report = await self._retry_failed_cues(
                    segments=processed_segments,
                    qc_report=qc_report,
                    constraints=job.request.constraints,
                    language=language_name,
                    provider=provider
                )
            
            job.translated_segments = processed_segments
            job.qc_report = qc_report
            await self._update_progress(job_id, 95)
            
            # Set review status based on QC results
            if qc_report.summary.passed:
                job.review_status = ReviewStatus.AUTO
                print(f"[INFO] Job {job_id}: QC passed, auto-approved")
            else:
                job.review_status = ReviewStatus.PENDING_REVIEW
                print(f"[INFO] Job {job_id}: QC failed with {qc_report.summary.errors_count} errors, pending review")
            
            # Mark complete
            job.status = JobStatus.COMPLETED
            job.progress = 100
            
            # Save to database
            await self._save_job_to_db(job)
            
        except Exception as e:
            job.status = JobStatus.FAILED
            job.error = str(e)
            # Save failed state to database
            await self._save_job_to_db(job)
            raise
    
    async def _parse_file(
        self,
        content: str,
        format: SubtitleFormat
    ) -> list[SubtitleSegment]:
        """Parse subtitle file based on format."""
        if format == SubtitleFormat.VTT:
            return parse_vtt(content)
        else:
            return parse_srt(content)
    
    async def _translate_segments(
        self,
        job_id: str,
        segments: list[SubtitleSegment],
        request: JobRequest
    ) -> list[SubtitleSegment]:
        """
        Translate segments in batches with context window.
        
        Uses sliding window of 15 segments for context.
        Processes 5 segments per batch.
        Uses Translation Memory to cache and reuse translations.
        """
        provider = self.get_provider()
        
        batch_size = 5
        context_size = 15
        total = len(segments)
        
        for i in range(0, total, batch_size):
            batch = segments[i:i + batch_size]
            
            # Get context window (already translated segments)
            context_start = max(0, i - context_size)
            context = segments[context_start:i]
            
            # Translate batch (with TM lookup and storage)
            await provider.translate_batch(
                segments=batch,
                context_window=context,
                source_lang=request.source_lang,
                target_lang=request.target_lang,
                glossary=request.glossary,
                constraints=request.constraints,
                job_id=job_id  # Pass job_id for TM tracking
            )
            
            # Update progress (10% to 80% range)
            progress = 10 + (70 * (i + len(batch)) / total)
            await self._update_progress(job_id, progress)
        
        return segments


# Global job runner instance
job_runner = JobRunner()
