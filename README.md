#  Job Tracker Bot

Automatically monitors **25+ top tech company** career pages and sends real-time alerts via **Telegram, Discord, WhatsApp, and Email**. Runs free on GitHub Actions every 2 hours.

---

##  Companies Tracked

| Category | Companies |
|---|---|
| Big Tech | Google, Apple, Meta, Microsoft, Amazon, Netflix |
| AI Labs | Anthropic, OpenAI, DeepMind, Mistral AI, Perplexity, Cursor |
| Developer Tools | Stripe, Vercel, Figma, Notion, Linear, Supabase, Dropbox |
| Others | Airbnb, Spotify, Twilio, Coinbase |

> **Want more?** Add any Greenhouse/Lever/Ashby company in `scripts/scraper.py` in under 2 lines , see the "Adding Companies" section below.

---

##  Setup (5–10 minutes)

### Step 1 — Fork this repo

Click **Fork** on GitHub to get your own copy.

### Step 2 — Add your secrets

Go to your repo → **Settings → Secrets and variables → Actions → New repository secret**

Add the secrets for whichever channels you want:

#### Telegram (recommended — easiest)
| Secret | Value |
|---|---|
| `TELEGRAM_BOT_TOKEN` | Get from [@BotFather](https://t.me/BotFather) → `/newbot` |
| `TELEGRAM_CHAT_ID` | Your chat ID — get from [@userinfobot](https://t.me/userinfobot) |

#### Discord
| Secret | Value |
|---|---|
| `DISCORD_WEBHOOK_URL` | Server Settings → Integrations → Webhooks → New Webhook → Copy URL |

#### WhatsApp (via Twilio)
| Secret | Value |
|---|---|
| `TWILIO_ACCOUNT_SID` | From [twilio.com/console](https://console.twilio.com) |
| `TWILIO_AUTH_TOKEN` | From [twilio.com/console](https://console.twilio.com) |
| `TWILIO_WHATSAPP_FROM` | `whatsapp:+14155238886` (Twilio sandbox number) |
| `TWILIO_WHATSAPP_TO` | `whatsapp:+YOUR_NUMBER` (must be verified in sandbox) |

#### Email (Gmail)
| Secret | Value |
|---|---|
| `SMTP_HOST` | `smtp.gmail.com` |
| `SMTP_PORT` | `587` |
| `SMTP_USER` | Your Gmail address |
| `SMTP_PASS` | A Gmail [App Password](https://myaccount.google.com/apppasswords) (not your real password!) |
| `EMAIL_TO` | Where to send alerts |

### Step 3 — (Optional) Set keyword filters

Add a secret called `JOB_KEYWORDS` with comma-separated keywords to only get relevant roles:

```
engineer,ml,python,backend
```

Leave it empty to receive all new job postings.

### Step 4 — Enable Actions

Go to **Actions tab** → click **"I understand my workflows, go ahead and enable them"**.

Then click **"Job Tracker Bot"** → **"Run workflow"** to test it manually!

---

##  Schedule

The bot runs **every 2 hours** by default. To change it, edit the cron in `.github/workflows/job-tracker.yml`:

```yaml
- cron: "0 */2 * * *"   # every 2 hours
- cron: "0 9,18 * * *"  # 9am and 6pm every day
- cron: "*/30 * * * *"  # every 30 minutes
```

> GitHub Actions free tier: 2,000 minutes/month. Every 2 hours = ~360 runs/month ≈ ~6 minutes total. 

---

##  Adding Companies

**Greenhouse** (most common — Figma, Notion, Linear, etc.):
```python
{"name": "YourCompany", "url": "https://boards-api.greenhouse.io/v1/boards/COMPANY_SLUG/jobs?content=true", "type": "greenhouse"},
```

**Lever** (Spotify, Coinbase, etc.):
```python
{"name": "YourCompany", "url": "https://api.lever.co/v0/postings/COMPANY_SLUG?mode=json&limit=20", "type": "lever"},
```

To find the company slug, visit their jobs page — it's usually in the URL (e.g. `jobs.lever.co/stripe` → slug is `stripe`).

---

##  Project Structure

```
job-tracker/
├── .github/
│   └── workflows/
│       └── job-tracker.yml   ← GitHub Actions schedule & config
├── scripts/
│   └── scraper.py            ← Main scraper + all notifiers
├── data/
│   └── seen_jobs.json        ← Cached job IDs (auto-managed)
└── README.md
```

---

##  Local Testing

```bash
pip install requests

# Set env vars first
export TELEGRAM_BOT_TOKEN="..."
export TELEGRAM_CHAT_ID="..."

python scripts/scraper.py
```

---

##  FAQ

**Why is `seen_jobs.json` in a GitHub Actions cache and not committed?**
Because GitHub Actions cache is ephemeral but persistent: it survives between runs but doesn't pollute your git history with JSON changes every 2 hours.

**It's not sending alerts after the first run.**
That's correct , it only alerts on *new* jobs. On the very first run it will populate the seen list. New alerts will fire as companies post new roles.

**A company's API changed and it's failing silently.**
Each company fetch is wrapped in a try/catch and logs a warning. Check the Actions run logs for `fetch failed` messages. Open an issue or update the URL.


---
 
## Contributing
 
PRs welcome - especially:
- New companies (Greenhouse/Lever/Ashby slugs are one line each)
- Better HTML parsers for custom career pages
- Bug fixes for unstable company APIs
 
