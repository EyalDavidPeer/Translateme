"""Tests for QC checks."""

import pytest

from app.models import SubtitleSegment, JobConstraints, QCIssueType, QCIssueSeverity
from app.qc.checks import (
    check_cps,
    check_line_length,
    check_line_count,
    check_empty_cue,
    check_overlap,
    check_short_duration,
    run_qc_checks,
)


class TestCPSCheck:
    """Tests for CPS (characters per second) check."""
    
    def test_cps_within_limit(self):
        # 10 chars in 1 second = 10 CPS (under 17)
        segment = SubtitleSegment(
            index=1, start_ms=0, end_ms=1000, text="1234567890"
        )
        issue = check_cps(segment, max_cps=17.0, use_translated=False)
        assert issue is None
    
    def test_cps_exceeds_limit(self):
        # 20 chars in 1 second = 20 CPS (over 17)
        segment = SubtitleSegment(
            index=1, start_ms=0, end_ms=1000, text="12345678901234567890"
        )
        issue = check_cps(segment, max_cps=17.0, use_translated=False)
        
        assert issue is not None
        assert issue.issue_type == QCIssueType.CPS_EXCEEDED
        assert issue.severity == QCIssueSeverity.ERROR
        assert issue.value == 20.0
    
    def test_cps_ignores_newlines(self):
        # 10 chars + newline in 1 second = 10 CPS
        segment = SubtitleSegment(
            index=1, start_ms=0, end_ms=1000, text="12345\n67890"
        )
        issue = check_cps(segment, max_cps=17.0, use_translated=False)
        assert issue is None
    
    def test_cps_zero_duration(self):
        segment = SubtitleSegment(
            index=1, start_ms=1000, end_ms=1000, text="Hello"
        )
        issue = check_cps(segment, max_cps=17.0, use_translated=False)
        
        assert issue is not None
        assert issue.issue_type == QCIssueType.CPS_EXCEEDED


class TestLineLengthCheck:
    """Tests for line length check."""
    
    def test_line_within_limit(self):
        segment = SubtitleSegment(
            index=1, start_ms=0, end_ms=1000, text="Short line"
        )
        issue = check_line_length(segment, max_chars_per_line=42, use_translated=False)
        assert issue is None
    
    def test_line_exceeds_limit(self):
        long_line = "A" * 50  # 50 chars, over 42 limit
        segment = SubtitleSegment(
            index=1, start_ms=0, end_ms=1000, text=long_line
        )
        issue = check_line_length(segment, max_chars_per_line=42, use_translated=False)
        
        assert issue is not None
        assert issue.issue_type == QCIssueType.LINE_TOO_LONG
        assert issue.value == 50
    
    def test_multiline_checks_each(self):
        # First line OK, second line too long
        text = "Short\n" + "B" * 50
        segment = SubtitleSegment(
            index=1, start_ms=0, end_ms=1000, text=text
        )
        issue = check_line_length(segment, max_chars_per_line=42, use_translated=False)
        
        assert issue is not None


class TestLineCountCheck:
    """Tests for line count check."""
    
    def test_two_lines_ok(self):
        segment = SubtitleSegment(
            index=1, start_ms=0, end_ms=1000, text="Line 1\nLine 2"
        )
        issue = check_line_count(segment, max_lines=2, use_translated=False)
        assert issue is None
    
    def test_three_lines_exceeds(self):
        segment = SubtitleSegment(
            index=1, start_ms=0, end_ms=1000, text="Line 1\nLine 2\nLine 3"
        )
        issue = check_line_count(segment, max_lines=2, use_translated=False)
        
        assert issue is not None
        assert issue.issue_type == QCIssueType.TOO_MANY_LINES
        assert issue.value == 3


class TestEmptyCueCheck:
    """Tests for empty cue check."""
    
    def test_non_empty_ok(self):
        segment = SubtitleSegment(
            index=1, start_ms=0, end_ms=1000, text="Hello"
        )
        issue = check_empty_cue(segment, use_translated=False)
        assert issue is None
    
    def test_empty_text(self):
        segment = SubtitleSegment(
            index=1, start_ms=0, end_ms=1000, text=""
        )
        issue = check_empty_cue(segment, use_translated=False)
        
        assert issue is not None
        assert issue.issue_type == QCIssueType.EMPTY_CUE
        assert issue.severity == QCIssueSeverity.WARNING
    
    def test_whitespace_only(self):
        segment = SubtitleSegment(
            index=1, start_ms=0, end_ms=1000, text="   \n  \t  "
        )
        issue = check_empty_cue(segment, use_translated=False)
        
        assert issue is not None
        assert issue.issue_type == QCIssueType.EMPTY_CUE


class TestOverlapCheck:
    """Tests for overlap detection."""
    
    def test_no_overlap(self):
        seg1 = SubtitleSegment(index=1, start_ms=0, end_ms=1000, text="A")
        seg2 = SubtitleSegment(index=2, start_ms=1000, end_ms=2000, text="B")
        
        issue = check_overlap(seg1, seg2)
        assert issue is None
    
    def test_overlap_detected(self):
        seg1 = SubtitleSegment(index=1, start_ms=0, end_ms=1500, text="A")
        seg2 = SubtitleSegment(index=2, start_ms=1000, end_ms=2000, text="B")
        
        issue = check_overlap(seg1, seg2)
        
        assert issue is not None
        assert issue.issue_type == QCIssueType.OVERLAP
        assert issue.value == 500  # 500ms overlap


class TestShortDurationCheck:
    """Tests for short duration check."""
    
    def test_duration_ok(self):
        segment = SubtitleSegment(
            index=1, start_ms=0, end_ms=1000, text="Hello"
        )
        issue = check_short_duration(segment, min_duration_ms=500)
        assert issue is None
    
    def test_duration_too_short(self):
        segment = SubtitleSegment(
            index=1, start_ms=0, end_ms=300, text="Hi"
        )
        issue = check_short_duration(segment, min_duration_ms=500)
        
        assert issue is not None
        assert issue.issue_type == QCIssueType.SHORT_DURATION
        assert issue.value == 300


class TestRunQCChecks:
    """Tests for the full QC check runner."""
    
    def test_all_pass(self):
        segments = [
            SubtitleSegment(index=1, start_ms=0, end_ms=2000, text="Hello world"),
            SubtitleSegment(index=2, start_ms=3000, end_ms=5000, text="Goodbye world"),
        ]
        constraints = JobConstraints()
        
        report = run_qc_checks(segments, constraints, use_translated=False)
        
        assert report.summary.passed is True
        assert report.summary.errors_count == 0
        assert report.summary.issues_count == 0
    
    def test_multiple_issues(self):
        segments = [
            # CPS issue: 50 chars in 1 second = 50 CPS
            SubtitleSegment(index=1, start_ms=0, end_ms=1000, text="A" * 50),
            # Short duration issue
            SubtitleSegment(index=2, start_ms=2000, end_ms=2200, text="B"),
        ]
        constraints = JobConstraints(max_cps=17.0, min_duration_ms=500)
        
        report = run_qc_checks(segments, constraints, use_translated=False)
        
        assert report.summary.passed is False
        assert report.summary.errors_count >= 1
        assert report.summary.issues_count >= 2
    
    def test_summary_by_type(self):
        segments = [
            SubtitleSegment(index=1, start_ms=0, end_ms=1000, text="A" * 50),  # CPS
            SubtitleSegment(index=2, start_ms=1000, end_ms=2000, text="B" * 50),  # CPS
            SubtitleSegment(index=3, start_ms=3000, end_ms=3100, text="C"),  # Short
        ]
        constraints = JobConstraints(max_cps=17.0, min_duration_ms=500)
        
        report = run_qc_checks(segments, constraints, use_translated=False)
        
        assert "cps_exceeded" in report.summary.by_type
        assert "short_duration" in report.summary.by_type
