"""WebVTT subtitle file parser."""

import re
from typing import List

from ..models import SubtitleSegment
from .base import parse_timing_line_vtt


def parse_vtt(content: str) -> List[SubtitleSegment]:
    """
    Parse WebVTT subtitle content into a list of segments.
    
    VTT format:
    ```
    WEBVTT
    
    1
    00:00:01.000 --> 00:00:04.000
    First subtitle text
    
    00:00:05.000 --> 00:00:08.000
    Second subtitle
    with multiple lines
    ```
    
    Note: VTT cue identifiers are optional.
    
    Args:
        content: Raw VTT file content
        
    Returns:
        List of SubtitleSegment objects
        
    Raises:
        ValueError: If the content cannot be parsed or is not valid VTT
    """
    segments: List[SubtitleSegment] = []
    
    # Normalize line endings
    content = content.replace('\r\n', '\n').replace('\r', '\n')
    
    # Remove BOM if present
    if content.startswith('\ufeff'):
        content = content[1:]
    
    lines = content.split('\n')
    
    # Check for WEBVTT header
    header_found = False
    start_idx = 0
    for i, line in enumerate(lines):
        stripped = line.strip()
        if stripped.startswith('WEBVTT'):
            header_found = True
            start_idx = i + 1
            break
        elif stripped:
            # Non-empty line before WEBVTT header
            break
    
    if not header_found:
        raise ValueError("Invalid VTT file: missing WEBVTT header")
    
    # Skip any header metadata (lines until first blank line or timing line)
    while start_idx < len(lines):
        line = lines[start_idx].strip()
        if not line or '-->' in line:
            break
        start_idx += 1
    
    # Parse cues
    current_index = 0
    i = start_idx
    
    while i < len(lines):
        line = lines[i].strip()
        
        # Skip empty lines
        if not line:
            i += 1
            continue
        
        # Skip NOTE blocks
        if line.startswith('NOTE'):
            i += 1
            while i < len(lines) and lines[i].strip():
                i += 1
            continue
        
        # Skip STYLE blocks
        if line.startswith('STYLE'):
            i += 1
            while i < len(lines) and lines[i].strip():
                i += 1
            continue
        
        # Skip REGION blocks
        if line.startswith('REGION'):
            i += 1
            while i < len(lines) and lines[i].strip():
                i += 1
            continue
        
        # Check if this is a timing line or cue identifier
        cue_id = None
        timing_line = None
        
        if '-->' in line:
            # This line is the timing line directly
            timing_line = line
        else:
            # This might be a cue identifier, next line should be timing
            if i + 1 < len(lines) and '-->' in lines[i + 1]:
                cue_id = line
                i += 1
                timing_line = lines[i].strip()
            else:
                # Unknown content, skip
                i += 1
                continue
        
        # Parse timing
        try:
            start_ms, end_ms = parse_timing_line_vtt(timing_line)
        except ValueError:
            i += 1
            continue
        
        # Collect text lines until blank line or end
        i += 1
        text_lines = []
        while i < len(lines):
            text_line = lines[i]
            if not text_line.strip():
                break
            # Stop if we hit another timing line
            if '-->' in text_line:
                # Back up, this is the next cue
                break
            text_lines.append(text_line.strip())
            i += 1
        
        text = '\n'.join(text_lines)
        
        # Increment index
        current_index += 1
        
        # Use cue_id as index if it's numeric, otherwise use sequential
        if cue_id and cue_id.isdigit():
            idx = int(cue_id)
        else:
            idx = current_index
        
        segment = SubtitleSegment(
            index=idx,
            start_ms=start_ms,
            end_ms=end_ms,
            text=text
        )
        segments.append(segment)
    
    # Sort by start time
    segments.sort(key=lambda s: (s.start_ms, s.index))
    
    # Re-index sequentially
    for i, segment in enumerate(segments, 1):
        segment.index = i
    
    return segments
