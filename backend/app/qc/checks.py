"""Quality Control checks for subtitles."""

from typing import List, Optional

from ..models import (
    SubtitleSegment,
    JobConstraints,
    QCIssue,
    QCIssueType,
    QCIssueSeverity,
    QCSummary,
    QCReport,
)


def check_cps(
    segment: SubtitleSegment,
    max_cps: float,
    use_translated: bool = True
) -> Optional[QCIssue]:
    """
    Check if a segment exceeds the maximum characters per second.
    
    Args:
        segment: The subtitle segment to check
        max_cps: Maximum allowed CPS
        use_translated: Whether to check translated text
        
    Returns:
        QCIssue if violation found, None otherwise
    """
    text = segment.translated_text if use_translated and segment.translated_text else segment.text
    if not text:
        return None
    
    duration_seconds = segment.duration_seconds
    if duration_seconds <= 0:
        return QCIssue(
            cue_index=segment.index,
            issue_type=QCIssueType.CPS_EXCEEDED,
            severity=QCIssueSeverity.ERROR,
            message=f"Cue has zero or negative duration",
            value=float('inf'),
            threshold=max_cps
        )
    
    # Calculate CPS excluding newlines
    char_count = len(text.replace('\n', ''))
    cps = char_count / duration_seconds
    
    if cps > max_cps:
        return QCIssue(
            cue_index=segment.index,
            issue_type=QCIssueType.CPS_EXCEEDED,
            severity=QCIssueSeverity.ERROR,
            message=f"CPS {cps:.1f} exceeds maximum {max_cps}",
            value=round(cps, 2),
            threshold=max_cps
        )
    
    return None


def check_line_length(
    segment: SubtitleSegment,
    max_chars_per_line: int,
    use_translated: bool = True
) -> Optional[QCIssue]:
    """
    Check if any line in a segment exceeds the maximum character limit.
    
    Args:
        segment: The subtitle segment to check
        max_chars_per_line: Maximum allowed characters per line
        use_translated: Whether to check translated text
        
    Returns:
        QCIssue if violation found, None otherwise
    """
    text = segment.translated_text if use_translated and segment.translated_text else segment.text
    if not text:
        return None
    
    lines = text.split('\n')
    for line in lines:
        if len(line) > max_chars_per_line:
            return QCIssue(
                cue_index=segment.index,
                issue_type=QCIssueType.LINE_TOO_LONG,
                severity=QCIssueSeverity.ERROR,
                message=f"Line has {len(line)} chars, exceeds maximum {max_chars_per_line}",
                value=len(line),
                threshold=max_chars_per_line
            )
    
    return None


def check_line_count(
    segment: SubtitleSegment,
    max_lines: int,
    use_translated: bool = True
) -> Optional[QCIssue]:
    """
    Check if a segment has too many lines.
    
    Args:
        segment: The subtitle segment to check
        max_lines: Maximum allowed lines per cue
        use_translated: Whether to check translated text
        
    Returns:
        QCIssue if violation found, None otherwise
    """
    text = segment.translated_text if use_translated and segment.translated_text else segment.text
    if not text:
        return None
    
    line_count = len(text.split('\n'))
    if line_count > max_lines:
        return QCIssue(
            cue_index=segment.index,
            issue_type=QCIssueType.TOO_MANY_LINES,
            severity=QCIssueSeverity.ERROR,
            message=f"Cue has {line_count} lines, exceeds maximum {max_lines}",
            value=line_count,
            threshold=max_lines
        )
    
    return None


def check_empty_cue(
    segment: SubtitleSegment,
    use_translated: bool = True
) -> Optional[QCIssue]:
    """
    Check if a segment has empty or whitespace-only text.
    
    Args:
        segment: The subtitle segment to check
        use_translated: Whether to check translated text
        
    Returns:
        QCIssue if violation found, None otherwise
    """
    text = segment.translated_text if use_translated and segment.translated_text else segment.text
    
    if not text or not text.strip():
        return QCIssue(
            cue_index=segment.index,
            issue_type=QCIssueType.EMPTY_CUE,
            severity=QCIssueSeverity.WARNING,
            message="Cue has empty or whitespace-only text"
        )
    
    return None


def check_overlap(
    current: SubtitleSegment,
    next_segment: SubtitleSegment
) -> Optional[QCIssue]:
    """
    Check if two consecutive segments overlap in time.
    
    Args:
        current: The current segment
        next_segment: The next segment
        
    Returns:
        QCIssue if overlap found, None otherwise
    """
    if current.end_ms > next_segment.start_ms:
        overlap_ms = current.end_ms - next_segment.start_ms
        return QCIssue(
            cue_index=current.index,
            issue_type=QCIssueType.OVERLAP,
            severity=QCIssueSeverity.WARNING,
            message=f"Cue {current.index} overlaps with cue {next_segment.index} by {overlap_ms}ms",
            value=overlap_ms
        )
    
    return None


def check_short_duration(
    segment: SubtitleSegment,
    min_duration_ms: int
) -> Optional[QCIssue]:
    """
    Check if a segment has an extremely short duration.
    
    Args:
        segment: The subtitle segment to check
        min_duration_ms: Minimum acceptable duration in milliseconds
        
    Returns:
        QCIssue if violation found, None otherwise
    """
    if segment.duration_ms < min_duration_ms:
        return QCIssue(
            cue_index=segment.index,
            issue_type=QCIssueType.SHORT_DURATION,
            severity=QCIssueSeverity.WARNING,
            message=f"Cue duration {segment.duration_ms}ms is less than minimum {min_duration_ms}ms",
            value=segment.duration_ms,
            threshold=min_duration_ms
        )
    
    return None


def check_gender_ambiguity(
    segment: SubtitleSegment,
    confidence_threshold: float = 0.7
) -> Optional[QCIssue]:
    """
    Check if a segment has ambiguous grammatical gender.
    
    Args:
        segment: The subtitle segment to check
        confidence_threshold: Below this confidence level, flag as ambiguous
        
    Returns:
        QCIssue if gender is ambiguous, None otherwise
    """
    # Only flag if there are gender alternatives and confidence is low
    if segment.gender_alternatives and len(segment.gender_alternatives) > 1:
        if segment.gender_confidence < confidence_threshold:
            # Get the alternative genders available
            genders = [alt.gender.value for alt in segment.gender_alternatives]
            gender_str = "/".join(genders)
            
            return QCIssue(
                cue_index=segment.index,
                issue_type=QCIssueType.GENDER_AMBIGUOUS,
                severity=QCIssueSeverity.WARNING,
                message=f"Gender uncertain ({int(segment.gender_confidence * 100)}% confidence) - alternatives: {gender_str}",
                value=segment.gender_confidence,
                threshold=confidence_threshold
            )
    
    return None


def run_qc_checks(
    segments: List[SubtitleSegment],
    constraints: JobConstraints,
    use_translated: bool = True
) -> QCReport:
    """
    Run all QC checks on a list of segments.
    
    Args:
        segments: List of subtitle segments to check
        constraints: Constraint settings to check against
        use_translated: Whether to check translated text (if available)
        
    Returns:
        Complete QC report with all issues
    """
    issues: List[QCIssue] = []
    
    # Sort segments by start time for overlap checking
    sorted_segments = sorted(segments, key=lambda s: s.start_ms)
    
    for i, segment in enumerate(sorted_segments):
        # Check CPS
        issue = check_cps(segment, constraints.max_cps, use_translated)
        if issue:
            issues.append(issue)
        
        # Check line length
        issue = check_line_length(segment, constraints.max_chars_per_line, use_translated)
        if issue:
            issues.append(issue)
        
        # Check line count
        issue = check_line_count(segment, constraints.max_lines, use_translated)
        if issue:
            issues.append(issue)
        
        # Check empty cue
        issue = check_empty_cue(segment, use_translated)
        if issue:
            issues.append(issue)
        
        # Check short duration
        issue = check_short_duration(segment, constraints.min_duration_ms)
        if issue:
            issues.append(issue)
        
        # Check gender ambiguity
        issue = check_gender_ambiguity(segment)
        if issue:
            issues.append(issue)
        
        # Check overlap with next segment
        if i < len(sorted_segments) - 1:
            issue = check_overlap(segment, sorted_segments[i + 1])
            if issue:
                issues.append(issue)
    
    # Build summary
    errors = [i for i in issues if i.severity == QCIssueSeverity.ERROR]
    warnings = [i for i in issues if i.severity == QCIssueSeverity.WARNING]
    
    by_type: dict[str, int] = {}
    for issue in issues:
        type_name = issue.issue_type.value
        by_type[type_name] = by_type.get(type_name, 0) + 1
    
    summary = QCSummary(
        total_cues=len(segments),
        issues_count=len(issues),
        errors_count=len(errors),
        warnings_count=len(warnings),
        passed=len(errors) == 0,
        by_type=by_type
    )
    
    return QCReport(issues=issues, summary=summary)


# Re-export for convenience
__all__ = ["run_qc_checks", "QCIssue", "QCReport"]
