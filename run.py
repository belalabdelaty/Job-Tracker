"""Entry point: scrape every enabled source and store results in SQLite.

    python run.py                 # scrape + save
    python run.py --profile me.txt  # score against a profile text file
"""
import argparse
import asyncio
import os
import sys

import httpx

ROOT = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, ROOT)
sys.path.insert(0, os.path.join(ROOT, "scripts"))

from dashboard import Database  # noqa: E402
from niches import apply_niches, load_niches  # noqa: E402
from scraper_v4 import Scraper  # noqa: E402


async def main(profile_path: str | None, niche: str | None = None, top: int = 10) -> int:
    profile = open(profile_path, encoding="utf-8").read() if profile_path else ""
    db = Database()
    await db.init()
    async with httpx.AsyncClient(follow_redirects=True, timeout=30.0) as client:
        scraper = Scraper(client)
        result = await scraper.fetch_all(profile)
    niches = load_niches()
    apply_niches(result.jobs, niches)
    if niche:
        result.jobs = [j for j in result.jobs if f"niche:{niche}" in j.skills]
        result.total_count = len(result.jobs)
    saved = await db.save_jobs(result.jobs)
    await db.save_analytics(result)
    print(f"Fetched {result.total_count} jobs, saved {saved} to {db.db_path}")
    for name, count in sorted(result.source_counts.items()):
        print(f"  {name:<18}{count}")
    print(f"\nTop {top}:")
    for j in sorted(result.jobs, key=lambda j: j.score, reverse=True)[:top]:
        print(f"  [{j.score:>3}] {j.title} @ {j.company} - {j.url}")
    for err in result.errors:
        print(f"  ! {err}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--profile", help="text file describing your skills/target roles")
    ap.add_argument("--niche", help="keep only one niche from niches.json, e.g. customer_support")
    ap.add_argument("--top", type=int, default=10, help="how many best jobs to print")
    a = ap.parse_args()
    sys.exit(asyncio.run(main(a.profile, a.niche, a.top)))
