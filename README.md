# Scanwave CyberIntel Platform

Real-time cyber intelligence platform monitoring Iranian-aligned hacktivist Telegram channels targeting Jordan. Combines live Telegram monitoring, AI-powered analysis, autonomous IOC research, and a military/intel-agency-style web dashboard with dark and light themes.

## Architecture

| Component | File | Role |
|-----------|------|------|
| **Web Dashboard** | `viewer.py` | Flask app serving a single-page UI (`app/static/index.html`) with REST API, APT tracker, blocklist, media viewer, and AI chatbot |
| **Telegram Monitor** | `telegram_monitor.py` | Async Telethon client — live monitoring, backfill, IOC extraction, channel discovery engine |
| **AI Agent** | `ai_agent.py` | GPT-4o — critical message enrichment, keyword learning, channel vetting, periodic threat briefs |
| **Orchestrator** | `orchestrator.py` | Process manager — runs all components, auto-restarts on crash |

## Key Features

### Intelligence Collection
- **43+ Channels Monitored** — Iranian hacktivist groups (APT, hacktivist, leak channels) across 3 threat tiers
- **Auto-Discovery Engine** — Scans forwarded messages, @mentions, t.me/ links to find new threat actor channels; auto-queues high-scoring candidates
- **Real-time Backfill** — Admin-triggered historical message collection with configurable date ranges and limits
- **Media Capture** — Lazy-loaded images and videos from Telegram messages, displayed inline with lightbox viewer

### AI & Analysis
- **AI Enrichment** — GPT-4o-mini analyzes critical alerts for group attribution, attack type, target sector, severity, and recommended actions
- **Keyword Auto-Learning** — AI suggests new attack terms every 2h, auto-applies at 80%+ confidence
- **Integrated Chatbot** — Map-reduce architecture over thousands of messages for comprehensive threat reports; SSE streaming with source citations
- **Autonomous IOC Research** — GPT + AlienVault OTX + ThreatFox fan-out, AbuseIPDB/VirusTotal verification

### Tracking & Reporting
- **APT Tracker** — Profiles threat groups with activity timelines, sector targeting bar charts, attack type breakdowns, and Jordan-specific attack histories
- **Central Blocklist** — Deduplicated, scored IOCs with verdict badges, CSV export, and PDF report generation
- **Coordinated Campaign Detection** — Identifies multiple channels targeting the same keyword on the same day
- **Escalation Alerts** — Pulsing banner when threat urgency reaches HIGH or CRITICAL

### UI / Dashboard
- **Military/Intel Agency Design** — Squared badges (2px radius), muted navy tones, red/amber threat classification markers, uppercase section headers, monospace data fields
- **Dark + Light Themes** — CSS custom property system with 60+ variables; toggle persisted via localStorage
- **Tab Persistence** — Active tab saved to localStorage, restored on page refresh
- **7 Tabs**: Monitor, Dashboard, Blocklist, Timeline, Chat, APT Tracker, Admin
- **Responsive Layout** — Breakpoints at 1400px, 1100px, 900px, and 700px
- **Typography** — Inter (UI) + JetBrains Mono (data) via Google Fonts

## Tech Stack

- **Backend**: Python 3.12, Flask, SQLite (migrated from JSONL)
- **Telegram**: Telethon (async + sync via TGSync)
- **AI/LLM**: OpenAI GPT-4o / GPT-4o-mini
- **Threat Intel**: AlienVault OTX, ThreatFox, AbuseIPDB, VirusTotal
- **Frontend**: Single-file SPA (`app/static/index.html`) — embedded CSS, HTML, JS (~5,300 lines)
- **Deploy**: Docker + Docker Compose on OCI

## Quick Start

### Local Development

```bash
# Set environment variables
export OPENAI_API_KEY=sk-...
export ABUSEIPDB_KEY=...       # Optional — for IOC verification
export VT_API_KEY=...          # Optional — for hash checking

# Install dependencies
pip install -r requirements.txt

# Run everything (recommended)
python orchestrator.py

# Or run individually
python viewer.py &
python telegram_monitor.py --live &
python ai_agent.py &
```

Dashboard: http://localhost:5000

### Docker

```bash
# Configure .env file with API keys
docker compose up --build -d
docker compose logs -f
```

Default port: `8888` (configurable via `HOST_PORT` in `.env`)

## Project Structure

```
cybernews/
  viewer.py                 # Flask web app + REST API (~6,400 lines)
  telegram_monitor.py       # Live Telegram monitoring + discovery engine
  ai_agent.py               # AI enrichment + keyword learning agent
  orchestrator.py            # Process manager (auto-restart)
  requirements.txt           # Python dependencies
  Dockerfile                 # Container build
  docker-compose.yml         # Container orchestration
  scanwave_report_template.docx  # PDF report template
  app/
    static/
      index.html             # Single-page frontend (~5,300 lines)
  telegram_intel/            # Data directory
    messages.jsonl           # Message database (~7,500+ messages)
    keywords.json            # Keyword filter lists (568 critical, 216 medium)
    channels_config.json     # Channel tier/threat/status config (43 channels)
    apt_ioc_research.json    # Cached IOC research results
    discovered_channels.json # Auto-discovery engine findings
    pending_channels.json    # Channels queued for monitoring
    ai_suggestions.json      # AI agent keyword/channel suggestions
    backfill_queue.json      # Admin-queued backfill requests
    abuseipdb_cache.json     # AbuseIPDB lookup cache
```

## API Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /api/messages/all` | All messages (filterable by priority, channel, date, search, critical_subtype) |
| `GET /api/messages/<channel>` | Messages for a specific channel |
| `GET /api/messages/export` | CSV export of messages |
| `GET /api/dashboard` | Dashboard stats, keyword heatmap, activity grid |
| `GET /api/briefing` | 24h intelligence briefing summary |
| `GET /api/trend` | 30-day alert trend data |
| `GET /api/escalation` | Current escalation level assessment |
| `GET /api/matrix` | Threat actor × target category matrix |
| `GET /api/apt/profiles` | APT group profiles with tier/status |
| `GET /api/apt/<name>/detail` | APT detail — sectors, attacks, timeline, IOCs |
| `GET /api/apt/<name>/research` | External threat intelligence for APT |
| `GET /api/blocklist` | Central IOC blocklist with verdicts |
| `GET /api/blocklist/export` | Blocklist CSV export |
| `GET /api/blocklist/report` | Generate PDF threat report |
| `GET /api/iocs` | Extracted IOCs from messages |
| `GET /api/media/lookup/<ch>/<id>` | Media files for a message |
| `POST /api/chat/stream` | SSE chatbot endpoint (map-reduce) |
| `POST /api/translate` | On-demand message translation |
| `GET /api/admin/status` | System health, DB stats, log tail |
| `GET/POST /api/admin/keywords` | Load/save keyword filter lists |
| `GET/POST/DELETE /api/admin/channels` | Channel configuration CRUD |
| `POST /api/admin/backfill` | Queue historical message backfill |
| `POST /api/admin/compact` | Deduplicate message database |
| `GET /api/admin/discovered` | Discovery engine results |
| `POST /api/ai/analyze` | Trigger AI analysis cycle |
| `GET /api/ai/status` | AI agent status |

## License

Private — internal use only.
