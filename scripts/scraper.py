#!/usr/bin/env python3
"""
Job Tracker Scraper
Fetches new job listings from major tech companies and sends alerts.
"""

import os
import json
import hashlib
import logging
import requests
import time
from datetime import datetime
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s")
log = logging.getLogger(__name__)

# ─────────────────────────────────────────────
# COMPANY CAREER PAGE CONFIGS
# Each entry: name, api_url or scrape_url, parser_type
# ─────────────────────────────────────────────
COMPANIES = [
    # ── Big Tech ──
    {
        "name": "Google",
        "url": "https://careers.google.com/api/v3/search/?page_size=20&sort_by=date",
        "type": "google",
    },
    {
        "name": "Apple",
        "url": "https://jobs.apple.com/api/role/search?page=1&pageSize=20&sort=newest",
        "type": "apple",
    },
    {
        "name": "Meta",
        "url": "https://www.metacareers.com/graphql",
        "type": "meta",
    },
    {
        "name": "Microsoft",
        "url": "https://gcsservices.careers.microsoft.com/search/api/v1/search?pg=1&pgSz=20&so=Relevance",
        "type": "microsoft",
    },
    {
        "name": "Amazon",
        "url": "https://www.amazon.jobs/en/search.json?country=&city=&region=&county=&query=&query_options=&normalized_country_code=&normalized_city_name=&normalized_state_name=&normalized_county_name=&offset=0&result_limit=20&sort=recent",
        "type": "amazon",
    },
    {
        "name": "Netflix",
        "url": "https://jobs.netflix.com/api/search?page=1",
        "type": "netflix",
    },
    # ── AI / Anthropic ──
    {
        "name": "Anthropic",
        "url": "https://boards-api.greenhouse.io/v1/boards/anthropic/jobs?content=true",
        "type": "greenhouse",
    },
    {
        "name": "OpenAI",
        "url": "https://boards-api.greenhouse.io/v1/boards/openai/jobs?content=true",
        "type": "greenhouse",
    },
    {
        "name": "DeepMind",
        "url": "https://boards-api.greenhouse.io/v1/boards/deepmind/jobs?content=true",
        "type": "greenhouse",
    },
    {
        "name": "Mistral AI",
        "url": "https://boards-api.greenhouse.io/v1/boards/mistral/jobs?content=true",
        "type": "greenhouse",
    },
    # ── Greenhouse-powered companies ──
    {
        "name": "Stripe",
        "url": "https://boards-api.greenhouse.io/v1/boards/stripe/jobs?content=true",
        "type": "greenhouse",
    },
    {
        "name": "Airbnb",
        "url": "https://boards-api.greenhouse.io/v1/boards/airbnb/jobs?content=true",
        "type": "greenhouse",
    },
    {
        "name": "Dropbox",
        "url": "https://boards-api.greenhouse.io/v1/boards/dropbox/jobs?content=true",
        "type": "greenhouse",
    },
    {
        "name": "Figma",
        "url": "https://boards-api.greenhouse.io/v1/boards/figma/jobs?content=true",
        "type": "greenhouse",
    },
    {
        "name": "Notion",
        "url": "https://boards-api.greenhouse.io/v1/boards/notion/jobs?content=true",
        "type": "greenhouse",
    },
    {
        "name": "Vercel",
        "url": "https://boards-api.greenhouse.io/v1/boards/vercel/jobs?content=true",
        "type": "greenhouse",
    },
    {
        "name": "Linear",
        "url": "https://boards-api.greenhouse.io/v1/boards/linear/jobs?content=true",
        "type": "greenhouse",
    },
    # ── Lever-powered companies ──
    {
        "name": "Spotify",
        "url": "https://api.lever.co/v0/postings/spotify?mode=json&limit=20",
        "type": "lever",
    },
    {
        "name": "Twilio",
        "url": "https://api.lever.co/v0/postings/twilio?mode=json&limit=20",
        "type": "lever",
    },
    {
        "name": "Coinbase",
        "url": "https://api.lever.co/v0/postings/coinbase?mode=json&limit=20",
        "type": "lever",
    },
    # ── Ashby-powered companies ──
    {
        "name": "Perplexity AI",
        "url": "https://jobs.ashbyhq.com/api/non-user-facing/job-board/perplexity/posting-groups",
        "type": "ashby",
    },
    {
        "name": "Cursor",
        "url": "https://jobs.ashbyhq.com/api/non-user-facing/job-board/cursor/posting-groups",
        "type": "ashby",
    },
    {
        "name": "Supabase",
        "url": "https://jobs.ashbyhq.com/api/non-user-facing/job-board/supabase/posting-groups",
        "type": "ashby",
    },
]

HEADERS = {
    "User-Agent": "Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36",
    "Accept": "application/json",
}

# ─────────────────────────────────────────────
# PARSERS — each returns list of {id, title, location, url, company}
# ─────────────────────────────────────────────

def parse_greenhouse(data, company_name):
    jobs = []
    for job in data.get("jobs", []):
        jobs.append({
            "id": str(job.get("id", "")),
            "title": job.get("title", ""),
            "location": job.get("location", {}).get("name", ""),
            "url": job.get("absolute_url", ""),
            "company": company_name,
        })
    return jobs


def parse_lever(data, company_name):
    jobs = []
    for job in data:
        jobs.append({
            "id": job.get("id", ""),
            "title": job.get("text", ""),
            "location": job.get("categories", {}).get("location", ""),
            "url": job.get("hostedUrl", ""),
            "company": company_name,
        })
    return jobs


def parse_ashby(data, company_name):
    jobs = []
    for group in data.get("jobPostingGroups", []):
        for job in group.get("jobPostings", []):
            jobs.append({
                "id": job.get("id", ""),
                "title": job.get("title", ""),
                "location": ", ".join([loc.get("name", "") for loc in job.get("jobLocations", [])]),
                "url": f"https://jobs.ashbyhq.com/{company_name.lower().replace(' ', '')}/{job.get('id', '')}",
                "company": company_name,
            })
    return jobs


def parse_google(data, company_name):
    jobs = []
    for job in data.get("jobs", []):
        locations = [loc.get("display", "") for loc in job.get("locations", [])]
        jobs.append({
            "id": job.get("job_id", ""),
            "title": job.get("title", ""),
            "location": ", ".join(locations[:2]),
            "url": f"https://careers.google.com/jobs/results/{job.get('job_id', '')}",
            "company": company_name,
        })
    return jobs


def parse_apple(data, company_name):
    jobs = []
    for job in data.get("searchResults", []):
        jobs.append({
            "id": str(job.get("positionId", "")),
            "title": job.get("postingTitle", ""),
            "location": job.get("location", ""),
            "url": f"https://jobs.apple.com/en-us/details/{job.get('positionId', '')}",
            "company": company_name,
        })
    return jobs


def parse_meta(data, company_name):
    jobs = []
    results = data.get("data", {}).get("job_search", {}).get("results", [])
    for job in results:
        jobs.append({
            "id": str(job.get("id", "")),
            "title": job.get("title", ""),
            "location": ", ".join(job.get("locations", [])),
            "url": f"https://www.metacareers.com/jobs/{job.get('id', '')}",
            "company": company_name,
        })
    return jobs


def parse_microsoft(data, company_name):
    jobs = []
    for job in data.get("operationResult", {}).get("result", {}).get("jobs", []):
        jobs.append({
            "id": str(job.get("jobId", "")),
            "title": job.get("title", ""),
            "location": job.get("properties", {}).get("primaryLocation", ""),
            "url": f"https://jobs.careers.microsoft.com/global/en/job/{job.get('jobId', '')}",
            "company": company_name,
        })
    return jobs


def parse_amazon(data, company_name):
    jobs = []
    for job in data.get("jobs", []):
        jobs.append({
            "id": str(job.get("id", "")),
            "title": job.get("title", ""),
            "location": job.get("location", ""),
            "url": f"https://www.amazon.jobs{job.get('job_path', '')}",
            "company": company_name,
        })
    return jobs


def parse_netflix(data, company_name):
    jobs = []
    for job in data.get("records", {}).get("postings", []):
        jobs.append({
            "id": job.get("external_id", job.get("id", "")),
            "title": job.get("text", ""),
            "location": job.get("location", ""),
            "url": f"https://jobs.netflix.com/jobs/{job.get('external_id', '')}",
            "company": company_name,
        })
    return jobs


PARSERS = {
    "greenhouse": parse_greenhouse,
    "lever": parse_lever,
    "ashby": parse_ashby,
    "google": parse_google,
    "apple": parse_apple,
    "meta": parse_meta,
    "microsoft": parse_microsoft,
    "amazon": parse_amazon,
    "netflix": parse_netflix,
}

# ─────────────────────────────────────────────
# FETCH JOBS
# ─────────────────────────────────────────────

def get_job_uid(job):
    """Generate a unique ID for a job, using content hash as fallback if ID is missing."""
    job_id = job.get("id", "").strip()
    
    if job_id:
        return f"{job['company']}::{job_id}"
    
    content = f"{job['company']}::{job['title']}::{job.get('location', '')}"
    content_hash = hashlib.md5(content.encode()).hexdigest()
    return f"{job['company']}::hash::{content_hash}"


def fetch_jobs(company):
    name = company["name"]
    url = company["url"]
    parser_type = company["type"]

    try:
        if parser_type == "meta":
            payload = {
                "query": """query JobSearchQuery($search_input: JobSearchInput!) {
                    job_search(search_input: $search_input) {
                        results { id title locations }
                    }
                }""",
                "variables": {"search_input": {"page": 1, "count": 20, "sort_by_date": True}},
            }
            r = requests.post(url, json=payload, headers=HEADERS, timeout=15)
        else:
            r = requests.get(url, headers=HEADERS, timeout=15)

        r.raise_for_status()
        data = r.json()
        parser = PARSERS.get(parser_type)
        if parser:
            return parser(data, name)
        return []

    except Exception as e:
        log.warning(f"[{name}] fetch failed: {e}")
        return []


# ─────────────────────────────────────────────
# SEEN JOBS STATE
# ─────────────────────────────────────────────

STATE_FILE = Path("data/seen_jobs.json")

def load_seen():
    if STATE_FILE.exists():
        return set(json.loads(STATE_FILE.read_text()))
    return set()

def save_seen(seen):
    STATE_FILE.parent.mkdir(exist_ok=True)
    STATE_FILE.write_text(json.dumps(list(seen)))


# ─────────────────────────────────────────────
# KEYWORD FILTERING
# ─────────────────────────────────────────────

KEYWORDS = os.getenv("JOB_KEYWORDS", "").lower().split(",")
KEYWORDS = [k.strip() for k in KEYWORDS if k.strip()]

def matches_filter(job):
    if not KEYWORDS:
        return True
    text = (job["title"] + " " + job.get("location", "")).lower()
    return any(kw in text for kw in KEYWORDS)


# ─────────────────────────────────────────────
# NOTIFIERS
# ─────────────────────────────────────────────

def send_telegram(jobs):
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        return
    for job in jobs:
        msg = (
            f"🆕 *New Job Alert*\n"
            f"🏢 *{job['company']}*\n"
            f"💼 {job['title']}\n"
            f"📍 {job.get('location') or 'Remote/Multiple'}\n"
            f"🔗 [Apply here]({job['url']})"
        )
        try:
            r = requests.post(
                f"https://api.telegram.org/bot{token}/sendMessage",
                json={"chat_id": chat_id, "text": msg, "parse_mode": "Markdown"},
                timeout=10,
            )
            r.raise_for_status()
        except Exception as e:
            log.warning(f"Telegram send failed: {e}")
        time.sleep(0.3)  # rate limit


def send_discord(jobs):
    webhook_url = os.getenv("DISCORD_WEBHOOK_URL")
    if not webhook_url:
        return
    for job in jobs:
        embed = {
            "title": job["title"],
            "url": job["url"],
            "color": 0x5865F2,
            "fields": [
                {"name": "Company", "value": job["company"], "inline": True},
                {"name": "Location", "value": job.get("location") or "Remote/Multiple", "inline": True},
            ],
            "footer": {"text": "Job Tracker Bot"},
            "timestamp": datetime.utcnow().isoformat(),
        }
        try:
            r = requests.post(webhook_url, json={"embeds": [embed]}, timeout=10)
            r.raise_for_status()
        except Exception as e:
            log.warning(f"Discord send failed: {e}")
        time.sleep(0.5)


def send_whatsapp(jobs):
    account_sid = os.getenv("TWILIO_ACCOUNT_SID")
    auth_token = os.getenv("TWILIO_AUTH_TOKEN")
    from_number = os.getenv("TWILIO_WHATSAPP_FROM")  # e.g. whatsapp:+14155238886
    to_number = os.getenv("TWILIO_WHATSAPP_TO")      # e.g. whatsapp:+1234567890
    if not all([account_sid, auth_token, from_number, to_number]):
        return
    for job in jobs:
        msg = (
            f"🆕 New Job Alert!\n"
            f"🏢 {job['company']}\n"
            f"💼 {job['title']}\n"
            f"📍 {job.get('location') or 'Remote/Multiple'}\n"
            f"🔗 {job['url']}"
        )
        try:
            r = requests.post(
                f"https://api.twilio.com/2010-04-01/Accounts/{account_sid}/Messages.json",
                auth=(account_sid, auth_token),
                data={"From": from_number, "To": to_number, "Body": msg},
                timeout=10,
            )
            r.raise_for_status()
        except Exception as e:
            log.warning(f"WhatsApp send failed: {e}")
        time.sleep(0.5)


def send_email(jobs):
    import smtplib
    from email.mime.multipart import MIMEMultipart
    from email.mime.text import MIMEText

    smtp_host = os.getenv("SMTP_HOST", "smtp.gmail.com")
    smtp_port = int(os.getenv("SMTP_PORT", "587"))
    smtp_user = os.getenv("SMTP_USER")
    smtp_pass = os.getenv("SMTP_PASS")
    email_to   = os.getenv("EMAIL_TO")

    if not all([smtp_user, smtp_pass, email_to]):
        return

    rows = ""
    for job in jobs:
        rows += f"""
        <tr>
          <td style="padding:8px;border-bottom:1px solid #eee;">{job['company']}</td>
          <td style="padding:8px;border-bottom:1px solid #eee;"><a href="{job['url']}">{job['title']}</a></td>
          <td style="padding:8px;border-bottom:1px solid #eee;">{job.get('location') or 'Remote'}</td>
        </tr>"""

    html = f"""
    <html><body style="font-family:sans-serif;max-width:680px;margin:auto;">
      <h2 style="color:#1a1a2e;">🆕 {len(jobs)} New Job Alert{"s" if len(jobs)>1 else ""}</h2>
      <table style="width:100%;border-collapse:collapse;">
        <thead><tr style="background:#f5f5f5;">
          <th style="padding:8px;text-align:left;">Company</th>
          <th style="padding:8px;text-align:left;">Role</th>
          <th style="padding:8px;text-align:left;">Location</th>
        </tr></thead>
        <tbody>{rows}</tbody>
      </table>
      <p style="color:#888;font-size:12px;margin-top:24px;">Sent by your Job Tracker Bot · {datetime.utcnow().strftime('%Y-%m-%d %H:%M UTC')}</p>
    </body></html>"""

    msg = MIMEMultipart("alternative")
    msg["Subject"] = f"[Job Tracker] {len(jobs)} new opening{'s' if len(jobs)>1 else ''}"
    msg["From"] = smtp_user
    msg["To"] = email_to
    msg.attach(MIMEText(html, "html"))

    try:
        with smtplib.SMTP(smtp_host, smtp_port) as s:
            s.starttls()
            s.login(smtp_user, smtp_pass)
            s.sendmail(smtp_user, email_to, msg.as_string())
        log.info(f"Email sent to {email_to}")
    except Exception as e:
        log.warning(f"Email send failed: {e}")


# ─────────────────────────────────────────────
# MAIN
# ─────────────────────────────────────────────

def main():
    log.info("=== Job Tracker started ===")
    seen = load_seen()
    new_jobs = []

    for company in COMPANIES:
        log.info(f"Fetching {company['name']}...")
        jobs = fetch_jobs(company)
        log.info(f"  → {len(jobs)} jobs fetched")

        for job in jobs:
            uid = get_job_uid(job)
            if uid not in seen:
                seen.add(uid)
                if matches_filter(job):
                    new_jobs.append(job)

        time.sleep(1)  # be polite

    log.info(f"\n✅ {len(new_jobs)} new jobs found")

    if new_jobs:
        send_telegram(new_jobs)
        send_discord(new_jobs)
        send_whatsapp(new_jobs)
        send_email(new_jobs)
        log.info("Alerts sent!")
    else:
        log.info("No new jobs — nothing to send.")

    save_seen(seen)
    log.info("=== Done ===")


if __name__ == "__main__":
    main()
