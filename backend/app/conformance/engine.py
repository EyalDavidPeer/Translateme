"""Subtitle Conformance Engine for ensuring platform compliance."""

import json
import re
from typing import List, Dict, Optional, Any
from dataclasses import dataclass

from ..models import SubtitleSegment, JobConstraints
from ..translation.provider import TranslationProvider
from .prompts import format_conformance_prompt


@dataclass
class ConformanceResult:
    """Result of conformance check for a single cue."""
    id: int
    start_ms: int
    end_ms: int
    lines: List[str]
    actions: List[str]
    notes: str
    original_text: str


def ms_to_srt_time(ms: int) -> str:
    """Convert milliseconds to SRT timestamp format HH:MM:SS,mmm."""
    hours = ms // 3600000
    minutes = (ms % 3600000) // 60000
    seconds = (ms % 60000) // 1000
    millis = ms % 1000
    return f"{hours:02d}:{minutes:02d}:{seconds:02d},{millis:03d}"


def srt_time_to_ms(time_str: str) -> int:
    """Convert SRT timestamp HH:MM:SS,mmm to milliseconds."""
    # Handle both comma and period as decimal separator
    time_str = time_str.replace('.', ',')
    match = re.match(r'(\d{1,2}):(\d{2}):(\d{2}),(\d{3})', time_str)
    if not match:
        raise ValueError(f"Invalid time format: {time_str}")
    
    hours, minutes, seconds, millis = map(int, match.groups())
    return hours * 3600000 + minutes * 60000 + seconds * 1000 + millis


def segments_to_cues(segments: List[SubtitleSegment], use_translated: bool = True) -> List[Dict]:
    """Convert SubtitleSegments to cue dictionaries for the conformance engine."""
    cues = []
    for seg in segments:
        text = seg.translated_text if use_translated and seg.translated_text else seg.text
        lines = text.split('\n') if text else []
        
        cues.append({
            "id": seg.index,
            "start": ms_to_srt_time(seg.start_ms),
            "end": ms_to_srt_time(seg.end_ms),
            "lines": lines
        })
    
    return cues


def parse_conformance_response(response_text: str) -> List[Dict]:
    """Parse the JSON response from the conformance engine."""
    # Try to extract JSON from the response
    response_text = response_text.strip()
    
    # Remove markdown code blocks if present
    if response_text.startswith('```'):
        lines = response_text.split('\n')
        # Remove first and last lines (```json and ```)
        lines = [l for l in lines if not l.strip().startswith('```')]
        response_text = '\n'.join(lines)
    
    try:
        data = json.loads(response_text)
        if isinstance(data, dict) and "cues" in data:
            return data["cues"]
        elif isinstance(data, list):
            return data
        else:
            return []
    except json.JSONDecodeError:
        # Try to find JSON object in the response
        match = re.search(r'\{[\s\S]*"cues"[\s\S]*\}', response_text)
        if match:
            try:
                data = json.loads(match.group())
                return data.get("cues", [])
            except json.JSONDecodeError:
                pass
        return []


class ConformanceEngine:
    """
    Engine for ensuring subtitle compliance with platform constraints.
    
    Uses LLM to intelligently reflow, extend timing, or compress text
    while preserving meaning.
    """
    
    def __init__(self, provider: TranslationProvider):
        self.provider = provider
    
    async def conform_batch(
        self,
        segments: List[SubtitleSegment],
        constraints: JobConstraints,
        language: str = "Hebrew",
        use_translated: bool = True
    ) -> List[SubtitleSegment]:
        """
        Apply conformance rules to a batch of segments.
        
        Args:
            segments: List of subtitle segments to conform
            constraints: Platform constraints
            language: Target language name
            use_translated: Whether to use translated_text or original text
            
        Returns:
            List of conformed segments
        """
        if not segments:
            return segments
        
        # Convert segments to cues format
        cues = segments_to_cues(segments, use_translated)
        
        # Format prompt
        system_prompt, user_prompt = format_conformance_prompt(
            cues=cues,
            language=language,
            max_lines=constraints.max_lines,
            max_chars_per_line=constraints.max_chars_per_line,
            max_cps=constraints.max_cps,
            min_duration_seconds=constraints.min_duration_ms / 1000.0,
            min_gap_seconds=0.08  # 80ms minimum gap
        )
        
        # Call LLM
        try:
            response = await self.provider.client.chat.completions.create(
                model=self.provider.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.2,  # Low temperature for consistent conformance
                max_tokens=4000
            )
            
            response_text = response.choices[0].message.content or ""
            conformed_cues = parse_conformance_response(response_text)
            
            # Apply conformed cues back to segments
            return self._apply_conformance(segments, conformed_cues, use_translated)
            
        except Exception as e:
            print(f"[WARN] Conformance failed: {e}, returning original segments")
            return segments
    
    def _apply_conformance(
        self,
        segments: List[SubtitleSegment],
        conformed_cues: List[Dict],
        use_translated: bool
    ) -> List[SubtitleSegment]:
        """Apply conformed cues back to segment objects."""
        # Build lookup by ID
        cue_lookup = {cue.get("id"): cue for cue in conformed_cues}
        
        for seg in segments:
            cue = cue_lookup.get(seg.index)
            if not cue:
                continue
            
            # Update timing if changed
            if "start" in cue:
                try:
                    seg.start_ms = srt_time_to_ms(cue["start"])
                except ValueError:
                    pass
            
            if "end" in cue:
                try:
                    seg.end_ms = srt_time_to_ms(cue["end"])
                except ValueError:
                    pass
            
            # Update text
            if "lines" in cue and cue["lines"]:
                new_text = "\n".join(cue["lines"])
                if use_translated:
                    seg.translated_text = new_text
                else:
                    seg.text = new_text
            
            # Store conformance actions in qc_flags for reporting
            if "actions" in cue:
                actions = cue["actions"]
                if isinstance(actions, list):
                    for action in actions:
                        if action not in ["NONE"] and action not in seg.qc_flags:
                            seg.qc_flags.append(f"CONFORMED:{action}")
        
        return segments


async def conform_subtitles(
    segments: List[SubtitleSegment],
    constraints: JobConstraints,
    language: str,
    provider: TranslationProvider,
    batch_size: int = 10
) -> List[SubtitleSegment]:
    """
    Apply conformance rules to subtitle segments in batches.
    
    Args:
        segments: All subtitle segments
        constraints: Platform constraints
        language: Target language name
        provider: Translation provider with LLM access
        batch_size: Number of segments to process at once
        
    Returns:
        Conformed segments
    """
    engine = ConformanceEngine(provider)
    
    # Process in batches to avoid token limits
    for i in range(0, len(segments), batch_size):
        batch = segments[i:i + batch_size]
        
        # Include next segment for gap calculation
        next_seg = segments[i + batch_size] if i + batch_size < len(segments) else None
        if next_seg:
            batch_with_context = batch + [next_seg]
        else:
            batch_with_context = batch
        
        conformed = await engine.conform_batch(
            segments=batch_with_context,
            constraints=constraints,
            language=language
        )
        
        # Update original segments (excluding context segment)
        for j, seg in enumerate(batch):
            if j < len(conformed):
                segments[i + j] = conformed[j]
    
    return segments
