"""Tests for SRT and VTT export."""

import pytest

from app.models import SubtitleSegment
from app.export import export_srt, export_vtt
from app.parsing import parse_srt, parse_vtt


class TestSRTExport:
    """Tests for SRT export."""
    
    def test_export_simple_srt(self):
        segments = [
            SubtitleSegment(index=1, start_ms=1000, end_ms=4000, text="Hello world"),
            SubtitleSegment(index=2, start_ms=5000, end_ms=8000, text="Goodbye world"),
        ]
        
        result = export_srt(segments, use_translated=False)
        
        assert "1\n00:00:01,000 --> 00:00:04,000\nHello world" in result
        assert "2\n00:00:05,000 --> 00:00:08,000\nGoodbye world" in result
    
    def test_export_with_translation(self):
        segments = [
            SubtitleSegment(
                index=1,
                start_ms=1000,
                end_ms=4000,
                text="Hello world",
                translated_text="שלום עולם"
            ),
        ]
        
        result = export_srt(segments, use_translated=True)
        assert "שלום עולם" in result
        assert "Hello world" not in result
    
    def test_export_multiline(self):
        segments = [
            SubtitleSegment(index=1, start_ms=1000, end_ms=4000, text="Line one\nLine two"),
        ]
        
        result = export_srt(segments, use_translated=False)
        assert "Line one\nLine two" in result


class TestVTTExport:
    """Tests for VTT export."""
    
    def test_export_simple_vtt(self):
        segments = [
            SubtitleSegment(index=1, start_ms=1000, end_ms=4000, text="Hello world"),
        ]
        
        result = export_vtt(segments, use_translated=False)
        
        assert result.startswith("WEBVTT")
        assert "00:00:01.000 --> 00:00:04.000" in result
        assert "Hello world" in result
    
    def test_export_vtt_uses_period(self):
        segments = [
            SubtitleSegment(index=1, start_ms=1500, end_ms=4500, text="Test"),
        ]
        
        result = export_vtt(segments, use_translated=False)
        
        # VTT uses period, not comma
        assert "00:00:01.500" in result
        assert "00:00:04.500" in result


class TestRoundTrip:
    """Test parsing and exporting preserves content."""
    
    def test_srt_round_trip(self):
        original = """1
00:00:01,000 --> 00:00:04,000
Hello world

2
00:00:05,000 --> 00:00:08,000
Goodbye world

"""
        segments = parse_srt(original)
        exported = export_srt(segments, use_translated=False)
        re_parsed = parse_srt(exported)
        
        assert len(re_parsed) == len(segments)
        for orig, reparsed in zip(segments, re_parsed):
            assert orig.start_ms == reparsed.start_ms
            assert orig.end_ms == reparsed.end_ms
            assert orig.text == reparsed.text
    
    def test_vtt_round_trip(self):
        original = """WEBVTT

1
00:00:01.000 --> 00:00:04.000
Hello world

2
00:00:05.000 --> 00:00:08.000
Goodbye world

"""
        segments = parse_vtt(original)
        exported = export_vtt(segments, use_translated=False)
        re_parsed = parse_vtt(exported)
        
        assert len(re_parsed) == len(segments)
        for orig, reparsed in zip(segments, re_parsed):
            assert orig.start_ms == reparsed.start_ms
            assert orig.end_ms == reparsed.end_ms
            assert orig.text == reparsed.text
