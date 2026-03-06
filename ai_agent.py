#!/usr/bin/env python3
"""
AI INTELLIGENCE AGENT — Jordan Cyber Intel Platform
=====================================================
Autonomous daemon that runs 8 parallel loops, each adding real value:

LOOP 1 — CRITICAL MESSAGE ENRICHMENT (near-real-time, ~30s lag)
  Watches messages.jsonl for new CRITICAL messages.
  For each one: calls GPT to add attribution, context, severity note.
  Writes enriched record to enriched_alerts.jsonl + ai_briefings key.

LOOP 2 — KEYWORD AUTO-LEARNING (every 2 hours)
  Reads last 2h of new messages.
  Asks GPT: "What new attack terms did you see that aren't in our keyword list?"
  Auto-applies suggestions with confidence >= 80% directly to keywords.json.
  No manual review needed — keywords grow automatically with the threat landscape.

LOOP 3 — CHANNEL AUTO-VETTING (every 5 minutes, watches discovery file)
  When the discovery engine adds a new candidate channel:
  Reads that channel's messages from our DB.
  AI decides: relevant threat actor (auto-approve) or noise (auto-dismiss).
  No human needs to review channels unless AI is unsure.

LOOP 4 — THREAT BRIEF GENERATION (every 6 hours)
  Produces a structured JSON intelligence brief:
    - Active threat actors and their recent activity
    - Attack patterns and targeted sectors
    - Key IOCs seen today
    - Escalation assessment
    - Recommended actions
  Stored in ai_brief.json, shown in dashboard.

SETUP:
  set OPENAI_API_KEY=sk-...    (Windows)
  python ai_agent.py           (runs all 4 loops forever)
"""

import os
import re
import json
import time
import threading
import logging
from pathlib import Path
from datetime import datetime, timezone, timedelta
from collections import defaultdict

try:
    from openai import OpenAI
except ImportError:
    print("ERROR: pip install openai")
    exit(1)

# ── Load .env at startup ────────────────────────────────────────────────────────
def _load_dotenv():
    env_path = Path(__file__).parent / ".env"
    if not env_path.exists():
        return
    for line in env_path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        key = key.strip(); val = val.strip().strip('"').strip("'")
        if key and val and key not in os.environ:
            os.environ[key] = val
_load_dotenv()

# ── httpx/openai compatibility patch (openai 1.55 + httpx 0.28) ────────────────
try:
    import httpx as _httpx
    _orig_client_init = _httpx.Client.__init__
    def _patched_client_init(self, *args, **kwargs):
        kwargs.pop("proxies", None)
        _orig_client_init(self, *args, **kwargs)
    _httpx.Client.__init__ = _patched_client_init

    _orig_async_init = _httpx.AsyncClient.__init__
    def _patched_async_init(self, *args, **kwargs):
        kwargs.pop("proxies", None)
        _orig_async_init(self, *args, **kwargs)
    _httpx.AsyncClient.__init__ = _patched_async_init
except Exception:
    pass

# ── SQLite Database Layer ────────────────────────────────────────────────────
import sys as _sys_db
_sys_db.path.insert(0, str(Path(__file__).resolve().parent))
try:
    from app.database import init_db
    from app.config import DB_PATH
    from app import models as _db
    init_db(DB_PATH)
    _SQLITE_OK = True
except Exception as _db_err:
    _SQLITE_OK = False

# ── Paths ───────────────────────────────────────────────────────────────────────
OUTPUT_DIR           = Path("./telegram_intel")
MESSAGES_FILE        = OUTPUT_DIR / "messages.jsonl"
KEYWORDS_FILE        = OUTPUT_DIR / "keywords.json"
DISCOVERY_FILE       = OUTPUT_DIR / "discovered_channels.json"
PENDING_FILE         = OUTPUT_DIR / "pending_channels.json"
ENRICHED_FILE        = OUTPUT_DIR / "enriched_alerts.jsonl"
BRIEF_FILE           = OUTPUT_DIR / "ai_brief.json"
AGENT_STATE_FILE     = OUTPUT_DIR / "ai_agent_state.json"
AGENT_LOG            = OUTPUT_DIR / "ai_agent.log"
DISCOVERY_TERMS_FILE = OUTPUT_DIR / "discovery_search_terms.json"
HUNTING_LEADS_FILE   = OUTPUT_DIR / "hunting_leads.json"
ESCALATION_FILE      = OUTPUT_DIR / "escalation_status.json"
ESCALATION_HIST_FILE = OUTPUT_DIR / "escalation_history.jsonl"
NETWORK_FILE         = OUTPUT_DIR / "channel_network.json"
OUTPUT_DIR.mkdir(exist_ok=True)

# ── Logging ────────────────────────────────────────────────────────────────────
import sys as _sys
_file_handler   = logging.FileHandler(AGENT_LOG, encoding="utf-8")
_stream_handler = logging.StreamHandler(_sys.stdout)
# Prevent UnicodeEncodeError on Windows when logging Arabic/non-ASCII characters
try:
    if hasattr(_sys.stdout, "reconfigure"):
        _sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [AI] %(message)s",
    handlers=[_file_handler, _stream_handler],
)
log = logging.getLogger("AI")

# ── State (which messages/channels already processed) ──────────────────────────
_state_lock = threading.Lock()

def _load_state():
    if AGENT_STATE_FILE.exists():
        try:
            return json.loads(AGENT_STATE_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {
        "enriched_ids": [],          # message IDs already enriched
        "vetted_channels": [],       # channels already vetted
        "last_kw_run": None,         # ISO timestamp of last keyword-learn run
        "last_brief_run": None,      # ISO timestamp of last brief run
        "last_hunt_run": None,       # ISO timestamp of last threat hunter run (LOOP 5)
        "last_escalation_run": None, # ISO timestamp of last escalation check (LOOP 6)
        "last_network_run": None,    # ISO timestamp of last network graph run (LOOP 7)
        "keywords_added": 0,
        "channels_autoapproved": 0,
        "channels_autodismissed": 0,
        "enrichments_done": 0,
        "briefs_generated": 0,
        "hunt_leads_found": 0,
        "escalation_alerts": 0,
    }

def _save_state(state):
    with _state_lock:
        AGENT_STATE_FILE.write_text(
            json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")

# ── OpenAI ─────────────────────────────────────────────────────────────────────
def _client():
    key = os.environ.get("OPENAI_API_KEY", "")
    if not key:
        raise RuntimeError("OPENAI_API_KEY not set")
    return OpenAI(api_key=key)

def _chat(messages_payload, model="gpt-4o-mini", max_tokens=800, json_mode=True):
    """Single OpenAI call with error handling. Returns parsed dict or None."""
    try:
        kwargs = dict(
            model=model,
            messages=messages_payload,
            temperature=0.2,
            max_tokens=max_tokens,
        )
        if json_mode:
            kwargs["response_format"] = {"type": "json_object"}
        r = _client().chat.completions.create(**kwargs)
        raw = r.choices[0].message.content
        return json.loads(raw) if json_mode else raw
    except Exception as e:
        log.warning(f"OpenAI call failed: {e}")
        return None


# ── File helpers ───────────────────────────────────────────────────────────────
def _load_keywords():
    if _SQLITE_OK:
        try:
            return _db.get_keywords()
        except Exception:
            pass
    if not KEYWORDS_FILE.exists():
        return {"critical": [], "medium": []}
    try:
        return json.loads(KEYWORDS_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {"critical": [], "medium": []}

def _save_keywords(kw):
    if _SQLITE_OK:
        try:
            _db.save_keywords(kw)
        except Exception:
            pass
    # Also write JSON file for backward compat
    KEYWORDS_FILE.write_text(
        json.dumps(kw, indent=2, ensure_ascii=False), encoding="utf-8")

def _load_messages(hours=2):
    """Load messages from last N hours — uses SQLite indexed query."""
    if _SQLITE_OK:
        try:
            rows = _db.get_messages_since(hours)
            # Convert SQLite rows to match JSONL format
            msgs = []
            for r in rows:
                if r.get("raw_json"):
                    try:
                        m = json.loads(r["raw_json"])
                        if r.get("critical_subtype"):
                            m["critical_subtype"] = r["critical_subtype"]
                        msgs.append(m)
                        continue
                    except Exception:
                        pass
                msgs.append(dict(r))
            return msgs
        except Exception:
            pass
    # Fallback to JSONL scan
    if not MESSAGES_FILE.exists():
        return []
    cutoff = (datetime.now(timezone.utc) - timedelta(hours=hours)).isoformat()
    msgs = []
    try:
        with open(MESSAGES_FILE, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    m = json.loads(line)
                    if m.get("timestamp_utc", "") >= cutoff:
                        msgs.append(m)
                except Exception:
                    pass
    except Exception:
        pass
    return msgs

def _load_discovery():
    if _SQLITE_OK:
        try:
            return _db.get_discovered_channels()
        except Exception:
            pass
    if not DISCOVERY_FILE.exists():
        return {}
    try:
        return json.loads(DISCOVERY_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {}

def _save_discovery(data):
    if _SQLITE_OK:
        try:
            for username, info in data.items():
                if isinstance(info, dict):
                    _db.upsert_discovered_channel(username, **info)
        except Exception:
            pass
    # Also write JSON file for backward compat
    DISCOVERY_FILE.write_text(
        json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

def _append_enriched(record):
    # Write to JSONL file
    with open(ENRICHED_FILE, "a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")
    # Also write to SQLite
    if _SQLITE_OK:
        try:
            ch = record.get("channel_username", "")
            mid = record.get("message_id", 0)
            enrichment = record.get("ai_enrichment", {})
            if ch and mid:
                _db.upsert_enrichment(ch, mid, enrichment)
        except Exception:
            pass

def _queue_for_monitoring(username):
    """Add a channel to the monitor's pending file."""
    try:
        data = {}
        if PENDING_FILE.exists():
            try:
                data = json.loads(PENDING_FILE.read_text(encoding="utf-8"))
            except Exception:
                pass
        pl = data.get("pending", [])
        pr = data.get("processed", [])
        if username not in pl and username not in pr:
            pl.append(username)
            data["pending"] = pl
            data["updated_at"] = datetime.now(timezone.utc).isoformat()
            PENDING_FILE.write_text(
                json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
    except Exception as e:
        log.warning(f"Queue error for @{username}: {e}")


# ══════════════════════════════════════════════════════════════════════════════
# LOOP 1: CRITICAL MESSAGE ENRICHMENT
# ══════════════════════════════════════════════════════════════════════════════

ENRICH_SYSTEM = """You are a cyber threat intelligence analyst for Jordan's Cyber Crimes Unit.
You receive a CRITICAL alert from a hacktivist Telegram channel and must provide rapid analysis.

Respond ONLY with valid JSON:
{
  "group_attribution": "Best guess at threat actor group name (or 'Unknown')",
  "attack_type": "DDoS | Defacement | DataLeak | Ransomware | Recon | Coordination | Other",
  "target_sector": "Government | Banking | Telecom | Military | Energy | Education | Media | Other",
  "severity": "LOW | MEDIUM | HIGH | CRITICAL",
  "confidence": 0-100,
  "summary": "1-2 sentence plain English analysis of what this message means",
  "recommended_action": "Notify X team | Monitor closely | Block IOC | Escalate to NCSC | None",
  "ioc_context": "Brief note on any IPs/domains/hashes in the message, or empty string"
}

Be concise. If unsure, say so in confidence score. Focus on actionable intel for defenders."""

def _enrich_one(msg, state):
    """Enrich a single CRITICAL message with AI analysis."""
    msg_id  = str(msg.get("message_id", ""))
    ch      = msg.get("channel_username", "unknown")
    text    = msg.get("text_preview", "")[:600]
    kw_hits = msg.get("keyword_hits", [])
    iocs    = msg.get("iocs", {})
    ts      = msg.get("timestamp_utc", "")[:16]

    user_content = (
        f"Channel: @{ch}\nTimestamp: {ts}\n"
        f"Keyword hits: {', '.join(kw_hits[:10])}\n"
        f"IOCs found: {json.dumps(iocs, ensure_ascii=False) if iocs else 'none'}\n"
        f"Message text:\n{text}"
    )

    result = _chat([
        {"role": "system", "content": ENRICH_SYSTEM},
        {"role": "user",   "content": user_content},
    ], max_tokens=400)

    if not result:
        return

    enriched = {
        **msg,
        "ai_enrichment": {
            **result,
            "enriched_at": datetime.now(timezone.utc).isoformat(),
            "model": "gpt-4o-mini",
        }
    }
    _append_enriched(enriched)

    state["enriched_ids"].append(msg_id)
    state["enrichments_done"] = state.get("enrichments_done", 0) + 1
    _save_state(state)

    log.info(
        f"[ENRICH] @{ch}: {result.get('attack_type','?')} / "
        f"{result.get('target_sector','?')} | {result.get('group_attribution','?')} | "
        f"action: {result.get('recommended_action','none')}"
    )


def loop_enrich_critical(state):
    """
    LOOP 1: Watch for new CRITICAL messages and enrich them.
    Polls messages.jsonl every 30 seconds.
    """
    log.info("[LOOP1] Critical enrichment loop started")
    while True:
        try:
            msgs = _load_messages(hours=48)  # Look back 48h to catch anything new
            already = set(state.get("enriched_ids", []))
            to_enrich = [
                m for m in msgs
                if (
                    m.get("priority") == "CRITICAL"
                    or (m.get("priority") == "MEDIUM" and len(m.get("keyword_hits", [])) >= 2)
                )
                and str(m.get("message_id", "")) not in already
            ]
            if to_enrich:
                log.info(f"[LOOP1] {len(to_enrich)} new CRITICAL/high-MEDIUM messages to enrich")
                for msg in to_enrich[:10]:  # Max 10 per cycle to control API spend
                    _enrich_one(msg, state)
                    time.sleep(1)  # Rate limit
        except Exception as e:
            log.error(f"[LOOP1] Error: {e}")
        time.sleep(30)


# ══════════════════════════════════════════════════════════════════════════════
# LOOP 2: KEYWORD AUTO-LEARNING
# ══════════════════════════════════════════════════════════════════════════════

KW_SYSTEM = """You are a cyber threat intelligence keyword analyst for Jordan's Cyber Crimes Unit.
You monitor hacktivist Telegram channels targeting Jordan and Arab countries.

Analyze the messages below and identify NEW keywords/phrases that should be added to detection lists.
Focus on:
- New Arabic/Farsi attack terms NOT in the current list
- New Jordanian government/bank/infrastructure targets being named
- New hacktivist group names or operation codenames
- New malware/tool names being used
- New target domains/IPs that appear significant

Only suggest keywords that:
1. Actually appeared in the messages
2. Are NOT already in the current keyword list
3. Are genuinely relevant to detecting attacks on Jordan

CRITICAL = directly signals Jordan being targeted
MEDIUM = attack tools/methods/groups/regional context

Respond ONLY with valid JSON:
{
  "new_critical_keywords": [
    {"keyword": "...", "reason": "...", "confidence": 0-100}
  ],
  "new_medium_keywords": [
    {"keyword": "...", "reason": "...", "confidence": 0-100}
  ],
  "analysis_note": "brief summary of what you observed in this message set"
}"""

HUNT_TERMS_SYSTEM = """You are extracting intelligence leads from Telegram hacktivist messages monitoring Jordan threats.
Be AGGRESSIVE — extract EVERYTHING that could lead to finding new threat channels.

Extract:
1. Telegram channel/group USERNAMES (@X, t.me/X, or any handle mentioned)
2. ALL hacktivist GROUP NAMES (even minor ones, even if well-known — we need their handles)
3. OPERATION NAMES (Op X, #OpJordan, عملية codenames, campaign hashtags)
4. TOOL/MALWARE names (DDoS tools, RATs, exploit kits — their channels often exist on Telegram)
5. PERSON handles/aliases (group leaders, hackers mentioned by name)
6. Arabic/Persian/Urdu group names (transliterate + original script)
7. Hashtags used for coordination (#OpJordan, #FreePalestine, #CyberJihad etc.)

Generate search terms that would find these channels on Telegram Search.
Include BOTH English and Arabic/Persian variants of each term.

Respond ONLY valid JSON:
{
  "new_channel_leads": [
    {"username": "exact_handle_or_null", "name": "display_name",
     "confidence": 0-100, "reason": "why relevant to Jordan threat landscape"}
  ],
  "new_search_terms": [
    {"term": "telegram_search_term", "language": "ar|en|fa", "confidence": 0-100}
  ]
}
Include items with confidence >= 50. username must be the raw @handle without @.
Generate at LEAST 5 search terms per call. Think about what a hacktivist would search for."""


def _load_discovery_terms():
    if not DISCOVERY_TERMS_FILE.exists():
        return {"terms": [], "channel_leads": []}
    try:
        return json.loads(DISCOVERY_TERMS_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {"terms": [], "channel_leads": []}


def _extract_discovery_entities(msgs, lines):
    """
    LOOP 2 second pass: extract group names, op names, channel leads from messages.
    Writes to discovery_search_terms.json. High-confidence channel leads auto-added
    to discovered_channels.json for LOOP 3 vetting.
    """
    try:
        result = _chat([
            {"role": "system", "content": HUNT_TERMS_SYSTEM},
            {"role": "user",   "content": "\n".join(lines[:150])},
        ], max_tokens=800)
        if not result:
            return

        data = _load_discovery_terms()
        existing_terms = {t["term"].lower() for t in data.get("terms", [])}
        existing_leads = {c.get("username", "").lower() for c in data.get("channel_leads", [])}
        now = datetime.now(timezone.utc).isoformat()
        added_terms, added_leads = 0, 0

        for item in result.get("new_search_terms", []):
            term = str(item.get("term", "")).strip()
            conf = int(item.get("confidence", 0))
            if term and conf >= 50 and term.lower() not in existing_terms:
                data.setdefault("terms", []).append({
                    "term": term,
                    "added_at": now,
                    "confidence": conf,
                    "source": "loop2",
                    "language": item.get("language", "en"),
                })
                existing_terms.add(term.lower())
                added_terms += 1

        for item in result.get("new_channel_leads", []):
            uname = str(item.get("username") or "").strip().lstrip("@")
            name  = str(item.get("name", "")).strip()
            conf  = int(item.get("confidence", 0))
            if conf < 50:
                continue
            key = uname.lower() if uname else name.lower()
            if key and key not in existing_leads:
                data.setdefault("channel_leads", []).append({
                    "username": uname or None,
                    "name": name,
                    "added_at": now,
                    "confidence": conf,
                    "reason": item.get("reason", ""),
                    "source": "loop2",
                })
                existing_leads.add(key)
                added_leads += 1

                # Auto-add channel leads to discovery pipeline
                if uname and conf >= 60:
                    disc = _load_discovery()
                    if uname not in disc:
                        disc[uname] = {
                            "username": uname,
                            "status": "pending_review",
                            "score": conf,
                            "reason": f"loop2_entity_extract: {item.get('reason','')}",
                            "discovered_at": now,
                            "source": "loop2",
                        }
                        _save_discovery(disc)
                        log.info(f"[LOOP2-ENT] Auto-queued channel @{uname} "
                                 f"(conf={conf}%) for vetting")

        DISCOVERY_TERMS_FILE.write_text(
            json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")
        if added_terms or added_leads:
            log.info(f"[LOOP2-ENT] discovery_search_terms.json: "
                     f"+{added_terms} search terms, +{added_leads} channel leads")
    except Exception as e:
        log.warning(f"[LOOP2-ENT] Entity extraction failed: {e}")


def loop_keyword_learning(state):
    """
    LOOP 2: Every 2 hours, analyze recent messages and auto-add keywords.
    Auto-applies keywords with confidence >= 80 without manual review.
    """
    log.info("[LOOP2] Keyword learning loop started")
    INTERVAL = 7200  # 2 hours

    while True:
        # Check if it's time to run
        last = state.get("last_kw_run")
        if last:
            elapsed = (datetime.now(timezone.utc) -
                       datetime.fromisoformat(last)).total_seconds()
            if elapsed < INTERVAL:
                time.sleep(60)
                continue

        try:
            msgs = _load_messages(hours=6)
            if len(msgs) < 5:
                log.info("[LOOP2] Not enough new messages (<5) — skipping keyword learning")
                state["last_kw_run"] = datetime.now(timezone.utc).isoformat()
                _save_state(state)
                time.sleep(60)
                continue

            kw = _load_keywords()
            existing_set = set(
                k.lower() for k in kw.get("critical", []) + kw.get("medium", [])
            )

            # Build compact message digest — all priorities, sorted critical first
            msgs_sorted = sorted(msgs, key=lambda x: {"CRITICAL":0,"MEDIUM":1,"LOW":2}.get(x.get("priority","LOW"),2))
            lines = []
            for m in msgs_sorted[:200]:  # Up to 200 messages across all priorities
                ch   = m.get("channel_username", "?")
                text = m.get("text_preview", "")[:250]
                p    = m.get("priority", "LOW")
                lines.append(f"[@{ch}|{p}] {text}")

            kw_sample_crit = kw.get("critical", [])[:40]
            kw_sample_med  = kw.get("medium",   [])[:30]
            current_summary = (
                f"CURRENT CRITICAL (sample of {len(kw.get('critical',[]))}): "
                f"{', '.join(kw_sample_crit)}\n"
                f"CURRENT MEDIUM (sample of {len(kw.get('medium',[]))}): "
                f"{', '.join(kw_sample_med)}"
            )

            user_content = (
                f"{current_summary}\n\n"
                f"MESSAGES FROM LAST 2H ({len(lines)} total):\n"
                + "\n".join(lines)
            )

            log.info(f"[LOOP2] Keyword learning: analyzing {len(msgs)} messages...")
            result = _chat([
                {"role": "system", "content": KW_SYSTEM},
                {"role": "user",   "content": user_content},
            ], max_tokens=1000)

            if not result:
                state["last_kw_run"] = datetime.now(timezone.utc).isoformat()
                _save_state(state)
                time.sleep(60)
                continue

            note = result.get("analysis_note", "")
            added_crit, added_med = 0, 0

            for entry in result.get("new_critical_keywords", []):
                kw_str = str(entry.get("keyword", "")).strip()
                conf   = int(entry.get("confidence", 0))
                if kw_str and conf >= 80 and kw_str.lower() not in existing_set:
                    kw["critical"].append(kw_str)
                    existing_set.add(kw_str.lower())
                    added_crit += 1
                    log.info(f"[LOOP2] AUTO-ADD critical: '{kw_str}' "
                             f"(conf={conf}%): {entry.get('reason','')}")

            for entry in result.get("new_medium_keywords", []):
                kw_str = str(entry.get("keyword", "")).strip()
                conf   = int(entry.get("confidence", 0))
                if kw_str and conf >= 80 and kw_str.lower() not in existing_set:
                    kw["medium"].append(kw_str)
                    existing_set.add(kw_str.lower())
                    added_med += 1
                    log.info(f"[LOOP2] AUTO-ADD medium: '{kw_str}' "
                             f"(conf={conf}%): {entry.get('reason','')}")

            if added_crit or added_med:
                _save_keywords(kw)
                log.info(f"[LOOP2] keywords.json updated: "
                         f"+{added_crit} critical, +{added_med} medium "
                         f"(total: {len(kw['critical'])} critical, {len(kw['medium'])} medium)")
                state["keywords_added"] = state.get("keywords_added", 0) + added_crit + added_med
            else:
                log.info(f"[LOOP2] No new keywords (conf >= 80%) found. Note: {note}")

            # Second pass: extract entity names → discovery_search_terms.json
            _extract_discovery_entities(msgs, lines)

            state["last_kw_run"] = datetime.now(timezone.utc).isoformat()
            _save_state(state)

        except Exception as e:
            log.error(f"[LOOP2] Error: {e}")

        time.sleep(60)


# ══════════════════════════════════════════════════════════════════════════════
# LOOP 3: CHANNEL AUTO-VETTING
# ══════════════════════════════════════════════════════════════════════════════

VET_SYSTEM = """You are vetting a candidate Telegram channel for a Jordan cyber threat monitoring system.
You will receive the channel username, discovery reason, channel metadata (if available),
and a sample of its messages from our database.

Decide: should this channel be APPROVED for active monitoring, or DISMISSED as irrelevant?

You MUST be DECISIVE. Do NOT use UNCERTAIN unless the channel name is truly random characters
with zero cyber/hacktivist/political indicators. When in doubt, lean toward APPROVE — it is
better to monitor a borderline channel than miss a real threat.

APPROVE if ANY of these apply:
- Channel name contains hack, cyber, attack, ddos, anon, leak, breach, deface, exploit, or similar
- Channel discusses attacks on Arab/Middle Eastern targets
- IOC sharing, DDoS coordination, data leaks, malware, or defacement proof
- Iranian, Palestinian, or Islamic resistance context
- The channel was discovered via forwarded messages from a known threat channel
- The discovery reason includes "forwarded_from" or "mentioned_in_message" from a monitored channel
- Channel has "team", "army", "force", "crew", "squad" combined with cyber/hack terms

DISMISS ONLY if:
- Clearly a regular news aggregator with no hacktivist content
- Personal blog, food, sports, entertainment
- Scam/fraud channel (not hacktivist)
- Completely empty with a generic non-cyber name

Respond ONLY with valid JSON:
{
  "decision": "APPROVE" | "DISMISS" | "UNCERTAIN",
  "confidence": 0-100,
  "reason": "1 sentence explaining decision",
  "threat_actor_guess": "group name or 'Unknown hacktivist' or 'Not a threat actor'",
  "priority_tier": 1 | 2 | 3,
  "suggested_threat_level": "CRITICAL" | "HIGH" | "MEDIUM" | "LOW"
}

Be aggressive with APPROVE — confidence 50+ is sufficient for channels with ANY cyber indicators."""

def _get_channel_messages_from_db(username, limit=15):
    """Get recent messages from our DB for a specific channel."""
    msgs = []
    if not MESSAGES_FILE.exists():
        return msgs
    try:
        with open(MESSAGES_FILE, encoding="utf-8") as f:
            for line in f:
                line = line.strip()
                if not line:
                    continue
                try:
                    m = json.loads(line)
                    if m.get("channel_username", "").lower() == username.lower():
                        msgs.append(m)
                        if len(msgs) >= limit:
                            break
                except Exception:
                    pass
    except Exception:
        pass
    return msgs[-limit:]


def loop_channel_vetting(state):
    """
    LOOP 3: Every 5 minutes, check for new unvetted discovered channels and auto-vet them.
    """
    log.info("[LOOP3] Channel vetting loop started")
    while True:
        try:
            disc = _load_discovery()
            vetted = set(state.get("vetted_channels", []))
            pending_vet = [
                (uname, info) for uname, info in disc.items()
                if uname not in vetted and info.get("status") == "pending_review"
            ]

            for uname, info in pending_vet:
                try:
                    # Auto-dismiss scam-flagged channels without using a GPT call
                    meta = info.get("metadata", {})
                    if meta.get("scam"):
                        disc = _load_discovery()
                        disc[uname]["status"]          = "dismissed"
                        disc[uname]["ai_vet_decision"] = "DISMISS"
                        disc[uname]["ai_vet_reason"]   = "Auto-dismissed: Telegram scam flag set"
                        disc[uname]["ai_confidence"]   = 99
                        _save_discovery(disc)
                        vetted.add(uname)
                        state["channels_autodismissed"] = state.get("channels_autodismissed", 0) + 1
                        state["vetted_channels"] = list(vetted)
                        _save_state(state)
                        log.info(f"[LOOP3] AUTO-DISMISSED @{uname} — Telegram scam flag")
                        continue

                    # Build metadata context string
                    meta_lines = []
                    if meta.get("about"):
                        meta_lines.append(f"Description: {meta['about'][:300]}")
                    if meta.get("participants_count"):
                        meta_lines.append(f"Subscribers: {meta['participants_count']:,}")
                    meta_str = "\n".join(meta_lines) if meta_lines else "No metadata available"

                    # Get messages from DB for this channel
                    db_msgs = _get_channel_messages_from_db(uname, limit=15)

                    if db_msgs:
                        # Build message sample
                        samples = "\n".join(
                            f"[{m.get('priority','?')}] {m.get('text_preview','')[:200]}"
                            for m in db_msgs[-10:]
                        )
                        user_content = (
                            f"Channel: @{uname}\n"
                            f"Discovery reason: {info.get('reason','?')}\n"
                            f"Discovery score: {info.get('score', 0)}\n"
                            f"{meta_str}\n"
                            f"Sample messages from DB ({len(db_msgs)}):\n{samples}"
                        )
                        approve_threshold = 50  # Lowered from 70 — be more aggressive
                    else:
                        # No messages in DB — vet on channel name + reason + metadata
                        user_content = (
                            f"Channel: @{uname}\n"
                            f"Discovery reason: {info.get('reason','?')}\n"
                            f"Discovery score: {info.get('score', 0)}\n"
                            f"{meta_str}\n"
                            f"No messages yet. Judge by the channel username, description, and discovery reason.\n"
                            f"APPROVE if the name contains ANY cyber/hack/attack/resistance indicators.\n"
                            f"APPROVE if discovered via forwarded_from or mentioned_in a known threat channel.\n"
                            f"Only DISMISS if clearly non-cyber (news, personal, food, sports, entertainment).\n"
                            f"Do NOT use UNCERTAIN — force a decision. APPROVE or DISMISS only."
                        )
                        approve_threshold = 40  # Lowered from 55 — name alone is enough

                    result = _chat([
                        {"role": "system", "content": VET_SYSTEM},
                        {"role": "user",   "content": user_content},
                    ], max_tokens=300)

                    if not result:
                        vetted.add(uname)
                        continue

                    decision = result.get("decision", "UNCERTAIN")
                    confidence = int(result.get("confidence", 0))
                    reason = result.get("reason", "")

                    # Reload discovery to avoid race condition
                    disc = _load_discovery()

                    if decision == "APPROVE" and confidence >= approve_threshold:
                        disc[uname]["status"]          = "approved"
                        disc[uname]["ai_vet_decision"] = decision
                        disc[uname]["ai_vet_reason"]   = reason
                        disc[uname]["ai_confidence"]   = confidence
                        disc[uname]["ai_threat_level"] = result.get("suggested_threat_level","MEDIUM")
                        disc[uname]["ai_tier"]         = result.get("priority_tier", 3)
                        disc[uname]["auto_added"]      = True
                        _save_discovery(disc)
                        _queue_for_monitoring(uname)
                        state["channels_autoapproved"] = state.get("channels_autoapproved", 0) + 1
                        log.info(f"[LOOP3] AUTO-APPROVED @{uname} "
                                 f"(conf={confidence}%): {reason}")

                    elif decision == "DISMISS":
                        disc[uname]["status"]          = "dismissed"
                        disc[uname]["ai_vet_decision"] = decision
                        disc[uname]["ai_vet_reason"]   = reason
                        disc[uname]["ai_confidence"]   = confidence
                        _save_discovery(disc)
                        state["channels_autodismissed"] = state.get("channels_autodismissed", 0) + 1
                        log.info(f"[LOOP3] AUTO-DISMISSED @{uname} "
                                 f"(conf={confidence}%): {reason}")

                    else:  # UNCERTAIN
                        disc[uname]["ai_vet_decision"] = "UNCERTAIN"
                        disc[uname]["ai_vet_reason"]   = reason
                        disc[uname]["ai_confidence"]   = confidence
                        _save_discovery(disc)
                        log.info(f"[LOOP3] UNCERTAIN @{uname} — left for human review")

                    vetted.add(uname)
                    state["vetted_channels"] = list(vetted)
                    _save_state(state)
                    time.sleep(2)  # Rate limit

                except Exception as e:
                    log.warning(f"[LOOP3] Error vetting @{uname}: {e}")
                    vetted.add(uname)

        except Exception as e:
            log.error(f"[LOOP3] Error: {e}")

        time.sleep(300)  # Check every 5 minutes


# ══════════════════════════════════════════════════════════════════════════════
# LOOP 4: THREAT BRIEF GENERATION
# ══════════════════════════════════════════════════════════════════════════════

BRIEF_SYSTEM = """You are a senior cyber threat intelligence analyst for Jordan's Cyber Crimes Unit.
Generate a structured threat intelligence brief based on recent Telegram channel activity.

Respond ONLY with valid JSON:
{
  "brief_period": "time period covered",
  "overall_threat_level": "LOW | MEDIUM | HIGH | CRITICAL",
  "executive_summary": "2-3 sentence non-technical summary for leadership",
  "active_threat_actors": [
    {"name": "...", "activity_level": "high|medium|low", "recent_actions": "..."}
  ],
  "targeted_sectors": [
    {"sector": "...", "threat_level": "...", "evidence": "..."}
  ],
  "key_iocs": ["ip or domain"],
  "attack_patterns": "observed TTP patterns in 2-3 sentences",
  "escalation_signals": ["any indicators of planned or imminent escalation"],
  "recommended_actions": ["action 1", "action 2", "action 3"],
  "confidence": 0-100
}"""

def loop_threat_brief(state):
    """
    LOOP 4: Every 6 hours generate a structured threat intelligence brief.
    """
    log.info("[LOOP4] Threat brief loop started")
    INTERVAL = 21600  # 6 hours

    while True:
        last = state.get("last_brief_run")
        if last:
            elapsed = (datetime.now(timezone.utc) -
                       datetime.fromisoformat(last)).total_seconds()
            if elapsed < INTERVAL:
                time.sleep(300)
                continue

        try:
            msgs = _load_messages(hours=24)  # Full 24h window — all priorities
            if len(msgs) < 10:
                log.info("[LOOP4] Not enough messages (<10) for meaningful brief")
                state["last_brief_run"] = datetime.now(timezone.utc).isoformat()
                _save_state(state)
                time.sleep(300)
                continue

            # Summarize by channel — include ALL priority levels for full picture
            ch_stats = defaultdict(lambda: {"total": 0, "critical": 0, "medium": 0, "low": 0, "texts": []})
            all_iocs = []
            for m in msgs:
                ch = m.get("channel_username", "unknown")
                p  = m.get("priority", "LOW")
                ch_stats[ch]["total"] += 1
                if p == "CRITICAL":
                    ch_stats[ch]["critical"] += 1
                    ch_stats[ch]["texts"].append(f"[CRITICAL] {m.get('text_preview','')[:180]}")
                elif p == "MEDIUM":
                    ch_stats[ch]["medium"] += 1
                    if len(ch_stats[ch]["texts"]) < 5:  # Include up to 5 MEDIUM samples too
                        ch_stats[ch]["texts"].append(f"[MEDIUM] {m.get('text_preview','')[:150]}")
                else:
                    ch_stats[ch]["low"] += 1
                    if len(ch_stats[ch]["texts"]) < 3:  # Include up to 3 LOW samples
                        ch_stats[ch]["texts"].append(f"[LOW] {m.get('text_preview','')[:120]}")
                ioc = m.get("iocs", {})
                for v in ioc.values():
                    all_iocs.extend(v or [])

            # Build briefing input — sort by critical+medium activity
            ch_lines = []
            for ch, stats in sorted(ch_stats.items(),
                                    key=lambda x: x[1]["critical"]*3 + x[1]["medium"], reverse=True)[:20]:
                sample_texts = " | ".join(stats["texts"][:5])
                ch_lines.append(
                    f"@{ch}: {stats['total']} msgs total "
                    f"({stats['critical']} CRITICAL, {stats['medium']} MEDIUM, {stats['low']} LOW). "
                    f"Samples: {sample_texts[:400]}"
                )

            unique_iocs = list(set(all_iocs))[:30]
            now_str = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")

            user_content = (
                f"Period: last 24 hours ending {now_str}\n"
                f"Total messages analyzed: {len(msgs)} (ALL priorities)\n"
                f"Critical: {sum(1 for m in msgs if m.get('priority')=='CRITICAL')} | "
                f"Medium: {sum(1 for m in msgs if m.get('priority')=='MEDIUM')} | "
                f"Low: {sum(1 for m in msgs if m.get('priority')=='LOW')}\n"
                f"IOCs observed: {', '.join(unique_iocs) if unique_iocs else 'none'}\n\n"
                f"Channel activity (all priority levels):\n" + "\n".join(ch_lines)
            )

            log.info(f"[LOOP4] Generating threat brief for {len(msgs)} messages...")
            result = _chat([
                {"role": "system", "content": BRIEF_SYSTEM},
                {"role": "user",   "content": user_content},
            ], max_tokens=1200)

            if result:
                result["generated_at"] = datetime.now(timezone.utc).isoformat()
                result["messages_analyzed"] = len(msgs)
                BRIEF_FILE.write_text(
                    json.dumps(result, indent=2, ensure_ascii=False),
                    encoding="utf-8")
                state["briefs_generated"] = state.get("briefs_generated", 0) + 1
                log.info(
                    f"[LOOP4] Brief generated: "
                    f"threat={result.get('overall_threat_level','?')} | "
                    f"{result.get('executive_summary','')[:100]}..."
                )

            state["last_brief_run"] = datetime.now(timezone.utc).isoformat()
            _save_state(state)

        except Exception as e:
            log.error(f"[LOOP4] Error: {e}")

        time.sleep(300)


# ══════════════════════════════════════════════════════════════════════════════
# LOOP 5: PROACTIVE THREAT HUNTER
# ══════════════════════════════════════════════════════════════════════════════

HUNT_SYSTEM = """You are a cyber threat intelligence analyst hunting for hacktivist Telegram channels targeting Jordan.

Analyze these Telegram messages and identify ALL external groups/channels that are:
- Being praised, coordinated with, or allied with
- Mentioned as having attacked Jordan, Arab countries, or Israel
- Referenced by name in a threat/attack context

Respond ONLY valid JSON:
{
  "group_leads": [
    {
      "name": "group name",
      "username": "@username if visible or null",
      "evidence": "exact quote from messages",
      "relationship": "ally|competitor|mentioned",
      "confidence": 0-100,
      "reason_to_monitor": "why this matters for Jordan threat landscape"
    }
  ],
  "operation_leads": [
    {
      "name": "operation name",
      "search_term": "best Telegram search term for this operation",
      "evidence": "exact quote",
      "confidence": 0-100
    }
  ],
  "summary": "1 sentence: most significant new lead found"
}
Only include items with confidence >= 60."""


def loop_threat_hunter(state):
    """
    LOOP 5: Every 3 hours, read last 6h of messages and ask GPT to identify
    all external groups/channels being discussed — allies, competitors, targets.
    Writes leads to hunting_leads.json. High-confidence leads auto-queued for vetting.
    """
    log.info("[LOOP5] Proactive threat hunter loop started")
    INTERVAL = 10800  # 3 hours

    while True:
        last = state.get("last_hunt_run")
        if last:
            elapsed = (datetime.now(timezone.utc) -
                       datetime.fromisoformat(last)).total_seconds()
            if elapsed < INTERVAL:
                time.sleep(120)
                continue

        try:
            msgs = _load_messages(hours=6)
            if len(msgs) < 10:
                log.info("[LOOP5] Not enough messages (<10) — skipping hunt")
                state["last_hunt_run"] = datetime.now(timezone.utc).isoformat()
                _save_state(state)
                time.sleep(120)
                continue

            # Build digest of all messages for context
            lines = []
            for m in msgs[:300]:
                ch   = m.get("channel_username", "?")
                text = m.get("text_preview", "")[:300]
                p    = m.get("priority", "LOW")
                lines.append(f"[@{ch}|{p}] {text}")

            log.info(f"[LOOP5] Threat hunting: analyzing {len(msgs)} messages...")
            result = _chat([
                {"role": "system", "content": HUNT_SYSTEM},
                {"role": "user",   "content": "\n".join(lines)},
            ], max_tokens=1200)

            if not result:
                state["last_hunt_run"] = datetime.now(timezone.utc).isoformat()
                _save_state(state)
                time.sleep(120)
                continue

            now = datetime.now(timezone.utc).isoformat()

            # Load or create hunting leads file
            if HUNTING_LEADS_FILE.exists():
                try:
                    hl = json.loads(HUNTING_LEADS_FILE.read_text(encoding="utf-8"))
                except Exception:
                    hl = {"group_leads": [], "operation_leads": [], "runs": []}
            else:
                hl = {"group_leads": [], "operation_leads": [], "runs": []}

            existing_names = {g.get("name", "").lower() for g in hl.get("group_leads", [])}
            new_groups, new_ops = 0, 0

            for lead in result.get("group_leads", []):
                conf  = int(lead.get("confidence", 0))
                name  = str(lead.get("name", "")).strip()
                uname = str(lead.get("username") or "").strip().lstrip("@")
                if not name or conf < 50:
                    continue
                if name.lower() not in existing_names:
                    hl["group_leads"].append({**lead, "found_at": now, "source": "loop5"})
                    existing_names.add(name.lower())
                    new_groups += 1
                    # Auto-queue channel leads for vetting
                    if uname and conf >= 60:
                        disc = _load_discovery()
                        if uname not in disc:
                            disc[uname] = {
                                "username": uname,
                                "status": "pending_review",
                                "score": conf,
                                "reason": f"loop5_hunt: {lead.get('reason_to_monitor','')}",
                                "discovered_at": now,
                                "source": "loop5",
                            }
                            _save_discovery(disc)
                            log.info(f"[LOOP5] Auto-queued @{uname} (conf={conf}%) for vetting")

            existing_ops = {o.get("name", "").lower() for o in hl.get("operation_leads", [])}
            for op in result.get("operation_leads", []):
                conf = int(op.get("confidence", 0))
                name = str(op.get("name", "")).strip()
                if not name or conf < 60 or name.lower() in existing_ops:
                    continue
                hl["operation_leads"].append({**op, "found_at": now, "source": "loop5"})
                existing_ops.add(name.lower())
                new_ops += 1
                # Add to discovery search terms
                search_term = op.get("search_term", "").strip()
                if search_term:
                    dt = _load_discovery_terms()
                    existing_t = {t["term"].lower() for t in dt.get("terms", [])}
                    if search_term.lower() not in existing_t:
                        dt.setdefault("terms", []).append({
                            "term": search_term,
                            "added_at": now,
                            "confidence": conf,
                            "source": "loop5_op",
                            "language": "en",
                        })
                        DISCOVERY_TERMS_FILE.write_text(
                            json.dumps(dt, indent=2, ensure_ascii=False), encoding="utf-8")

            hl["runs"] = hl.get("runs", [])[-49:]  # Keep last 50 run summaries
            hl["runs"].append({
                "at": now,
                "msgs_analyzed": len(msgs),
                "new_groups": new_groups,
                "new_ops": new_ops,
                "summary": result.get("summary", ""),
            })
            HUNTING_LEADS_FILE.write_text(
                json.dumps(hl, indent=2, ensure_ascii=False), encoding="utf-8")

            state["hunt_leads_found"] = state.get("hunt_leads_found", 0) + new_groups
            state["last_hunt_run"] = now
            _save_state(state)
            log.info(f"[LOOP5] Hunt complete: +{new_groups} group leads, "
                     f"+{new_ops} op leads | {result.get('summary','')[:100]}")

        except Exception as e:
            log.error(f"[LOOP5] Error: {e}")

        time.sleep(120)


# ══════════════════════════════════════════════════════════════════════════════
# LOOP 6: ESCALATION SIGNAL DETECTOR
# ══════════════════════════════════════════════════════════════════════════════

ESCALATION_SYSTEM = """You are monitoring Telegram for IMMINENT cyberattack indicators against Jordan.

Detect ANY of:
1. COUNTDOWN: "in X hours/days", "tonight", "tomorrow", "قريباً", "الليلة", "غداً"
2. TARGET_PUB: specific Jordan URLs/IPs posted as attack targets
3. COORDINATION: "all teams", "attack now", "كل الفرق", "confirm", "ready"
4. TOOL_SHARE: download links for attack tools, DDoS APIs, webshells, ransomware
5. SUCCESS_CLAIM: "we have access", "server compromised", "we are inside", "تم اختراق"
6. MOBILIZATION: recruiting for operation, calling for DDoS volunteers

Respond ONLY valid JSON:
{
  "escalation_detected": true|false,
  "urgency": "CRITICAL"|"HIGH"|"MEDIUM"|"NONE",
  "signals": [
    {
      "type": "COUNTDOWN|TARGET_PUB|COORDINATION|TOOL_SHARE|SUCCESS_CLAIM|MOBILIZATION",
      "channel": "@channel",
      "evidence": "exact quote (max 200 chars)",
      "target": "specific target if mentioned or null",
      "timeframe": "timeframe if mentioned or null"
    }
  ],
  "summary": "1 sentence plain English",
  "recommended_action": "specific action for Jordan SOC"
}
If nothing detected, return urgency NONE with empty signals array."""


def loop_escalation_detector(state):
    """
    LOOP 6: Every 15 minutes, scan last 2 hours for imminent attack signals.
    Writes current state to escalation_status.json (overwritten each run).
    HIGH/CRITICAL events appended to escalation_history.jsonl.
    """
    log.info("[LOOP6] Escalation detector loop started")
    INTERVAL = 900  # 15 minutes

    while True:
        last = state.get("last_escalation_run")
        if last:
            elapsed = (datetime.now(timezone.utc) -
                       datetime.fromisoformat(last)).total_seconds()
            if elapsed < INTERVAL:
                time.sleep(30)
                continue

        try:
            msgs = _load_messages(hours=2)
            if len(msgs) < 3:
                # Write NONE status even with no messages
                status = {
                    "escalation_detected": False,
                    "urgency": "NONE",
                    "signals": [],
                    "summary": "Insufficient message volume for analysis",
                    "recommended_action": "",
                    "checked_at": datetime.now(timezone.utc).isoformat(),
                    "msgs_analyzed": len(msgs),
                }
                ESCALATION_FILE.write_text(
                    json.dumps(status, indent=2, ensure_ascii=False), encoding="utf-8")
                state["last_escalation_run"] = datetime.now(timezone.utc).isoformat()
                _save_state(state)
                time.sleep(30)
                continue

            # Focus on CRITICAL + MEDIUM messages for speed
            priority_msgs = [m for m in msgs if m.get("priority") in ("CRITICAL", "MEDIUM")]
            if not priority_msgs:
                priority_msgs = msgs[:50]

            lines = []
            for m in priority_msgs[:100]:
                ch   = m.get("channel_username", "?")
                text = m.get("text_preview", "")[:300]
                ts   = m.get("timestamp_utc", "")[:16]
                lines.append(f"[{ts}|@{ch}] {text}")

            result = _chat([
                {"role": "system", "content": ESCALATION_SYSTEM},
                {"role": "user",   "content": "\n".join(lines)},
            ], max_tokens=800)

            now = datetime.now(timezone.utc).isoformat()
            if not result:
                result = {
                    "escalation_detected": False,
                    "urgency": "NONE",
                    "signals": [],
                    "summary": "Analysis failed",
                    "recommended_action": "",
                }

            result["checked_at"] = now
            result["msgs_analyzed"] = len(priority_msgs)

            ESCALATION_FILE.write_text(
                json.dumps(result, indent=2, ensure_ascii=False), encoding="utf-8")

            urgency = result.get("urgency", "NONE")
            if urgency in ("HIGH", "CRITICAL"):
                with open(ESCALATION_HIST_FILE, "a", encoding="utf-8") as f:
                    f.write(json.dumps(result, ensure_ascii=False) + "\n")
                state["escalation_alerts"] = state.get("escalation_alerts", 0) + 1
                log.warning(
                    f"[LOOP6] ⚠ ESCALATION {urgency}: {result.get('summary','')[:120]} | "
                    f"Action: {result.get('recommended_action','')}"
                )
            else:
                log.info(f"[LOOP6] Escalation check: {urgency} — {result.get('summary','')[:80]}")

            state["last_escalation_run"] = now
            _save_state(state)

        except Exception as e:
            log.error(f"[LOOP6] Error: {e}")

        time.sleep(30)


# ══════════════════════════════════════════════════════════════════════════════
# LOOP 7: NETWORK GRAPH BUILDER
# ══════════════════════════════════════════════════════════════════════════════

def loop_network_graph(state):
    """
    LOOP 7: Every hour, build a channel relationship graph from @mentions and
    forwarded-from metadata. Scores unknown channels by weighted in-degree from
    monitored channels. Writes channel_network.json. No GPT calls.
    """
    import re as _re
    log.info("[LOOP7] Network graph builder loop started")
    INTERVAL = 3600  # 1 hour
    TIER_WEIGHT = {"tier1": 3, "tier2": 2, "tier3": 1, "unknown": 1}

    while True:
        last = state.get("last_network_run")
        if last:
            elapsed = (datetime.now(timezone.utc) -
                       datetime.fromisoformat(last)).total_seconds()
            if elapsed < INTERVAL:
                time.sleep(120)
                continue

        try:
            msgs = _load_messages(hours=168)  # 7-day window
            if len(msgs) < 20:
                state["last_network_run"] = datetime.now(timezone.utc).isoformat()
                _save_state(state)
                time.sleep(120)
                continue

            disc = _load_discovery()
            monitored = {u for u, info in disc.items()
                         if info.get("status") in ("approved", "active")}

            # Build edge graph: src_channel → {referenced_channel: count}
            edges = defaultdict(lambda: defaultdict(int))

            for m in msgs:
                src = m.get("channel_username", "")
                if not src:
                    continue
                text = m.get("text_preview", "")

                # Extract @mentions
                mentions = _re.findall(r'@([A-Za-z0-9_]{4,32})', text)
                for mention in mentions:
                    if mention.lower() != src.lower():
                        edges[src.lower()][mention.lower()] += 1

                # Extract t.me/ links
                tme_links = _re.findall(r't\.me/([A-Za-z0-9_]{4,32})', text)
                for link in tme_links:
                    if link.lower() != src.lower():
                        edges[src.lower()][link.lower()] += 1

                # Forwarded-from metadata (weight=3)
                fwd = m.get("forwarded_from", "")
                if fwd and isinstance(fwd, str) and fwd.lower() != src.lower():
                    edges[src.lower()][fwd.lower()] += 3

            # Score unknown channels by weighted in-degree from monitored channels
            unknown_scores = defaultdict(float)
            for src, targets in edges.items():
                # Weight by tier of the source channel
                src_info = disc.get(src, {})
                tier_str = f"tier{src_info.get('ai_tier', 3)}" if src in disc else "unknown"
                weight = TIER_WEIGHT.get(tier_str, 1)
                # Only edges FROM monitored channels matter for discovery
                if src in monitored or src in {u.lower() for u in monitored}:
                    for tgt, count in targets.items():
                        if tgt not in monitored and tgt not in {u.lower() for u in monitored}:
                            unknown_scores[tgt] += count * weight

            # Channels with graph_score >= 5 → auto-queue for vetting
            now = datetime.now(timezone.utc).isoformat()
            newly_queued = 0
            for uname, score in sorted(unknown_scores.items(), key=lambda x: -x[1]):
                if score >= 5 and uname not in disc:
                    disc[uname] = {
                        "username": uname,
                        "status": "pending_review",
                        "score": min(int(score * 5), 95),
                        "reason": f"network_graph: score={score:.1f} (weighted in-degree from monitored channels)",
                        "discovered_at": now,
                        "source": "loop7",
                        "graph_score": round(score, 2),
                    }
                    newly_queued += 1

            if newly_queued:
                _save_discovery(disc)

            # Build full adjacency graph for visualization (top 200 nodes)
            top_edges = []
            for src, targets in edges.items():
                for tgt, count in targets.items():
                    top_edges.append({"src": src, "tgt": tgt, "weight": count})
            top_edges.sort(key=lambda x: -x["weight"])

            graph_data = {
                "generated_at": now,
                "msgs_analyzed": len(msgs),
                "monitored_channels": len(monitored),
                "unknown_channels_scored": len(unknown_scores),
                "newly_queued": newly_queued,
                "top_unknown": [
                    {"username": u, "graph_score": round(s, 2)}
                    for u, s in sorted(unknown_scores.items(), key=lambda x: -x[1])[:50]
                ],
                "edges": top_edges[:500],  # Top 500 edges for visualization
            }
            NETWORK_FILE.write_text(
                json.dumps(graph_data, indent=2, ensure_ascii=False), encoding="utf-8")

            state["last_network_run"] = now
            _save_state(state)
            log.info(f"[LOOP7] Network graph: {len(unknown_scores)} unknown channels scored, "
                     f"{newly_queued} newly queued for vetting "
                     f"(score>=5 threshold, {len(msgs)} msgs)")

        except Exception as e:
            log.error(f"[LOOP7] Error: {e}")

        time.sleep(120)


# ══════════════════════════════════════════════════════════════════════════════
# LOOP 8: PROACTIVE SEARCH TERM EXPANSION
# ══════════════════════════════════════════════════════════════════════════════

TERM_EXPAND_SYSTEM = """You are a cyber threat intelligence analyst expanding search terms for a Telegram
monitoring platform focused on hacktivist threats against Jordan and the Middle East.

You will receive:
1. Currently monitored channels and their threat groups
2. Currently known search terms
3. Recent intelligence context

Your job: generate NEW search terms and channel leads that we're NOT already searching for.
Think like an OSINT analyst — what would you search to find:
- Backup/alt channels of known groups (groups often get banned and recreate)
- Affiliated groups and alliances
- Tool/malware distribution channels
- Coordination/planning channels
- Regional hacktivist groups that might pivot to Jordan targeting
- Arabic, Persian, Urdu, Turkish, Malay, Indonesian terms
- Leetspeak and creative spelling variations (3 for e, 0 for o, etc.)
- Channels using coded language to avoid detection

Respond ONLY valid JSON:
{
  "new_search_terms": [
    {"term": "search term", "language": "ar|en|fa|tr|id|ur", "confidence": 50-100,
     "rationale": "why this term would find threat channels"}
  ],
  "new_channel_leads": [
    {"username": "handle_without_at", "name": "group name",
     "confidence": 50-100, "reason": "why we should monitor this"}
  ],
  "expansion_notes": "brief summary of expansion strategy used"
}
Generate at LEAST 10 new search terms and 3 channel leads per call.
Focus on terms we're NOT already searching. Be creative with spelling variations."""


def loop_search_term_expansion(state):
    """
    LOOP 8: Every 4 hours, proactively expand search terms using AI.
    Analyzes current channel config + known terms to find gaps in coverage.
    """
    log.info("[LOOP8] Search term expansion loop started")
    INTERVAL = 14400  # 4 hours

    while True:
        last = state.get("last_term_expand_run")
        if last:
            elapsed = (datetime.now(timezone.utc) -
                       datetime.fromisoformat(last)).total_seconds()
            if elapsed < INTERVAL:
                time.sleep(120)
                continue

        try:
            # Build context: current channels + current search terms
            channels_file = OUTPUT_DIR / "channels_config.json"
            if channels_file.exists():
                try:
                    cfg = json.loads(channels_file.read_text(encoding="utf-8"))
                except Exception:
                    cfg = {}
            else:
                cfg = {}

            channel_summary = []
            for uname, info in cfg.items():
                label = info.get("label", uname)
                tier = info.get("tier", "?")
                threat = info.get("threat", "?")
                status = info.get("status", "active")
                channel_summary.append(f"@{uname} | T{tier} {threat} | {label} | {status}")

            # Current search terms
            dt = _load_discovery_terms()
            current_terms = [t["term"] for t in dt.get("terms", [])]
            current_leads = [c.get("username", "") for c in dt.get("channel_leads", []) if c.get("username")]

            # Get recent messages for context
            msgs = _load_messages(hours=24)
            msg_channels = set()
            msg_groups_mentioned = set()
            for m in msgs[:200]:
                ch = m.get("channel_username", "")
                if ch:
                    msg_channels.add(ch)
                text = m.get("text_preview", "")
                # Extract @mentions and t.me links
                for mention in re.findall(r'@([a-zA-Z]\w{3,})', text):
                    msg_groups_mentioned.add(mention)
                for link in re.findall(r't\.me/([a-zA-Z]\w{3,})', text):
                    msg_groups_mentioned.add(link)

            user_content = (
                f"CURRENTLY MONITORED ({len(cfg)} channels):\n"
                + "\n".join(channel_summary[:80]) + "\n\n"
                f"CURRENT SEARCH TERMS ({len(current_terms)}):\n"
                + ", ".join(current_terms[:60]) + "\n\n"
                f"CURRENT CHANNEL LEADS ({len(current_leads)}):\n"
                + ", ".join(current_leads[:30]) + "\n\n"
                f"RECENTLY ACTIVE CHANNELS: {', '.join(list(msg_channels)[:30])}\n"
                f"GROUPS MENTIONED IN MESSAGES: {', '.join(list(msg_groups_mentioned)[:30])}\n\n"
                "Generate NEW search terms and channel leads that would help us find "
                "ADDITIONAL hacktivist channels we're NOT already monitoring. "
                "Focus on: backup channels of banned groups, affiliated groups, "
                "regional groups that target Jordan/Middle East, "
                "and Arabic/Persian/Turkish/Indonesian variations of known terms."
            )

            log.info(f"[LOOP8] Expanding search terms (analyzing {len(cfg)} channels, "
                     f"{len(current_terms)} existing terms)...")
            result = _chat([
                {"role": "system", "content": TERM_EXPAND_SYSTEM},
                {"role": "user",   "content": user_content},
            ], max_tokens=1500)

            if not result:
                state["last_term_expand_run"] = datetime.now(timezone.utc).isoformat()
                _save_state(state)
                time.sleep(120)
                continue

            now = datetime.now(timezone.utc).isoformat()
            data = _load_discovery_terms()
            existing_terms = {t["term"].lower() for t in data.get("terms", [])}
            existing_leads = {c.get("username", "").lower() for c in data.get("channel_leads", [])}
            added_terms, added_leads = 0, 0

            for item in result.get("new_search_terms", []):
                term = str(item.get("term", "")).strip()
                conf = int(item.get("confidence", 0))
                if term and conf >= 50 and term.lower() not in existing_terms:
                    data.setdefault("terms", []).append({
                        "term": term,
                        "added_at": now,
                        "confidence": conf,
                        "source": "loop8_expand",
                        "language": item.get("language", "en"),
                        "rationale": item.get("rationale", ""),
                    })
                    existing_terms.add(term.lower())
                    added_terms += 1

            for item in result.get("new_channel_leads", []):
                uname = str(item.get("username") or "").strip().lstrip("@")
                name  = str(item.get("name", "")).strip()
                conf  = int(item.get("confidence", 0))
                if conf < 50:
                    continue
                key = uname.lower() if uname else name.lower()
                if key and key not in existing_leads:
                    data.setdefault("channel_leads", []).append({
                        "username": uname or None,
                        "name": name,
                        "added_at": now,
                        "confidence": conf,
                        "reason": item.get("reason", ""),
                        "source": "loop8_expand",
                    })
                    existing_leads.add(key)
                    added_leads += 1

                    # Auto-add to discovery pipeline
                    if uname and conf >= 60:
                        disc = _load_discovery()
                        if uname.lower() not in disc:
                            disc[uname.lower()] = {
                                "username": uname,
                                "status": "pending_review",
                                "score": conf,
                                "reason": f"loop8_expand: {item.get('reason', '')}",
                                "discovered_at": now,
                                "source": "loop8",
                            }
                            _save_discovery(disc)
                            log.info(f"[LOOP8] Auto-queued @{uname} (conf={conf}%) for vetting")

            DISCOVERY_TERMS_FILE.write_text(
                json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8")

            notes = result.get("expansion_notes", "")
            state["last_term_expand_run"] = now
            state["terms_expanded"] = state.get("terms_expanded", 0) + added_terms
            _save_state(state)
            log.info(f"[LOOP8] Search term expansion: +{added_terms} terms, "
                     f"+{added_leads} channel leads | {notes[:100]}")

        except Exception as e:
            log.error(f"[LOOP8] Error: {e}")

        time.sleep(120)



# ══════════════════════════════════════════════════════════════════════════════

def main():
    state = _load_state()
    log.info("=" * 60)
    log.info("AI INTELLIGENCE AGENT — STARTING (8 loops)")
    log.info(f"State: {state.get('enrichments_done',0)} enrichments, "
             f"{state.get('keywords_added',0)} keywords added, "
             f"{state.get('channels_autoapproved',0)} channels approved, "
             f"{state.get('hunt_leads_found',0)} hunt leads, "
             f"{state.get('escalation_alerts',0)} escalation alerts, "
             f"{state.get('terms_expanded',0)} terms expanded")
    log.info("=" * 60)

    threads = [
        threading.Thread(target=loop_enrich_critical,       args=(state,), name="L1-Enrich",     daemon=True),
        threading.Thread(target=loop_keyword_learning,      args=(state,), name="L2-Keywords",    daemon=True),
        threading.Thread(target=loop_channel_vetting,       args=(state,), name="L3-Vetting",     daemon=True),
        threading.Thread(target=loop_threat_brief,          args=(state,), name="L4-Brief",       daemon=True),
        threading.Thread(target=loop_threat_hunter,         args=(state,), name="L5-Hunter",      daemon=True),
        threading.Thread(target=loop_escalation_detector,   args=(state,), name="L6-Escalation",  daemon=True),
        threading.Thread(target=loop_network_graph,         args=(state,), name="L7-Network",     daemon=True),
        threading.Thread(target=loop_search_term_expansion, args=(state,), name="L8-TermExpand",  daemon=True),
    ]

    for t in threads:
        t.start()
        log.info(f"Started thread: {t.name}")

    log.info("\nAll 8 loops running. Press Ctrl+C to stop.\n")
    try:
        while True:
            time.sleep(60)
            # Periodic heartbeat
            log.info(
                f"[HEARTBEAT] enrichments={state.get('enrichments_done',0)} | "
                f"kw_added={state.get('keywords_added',0)} | "
                f"ch_approved={state.get('channels_autoapproved',0)} | "
                f"ch_dismissed={state.get('channels_autodismissed',0)} | "
                f"briefs={state.get('briefs_generated',0)} | "
                f"hunt_leads={state.get('hunt_leads_found',0)} | "
                f"escalation_alerts={state.get('escalation_alerts',0)} | "
                f"terms_expanded={state.get('terms_expanded',0)}"
            )
    except KeyboardInterrupt:
        log.info("Shutting down AI agent...")
        _save_state(state)


if __name__ == "__main__":
    main()
