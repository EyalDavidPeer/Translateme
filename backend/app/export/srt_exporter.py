"""SRT subtitle file exporter."""

from typing import List

from ..models import SubtitleSegment
from ..parsing.base import format_timestamp_srt


def export_srt(
    segments: List[SubtitleSegment],
    use_translated: bool = True
) -> str:
    """
    Export segments to SRT format.
    
    Args:
        segments: List of subtitle segments
        use_translated: If True, use translated_text when available
        
    Returns:
        SRT file content as string
    """
    lines: List[str] = []
    
    # Sort segments by start time
    sorted_segments = sorted(segments, key=lambda s: (s.start_ms, s.index))
    
    for i, segment in enumerate(sorted_segments, 1):
        # Cue index
        lines.append(str(i))
        
        # Timing line
        start = format_timestamp_srt(segment.start_ms)
        end = format_timestamp_srt(segment.end_ms)
        lines.append(f"{start} --> {end}")
        
        # Text (use translated if available and requested)
        if use_translated and segment.translated_text is not None:
            text = segment.translated_text
        else:
            text = segment.text
        
        lines.append(text)
        
        # Blank line between cues
        lines.append("")
    
    return "\n".join(lines)
