"""Data models shared by the scraper, database layer and dashboard."""
from __future__ import annotations

from dataclasses import dataclass, field, fields
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


class JobType(str, Enum):
    JOB = "job"
    TASK = "task"


class JobStatus(str, Enum):
    NEW = "new"
    SAVED = "saved"
    APPLIED = "applied"
    INTERVIEW = "interview"
    OFFER = "offer"
    REJECTED = "rejected"
    IGNORED = "ignored"


class RemoteLevel(str, Enum):
    GLOBAL = "global"
    COUNTRY = "country-specific"
    TIMEZONE = "timezone-specific"
    OFFICE_FIRST = "office-first"
    UNKNOWN = "unknown"

    @classmethod
    def _missing_(cls, value):  # unknown LLM output -> UNKNOWN instead of ValueError
        return cls.UNKNOWN


def _parse_dt(value: Any) -> datetime:
    if isinstance(value, datetime):
        return value.replace(tzinfo=None) if value.tzinfo else value
    if isinstance(value, str) and value:
        try:
            dt = datetime.fromisoformat(value.replace("Z", "+00:00"))
            return dt.replace(tzinfo=None) if dt.tzinfo else dt
        except ValueError:
            pass
    return datetime.utcnow()


def _enum(cls, value, default):
    if isinstance(value, cls):
        return value
    try:
        return cls(value)
    except ValueError:
        return default


@dataclass
class EnrichedData:
    salary_range: Optional[str] = None
    required_skills: List[str] = field(default_factory=list)
    experience_years: Optional[float] = None
    visa_sponsorship: bool = False
    benefits: List[str] = field(default_factory=list)
    remote_level: RemoteLevel = RemoteLevel.UNKNOWN
    company_culture: Optional[str] = None
    growth_potential: int = 50

    def to_dict(self) -> Dict[str, Any]:
        d = {f.name: getattr(self, f.name) for f in fields(self)}
        d["remote_level"] = self.remote_level.value
        return d

    @classmethod
    def from_dict(cls, data: Optional[Dict[str, Any]]) -> "EnrichedData":
        data = data or {}
        known = {f.name for f in fields(cls)}
        kwargs = {k: v for k, v in data.items() if k in known}
        kwargs["remote_level"] = _enum(RemoteLevel, kwargs.get("remote_level"), RemoteLevel.UNKNOWN)
        return cls(**kwargs)


@dataclass
class Job:
    id: str = ""
    title: str = ""
    company: str = ""
    location: str = ""
    url: str = ""
    source: str = ""
    source_url: str = ""
    posted_at: datetime = field(default_factory=datetime.utcnow)
    score: int = 0
    kimi_score: Optional[int] = None
    status: JobStatus = JobStatus.NEW
    type: JobType = JobType.JOB
    content: str = ""
    salary_min: Optional[int] = None
    salary_max: Optional[int] = None
    salary_text: Optional[str] = None
    dedup_hash: str = ""
    enriched: Optional[EnrichedData] = None
    remote_issue: Optional[str] = None
    remote_level: Optional[str] = None
    skills: List[str] = field(default_factory=list)
    notes: str = ""
    saved: bool = False
    seen_at: datetime = field(default_factory=datetime.utcnow)

    def __post_init__(self):
        self.posted_at = _parse_dt(self.posted_at)
        self.seen_at = _parse_dt(self.seen_at)
        self.status = _enum(JobStatus, self.status, JobStatus.NEW)
        self.type = _enum(JobType, self.type, JobType.JOB)
        if isinstance(self.enriched, dict):
            self.enriched = EnrichedData.from_dict(self.enriched)
        self.skills = list(self.skills or [])
        self.score = int(self.score or 0)

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> "Job":
        """Build a Job, ignoring keys the scrapers add that aren't model fields."""
        known = {f.name for f in fields(cls)}
        return cls(**{k: v for k, v in data.items() if k in known and v is not None})

    def to_dict(self) -> Dict[str, Any]:
        return {
            "id": self.id, "title": self.title, "company": self.company,
            "location": self.location, "url": self.url, "source": self.source,
            "source_url": self.source_url, "posted_at": self.posted_at.isoformat(),
            "score": self.score, "kimi_score": self.kimi_score,
            "status": self.status.value, "type": self.type.value,
            "content": self.content, "salary_min": self.salary_min,
            "salary_max": self.salary_max, "salary_text": self.salary_text,
            "dedup_hash": self.dedup_hash,
            "enriched": self.enriched.to_dict() if self.enriched else None,
            "remote_issue": self.remote_issue, "remote_level": self.remote_level,
            "skills": self.skills, "notes": self.notes, "saved": self.saved,
            "seen_at": self.seen_at.isoformat(),
        }


@dataclass
class ScrapeResult:
    jobs: List[Job] = field(default_factory=list)
    total_count: int = 0
    source_counts: Dict[str, int] = field(default_factory=dict)
    timestamp: datetime = field(default_factory=datetime.utcnow)
    kimi_enriched: bool = False
    errors: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "total_count": self.total_count,
            "source_counts": self.source_counts,
            "timestamp": self.timestamp.isoformat(),
            "kimi_enriched": self.kimi_enriched,
            "errors": self.errors,
            "jobs": [j.to_dict() for j in self.jobs],
        }
