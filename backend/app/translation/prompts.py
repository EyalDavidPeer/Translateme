"""LLM prompt templates for subtitle translation and condensation."""

# Map language codes to full names for clearer prompts
LANGUAGE_NAMES = {
    "en": "English",
    "he": "Hebrew",
    "es": "Spanish", 
    "fr": "French",
    "de": "German",
    "it": "Italian",
    "pt": "Portuguese",
    "ru": "Russian",
    "zh": "Chinese",
    "ja": "Japanese",
    "ko": "Korean",
    "ar": "Arabic",
    "hi": "Hindi",
    "tr": "Turkish",
    "pl": "Polish",
    "nl": "Dutch",
    "sv": "Swedish",
    "da": "Danish",
    "no": "Norwegian",
    "fi": "Finnish",
}

def get_language_name(code: str) -> str:
    """Convert language code to full name."""
    return LANGUAGE_NAMES.get(code.lower(), code)

TRANSLATION_SYSTEM_PROMPT = """You are a professional subtitle translator. Your ONLY job is to translate subtitles from one language to another.

CRITICAL RULES:
1. You MUST translate ALL text to the target language - do NOT leave anything in the source language
2. You MUST output the translation in the target language's script (e.g., Hebrew uses Hebrew alphabet, not Latin)
3. Preserve the meaning, tone, and style of the original
4. Keep translations concise for subtitle readability
5. Adapt idioms and expressions naturally to the target language

Technical limits:
- Max {max_chars_per_line} characters per line
- Max {max_lines} lines per subtitle

Output format: Return ONLY numbered translations. Nothing else.
Example output:
1: [translated text in target language]
2: [translated text in target language]
"""

# Special prompt for languages with grammatical gender (Hebrew, Spanish, etc.)
TRANSLATION_WITH_GENDER_SYSTEM_PROMPT = """You are a professional subtitle translator specializing in {target_lang}. Your job is to translate subtitles while handling grammatical gender correctly.

CRITICAL RULES:
1. You MUST translate ALL text to {target_lang} - do NOT leave anything in the source language
2. You MUST output the translation in the target language's script
3. Preserve the meaning, tone, and style of the original
4. Keep translations concise for subtitle readability

GENDER HANDLING (IMPORTANT):
When the speaker's gender is AMBIGUOUS (cannot be determined from context):
- Mark the line with [GENDER_AMBIGUOUS]
- Provide BOTH masculine (M) and feminine (F) versions
- Estimate confidence (0.0-1.0) that the default is correct

When gender IS clear from context (names, pronouns, previous dialogue):
- Use the correct gendered form
- Mark with [GENDER_CLEAR]

Technical limits:
- Max {max_chars_per_line} characters per line
- Max {max_lines} lines per subtitle

Output format:
For clear gender:
1: [GENDER_CLEAR] [translated text]

For ambiguous gender:
2: [GENDER_AMBIGUOUS:0.5] M:[masculine version] F:[feminine version]

The number after GENDER_AMBIGUOUS is your confidence (0.5 = completely uncertain, 0.8 = fairly confident in default).
"""

TRANSLATION_WITH_GENDER_USER_PROMPT = """TASK: Translate these subtitles from {source_lang} to {target_lang}.

CRITICAL: 
- Output MUST be in {target_lang} language and script
- For lines where speaker gender is UNKNOWN, provide both M: and F: versions
- Use context (names, previous lines) to determine gender when possible
{glossary_section}
{context_section}

Source subtitles to translate:
{subtitles}

Now provide the {target_lang} translations with gender markers:"""

TRANSLATION_USER_PROMPT = """TASK: Translate these subtitles from {source_lang} to {target_lang}.

CRITICAL: 
- Output MUST be in {target_lang} language and script
- Do NOT output English if target is not English
- Translate EVERY subtitle
{glossary_section}
{context_section}

Source subtitles to translate:
{subtitles}

Now provide the {target_lang} translations (numbered, one per line):"""

GLOSSARY_SECTION_TEMPLATE = """Glossary (use these exact translations for these terms):
{glossary_items}
"""

CONTEXT_SECTION_TEMPLATE = """Context (previous subtitles for reference):
{context_items}
"""

CONDENSATION_SYSTEM_PROMPT = """You are a subtitle editor. Your task is to shorten subtitle text while preserving its core meaning.

Rules:
1. Keep the essential message intact
2. Remove filler words and redundant phrases
3. Use shorter synonyms where possible
4. Maintain natural language flow
5. Preserve any names or key terms
6. The shortened version must be under {target_chars} characters

Output ONLY the shortened text, nothing else."""

CONDENSATION_USER_PROMPT = """Shorten this subtitle text to under {target_chars} characters while preserving its meaning.

Original ({current_chars} characters):
"{text}"

Shortened version (must be under {target_chars} characters):"""


def format_translation_prompt(
    segments_to_translate: list,
    context_segments: list,
    source_lang: str,
    target_lang: str,
    glossary: dict,
    max_chars_per_line: int,
    max_lines: int,
    max_cps: float
) -> tuple:
    """
    Format the translation prompt.
    
    Args:
        segments_to_translate: List of SubtitleSegment to translate
        context_segments: Previous segments for context
        source_lang: Source language code
        target_lang: Target language code  
        glossary: Term glossary dictionary
        max_chars_per_line: Maximum characters per line
        max_lines: Maximum lines per cue
        max_cps: Maximum characters per second
        
    Returns:
        Tuple of (system_prompt, user_prompt)
    """
    # Convert language codes to full names
    source_name = get_language_name(source_lang)
    target_name = get_language_name(target_lang)
    
    # Format system prompt
    system_prompt = TRANSLATION_SYSTEM_PROMPT.format(
        max_chars_per_line=max_chars_per_line,
        max_lines=max_lines,
        max_cps=max_cps
    )
    
    # Format glossary section
    glossary_section = ""
    if glossary:
        glossary_items = "\n".join(
            f"  {src} → {tgt}" for src, tgt in glossary.items()
        )
        glossary_section = GLOSSARY_SECTION_TEMPLATE.format(
            glossary_items=glossary_items
        )
    
    # Format context section
    context_section = ""
    if context_segments:
        context_items = "\n".join(
            f"  [{s.index}] {s.translated_text or s.text}"
            for s in context_segments[-10:]  # Last 10 for context
        )
        context_section = CONTEXT_SECTION_TEMPLATE.format(
            context_items=context_items
        )
    
    # Format subtitles to translate
    subtitles = "\n".join(
        f"{s.index}: {s.text}" for s in segments_to_translate
    )
    
    # Format user prompt with full language names
    user_prompt = TRANSLATION_USER_PROMPT.format(
        source_lang=source_name,
        target_lang=target_name,
        glossary_section=glossary_section,
        context_section=context_section,
        subtitles=subtitles
    )
    
    return system_prompt, user_prompt


# Languages that have grammatical gender affecting verbs/adjectives
GENDERED_LANGUAGES = {"he", "ar", "es", "fr", "it", "pt", "de", "ru", "pl", "hi"}


def is_gendered_language(lang_code: str) -> bool:
    """Check if a language has grammatical gender that affects translation."""
    return lang_code.lower() in GENDERED_LANGUAGES


def format_gender_aware_translation_prompt(
    segments_to_translate: list,
    context_segments: list,
    source_lang: str,
    target_lang: str,
    glossary: dict,
    max_chars_per_line: int,
    max_lines: int,
    max_cps: float
) -> tuple:
    """
    Format translation prompt with gender awareness for gendered languages.
    
    Args:
        segments_to_translate: List of SubtitleSegment to translate
        context_segments: Previous segments for context
        source_lang: Source language code
        target_lang: Target language code  
        glossary: Term glossary dictionary
        max_chars_per_line: Maximum characters per line
        max_lines: Maximum lines per cue
        max_cps: Maximum characters per second
        
    Returns:
        Tuple of (system_prompt, user_prompt)
    """
    source_name = get_language_name(source_lang)
    target_name = get_language_name(target_lang)
    
    # Use gender-aware prompt for gendered languages
    system_prompt = TRANSLATION_WITH_GENDER_SYSTEM_PROMPT.format(
        target_lang=target_name,
        max_chars_per_line=max_chars_per_line,
        max_lines=max_lines,
        max_cps=max_cps
    )
    
    # Format glossary section
    glossary_section = ""
    if glossary:
        glossary_items = "\n".join(
            f"  {src} → {tgt}" for src, tgt in glossary.items()
        )
        glossary_section = GLOSSARY_SECTION_TEMPLATE.format(
            glossary_items=glossary_items
        )
    
    # Format context section with gender info
    context_section = ""
    if context_segments:
        context_items = []
        for s in context_segments[-10:]:
            text = s.translated_text or s.text
            gender_info = ""
            if hasattr(s, 'active_gender') and s.active_gender.value != "unknown":
                gender_info = f" ({s.active_gender.value})"
            context_items.append(f"  [{s.index}] {text}{gender_info}")
        context_section = CONTEXT_SECTION_TEMPLATE.format(
            context_items="\n".join(context_items)
        )
    
    # Format subtitles to translate
    subtitles = "\n".join(
        f"{s.index}: {s.text}" for s in segments_to_translate
    )
    
    user_prompt = TRANSLATION_WITH_GENDER_USER_PROMPT.format(
        source_lang=source_name,
        target_lang=target_name,
        glossary_section=glossary_section,
        context_section=context_section,
        subtitles=subtitles
    )
    
    return system_prompt, user_prompt


def format_condensation_prompt(
    text: str,
    target_chars: int
) -> tuple:
    """
    Format the condensation prompt.
    
    Args:
        text: Text to condense
        target_chars: Target character limit
        
    Returns:
        Tuple of (system_prompt, user_prompt)
    """
    system_prompt = CONDENSATION_SYSTEM_PROMPT.format(
        target_chars=target_chars
    )
    
    user_prompt = CONDENSATION_USER_PROMPT.format(
        target_chars=target_chars,
        current_chars=len(text),
        text=text
    )
    
    return system_prompt, user_prompt
