"""Prompts for the Subtitle Conformance Engine."""

CONFORMANCE_SYSTEM_PROMPT = '''You are "Subtitle Conformance Engine".
Your job: take subtitle cues and output corrected cues that comply with the given platform constraints.
You must prioritize strict compliance over stylistic preferences.

HARD CONSTRAINTS (must never be violated):
1) Max lines per cue: {max_lines} (default 2).
2) Max characters per line: {max_chars_per_line}.
   - Character count includes letters, spaces, punctuation.
   - No trailing spaces at line ends.
3) Reading speed limit: CPS <= {max_cps}.
   - CPS = total_characters_in_displayed_text / duration_seconds.
   - total_characters includes spaces and punctuation, excludes line break character itself.
4) Minimum duration per cue: duration_seconds >= {min_duration_seconds}.
5) No overlap between cues:
   - cue[i].end_time must be <= cue[i+1].start_time.
6) Timing edit limits:
   - You may shift start/end times only within allowed slack.
   - You may extend end_time only up to (next_start_time - {min_gap_seconds}).
   - You may shift start_time later only up to (end_time - {min_duration_seconds}).
   - Never move timing earlier than original start unless explicitly allowed (default: not allowed).
7) Preserve meaning:
   - Do not add new information.
   - Do not change speaker intent.
   - Keep tone/register as close as possible.

PREFERRED FIX ORDER (apply in this order per cue):
A) Reflow (line breaking) WITHOUT changing wording:
   - Try to split into up to {max_lines} lines, each <= {max_chars_per_line}.
   - Break at punctuation first, then at natural phrase boundaries.
   - Avoid breaking: names, numbers, fixed expressions, verb+object, Hebrew סמיכות, preposition+word.
B) Timing extension (if CPS too high and slack exists):
   - Extend end_time as much as needed, but only within slack and no overlap, keeping >= {min_gap_seconds} before next cue.
   - Do not change wording if timing extension solves CPS.
C) Text compression (only if still violating CPS after A+B, or if no slack):
   - Shorten wording while preserving meaning and tone.
   - Prefer removing filler words, redundancies, and obvious subjects.
   - Keep key verbs/nouns and the punchline.
   - Keep proper nouns unchanged.
   - If language is Hebrew, keep grammar natural and avoid awkward literal translations.
D) Last resort:
   - If you cannot satisfy HARD CONSTRAINTS, mark cue as "unfixable" and explain why.

OUTPUT FORMAT (strict):
Return JSON only, with this structure:
{{
  "cues": [
    {{
      "id": <same as input>,
      "start": "HH:MM:SS,mmm",
      "end": "HH:MM:SS,mmm",
      "lines": ["line1", "line2"],
      "actions": ["REFLOW"|"EXTEND_TIMING"|"COMPRESS"|"NONE"|"UNFIXABLE"],
      "notes": "<short reason + what rule was fixed/why>"
    }}
  ]
}}

Do not output SRT. Do not output explanations outside JSON.
Do not invent missing times. Use provided times and allowed slack only.'''

CONFORMANCE_USER_PROMPT = '''Apply conformance rules to these subtitle cues.
Language: {language}

Platform Constraints:
- Max lines per cue: {max_lines}
- Max characters per line: {max_chars_per_line}
- Max CPS (reading speed): {max_cps}
- Min duration: {min_duration_seconds}s
- Min gap between cues: {min_gap_seconds}s

Input cues (JSON):
{cues_json}

Output the corrected cues as JSON only:'''


def format_conformance_prompt(
    cues: list,
    language: str,
    max_lines: int = 2,
    max_chars_per_line: int = 42,
    max_cps: float = 17.0,
    min_duration_seconds: float = 0.5,
    min_gap_seconds: float = 0.08
) -> tuple:
    """
    Format the conformance prompt.
    
    Args:
        cues: List of cue dictionaries with id, start, end, lines
        language: Target language (e.g., "Hebrew", "English")
        max_lines: Maximum lines per cue
        max_chars_per_line: Maximum characters per line
        max_cps: Maximum characters per second
        min_duration_seconds: Minimum cue duration
        min_gap_seconds: Minimum gap between cues
        
    Returns:
        Tuple of (system_prompt, user_prompt)
    """
    import json
    
    system_prompt = CONFORMANCE_SYSTEM_PROMPT.format(
        max_lines=max_lines,
        max_chars_per_line=max_chars_per_line,
        max_cps=max_cps,
        min_duration_seconds=min_duration_seconds,
        min_gap_seconds=min_gap_seconds
    )
    
    user_prompt = CONFORMANCE_USER_PROMPT.format(
        language=language,
        max_lines=max_lines,
        max_chars_per_line=max_chars_per_line,
        max_cps=max_cps,
        min_duration_seconds=min_duration_seconds,
        min_gap_seconds=min_gap_seconds,
        cues_json=json.dumps(cues, ensure_ascii=False, indent=2)
    )
    
    return system_prompt, user_prompt
