# RemoteLover

Async remote-job scraper and tracking dashboard. It pulls listings from RemoteOK, Remotive, Himalayas, We Work Remotely, YC, Wellfound, Reddit, Hacker News, GitHub issues, Greenhouse boards (and Indeed/LinkedIn via JobSpy), scores them, optionally enriches them with Kimi K2, and stores everything in SQLite. A Dash app lets you browse, match against your profile and track applications.

## Quick start

```bash
pip install -r requirements-dashboard.txt
cp .env.example .env        # all keys optional
python run.py               # scrape -> data/jobs.db
python app_dash.py          # open the dashboard
```

`python run.py --niche customer_support --top 20` keeps one niche; `--profile me.txt` scores jobs against a description of your skills.

## Layout

| File | Purpose |
|---|---|
| `run.py` | CLI entry point: scrape, save, record analytics |
| `scripts/scraper_v4.py` | Source fetchers, scoring, Kimi K2 enrichment |
| `niches.py` + `niches.json` | Role niches (customer support, VA, data ops...) and geo-restriction detection. Add a niche by editing the JSON |
| `models.py` | `Job`, `EnrichedData`, `ScrapeResult` and enums |
| `config.py` | Settings from env vars / `.env` |
| `dashboard.py` | Async SQLite layer (jobs, applications, sources, analytics) |
| `app_dash.py` | Dash web UI |

## Scheduled scraping

`.github/workflows/job-tracker.yml` runs `run.py` every 2 hours, keeps `data/jobs.db` in the Actions cache between runs, and uploads it as an artifact (download it to browse locally). Optional secrets: `KIMI_API_KEY`, `SERPAPI_KEY`, `X_BEARER_TOKEN`.

## Configuration

See `.env.example`. Sources that need a key (X, Google via SerpAPI) are skipped when it is missing; without `KIMI_API_KEY` jobs use rule-based scoring.
