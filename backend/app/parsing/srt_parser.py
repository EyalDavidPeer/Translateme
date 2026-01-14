"""SRT subtitle file parser."""

import re
from typing import List

from ..models import SubtitleSegment
from .base import parse_timing_line_srt


def parse_srt(content: str) -> List[SubtitleSegment]:
    """
    Parse SRT subtitle content into a list of segments.
    
    SRT format:
    ```
    1
    00:00:01,000 --> 00:00:04,000
    First subtitle text
    
    2
    00:00:05,000 --> 00:00:08,000
    Second subtitle
    with multiple lines
    ```
    
    Args:
        content: Raw SRT file content
        
    Returns:
        List of SubtitleSegment objects
        
    Raises:
        ValueError: If the content cannot be parsed
    """
    segments: List[SubtitleSegment] = []
    
    # Normalize line endings and split into blocks
    content = content.replace('\r\n', '\n').replace('\r', '\n')
    
    # Remove BOM if present
    if content.startswith('\ufeff'):
        content = content[1:]
    
    # Split by blank lines to get cue blocks
    blocks = re.split(r'\n\s*\n', content.strip())
    
    for block in blocks:
        block = block.strip()
        if not block:
            continue
            
        lines = block.split('\n')
        if len(lines) < 2:
            continue
        
        # First line should be the cue index
        try:
            index = int(lines[0].strip())
        except ValueError:
            # Skip blocks that don't start with a number
            continue
        
        # Second line should be the timing
        try:
            start_ms, end_ms = parse_timing_line_srt(lines[1])
        except ValueError:
            # Skip blocks with invalid timing
            continue
        
        # Remaining lines are the subtitle text
        text_lines = lines[2:]
        text = '\n'.join(line.strip() for line in text_lines if line.strip())
        
        # Skip empty cues
        if not text:
            text = ""  # Allow empty text, QC will flag it
        
        segment = SubtitleSegment(
            index=index,
            start_ms=start_ms,
            end_ms=end_ms,
            text=text
        )
        segments.append(segment)
    
    # Sort by start time to ensure proper order
    segments.sort(key=lambda s: (s.start_ms, s.index))
    
    return segments
