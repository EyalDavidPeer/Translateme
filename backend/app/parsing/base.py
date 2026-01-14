"""Base classes and utilities for subtitle parsing."""

import re
from typing import Tuple

from ..models import SubtitleSegment


def parse_timestamp_srt(timestamp: str) -> int:
    """
    Parse SRT timestamp format (HH:MM:SS,mmm) to milliseconds.
    
    Args:
        timestamp: Timestamp string in format "HH:MM:SS,mmm"
        
    Returns:
        Time in milliseconds
        
    Raises:
        ValueError: If timestamp format is invalid
    """
    pattern = r"(\d{1,2}):(\d{2}):(\d{2}),(\d{3})"
    match = re.match(pattern, timestamp.strip())
    if not match:
        raise ValueError(f"Invalid SRT timestamp format: {timestamp}")
    
    hours, minutes, seconds, millis = match.groups()
    return (
        int(hours) * 3600000 +
        int(minutes) * 60000 +
        int(seconds) * 1000 +
        int(millis)
    )


def parse_timestamp_vtt(timestamp: str) -> int:
    """
    Parse VTT timestamp format (HH:MM:SS.mmm or MM:SS.mmm) to milliseconds.
    
    Args:
        timestamp: Timestamp string in format "HH:MM:SS.mmm" or "MM:SS.mmm"
        
    Returns:
        Time in milliseconds
        
    Raises:
        ValueError: If timestamp format is invalid
    """
    # Try HH:MM:SS.mmm format first
    pattern_full = r"(\d{1,2}):(\d{2}):(\d{2})\.(\d{3})"
    match = re.match(pattern_full, timestamp.strip())
    if match:
        hours, minutes, seconds, millis = match.groups()
        return (
            int(hours) * 3600000 +
            int(minutes) * 60000 +
            int(seconds) * 1000 +
            int(millis)
        )
    
    # Try MM:SS.mmm format
    pattern_short = r"(\d{1,2}):(\d{2})\.(\d{3})"
    match = re.match(pattern_short, timestamp.strip())
    if match:
        minutes, seconds, millis = match.groups()
        return (
            int(minutes) * 60000 +
            int(seconds) * 1000 +
            int(millis)
        )
    
    raise ValueError(f"Invalid VTT timestamp format: {timestamp}")


def format_timestamp_srt(ms: int) -> str:
    """
    Format milliseconds to SRT timestamp format (HH:MM:SS,mmm).
    
    Args:
        ms: Time in milliseconds
        
    Returns:
        Formatted timestamp string
    """
    hours = ms // 3600000
    ms %= 3600000
    minutes = ms // 60000
    ms %= 60000
    seconds = ms // 1000
    millis = ms % 1000
    
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{millis:03d}"


def format_timestamp_vtt(ms: int) -> str:
    """
    Format milliseconds to VTT timestamp format (HH:MM:SS.mmm).
    
    Args:
        ms: Time in milliseconds
        
    Returns:
        Formatted timestamp string
    """
    hours = ms // 3600000
    ms %= 3600000
    minutes = ms // 60000
    ms %= 60000
    seconds = ms // 1000
    millis = ms % 1000
    
    return f"{hours:02d}:{minutes:02d}:{seconds:02d}.{millis:03d}"


def parse_timing_line_srt(line: str) -> Tuple[int, int]:
    """
    Parse SRT timing line (start --> end).
    
    Args:
        line: Timing line in format "HH:MM:SS,mmm --> HH:MM:SS,mmm"
        
    Returns:
        Tuple of (start_ms, end_ms)
        
    Raises:
        ValueError: If timing line format is invalid
    """
    parts = line.split("-->")
    if len(parts) != 2:
        raise ValueError(f"Invalid timing line: {line}")
    
    start_ms = parse_timestamp_srt(parts[0].strip())
    end_ms = parse_timestamp_srt(parts[1].strip())
    
    return start_ms, end_ms


def parse_timing_line_vtt(line: str) -> Tuple[int, int]:
    """
    Parse VTT timing line (start --> end), ignoring optional cue settings.
    
    Args:
        line: Timing line in format "HH:MM:SS.mmm --> HH:MM:SS.mmm [settings]"
        
    Returns:
        Tuple of (start_ms, end_ms)
        
    Raises:
        ValueError: If timing line format is invalid
    """
    # Split by --> and handle optional cue settings after end time
    parts = line.split("-->")
    if len(parts) != 2:
        raise ValueError(f"Invalid timing line: {line}")
    
    start_ms = parse_timestamp_vtt(parts[0].strip())
    
    # End time might have cue settings after it, separated by space
    end_part = parts[1].strip().split()[0]
    end_ms = parse_timestamp_vtt(end_part)
    
    return start_ms, end_ms


# Re-export SubtitleSegment for convenience
__all__ = [
    "SubtitleSegment",
    "parse_timestamp_srt",
    "parse_timestamp_vtt", 
    "format_timestamp_srt",
    "format_timestamp_vtt",
    "parse_timing_line_srt",
    "parse_timing_line_vtt",
]
