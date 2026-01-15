"""Pydantic models for the subtitle localization platform."""

from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class JobStatus(str, Enum):
    """Status of a translation job."""
    PENDING = "pending"
    PROCESSING = "processing"
    COMPLETED = "completed"
    FAILED = "failed"


class SubtitleFormat(str, Enum):
    """Supported subtitle formats."""
    SRT = "srt"
    VTT = "vtt"


class QCIssueType(str, Enum):
    """Types of QC issues."""
    CPS_EXCEEDED = "cps_exceeded"
    LINE_TOO_LONG = "line_too_long"
    TOO_MANY_LINES = "too_many_lines"
    EMPTY_CUE = "empty_cue"
    OVERLAP = "overlap"
    SHORT_DURATION = "short_duration"


class QCIssueSeverity(str, Enum):
    """Severity levels for QC issues."""
    ERROR = "error"
    WARNING = "warning"


class ReviewStatus(str, Enum):
    """Review status for jobs."""
    AUTO = "auto"                    # QC passed automatically
    PENDING_REVIEW = "pending_review"  # QC failed, needs human review
    APPROVED = "approved"            # Human approved
    REJECTED = "rejected"            # Human rejected


class JobConstraints(BaseModel):
    """Constraints for subtitle processing."""
    max_lines: int = Field(default=2, ge=1, le=4, description="Maximum lines per cue")
    max_chars_per_line: int = Field(default=42, ge=20, le=80, description="Maximum characters per line")
    max_cps: float = Field(default=17.0, ge=10.0, le=30.0, description="Maximum characters per second")
    min_duration_ms: int = Field(default=500, ge=100, le=2000, description="Minimum cue duration in ms")


class SubtitleSegment(BaseModel):
    """A single subtitle cue/segment."""
    index: int = Field(..., description="Cue index (1-based)")
    start_ms: int = Field(..., ge=0, description="Start time in milliseconds")
    end_ms: int = Field(..., ge=0, description="End time in milliseconds")
    text: str = Field(..., description="Original subtitle text")
    translated_text: Optional[str] = Field(default=None, description="Translated text")
    qc_flags: list[str] = Field(default_factory=list, description="QC issue flags for this cue")

    @property
    def duration_ms(self) -> int:
        """Duration in milliseconds."""
        return self.end_ms - self.start_ms

    @property
    def duration_seconds(self) -> float:
        """Duration in seconds."""
        return self.duration_ms / 1000.0

    def calculate_cps(self, use_translated: bool = False) -> float:
        """Calculate characters per second."""
        text = self.translated_text if use_translated and self.translated_text else self.text
        if self.duration_seconds <= 0:
            return float('inf')
        return len(text.replace('\n', '')) / self.duration_seconds


class QCIssue(BaseModel):
    """A single QC issue."""
    cue_index: int = Field(..., description="Index of the affected cue")
    issue_type: QCIssueType = Field(..., description="Type of issue")
    severity: QCIssueSeverity = Field(..., description="Severity level")
    message: str = Field(..., description="Human-readable description")
    value: Optional[float] = Field(default=None, description="Actual value that triggered the issue")
    threshold: Optional[float] = Field(default=None, description="Threshold that was exceeded")


class QCSummary(BaseModel):
    """Summary of QC results."""
    total_cues: int = Field(..., description="Total number of cues")
    issues_count: int = Field(..., description="Total number of issues")
    errors_count: int = Field(..., description="Number of errors")
    warnings_count: int = Field(..., description="Number of warnings")
    passed: bool = Field(..., description="Whether QC passed (no errors)")
    by_type: dict[str, int] = Field(default_factory=dict, description="Issue counts by type")


class QCReport(BaseModel):
    """Full QC report."""
    issues: list[QCIssue] = Field(default_factory=list, description="All QC issues")
    summary: QCSummary = Field(..., description="Summary statistics")


class JobRequest(BaseModel):
    """Request to create a new translation job."""
    source_lang: str = Field(default="en", description="Source language code")
    target_lang: str = Field(default="he", description="Target language code")
    format: SubtitleFormat = Field(default=SubtitleFormat.SRT, description="Input file format")
    constraints: JobConstraints = Field(default_factory=JobConstraints, description="Processing constraints")
    glossary: dict[str, str] = Field(default_factory=dict, description="Term glossary (source -> target)")
    dry_run: bool = Field(default=False, description="If true, only run parsing and QC")


class JobState(BaseModel):
    """Current state of a job."""
    job_id: str = Field(..., description="Unique job identifier")
    status: JobStatus = Field(default=JobStatus.PENDING, description="Current status")
    progress: float = Field(default=0.0, ge=0.0, le=100.0, description="Progress percentage")
    error: Optional[str] = Field(default=None, description="Error message if failed")
    request: JobRequest = Field(..., description="Original request")
    source_segments: list[SubtitleSegment] = Field(default_factory=list, description="Parsed source segments")
    translated_segments: list[SubtitleSegment] = Field(default_factory=list, description="Translated segments")
    qc_report: Optional[QCReport] = Field(default=None, description="QC report")
    source_filename: str = Field(default="subtitle", description="Original filename")
    # Review fields
    review_status: ReviewStatus = Field(default=ReviewStatus.AUTO, description="Human review status")
    reviewer_notes: Optional[str] = Field(default=None, description="Notes from human reviewer")


class MultiTargetJobRequest(BaseModel):
    """Request for multi-language translation."""
    source_lang: str = Field(default="en", description="Source language code")
    target_langs: list[str] = Field(..., description="List of target language codes")
    format: SubtitleFormat = Field(default=SubtitleFormat.SRT, description="Input file format")
    constraints: JobConstraints = Field(default_factory=JobConstraints, description="Processing constraints")
    glossary: dict[str, dict[str, str]] = Field(
        default_factory=dict, 
        description="Per-language glossaries: {lang_code: {source_term: target_term}}"
    )
    dry_run: bool = Field(default=False, description="If true, only run parsing and QC")


class MultiTargetJobState(BaseModel):
    """State of a multi-target translation job."""
    parent_job_id: str = Field(..., description="Parent job identifier")
    child_jobs: dict[str, str] = Field(
        default_factory=dict, 
        description="Mapping of target language to child job ID"
    )
    status: JobStatus = Field(default=JobStatus.PENDING, description="Overall status")
    progress: float = Field(default=0.0, ge=0.0, le=100.0, description="Average progress of all child jobs")
    source_filename: str = Field(default="subtitle", description="Original filename")


class JobStatusResponse(BaseModel):
    """Response for job status endpoint."""
    job_id: str
    status: JobStatus
    progress: float
    error: Optional[str] = None
    qc_summary: Optional[QCSummary] = None


class JobResultResponse(BaseModel):
    """Response for job result endpoint."""
    job_id: str
    segments: list[SubtitleSegment]
    qc_report: QCReport


class MultiTargetJobStatusResponse(BaseModel):
    """Response for multi-target job status endpoint."""
    parent_job_id: str
    status: JobStatus
    progress: float
    child_jobs: dict[str, JobStatusResponse] = Field(
        default_factory=dict,
        description="Status of each child job by language"
    )
