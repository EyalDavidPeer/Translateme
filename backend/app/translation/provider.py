"""Abstract base class for translation providers."""

from abc import ABC, abstractmethod
from typing import List, Dict, Optional

from ..models import SubtitleSegment, JobConstraints


class TranslationProvider(ABC):
    """
    Abstract base class for translation providers.
    
    Implementations should handle batched translation of subtitle segments
    with context awareness and glossary support.
    """
    
    @abstractmethod
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
        Translate a batch of subtitle segments.
        
        Args:
            segments: The segments to translate (will be modified in place)
            context_window: Previous segments for context (already translated)
            source_lang: Source language code (e.g., "en")
            target_lang: Target language code (e.g., "he")
            glossary: Dictionary mapping source terms to target translations
            constraints: Subtitle constraints to consider during translation
            
        Returns:
            The segments with translated_text field populated
        """
        pass
    
    @abstractmethod
    async def condense_text(
        self,
        text: str,
        target_chars: int,
        target_lang: str
    ) -> str:
        """
        Condense text to fit within a character limit while preserving meaning.
        
        Args:
            text: Text to condense
            target_chars: Target maximum character count
            target_lang: Target language code
            
        Returns:
            Condensed text
        """
        pass
    
    def get_provider_name(self) -> str:
        """Return the name of this provider."""
        return self.__class__.__name__
