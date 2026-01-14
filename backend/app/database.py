"""SQLite database setup and management."""

import sqlite3
import json
from pathlib import Path
from typing import Optional, List, Dict, Any
from datetime import datetime
from contextlib import contextmanager


# Database path
DB_PATH = Path(__file__).parent.parent / "data" / "translateme.db"


def init_db() -> sqlite3.Connection:
    """
    Initialize the database and create tables if they don't exist.
    
    Returns:
        Database connection
    """
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row  # Enable dict-like access to rows
    
    # Create jobs table
    conn.execute("""
        CREATE TABLE IF NOT EXISTS jobs (
            job_id TEXT PRIMARY KEY,
            status TEXT NOT NULL,
            review_status TEXT DEFAULT 'auto',
            reviewer_notes TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            reviewed_at TIMESTAMP,
            completed_at TIMESTAMP,
            source_filename TEXT,
            source_lang TEXT,
            target_lang TEXT,
            data JSON
        )
    """)
    
    # Create translation_memory table (for Phase 4)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS translation_memory (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            source_text TEXT NOT NULL,
            source_lang TEXT NOT NULL,
            target_text TEXT NOT NULL,
            target_lang TEXT NOT NULL,
            context TEXT,
            approved BOOLEAN DEFAULT FALSE,
            job_id TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(source_text, source_lang, target_lang)
        )
    """)
    
    # Create index for fast TM lookups
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_tm_lookup 
        ON translation_memory(source_text, source_lang, target_lang)
    """)
    
    # Create index for pending reviews
    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_jobs_review_status 
        ON jobs(review_status)
    """)
    
    conn.commit()
    return conn


@contextmanager
def get_db():
    """Context manager for database connections."""
    conn = sqlite3.connect(str(DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
    finally:
        conn.close()


class JobRepository:
    """Repository for job persistence operations."""
    
    def __init__(self, conn: Optional[sqlite3.Connection] = None):
        self.conn = conn or init_db()
    
    def save_job(
        self,
        job_id: str,
        status: str,
        review_status: str = "auto",
        source_filename: str = "",
        source_lang: str = "",
        target_lang: str = "",
        data: Optional[Dict] = None
    ) -> None:
        """Save or update a job in the database."""
        self.conn.execute("""
            INSERT OR REPLACE INTO jobs 
            (job_id, status, review_status, source_filename, source_lang, target_lang, data)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, (
            job_id,
            status,
            review_status,
            source_filename,
            source_lang,
            target_lang,
            json.dumps(data) if data else None
        ))
        self.conn.commit()
    
    def get_job(self, job_id: str) -> Optional[Dict]:
        """Get a job by ID."""
        cursor = self.conn.execute(
            "SELECT * FROM jobs WHERE job_id = ?",
            (job_id,)
        )
        row = cursor.fetchone()
        if row:
            result = dict(row)
            if result.get('data'):
                result['data'] = json.loads(result['data'])
            return result
        return None
    
    def update_review_status(
        self,
        job_id: str,
        review_status: str,
        reviewer_notes: str = ""
    ) -> bool:
        """Update the review status of a job."""
        cursor = self.conn.execute("""
            UPDATE jobs 
            SET review_status = ?, reviewer_notes = ?, reviewed_at = ?
            WHERE job_id = ?
        """, (review_status, reviewer_notes, datetime.utcnow().isoformat(), job_id))
        self.conn.commit()
        return cursor.rowcount > 0
    
    def get_pending_reviews(self) -> List[Dict]:
        """Get all jobs pending human review."""
        cursor = self.conn.execute("""
            SELECT * FROM jobs 
            WHERE review_status = 'pending_review'
            ORDER BY created_at DESC
        """)
        return [dict(row) for row in cursor.fetchall()]
    
    def get_jobs_by_status(self, status: str) -> List[Dict]:
        """Get all jobs with a specific status."""
        cursor = self.conn.execute(
            "SELECT * FROM jobs WHERE status = ? ORDER BY created_at DESC",
            (status,)
        )
        return [dict(row) for row in cursor.fetchall()]
    
    def mark_completed(self, job_id: str) -> None:
        """Mark a job as completed."""
        self.conn.execute("""
            UPDATE jobs SET completed_at = ? WHERE job_id = ?
        """, (datetime.utcnow().isoformat(), job_id))
        self.conn.commit()


# Global repository instance (initialized lazily)
_repository: Optional[JobRepository] = None


def get_repository() -> JobRepository:
    """Get or create the global repository instance."""
    global _repository
    if _repository is None:
        _repository = JobRepository()
    return _repository
