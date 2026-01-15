"""OpenAI-based translation provider."""

import os
import re
from typing import List, Dict, Optional

from openai import AsyncOpenAI

from .provider import TranslationProvider
from .prompts import format_translation_prompt, format_condensation_prompt
from ..models import SubtitleSegment, JobConstraints
from ..translation_memory import get_translation_memory


class OpenAIProvider(TranslationProvider):
    """
    Translation provider using OpenAI's GPT models.
    
    Requires OPENAI_API_KEY environment variable.
    """
    
    def __init__(
        self,
        api_key: Optional[str] = None,
        model: Optional[str] = None
    ):
        """
        Initialize the OpenAI provider.
        
        Args:
            api_key: OpenAI API key (defaults to OPENAI_API_KEY env var)
            model: Model to use (defaults to OPENAI_MODEL env var or gpt-4o)
        """
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.model = model or os.getenv("OPENAI_MODEL", "gpt-4o")
        
        if not self.api_key:
            raise ValueError(
                "OpenAI API key not provided. Set OPENAI_API_KEY environment variable "
                "or pass api_key parameter."
            )
        
        self.client = AsyncOpenAI(api_key=self.api_key)
    
    async def translate_batch(
        self,
        segments: List[SubtitleSegment],
        context_window: List[SubtitleSegment],
        source_lang: str,
        target_lang: str,
        glossary: Dict[str, str],
        constraints: JobConstraints,
        job_id: Optional[str] = None,
        use_tm: bool = True
    ) -> List[SubtitleSegment]:
        """
        Translate a batch of segments using OpenAI.
        
        Checks Translation Memory first and only translates segments not found in TM.
        New translations are stored in TM for future reuse.
        """
        if not segments:
            return segments
        
        segments_to_translate = []
        tm = get_translation_memory() if use_tm else None
        
        # Step 1: Check Translation Memory for cached translations
        if tm:
            source_texts = [seg.text for seg in segments]
            cached = tm.lookup_batch(source_texts, source_lang, target_lang)
            
            for segment in segments:
                if segment.text in cached:
                    # Use cached translation
                    segment.translated_text = cached[segment.text]
                    if "FROM_TM" not in segment.qc_flags:
                        segment.qc_flags.append("FROM_TM")
                else:
                    segments_to_translate.append(segment)
            
            if cached:
                print(f"[TM] Found {len(cached)} cached translations, translating {len(segments_to_translate)} new")
        else:
            segments_to_translate = segments
        
        # Step 2: Translate segments not found in TM
        if segments_to_translate:
            # Format the prompt
            system_prompt, user_prompt = format_translation_prompt(
                segments_to_translate=segments_to_translate,
                context_segments=context_window,
                source_lang=source_lang,
                target_lang=target_lang,
                glossary=glossary,
                max_chars_per_line=constraints.max_chars_per_line,
                max_lines=constraints.max_lines,
                max_cps=constraints.max_cps
            )
            
            # Call OpenAI
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.3,  # Lower temperature for more consistent translations
                max_tokens=2000
            )
            
            # Parse the response
            response_text = response.choices[0].message.content or ""
            translations = self._parse_translations(response_text, segments_to_translate)
            
            # Apply translations to segments
            new_translations = []
            for segment in segments_to_translate:
                if segment.index in translations:
                    segment.translated_text = translations[segment.index]
                    new_translations.append((segment.text, segment.translated_text))
                else:
                    # Fallback: keep original if translation not found
                    segment.translated_text = segment.text
            
            # Step 3: Store new translations in TM (unapproved until human review)
            if tm and new_translations:
                tm.store_batch(
                    translations=new_translations,
                    source_lang=source_lang,
                    target_lang=target_lang,
                    job_id=job_id,
                    approved=False  # Will be approved when job is reviewed
                )
                print(f"[TM] Stored {len(new_translations)} new translations")
        
        return segments
    
    def _parse_translations(
        self,
        response_text: str,
        segments: List[SubtitleSegment]
    ) -> Dict[int, str]:
        """
        Parse the translation response to extract individual translations.
        
        Expected format:
        1: translated text
        2: translated text
        ...
        """
        translations: Dict[int, str] = {}
        
        # Pattern to match numbered translations
        # Handles formats like "1: text", "1. text", "1) text"
        pattern = r"^(\d+)[:\.\)]\s*(.+?)(?=\n\d+[:\.\)]|\Z)"
        
        matches = re.findall(pattern, response_text, re.MULTILINE | re.DOTALL)
        
        for match in matches:
            try:
                index = int(match[0])
                text = match[1].strip()
                translations[index] = text
            except (ValueError, IndexError):
                continue
        
        # If pattern matching fails, try line-by-line matching
        if not translations:
            lines = response_text.strip().split('\n')
            segment_indices = [s.index for s in segments]
            
            for i, line in enumerate(lines):
                line = line.strip()
                if not line:
                    continue
                
                # Try to extract number prefix
                number_match = re.match(r'^(\d+)[:\.\)]?\s*(.*)$', line)
                if number_match:
                    index = int(number_match.group(1))
                    text = number_match.group(2).strip()
                    if text:
                        translations[index] = text
                elif i < len(segment_indices):
                    # Assume lines are in order
                    translations[segment_indices[i]] = line
        
        return translations
    
    async def condense_text(
        self,
        text: str,
        target_chars: int,
        target_lang: str
    ) -> str:
        """
        Condense text to fit within character limit.
        """
        if len(text) <= target_chars:
            return text
        
        system_prompt, user_prompt = format_condensation_prompt(text, target_chars)
        
        # Try up to 3 times to get text under limit
        for attempt in range(3):
            response = await self.client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                temperature=0.5 + (attempt * 0.1),  # Increase creativity each attempt
                max_tokens=500
            )
            
            condensed = response.choices[0].message.content or ""
            condensed = condensed.strip().strip('"\'')
            
            if len(condensed) <= target_chars:
                return condensed
            
            # Update prompt for next attempt with the condensed version
            user_prompt = format_condensation_prompt(condensed, target_chars)[1]
        
        # Last resort: truncate
        return text[:target_chars - 3] + "..."
    
    def get_provider_name(self) -> str:
        return f"OpenAIProvider ({self.model})"
