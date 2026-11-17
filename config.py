"""Settings loaded from environment variables (and an optional local .env)."""
import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path


def _load_dotenv(path: Path = Path(".env")) -> None:
    if not path.exists():
        return
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        os.environ.setdefault(key.strip(), value.split(" #")[0].strip().strip('"').strip("'"))


def _bool(name: str, default: bool) -> bool:
    return os.getenv(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


def _int(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, default))
    except ValueError:
        return default


def _float(name: str, default: float) -> float:
    try:
        return float(os.getenv(name, default))
    except ValueError:
        return default


@dataclass(frozen=True)
class Settings:
    DB_PATH: str
    REQUEST_TIMEOUT: int
    MAX_RETRIES: int
    MAX_RESULTS_PER_SOURCE: int
    KIMI_API_KEY: str
    KIMI_ENABLED: bool
    KIMI_MODEL: str
    KIMI_TEMPERATURE: float
    KIMI_MAX_TOKENS: int
    KIMI_MAX_CONCURRENT: int
    GITHUB_TOKEN: str
    SERPAPI_KEY: str
    X_BEARER_TOKEN: str
    GEMINI_API_KEY: str
    LOG_LEVEL: str


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    _load_dotenv()
    return Settings(
        DB_PATH=os.getenv("DB_PATH", "data/jobs.db"),
        REQUEST_TIMEOUT=_int("REQUEST_TIMEOUT", 20),
        MAX_RETRIES=_int("MAX_RETRIES", 3),
        MAX_RESULTS_PER_SOURCE=_int("MAX_RESULTS_PER_SOURCE", 50),
        KIMI_API_KEY=os.getenv("KIMI_API_KEY", ""),
        KIMI_ENABLED=_bool("KIMI_ENABLED", True),
        KIMI_MODEL=os.getenv("KIMI_MODEL", "kimi-k2-0905-preview"),
        KIMI_TEMPERATURE=_float("KIMI_TEMPERATURE", 0.3),
        KIMI_MAX_TOKENS=_int("KIMI_MAX_TOKENS", 1024),
        KIMI_MAX_CONCURRENT=_int("KIMI_MAX_CONCURRENT", 5),
        GITHUB_TOKEN=os.getenv("GITHUB_TOKEN", ""),
        SERPAPI_KEY=os.getenv("SERPAPI_KEY", ""),
        X_BEARER_TOKEN=os.getenv("X_BEARER_TOKEN", ""),
        GEMINI_API_KEY=os.getenv("GEMINI_API_KEY", ""),
        LOG_LEVEL=os.getenv("LOG_LEVEL", "INFO"),
    )
