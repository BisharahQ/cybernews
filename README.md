# Scanwave CyberIntel Platform

Real-time cyber intelligence platform monitoring Iranian-aligned hacktivist Telegram channels targeting Jordan. Combines live Telegram monitoring, AI-powered analysis, autonomous IOC research, and a military-style web dashboard.

## Architecture

| Component | File | Role |
|-----------|------|------|
| **Web Dashboard** | `viewer.py` | Flask app — UI, REST API, APT tracker, blocklist, chatbot |
| **Telegram Monitor** | `telegram_monitor.py` | Async Telethon client — live monitoring, IOC extraction, channel discovery |
| **AI Agent** | `ai_agent.py` | GPT-4o — message enrichment, keyword learning, channel vetting, threat briefs |
| **Orchestrator** | `orchestrator.py` | Process manager — runs all components, auto-restarts on crash |

## Key Features

- **43+ Channels Monitored** — Iranian hacktivist groups (APT, hacktivist, leak channels)
- **Auto-Discovery Engine** — Scans forwarded messages, @mentions, t.me/ links to find new threat actor channels
- **AI Enrichment** — GPT-4o-mini analyzes critical alerts for attribution, attack type, severity, recommended actions
- **Keyword Auto-Learning** — AI suggests new attack terms every 2h, auto-applies at 80%+ confidence
- **APT Tracker** — Profiles threat groups with timelines, sector targeting, attack patterns
- **Autonomous IOC Research** — GPT + AlienVault OTX + ThreatFox fan-out, AbuseIPDB/VirusTotal verification
- **Central Blocklist** — Deduplicated, scored IOCs with CSV export and Telegram bot notifications
- **Integrated Chatbot** — Map-reduce over thousands of messages for comprehensive threat reports
- **Responsive Dashboard** — Scales from 700px mobile to 1400px+ widescreen

## Tech Stack

- **Backend**: Python 3.12, Flask
- **Telegram**: Telethon (async + sync)
- **AI/LLM**: OpenAI GPT-4o / GPT-4o-mini
- **Threat Intel**: AlienVault OTX, ThreatFox, AbuseIPDB, VirusTotal
- **Data**: JSONL flat files (no database)
- **Deploy**: Docker + Docker Compose

## Quick Start

### Local Development

```bash
# Set environment variables
export OPENAI_API_KEY=sk-...
export ABUSEIPDB_KEY=...       # Optional — for IOC verification
export VT_API_KEY=...          # Optional — for hash checking

# Install dependencies
pip install -r requirements.txt

# Run everything
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
  viewer.py              # Flask web app + all frontend (single-file)
  telegram_monitor.py    # Live Telegram monitoring + discovery
  ai_agent.py            # AI enrichment + keyword learning
  orchestrator.py        # Process manager
  requirements.txt       # Python dependencies
  Dockerfile             # Container build
  docker-compose.yml     # Container orchestration
  telegram_intel/        # Data directory
    messages.jsonl       # Message database
    keywords.json        # Keyword filter lists
    channels_config.json # Channel tier config
    apt_ioc_research.json # Cached IOC research
    ...
```

## API Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /api/messages/all` | All messages (filterable by priority, date) |
| `GET /api/messages/<channel>` | Messages for a specific channel |
| `GET /api/dashboard` | Dashboard stats and charts |
| `GET /api/apt/profiles` | APT group profiles |
| `GET /api/apt/<name>/detail` | APT detail + IOCs |
| `GET /api/blocklist` | Central IOC blocklist |
| `GET /api/blocklist/export` | CSV export |
| `POST /api/chat/stream` | SSE chatbot endpoint |
| `GET /api/admin/status` | System health |
| `POST /api/admin/keywords` | Update keyword filters |

## License

Private — internal use only.
