"""Translation Memory module for caching and reusing translations."""

import sqlite3
from pathlib import Path
from typing import Optional, List, Dict, Tuple
from dataclasses import dataclass
from datetime import datetime

from .database import DB_PATH, init_db


@dataclass
class TMEntry:
    """A single translation memory entry."""
    id: int
    source_text: str
    source_lang: str
    target_text: str
    target_lang: str
    context: Optional[str]
    approved: bool
    job_id: Optional[str]
    created_at: str


class TranslationMemory:
    """
    Translation Memory for caching and reusing approved translations.
    
    Features:
    - Lookup translations by exact source text match
    - Store new translations (unapproved by default)
    - Approve translations when jobs are reviewed
    - Track which job created each translation
    """
    
    def __init__(self, db_path: Optional[Path] = None):
        """
        Initialize Translation Memory.
        
        Args:
            db_path: Path to SQLite database (defaults to standard location)
        """
        self.db_path = db_path or DB_PATH
        self._ensure_db()
    
    def _ensure_db(self) -> None:
        """Ensure database and tables exist."""
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        init_db()
    
    def _get_conn(self) -> sqlite3.Connection:
        """Get a database connection."""
        conn = sqlite3.connect(str(self.db_path), check_same_thread=False)
        conn.row_factory = sqlite3.Row
        return conn
    
    def lookup(
        self,
        source_text: str,
        source_lang: str,
        target_lang: str,
        approved_only: bool = True
    ) -> Optional[str]:
        """
        Look up a translation in the memory.
        
        Args:
            source_text: The source text to translate
            source_lang: Source language code
            target_lang: Target language code
            approved_only: If True, only return approved translations
            
        Returns:
            The cached translation if found, None otherwise
        """
        conn = self._get_conn()
        try:
            if approved_only:
                cursor = conn.execute(
                    """SELECT target_text FROM translation_memory 
                       WHERE source_text = ? AND source_lang = ? AND target_lang = ? AND approved = 1
                       ORDER BY created_at DESC LIMIT 1""",
                    (source_text, source_lang, target_lang)
                )
            else:
                cursor = conn.execute(
                    """SELECT target_text FROM translation_memory 
                       WHERE source_text = ? AND source_lang = ? AND target_lang = ?
                       ORDER BY approved DESC, created_at DESC LIMIT 1""",
                    (source_text, source_lang, target_lang)
                )
            
            row = cursor.fetchone()
            return row["target_text"] if row else None
        finally:
            conn.close()
    
    def lookup_batch(
        self,
        texts: List[str],
        source_lang: str,
        target_lang: str,
        approved_only: bool = True
    ) -> Dict[str, str]:
        """
        Look up multiple translations at once.
        
        Args:
            texts: List of source texts to look up
            source_lang: Source language code
            target_lang: Target language code
            approved_only: If True, only return approved translations
            
        Returns:
            Dictionary mapping source text to target text for found translations
        """
        if not texts:
            return {}
        
        conn = self._get_conn()
        try:
            placeholders = ",".join("?" * len(texts))
            
            if approved_only:
                query = f"""
                    SELECT source_text, target_text FROM translation_memory 
                    WHERE source_text IN ({placeholders}) 
                    AND source_lang = ? AND target_lang = ? AND approved = 1
                """
            else:
                query = f"""
                    SELECT source_text, target_text FROM translation_memory 
                    WHERE source_text IN ({placeholders}) 
                    AND source_lang = ? AND target_lang = ?
                """
            
            params = list(texts) + [source_lang, target_lang]
            cursor = conn.execute(query, params)
            
            return {row["source_text"]: row["target_text"] for row in cursor.fetchall()}
        finally:
            conn.close()
    
    def store(
        self,
        source_text: str,
        source_lang: str,
        target_text: str,
        target_lang: str,
        context: Optional[str] = None,
        job_id: Optional[str] = None,
        approved: bool = False
    ) -> None:
        """
        Store a translation in the memory.
        
        Args:
            source_text: Original text
            source_lang: Source language code
            target_text: Translated text
            target_lang: Target language code
            context: Optional context (e.g., show name, episode)
            job_id: Optional job ID that created this translation
            approved: Whether this translation is approved
        """
        conn = self._get_conn()
        try:
            conn.execute(
                """INSERT OR REPLACE INTO translation_memory 
                   (source_text, source_lang, target_text, target_lang, context, job_id, approved, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (source_text, source_lang, target_text, target_lang, 
                 context, job_id, approved, datetime.utcnow().isoformat())
            )
            conn.commit()
        finally:
            conn.close()
    
    def store_batch(
        self,
        translations: List[Tuple[str, str]],  # [(source, target), ...]
        source_lang: str,
        target_lang: str,
        job_id: Optional[str] = None,
        approved: bool = False
    ) -> int:
        """
        Store multiple translations at once.
        
        Args:
            translations: List of (source_text, target_text) tuples
            source_lang: Source language code
            target_lang: Target language code
            job_id: Optional job ID
            approved: Whether these translations are approved
            
        Returns:
            Number of translations stored
        """
        if not translations:
            return 0
        
        conn = self._get_conn()
        try:
            created_at = datetime.utcnow().isoformat()
            data = [
                (src, source_lang, tgt, target_lang, None, job_id, approved, created_at)
                for src, tgt in translations
            ]
            
            conn.executemany(
                """INSERT OR REPLACE INTO translation_memory 
                   (source_text, source_lang, target_text, target_lang, context, job_id, approved, created_at)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                data
            )
            conn.commit()
            return len(translations)
        finally:
            conn.close()
    
    def approve_job_translations(self, job_id: str) -> int:
        """
        Mark all translations from a job as approved.
        
        Called when a human reviewer approves a job.
        
        Args:
            job_id: The job ID whose translations to approve
            
        Returns:
            Number of translations approved
        """
        conn = self._get_conn()
        try:
            cursor = conn.execute(
                "UPDATE translation_memory SET approved = 1 WHERE job_id = ?",
                (job_id,)
            )
            conn.commit()
            return cursor.rowcount
        finally:
            conn.close()
    
    def reject_job_translations(self, job_id: str) -> int:
        """
        Delete all translations from a rejected job.
        
        Called when a human reviewer rejects a job.
        
        Args:
            job_id: The job ID whose translations to delete
            
        Returns:
            Number of translations deleted
        """
        conn = self._get_conn()
        try:
            cursor = conn.execute(
                "DELETE FROM translation_memory WHERE job_id = ? AND approved = 0",
                (job_id,)
            )
            conn.commit()
            return cursor.rowcount
        finally:
            conn.close()
    
    def get_stats(self) -> Dict[str, int]:
        """
        Get statistics about the translation memory.
        
        Returns:
            Dictionary with counts of total, approved, and unapproved translations
        """
        conn = self._get_conn()
        try:
            cursor = conn.execute("""
                SELECT 
                    COUNT(*) as total,
                    SUM(CASE WHEN approved = 1 THEN 1 ELSE 0 END) as approved,
                    SUM(CASE WHEN approved = 0 THEN 1 ELSE 0 END) as unapproved
                FROM translation_memory
            """)
            row = cursor.fetchone()
            return {
                "total": row["total"] or 0,
                "approved": row["approved"] or 0,
                "unapproved": row["unapproved"] or 0
            }
        finally:
            conn.close()
    
    def get_language_pairs(self) -> List[Dict[str, str]]:
        """
        Get all language pairs in the translation memory.
        
        Returns:
            List of dictionaries with source_lang and target_lang
        """
        conn = self._get_conn()
        try:
            cursor = conn.execute("""
                SELECT DISTINCT source_lang, target_lang, COUNT(*) as count
                FROM translation_memory
                GROUP BY source_lang, target_lang
            """)
            return [
                {"source_lang": row["source_lang"], "target_lang": row["target_lang"], "count": row["count"]}
                for row in cursor.fetchall()
            ]
        finally:
            conn.close()


# Global instance (lazy initialization)
_tm_instance: Optional[TranslationMemory] = None


def get_translation_memory() -> TranslationMemory:
    """Get or create the global TranslationMemory instance."""
    global _tm_instance
    if _tm_instance is None:
        _tm_instance = TranslationMemory()
    return _tm_instance
