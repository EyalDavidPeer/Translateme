"""WebVTT subtitle file exporter."""

from typing import List

from ..models import SubtitleSegment
from ..parsing.base import format_timestamp_vtt


def export_vtt(
    segments: List[SubtitleSegment],
    use_translated: bool = True
) -> str:
    """
    Export segments to WebVTT format.
    
    Args:
        segments: List of subtitle segments
        use_translated: If True, use translated_text when available
        
    Returns:
        VTT file content as string
    """
    lines: List[str] = []
    
    # VTT header
    lines.append("WEBVTT")
    lines.append("")
    
    # Sort segments by start time
    sorted_segments = sorted(segments, key=lambda s: (s.start_ms, s.index))
    
    for i, segment in enumerate(sorted_segments, 1):
        # Cue identifier (optional but helpful)
        lines.append(str(i))
        
        # Timing line
        start = format_timestamp_vtt(segment.start_ms)
        end = format_timestamp_vtt(segment.end_ms)
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
