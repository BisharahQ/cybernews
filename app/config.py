"""
Scanwave CyberIntel Platform — Centralized Configuration
=========================================================
All environment variables, paths, and constants live here.
"""

import os
from pathlib import Path
from dotenv import load_dotenv

# Load .env from project root
_PROJECT_ROOT = Path(__file__).resolve().parent.parent
load_dotenv(_PROJECT_ROOT / ".env")

# ── Paths ───────────────────────────────────────────────────────────────────
DATA_DIR = _PROJECT_ROOT / "telegram_intel"
DB_PATH = DATA_DIR / "intel.db"
SESSION_PATH = str(_PROJECT_ROOT / "jordan_cyber_intel")

# ── API Keys ────────────────────────────────────────────────────────────────
OPENAI_API_KEY = os.environ.get("OPENAI_API_KEY", "")
ABUSEIPDB_KEY = os.environ.get("ABUSEIPDB_API_KEY",
    "d1ee5f84fe37927d1e03bc40eee43241f0da49c4c192f2bba149e4895f8c664de10bac16360b271d")
OTX_KEY = os.environ.get("OTX_API_KEY",
    "868c2e9e62dfc53b961657ef3194890c6d716774f8755a75aa46a8a24832d0fc")

# ── Telegram ────────────────────────────────────────────────────────────────
TG_API_ID = int(os.environ.get("TG_API_ID", "35545979"))
TG_API_HASH = os.environ.get("TG_API_HASH", "41240e3f451065a430692d2e1bc82453")

# ── Cache / TTL ─────────────────────────────────────────────────────────────
APT_RESEARCH_TTL_HOURS = 48
ABUSEIPDB_CACHE_TTL_HOURS = 168  # 7 days

# ── Flask ───────────────────────────────────────────────────────────────────
FLASK_HOST = os.environ.get("FLASK_HOST", "0.0.0.0")
FLASK_PORT = int(os.environ.get("FLASK_PORT", "5000"))
FLASK_DEBUG = os.environ.get("FLASK_DEBUG", "0") == "1"
