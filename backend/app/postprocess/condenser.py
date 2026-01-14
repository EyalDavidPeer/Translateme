"""Text condensation for CPS violation fixes."""

from typing import Optional, TYPE_CHECKING

from ..models import SubtitleSegment, JobConstraints

if TYPE_CHECKING:
    from ..translation.provider import TranslationProvider


async def condense_text(
    text: str,
    target_chars: int,
    target_lang: str,
    provider: "TranslationProvider"
) -> str:
    """
    Condense text to fit within character limit using LLM.
    
    Args:
        text: Text to condense
        target_chars: Target maximum characters
        target_lang: Target language code
        provider: Translation provider to use for condensation
        
    Returns:
        Condensed text
    """
    if len(text) <= target_chars:
        return text
    
    return await provider.condense_text(text, target_chars, target_lang)


def calculate_target_chars(
    segment: SubtitleSegment,
    max_cps: float
) -> int:
    """
    Calculate target character count based on CPS constraint.
    
    Args:
        segment: The subtitle segment
        max_cps: Maximum characters per second
        
    Returns:
        Target character count
    """
    duration_seconds = segment.duration_seconds
    if duration_seconds <= 0:
        return 0
    
    # Calculate max chars based on duration and CPS
    # Use 90% of max to provide some buffer
    max_chars = int(duration_seconds * max_cps * 0.9)
    
    return max(max_chars, 10)  # Minimum 10 chars


async def fix_cps_violation(
    segment: SubtitleSegment,
    constraints: JobConstraints,
    target_lang: str,
    provider: "TranslationProvider"
) -> bool:
    """
    Attempt to fix a CPS violation by condensing the translated text.
    
    Args:
        segment: The segment to fix (modified in place)
        constraints: Job constraints
        target_lang: Target language code
        provider: Translation provider for condensation
        
    Returns:
        True if the violation was fixed, False otherwise
    """
    text = segment.translated_text or segment.text
    current_cps = segment.calculate_cps(use_translated=True)
    
    if current_cps <= constraints.max_cps:
        return True  # No violation
    
    # Calculate target character count
    target_chars = calculate_target_chars(segment, constraints.max_cps)
    
    if target_chars <= 0:
        return False  # Can't fix - duration too short
    
    # Attempt condensation
    condensed = await condense_text(
        text=text,
        target_chars=target_chars,
        target_lang=target_lang,
        provider=provider
    )
    
    # Check if condensation worked
    segment.translated_text = condensed
    new_cps = segment.calculate_cps(use_translated=True)
    
    return new_cps <= constraints.max_cps


async def postprocess_segments(
    segments: list[SubtitleSegment],
    constraints: JobConstraints,
    target_lang: str,
    provider: "TranslationProvider"
) -> list[SubtitleSegment]:
    """
    Post-process translated segments: wrap lines and fix CPS violations.
    
    Args:
        segments: Translated segments to post-process
        constraints: Job constraints
        target_lang: Target language code
        provider: Translation provider for condensation
        
    Returns:
        Post-processed segments
    """
    from .line_wrapper import wrap_lines, needs_wrapping
    
    for segment in segments:
        if not segment.translated_text:
            continue
        
        # First, wrap lines
        if needs_wrapping(
            segment.translated_text,
            constraints.max_chars_per_line,
            constraints.max_lines
        ):
            segment.translated_text = wrap_lines(
                segment.translated_text,
                max_chars_per_line=constraints.max_chars_per_line,
                max_lines=constraints.max_lines,
                target_lang=target_lang
            )
        
        # Then check/fix CPS
        current_cps = segment.calculate_cps(use_translated=True)
        if current_cps > constraints.max_cps:
            await fix_cps_violation(
                segment=segment,
                constraints=constraints,
                target_lang=target_lang,
                provider=provider
            )
            
            # Re-wrap after condensation
            if segment.translated_text and needs_wrapping(
                segment.translated_text,
                constraints.max_chars_per_line,
                constraints.max_lines
            ):
                segment.translated_text = wrap_lines(
                    segment.translated_text,
                    max_chars_per_line=constraints.max_chars_per_line,
                    max_lines=constraints.max_lines,
                    target_lang=target_lang
                )
    
    return segments
