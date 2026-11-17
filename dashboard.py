import aiosqlite
import json
from datetime import datetime, timedelta
from typing import List, Optional, Dict, Any
from pathlib import Path
from models import Job, JobStatus, JobType, ScrapeResult
from config import get_settings

settings = get_settings()

class Database:
    """Async database operations."""
    
    def __init__(self, db_path: str = None):
        self.db_path = db_path or settings.DB_PATH
        self._ensure_db_exists()
    
    def _ensure_db_exists(self):
        """Ensure database directory exists."""
        Path(self.db_path).parent.mkdir(parents=True, exist_ok=True)
    
    async def init(self):
        """Initialize database tables."""
        async with aiosqlite.connect(self.db_path) as conn:
            # Jobs table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS jobs (
                    id TEXT PRIMARY KEY,
                    title TEXT NOT NULL,
                    company TEXT NOT NULL,
                    location TEXT,
                    url TEXT UNIQUE,
                    source TEXT,
                    source_url TEXT,
                    posted_at DATETIME,
                    score INTEGER DEFAULT 0,
                    kimi_score INTEGER,
                    status TEXT DEFAULT 'new',
                    type TEXT DEFAULT 'job',
                    content TEXT,
                    salary_min INTEGER,
                    salary_max INTEGER,
                    salary_text TEXT,
                    dedup_hash TEXT UNIQUE,
                    enriched JSON,
                    remote_issue TEXT,
                    skills JSON,
                    notes TEXT,
                    saved BOOLEAN DEFAULT 0,
                    seen_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    created_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    updated_at DATETIME DEFAULT CURRENT_TIMESTAMP
                )
            """)
            
            # Applications table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS applications (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    job_id TEXT REFERENCES jobs(id),
                    cover_letter TEXT,
                    status TEXT DEFAULT 'submitted',
                    applied_at DATETIME DEFAULT CURRENT_TIMESTAMP,
                    notes TEXT,
                    follow_up_date DATETIME,
                    offer_details TEXT,
                    UNIQUE(job_id)
                )
            """)
            
            # Interviews table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS interviews (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    application_id INTEGER REFERENCES applications(id),
                    scheduled_at DATETIME,
                    notes TEXT,
                    status TEXT DEFAULT 'scheduled'
                )
            """)
            
            # Sources table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS sources (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    name TEXT,
                    url TEXT UNIQUE,
                    type TEXT,
                    active BOOLEAN DEFAULT 1,
                    discovered_at DATETIME,
                    last_checked DATETIME,
                    success_count INTEGER DEFAULT 0,
                    failure_count INTEGER DEFAULT 0,
                    quality_score INTEGER DEFAULT 0
                )
            """)
            
            # Analytics table
            await conn.execute("""
                CREATE TABLE IF NOT EXISTS analytics (
                    id INTEGER PRIMARY KEY AUTOINCREMENT,
                    date DATE UNIQUE,
                    jobs_found INTEGER DEFAULT 0,
                    jobs_applied INTEGER DEFAULT 0,
                    avg_score FLOAT DEFAULT 0,
                    sources_used INTEGER DEFAULT 0,
                    kimi_enriched BOOLEAN DEFAULT 0,
                    data JSON
                )
            """)
            
            await conn.commit()
    
    async def save_jobs(self, jobs: List[Job]) -> int:
        """Save jobs to database."""
        saved = 0
        async with aiosqlite.connect(self.db_path) as conn:
            for job in jobs:
                try:
                    # Check if exists
                    cursor = await conn.execute(
                        "SELECT id FROM jobs WHERE dedup_hash = ? OR url = ?",
                        (job.dedup_hash, job.url)
                    )
                    existing = await cursor.fetchone()
                    
                    if existing:
                        # Update existing
                        await conn.execute("""
                            UPDATE jobs SET
                                title = ?, company = ?, location = ?, url = ?,
                                source = ?, source_url = ?, posted_at = ?,
                                score = ?, kimi_score = ?, status = ?, type = ?,
                                content = ?, salary_min = ?, salary_max = ?,
                                salary_text = ?, enriched = ?, remote_issue = ?,
                                skills = ?, notes = ?, saved = ?, seen_at = ?,
                                updated_at = CURRENT_TIMESTAMP
                            WHERE dedup_hash = ? OR url = ?
                        """, (
                            job.title, job.company, job.location, job.url,
                            job.source, job.source_url, job.posted_at.isoformat(),
                            job.score, job.kimi_score, job.status.value,
                            job.type.value, job.content, job.salary_min,
                            job.salary_max, job.salary_text,
                            json.dumps(job.enriched.to_dict()) if job.enriched else None,
                            job.remote_issue, json.dumps(job.skills),
                            job.notes, job.saved, job.seen_at.isoformat(),
                            job.dedup_hash, job.url
                        ))
                    else:
                        # Insert new
                        await conn.execute("""
                            INSERT INTO jobs (
                                id, title, company, location, url, source,
                                source_url, posted_at, score, kimi_score,
                                status, type, content, salary_min, salary_max,
                                salary_text, dedup_hash, enriched, remote_issue,
                                skills, notes, saved, seen_at
                            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                        """, (
                            job.id, job.title, job.company, job.location, job.url,
                            job.source, job.source_url, job.posted_at.isoformat(),
                            job.score, job.kimi_score, job.status.value,
                            job.type.value, job.content, job.salary_min,
                            job.salary_max, job.salary_text, job.dedup_hash,
                            json.dumps(job.enriched.to_dict()) if job.enriched else None,
                            job.remote_issue, json.dumps(job.skills),
                            job.notes, job.saved, job.seen_at.isoformat()
                        ))
                    saved += 1
                except Exception as e:
                    print(f"[db] failed to save {getattr(job, 'url', '?')}: {e}")
            
            await conn.commit()
        return saved
    
    async def get_jobs(self, status: Optional[JobStatus] = None, 
                       min_score: int = 0, limit: int = 100) -> List[Job]:
        """Get jobs from database."""
        async with aiosqlite.connect(self.db_path) as conn:
            query = "SELECT * FROM jobs WHERE score >= ?"
            params = [min_score]
            
            if status:
                query += " AND status = ?"
                params.append(status.value)
            
            query += " ORDER BY score DESC LIMIT ?"
            params.append(limit)
            
            cursor = await conn.execute(query, params)
            rows = await cursor.fetchall()
            
            jobs = []
            for row in rows:
                job_dict = {
                    "id": row[0], "title": row[1], "company": row[2],
                    "location": row[3], "url": row[4], "source": row[5],
                    "source_url": row[6], "posted_at": row[7], "score": row[8],
                    "kimi_score": row[9], "status": row[10], "type": row[11],
                    "content": row[12], "salary_min": row[13], "salary_max": row[14],
                    "salary_text": row[15], "dedup_hash": row[16],
                    "enriched": json.loads(row[17]) if row[17] else None,
                    "remote_issue": row[18], "skills": json.loads(row[19]) if row[19] else [],
                    "notes": row[20], "saved": bool(row[21]) if row[21] is not None else False,
                    "seen_at": row[22]
                }
                jobs.append(Job.from_dict(job_dict))
            
            return jobs
    
    async def get_job_stats(self) -> Dict[str, Any]:
        """Get job statistics."""
        async with aiosqlite.connect(self.db_path) as conn:
            stats = {}
            
            # Total jobs
            cursor = await conn.execute("SELECT COUNT(*) FROM jobs")
            stats["total"] = (await cursor.fetchone())[0]
            
            # By status
            cursor = await conn.execute(
                "SELECT status, COUNT(*) FROM jobs GROUP BY status"
            )
            rows = await cursor.fetchall()
            stats["by_status"] = {r[0]: r[1] for r in rows}
            
            # Average score
            cursor = await conn.execute("SELECT AVG(score) FROM jobs")
            stats["avg_score"] = (await cursor.fetchone())[0] or 0
            
            # High score jobs
            cursor = await conn.execute(
                "SELECT COUNT(*) FROM jobs WHERE score >= 70"
            )
            stats["high_score"] = (await cursor.fetchone())[0]
            
            # Jobs by source
            cursor = await conn.execute(
                "SELECT source, COUNT(*) FROM jobs GROUP BY source ORDER BY COUNT(*) DESC LIMIT 10"
            )
            rows = await cursor.fetchall()
            stats["by_source"] = {r[0]: r[1] for r in rows}
            
            # Recent jobs (last 7 days)
            cutoff = (datetime.utcnow() - timedelta(days=7)).isoformat()
            cursor = await conn.execute(
                "SELECT COUNT(*) FROM jobs WHERE seen_at >= ?",
                (cutoff,)
            )
            stats["recent"] = (await cursor.fetchone())[0]
            
            return stats
    
    async def save_application(self, job_id: str, cover_letter: str,
                               notes: str = "") -> int:
        """Save a job application."""
        async with aiosqlite.connect(self.db_path) as conn:
            cursor = await conn.execute(
                "INSERT INTO applications (job_id, cover_letter, notes) VALUES (?, ?, ?)",
                (job_id, cover_letter, notes)
            )
            app_id = cursor.lastrowid
            
            # Update job status
            await conn.execute(
                "UPDATE jobs SET status = 'applied', updated_at = CURRENT_TIMESTAMP WHERE id = ?",
                (job_id,)
            )
            
            await conn.commit()
            return app_id
    
    async def save_analytics(self, result: ScrapeResult):
        """Save scraping analytics."""
        async with aiosqlite.connect(self.db_path) as conn:
            today = datetime.utcnow().date().isoformat()
            
            # Calculate average score
            avg_score = sum(j.score for j in result.jobs) / len(result.jobs) if result.jobs else 0
            
            await conn.execute("""
                INSERT OR REPLACE INTO analytics (
                    date, jobs_found, avg_score, sources_used, kimi_enriched, data
                ) VALUES (?, ?, ?, ?, ?, ?)
            """, (
                today,
                result.total_count,
                avg_score,
                len(result.source_counts),
                1 if result.kimi_enriched else 0,
                json.dumps(result.to_dict())
            ))
            
            await conn.commit()
