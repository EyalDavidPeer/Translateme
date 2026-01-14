"""Tests for SRT and VTT parsing."""

import pytest
from pathlib import Path

from app.parsing import parse_srt, parse_vtt
from app.parsing.base import (
    parse_timestamp_srt,
    parse_timestamp_vtt,
    format_timestamp_srt,
    format_timestamp_vtt,
)


class TestTimestampParsing:
    """Tests for timestamp parsing functions."""
    
    def test_parse_srt_timestamp_basic(self):
        assert parse_timestamp_srt("00:00:01,000") == 1000
        assert parse_timestamp_srt("00:01:00,000") == 60000
        assert parse_timestamp_srt("01:00:00,000") == 3600000
    
    def test_parse_srt_timestamp_with_millis(self):
        assert parse_timestamp_srt("00:00:01,500") == 1500
        assert parse_timestamp_srt("00:00:01,001") == 1001
        assert parse_timestamp_srt("00:00:01,999") == 1999
    
    def test_parse_srt_timestamp_complex(self):
        assert parse_timestamp_srt("01:23:45,678") == 5025678
    
    def test_parse_srt_timestamp_invalid(self):
        with pytest.raises(ValueError):
            parse_timestamp_srt("invalid")
        with pytest.raises(ValueError):
            parse_timestamp_srt("00:00:01.000")  # VTT format
    
    def test_parse_vtt_timestamp_basic(self):
        assert parse_timestamp_vtt("00:00:01.000") == 1000
        assert parse_timestamp_vtt("00:01:00.000") == 60000
        assert parse_timestamp_vtt("01:00:00.000") == 3600000
    
    def test_parse_vtt_timestamp_short_format(self):
        # VTT allows MM:SS.mmm format
        assert parse_timestamp_vtt("01:30.500") == 90500
        assert parse_timestamp_vtt("00:05.000") == 5000
    
    def test_format_srt_timestamp(self):
        assert format_timestamp_srt(1000) == "00:00:01,000"
        assert format_timestamp_srt(5025678) == "01:23:45,678"
        assert format_timestamp_srt(0) == "00:00:00,000"
    
    def test_format_vtt_timestamp(self):
        assert format_timestamp_vtt(1000) == "00:00:01.000"
        assert format_timestamp_vtt(5025678) == "01:23:45.678"


class TestSRTParser:
    """Tests for SRT file parsing."""
    
    def test_parse_simple_srt(self):
        content = """1
00:00:01,000 --> 00:00:04,000
Hello world

2
00:00:05,000 --> 00:00:08,000
Goodbye world
"""
        segments = parse_srt(content)
        
        assert len(segments) == 2
        assert segments[0].index == 1
        assert segments[0].start_ms == 1000
        assert segments[0].end_ms == 4000
        assert segments[0].text == "Hello world"
        
        assert segments[1].index == 2
        assert segments[1].start_ms == 5000
        assert segments[1].end_ms == 8000
        assert segments[1].text == "Goodbye world"
    
    def test_parse_multiline_srt(self):
        content = """1
00:00:01,000 --> 00:00:04,000
Line one
Line two
"""
        segments = parse_srt(content)
        
        assert len(segments) == 1
        assert segments[0].text == "Line one\nLine two"
    
    def test_parse_srt_with_bom(self):
        content = "\ufeff1\n00:00:01,000 --> 00:00:04,000\nHello"
        segments = parse_srt(content)
        
        assert len(segments) == 1
        assert segments[0].text == "Hello"
    
    def test_parse_srt_fixture(self):
        fixture_path = Path(__file__).parent / "fixtures" / "sample.srt"
        content = fixture_path.read_text(encoding="utf-8")
        
        segments = parse_srt(content)
        
        assert len(segments) == 5
        assert segments[0].text == "Hello, and welcome to\nour presentation today."
        assert segments[4].start_ms == 16000
        assert segments[4].end_ms == 20000


class TestVTTParser:
    """Tests for WebVTT file parsing."""
    
    def test_parse_simple_vtt(self):
        content = """WEBVTT

1
00:00:01.000 --> 00:00:04.000
Hello world

2
00:00:05.000 --> 00:00:08.000
Goodbye world
"""
        segments = parse_vtt(content)
        
        assert len(segments) == 2
        assert segments[0].start_ms == 1000
        assert segments[0].end_ms == 4000
        assert segments[0].text == "Hello world"
    
    def test_parse_vtt_without_cue_ids(self):
        content = """WEBVTT

00:00:01.000 --> 00:00:04.000
First cue

00:00:05.000 --> 00:00:08.000
Second cue
"""
        segments = parse_vtt(content)
        
        assert len(segments) == 2
        assert segments[0].index == 1
        assert segments[1].index == 2
    
    def test_parse_vtt_missing_header(self):
        content = """00:00:01.000 --> 00:00:04.000
Hello world
"""
        with pytest.raises(ValueError, match="WEBVTT"):
            parse_vtt(content)
    
    def test_parse_vtt_with_metadata(self):
        content = """WEBVTT
Kind: captions
Language: en

00:00:01.000 --> 00:00:04.000
Hello world
"""
        segments = parse_vtt(content)
        
        assert len(segments) == 1
        assert segments[0].text == "Hello world"
    
    def test_parse_vtt_fixture(self):
        fixture_path = Path(__file__).parent / "fixtures" / "sample.vtt"
        content = fixture_path.read_text(encoding="utf-8")
        
        segments = parse_vtt(content)
        
        assert len(segments) == 5
