"""Fix suggestion engine for QC issues."""

from typing import List, Optional, Dict, Any
from dataclasses import dataclass
from enum import Enum

from .models import SubtitleSegment, JobConstraints, QCIssue, QCIssueType


class FixType(str, Enum):
    """Types of fixes that can be suggested."""
    COMPRESS = "compress"
    EXTEND_TIMING = "extend_timing"
    SPLIT_CUE = "split_cue"
    REFLOW = "reflow"
    MANUAL = "manual"


@dataclass
class FixOption:
    """A single fix option for a QC issue."""
    fix_type: FixType
    description: str
    preview_text: str
    new_start_ms: Optional[int] = None
    new_end_ms: Optional[int] = None
    resulting_cps: Optional[float] = None
    resulting_line_length: Optional[int] = None
    confidence: float = 0.0  # 0-1 score
    is_applicable: bool = True
    reason: Optional[str] = None


@dataclass
class FixSuggestions:
    """Collection of fix suggestions for a cue."""
    cue_index: int
    original_text: str
    current_cps: float
    current_max_line_length: int
    current_line_count: int
    issues: List[str]
    options: List[FixOption]
    constraints: Dict[str, Any]


def calculate_cps(text: str, duration_ms: int) -> float:
    """Calculate characters per second."""
    if duration_ms <= 0:
        return float('inf')
    char_count = len(text.replace('\n', ''))
    return char_count / (duration_ms / 1000.0)


def calculate_max_line_length(text: str) -> int:
    """Get the length of the longest line."""
    lines = text.split('\n')
    return max(len(line) for line in lines) if lines else 0


def calculate_target_chars(duration_ms: int, max_cps: float) -> int:
    """Calculate target character count based on CPS constraint."""
    duration_seconds = duration_ms / 1000.0
    if duration_seconds <= 0:
        return 0
    # Use 95% of max to provide some buffer
    max_chars = int(duration_seconds * max_cps * 0.95)
    return max(max_chars, 10)


def calculate_max_extension(
    segment: SubtitleSegment,
    next_segment: Optional[SubtitleSegment],
    min_gap_ms: int = 80
) -> int:
    """Calculate maximum timing extension in ms."""
    if next_segment is None:
        # Last segment - can extend up to 2 seconds
        return min(2000, segment.duration_ms)
    
    available_gap = next_segment.start_ms - segment.end_ms
    max_extension = max(0, available_gap - min_gap_ms)
    return max_extension


def generate_timing_fix(
    segment: SubtitleSegment,
    next_segment: Optional[SubtitleSegment],
    constraints: JobConstraints,
    text: str
) -> Optional[FixOption]:
    """Generate a timing extension fix if possible."""
    max_extension = calculate_max_extension(segment, next_segment)
    
    if max_extension <= 0:
        return FixOption(
            fix_type=FixType.EXTEND_TIMING,
            description="Extend cue timing",
            preview_text=text,
            is_applicable=False,
            reason="No timing slack available (next cue is too close)"
        )
    
    # Calculate how much extension we need
    current_cps = calculate_cps(text, segment.duration_ms)
    if current_cps <= constraints.max_cps:
        return None  # No need for timing fix
    
    # Calculate required duration for target CPS
    char_count = len(text.replace('\n', ''))
    required_duration_ms = int((char_count / constraints.max_cps) * 1000)
    needed_extension = required_duration_ms - segment.duration_ms
    
    # Check if we can fully fix with timing
    actual_extension = min(needed_extension, max_extension)
    new_end_ms = segment.end_ms + actual_extension
    new_duration_ms = segment.duration_ms + actual_extension
    new_cps = calculate_cps(text, new_duration_ms)
    
    is_full_fix = new_cps <= constraints.max_cps
    
    return FixOption(
        fix_type=FixType.EXTEND_TIMING,
        description=f"Extend timing by {actual_extension}ms" + (" (full fix)" if is_full_fix else " (partial)"),
        preview_text=text,
        new_start_ms=segment.start_ms,
        new_end_ms=new_end_ms,
        resulting_cps=round(new_cps, 1),
        confidence=0.9 if is_full_fix else 0.5,
        is_applicable=True
    )


def generate_reflow_fix(
    text: str,
    constraints: JobConstraints
) -> Optional[FixOption]:
    """Generate a line reflow fix."""
    lines = text.split('\n')
    max_line_len = max(len(line) for line in lines)
    
    if max_line_len <= constraints.max_chars_per_line and len(lines) <= constraints.max_lines:
        return None  # No reflow needed
    
    # Try to reflow the text
    words = ' '.join(lines).split()
    new_lines = []
    current_line = []
    current_len = 0
    
    for word in words:
        word_len = len(word)
        # Check if adding this word exceeds line limit
        if current_len + word_len + (1 if current_line else 0) > constraints.max_chars_per_line:
            if current_line:
                new_lines.append(' '.join(current_line))
            current_line = [word]
            current_len = word_len
        else:
            current_line.append(word)
            current_len += word_len + (1 if len(current_line) > 1 else 0)
    
    if current_line:
        new_lines.append(' '.join(current_line))
    
    # Check if reflow is valid
    if len(new_lines) > constraints.max_lines:
        return FixOption(
            fix_type=FixType.REFLOW,
            description="Reflow lines",
            preview_text='\n'.join(new_lines[:constraints.max_lines]),
            is_applicable=False,
            reason=f"Text requires {len(new_lines)} lines, max is {constraints.max_lines}"
        )
    
    new_text = '\n'.join(new_lines)
    new_max_line = max(len(line) for line in new_lines)
    
    return FixOption(
        fix_type=FixType.REFLOW,
        description="Reflow text into proper lines",
        preview_text=new_text,
        resulting_line_length=new_max_line,
        confidence=0.8,
        is_applicable=new_max_line <= constraints.max_chars_per_line
    )


def generate_split_fix(
    segment: SubtitleSegment,
    next_segment: Optional[SubtitleSegment],
    text: str,
    constraints: JobConstraints
) -> Optional[FixOption]:
    """Generate a split cue fix suggestion."""
    # Only suggest split if there's room and text is long enough
    lines = text.split('\n')
    total_text = ' '.join(lines)
    words = total_text.split()
    
    if len(words) < 4:
        return FixOption(
            fix_type=FixType.SPLIT_CUE,
            description="Split into two cues",
            preview_text=text,
            is_applicable=False,
            reason="Text too short to split meaningfully"
        )
    
    # Check timing availability
    max_extension = calculate_max_extension(segment, next_segment)
    min_cue_duration = constraints.min_duration_ms
    
    if segment.duration_ms < min_cue_duration * 2:
        return FixOption(
            fix_type=FixType.SPLIT_CUE,
            description="Split into two cues",
            preview_text=text,
            is_applicable=False,
            reason=f"Duration too short to split (need {min_cue_duration * 2}ms minimum)"
        )
    
    # Find midpoint for split
    mid_word_idx = len(words) // 2
    first_half = ' '.join(words[:mid_word_idx])
    second_half = ' '.join(words[mid_word_idx:])
    
    # Calculate timing for split
    mid_time_ms = segment.start_ms + (segment.duration_ms // 2)
    
    preview = f"Cue 1: {first_half}\nCue 2: {second_half}"
    
    return FixOption(
        fix_type=FixType.SPLIT_CUE,
        description="Split into two cues at midpoint",
        preview_text=preview,
        new_end_ms=mid_time_ms,  # First cue ends here
        confidence=0.6,
        is_applicable=True,
        reason=f"Split at {mid_time_ms}ms"
    )


async def generate_compress_fix(
    segment: SubtitleSegment,
    text: str,
    constraints: JobConstraints,
    target_lang: str,
    provider: Any
) -> FixOption:
    """Generate a compressed version of the text using LLM."""
    target_chars = calculate_target_chars(segment.duration_ms, constraints.max_cps)
    
    if len(text.replace('\n', '')) <= target_chars:
        return FixOption(
            fix_type=FixType.COMPRESS,
            description="Compress text",
            preview_text=text,
            is_applicable=False,
            reason="Text already within limit"
        )
    
    try:
        # Use the provider to compress
        compressed = await provider.condense_text(text, target_chars, target_lang)
        new_cps = calculate_cps(compressed, segment.duration_ms)
        
        return FixOption(
            fix_type=FixType.COMPRESS,
            description=f"Compress to {len(compressed.replace(chr(10), ''))} chars",
            preview_text=compressed,
            resulting_cps=round(new_cps, 1),
            confidence=0.85 if new_cps <= constraints.max_cps else 0.4,
            is_applicable=True
        )
    except Exception as e:
        return FixOption(
            fix_type=FixType.COMPRESS,
            description="Compress text (AI-powered)",
            preview_text=text,
            is_applicable=False,
            reason=f"Compression failed: {str(e)}"
        )


async def generate_fix_suggestions(
    segment: SubtitleSegment,
    next_segment: Optional[SubtitleSegment],
    issues: List[QCIssue],
    constraints: JobConstraints,
    target_lang: str,
    provider: Any
) -> FixSuggestions:
    """
    Generate all applicable fix suggestions for a segment.
    
    Args:
        segment: The segment with QC issues
        next_segment: The next segment (for timing calculations)
        issues: List of QC issues for this segment
        constraints: Job constraints
        target_lang: Target language code
        provider: Translation provider for AI-powered fixes
        
    Returns:
        FixSuggestions with all options
    """
    text = segment.translated_text or segment.text
    options: List[FixOption] = []
    issue_types = [issue.issue_type for issue in issues]
    
    # Calculate current metrics
    current_cps = calculate_cps(text, segment.duration_ms)
    current_max_line = calculate_max_line_length(text)
    current_line_count = len(text.split('\n'))
    
    # Generate timing fix (if CPS is the issue)
    if QCIssueType.CPS_EXCEEDED in issue_types:
        timing_fix = generate_timing_fix(segment, next_segment, constraints, text)
        if timing_fix:
            options.append(timing_fix)
    
    # Generate reflow fix (if line length or count is the issue)
    if QCIssueType.LINE_TOO_LONG in issue_types or QCIssueType.TOO_MANY_LINES in issue_types:
        reflow_fix = generate_reflow_fix(text, constraints)
        if reflow_fix:
            options.append(reflow_fix)
    
    # Generate compress fix (if CPS or line length is the issue)
    if QCIssueType.CPS_EXCEEDED in issue_types or QCIssueType.LINE_TOO_LONG in issue_types:
        compress_fix = await generate_compress_fix(
            segment, text, constraints, target_lang, provider
        )
        options.append(compress_fix)
    
    # Generate split fix (for severe CPS violations)
    if QCIssueType.CPS_EXCEEDED in issue_types and current_cps > constraints.max_cps * 1.3:
        split_fix = generate_split_fix(segment, next_segment, text, constraints)
        if split_fix:
            options.append(split_fix)
    
    # Sort by confidence (highest first)
    options.sort(key=lambda x: (-x.confidence if x.is_applicable else -999, x.fix_type.value))
    
    return FixSuggestions(
        cue_index=segment.index,
        original_text=text,
        current_cps=round(current_cps, 1),
        current_max_line_length=current_max_line,
        current_line_count=current_line_count,
        issues=[str(it.value) for it in issue_types],
        options=[
            {
                "fix_type": opt.fix_type.value,
                "description": opt.description,
                "preview_text": opt.preview_text,
                "new_start_ms": opt.new_start_ms,
                "new_end_ms": opt.new_end_ms,
                "resulting_cps": opt.resulting_cps,
                "resulting_line_length": opt.resulting_line_length,
                "confidence": opt.confidence,
                "is_applicable": opt.is_applicable,
                "reason": opt.reason
            }
            for opt in options
        ],
        constraints={
            "max_cps": constraints.max_cps,
            "max_chars_per_line": constraints.max_chars_per_line,
            "max_lines": constraints.max_lines,
            "min_duration_ms": constraints.min_duration_ms
        }
    )


def apply_fix(
    segment: SubtitleSegment,
    fix_type: str,
    new_text: Optional[str] = None,
    new_start_ms: Optional[int] = None,
    new_end_ms: Optional[int] = None
) -> SubtitleSegment:
    """
    Apply a fix to a segment.
    
    Args:
        segment: The segment to modify
        fix_type: Type of fix to apply
        new_text: New text (for compress/reflow/manual)
        new_start_ms: New start time (for timing fixes)
        new_end_ms: New end time (for timing fixes)
        
    Returns:
        Modified segment
    """
    if new_text is not None:
        segment.translated_text = new_text
    
    if new_start_ms is not None:
        segment.start_ms = new_start_ms
    
    if new_end_ms is not None:
        segment.end_ms = new_end_ms
    
    # Clear old QC flags and add fix marker
    segment.qc_flags = [f for f in segment.qc_flags if not f.startswith('UNFIXABLE')]
    if f"FIXED:{fix_type}" not in segment.qc_flags:
        segment.qc_flags.append(f"FIXED:{fix_type}")
    
    return segment
