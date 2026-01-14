"""Mock translation provider for testing and dry runs."""

from typing import List, Dict

from .provider import TranslationProvider
from ..models import SubtitleSegment, JobConstraints


class MockProvider(TranslationProvider):
    """
    Mock translation provider that returns the original text.
    
    Useful for testing the pipeline and for dry-run mode.
    """
    
    async def translate_batch(
        self,
        segments: List[SubtitleSegment],
        context_window: List[SubtitleSegment],
        source_lang: str,
        target_lang: str,
        glossary: Dict[str, str],
        constraints: JobConstraints
    ) -> List[SubtitleSegment]:
        """
        'Translate' by copying original text to translated_text.
        
        If target language is Hebrew, adds [HE] prefix to indicate mock translation.
        """
        for segment in segments:
            # For mock, just copy the text with a language indicator
            if target_lang == "he":
                segment.translated_text = f"[HE] {segment.text}"
            else:
                segment.translated_text = f"[{target_lang.upper()}] {segment.text}"
        
        return segments
    
    async def condense_text(
        self,
        text: str,
        target_chars: int,
        target_lang: str
    ) -> str:
        """
        Mock condensation - just truncates if necessary.
        """
        if len(text) <= target_chars:
            return text
        
        # Simple truncation with ellipsis
        return text[:target_chars - 3] + "..."
    
    def get_provider_name(self) -> str:
        return "MockProvider"
