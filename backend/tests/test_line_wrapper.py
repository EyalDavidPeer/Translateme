"""Tests for line wrapping functionality."""

import pytest

from app.postprocess.line_wrapper import (
    wrap_lines,
    find_best_break_point,
    needs_wrapping,
    balance_lines,
)


class TestFindBestBreakPoint:
    """Tests for finding optimal line break points."""
    
    def test_short_text_no_break_needed(self):
        text = "Hello world"
        assert find_best_break_point(text, 42) == len(text)
    
    def test_break_at_comma(self):
        text = "Hello, world and everyone"
        # Should prefer breaking after comma
        break_point = find_best_break_point(text, 15)
        assert text[:break_point].strip().endswith(",")
    
    def test_break_at_period(self):
        text = "First sentence. Second sentence"
        break_point = find_best_break_point(text, 20)
        assert "." in text[:break_point]
    
    def test_break_at_space_when_no_punctuation(self):
        text = "Hello world again"
        break_point = find_best_break_point(text, 13)
        # Should break at a word boundary
        first_part = text[:break_point]
        assert first_part.strip() in ["Hello world", "Hello"]


class TestWrapLines:
    """Tests for the main line wrapping function."""
    
    def test_short_text_unchanged(self):
        text = "Hello world"
        result = wrap_lines(text, max_chars_per_line=42)
        assert result == text
    
    def test_splits_long_text(self):
        text = "This is a longer piece of text that needs to be split across two lines"
        result = wrap_lines(text, max_chars_per_line=42, max_lines=2)
        
        lines = result.split('\n')
        assert len(lines) == 2
        for line in lines:
            assert len(line) <= 42
    
    def test_respects_max_lines(self):
        text = "A " * 100  # Very long text
        result = wrap_lines(text, max_chars_per_line=42, max_lines=2)
        
        lines = result.split('\n')
        assert len(lines) <= 2
    
    def test_preserves_short_text(self):
        text = "Short"
        result = wrap_lines(text, max_chars_per_line=42)
        assert result == "Short"
    
    def test_handles_empty_text(self):
        result = wrap_lines("", max_chars_per_line=42)
        assert result == ""
    
    def test_normalizes_whitespace(self):
        text = "Hello   world    test"
        result = wrap_lines(text, max_chars_per_line=42)
        assert "   " not in result
    
    def test_prefers_punctuation_break(self):
        text = "Hello, this is a test of the line wrapping system"
        result = wrap_lines(text, max_chars_per_line=30, max_lines=2)
        
        lines = result.split('\n')
        # First line should end near punctuation or at word boundary
        assert len(lines[0]) <= 30


class TestBalanceLines:
    """Tests for line balancing."""
    
    def test_balance_two_uneven_lines(self):
        lines = ["Hello world", "test"]
        balanced = balance_lines(lines, max_chars=42)
        
        # Should redistribute to be more even
        assert len(balanced) == 2
        # Lengths should be closer together
        len_diff = abs(len(balanced[0]) - len(balanced[1]))
        original_diff = abs(len(lines[0]) - len(lines[1]))
        assert len_diff <= original_diff
    
    def test_balance_respects_max(self):
        lines = ["A" * 30, "B" * 30]
        balanced = balance_lines(lines, max_chars=35)
        
        # Should not exceed max
        for line in balanced:
            assert len(line) <= 35


class TestNeedsWrapping:
    """Tests for wrapping detection."""
    
    def test_short_single_line_no_wrap(self):
        assert needs_wrapping("Hello", max_chars_per_line=42) is False
    
    def test_long_line_needs_wrap(self):
        text = "A" * 50
        assert needs_wrapping(text, max_chars_per_line=42) is True
    
    def test_too_many_lines_needs_wrap(self):
        text = "Line 1\nLine 2\nLine 3"
        assert needs_wrapping(text, max_chars_per_line=42, max_lines=2) is True
    
    def test_acceptable_two_lines(self):
        text = "Line 1\nLine 2"
        assert needs_wrapping(text, max_chars_per_line=42, max_lines=2) is False
