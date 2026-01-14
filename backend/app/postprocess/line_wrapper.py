"""Line wrapping and text formatting for subtitles."""

import re
from typing import List, Tuple


# Preferred break points (in order of preference)
BREAK_PUNCTUATION = ['. ', '? ', '! ', ', ', ': ', '; ', ' - ', '– ', '— ']

# RTL languages that need special handling
RTL_LANGUAGES = {'he', 'ar', 'fa', 'ur', 'yi'}


def find_best_break_point(text: str, max_length: int) -> int:
    """
    Find the best position to break a line.
    
    Prefers breaking at punctuation, then at word boundaries.
    
    Args:
        text: Text to find break point in
        max_length: Maximum allowed length for the first part
        
    Returns:
        Index at which to break (break happens before this index)
    """
    if len(text) <= max_length:
        return len(text)
    
    # Look for punctuation breaks within the allowed range
    best_break = -1
    
    for punct in BREAK_PUNCTUATION:
        # Find the last occurrence of this punctuation within range
        search_text = text[:max_length + len(punct)]
        idx = search_text.rfind(punct)
        if idx > 0 and idx + len(punct) <= max_length + len(punct):
            # Break after the punctuation
            break_point = idx + len(punct)
            if break_point <= max_length + 1 and break_point > best_break:
                best_break = break_point
    
    if best_break > 0:
        return best_break
    
    # No punctuation found, look for word boundary (space)
    search_text = text[:max_length + 1]
    last_space = search_text.rfind(' ')
    
    if last_space > 0:
        return last_space + 1  # Break after the space
    
    # No good break point, force break at max_length
    return max_length


def balance_lines(lines: List[str], max_chars: int) -> List[str]:
    """
    Try to balance line lengths for better visual appearance.
    
    Args:
        lines: List of lines to balance
        max_chars: Maximum characters per line
        
    Returns:
        Balanced lines
    """
    if len(lines) != 2:
        return lines
    
    # Combine and try to split more evenly
    combined = ' '.join(lines)
    target_length = len(combined) // 2
    
    # Don't rebalance if it would exceed max
    if target_length > max_chars:
        return lines
    
    # Find a good break point near the middle
    best_break = -1
    best_diff = float('inf')
    
    # Search for break points near the target
    for i in range(max(0, target_length - 15), min(len(combined), target_length + 15)):
        if i < len(combined) and combined[i] == ' ':
            diff = abs(i - target_length)
            if diff < best_diff:
                # Check if both parts would fit
                first_part = combined[:i].strip()
                second_part = combined[i:].strip()
                if len(first_part) <= max_chars and len(second_part) <= max_chars:
                    best_break = i
                    best_diff = diff
    
    if best_break > 0:
        return [combined[:best_break].strip(), combined[best_break:].strip()]
    
    return lines


def wrap_lines(
    text: str,
    max_chars_per_line: int = 42,
    max_lines: int = 2,
    target_lang: str = "en",
    balance: bool = True
) -> str:
    """
    Wrap subtitle text to fit within constraints.
    
    Args:
        text: Text to wrap
        max_chars_per_line: Maximum characters per line
        max_lines: Maximum number of lines
        target_lang: Target language code (for RTL handling)
        balance: Whether to try to balance line lengths
        
    Returns:
        Wrapped text with newlines
    """
    if not text:
        return text
    
    # Remove existing line breaks and normalize whitespace
    text = ' '.join(text.split())
    
    # If text already fits on one line, return as-is
    if len(text) <= max_chars_per_line:
        return text
    
    lines: List[str] = []
    remaining = text
    
    while remaining and len(lines) < max_lines:
        if len(remaining) <= max_chars_per_line:
            lines.append(remaining.strip())
            remaining = ""
        else:
            break_point = find_best_break_point(remaining, max_chars_per_line)
            line = remaining[:break_point].strip()
            remaining = remaining[break_point:].strip()
            lines.append(line)
    
    # If there's still remaining text, append to last line
    if remaining and lines:
        lines[-1] = lines[-1] + ' ' + remaining
    elif remaining:
        lines.append(remaining)
    
    # Try to balance lines if we have exactly 2
    if balance and len(lines) == 2:
        lines = balance_lines(lines, max_chars_per_line)
    
    # For RTL languages, we might want to add RTL markers
    # (leaving this as a placeholder - proper RTL handling depends on rendering context)
    
    return '\n'.join(lines)


def estimate_wrapped_length(text: str) -> Tuple[int, int]:
    """
    Estimate the number of lines and max line length after wrapping.
    
    Args:
        text: Text to analyze
        
    Returns:
        Tuple of (line_count, max_line_length)
    """
    if not text:
        return (0, 0)
    
    lines = text.split('\n')
    return (len(lines), max(len(line) for line in lines))


def needs_wrapping(
    text: str,
    max_chars_per_line: int = 42,
    max_lines: int = 2
) -> bool:
    """
    Check if text needs to be wrapped.
    
    Args:
        text: Text to check
        max_chars_per_line: Maximum characters per line
        max_lines: Maximum number of lines
        
    Returns:
        True if wrapping is needed
    """
    if not text:
        return False
    
    lines = text.split('\n')
    
    # Too many lines
    if len(lines) > max_lines:
        return True
    
    # Any line too long
    for line in lines:
        if len(line) > max_chars_per_line:
            return True
    
    return False
