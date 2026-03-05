#!/usr/bin/env python3
"""
Scanwave CyberIntel Platform - Full Dashboard Viewer
====================================================
Usage: python viewer.py
Then open http://localhost:5000
"""

import os
import re
import csv
import json
import time
import asyncio
import threading
import subprocess
from concurrent.futures import ThreadPoolExecutor, as_completed
from io import StringIO, BytesIO
from pathlib import Path
from datetime import datetime, timezone, timedelta
from collections import defaultdict
from flask import Flask, jsonify, request, Response

try:
    from telethon.sync import TelegramClient as TGSync
    TELETHON_OK = True
except ImportError:
    TELETHON_OK = False

app = Flask(__name__)

OUTPUT_DIR     = Path("./telegram_intel")
SESSION        = str(Path("./jordan_cyber_intel"))
API_ID         = int(os.environ.get("TG_API_ID",   "35545979"))
API_HASH       = os.environ.get("TG_API_HASH", "41240e3f451065a430692d2e1bc82453")
WATCHLIST_FILE = OUTPUT_DIR / "active_watchlist.json"

# Channel tier metadata for sidebar display and briefing context
CHANNEL_TIERS = {
    # TIER 1 — Directly targeting Jordan
    "hak993":               {"tier": 1, "label": "Fatemiyoun Cyber Team", "threat": "CRITICAL"},
    "hak994":               {"tier": 1, "label": "Fatemiyoun Cyber Team", "threat": "CRITICAL"},
    "Fatimion310_bot":      {"tier": 1, "label": "Fatemiyoun Bot",        "threat": "CRITICAL"},
    "fatimion110":          {"tier": 1, "label": "Fatemiyoun Community",  "threat": "CRITICAL"},
    "hkr313":               {"tier": 1, "label": "Fatemiyoun Field Team", "threat": "CRITICAL"},
    "xX313XxTeam":          {"tier": 1, "label": "313 Team (Iraqi Cyber Resistance)", "threat": "CRITICAL"},
    "Team313Official":      {"tier": 1, "label": "313 Team Official",     "threat": "CRITICAL"},
    "x313xTeamLeak":        {"tier": 1, "label": "313 Team Leaks",        "threat": "CRITICAL"},
    "x313xTeamBackup":      {"tier": 1, "label": "313 Team Backup",       "threat": "CRITICAL"},
    # TIER 2 — Iran-aligned ecosystem
    "Mhwear98":             {"tier": 2, "label": "Cyber Islamic Resistance", "threat": "HIGH",   "status": "banned"},
    "Mhwercyber4":          {"tier": 2, "label": "Cyber Islamic Resistance", "threat": "HIGH",   "status": "banned"},
    "mhwear0":              {"tier": 2, "label": "Cyber Islamic Resistance (active handle)", "threat": "HIGH"},
    "fattahh_ir":           {"tier": 2, "label": "Cyber Fattah Team",     "threat": "HIGH",   "status": "banned"},
    "Handala_hack":         {"tier": 2, "label": "Handala (MOIS/Void Manticore)", "threat": "HIGH", "status": "banned"},
    "handala_hack26":       {"tier": 2, "label": "Handala Backup",        "threat": "HIGH",   "status": "banned"},
    "handal_a":             {"tier": 2, "label": "Handala (Active 2025)", "threat": "HIGH"},
    "Handala_hack_iranian": {"tier": 2, "label": "Handala Iranian",       "threat": "HIGH"},
    "Handala_Hack_Team":    {"tier": 2, "label": "Handala Team",          "threat": "HIGH"},
    "blackopmrhamza":       {"tier": 2, "label": "Mr Hamza",              "threat": "HIGH",   "status": "banned"},
    "RipperSec":            {"tier": 2, "label": "RipperSec (Malaysia)",  "threat": "HIGH",   "status": "banned"},
    "TheRipperSec":         {"tier": 2, "label": "RipperSec Main",        "threat": "HIGH",   "status": "banned"},
    "AnonGhostOfficialTeam":{"tier": 2, "label": "AnonGhost",             "threat": "HIGH",   "status": "banned"},
    "sylhetgangsgofficial": {"tier": 2, "label": "Sylhet Gang SG",        "threat": "HIGH",   "status": "banned"},
    "KeymousTeam":          {"tier": 2, "label": "Keymous+",              "threat": "HIGH"},
    "KMPteam":              {"tier": 2, "label": "Keymous+ (Alt)",        "threat": "HIGH",   "status": "banned"},
    "Keymous_V2":           {"tier": 2, "label": "Keymous+ Backup",       "threat": "HIGH",   "status": "banned"},
    "islamic_hacker_army1": {"tier": 2, "label": "Islamic Hacker Army",   "threat": "HIGH"},
    # TIER 3 — Broader ecosystem
    "noname05716eng":       {"tier": 3, "label": "NoName057(16) EN",      "threat": "MEDIUM", "status": "banned"},
    "noname05716":          {"tier": 3, "label": "NoName057(16) RU",      "threat": "MEDIUM", "status": "banned"},
    "dienet3":              {"tier": 3, "label": "DieNet (DDoS-as-a-service)", "threat": "MEDIUM"},
    "dnnmabot":             {"tier": 3, "label": "DieNet Attack Notifier Bot", "threat": "MEDIUM"},
    "LulzSecBlack":         {"tier": 3, "label": "LulzSec Black (PIJ)",   "threat": "MEDIUM"},
    "LulzSecHackers":       {"tier": 3, "label": "LulzSec Hackers",       "threat": "MEDIUM"},
    "Luls_sec_muslims":     {"tier": 3, "label": "LulzSec Muslims",       "threat": "MEDIUM"},
    "ElamAlmoqawama":       {"tier": 3, "label": "Islamic Resistance Iraq","threat": "MEDIUM"},
    "toufan_alaksa":        {"tier": 3, "label": "Al Aqsa Resistance Axis","threat": "MEDIUM"},
    "Chat_Islamic_Hacker_Army": {"tier": 3, "label": "IHA Discussion",    "threat": "MEDIUM"},
    "Khamenei_arabi":       {"tier": 3, "label": "Khamenei Arabic",       "threat": "LOW"},
    "operationswordofjustice": {"tier": 2, "label": "Operation Sword of Justice", "threat": "HIGH"},
    "Anonymous0islamic":    {"tier": 3, "label": "Anonymous Islamic",     "threat": "MEDIUM"},
    "handala24":            {"tier": 2, "label": "Handala (Active 2024+)","threat": "HIGH"},
    "tttteam313":           {"tier": 2, "label": "313 Team (Affiliated)", "threat": "HIGH"},
    "SabrenNewss":          {"tier": 2, "label": "Sabren News",           "threat": "HIGH"},
    # ── VERIFIED ADDITIONS (2026-03-03, cross-referenced TGStat/telemetr.io) ───
    # Dark Storm Team — DDoS/defacement US/EU/ME infrastructure
    "DarkStormTeams":       {"tier": 2, "label": "Dark Storm Team",        "threat": "HIGH"},
    "DarkStormBackup":      {"tier": 2, "label": "Dark Storm Team (Backup)", "threat": "HIGH"},
    "darkstormchat":        {"tier": 2, "label": "Dark Storm Team (Chat)", "threat": "HIGH"},
    # Arabian Ghosts — pro-Palestine Gulf hacktivist
    "arabian_ghosts":       {"tier": 2, "label": "Arabian Ghosts",         "threat": "HIGH"},
    # APT Iran — IRGC cyber readiness, threat tracking
    "aptiran":              {"tier": 2, "label": "APT Iran",               "threat": "HIGH"},
    # Golden Falcon — pro-Palestine DDoS/defacement
    "Golden_falcon_team":   {"tier": 2, "label": "Golden Falcon",          "threat": "HIGH"},
    # Stucx Team — active defacement, multiple verified handles
    "stucxteam":            {"tier": 2, "label": "Stucx Team",             "threat": "HIGH"},
    "stucxnet":             {"tier": 2, "label": "Stucx Net",              "threat": "HIGH"},
    "xxstucxteam":          {"tier": 2, "label": "Stucx Team (Alt)",       "threat": "HIGH"},
    # Hand of Justice — affiliated with Cyber Isnaad Front
    "the_hand_of_justice":  {"tier": 2, "label": "Hand of Justice",        "threat": "HIGH"},
    # Cyber Isnaad Front — Iranian-aligned Syrian hacktivist
    "CyberIsnaadFront":     {"tier": 2, "label": "Cyber Isnaad Front",     "threat": "HIGH"},
    # Cyb3rDrag0nz / CyberDrag0nzz — defacement coalition
    "TeamCyb3rDrag0nz":     {"tier": 2, "label": "CyberDrag0nzz",         "threat": "HIGH"},
    "cyb3r_drag0nz_team":   {"tier": 2, "label": "CyberDrag0nzz (Alt)",   "threat": "HIGH"},
    # Hacktivist of Garuda / Garuda Eye — Indonesian hacktivist
    "HacktivistOfGaruda":   {"tier": 3, "label": "Garuda Eye (Indonesia)", "threat": "MEDIUM"},
    "HacktivistOfGarudaOfficial": {"tier": 3, "label": "Garuda Eye (Official)", "threat": "MEDIUM"},
    # Nation of Saviours — active pro-Palestine
    "nation_of_saviors_public": {"tier": 3, "label": "Nation of Saviours", "threat": "MEDIUM"},
    # EvilNet 3.0 — data exfiltration, defacement
    "EvilNet3":             {"tier": 3, "label": "EvilNet 3.0",            "threat": "MEDIUM"},
    # Gaza Children's Group — Gaza-based hacktivist
    "Gaza_Children_Hackers": {"tier": 2, "label": "Gaza Children's Group", "threat": "HIGH"},
    "gaza_children_ha":     {"tier": 2, "label": "Gaza Children (Backup)", "threat": "HIGH"},
    # Indohaxsec — Indonesian hacktivist, Arctic Wolf-reported
    "INDOHAXSEC":           {"tier": 3, "label": "Indohaxsec",             "threat": "MEDIUM"},
    # Altoufan Team — resistance cyber ops
    "ALTOUFANTEAM":         {"tier": 2, "label": "Altoufan Team",          "threat": "HIGH"},
    # Team Azrael (Angel of Death) — resistance-axis
    "anonymous_cr02x":      {"tier": 2, "label": "Team Azrael (Angel of Death)", "threat": "HIGH"},
    "teamAzraelbackup":     {"tier": 2, "label": "Team Azrael (Backup)",   "threat": "HIGH"},
    # BD Anonymous / The Anonymous BD — Bangladesh
    "anonymous_bangladesh": {"tier": 3, "label": "BD Anonymous",           "threat": "MEDIUM"},
    "t_gray_hacker":        {"tier": 3, "label": "The Anonymous BD",       "threat": "MEDIUM"},
    # Moroccan Black Cyber Army — note: zero not O
    "M0roccan_Black_CyberArmy": {"tier": 3, "label": "Moroccan Black Cyber Army", "threat": "MEDIUM"},
    "moroccan_blackcyberarmy": {"tier": 3, "label": "MBCA (Alt)",          "threat": "MEDIUM"},
    # Akatsuki Cyber Team — pro-Palestine, pro-Iran ops
    "akatsukicyberteam":    {"tier": 3, "label": "Akatsuki Cyber Team",    "threat": "MEDIUM"},
    # FAD Team — CONFIRMED Ministry of Finance breach, real channel @r3_6j
    "r3_6j":                {"tier": 1, "label": "FAD Team (Min. of Finance breach)", "threat": "CRITICAL"},
    # Cyber Av3ngers — IRGC-affiliated, ICS/OT attacks on water/energy
    "CyberAv3ngers":        {"tier": 2, "label": "Cyber Av3ngers (IRGC)",  "threat": "HIGH"},
    "cyberaveng3rs":        {"tier": 2, "label": "Cyber Av3ngers (Alt)",   "threat": "HIGH"},
    # Iran Anonymous / Anonymous OpIran
    "anonopiran":           {"tier": 3, "label": "Anonymous OpIran",       "threat": "MEDIUM"},
    # Liwaa Mohammad (Mohamed Brigade) — Lebanese resistance cyber unit
    "liwaamohammad":        {"tier": 2, "label": "Liwaa Mohammad (Lebanese Resistance)", "threat": "HIGH"},
    # Tharallah Brigade — uses mhwear* namespace
    "mhwear10":             {"tier": 2, "label": "Tharallah Brigade",      "threat": "HIGH"},
    # Cyber32
    "Cyber32":              {"tier": 3, "label": "Cyber32",                "threat": "MEDIUM"},
    # DieNet extended channels
    "DieNetAPI":            {"tier": 3, "label": "DieNet API Info",        "threat": "MEDIUM"},
    "dienet_media":         {"tier": 3, "label": "DieNet Media Corp",      "threat": "MEDIUM"},
}

# Scan process state
_scan = {"running": False, "last_run": None, "pid": None}

# ── In-memory cache for performance ──────────────────────────────────────────
_msg_cache = {"data": None, "mtime": 0}

# ── AI enrichment cache ────────────────────────────────────────────────────────
_enrich_cache = {"data": None, "mtime": 0}

def load_enrichments():
    """Load AI-enriched alerts, keyed by channel_username+message_id."""
    f = OUTPUT_DIR / "enriched_alerts.jsonl"
    if not f.exists():
        return {}
    try:
        mtime = f.stat().st_mtime
        if _enrich_cache["data"] is not None and _enrich_cache["mtime"] == mtime:
            return _enrich_cache["data"]
        out = {}
        with open(f, "r", encoding="utf-8") as fh:
            for line in fh:
                line = line.strip()
                if not line:
                    continue
                try:
                    m = json.loads(line)
                    key = f"{m.get('channel_username','')}_{m.get('message_id','')}"
                    out[key] = m.get("ai_enrichment", {})
                except Exception:
                    pass
        _enrich_cache["data"]  = out
        _enrich_cache["mtime"] = mtime
        return out
    except Exception:
        return {}

def load_messages():
    """Load messages from JSONL, de-duplicate, with mtime cache."""
    f = OUTPUT_DIR / "messages.jsonl"
    if not f.exists():
        return []
    mtime = f.stat().st_mtime
    if _msg_cache["data"] is not None and _msg_cache["mtime"] == mtime:
        return _msg_cache["data"]
    msgs, seen = [], set()
    with open(f, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                m = json.loads(line)
                key = f"{m.get('channel_username','')}_{m.get('message_id','')}"
                if key not in seen:
                    seen.add(key)
                    msgs.append(m)
            except Exception:
                pass
    _msg_cache["data"]  = msgs
    _msg_cache["mtime"] = mtime
    return msgs


# Keywords for live-fetch scoring
_SCORE_CRIT = [
    "jordan","الاردن","الأردن","أردن","اردن",".jo",".gov.jo",
    "hacked","breached","defaced","leak","dump","wiper","destroy",
    "ddos","تسريب","تم اختراق","arab bank","البنك العربي",
    "bank of jordan","بنك الأردن","housing bank","بنك الإسكان",
    "ministry of interior","وزارة الداخلية","ministry of defense",
    "royal court","الديوان الملكي","prime minister","رئاسة الوزراء",
    "jordan islamic bank","البنك الإسلامي الأردني","jmis","jcbank",
]

def _score_text(text):
    tl = text.lower()
    hits = [k for k in _SCORE_CRIT if k in tl]
    if any(k in tl for k in ["jordan","الاردن","الأردن",".jo",".gov.jo"]):
        return "CRITICAL", hits
    if hits:
        return "MEDIUM", hits
    return "LOW", []


def fetch_live_context(channel_username, msg_id, before, after):
    """Pull real messages from Telegram by ID range, merge stored metadata."""
    if not TELETHON_OK:
        return None, -1
    try:
        try:
            asyncio.get_event_loop()
        except RuntimeError:
            asyncio.set_event_loop(asyncio.new_event_loop())
        with TGSync(SESSION, API_ID, API_HASH) as client:
            raw = list(client.iter_messages(
                channel_username,
                min_id=max(0, msg_id - before - 1),
                max_id=msg_id + after + 1,
                limit=before + after + 1,
            ))
        raw = sorted(raw, key=lambda m: m.id)
        stored_map = {}
        for m in load_messages():
            ch = m.get("channel_username") or m.get("channel", "")
            if ch == channel_username:
                stored_map[m.get("message_id")] = m
        result = []
        target_idx = -1
        for i, m in enumerate(raw):
            stored = stored_map.get(m.id, {})
            if m.id == msg_id:
                target_idx = i
            result.append({
                "message_id":       m.id,
                "channel_username": channel_username,
                "channel":          stored.get("channel", channel_username),
                "timestamp_utc":    m.date.isoformat() if m.date else "",
                "timestamp_irst":   stored.get("timestamp_irst", ""),
                "text_preview":     (m.text or ""),
                "priority":         stored.get("priority", "LOW"),
                "keyword_hits":     stored.get("keyword_hits", []),
                "iocs":             stored.get("iocs", {}),
                "has_media":        bool(m.media),
                "live":             True,
            })
        return result, target_idx
    except Exception:
        return None, -1


# ═══════════════════════════════════════════════════════════════════════════════
# API ROUTES
# ═══════════════════════════════════════════════════════════════════════════════

@app.route("/api/channels")
def api_channels():
    messages = load_messages()
    now      = datetime.now(timezone.utc)
    # 7-day sparkline buckets: index 0 = 6 days ago, index 6 = today
    def _spark_key(ts_str):
        try:
            dt = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
            delta = (now.date() - dt.date()).days
            if 0 <= delta < 7:
                return 6 - delta   # 0=6days_ago .. 6=today
        except Exception:
            pass
        return None

    stats = defaultdict(lambda: {
        "channel": "", "channel_username": "",
        "count": 0, "critical": 0, "medium": 0,
        "last_date": "", "last_critical_date": "",
        "spark_7d": [0, 0, 0, 0, 0, 0, 0],  # 7-day critical count per day
    })
    for m in messages:
        ch  = m.get("channel_username") or m.get("channel", "unknown")
        s   = stats[ch]
        s["channel"]          = m.get("channel", ch)
        s["channel_username"] = ch
        s["count"] += 1
        p  = m.get("priority", "LOW")
        ts = m.get("timestamp_utc", "")
        if p == "CRITICAL":
            s["critical"] += 1
            if ts > s["last_critical_date"]:
                s["last_critical_date"] = ts
            idx = _spark_key(ts)
            if idx is not None:
                s["spark_7d"][idx] += 1
        elif p == "MEDIUM":
            s["medium"] += 1
        if ts > s["last_date"]:
            s["last_date"] = ts
    # Enrich with tier metadata
    now = datetime.now(timezone.utc)
    for s in stats.values():
        ch = s["channel_username"]
        meta = CHANNEL_TIERS.get(ch, {})
        s["tier"]         = meta.get("tier", 0)
        s["tier_label"]   = meta.get("label", "")
        s["threat_level"] = meta.get("threat", "")
        s["status"]       = meta.get("status", "active")
        # Days since last post
        if s["last_date"]:
            try:
                ld = datetime.fromisoformat(s["last_date"].replace("Z", "+00:00"))
                if ld.tzinfo is None:
                    ld = ld.replace(tzinfo=timezone.utc)
                s["days_silent"] = max(0, (now - ld).days)
            except Exception:
                s["days_silent"] = -1
        else:
            s["days_silent"] = -1

    # Inject stubs for all CHANNEL_TIERS entries with no messages in DB
    # so analysts can see the full picture including banned and newly-added channels
    for username, meta in CHANNEL_TIERS.items():
        if username not in stats:
            stats[username] = {
                "channel": meta.get("label", username),
                "channel_username": username,
                "count": 0, "critical": 0, "medium": 0,
                "last_date": "", "last_critical_date": "",
                "tier": meta.get("tier", 0),
                "tier_label": meta.get("label", ""),
                "threat_level": meta.get("threat", ""),
                "status": meta.get("status", "active"),
                "days_silent": -1,
                "spark_7d": [0, 0, 0, 0, 0, 0, 0],
            }

    # Enrich status for all stats entries that aren't already enriched
    for s in stats.values():
        if "status" not in s:
            ch   = s["channel_username"]
            meta = CHANNEL_TIERS.get(ch, {})
            s["status"] = meta.get("status", "active")

    # Sort: active channels with criticals first, then by date DESC;
    # banned channels always go to the bottom of the list
    result = sorted(stats.values(),
        key=lambda x: (
            0 if x.get("status") == "banned" else 1,           # banned → bottom
            1 if x["last_critical_date"] else 0,               # has crit → higher
            x["last_critical_date"] or x["last_date"] or ""    # newest first
        ),
        reverse=True
    )
    return jsonify(result)


@app.route("/api/channel/<channel_username>/iocs")
def api_channel_iocs(channel_username):
    """Aggregated IOCs for a single channel - for per-channel IOC drill-down."""
    from collections import Counter
    messages = load_messages()
    agg = defaultdict(Counter)
    msg_count = 0
    for m in messages:
        ch = m.get("channel_username") or m.get("channel", "")
        if ch != channel_username:
            continue
        msg_count += 1
        for ioc_type, vals in (m.get("iocs") or {}).items():
            for v in (vals or []):
                agg[ioc_type][v] += 1
    result = []
    for ioc_type, counts in agg.items():
        for val, count in counts.most_common(50):
            result.append({"type": ioc_type, "value": val, "count": count})
    result.sort(key=lambda x: -x["count"])
    return jsonify({"channel": channel_username, "msg_count": msg_count, "iocs": result})


@app.route("/api/channel/<channel_username>/trend")
def api_channel_trend(channel_username):
    """Daily message counts for a single channel over last 30 days."""
    messages = load_messages()
    now  = datetime.now(timezone.utc)
    days = 30
    buckets = defaultdict(lambda: {"total": 0, "critical": 0, "medium": 0})
    for m in messages:
        ch = m.get("channel_username") or m.get("channel", "")
        if ch != channel_username:
            continue
        ts = m.get("timestamp_utc", "")
        if not ts:
            continue
        try:
            dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
            delta = (now - dt).days
            if 0 <= delta < days:
                day_key = dt.strftime("%Y-%m-%d")
                p = m.get("priority", "LOW")
                buckets[day_key]["total"] += 1
                if p == "CRITICAL":   buckets[day_key]["critical"] += 1
                elif p == "MEDIUM":   buckets[day_key]["medium"]   += 1
        except Exception:
            pass
    result = sorted(
        [{"date": k, **v} for k, v in buckets.items()],
        key=lambda x: x["date"]
    )
    return jsonify(result)


@app.route("/api/messages/<channel_username>")
def api_messages(channel_username):
    priority_filter  = request.args.get("priority", "ALL")
    subtype_filter   = request.args.get("critical_subtype", "ALL")
    since  = request.args.get("since", "")
    until  = request.args.get("until", "")
    search = request.args.get("search", "").lower()

    enrichments = load_enrichments()
    result = []
    for m in load_messages():
        ch = m.get("channel_username") or m.get("channel", "unknown")
        if ch != channel_username:
            continue
        if priority_filter != "ALL" and m.get("priority") != priority_filter:
            continue
        ts = m.get("timestamp_utc", "")
        if since and ts < since:
            continue
        if until and ts > until + " 99":
            continue
        if search:
            text = ((m.get("text_preview") or "") + " " +
                    " ".join(m.get("keyword_hits", []))).lower()
            if search not in text:
                continue
        # Attach AI enrichment if available
        key = f"{ch}_{m.get('message_id','')}"
        m = dict(m)
        if key in enrichments:
            m["ai_enrichment"] = enrichments[key]
        # Inject critical_subtype for backward compat (old messages won't have it)
        if m.get("priority") == "CRITICAL" and not m.get("critical_subtype"):
            m["critical_subtype"] = _compute_critical_subtype(m.get("keyword_hits", []))
        # Apply critical_subtype filter (only filters CRITICAL messages)
        if subtype_filter != "ALL" and m.get("priority") == "CRITICAL":
            ms = m.get("critical_subtype", "GENERAL")
            if ms != subtype_filter and ms != "BOTH":
                continue
        result.append(m)

    result.sort(key=lambda x: x.get("timestamp_utc", ""))
    return jsonify(result)


@app.route("/api/messages/all")
def api_messages_all():
    """Combined feed across all channels. Used by Dashboard and Timeline."""
    priority_filter = request.args.get("priority", "ALL")
    subtype_filter  = request.args.get("critical_subtype", "ALL")
    since   = request.args.get("since", "")
    until   = request.args.get("until", "")
    search  = request.args.get("search", "").lower()
    keyword = request.args.get("keyword", "").lower()
    channel = request.args.get("channel", "").lower()
    limit   = min(int(request.args.get("limit", 1000)), 5000)

    enrichments = load_enrichments()
    result = []
    for m in load_messages():
        p  = m.get("priority", "LOW")
        ts = m.get("timestamp_utc", "")
        ch = (m.get("channel_username") or m.get("channel", "")).lower()

        if priority_filter != "ALL" and p != priority_filter:
            continue
        if since  and ts < since:
            continue
        if until  and ts > until + " 99":
            continue
        if channel and channel not in ch:
            continue
        if search:
            haystack = ((m.get("text_preview") or "") + " " +
                        " ".join(m.get("keyword_hits", [])) + " " +
                        (m.get("channel", "") or "")).lower()
            if search not in haystack:
                continue
        if keyword:
            kws      = [k.lower() for k in m.get("keyword_hits", [])]
            txt_low  = (m.get("text_preview") or "").lower()
            if keyword not in kws and keyword not in txt_low:
                continue
        m = dict(m)
        # Inject critical_subtype for backward compat (old messages won't have it)
        if p == "CRITICAL" and not m.get("critical_subtype"):
            m["critical_subtype"] = _compute_critical_subtype(m.get("keyword_hits", []))
        # Attach AI enrichment if available
        ch_full = m.get("channel_username") or m.get("channel", "")
        key = f"{ch_full}_{m.get('message_id','')}"
        if key in enrichments:
            m["ai_enrichment"] = enrichments[key]
        # Apply critical_subtype filter (only filters CRITICAL messages)
        if subtype_filter != "ALL" and p == "CRITICAL":
            ms = m.get("critical_subtype", "GENERAL")
            if ms != subtype_filter and ms != "BOTH":
                continue
        result.append(m)

    result.sort(key=lambda x: x.get("timestamp_utc", ""), reverse=True)
    return jsonify(result[:limit])


@app.route("/api/dashboard")
def api_dashboard():
    """Aggregated intelligence for the Dashboard tab."""
    messages = load_messages()

    kw_crit  = defaultdict(int)
    kw_med   = defaultdict(int)
    kw_total = defaultdict(int)

    ioc_agg = defaultdict(lambda: defaultdict(lambda: {
        "count": 0, "channels": set(), "last_seen": ""
    }))

    # (weekday_abbr, hour_int) → count
    WEEKDAYS = ["Mon","Tue","Wed","Thu","Fri","Sat","Sun"]
    activity_matrix = {wd: {h: 0 for h in range(24)} for wd in WEEKDAYS}

    ch_last_critical = {}
    ch_msg_count     = defaultdict(int)
    total = len(messages)
    critical_count = medium_count = ioc_count = 0

    # Campaign detection: track per-keyword which channels post in same 6-hour window
    kw_windows = defaultdict(list)  # kw → list of (timestamp, channel)

    for m in messages:
        p  = m.get("priority", "LOW")
        ch = m.get("channel_username") or m.get("channel", "unknown")
        ts = m.get("timestamp_utc", "")
        ch_msg_count[ch] += 1

        if p == "CRITICAL":
            critical_count += 1
            if ts > ch_last_critical.get(ch, ""):
                ch_last_critical[ch] = ts
        elif p == "MEDIUM":
            medium_count += 1

        for kw in m.get("keyword_hits", []):
            kw_total[kw] += 1
            if p == "CRITICAL":
                kw_crit[kw]  += 1
                kw_windows[kw].append((ts, ch))
            elif p == "MEDIUM":
                kw_med[kw] += 1

        for ioc_type, vals in (m.get("iocs") or {}).items():
            for val in (vals or []):
                entry = ioc_agg[ioc_type][val]
                entry["count"] += 1
                entry["channels"].add(ch)
                if ts > entry["last_seen"]:
                    entry["last_seen"] = ts
                ioc_count += 1

        # Activity matrix
        irst_hour    = m.get("irst_hour")
        irst_weekday = m.get("irst_weekday", "")
        if irst_hour is not None and irst_weekday:
            wd_abbr = irst_weekday[:3]
            if wd_abbr in activity_matrix and 0 <= irst_hour < 24:
                activity_matrix[wd_abbr][irst_hour] += 1

    # Keywords sorted by weight
    keywords = []
    for kw in kw_total:
        weight = kw_crit.get(kw, 0) * 3 + kw_med.get(kw, 0)
        keywords.append({
            "keyword": kw,
            "total":   kw_total[kw],
            "critical": kw_crit.get(kw, 0),
            "medium":  kw_med.get(kw, 0),
            "weight":  weight,
        })
    keywords.sort(key=lambda x: -x["weight"])

    # IOC list
    iocs_out = []
    for ioc_type, vals in ioc_agg.items():
        for val, info in vals.items():
            iocs_out.append({
                "type":     ioc_type,
                "value":    val,
                "count":    info["count"],
                "channels": sorted(info["channels"]),
                "last_seen": info["last_seen"],
            })
    iocs_out.sort(key=lambda x: -x["count"])

    # Coordinated campaigns: keyword with 2+ distinct channels in 6-hour window
    campaigns = []
    for kw, events in kw_windows.items():
        if len(events) < 2:
            continue
        events_s = sorted(events, key=lambda e: e[0])
        i = 0
        while i < len(events_s):
            t0_str, ch0 = events_s[i]
            cluster_chs = {ch0}
            j = i + 1
            while j < len(events_s):
                tj_str, chj = events_s[j]
                if t0_str and tj_str and tj_str[:10] == t0_str[:10]:
                    cluster_chs.add(chj)
                    j += 1
                else:
                    break
            if len(cluster_chs) >= 2:
                campaigns.append({
                    "keyword":  kw,
                    "channels": sorted(cluster_chs),
                    "date":     t0_str[:10] if t0_str else "",
                    "count":    len(cluster_chs),
                })
            i = j if j > i else i + 1
    # Deduplicate campaigns by (keyword, date)
    seen_c = set()
    campaigns_dedup = []
    for c in sorted(campaigns, key=lambda x: (-x["count"], x["keyword"])):
        k = (c["keyword"], c["date"])
        if k not in seen_c:
            seen_c.add(k)
            campaigns_dedup.append(c)
    campaigns_dedup = campaigns_dedup[:30]

    # Channel ranking
    ch_ranking = sorted(
        [{"channel": ch, "count": cnt, "last_critical": ch_last_critical.get(ch, "")}
         for ch, cnt in ch_msg_count.items()],
        key=lambda x: -x["count"]
    )[:20]

    total_configured = len(CHANNEL_TIERS)
    banned_count     = sum(1 for v in CHANNEL_TIERS.values() if v.get("status") == "banned")
    return jsonify({
        "total":            total,
        "critical":         critical_count,
        "medium":           medium_count,
        "ioc_count":        ioc_count,
        "channel_count":    len(ch_msg_count),
        "total_configured": total_configured,
        "banned_count":     banned_count,
        "keywords":         keywords[:100],
        "iocs":             iocs_out[:500],
        "activity_matrix":  {wd: list(hours.values()) for wd, hours in activity_matrix.items()},
        "campaigns":        campaigns_dedup,
        "ch_ranking":       ch_ranking,
    })


@app.route("/api/trend")
def api_trend():
    """Daily message volume over past 60 days, broken down by priority."""
    messages  = load_messages()
    now       = datetime.now(timezone.utc)
    days      = int(request.args.get("days", 60))
    cutoff    = (now - timedelta(days=days)).isoformat()

    day_data = defaultdict(lambda: {"CRITICAL": 0, "MEDIUM": 0, "LOW": 0})
    for m in messages:
        ts = m.get("timestamp_utc", "")
        if ts < cutoff:
            continue
        day = ts[:10]
        p   = m.get("priority", "LOW")
        day_data[day][p] += 1

    # Fill every day in range
    result = []
    for i in range(days):
        day = (now - timedelta(days=days-1-i)).strftime("%Y-%m-%d")
        d   = day_data.get(day, {"CRITICAL": 0, "MEDIUM": 0, "LOW": 0})
        result.append({"date": day, **d})

    return jsonify(result)


@app.route("/api/briefing")
def api_briefing():
    """24-hour intelligence briefing for the analyst."""
    messages = load_messages()
    now = datetime.now(timezone.utc)
    cutoff_24h = (now - timedelta(hours=24)).isoformat()
    cutoff_7d  = (now - timedelta(days=7)).isoformat()

    recent   = [m for m in messages if m.get("timestamp_utc","") >= cutoff_24h]
    week     = [m for m in messages if m.get("timestamp_utc","") >= cutoff_7d]
    all_crit = [m for m in messages if m.get("priority") == "CRITICAL"]
    rec_crit = [m for m in recent  if m.get("priority") == "CRITICAL"]
    rec_med  = [m for m in recent  if m.get("priority") == "MEDIUM"]

    # Top targeted Jordan entities in last 24h
    entity_hits = defaultdict(int)
    for m in rec_crit:
        for kw in m.get("keyword_hits", []):
            entity_hits[kw] += 1
    top_entities = sorted(entity_hits.items(), key=lambda x: -x[1])[:15]

    # Active channels last 24h
    ch_24h = defaultdict(lambda: {"critical": 0, "medium": 0, "total": 0})
    for m in recent:
        ch = m.get("channel_username") or m.get("channel", "")
        ch_24h[ch]["total"] += 1
        p = m.get("priority","LOW")
        if p == "CRITICAL": ch_24h[ch]["critical"] += 1
        elif p == "MEDIUM": ch_24h[ch]["medium"] += 1
    active_channels = sorted(
        [{"channel": k, **v} for k, v in ch_24h.items()],
        key=lambda x: -x["critical"]
    )[:10]

    # Fresh IOCs in last 24h
    fresh_iocs = defaultdict(set)
    for m in recent:
        for ioc_type, vals in (m.get("iocs") or {}).items():
            for v in (vals or []):
                fresh_iocs[ioc_type].add(v)
    fresh_ioc_list = {k: sorted(v)[:20] for k, v in fresh_iocs.items()}

    # Trend: last 24h vs previous 24h
    cutoff_48h = (now - timedelta(hours=48)).isoformat()
    prev_24h_crit = sum(1 for m in messages
                        if cutoff_48h <= m.get("timestamp_utc","") < cutoff_24h
                        and m.get("priority") == "CRITICAL")
    trend = "ESCALATING" if len(rec_crit) > prev_24h_crit else \
            "DECREASING" if len(rec_crit) < prev_24h_crit else "STABLE"

    # Newest critical messages
    newest_crits = sorted(rec_crit, key=lambda x: x.get("timestamp_utc",""), reverse=True)[:10]

    return jsonify({
        "generated_at":    now.isoformat(),
        "period_hours":    24,
        "summary": {
            "total_messages_24h":    len(recent),
            "critical_alerts_24h":   len(rec_crit),
            "medium_alerts_24h":     len(rec_med),
            "active_channels_24h":   len(ch_24h),
            "fresh_ioc_count":       sum(len(v) for v in fresh_ioc_list.values()),
            "prev_24h_critical":     prev_24h_crit,
            "trend":                 trend,
            "total_all_time":        len(messages),
            "total_critical_all":    len(all_crit),
        },
        "top_targeted_entities": top_entities,
        "active_channels":       active_channels,
        "fresh_iocs":            fresh_ioc_list,
        "newest_critical":       newest_crits[:5],
        "weekly_critical":       len([m for m in week if m.get("priority")=="CRITICAL"]),
    })


@app.route("/api/messages/export")
def api_messages_export():
    """Download filtered messages as CSV."""
    priority_filter = request.args.get("priority", "CRITICAL")
    since = request.args.get("since", "")
    search = request.args.get("search", "").lower()

    rows = []
    for m in load_messages():
        p  = m.get("priority", "LOW")
        ts = m.get("timestamp_utc", "")
        if priority_filter != "ALL" and p != priority_filter:
            continue
        if since and ts < since:
            continue
        if search:
            haystack = ((m.get("text_preview") or "") + " " + " ".join(m.get("keyword_hits", []))).lower()
            if search not in haystack:
                continue
        rows.append(m)
    rows.sort(key=lambda x: x.get("timestamp_utc",""), reverse=True)

    buf = StringIO()
    w   = csv.writer(buf)
    w.writerow(["timestamp_utc","timestamp_irst","channel","channel_username",
                "priority","keyword_hits","text_preview","iocs"])
    for m in rows:
        ioc_str = "; ".join(f"{t}:{','.join(vs)}" for t, vs in (m.get("iocs") or {}).items())
        w.writerow([
            m.get("timestamp_utc",""), m.get("timestamp_irst",""),
            m.get("channel",""),       m.get("channel_username",""),
            m.get("priority",""),      "|".join(m.get("keyword_hits",[])),
            (m.get("text_preview") or "").replace("\n"," "),
            ioc_str
        ])
    fname = f"intel_{priority_filter.lower()}_{datetime.now().strftime('%Y%m%d_%H%M')}.csv"
    return Response(buf.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition": f"attachment;filename={fname}"})


@app.route("/api/iocs/export")
def api_iocs_export():
    """Download all IOCs as CSV."""
    messages = load_messages()
    ioc_agg  = defaultdict(lambda: defaultdict(lambda: {
        "count": 0, "channels": set(), "last_seen": ""
    }))
    for m in messages:
        ch = m.get("channel_username") or m.get("channel", "unknown")
        ts = m.get("timestamp_utc", "")
        for ioc_type, vals in (m.get("iocs") or {}).items():
            for val in (vals or []):
                e = ioc_agg[ioc_type][val]
                e["count"] += 1
                e["channels"].add(ch)
                if ts > e["last_seen"]:
                    e["last_seen"] = ts
    buf = StringIO()
    w   = csv.writer(buf)
    w.writerow(["type", "value", "count", "channels", "last_seen"])
    for ioc_type, vals in ioc_agg.items():
        for val, info in sorted(vals.items(), key=lambda x: -x[1]["count"]):
            w.writerow([ioc_type, val, info["count"],
                        "|".join(sorted(info["channels"])), info["last_seen"]])
    return Response(buf.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition": "attachment;filename=iocs.csv"})


@app.route("/api/threat_matrix")
def api_threat_matrix():
    """Matrix of threat actors (channels) vs Jordan target categories. Critical msgs only."""
    TARGET_CATEGORIES = {
        "Banking":   ["bank", "arab bank", "housing bank", "jordan ahli", "cairo amman",
                      "central bank", "البنك", "بنك", "aib", "invest bank"],
        "Telecom":   ["zain", "orange", "umniah", "tcs.jo", "jet.jo", "go.jo",
                      "jordan telecom", "اتصالات", "tcs communications"],
        "Gov/Mil":   ["government", "ministry", "military", "army", "وزار", "جيش",
                      "parliament", "muwaffaq", "قوات", "نيابة", "armed forces",
                      "مجلس", "presidency", "prime minister"],
        "ISP/Net":   ["cablenet", "index.jo", "internet", "broadband", "isp",
                      "network", "الانترنت"],
        "Media":     ["media", "news", "petra", "jordan tv", "قناة", "بث",
                      "television", "broadcast", "جهاز"],
        "Infra":     ["power", "water", "airport", "electricity", "سد", "كهرباء",
                      "fuel", "oil", "energy", "pipeline"],
        "General":   ["jordan", "الأردن", "amman", "عمان", "hashemite"],
    }
    messages = load_messages()
    matrix = defaultdict(lambda: {cat: 0 for cat in TARGET_CATEGORIES})
    for m in messages:
        if m.get("priority") != "CRITICAL":
            continue
        ch   = m.get("channel_username") or m.get("channel", "unknown")
        text = (m.get("text_preview") or "").lower()
        kws  = " ".join(m.get("keyword_hits", [])).lower()
        haystack = text + " " + kws
        for cat, keywords in TARGET_CATEGORIES.items():
            if any(kw.lower() in haystack for kw in keywords):
                matrix[ch][cat] += 1
    # Build rows from known CHANNEL_TIERS actors
    actors = []
    for ch, meta in CHANNEL_TIERS.items():
        if meta.get("status") == "banned":
            continue
        row = {
            "channel":  ch,
            "label":    meta.get("label", ch),
            "tier":     meta.get("tier", 0),
            "threat":   meta.get("threat", ""),
        }
        row_totals = 0
        for cat in TARGET_CATEGORIES:
            cnt = matrix[ch].get(cat, 0)
            row[cat] = cnt
            row_totals += cnt
        row["total"] = row_totals
        if row_totals > 0:
            actors.append(row)
    # Also include active channels not in CHANNEL_TIERS
    known = set(CHANNEL_TIERS.keys())
    for ch, cats in matrix.items():
        if ch in known:
            continue
        total = sum(cats.values())
        if total > 0:
            actors.append({"channel": ch, "label": ch, "tier": 0, "threat": "", "total": total, **cats})
    actors.sort(key=lambda x: (-(x.get("tier") or 0), -x["total"]))
    return jsonify({"categories": list(TARGET_CATEGORIES.keys()), "actors": actors})


# ─── APT TRACKER & IOC INTELLIGENCE ENDPOINTS ────────────────────────────────

def _build_apt_profiles():
    """Aggregate APT profiles from CHANNEL_TIERS + message data."""
    messages = load_messages()
    enrichments = load_enrichments()

    # Group channels by APT label (many channels → one APT)
    apt_groups = defaultdict(lambda: {
        "channels": [], "tier": 99, "threat": "", "status": "active",
        "total_msgs": 0, "critical_count": 0, "medium_count": 0,
        "sectors": defaultdict(int),
        "attack_types": defaultdict(int),
        "first_seen": "", "last_seen": "",
        "jordan_attacks": 0,
    })
    research_cache = _load_research_cache()

    # Map channel → APT name
    channel_to_apt = {}
    for ch, meta in CHANNEL_TIERS.items():
        if meta.get("status") == "banned":
            continue
        label = meta.get("label", ch)
        # Normalize group names: strip suffixes like (Backup), (Alt), (Active 2024+)
        base = re.sub(r'\s*\((?:Backup|Alt|Active\s*\d+\+?|Chat|Bot)\)\s*$', '', label).strip()
        channel_to_apt[ch] = base
        grp = apt_groups[base]
        grp["channels"].append(ch)
        tier = meta.get("tier", 3)
        if tier < grp["tier"]:
            grp["tier"] = tier
            grp["threat"] = meta.get("threat", "MEDIUM")

    # Jordan keywords for attack detection
    _jo_kw = [".jo", "jordan", "الاردن", "الأردن", "أردن", "اردن", "عمان", "amman", "hashemite"]

    # Scan all messages
    for m in messages:
        ch = m.get("channel_username") or m.get("channel", "")
        apt_name = channel_to_apt.get(ch)

        # Also check ai_enrichment group_attribution for channels not in CHANNEL_TIERS
        if not apt_name:
            ekey = f"{ch}_{m.get('message_id', '')}"
            ai = enrichments.get(ekey, m.get("ai_enrichment", {}))
            ga = ai.get("group_attribution", "")
            if ga and ga.lower() not in ("unknown", "n/a", ""):
                apt_name = ga
                if apt_name not in apt_groups:
                    apt_groups[apt_name]["channels"].append(ch)
                    apt_groups[apt_name]["tier"] = 3
                    apt_groups[apt_name]["threat"] = "MEDIUM"
                elif ch not in apt_groups[apt_name]["channels"]:
                    apt_groups[apt_name]["channels"].append(ch)

        if not apt_name:
            continue

        grp = apt_groups[apt_name]
        grp["total_msgs"] += 1
        pri = m.get("priority", "LOW")
        if pri == "CRITICAL":
            grp["critical_count"] += 1
        elif pri == "MEDIUM":
            grp["medium_count"] += 1

        # Timestamps
        ts = m.get("timestamp_utc", "")
        if ts:
            if not grp["first_seen"] or ts < grp["first_seen"]:
                grp["first_seen"] = ts
            if not grp["last_seen"] or ts > grp["last_seen"]:
                grp["last_seen"] = ts

        # AI enrichment — sectors and attack types
        ekey = f"{ch}_{m.get('message_id', '')}"
        ai = enrichments.get(ekey, m.get("ai_enrichment", {}))
        sector = ai.get("target_sector", "")
        if sector and sector.lower() not in ("unknown", "n/a", ""):
            grp["sectors"][sector] += 1
        atype = ai.get("attack_type", "")
        if atype and atype.lower() not in ("unknown", "n/a", ""):
            grp["attack_types"][atype] += 1

        # Jordan attack detection
        text = (m.get("text_preview") or "").lower()
        kws = " ".join(m.get("keyword_hits", [])).lower()
        haystack = text + " " + kws
        if any(kw in haystack for kw in _jo_kw):
            grp["jordan_attacks"] += 1

    # Build response list
    profiles = []
    for name, grp in apt_groups.items():
        if grp["total_msgs"] == 0:
            continue
        # IOC counts from external research cache
        research = research_cache.get(name, {})
        r_stats = research.get("stats", {})
        ioc_total = r_stats.get("total", 0)
        ioc_malicious = r_stats.get("malicious", 0)
        ioc_suspicious = r_stats.get("suspicious", 0)

        # Activity status
        last = grp["last_seen"]
        status = "inactive"
        if last:
            try:
                ld = datetime.fromisoformat(last.replace("Z", "+00:00"))
                delta = (datetime.now(timezone.utc) - ld).days
                status = "active" if delta <= 14 else ("stale" if delta <= 60 else "inactive")
            except Exception:
                pass

        profiles.append({
            "name": name,
            "tier": grp["tier"],
            "threat": grp["threat"],
            "channels": grp["channels"][:10],
            "status": status,
            "total_msgs": grp["total_msgs"],
            "critical_count": grp["critical_count"],
            "medium_count": grp["medium_count"],
            "ioc_count": ioc_total,
            "ioc_malicious": ioc_malicious,
            "ioc_suspicious": ioc_suspicious,
            "sectors": dict(sorted(grp["sectors"].items(), key=lambda x: -x[1])[:10]),
            "attack_types": dict(sorted(grp["attack_types"].items(), key=lambda x: -x[1])[:10]),
            "first_seen": grp["first_seen"],
            "last_seen": grp["last_seen"],
            "jordan_attacks": grp["jordan_attacks"],
        })
    profiles.sort(key=lambda x: (x["tier"], -x["critical_count"], -x["total_msgs"]))
    return profiles


@app.route("/api/apt/profiles")
def api_apt_profiles():
    """APT profile listing for APT Tracker sidebar."""
    return jsonify(_build_apt_profiles())


@app.route("/api/apt/<path:name>/detail")
def api_apt_detail(name):
    """Full APT detail: IOCs, attacks, timeline, recent messages."""
    messages = load_messages()
    enrichments = load_enrichments()

    # Find channels for this APT
    apt_channels = set()
    for ch, meta in CHANNEL_TIERS.items():
        if meta.get("status") == "banned":
            continue
        label = meta.get("label", ch)
        base = re.sub(r'\s*\((?:Backup|Alt|Active\s*\d+\+?|Chat|Bot)\)\s*$', '', label).strip()
        if base == name:
            apt_channels.add(ch)

    _jo_kw = [".jo", "jordan", "الاردن", "الأردن", "أردن", "اردن", "عمان", "amman", "hashemite"]
    attacks = []
    recent_critical = []
    timeline = defaultdict(lambda: {"critical": 0, "medium": 0, "low": 0})
    total_msgs = 0
    critical_count = 0
    medium_count = 0
    sectors = defaultdict(int)
    attack_types = defaultdict(int)
    first_seen = ""
    last_seen = ""

    for m in messages:
        ch = m.get("channel_username") or m.get("channel", "")

        # Check direct channel membership
        in_apt = ch in apt_channels

        # Also check ai_enrichment group_attribution
        if not in_apt:
            ekey = f"{ch}_{m.get('message_id', '')}"
            ai = enrichments.get(ekey, m.get("ai_enrichment", {}))
            ga = ai.get("group_attribution", "")
            if ga:
                ga_base = re.sub(r'\s*\((?:Backup|Alt|Active\s*\d+\+?|Chat|Bot)\)\s*$', '', ga).strip()
                if ga_base == name:
                    in_apt = True

        if not in_apt:
            continue

        total_msgs += 1
        ts = m.get("timestamp_utc", "")
        pri = m.get("priority", "LOW")
        if pri == "CRITICAL":
            critical_count += 1
        elif pri == "MEDIUM":
            medium_count += 1

        if ts:
            if not first_seen or ts < first_seen:
                first_seen = ts
            if not last_seen or ts > last_seen:
                last_seen = ts
            try:
                month = ts[:7]
                if pri == "CRITICAL":
                    timeline[month]["critical"] += 1
                elif pri == "MEDIUM":
                    timeline[month]["medium"] += 1
                else:
                    timeline[month]["low"] += 1
            except Exception:
                pass

        # IOCs
        msg_id = m.get("message_id", "")

        # AI enrichment
        ekey = f"{ch}_{m.get('message_id', '')}"
        ai = enrichments.get(ekey, m.get("ai_enrichment", {}))
        sector = ai.get("target_sector", "")
        if sector and sector.lower() not in ("unknown", "n/a", ""):
            sectors[sector] += 1
        atype = ai.get("attack_type", "")
        if atype and atype.lower() not in ("unknown", "n/a", ""):
            attack_types[atype] += 1

        # Jordan attacks
        text = (m.get("text_preview") or "").lower()
        kws = " ".join(m.get("keyword_hits", [])).lower()
        haystack = text + " " + kws
        if any(kw in haystack for kw in _jo_kw) and pri in ("CRITICAL", "MEDIUM"):
            # Extract target domain if present
            domains = (m.get("iocs") or {}).get("domain", [])
            jo_domains = [d for d in domains if ".jo" in d.lower()]
            target = jo_domains[0] if jo_domains else "Jordan target"
            attacks.append({
                "date": ts[:10] if ts else "",
                "target": target,
                "type": atype or pri,
                "channel": ch,
                "msg_id": str(msg_id),
                "summary": (m.get("text_preview") or "")[:120],
            })

        # Recent CRITICAL messages
        if pri == "CRITICAL":
            recent_critical.append({
                "msg_id": str(msg_id),
                "channel": ch,
                "timestamp": ts,
                "text": (m.get("text_preview") or "")[:200],
                "keyword_hits": m.get("keyword_hits", [])[:5],
                "iocs": {k: v[:3] for k, v in (m.get("iocs") or {}).items()},
            })

    # Timeline sorted
    tl = [{"month": k, **v} for k, v in sorted(timeline.items())]

    # Attacks sorted by date desc
    attacks.sort(key=lambda x: x["date"], reverse=True)

    # Recent critical sorted by timestamp desc
    recent_critical.sort(key=lambda x: x["timestamp"], reverse=True)

    return jsonify({
        "name": name,
        "channels": sorted(apt_channels),
        "total_msgs": total_msgs,
        "critical_count": critical_count,
        "medium_count": medium_count,
        "first_seen": first_seen,
        "last_seen": last_seen,
        "sectors": dict(sorted(sectors.items(), key=lambda x: -x[1])),
        "attack_types": dict(sorted(attack_types.items(), key=lambda x: -x[1])),
        "attacks": attacks[:50],
        "recent_messages": recent_critical[:20],
        "timeline": tl,
    })


# ─── AbuseIPDB Integration ───────────────────────────────────────────────────

_ABUSEIPDB_CACHE_FILE = OUTPUT_DIR / "abuseipdb_cache.json"
_ABUSEIPDB_KEY = "d1ee5f84fe37927d1e03bc40eee43241f0da49c4c192f2bba149e4895f8c664de10bac16360b271d"

def _load_abuse_cache():
    if _ABUSEIPDB_CACHE_FILE.exists():
        try:
            with open(_ABUSEIPDB_CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def _save_abuse_cache(cache):
    try:
        with open(_ABUSEIPDB_CACHE_FILE, "w", encoding="utf-8") as f:
            json.dump(cache, f, ensure_ascii=False, indent=1)
    except Exception:
        pass

def _abuseipdb_check(value, ioc_type):
    """Check IP/domain against AbuseIPDB with 24h cache."""
    import urllib.request, urllib.parse
    key = os.environ.get("ABUSEIPDB_API_KEY", _ABUSEIPDB_KEY)
    if not key:
        return None

    cache = _load_abuse_cache()
    cache_key = f"{ioc_type}:{value}"
    if cache_key in cache:
        entry = cache[cache_key]
        try:
            cached_at = datetime.fromisoformat(entry["cached_at"].replace("Z", "+00:00"))
            if (datetime.now(timezone.utc) - cached_at).total_seconds() < 86400:
                return entry["data"]
        except Exception:
            pass

    try:
        # AbuseIPDB only accepts IPs — resolve domains first
        lookup_ip = value
        if ioc_type == "domain":
            import socket
            try:
                lookup_ip = socket.gethostbyname(value)
            except socket.gaierror:
                return {"error": f"Cannot resolve domain {value}"}

        if ioc_type == "subnet":
            url = f"https://api.abuseipdb.com/api/v2/check-block?network={urllib.parse.quote(value)}"
        else:
            url = f"https://api.abuseipdb.com/api/v2/check?ipAddress={urllib.parse.quote(lookup_ip)}&maxAgeInDays=90&verbose=true"

        req = urllib.request.Request(url, headers={"Key": key, "Accept": "application/json"})
        resp = urllib.request.urlopen(req, timeout=15)
        data = json.loads(resp.read().decode())["data"]

        cache[cache_key] = {"data": data, "cached_at": datetime.now(timezone.utc).isoformat()}
        _save_abuse_cache(cache)
        return data
    except Exception as e:
        return {"error": str(e)}


def _virustotal_check(hash_value):
    """Check a hash against VirusTotal free API. Returns score + verdict."""
    import urllib.request
    vt_key = os.environ.get("VT_API_KEY", "")
    if not vt_key:
        return None
    try:
        url = f"https://www.virustotal.com/api/v3/files/{hash_value}"
        req = urllib.request.Request(url, headers={"x-apikey": vt_key, "Accept": "application/json"})
        resp = urllib.request.urlopen(req, timeout=15)
        data = json.loads(resp.read().decode())
        stats = data.get("data", {}).get("attributes", {}).get("last_analysis_stats", {})
        malicious = stats.get("malicious", 0)
        total = sum(stats.values()) if stats else 0
        score = int((malicious / total) * 100) if total > 0 else 0
        verdict = "MALICIOUS" if score > 50 else ("SUSPICIOUS" if score > 10 else "CLEAN")
        return {"score": score, "verdict": verdict, "detections": f"{malicious}/{total}"}
    except Exception:
        return None


def _detect_ioc_type(value):
    """Auto-detect IOC type from value."""
    v = value.strip()
    if re.match(r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}$', v):
        return "ipv4"
    if re.match(r'^\d{1,3}\.\d{1,3}\.\d{1,3}\.\d{1,3}/\d{1,2}$', v):
        return "subnet"
    if re.match(r'^[a-fA-F0-9]{32}$', v):
        return "hash_md5"
    if re.match(r'^[a-fA-F0-9]{64}$', v):
        return "hash_sha256"
    if re.match(r'^CVE-\d{4}-\d+$', v, re.I):
        return "cve"
    if re.match(r'^https?://', v, re.I):
        return "url"
    if re.match(r'^[\w.+-]+@[\w.-]+\.\w+$', v):
        return "email"
    if re.match(r'^[\w.-]+\.[a-zA-Z]{2,}$', v):
        return "domain"
    return "unknown"


@app.route("/api/apt/ioc/lookup", methods=["POST"])
def api_apt_ioc_lookup():
    """Lookup an IOC: local DB search + AbuseIPDB enrichment."""
    body = request.get_json(force=True, silent=True) or {}
    value = (body.get("value") or "").strip()
    if not value:
        return jsonify({"error": "No IOC value provided"}), 400

    ioc_type = body.get("type", "auto")
    if ioc_type == "auto":
        ioc_type = _detect_ioc_type(value)

    messages = load_messages()
    enrichments = load_enrichments()

    # Local DB search
    local_matches = []
    local_channels = set()
    local_apts = set()
    first_seen = ""
    last_seen = ""
    count = 0

    for m in messages:
        ch = m.get("channel_username") or m.get("channel", "")
        ts = m.get("timestamp_utc", "")
        msg_id = str(m.get("message_id", ""))

        # Check IOC fields
        found = False
        for it, vals in (m.get("iocs") or {}).items():
            if value.lower() in [v.lower() for v in (vals or [])]:
                found = True
                break

        # Also check text content for the value
        if not found:
            text = (m.get("text_preview") or "").lower()
            if value.lower() in text:
                found = True

        if not found:
            continue

        count += 1
        local_channels.add(ch)

        # Map to APT
        if ch in CHANNEL_TIERS and CHANNEL_TIERS[ch].get("status") != "banned":
            label = CHANNEL_TIERS[ch].get("label", ch)
            base = re.sub(r'\s*\((?:Backup|Alt|Active\s*\d+\+?|Chat|Bot)\)\s*$', '', label).strip()
            local_apts.add(base)
        else:
            ekey = f"{ch}_{m.get('message_id', '')}"
            ai = enrichments.get(ekey, m.get("ai_enrichment", {}))
            ga = ai.get("group_attribution", "")
            if ga and ga.lower() not in ("unknown", "n/a", ""):
                local_apts.add(ga)

        if ts:
            if not first_seen or ts < first_seen:
                first_seen = ts
            if not last_seen or ts > last_seen:
                last_seen = ts

        if len(local_matches) < 10:
            local_matches.append({
                "msg_id": msg_id,
                "channel": ch,
                "timestamp": ts,
                "summary_snippet": (m.get("text_preview") or "")[:150],
            })

    result = {
        "value": value,
        "type": ioc_type,
        "local": {
            "found": count > 0,
            "count": count,
            "apts": sorted(local_apts),
            "channels": sorted(local_channels),
            "first_seen": first_seen,
            "last_seen": last_seen,
            "messages": local_matches,
        },
    }

    # AbuseIPDB enrichment for IPs, domains, and subnets
    if ioc_type in ("ipv4", "domain", "subnet"):
        abuse_data = _abuseipdb_check(value, ioc_type)
        if abuse_data and "error" not in abuse_data:
            score = abuse_data.get("abuseConfidenceScore", 0)
            result["abuseipdb"] = {
                "abuseConfidenceScore": score,
                "countryCode": abuse_data.get("countryCode", ""),
                "isp": abuse_data.get("isp", ""),
                "domain": abuse_data.get("domain", ""),
                "totalReports": abuse_data.get("totalReports", 0),
                "lastReportedAt": abuse_data.get("lastReportedAt", ""),
                "usageType": abuse_data.get("usageType", ""),
                "isWhitelisted": abuse_data.get("isWhitelisted", False),
                "hostnames": abuse_data.get("hostnames", []),
            }
            # Verdict
            if score <= 25:
                verdict = "CLEAN"
            elif score <= 70:
                verdict = "SUSPICIOUS"
            else:
                verdict = "MALICIOUS"
            # Auto-bump if found in local DB linked to known APT
            if count > 0 and local_apts and verdict == "CLEAN":
                verdict = "SUSPICIOUS"
            result["verdict"] = verdict
        elif abuse_data and "error" in abuse_data:
            result["abuseipdb_error"] = abuse_data["error"]
    else:
        # For non-IP types, verdict based on local presence
        if count > 0 and local_apts:
            result["verdict"] = "SUSPICIOUS"
        elif count > 0:
            result["verdict"] = "SUSPICIOUS"
        else:
            result["verdict"] = "CLEAN"

    return jsonify(result)


@app.route("/api/apt/ioc/ai-extract", methods=["POST"])
def api_apt_ioc_ai_extract():
    """AI-powered deep IOC extraction — finds IOCs regex missed."""
    import openai
    body = request.get_json(force=True, silent=True) or {}
    apt_name = body.get("apt_name", "")
    if not apt_name:
        return jsonify({"error": "apt_name required"}), 400

    openai_key = os.environ.get("OPENAI_API_KEY", "")
    if not openai_key:
        return jsonify({"error": "OPENAI_API_KEY not set"}), 500

    messages = load_messages()
    enrichments = load_enrichments()

    # Find channels for this APT
    apt_channels = set()
    for ch, meta in CHANNEL_TIERS.items():
        if meta.get("status") == "banned":
            continue
        label = meta.get("label", ch)
        base = re.sub(r'\s*\((?:Backup|Alt|Active\s*\d+\+?|Chat|Bot)\)\s*$', '', label).strip()
        if base == apt_name:
            apt_channels.add(ch)

    # Gather CRITICAL+MEDIUM messages for this APT
    target_msgs = []
    for m in messages:
        ch = m.get("channel_username") or m.get("channel", "")
        if ch not in apt_channels:
            continue
        if m.get("priority") not in ("CRITICAL", "MEDIUM"):
            continue
        text = m.get("text_preview") or ""
        if text.strip():
            target_msgs.append({
                "id": str(m.get("message_id", "")),
                "ch": ch,
                "text": text[:500],
                "existing_iocs": m.get("iocs", {}),
            })

    if not target_msgs:
        return jsonify({"apt_name": apt_name, "new_iocs": [], "msg": "No messages to scan"})

    client = openai.OpenAI(api_key=openai_key)

    extract_prompt = """Analyze these Telegram messages from threat actor "{apt}" and extract ALL indicators of compromise (IOCs).

Look for:
- IP addresses (including defanged: 1[.]2[.]3[.]4, 1{.}2{.}3{.}4)
- Domains (including defanged: hxxps://evil[.]com, evil{dot}com)
- File hashes (MD5, SHA256)
- CVEs (CVE-YYYY-NNNNN)
- Email addresses
- C2 server addresses
- URLs to paste sites, file shares, proof screenshots
- Infrastructure mentioned in attack context

For each IOC found, output ONE line:
TYPE|VALUE|CONTEXT

TYPE = ipv4, domain, url, hash_md5, hash_sha256, cve, email
VALUE = deobfuscated (hxxp→http, [.]→., etc.)
CONTEXT = brief description

ONLY output IOC lines. No explanations."""

    # Process in chunks
    chunk_size = 40
    all_new_iocs = []

    def _process_chunk(chunk):
        msg_block = "\n---\n".join([f"[{m['id']}@{m['ch']}] {m['text']}" for m in chunk])
        try:
            resp = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[
                    {"role": "system", "content": extract_prompt.format(apt=apt_name)},
                    {"role": "user", "content": msg_block}
                ],
                temperature=0.1,
                max_tokens=2000,
            )
            return resp.choices[0].message.content or ""
        except Exception as e:
            return f"ERROR:{e}"

    chunks = [target_msgs[i:i+chunk_size] for i in range(0, len(target_msgs), chunk_size)]

    with ThreadPoolExecutor(max_workers=5) as pool:
        futures = {pool.submit(_process_chunk, c): i for i, c in enumerate(chunks)}
        for fut in as_completed(futures):
            try:
                result = fut.result()
                for line in result.strip().split("\n"):
                    parts = [p.strip() for p in line.split("|")]
                    if len(parts) >= 2:
                        itype = parts[0].lower()
                        ival = parts[1]
                        ctx = parts[2] if len(parts) > 2 else ""
                        if itype in ("ipv4", "domain", "url", "hash_md5", "hash_sha256", "cve", "email"):
                            all_new_iocs.append({"type": itype, "value": ival, "context": ctx})
            except Exception:
                pass

    # Deduplicate and filter out already-known IOCs
    existing = set()
    for m in target_msgs:
        for itype, vals in (m.get("existing_iocs") or {}).items():
            for v in (vals or []):
                existing.add(f"{itype}:{v.lower()}")

    unique_new = []
    seen = set()
    for ioc in all_new_iocs:
        key = f"{ioc['type']}:{ioc['value'].lower()}"
        if key not in existing and key not in seen:
            seen.add(key)
            unique_new.append(ioc)

    return jsonify({
        "apt_name": apt_name,
        "messages_scanned": len(target_msgs),
        "chunks_processed": len(chunks),
        "new_iocs": unique_new,
        "total_found": len(all_new_iocs),
        "already_known": len(all_new_iocs) - len(unique_new),
    })


# ─── External IOC Research Engine ─────────────────────────────────────────────

_RESEARCH_CACHE_FILE = OUTPUT_DIR / "apt_ioc_research.json"
_RESEARCH_TTL = 48 * 3600  # 48 hours
_OTX_KEY = "868c2e9e62dfc53b961657ef3194890c6d716774f8755a75aa46a8a24832d0fc"
_research_lock = threading.Lock()

def _load_research_cache():
    if _RESEARCH_CACHE_FILE.exists():
        try:
            with open(_RESEARCH_CACHE_FILE, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception:
            pass
    return {}

def _save_research_cache(cache):
    with _research_lock:
        try:
            with open(_RESEARCH_CACHE_FILE, "w", encoding="utf-8") as f:
                json.dump(cache, f, ensure_ascii=False, indent=1)
        except Exception:
            pass

def _research_cache_fresh(entry):
    """Check if a research cache entry is still fresh."""
    try:
        ts = entry.get("researched_at", "")
        dt = datetime.fromisoformat(ts.replace("Z", "+00:00"))
        return (datetime.now(timezone.utc) - dt).total_seconds() < _RESEARCH_TTL
    except Exception:
        return False


def _generate_apt_summary(apt_name, aliases):
    """Generate an OSINT-based summary/bio for an APT group using GPT-4o-mini."""
    import openai
    openai_key = os.environ.get("OPENAI_API_KEY", "")
    if not openai_key:
        return ""
    alias_str = ", ".join(aliases) if aliases else apt_name
    try:
        client = openai.OpenAI(api_key=openai_key)
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a senior cyber threat intelligence analyst. Provide concise, factual profiles of threat actors based on publicly available OSINT and published CTI reports. Write in a professional, intelligence-briefing style."},
                {"role": "user", "content": f"""Write a 2-3 sentence intelligence profile of the threat group "{apt_name}" (aliases: {alias_str}).

Include: origin/nationality, known affiliations (state sponsors, parent APT groups, or hacktivist collectives), primary motivations, known targets/campaigns, and operational timeline if known.

This is a hacktivist/APT group active in the Middle East conflict. They may be linked to Iranian, Russian, or pro-Palestinian cyber operations.

If you have limited info, state what is known and note it's a lesser-known group. Be factual and concise. No headers or bullet points — just a paragraph."""}
            ],
            temperature=0.2,
            max_tokens=300,
        )
        summary = (resp.choices[0].message.content or "").strip()
        print(f"[RESEARCH] Generated summary for {apt_name}: {len(summary)} chars", flush=True)
        return summary
    except Exception as e:
        print(f"[RESEARCH] Summary generation error for {apt_name}: {e}", flush=True)
        return ""


def _research_gpt(apt_name, aliases):
    """Ask GPT-4o-mini for known IOCs attributed to an APT group."""
    import openai
    openai_key = os.environ.get("OPENAI_API_KEY", "")
    if not openai_key:
        return []
    alias_str = ", ".join(aliases) if aliases else apt_name
    prompt = f"""List the known INFRASTRUCTURE IOCs specifically attributed to "{apt_name}" (also known as: {alias_str}).

This is a hacktivist/APT group active in the Middle East targeting Jordan, Israel, and Gulf states.

IMPORTANT RULES:
- Only include IOCs that are SPECIFICALLY attributed to this group in published CTI reports
- DO NOT include generic Tor exit nodes, public VPN IPs, or shared hosting IPs
- DO NOT include 185.220.101.x, 45.153.160.x, or other well-known Tor relay ranges
- Each IOC must be unique to this group's operations, not shared internet infrastructure
- If you don't know any group-specific IOCs, output NONE — do not guess or use generic IPs

I want:
- C2 server IPs specifically used by this group
- Domains registered/used by this group for C2, phishing, defacement
- Malware hashes of their specific tools, payloads, webshells
- URLs of their C2 panels, leak sites, dropper locations

DO NOT include CVEs or generic infrastructure.

Format — one line per IOC:
ipv4|1.2.3.4|C2 server for campaign X|high
domain|evil.com|phishing domain used in Y attack|medium
hash_md5|abc123...|webshell used in Z campaign|high
hash_sha256|def456...|RAT payload|high

Only output IOC lines. If zero knowledge, output: NONE"""

    try:
        client = openai.OpenAI(api_key=openai_key)
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": "You are a CTI analyst. When asked about threat actors, always list any IOCs you know from published reports, blog posts, CISA advisories, or OSINT research. Never say NONE if you can recall any infrastructure details at all. Include approximate or historically reported IOCs."},
                {"role": "user", "content": prompt}
            ],
            temperature=0.3,
            max_tokens=3000,
        )
        text = resp.choices[0].message.content or ""
        if "NONE" in text.strip().upper()[:10]:
            return []
        # Type aliases: GPT often outputs "IP" instead of "ipv4", "Hash" instead of "hash_md5"
        _type_aliases = {
            "ip": "ipv4", "ipv4": "ipv4", "ipv6": "ipv4",
            "domain": "domain", "hostname": "domain",
            "url": "url",
            "hash": "hash_md5", "md5": "hash_md5", "hash_md5": "hash_md5",
            "sha256": "hash_sha256", "hash_sha256": "hash_sha256", "sha1": "hash_sha256",
        }
        results = []
        for line in text.strip().split("\n"):
            # Strip markdown: numbered lists, bold, backticks, bullets
            clean = re.sub(r'^\s*\d+[\.\)]\s*', '', line)   # "1. " or "1) "
            clean = clean.strip().strip('*').strip('`').strip('-').strip()
            clean = clean.replace('**', '')
            if '|' not in clean:
                continue
            parts = [p.strip().strip('*').strip('`').strip() for p in clean.split("|")]
            if len(parts) < 3:
                continue
            ioc_type = _type_aliases.get(parts[0].lower().replace(" ", "_"))
            if not ioc_type:
                continue
            value = parts[1].strip()
            if not value or len(value) < 3:
                continue
            results.append({
                "type": ioc_type,
                "value": value,
                "source": "gpt-4o",
                "context": parts[2],
                "confidence": parts[3].lower() if len(parts) > 3 and parts[3].lower() in ("high","medium","low") else "medium",
            })
        print(f"[RESEARCH] GPT returned {len(results)} IOCs for {apt_name}", flush=True)
        return results
    except Exception as e:
        print(f"[RESEARCH] GPT error for {apt_name}: {e}")
        return []


def _research_otx(apt_name):
    """Search AlienVault OTX for pulses mentioning this APT and extract IOCs."""
    import urllib.request, urllib.parse
    headers = {"Accept": "application/json", "X-OTX-API-KEY": _OTX_KEY}
    results = []
    try:
        search_url = f"https://otx.alienvault.com/api/v1/search/pulses?q={urllib.parse.quote(apt_name)}&limit=5&sort=modified"
        req = urllib.request.Request(search_url, headers=headers)
        resp = urllib.request.urlopen(req, timeout=20)
        data = json.loads(resp.read().decode())
        pulse_ids = [p["id"] for p in data.get("results", [])[:5]]
        type_map = {"IPv4": "ipv4", "domain": "domain", "URL": "url",
                    "FileHash-MD5": "hash_md5", "FileHash-SHA256": "hash_sha256",
                    "hostname": "domain"}
        for pid in pulse_ids:
            try:
                ind_url = f"https://otx.alienvault.com/api/v1/pulses/{pid}/indicators?limit=50"
                req2 = urllib.request.Request(ind_url, headers=headers)
                resp2 = urllib.request.urlopen(req2, timeout=15)
                ind_data = json.loads(resp2.read().decode())
                for ind in ind_data.get("results", []):
                    otype = type_map.get(ind.get("type"), "")
                    if otype:
                        results.append({
                            "type": otype,
                            "value": ind.get("indicator", ""),
                            "source": "otx",
                            "context": (ind.get("description") or "") or f"OTX pulse {pid[:8]}",
                            "confidence": "high",
                        })
            except Exception:
                pass
    except Exception as e:
        print(f"[RESEARCH] OTX error for {apt_name}: {e}")
    return results


def _research_threatfox(apt_name):
    """Search ThreatFox for IOCs tagged with this APT name."""
    import urllib.request
    results = []
    for qtype, qfield in [("taginfo", "tag"), ("malwareinfo", "malware")]:
        try:
            body = json.dumps({"query": qtype, qfield: apt_name, "limit": 50}).encode()
            req = urllib.request.Request(
                "https://threatfox-api.abuse.ch/api/v1/",
                data=body,
                headers={"Content-Type": "application/json"},
            )
            resp = urllib.request.urlopen(req, timeout=15)
            data = json.loads(resp.read().decode())
            if data.get("query_status") != "ok":
                continue
            type_map = {"ip:port": "ipv4", "domain": "domain", "url": "url",
                        "md5_hash": "hash_md5", "sha256_hash": "hash_sha256"}
            for item in (data.get("data") or []):
                ioc_val = item.get("ioc", "")
                otype = type_map.get(item.get("ioc_type", ""), "")
                if otype:
                    if otype == "ipv4" and ":" in ioc_val:
                        ioc_val = ioc_val.split(":")[0]
                    results.append({
                        "type": otype,
                        "value": ioc_val,
                        "source": "threatfox",
                        "context": item.get("malware_printable", "") or item.get("threat_type_desc", ""),
                        "confidence": "high" if item.get("confidence_level", 0) >= 75 else "medium",
                    })
        except Exception as e:
            print(f"[RESEARCH] ThreatFox {qtype} error for {apt_name}: {e}")
    return results


def _get_apt_aliases(apt_name):
    """Get aliases for an APT from CHANNEL_TIERS labels."""
    aliases = set()
    for ch, meta in CHANNEL_TIERS.items():
        if meta.get("status") == "banned":
            continue
        label = meta.get("label", "")
        base = re.sub(r'\s*\((?:Backup|Alt|Active\s*\d+\+?|Chat|Bot|IRGC|MOIS[^)]*|[^)]*handle[^)]*|[^)]*breach[^)]*)\)\s*$', '', label).strip()
        if base == apt_name and label != base:
            aliases.add(label)
    return list(aliases)


def _research_apt_iocs(apt_name):
    """Research IOCs for an APT group from all external sources, verify via AbuseIPDB."""
    aliases = _get_apt_aliases(apt_name)
    all_raw = []
    sources_queried = []
    apt_summary_text = ""

    with ThreadPoolExecutor(max_workers=4) as pool:
        summary_fut = pool.submit(_generate_apt_summary, apt_name, aliases)
        ioc_futures = {
            pool.submit(_research_gpt, apt_name, aliases): "gpt-4o",
            pool.submit(_research_otx, apt_name): "otx",
            pool.submit(_research_threatfox, apt_name): "threatfox",
        }
        for fut in as_completed(ioc_futures):
            src = ioc_futures[fut]
            sources_queried.append(src)
            try:
                res = fut.result()
                print(f"[RESEARCH] {apt_name} <- {src}: {len(res)} IOCs", flush=True)
                all_raw.extend(res)
            except Exception as e:
                print(f"[RESEARCH] {apt_name} <- {src}: ERROR {e}", flush=True)
        try:
            apt_summary_text = summary_fut.result()
        except Exception:
            apt_summary_text = ""

    # Deduplicate by type:value
    seen = {}
    for ioc in all_raw:
        key = f"{ioc['type']}:{ioc['value'].lower().strip()}"
        if key not in seen:
            seen[key] = ioc
        else:
            existing = seen[key]
            if ioc.get("confidence") == "high":
                existing["confidence"] = "high"
            if ioc["source"] not in existing["source"]:
                existing["source"] += "+" + ioc["source"]
    unique_iocs = list(seen.values())

    # Verify ALL IOCs — IPs/domains/URLs via AbuseIPDB, hashes via VirusTotal
    def _verify(ioc):
        itype = ioc["type"]
        val = ioc["value"]

        # IPs — direct AbuseIPDB check
        if itype == "ipv4":
            abuse = _abuseipdb_check(val, "ipv4")
            if abuse and "error" not in abuse:
                score = abuse.get("abuseConfidenceScore", 0)
                ioc["abuse_score"] = score
                ioc["abuse_verdict"] = "MALICIOUS" if score > 70 else ("SUSPICIOUS" if score > 25 else "CLEAN")
                ioc["abuse_country"] = abuse.get("countryCode", "")
                ioc["abuse_isp"] = abuse.get("isp", "")
                ioc["abuse_reports"] = abuse.get("totalReports", 0)
            else:
                ioc["abuse_score"] = -1
                ioc["abuse_verdict"] = "UNVERIFIED"
            return ioc

        # Domains — resolve then AbuseIPDB
        if itype == "domain":
            abuse = _abuseipdb_check(val, "domain")
            if abuse and "error" not in abuse:
                score = abuse.get("abuseConfidenceScore", 0)
                ioc["abuse_score"] = score
                ioc["abuse_verdict"] = "MALICIOUS" if score > 70 else ("SUSPICIOUS" if score > 25 else "CLEAN")
                ioc["abuse_country"] = abuse.get("countryCode", "")
                ioc["abuse_isp"] = abuse.get("isp", "")
                ioc["abuse_reports"] = abuse.get("totalReports", 0)
            else:
                ioc["abuse_score"] = -1
                ioc["abuse_verdict"] = "SUSPICIOUS"  # GPT attributed it — at least suspicious
            return ioc

        # URLs — extract domain, check via AbuseIPDB
        if itype == "url":
            try:
                from urllib.parse import urlparse
                host = urlparse(val).hostname or ""
                if host:
                    abuse = _abuseipdb_check(host, "domain")
                    if abuse and "error" not in abuse:
                        score = abuse.get("abuseConfidenceScore", 0)
                        ioc["abuse_score"] = score
                        ioc["abuse_verdict"] = "MALICIOUS" if score > 70 else ("SUSPICIOUS" if score > 25 else "CLEAN")
                        ioc["abuse_country"] = abuse.get("countryCode", "")
                        return ioc
            except Exception:
                pass
            ioc["abuse_score"] = -1
            ioc["abuse_verdict"] = "SUSPICIOUS"
            return ioc

        # Hashes — check VirusTotal
        if itype in ("hash_md5", "hash_sha256"):
            vt_result = _virustotal_check(val)
            if vt_result:
                ioc["abuse_score"] = vt_result["score"]
                ioc["abuse_verdict"] = vt_result["verdict"]
                ioc["vt_detections"] = vt_result.get("detections", "")
            else:
                ioc["abuse_score"] = -1
                ioc["abuse_verdict"] = "SUSPICIOUS"
            return ioc

        # Fallback for any other type
        ioc["abuse_score"] = -1
        ioc["abuse_verdict"] = "SUSPICIOUS"
        return ioc

    with ThreadPoolExecutor(max_workers=3) as pool:
        list(pool.map(_verify, unique_iocs))

    # Sort: malicious first
    vord = {"MALICIOUS": 0, "SUSPICIOUS": 1, "UNVERIFIED": 2, "CLEAN": 3}
    unique_iocs.sort(key=lambda x: (vord.get(x.get("abuse_verdict", "UNVERIFIED"), 9), -(x.get("abuse_score", -1))))

    stats = {
        "total": len(unique_iocs),
        "verified": sum(1 for i in unique_iocs if i.get("abuse_score", -1) >= 0),
        "malicious": sum(1 for i in unique_iocs if i.get("abuse_verdict") == "MALICIOUS"),
        "suspicious": sum(1 for i in unique_iocs if i.get("abuse_verdict") == "SUSPICIOUS"),
        "clean": sum(1 for i in unique_iocs if i.get("abuse_verdict") == "CLEAN"),
    }

    return {
        "researched_at": datetime.now(timezone.utc).isoformat(),
        "sources_queried": sources_queried,
        "summary": apt_summary_text,
        "iocs": unique_iocs,
        "stats": stats,
    }


def _get_all_apt_names():
    """Get unique APT names from CHANNEL_TIERS."""
    names = set()
    for ch, meta in CHANNEL_TIERS.items():
        if meta.get("status") == "banned":
            continue
        label = meta.get("label", ch)
        base = re.sub(r'\s*\((?:Backup|Alt|Active\s*\d+\+?|Chat|Bot)\)\s*$', '', label).strip()
        names.add(base)
    return sorted(names)


_TG_BOT_TOKEN = "8731122610:AAGeLVygNXo6Ybq1WUTznXmQG30mr0X6CdM"
_TG_CHAT_ID = "-5258928587"


def _tg_send(text, parse_mode="HTML"):
    """Send a message to the Telegram bot chat."""
    import urllib.request, urllib.parse
    url = f"https://api.telegram.org/bot{_TG_BOT_TOKEN}/sendMessage"
    payload = json.dumps({
        "chat_id": _TG_CHAT_ID,
        "text": text,
        "parse_mode": parse_mode,
        "disable_web_page_preview": True,
    }).encode()
    try:
        req = urllib.request.Request(url, data=payload, headers={"Content-Type": "application/json"})
        urllib.request.urlopen(req, timeout=15)
    except Exception as e:
        print(f"[TG-BOT] Send error: {e}", flush=True)


_TG_SENT_FILE = OUTPUT_DIR / "tg_sent_iocs.json"


def _load_tg_sent():
    try:
        return set(json.loads(_TG_SENT_FILE.read_text()))
    except Exception:
        return set()


def _save_tg_sent(sent):
    try:
        _TG_SENT_FILE.write_text(json.dumps(list(sent)))
    except Exception:
        pass


_tg_sent_iocs = _load_tg_sent()


def _tg_notify_apt_research(apt_name, result):
    """Send researched IOCs for an APT to Telegram — only NEW IOCs not yet sent."""
    global _tg_sent_iocs
    stats = result.get("stats", {})
    total = stats.get("total", 0)
    if total == 0:
        return

    iocs = result.get("iocs", [])
    # Filter to only IOCs we haven't already sent
    new_iocs = [i for i in iocs if i["value"] not in _tg_sent_iocs]
    new_actionable = [i for i in new_iocs if i.get("abuse_verdict") in ("MALICIOUS", "SUSPICIOUS")]

    if not new_actionable:
        for i in iocs:
            _tg_sent_iocs.add(i["value"])
        _save_tg_sent(_tg_sent_iocs)
        return

    mal = sum(1 for i in new_actionable if i.get("abuse_verdict") == "MALICIOUS")
    sus = sum(1 for i in new_actionable if i.get("abuse_verdict") == "SUSPICIOUS")

    lines = [f"\U0001f6e1 <b>Scanwave CyberIntel</b> \u2014 IOCs Detected & Blocked"]
    lines.append(f"\n\U0001f3af <b>{apt_name}</b>")
    summary = result.get("summary", "")
    if summary:
        lines.append(f"<i>{summary[:250]}</i>")
    lines.append(f"\n\u2716 {len(new_actionable)} new IOCs | \U0001f534 {mal} Malicious | \U0001f7e1 {sus} Suspicious")

    lines.append("")
    for ioc in new_actionable[:10]:
        v = ioc.get("abuse_verdict", "")
        icon = "\U0001f6ab" if v == "MALICIOUS" else "\u26a0\ufe0f"
        score = ioc.get("abuse_score", -1)
        tag = f" {score}%" if score >= 0 else f" [{ioc.get('type','')}]"
        lines.append(f"{icon} <code>{ioc['value']}</code>{tag}")

    # Mark all as sent and persist
    for i in iocs:
        _tg_sent_iocs.add(i["value"])
    _save_tg_sent(_tg_sent_iocs)

    text = "\n".join(lines)
    if len(text) > 4000:
        text = text[:4000] + "\n..."
    _tg_send(text)


def _tg_notify_cycle_complete(cache):
    """Send summary when full research cycle completes, including top IOCs."""
    seen = {}
    for apt_name, entry in cache.items():
        for ioc in entry.get("iocs", []):
            val = ioc["value"].lower().strip()
            if val not in seen:
                seen[val] = {"apt": apt_name, **ioc}
            elif apt_name not in seen[val].get("apt", ""):
                seen[val]["apt"] += ", " + apt_name

    all_iocs = list(seen.values())
    total_mal = sum(1 for i in all_iocs if i.get("abuse_verdict") == "MALICIOUS")
    total_sus = sum(1 for i in all_iocs if i.get("abuse_verdict") == "SUSPICIOUS")
    apts_hit = sum(1 for e in cache.values() if e.get("stats", {}).get("total", 0) > 0)

    lines = [
        "\U0001f6e1 <b>Scanwave CyberIntel</b> \u2014 Research Cycle Complete",
        f"\n{len(cache)} APT groups scanned \u2022 {apts_hit} with IOCs",
        f"\U0001f534 {total_mal} Malicious \u2022 \U0001f7e1 {total_sus} Suspicious \u2022 {len(all_iocs)} Unique IOCs",
    ]

    malicious = sorted([i for i in all_iocs if i.get("abuse_verdict") == "MALICIOUS"], key=lambda x: -(x.get("abuse_score", 0)))
    if malicious:
        lines.append("\n<b>Top Malicious:</b>")
        for ioc in malicious[:10]:
            score = ioc.get("abuse_score", -1)
            tag = f" {score}%" if score >= 0 else ""
            lines.append(f"\U0001f6ab <code>{ioc['value']}</code>{tag}")

    suspicious = sorted([i for i in all_iocs if i.get("abuse_verdict") == "SUSPICIOUS"], key=lambda x: -(x.get("abuse_score", 0)))
    if suspicious:
        lines.append("\n<b>Suspicious:</b>")
        for ioc in suspicious[:8]:
            score = ioc.get("abuse_score", -1)
            tag = f" {score}%" if score >= 0 else f" [{ioc.get('type','')}]"
            lines.append(f"\u26a0\ufe0f <code>{ioc['value']}</code>{tag}")

    lines.append(f"\n<a href='http://138.2.138.225:8888'>Open Dashboard</a>")

    text = "\n".join(lines)
    if len(text) > 4000:
        text = text[:4000] + "\n..."
    _tg_send(text)


def _auto_research_loop():
    """Background thread: research all APTs on startup, then every 24h."""
    time.sleep(10)  # Let Flask start first
    while True:
        _tg_sent_iocs.update(_load_tg_sent())  # Reload persisted set
        try:
            cache = _load_research_cache()
            apt_names = _get_all_apt_names()
            for apt_name in apt_names:
                if apt_name in cache and _research_cache_fresh(cache[apt_name]):
                    continue
                print(f"[RESEARCH] Auto-researching: {apt_name}", flush=True)
                try:
                    result = _research_apt_iocs(apt_name)
                    cache[apt_name] = result
                    _save_research_cache(cache)
                    print(f"[RESEARCH] {apt_name}: {result['stats']['total']} IOCs ({result['stats']['malicious']} malicious)", flush=True)
                    _tg_notify_apt_research(apt_name, result)
                except Exception as e:
                    print(f"[RESEARCH] Error for {apt_name}: {e}", flush=True)
                time.sleep(3)  # Throttle between APTs
            print(f"[RESEARCH] Auto-research cycle complete. {len(apt_names)} APTs processed.", flush=True)
            _tg_notify_cycle_complete(cache)
        except Exception as e:
            print(f"[RESEARCH] Cycle error: {e}", flush=True)
        time.sleep(86400)  # Sleep 24h


@app.route("/api/apt/<path:name>/research")
def api_apt_research(name):
    """Get researched IOCs for an APT. Auto-triggers if stale."""
    cache = _load_research_cache()
    if name in cache and _research_cache_fresh(cache[name]):
        entry = cache[name]
        entry["cached"] = True
        return jsonify(entry)
    # Research fresh (this may take 10-30s)
    result = _research_apt_iocs(name)
    result["cached"] = False
    cache[name] = result
    _save_research_cache(cache)
    return jsonify(result)


@app.route("/api/blocklist")
def api_blocklist():
    """Central blocklist: ALL researched IOCs across ALL APTs."""
    cache = _load_research_cache()
    apt_filter = request.args.get("apt", "").strip()
    type_filter = request.args.get("type", "").strip().lower()
    verdict_filter = request.args.get("verdict", "").strip().upper()
    search_q = request.args.get("q", "").strip().lower()

    apt_summary = {}
    # Collect all IOCs, dedup by value — merge APT attributions
    seen = {}  # key=value -> merged IOC dict

    for apt_name, entry in cache.items():
        if apt_filter and apt_name != apt_filter:
            continue
        stats = entry.get("stats", {})
        apt_summary[apt_name] = {
            "researched_at": entry.get("researched_at", ""),
            "total": stats.get("total", 0),
            "malicious": stats.get("malicious", 0),
            "suspicious": stats.get("suspicious", 0),
        }
        for ioc in entry.get("iocs", []):
            if type_filter and ioc.get("type") != type_filter:
                continue
            if verdict_filter and ioc.get("abuse_verdict") != verdict_filter:
                continue
            if search_q and search_q not in ioc.get("value", "").lower() and search_q not in ioc.get("context", "").lower():
                continue
            val = ioc["value"].lower().strip()
            if val in seen:
                # Merge: append APT name if not already there
                existing = seen[val]
                if apt_name not in existing["apt"]:
                    existing["apt"] += ", " + apt_name
            else:
                seen[val] = {"apt": apt_name, **ioc}

    blocklist = list(seen.values())
    vord = {"MALICIOUS": 0, "SUSPICIOUS": 1, "UNVERIFIED": 2, "CLEAN": 3}
    blocklist.sort(key=lambda x: (vord.get(x.get("abuse_verdict", "UNVERIFIED"), 9), -(x.get("abuse_score", -1))))

    total_mal = sum(1 for i in blocklist if i.get("abuse_verdict") == "MALICIOUS")
    total_sus = sum(1 for i in blocklist if i.get("abuse_verdict") == "SUSPICIOUS")
    total_clean = sum(1 for i in blocklist if i.get("abuse_verdict") == "CLEAN")
    return jsonify({
        "total": len(blocklist),
        "apts_researched": len([a for a in apt_summary.values() if a.get("total", 0) > 0]),
        "malicious": total_mal,
        "suspicious": total_sus,
        "clean": total_clean,
        "apt_summary": apt_summary,
        "iocs": blocklist[:1000],
    })


@app.route("/api/blocklist/export")
def api_blocklist_export():
    """Export blocklist as CSV."""
    cache = _load_research_cache()
    verdict_filter = request.args.get("verdict", "").strip().upper()
    buf = StringIO()
    w = csv.writer(buf)
    w.writerow(["APT Group", "IOC Type", "Value", "Verdict", "AbuseIPDB Score",
                "Country", "ISP", "Reports", "Source", "Context", "Confidence"])
    for apt_name, entry in cache.items():
        for ioc in entry.get("iocs", []):
            if verdict_filter and ioc.get("abuse_verdict") != verdict_filter:
                continue
            w.writerow([apt_name, ioc.get("type", ""), ioc.get("value", ""),
                        ioc.get("abuse_verdict", ""), ioc.get("abuse_score", ""),
                        ioc.get("abuse_country", ""), ioc.get("abuse_isp", ""),
                        ioc.get("abuse_reports", ""), ioc.get("source", ""),
                        ioc.get("context", ""), ioc.get("confidence", "")])
    return Response(buf.getvalue(), mimetype="text/csv",
                    headers={"Content-Disposition": "attachment;filename=blocklist.csv"})


# ── DOCX Report Generator (Template-based) ────────────────────
def _generate_blocklist_report():
    """Generate ScanWave SOC Client Advisory using the original branded template.

    Opens scanwave_report_template.docx (exact copy of original report),
    preserves ALL styling/branding/logo/cover page, removes old IOC tables,
    inserts live blocklist IOCs organized by APT group.
    """
    from docx import Document
    from docx.shared import Pt, RGBColor
    from docx.oxml.ns import qn
    from docx.oxml import OxmlElement

    template_path = Path(__file__).parent / "scanwave_report_template.docx"
    if not template_path.exists():
        raise FileNotFoundError("Report template not found: scanwave_report_template.docx")

    doc = Document(str(template_path))
    body = doc.element.body
    now = datetime.now(timezone.utc)

    # ── Load live IOC data — per-group, no cross-group name merging ──
    cache = _load_research_cache()
    apt_iocs = {}  # {apt_name: [unique IOC dicts]}
    global_seen = set()  # track all unique IOC values for total count
    for apt_name, entry in cache.items():
        iocs = entry.get("iocs", [])
        if not iocs:
            continue
        seen_in_group = set()
        unique = []
        for ioc in iocs:
            val = ioc["value"].lower().strip()
            if val not in seen_in_group:
                seen_in_group.add(val)
                unique.append(ioc)
                global_seen.add(val)
        if unique:
            apt_iocs[apt_name] = unique

    # Split: major groups (>=4 IOCs) shown individually, minor (<4) pooled
    THRESHOLD = 4
    major = {k: v for k, v in apt_iocs.items() if len(v) >= THRESHOLD}
    minor = {k: v for k, v in apt_iocs.items() if len(v) < THRESHOLD}

    # Pool minor-group IOCs (deduped)
    other_iocs = []
    other_seen = set()
    other_group_names = sorted(minor.keys())
    for grp in other_group_names:
        for ioc in minor[grp]:
            val = ioc["value"].lower().strip()
            if val not in other_seen:
                other_seen.add(val)
                other_iocs.append(ioc)

    total_iocs = len(global_seen)
    all_flat = [ioc for group_iocs in apt_iocs.values() for ioc in group_iocs]
    total_mal = sum(1 for i in all_flat if i.get("abuse_verdict") == "MALICIOUS")
    total_sus = sum(1 for i in all_flat if i.get("abuse_verdict") == "SUSPICIOUS")

    # ── Step 1: Update date on cover page ──
    import re as _re
    for p in doc.paragraphs:
        if _re.match(r'^[A-Z][a-z]+ \d{4}$', p.text.strip()):
            for run in p.runs:
                run.text = now.strftime("%B %Y")
            break

    # ── Step 2: Find markers ──
    ioc_summary_el = None
    critical_note_el = None
    for p in doc.paragraphs:
        if "IOC SUMMARY" in p.text and ioc_summary_el is None:
            ioc_summary_el = p._element
        if "CRITICAL NOTE" in p.text:
            critical_note_el = p._element

    if ioc_summary_el is None or critical_note_el is None:
        raise ValueError("Template missing IOC SUMMARY or CRITICAL NOTE markers")

    # ── Step 3: Remove everything between IOC SUMMARY and CRITICAL NOTE ──
    # Find indices of the two markers
    children = list(body)
    ioc_idx = None
    crit_idx = None
    for i, child in enumerate(children):
        if child is ioc_summary_el:
            ioc_idx = i
        if child is critical_note_el:
            crit_idx = i
    if ioc_idx is None or crit_idx is None:
        raise ValueError("Cannot locate marker indices")

    # Remove elements between markers (exclusive of both)
    for child in children[ioc_idx + 1:crit_idx]:
        body.remove(child)

    # ── Step 4: Build new IOC content as raw XML elements ──
    # We build elements via doc.add_paragraph/add_table, then detach and
    # insert at the correct position right after IOC SUMMARY.
    new_elements = []

    # Helper: build a 3-column IOC grid table and return the tbl element
    def _add_ioc_table(ioc_list):
        values = [i["value"] for i in ioc_list]
        cols = 3
        nrows = (len(values) + cols - 1) // cols
        table = doc.add_table(rows=nrows, cols=cols)
        tbl = table._tbl
        tblPr = tbl.tblPr
        if tblPr is None:
            tblPr = OxmlElement("w:tblPr")
            tbl.insert(0, tblPr)
        borders = OxmlElement("w:tblBorders")
        for edge in ("top", "left", "bottom", "right", "insideH", "insideV"):
            el = OxmlElement(f"w:{edge}")
            el.set(qn("w:val"), "single")
            el.set(qn("w:sz"), "4")
            el.set(qn("w:space"), "0")
            el.set(qn("w:color"), "E5E7EB")
            borders.append(el)
        tblPr.append(borders)
        for idx, val in enumerate(values):
            r, c = divmod(idx, cols)
            cell = table.cell(r, c)
            cell.text = val
            for par in cell.paragraphs:
                for rn in par.runs:
                    rn.font.size = Pt(7)
                    rn.font.color.rgb = RGBColor(0x1F, 0x2A, 0x37)
        return tbl

    # Summary paragraph
    p = doc.add_paragraph()
    run = p.add_run(
        f"All indicators below are sourced from automated threat intelligence research "
        f"conducted by the ScanWave CyberIntel Platform across AlienVault OTX, ThreatFox, "
        f"and curated CTI reports, collected {now.strftime('%B %d, %Y')}. "
        f"Total unique IOCs: {total_iocs} (Malicious: {total_mal}, Suspicious: {total_sus}). "
        f"Every IOC has been verified through automated scoring and cross-referenced "
        f"against multiple threat intelligence feeds before inclusion."
    )
    run.font.size = Pt(8)
    run.font.color.rgb = RGBColor(0x1F, 0x2A, 0x37)
    new_elements.append(p._element)

    spacer = doc.add_paragraph()
    new_elements.append(spacer._element)

    # ── Major APT groups (>= 4 IOCs each) — individual sections ──
    for apt_name, iocs in sorted(major.items()):
        # Sub-header
        p = doc.add_paragraph()
        run = p.add_run(f"{apt_name} \u2014 {len(iocs)} Indicators")
        run.bold = True
        run.font.size = Pt(10.5)
        run.font.color.rgb = RGBColor(0x2D, 0x3A, 0x4A)
        new_elements.append(p._element)

        # AI summary
        summary = cache.get(apt_name, {}).get("summary", "")
        if summary:
            p = doc.add_paragraph()
            run = p.add_run(summary)
            run.font.size = Pt(8)
            run.font.color.rgb = RGBColor(0x4A, 0x55, 0x68)
            run.italic = True
            new_elements.append(p._element)

        new_elements.append(_add_ioc_table(iocs))

        spacer = doc.add_paragraph()
        new_elements.append(spacer._element)

    # ── Minor groups (< 4 IOCs) — pooled into one section ──
    if other_iocs:
        p = doc.add_paragraph()
        run = p.add_run(
            f"Additional Threat Indicators \u2014 {len(other_iocs)} IOCs "
            f"from {len(other_group_names)} Monitored Groups"
        )
        run.bold = True
        run.font.size = Pt(10.5)
        run.font.color.rgb = RGBColor(0x2D, 0x3A, 0x4A)
        new_elements.append(p._element)

        p = doc.add_paragraph()
        run = p.add_run(
            "The following indicators were identified across additional threat groups "
            "under active monitoring, each contributing a small number of IOCs: "
            + ", ".join(other_group_names) + "."
        )
        run.font.size = Pt(8)
        run.font.color.rgb = RGBColor(0x4A, 0x55, 0x68)
        run.italic = True
        new_elements.append(p._element)

        new_elements.append(_add_ioc_table(other_iocs))

        spacer = doc.add_paragraph()
        new_elements.append(spacer._element)

    # ── Step 5: Detach new elements from end of doc, insert after IOC SUMMARY ──
    for elem in new_elements:
        body.remove(elem)

    # Insert right after ioc_summary_el (ioc_idx position)
    insert_pos = list(body).index(ioc_summary_el) + 1
    for i, elem in enumerate(new_elements):
        body.insert(insert_pos + i, elem)

    # ── Save ──
    buf = BytesIO()
    doc.save(buf)
    buf.seek(0)
    return buf


@app.route("/api/blocklist/report")
def api_blocklist_report():
    """Generate and download ScanWave SOC Client Advisory DOCX."""
    try:
        buf = _generate_blocklist_report()
        now = datetime.now(timezone.utc)
        fname = f"ScanWave_SOC_Client_Advisory_{now.strftime('%d_%B%Y')}.docx"
        return Response(
            buf.getvalue(),
            mimetype="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
            headers={"Content-Disposition": f"attachment;filename={fname}"}
        )
    except Exception as e:
        import traceback
        traceback.print_exc(flush=True)
        return jsonify({"error": str(e)}), 500


@app.route("/api/messages/<channel_username>/<message_id>/context")
def api_message_context(channel_username, message_id):
    before = min(max(int(request.args.get("before", 5)), 1), 50)
    after  = min(max(int(request.args.get("after",  5)), 1), 50)
    msg_id = int(message_id)

    all_ch = [m for m in load_messages()
              if (m.get("channel_username") or m.get("channel", "unknown")) == channel_username]
    total  = len(all_ch)

    live_msgs, target_idx = fetch_live_context(channel_username, msg_id, before, after)
    if live_msgs is not None:
        return jsonify({"messages": live_msgs, "target_idx": target_idx,
                        "total": total, "source": "live"})

    all_ch.sort(key=lambda x: x.get("timestamp_utc", ""))
    idx = next((i for i, m in enumerate(all_ch)
                if str(m.get("message_id", "")) == str(message_id)), None)
    if idx is None:
        return jsonify({"messages": [], "target_idx": -1, "total": total, "source": "stored"})
    start = max(0, idx - before)
    end   = min(len(all_ch), idx + after + 1)
    return jsonify({"messages": all_ch[start:end], "target_idx": idx - start,
                    "total": total, "source": "stored"})


@app.route("/api/discovery/list")
def api_discovery_list():
    if WATCHLIST_FILE.exists():
        with open(WATCHLIST_FILE, encoding="utf-8") as f:
            data = json.load(f)
        return jsonify(data.get("all_discovered", []))
    return jsonify([])


@app.route("/api/discovery/scan", methods=["POST"])
def api_discovery_scan():
    global _scan
    if _scan["running"]:
        return jsonify({"error": "scan already running"})
    quick = (request.json or {}).get("quick", False)
    args  = ["python", "channel_discovery.py"] + (["--quick"] if quick else [])

    def _run():
        global _scan
        p = subprocess.Popen(args, cwd=str(Path(__file__).parent))
        _scan["running"] = True
        _scan["pid"]     = p.pid
        p.wait()
        _scan["running"]  = False
        _scan["last_run"] = datetime.now(timezone.utc).isoformat()

    threading.Thread(target=_run, daemon=True).start()
    return jsonify({"started": True})


@app.route("/api/discovery/status")
def api_discovery_status():
    return jsonify(_scan)


# ══════════════════════════════════════════════════════════════════════════════
# ADMIN PANEL API
# ══════════════════════════════════════════════════════════════════════════════

KEYWORDS_FILE     = OUTPUT_DIR / "keywords.json"
BACKFILL_QUEUE    = OUTPUT_DIR / "backfill_queue.json"
PENDING_FILE_VIEW = OUTPUT_DIR / "pending_channels.json"
CHANNELS_FILE     = OUTPUT_DIR / "channels_config.json"
MONITOR_LOG       = OUTPUT_DIR / "monitor.log"
AI_SUGGESTIONS        = OUTPUT_DIR / "ai_suggestions.json"
AI_BRIEF_FILE         = OUTPUT_DIR / "ai_brief.json"
AI_ENRICHED_FILE      = OUTPUT_DIR / "enriched_alerts.jsonl"
AI_STATE_FILE         = OUTPUT_DIR / "ai_agent_state.json"
ESCALATION_FILE       = OUTPUT_DIR / "escalation_status.json"
HUNTING_LEADS_FILE    = OUTPUT_DIR / "hunting_leads.json"
NETWORK_FILE          = OUTPUT_DIR / "channel_network.json"

# ── Critical Subtype Classification (mirrors telegram_monitor.py) ─────────────
_CYBER_SIGNALS = {
    # Attack types
    "ddos", "d-dos", "defacement", "defaced", "data leak", "data breach", "databreach",
    "ransomware", "ransom", "malware", "trojan", "botnet", "exploit", "sql injection",
    "sqlmap", "webshell", "shell", "backdoor", "rootkit", "c2",
    "brute force", "credential", "hacked", "hacking", "hack", "pwned", "owned",
    "breach", "breached", "leak", "dump", "wiper", "destroy",
    "root access", "full access",
    # Arabic cyber terms
    "اختراق", "تسريب", "بيانات", "قرصنة", "هاكر", "فيروس", "هجوم",
    "دي دوس", "برامج خبيثة", "رانسوم", "فدية", "مسح",
    # Jordan domain targets (domain targeting = cyber)
    ".jo", ".gov.jo", ".com.jo", ".edu.jo", ".org.jo",
    # DDoS tools / indicators
    "check-host", "dienet", "connection timed out", "connection refused",
    "layer7", "layer4", "http flood",
    # Critical infrastructure (attacks on infra = cyber)
    "bank", "بنك", "مصرف", "arab bank", "البنك العربي", "housing bank",
    "cairo amman", "القاهرة عمان", "jordan bank", "البنك الاردني", "financial", "مالي",
    "telecom", "اتصالات", "nepco", "jepco", "miyahuna", "مياهنا",
    "water authority", "electric power", "كهرباء",
}
_NATIONAL_SIGNALS = {
    # Iranian/IRGC
    "irgc", "iranian", "khamenei", "خامنئي", "حرس الثوري", "فاطميون",
    "soleimani", "سليماني", "quds force", "الحرس الثوري",
    # Resistance axis
    "hezbollah", "حزب الله", "hamas", "حماس", "qassam", "قسام", "houthi", "حوثي",
    "انصار الله", "مقاومة", "جهاد اسلامي",
    # Jordan military / security services
    "military", "عسكري", "troops", "army", "القوات المسلحة",
    "الجيش الاردني", "jordan armed forces", "القوات الجوية", "air force",
    "us base", "nato", "ain al asad", "العديد", "المفرق",
    ".mil.jo",  # military domain = national security
    "استخبارات", "intelligence", "gendarmerie", "الدرك",
    "border guard", "حرس الحدود", "مكافحة الإرهاب", "counter terrorism",
    "الأمن العام", "security directorate", "muwaffaq", "الموفق",
    # War / conflict
    "war", "حرب", "missile", "صاروخ", "escalation", "تصعيد",
    "strike", "عملية عسكرية", "military operation",
}

def _compute_critical_subtype(keyword_hits):
    """Classify a CRITICAL message by subtype using substring matching against stored keyword_hits."""
    if not keyword_hits:
        return "GENERAL"
    hits = [kw.lower() for kw in keyword_hits]
    # Substring match: signal keyword contained within the hit phrase (handles multi-word hits)
    is_cyber    = any(sig in hit for hit in hits for sig in _CYBER_SIGNALS)
    is_national = any(sig in hit for hit in hits for sig in _NATIONAL_SIGNALS)
    if is_cyber and is_national: return "BOTH"
    if is_cyber:    return "CYBER"
    if is_national: return "NATIONAL"
    return "GENERAL"


def _load_channels_config():
    """Load channels: start with hardcoded CHANNEL_TIERS, overlay with saved config."""
    base = {k: dict(v) for k, v in CHANNEL_TIERS.items()}
    if CHANNELS_FILE.exists():
        try:
            saved = json.loads(CHANNELS_FILE.read_text(encoding="utf-8"))
            base.update(saved)
        except Exception:
            pass
    return base


def _save_channels_config(cfg):
    CHANNELS_FILE.write_text(json.dumps(cfg, ensure_ascii=False, indent=2), encoding="utf-8")


@app.route("/api/admin/status")
def api_admin_status():
    """System health: monitor process, DB stats, cursor, log tail."""
    import subprocess as _sp
    # Check if monitor is running (look for telegram_monitor.py in process list)
    monitor_running = False
    try:
        import os as _os
        for _pid in _os.listdir("/proc"):
            if not _pid.isdigit():
                continue
            try:
                _cmd = open(f"/proc/{_pid}/cmdline", "rb").read().replace(b"\x00", b" ").decode()
                if "telegram_monitor.py" in _cmd:
                    monitor_running = True
                    break
            except Exception:
                continue
    except Exception:
        try:
            result = _sp.run(["tasklist", "/FI", "IMAGENAME eq python.exe", "/FO", "CSV"],
                             capture_output=True, text=True, timeout=5)
            monitor_running = "python" in result.stdout.lower()
        except Exception:
            pass

    cursor = {}
    if (OUTPUT_DIR / "last_seen.json").exists():
        try:
            cursor = json.loads((OUTPUT_DIR / "last_seen.json").read_text(encoding="utf-8"))
        except Exception:
            pass

    # DB stats
    msgs = load_messages()
    crit = sum(1 for m in msgs if m.get("priority") == "CRITICAL")
    med  = sum(1 for m in msgs if m.get("priority") == "MEDIUM")
    chs  = len(set(m.get("channel_username","") for m in msgs if m.get("channel_username")))
    iocs = sum(len(v or []) for m in msgs for v in (m.get("iocs") or {}).values())
    last_ts = max((m.get("timestamp_utc","") for m in msgs), default="")

    # Last 30 lines of monitor log
    log_tail = []
    if MONITOR_LOG.exists():
        try:
            lines = MONITOR_LOG.read_text(encoding="utf-8", errors="replace").splitlines()
            log_tail = lines[-30:]
        except Exception:
            pass

    # Backfill queue status
    bfq = {}
    if BACKFILL_QUEUE.exists():
        try:
            bfq = json.loads(BACKFILL_QUEUE.read_text(encoding="utf-8"))
        except Exception:
            pass

    return jsonify({
        "monitor_running": monitor_running,
        "cursor": cursor,
        "db": {"total": len(msgs), "critical": crit, "medium": med,
               "channels": chs, "iocs": iocs, "last_message": last_ts},
        "log_tail": log_tail,
        "backfill_queue": bfq,
    })


@app.route("/api/admin/keywords", methods=["GET"])
def api_admin_keywords_get():
    if KEYWORDS_FILE.exists():
        try:
            return jsonify(json.loads(KEYWORDS_FILE.read_text(encoding="utf-8")))
        except Exception:
            pass
    return jsonify({"critical": [], "medium": []})


@app.route("/api/admin/keywords", methods=["POST"])
def api_admin_keywords_post():
    data = request.get_json(force=True)
    crit = [str(k).strip() for k in data.get("critical", []) if str(k).strip()]
    med  = [str(k).strip() for k in data.get("medium",   []) if str(k).strip()]
    KEYWORDS_FILE.write_text(
        json.dumps({"critical": crit, "medium": med}, ensure_ascii=False, indent=2),
        encoding="utf-8")
    return jsonify({"ok": True, "critical": len(crit), "medium": len(med),
                    "note": "Restart monitor for changes to take effect"})


@app.route("/api/admin/channels", methods=["GET"])
def api_admin_channels_get():
    cfg = _load_channels_config()
    return jsonify(cfg)


@app.route("/api/admin/channels", methods=["POST"])
def api_admin_channels_post():
    """Add or update a channel entry."""
    data = request.get_json(force=True)
    username = data.get("username", "").strip().lstrip("@")
    if not username:
        return jsonify({"ok": False, "error": "username required"}), 400
    cfg = _load_channels_config()
    cfg[username] = {
        "tier":   int(data.get("tier", 3)),
        "label":  data.get("label", username),
        "threat": data.get("threat", "MEDIUM"),
        "status": data.get("status", "active"),
    }
    _save_channels_config(cfg)
    # Also add to CHANNEL_TIERS runtime dict
    CHANNEL_TIERS[username] = cfg[username]
    # Add to pending file so live monitor joins it
    pf_data = {"pending": [], "processed": []}
    if PENDING_FILE_VIEW.exists():
        try:
            pf_data = json.loads(PENDING_FILE_VIEW.read_text(encoding="utf-8"))
        except Exception:
            pass
    if username not in pf_data.get("pending", []) and username not in pf_data.get("processed", []):
        pf_data.setdefault("pending", []).append(username)
        PENDING_FILE_VIEW.write_text(json.dumps(pf_data, indent=2, ensure_ascii=False), encoding="utf-8")
    return jsonify({"ok": True, "channel": username, "config": cfg[username]})


@app.route("/api/admin/channels/<username>", methods=["DELETE"])
def api_admin_channels_delete(username):
    cfg = _load_channels_config()
    if username in cfg:
        del cfg[username]
        _save_channels_config(cfg)
        CHANNEL_TIERS.pop(username, None)
    return jsonify({"ok": True, "removed": username})


@app.route("/api/admin/backfill", methods=["POST"])
def api_admin_backfill():
    """Queue a backfill request — picked up by live monitor within 60s."""
    data     = request.get_json(force=True)
    channel  = data.get("channel", "").strip().lstrip("@")
    limit    = min(int(data.get("limit", 500)), 2000)
    since    = data.get("since", "")
    if not channel:
        return jsonify({"ok": False, "error": "channel required"}), 400

    req = {"channel": channel, "limit": limit, "queued_at": datetime.now(timezone.utc).isoformat()}
    if since:
        req["since"] = since

    bfq = {"pending": [], "completed": []}
    if BACKFILL_QUEUE.exists():
        try:
            bfq = json.loads(BACKFILL_QUEUE.read_text(encoding="utf-8"))
        except Exception:
            pass
    bfq.setdefault("pending", []).append(req)
    BACKFILL_QUEUE.write_text(json.dumps(bfq, ensure_ascii=False, indent=2), encoding="utf-8")
    return jsonify({"ok": True, "queued": req,
                    "note": "Monitor will process within 60 seconds"})


@app.route("/api/admin/compact", methods=["POST"])
def api_admin_compact():
    """Deduplicate and sort messages.jsonl in-place."""
    mf = OUTPUT_DIR / "messages.jsonl"
    if not mf.exists():
        return jsonify({"ok": False, "error": "messages.jsonl not found"})
    seen, msgs = {}, []
    for line in mf.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            m = json.loads(line)
            key = f"{m.get('channel_username','')}_{m.get('message_id','')}"
            if key not in seen:
                seen[key] = True
                msgs.append(m)
        except Exception:
            pass
    msgs.sort(key=lambda x: x.get("timestamp_utc", ""))
    mf.write_text("\n".join(json.dumps(m, ensure_ascii=False) for m in msgs) + "\n", encoding="utf-8")
    # Bust cache
    global _msg_cache_mtime, _msg_cache_data
    _msg_cache_mtime = 0
    _msg_cache_data  = []
    return jsonify({"ok": True, "unique": len(msgs),
                    "critical": sum(1 for m in msgs if m.get("priority")=="CRITICAL")})


@app.route("/api/stats/summary")
def api_stats_summary():
    """Lightweight real-time stats for the status bar — low-cost poll."""
    messages = load_messages()
    now = datetime.now(timezone.utc)
    cutoff_24h = (now - timedelta(hours=24)).isoformat()
    cutoff_1h  = (now - timedelta(hours=1)).isoformat()
    total, crit, med, crit_24h, crit_1h = 0, 0, 0, 0, 0
    channels = set()
    ioc_count = 0
    for m in messages:
        total += 1
        p  = m.get("priority","LOW")
        ts = m.get("timestamp_utc","")
        ch = m.get("channel_username","")
        if ch: channels.add(ch)
        ioc_count += sum(len(v or []) for v in (m.get("iocs") or {}).values())
        if p == "CRITICAL":
            crit += 1
            if ts >= cutoff_24h: crit_24h += 1
            if ts >= cutoff_1h:  crit_1h  += 1
        elif p == "MEDIUM":
            med += 1
    return jsonify({
        "total":       total,
        "critical":    crit,
        "medium":      med,
        "critical_24h": crit_24h,
        "critical_1h":  crit_1h,
        "channels":    len(channels),
        "iocs":        ioc_count,
        "generated_at": now.isoformat(),
    })


@app.route("/api/admin/discovered")
def api_admin_discovered():
    """Return live-discovery engine results (discovered_channels.json)."""
    disc_file = OUTPUT_DIR / "discovered_channels.json"
    if not disc_file.exists():
        return jsonify({})
    try:
        return jsonify(json.loads(disc_file.read_text(encoding="utf-8")))
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/admin/discovered/<action>/<username>", methods=["POST"])
def api_admin_discovered_action(action, username):
    """
    Actions on a discovered channel:
      approve  — add to CHANNEL_TIERS + queue join
      dismiss  — mark as dismissed so it stops appearing
      ignore   — same as dismiss but keeps low-priority entries hidden
    """
    disc_file = OUTPUT_DIR / "discovered_channels.json"
    if not disc_file.exists():
        return jsonify({"error": "no discovery data"}), 404
    try:
        data = json.loads(disc_file.read_text(encoding="utf-8"))
        uname = username.lower().lstrip("@")
        if uname not in data:
            return jsonify({"error": "channel not found"}), 404
        if action == "approve":
            body = request.json or {}
            tier   = int(body.get("tier", 3))
            threat = body.get("threat", "MEDIUM")
            label  = body.get("label", username)
            # Add to CHANNEL_TIERS runtime + config file
            CHANNEL_TIERS[uname] = {"label": label, "tier": tier,
                                    "threat": threat, "status": "active"}
            cfg = _load_channels_config()
            cfg[uname] = CHANNEL_TIERS[uname]
            _save_channels_config(cfg)
            # Queue for join
            pending_path = PENDING_FILE_VIEW
            pdata = {}
            if pending_path.exists():
                try:
                    pdata = json.loads(pending_path.read_text(encoding="utf-8"))
                except Exception:
                    pass
            pl = pdata.get("pending", [])
            if uname not in pl and uname not in pdata.get("processed", []):
                pl.append(uname)
            pdata["pending"]    = pl
            pdata["updated_at"] = datetime.now(timezone.utc).isoformat()
            pending_path.write_text(json.dumps(pdata, indent=2, ensure_ascii=False),
                                    encoding="utf-8")
            data[uname]["status"] = "approved"
        elif action in ("dismiss", "ignore"):
            data[uname]["status"] = "dismissed"
        else:
            return jsonify({"error": "unknown action"}), 400
        disc_file.write_text(json.dumps(data, indent=2, ensure_ascii=False),
                             encoding="utf-8")
        return jsonify({"ok": True, "action": action, "username": uname})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


# ══════════════════════════════════════════════════════════════════════════════
# AI AGENT API
# ══════════════════════════════════════════════════════════════════════════════

_ai_running = {"status": "idle", "started": None}


@app.route("/api/ai/status")
def api_ai_status():
    agent_state = {}
    if AI_STATE_FILE.exists():
        try:
            agent_state = json.loads(AI_STATE_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    brief = None
    if AI_BRIEF_FILE.exists():
        try:
            brief = json.loads(AI_BRIEF_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    # Check if ai_agent.py process is running
    import psutil
    agent_running = False
    try:
        for p in psutil.process_iter(['pid', 'cmdline']):
            if p.info['cmdline'] and 'ai_agent.py' in ' '.join(p.info['cmdline']):
                agent_running = True
                break
    except Exception:
        pass
    return jsonify({
        "agent_running": agent_running,
        "enrichments_done": agent_state.get("enrichments_done", 0),
        "keywords_added": agent_state.get("keywords_added", 0),
        "channels_autoapproved": agent_state.get("channels_autoapproved", 0),
        "channels_autodismissed": agent_state.get("channels_autodismissed", 0),
        "briefs_generated": agent_state.get("briefs_generated", 0),
        "last_kw_run": agent_state.get("last_kw_run"),
        "last_brief_run": agent_state.get("last_brief_run"),
        "latest_brief": brief,
    })


@app.route("/api/ai/suggestions")
def api_ai_suggestions():
    if not AI_SUGGESTIONS.exists():
        return jsonify({"runs": [], "latest": None})
    try:
        return jsonify(json.loads(AI_SUGGESTIONS.read_text(encoding="utf-8")))
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/ai/brief")
def api_ai_brief():
    """Latest AI-generated threat intelligence brief."""
    if not AI_BRIEF_FILE.exists():
        return jsonify({"error": "no brief available yet"})
    try:
        return jsonify(json.loads(AI_BRIEF_FILE.read_text(encoding="utf-8")))
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/translate", methods=["POST"])
def api_translate():
    """On-demand translation of a message text via OpenAI gpt-4o-mini."""
    data = request.get_json(force=True) or {}
    text = (data.get("text") or "")[:2000]
    if not text:
        return jsonify({"error": "no text provided"}), 400
    api_key = os.environ.get("OPENAI_API_KEY", "")
    if not api_key:
        return jsonify({"error": "OPENAI_API_KEY not configured"}), 503
    try:
        from openai import OpenAI as _OAI
        client = _OAI(api_key=api_key)
        r = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content":
                    "You are a professional translator. Translate the following text to English. "
                    "Return ONLY the English translation — no explanations, no quoting the original."},
                {"role": "user", "content": text},
            ],
            max_tokens=600,
            temperature=0.1,
        )
        translation = r.choices[0].message.content.strip()
        return jsonify({"translation": translation})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/escalation/status")
def api_escalation_status():
    """Current escalation state from LOOP 6 (updated every 15 min)."""
    if not ESCALATION_FILE.exists():
        return jsonify({
            "escalation_detected": False,
            "urgency": "NONE",
            "signals": [],
            "summary": "No data yet — LOOP 6 starts after first 15-minute cycle",
            "recommended_action": "",
            "checked_at": None,
        })
    try:
        return jsonify(json.loads(ESCALATION_FILE.read_text(encoding="utf-8")))
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/hunting/leads")
def api_hunting_leads():
    """Group and operation leads from LOOP 5 Threat Hunter."""
    if not HUNTING_LEADS_FILE.exists():
        return jsonify({"group_leads": [], "operation_leads": [], "runs": []})
    try:
        data = json.loads(HUNTING_LEADS_FILE.read_text(encoding="utf-8"))
        # Sort by confidence descending, return top 100
        data["group_leads"] = sorted(
            data.get("group_leads", []),
            key=lambda x: -int(x.get("confidence", 0))
        )[:100]
        data["operation_leads"] = sorted(
            data.get("operation_leads", []),
            key=lambda x: -int(x.get("confidence", 0))
        )[:50]
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/network/graph")
def api_network_graph():
    """Channel relationship graph summary from LOOP 7."""
    if not NETWORK_FILE.exists():
        return jsonify({
            "generated_at": None,
            "monitored_channels": 0,
            "unknown_channels_scored": 0,
            "newly_queued": 0,
            "top_unknown": [],
            "edges": [],
        })
    try:
        data = json.loads(NETWORK_FILE.read_text(encoding="utf-8"))
        # Trim edges for API response — return top 50 only
        data["edges"] = data.get("edges", [])[:50]
        return jsonify(data)
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/ai/enriched")
def api_ai_enriched():
    """Latest N AI-enriched critical alerts."""
    limit = min(int(request.args.get("limit", 20)), 100)
    if not AI_ENRICHED_FILE.exists():
        return jsonify([])
    try:
        lines = AI_ENRICHED_FILE.read_text(encoding="utf-8").splitlines()
        records = []
        for line in reversed(lines):
            line = line.strip()
            if not line:
                continue
            try:
                records.append(json.loads(line))
                if len(records) >= limit:
                    break
            except Exception:
                pass
        return jsonify(list(reversed(records)))
    except Exception as e:
        return jsonify({"error": str(e)}), 500


CHAT_HISTORY_FILE = OUTPUT_DIR / "chat_history.json"

# ── httpx compat patch so openai works inside viewer too ──────────────────────
try:
    import httpx as _vhttpx
    _vorig_client = _vhttpx.Client.__init__
    def _vp_client(self, *a, **kw):
        kw.pop("proxies", None); _vorig_client(self, *a, **kw)
    _vhttpx.Client.__init__ = _vp_client
    _vorig_async = _vhttpx.AsyncClient.__init__
    def _vp_async(self, *a, **kw):
        kw.pop("proxies", None); _vorig_async(self, *a, **kw)
    _vhttpx.AsyncClient.__init__ = _vp_async
except Exception:
    pass

def _chat_openai_client():
    key = os.environ.get("OPENAI_API_KEY", "")
    if not key:
        # Try reading .env directly
        env_path = Path(__file__).parent / ".env"
        if env_path.exists():
            for ln in env_path.read_text(encoding="utf-8").splitlines():
                ln = ln.strip()
                if ln.startswith("OPENAI_API_KEY="):
                    key = ln.split("=", 1)[1].strip().strip('"').strip("'")
                    os.environ["OPENAI_API_KEY"] = key
                    break
    if not key:
        return None
    try:
        from openai import OpenAI
        return OpenAI(api_key=key)
    except Exception:
        return None

# Synonym expansion — common intel query terms mapped to domain-specific search terms
_CHAT_SYNONYMS = {
    "bank":       ["jcbank","arab bank","housing bank","bank of jordan","capital bank","capitalbank","cairo amman","etihad bank","البنك","بنك",".jo","ahli bank","jordan ahli","jordan kuwait bank","jkb"],
    "banks":      ["jcbank","arab bank","housing bank","bank of jordan","capital bank","capitalbank","cairo amman","etihad bank","البنك","بنك",".jo","ahli bank","jordan ahli","jordan kuwait bank","jkb"],
    "jordanian":  ["jordan","الاردن","الأردن","أردن","اردن",".jo","amman","عمان"],
    "jordan":     ["الاردن","الأردن","أردن","اردن",".jo","amman","عمان"],
    "government": ["ministry","وزارة","الديوان","royal court","prime minister","رئاسة الوزراء","gov.jo"],
    "ministry":   ["وزارة","ministry of","الديوان","gov.jo"],
    "attack":     ["ddos","hacked","breach","defaced","down","offline","closed","تم اختراق","اختراق","هكر","check-host"],
    "attacks":    ["ddos","hacked","breach","defaced","down","offline","closed","تم اختراق","اختراق","check-host"],
    "hack":       ["hacked","breach","defaced","leak","dump","تسريب","تم اختراق","اختراق"],
    "hacked":     ["breach","defaced","leak","dump","تسريب","تم اختراق","check-host"],
    "breach":     ["hacked","leak","dump","data","database","تسريب","credentials"],
    "ddos":       ["down","offline","closed","connection refused","check-host","flood","layer7","layer4","http flood"],
    "leak":       ["dump","تسريب","data","database","credentials","pastebin"],
    "data":       ["leak","dump","database","تسريب","credentials","passwords"],
    "israel":     ["إسرائيل","زيونيست","zionist","صهيوني","idf","israeli","tel aviv"],
    "iran":       ["إيران","islamic resistance","حزب الله","hezbollah","fatemiyoun","فاطميون","irgc"],
    "critical":   ["CRITICAL"],
    "recent":     [],
    "latest":     [],
    "today":      [],
    "new":        [],
    "any":        [],
}

def _extract_search_query(user_msg: str, history: list) -> str:
    """Use gpt-4o-mini to extract optimal search terms from conversation context.
    For first messages or clearly self-contained queries, skip the GPT call."""
    meaningful_words = [w for w in re.split(r'\W+', user_msg.lower()) if len(w) > 2]
    has_pronouns = any(w in user_msg.lower() for w in (
        "that", "this", "those", "these", "them", "it", "they",
        "more", "above", "previous", "earlier", "same", "again"
    ))
    if not history or (len(meaningful_words) >= 5 and not has_pronouns):
        return user_msg
    client = _chat_openai_client()
    if not client:
        return user_msg
    recent = history[-6:]
    context_lines = []
    for h in recent:
        role = h.get("role", "")
        content = str(h.get("content", ""))[:300]
        if role in ("user", "assistant"):
            context_lines.append(f"{role}: {content}")
    try:
        resp = client.chat.completions.create(
            model="gpt-4o-mini",
            messages=[
                {"role": "system", "content": (
                    "You extract search keywords from a conversation. "
                    "Given the conversation history and the user's latest message, "
                    "output 3-8 specific search terms/phrases that would find the relevant Telegram messages. "
                    "Include entity names, attack types, dates, and channel names mentioned in context. "
                    "Output ONLY the search terms separated by spaces. No explanation."
                )},
                {"role": "user", "content": (
                    f"Conversation:\n" + "\n".join(context_lines) +
                    f"\n\nLatest user message: {user_msg}\n\nSearch terms:"
                )}
            ],
            max_tokens=100,
            temperature=0,
        )
        extracted = resp.choices[0].message.content.strip()
        return f"{user_msg} {extracted}"
    except Exception:
        return user_msg


def _search_messages_for_chat(query: str, limit: int = 500) -> list:
    """
    Score messages by relevance to query.
    Strategy:
      1. Expand query words with domain synonyms
      2. Score all messages by keyword hits + strong recency boost
      3. Always inject last 100 messages + all CRITICALs as baseline
      4. Return sorted chronologically so AI sees a timeline
    """
    msgs = load_messages()
    now_utc = datetime.now(timezone.utc)

    def _recency_boost(ts_str):
        """Massive boost for recent messages so 'now/today' queries work."""
        if not ts_str:
            return 0
        try:
            dt = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            age_h = (now_utc - dt).total_seconds() / 3600
            if age_h < 1:    return 30   # last hour — highest priority
            if age_h < 6:    return 15   # last 6h
            if age_h < 24:   return 8    # today
            if age_h < 72:   return 3    # last 3 days
            return 0
        except Exception:
            return 0

    # Base query words
    base_words = [w for w in re.split(r'\W+', query.lower()) if len(w) > 2]

    # Detect if user is asking about "now/today/current/latest/recent"
    recency_query = any(w in query.lower() for w in (
        "now", "today", "current", "latest", "recent", "right now",
        "happening", "new", "just", "currently", "active", "ongoing"
    ))

    # Expand with synonyms
    expanded = list(set(base_words))
    for w in base_words:
        for syn in _CHAT_SYNONYMS.get(w, []):
            expanded.append(syn.lower())

    prio_boost = {"CRITICAL": 4, "HIGH": 2, "MEDIUM": 1, "LOW": 0}
    seen_ids = {}

    for m in msgs:
        mid = f"{m.get('channel_username','')}_{m.get('message_id','')}"
        text   = (m.get("text_preview") or "").lower()
        ch     = (m.get("channel") or "").lower()
        uname  = (m.get("channel_username") or "").lower()
        ae     = m.get("ai_enrichment") or {}
        enrich = " ".join(str(v) for v in ae.values()).lower() if ae else ""
        kwhits = " ".join(m.get("keyword_hits") or []).lower()

        score = 0
        for w in expanded:
            if w in text:    score += 2
            if w in ch:      score += 3
            if w in uname:   score += 3
            if w in enrich:  score += 2
            if w in kwhits:  score += 2
        score += prio_boost.get(m.get("priority", "LOW"), 0)
        score += _recency_boost(m.get("timestamp_utc", ""))

        # For recency queries, give all messages a base score so recent ones appear
        if recency_query:
            score = max(score, _recency_boost(m.get("timestamp_utc", "")))

        if score > 0:
            seen_ids[mid] = (score, m)

    # Top keyword-ranked results
    ranked = sorted(seen_ids.values(), key=lambda x: x[0], reverse=True)
    result = [m for _, m in ranked[:limit]]
    result_set = {f"{m.get('channel_username','')}_{m.get('message_id','')}" for m in result}

    # Always inject last 100 messages (regardless of keyword match) — captures live events
    recent_all = sorted(msgs, key=lambda m: m.get("timestamp_utc", ""), reverse=True)[:100]
    for m in recent_all:
        mid = f"{m.get('channel_username','')}_{m.get('message_id','')}"
        if mid not in result_set:
            result.append(m)
            result_set.add(mid)

    # Always inject ALL CRITICAL messages as baseline
    recent_crits = sorted(
        [m for m in msgs if m.get("priority") == "CRITICAL"],
        key=lambda m: m.get("timestamp_utc", ""),
        reverse=True
    )
    for m in recent_crits:
        mid = f"{m.get('channel_username','')}_{m.get('message_id','')}"
        if mid not in result_set:
            result.append(m)
            result_set.add(mid)

    # Sort final list chronologically — AI reads a timeline, not a random pile
    result.sort(key=lambda m: m.get("timestamp_utc", ""))
    return result


def _search_messages_for_chat_v2(search_query: str, original_query: str, limit: int = 150) -> list:
    """V2 context retrieval: relevance-focused, no context flooding."""
    msgs = load_messages()
    now_utc = datetime.now(timezone.utc)

    def _recency_boost(ts_str):
        if not ts_str:
            return 0
        try:
            dt = datetime.fromisoformat(ts_str.replace("Z", "+00:00"))
            if dt.tzinfo is None:
                dt = dt.replace(tzinfo=timezone.utc)
            age_h = (now_utc - dt).total_seconds() / 3600
            if age_h < 1:    return 30
            if age_h < 6:    return 15
            if age_h < 24:   return 8
            if age_h < 72:   return 3
            return 0
        except Exception:
            return 0

    combined = f"{search_query} {original_query}"
    base_words = list(set(w for w in re.split(r'\W+', combined.lower()) if len(w) > 2))

    recency_query = any(w in original_query.lower() for w in (
        "now", "today", "current", "latest", "recent", "right now",
        "happening", "new", "just", "currently", "active", "ongoing"
    ))

    expanded = list(set(base_words))
    for w in base_words:
        for syn in _CHAT_SYNONYMS.get(w, []):
            expanded.append(syn.lower())

    prio_boost = {"CRITICAL": 4, "HIGH": 2, "MEDIUM": 1, "LOW": 0}
    seen_ids = {}

    for m in msgs:
        mid = f"{m.get('channel_username','')}_{m.get('message_id','')}"
        text   = (m.get("text_preview") or "").lower()
        ch     = (m.get("channel") or "").lower()
        uname  = (m.get("channel_username") or "").lower()
        ae     = m.get("ai_enrichment") or {}
        enrich = " ".join(str(v) for v in ae.values()).lower() if ae else ""
        kwhits = " ".join(m.get("keyword_hits") or []).lower()

        score = 0
        for w in expanded:
            if w in text:    score += 2
            if w in ch:      score += 3
            if w in uname:   score += 3
            if w in enrich:  score += 2
            if w in kwhits:  score += 2
        score += prio_boost.get(m.get("priority", "LOW"), 0)
        score += _recency_boost(m.get("timestamp_utc", ""))

        if recency_query:
            score = max(score, _recency_boost(m.get("timestamp_utc", "")))

        if score > 0:
            seen_ids[mid] = (score, m)

    ranked = sorted(seen_ids.values(), key=lambda x: x[0], reverse=True)
    result = [m for _, m in ranked[:limit]]
    result_set = {f"{m.get('channel_username','')}_{m.get('message_id','')}" for m in result}

    # Only inject recent messages if recency query (25, not 100)
    if recency_query:
        recent_all = sorted(msgs, key=lambda m: m.get("timestamp_utc", ""), reverse=True)[:25]
        for m in recent_all:
            mid = f"{m.get('channel_username','')}_{m.get('message_id','')}"
            if mid not in result_set:
                result.append(m)
                result_set.add(mid)

    # Only CRITICAL from last 7 days, cap at 50
    seven_days_ago = (now_utc - timedelta(days=7)).isoformat()
    recent_crits = [
        m for m in msgs
        if m.get("priority") == "CRITICAL"
        and (m.get("timestamp_utc", "") >= seven_days_ago)
    ]
    recent_crits.sort(key=lambda m: m.get("timestamp_utc", ""), reverse=True)
    for m in recent_crits[:50]:
        mid = f"{m.get('channel_username','')}_{m.get('message_id','')}"
        if mid not in result_set:
            result.append(m)
            result_set.add(mid)

    result.sort(key=lambda m: m.get("timestamp_utc", ""))
    return result


def _format_msg_for_context(idx: int, m: dict) -> str:
    """Format a single message for the AI context block.
    Uses sequential index (idx) as the REF ID — guaranteed unique across all channels."""
    ts    = (m.get("timestamp_utc") or "")[:16].replace("T", " ")
    pri   = m.get("priority", "LOW")
    ch    = m.get("channel") or m.get("channel_username", "?")
    uname = m.get("channel_username", "")
    text  = (m.get("text_preview") or "")[:500]
    lines = [f"[REF:{idx}] [{pri}] {ts} UTC | @{uname} | {ch}", text]
    ae = m.get("ai_enrichment") or {}
    if ae.get("summary"):
        lines.append(f"  >> AI: {ae['summary'][:250]}")
    if ae.get("target_sector"):
        lines.append(f"  >> Target: {ae['target_sector']} | Severity: {ae.get('severity','')} | Confidence: {ae.get('confidence','')}%")
    kw = m.get("keyword_hits") or []
    if kw:
        lines.append(f"  >> Keywords: {', '.join(kw[:10])}")
    return "\n".join(lines)

_CHAT_SYSTEM_TEMPLATE = """You are a senior cyber threat intelligence analyst for the Scanwave CyberIntel Platform.
You monitor hacktivist and state-linked threat actor activity targeting Jordan and the wider Middle East.

TODAY'S DATE/TIME (UTC): {now_utc}

You are given a numbered context of Telegram messages from monitored threat-actor channels, each tagged [REF:N].
The messages are sorted OLDEST FIRST — the most recent messages are at the END of the context.
Your job is to answer the analyst's question using ONLY this evidence. Be thorough, precise, and analytical.

Rules:
- Cite every [REF:N] tag that supports a claim. Multiple refs per claim are encouraged.
- If a message is in Arabic, translate the key parts in your answer.
- Group findings by threat actor or attack type when it makes sense.
- When asked about "now/today/current", focus on messages from today's date ({today}).
- If the context truly contains no relevant information for the specific date asked, say so clearly — do NOT fabricate.
- Respond ONLY in this exact JSON format (no markdown, no code fences):
  {{"answer":"full detailed answer","references":[0,1,2,...]}}

The "references" array must contain INTEGER indices (0,1,2...) matching the [REF:N] numbers used."""

_CHAT_SYSTEM_TEMPLATE_V2 = """You are a senior cyber threat intelligence analyst for the Scanwave CyberIntel Platform.
You monitor hacktivist and state-linked threat actor activity targeting Jordan and the wider Middle East.

TODAY'S DATE/TIME (UTC): {now_utc}

You are given a numbered context of Telegram messages from monitored threat-actor channels, each tagged [REF:N].
The messages are sorted OLDEST FIRST — the most recent messages are at the END of the context.
Your job is to answer the analyst's question using ONLY this evidence.

ALWAYS respond in English. Translate any Arabic or Farsi content inline.

RESPONSE MODES:
1. **Q&A mode** (default): Be brief, factual, and precise. Cite [REF:N] tags inline.
2. **Report mode** (when user asks to "generate report", "write report", "summarize all", "full analysis"):
   Use this structured format:
   # Report Title
   **Date:** {today} | **Scope:** [describe]
   ## Executive Summary
   [2-3 sentence overview]
   ## Key Findings
   [Group by threat actor or attack type, use bullet points, cite [REF:N]]
   ## Indicators of Compromise
   | Type | Value | Source |
   |------|-------|--------|
   [table rows from context]
   ## Risk Assessment
   [Brief risk level and impact analysis]
   ## Recommendations
   [Actionable bullet points]

Rules:
- Cite [REF:N] tags that support each claim. Multiple refs per claim encouraged.
- Use **bold** for emphasis, bullet lists, and numbered lists as needed.
- When asked about "now/today/current", focus on messages from today's date ({today}).
- If the context contains no relevant information, say so clearly — do NOT fabricate.
- After your complete answer, write exactly this delimiter on its own line:
  ---REFS---
  Then list ALL referenced numbers as comma-separated integers. Example: 3, 7, 12, 45
- If you cited no references, still write ---REFS--- followed by nothing."""

# ── Agentic search: GPT tool-calling for iterative intel retrieval ─────

_SEARCH_INTEL_TOOL = {
    "type": "function",
    "function": {
        "name": "search_intel",
        "description": (
            "Search the Telegram intelligence message database. "
            "Returns messages matching the query, formatted with [REF:N] tags for citation. "
            "Call multiple times with different queries for comprehensive coverage. "
            "Use specific terms: target names, domains (.jo, gov.jo), attack types, actor names, Arabic keywords."
        ),
        "parameters": {
            "type": "object",
            "properties": {
                "query": {
                    "type": "string",
                    "description": "Search terms: target names, domains, attack types (DDoS, breach, leak, defacement), actor names, Arabic/English keywords"
                },
                "severity": {
                    "type": "string",
                    "enum": ["all", "CRITICAL", "MEDIUM", "LOW"],
                    "description": "Filter by severity. Default: all"
                },
                "days_back": {
                    "type": "integer",
                    "description": "How many days back to search. Default: 365"
                }
            },
            "required": ["query"]
        }
    }
}


def _format_msg_compact(idx: int, m: dict) -> str:
    """Compact message format for tool search results — optimized for token budget.
    Arabic text tokenizes at 2-4x English rate, so keep text short."""
    ts    = (m.get("timestamp_utc") or "")[:16].replace("T", " ")
    pri   = m.get("priority", "LOW")
    uname = m.get("channel_username", "?")
    text  = (m.get("text_preview") or "")[:150]
    ae    = m.get("ai_enrichment") or {}
    summary = (ae.get("summary") or "")[:120]
    kw = m.get("keyword_hits") or []
    # Prefer English summary over raw Arabic text when available
    if summary:
        return f"[REF:{idx}] [{pri}] {ts} | @{uname}\n>> {summary}\n>> KW: {', '.join(kw[:5])}"
    line = f"[REF:{idx}] [{pri}] {ts} | @{uname}\n{text}"
    if kw:
        line += f"\n>> KW: {', '.join(kw[:5])}"
    return line


def _execute_search_tool(query: str, severity: str, days_back: int,
                         seen_ids: set, all_ref_msgs: list,
                         all_msgs: list) -> tuple:
    """Execute an agentic search, return (count, formatted_text).
    Maintains global REF numbering across calls via all_ref_msgs/seen_ids."""
    now_utc = datetime.now(timezone.utc)
    cutoff = (now_utc - timedelta(days=days_back)).isoformat() if days_back < 365 else ""

    base_words = [w for w in re.split(r'\W+', query.lower()) if len(w) > 2]
    expanded = list(set(base_words))
    for w in base_words:
        for syn in _CHAT_SYNONYMS.get(w, []):
            expanded.append(syn.lower())
    # Also add the raw query terms (including short ones like ".jo")
    for part in query.lower().split():
        part = part.strip(".,;:!?")
        if part and part not in expanded:
            expanded.append(part)

    prio_boost = {"CRITICAL": 4, "HIGH": 2, "MEDIUM": 1, "LOW": 0}
    scored = []

    for m in all_msgs:
        mid = f"{m.get('channel_username','')}_{m.get('message_id','')}"
        if mid in seen_ids:
            continue
        if cutoff and (m.get("timestamp_utc", "") < cutoff):
            continue
        if severity != "all" and m.get("priority") != severity:
            continue

        text  = (m.get("text_preview") or "").lower()
        ch    = (m.get("channel") or "").lower()
        uname = (m.get("channel_username") or "").lower()
        ae    = m.get("ai_enrichment") or {}
        enrich = " ".join(str(v) for v in ae.values()).lower() if ae else ""
        kwhits = " ".join(m.get("keyword_hits") or []).lower()

        score = 0
        for w in expanded:
            if w in text:    score += 2
            if w in ch:      score += 3
            if w in uname:   score += 3
            if w in enrich:  score += 2
            if w in kwhits:  score += 2
        score += prio_boost.get(m.get("priority", "LOW"), 0)
        # Severity-filtered searches: give base score so results appear even without keyword match
        if severity != "all" and score == 0:
            score = 1

        if score > 0:
            scored.append((score, m, mid))

    scored.sort(key=lambda x: x[0], reverse=True)

    results = []
    for score, m, mid in scored[:30]:
        ref_idx = len(all_ref_msgs)
        all_ref_msgs.append(m)
        seen_ids.add(mid)
        results.append((ref_idx, m))

    if not results:
        return 0, f"No messages found matching '{query}'"

    results.sort(key=lambda x: x[1].get("timestamp_utc", ""))
    blocks = [_format_msg_compact(ref_idx, m) for ref_idx, m in results]
    formatted = f"Found {len(results)} messages:\n" + "\n---\n".join(blocks)

    if len(formatted) > 10000:
        formatted = formatted[:10000] + "\n[...truncated, try a more specific query]"

    return len(results), formatted


_CHAT_SYSTEM_TEMPLATE_V3 = """You are a senior cyber threat intelligence analyst for the Scanwave CyberIntel Platform.
You monitor hacktivist and state-linked threat actor activity targeting Jordan and the wider Middle East.

TODAY'S DATE/TIME (UTC): {now_utc}

DATABASE: {total_msgs} messages from {total_channels} monitored Telegram channels ({critical_count} CRITICAL, {medium_count} MEDIUM, {low_count} LOW).

You have a **search_intel** tool to query the message database. Each search returns up to 50 messages with [REF:N] citation tags.

ALWAYS respond in English. Translate any Arabic/Farsi content inline.

SEARCH STRATEGY:
- For simple questions: 1-2 focused searches
- For comprehensive requests ("full report", "name all", "everything", "all sectors"):
  * FIRST: search severity="CRITICAL" to get all high-priority attack reports
  * Then search by SECTOR: banks, government, military, telecom, education, energy, media, aviation
  * Then search by ATTACK TYPE: DDoS, breach, leak, defacement
  * Then do FOLLOW-UP searches for specific targets/actors found in earlier results
  * Aim for 6-10 searches total for maximum coverage
- Use both English AND Arabic terms when relevant (e.g., "اختراق" for hack, "بنك" for bank)
- Include domain patterns: .jo, gov.jo, mil.jo, edu.jo, com.jo
- Search for specific organization names found in prior results
- Use severity="CRITICAL" filter to find confirmed attack reports efficiently

RESPONSE MODES:
1. **Q&A mode** (default): Brief, factual, precise. Cite [REF:N] inline.
2. **Report mode** (when asked for "report", "full report", "all", "everything", "summarize", "name all"):
   # Report Title
   **Date:** {today} | **Scope:** [describe]
   ## Executive Summary
   [2-3 sentence overview]
   ## Key Findings
   [Group by sector or attack type, bullet points, cite [REF:N] for every claim]
   ## Indicators of Compromise
   | Type | Value | Source |
   |------|-------|--------|
   [table rows from context]
   ## Risk Assessment
   [Brief risk analysis]
   ## Recommendations
   [Actionable points]

Rules:
- Cite [REF:N] tags for EVERY factual claim. Multiple refs encouraged.
- Use **bold**, bullet lists, numbered lists, and tables as needed.
- When asked about "now/today/current", focus on today's date ({today}).
- Do NOT fabricate information. Only report what you found in search results.
- After your complete answer, write exactly on its own line:
  ---REFS---
  Then list ALL referenced numbers as comma-separated integers.
- If you cited no references, still write ---REFS--- followed by nothing."""


@app.route("/api/chat", methods=["POST"])
def api_chat():
    data = request.get_json(silent=True) or {}
    user_msg = (data.get("message") or "").strip()
    history  = data.get("history") or []
    if not user_msg:
        return jsonify({"error": "empty message"}), 400
    client = _chat_openai_client()
    if not client:
        return jsonify({"error": "OPENAI_API_KEY not configured"}), 503

    # Retrieve relevant messages with conversation-aware search
    search_query = _extract_search_query(user_msg, history)
    rel_msgs = _search_messages_for_chat_v2(search_query, user_msg, limit=150)

    # Build context with sequential REF indices — this is the ONLY source of truth for refs
    context_blocks = [_format_msg_for_context(i, m) for i, m in enumerate(rel_msgs)]
    context_text   = "\n---\n".join(context_blocks)

    # gpt-4o supports 128k tokens. Cap context at ~100k chars safely.
    if len(context_text) > 100000:
        # Keep as many complete blocks as fit
        kept, total = [], 0
        for blk in context_blocks:
            if total + len(blk) + 5 > 100000:
                break
            kept.append(blk)
            total += len(blk) + 5
        context_text = "\n---\n".join(kept)
        rel_msgs = rel_msgs[:len(kept)]   # keep index alignment

    # Build date-aware system prompt
    now_utc = datetime.now(timezone.utc)
    today_str  = now_utc.strftime("%Y-%m-%d")
    now_str    = now_utc.strftime("%Y-%m-%d %H:%M UTC")
    newest_ts  = max((m.get("timestamp_utc","") for m in rel_msgs), default="unknown")
    chat_system = _CHAT_SYSTEM_TEMPLATE.format(now_utc=now_str, today=today_str)

    trimmed_history = history[-16:]   # last 8 exchanges
    payload = [{"role": "system", "content": chat_system}]
    payload.append({
        "role": "system",
        "content": (
            f"=== INTEL CONTEXT: {len(rel_msgs)} messages from monitored channels ===\n"
            f"(Messages sorted oldest→newest. Newest message timestamp: {newest_ts[:16]})\n"
            f"{context_text}\n"
            f"=== END CONTEXT ==="
        )
    })
    for h in trimmed_history:
        if h.get("role") in ("user", "assistant") and h.get("content"):
            payload.append({"role": h["role"], "content": str(h["content"])})
    payload.append({"role": "user", "content": user_msg})

    try:
        resp = client.chat.completions.create(
            model="gpt-4o",
            messages=payload,
            max_tokens=2000,
            temperature=0.2,
            response_format={"type": "json_object"},
        )
        raw = resp.choices[0].message.content or "{}"
        parsed = json.loads(raw)
    except json.JSONDecodeError:
        parsed = {"answer": raw, "references": []}
    except Exception as e:
        return jsonify({"error": str(e)}), 500

    answer = parsed.get("answer", "")
    # AI returns integer indices; resolve them to actual messages
    raw_refs = parsed.get("references") or []
    valid_refs = []
    ref_messages = []
    seen_idx = set()
    for r in raw_refs:
        try:
            idx = int(r)
        except (ValueError, TypeError):
            continue
        if 0 <= idx < len(rel_msgs) and idx not in seen_idx:
            seen_idx.add(idx)
            valid_refs.append(idx)
            ref_messages.append(rel_msgs[idx])

    return jsonify({"answer": answer, "references": valid_refs, "ref_messages": ref_messages})


@app.route("/api/chat/history")
def api_chat_history():
    # Session-only: history lives in frontend _chatHistory array
    return jsonify({"messages": []})


@app.route("/api/chat/reset", methods=["POST"])
def api_chat_reset():
    return jsonify({"ok": True})


@app.route("/api/chat/stream", methods=["POST"])
def api_chat_stream():
    """Agentic streaming chat: AI iteratively searches intel DB via tool calling."""
    data = request.get_json(silent=True) or {}
    user_msg = (data.get("message") or "").strip()
    history  = data.get("history") or []
    if not user_msg:
        return jsonify({"error": "empty message"}), 400
    client = _chat_openai_client()
    if not client:
        return jsonify({"error": "OPENAI_API_KEY not configured"}), 503

    # Load messages once for this request
    all_msgs = load_messages()
    total_msgs = len(all_msgs)
    critical_count = sum(1 for m in all_msgs if m.get("priority") == "CRITICAL")
    medium_count = sum(1 for m in all_msgs if m.get("priority") == "MEDIUM")
    low_count = total_msgs - critical_count - medium_count
    n_channels = len(set(m.get("channel_username", "") for m in all_msgs if m.get("channel_username")))

    now_utc = datetime.now(timezone.utc)
    today_str = now_utc.strftime("%Y-%m-%d")
    now_str   = now_utc.strftime("%Y-%m-%d %H:%M UTC")

    chat_system = _CHAT_SYSTEM_TEMPLATE_V3.format(
        now_utc=now_str, today=today_str,
        total_msgs=total_msgs, total_channels=n_channels,
        critical_count=critical_count, medium_count=medium_count, low_count=low_count
    )

    # Build message list: system + conversation history + new question
    # Use generous limits for recent messages (reports can be 5-8k chars)
    messages = [{"role": "system", "content": chat_system}]
    recent_history = history[-16:]
    for i, h in enumerate(recent_history):
        if h.get("role") in ("user", "assistant") and h.get("content"):
            # Last 4 messages get full context (8k), older ones get 2k
            char_limit = 8000 if i >= len(recent_history) - 4 else 2000
            messages.append({"role": h["role"], "content": str(h["content"])[:char_limit]})
    messages.append({"role": "user", "content": user_msg})

    # Shared state across agentic iterations
    all_ref_msgs = []
    seen_ids = set()

    # Detect comprehensive queries → use map-reduce approach
    _comprehensive_kw = ("full report", "all sectors", "everything", "name all",
        "name everything", "comprehensive", "dont skip", "don't skip",
        "complete report", "all cybersecurity", "all incidents", "all attacks")
    is_comprehensive = any(kw in user_msg.lower() for kw in _comprehensive_kw)

    # --- Map-Reduce prompts ---
    _MAP_EXTRACT_PROMPT = (
        "You are a cybersecurity incident extractor. Analyze Telegram channel messages and extract EVERY cyber attack or threat targeting JORDAN.\n\n"
        "OUTPUT FORMAT — one line per incident:\n"
        "[REF:N] | DATE | @CHANNEL | ATTACK_TYPE | TARGET_DOMAIN_OR_ORG | BRIEF_DETAILS\n\n"
        "ATTACK_TYPE categories:\n"
        "- DDoS: website/service taken down, knocked offline, overloaded\n"
        "- Defacement: website content changed/replaced\n"
        "- Data Breach: stolen data, leaked credentials, dumped databases\n"
        "- Data Leak: personal info published (names, phones, emails)\n"
        "- Hack: unauthorized access, system compromise, infiltration\n"
        "- Threat/Warning: explicit announcement of planned attack on Jordan\n\n"
        "JORDAN TARGETS TO WATCH FOR (extract ALL, not just these):\n"
        "Government: jordan.gov.jo, moe.gov.jo, moj.gov.jo, psd.gov.jo, petra.gov.jo, mof.gov.jo, jhr.gov.jo, ncsc.jo, form.jordan.gov.jo, govreform.jo\n"
        "Military: rjaf.mil.jo, any military base in Jordan\n"
        "Banking: jkb.com, bankofjordan.com, jcbank.com.jo, capitalbank.jo, arabbank.jo, housing-bank.com\n"
        "Telecom: orange.jo, zain.com, umniah.com\n"
        "Aviation: rj.com (Royal Jordanian), jac.jo (Jordan Airports)\n"
        "Energy: jordanenergy.jo, nepco.com.jo\n"
        "Education: jmi.edu.jo, any .edu.jo domain\n"
        "Media: jordantimes.com, jordannews.jo\n"
        "Tax/Finance: Income & Sales Tax Department, any government financial system\n\n"
        "CRITICAL RULES:\n"
        "1. Extract EVERY incident — do NOT skip small or less prominent attacks\n"
        "2. Look for .jo domains, Arabic mentions of Jordan (الاردن), and named Jordanian orgs\n"
        "3. If the same target is attacked by DIFFERENT actors or on DIFFERENT dates, list each separately\n"
        "4. Data breaches/leaks are HIGH VALUE — never skip these even if brief\n"
        "5. Distinguish CYBER attacks from KINETIC/military actions (missiles, explosions = skip)\n"
        "6. Include the threat ACTOR name if visible (group name, channel name)\n\n"
        "SKIP: General news, political commentary, non-Jordan targets, kinetic military operations, messages just sharing news without attack claims.\n\n"
        "Output ONLY incident lines. If no Jordan cyber incidents found: NO_JORDAN_INCIDENTS"
    )

    _REDUCE_REPORT_PROMPT = _CHAT_SYSTEM_TEMPLATE_V3.format(
        now_utc=now_str, today=today_str,
        total_msgs=total_msgs, total_channels=n_channels,
        critical_count=critical_count, medium_count=medium_count, low_count=low_count
    ).replace(
        "You have a **search_intel** tool to query the message database.",
        "You have been given pre-extracted incident findings from the full message database."
    ).replace(
        "Each search returns up to 50 messages with [REF:N] citation tags.",
        "Each finding has a [REF:N] tag you must cite."
    )

    def _format_ultracompact(idx, m):
        """One-line format: ~100-150 chars. Prefers English AI summary."""
        ts = (m.get("timestamp_utc") or "")[:10]
        uname = m.get("channel_username", "?")
        pri = m.get("priority", "LOW")
        ae = m.get("ai_enrichment") or {}
        summary = (ae.get("summary") or "")[:120]
        if summary:
            return f"[REF:{idx}] [{pri}] {ts} @{uname} | {summary}"
        text = (m.get("text_preview") or "")[:100]
        kw = m.get("keyword_hits") or []
        return f"[REF:{idx}] [{pri}] {ts} @{uname} | {text} | KW:{','.join(kw[:4])}"

    def generate():
        nonlocal messages
        start_time = time.time()

        if is_comprehensive:
            # ── MAP-REDUCE: process CRITICAL + MEDIUM messages in chunks ──
            target_msgs = [m for m in all_msgs if m.get("priority") in ("CRITICAL", "MEDIUM")]
            target_msgs.sort(key=lambda m: m.get("timestamp_utc", ""))

            chunk_size = 150
            chunks = [target_msgs[i:i+chunk_size] for i in range(0, len(target_msgs), chunk_size)]

            # Pre-assign REF IDs for all messages (needed before parallel calls)
            chunk_contexts = []
            for chunk in chunks:
                formatted_lines = []
                for m in chunk:
                    mid = f"{m.get('channel_username','')}_{m.get('message_id','')}"
                    if mid not in seen_ids:
                        ref_idx = len(all_ref_msgs)
                        all_ref_msgs.append(m)
                        seen_ids.add(mid)
                        formatted_lines.append(_format_ultracompact(ref_idx, m))
                chunk_contexts.append("\n".join(formatted_lines))

            yield f"data: {json.dumps({'type':'status','message':f'Launching {len(chunks)} parallel agents to analyze {len(target_msgs)} CRITICAL+MEDIUM messages...'})}\n\n"

            # ── PARALLEL MAP: all agents run simultaneously ──
            def _run_map_agent(agent_idx, context_text):
                """Single map agent — runs in thread pool."""
                if not context_text.strip():
                    return agent_idx, ""
                try:
                    resp = client.chat.completions.create(
                        model="gpt-4o-mini",
                        messages=[
                            {"role": "system", "content": _MAP_EXTRACT_PROMPT},
                            {"role": "user", "content": context_text}
                        ],
                        max_tokens=2000,
                        temperature=0,
                    )
                    return agent_idx, resp.choices[0].message.content.strip()
                except Exception as e:
                    return agent_idx, f"ERROR: {str(e)[:100]}"

            all_findings = []
            with ThreadPoolExecutor(max_workers=min(len(chunks), 10)) as executor:
                futures = {
                    executor.submit(_run_map_agent, ci, ctx): ci
                    for ci, ctx in enumerate(chunk_contexts)
                }
                for future in as_completed(futures):
                    agent_idx, result = future.result()
                    yield f"data: {json.dumps({'type':'status','message':f'Agent {agent_idx+1}/{len(chunks)} done'})}\n\n"
                    if result and "NO_JORDAN_INCIDENTS" not in result and not result.startswith("ERROR:"):
                        all_findings.append(result)

            # ── DEDUP: merge duplicate incidents by target domain ──
            import re as _re
            incident_lines = []
            for f in all_findings:
                incident_lines.extend([l.strip() for l in f.split("\n") if l.strip() and l.strip().startswith("[")])
            raw_count = len(incident_lines)

            # Parse each line: [REF:N] | DATE | @CHANNEL | TYPE | TARGET | DETAILS
            dedup = {}  # key = normalized target → merged incident
            for line in incident_lines:
                parts = [p.strip() for p in line.split("|")]
                if len(parts) < 5:
                    continue
                refs = _re.findall(r'\[REF:(\d+)\]', parts[0])
                date = parts[1].strip() if len(parts) > 1 else ""
                actor = parts[2].strip() if len(parts) > 2 else ""
                atype = parts[3].strip() if len(parts) > 3 else ""
                target = parts[4].strip() if len(parts) > 4 else ""
                details = parts[5].strip() if len(parts) > 5 else ""

                # Normalize target for grouping: lowercase, strip www., extract domain
                key = target.lower().strip()
                key = _re.sub(r'^(https?://)?www\.', '', key)
                key = _re.sub(r'[/\s]+$', '', key)
                # Also extract .jo domain if present
                domain_match = _re.search(r'[\w.-]+\.jo\b', key)
                if domain_match:
                    key = domain_match.group(0)

                if not key or len(key) < 3:
                    continue

                if key not in dedup:
                    dedup[key] = {
                        "target": target, "refs": set(), "dates": set(),
                        "actors": set(), "types": set(), "details": []
                    }
                for r in refs:
                    dedup[key]["refs"].add(int(r))
                if date:
                    dedup[key]["dates"].add(date[:10])
                if actor:
                    dedup[key]["actors"].add(actor)
                if atype:
                    dedup[key]["types"].add(atype)
                if details and details not in dedup[key]["details"]:
                    dedup[key]["details"].append(details)

            # Build deduplicated incident table for reduce phase
            dedup_lines = []
            for key in sorted(dedup.keys()):
                d = dedup[key]
                ref_str = ", ".join(f"[REF:{r}]" for r in sorted(d["refs"])[:8])
                dates = ", ".join(sorted(d["dates"])[:3])
                actors = ", ".join(sorted(d["actors"])[:3])
                types = " / ".join(sorted(d["types"]))
                detail = d["details"][0][:120] if d["details"] else ""
                dedup_lines.append(f"{ref_str} | {dates} | {actors} | {types} | {d['target']} | {detail}")

            unique_count = len(dedup_lines)
            combined_dedup = "\n".join(dedup_lines)

            yield f"data: {json.dumps({'type':'status','message':f'Found {raw_count} raw → {unique_count} unique incidents. Generating report...'})}\n\n"

            # ── REDUCE: final GPT-4o synthesizes the report ──
            reduce_messages = [
                {"role": "system", "content": _REDUCE_REPORT_PROMPT},
                {"role": "system", "content": (
                    f"=== DEDUPLICATED FINDINGS: {unique_count} unique cyber incidents (from {raw_count} raw extractions) ===\n"
                    f"Format: REFS | DATES | ACTORS | ATTACK_TYPE | TARGET | DETAILS\n\n"
                    f"{combined_dedup}\n\n=== END FINDINGS ===\n\n"
                    f"IMPORTANT: Your report MUST include ALL {unique_count} incidents listed above. "
                    f"Do NOT summarize or skip any. Present every single one in the report with its [REF:N] citations. "
                    f"Include a comprehensive incident table with ALL entries."
                )},
            ]
            for h in history[-10:]:
                if h.get("role") in ("user", "assistant") and h.get("content"):
                    reduce_messages.append({"role": h["role"], "content": str(h["content"])[:2000]})
            reduce_messages.append({"role": "user", "content": user_msg})

            try:
                stream = client.chat.completions.create(
                    model="gpt-4o",
                    messages=reduce_messages,
                    max_tokens=6000,
                    temperature=0.2,
                    stream=True,
                )
                full_content = ""
                for chunk_resp in stream:
                    delta = chunk_resp.choices[0].delta
                    if delta.content:
                        full_content += delta.content
                        yield f"data: {json.dumps({'type':'token','content':delta.content}, ensure_ascii=False)}\n\n"
            except Exception as e:
                yield f"data: {json.dumps({'type':'error','message':str(e)})}\n\n"
                return

            # Parse refs
            answer = full_content
            raw_refs = []
            if "---REFS---" in full_content:
                parts = full_content.split("---REFS---", 1)
                answer = parts[0].rstrip()
                ref_str = parts[1].strip()
                raw_refs = [r.strip() for r in ref_str.split(",") if r.strip()]

            valid_refs, ref_messages, seen_ref_idx = [], [], set()
            for r in raw_refs:
                try:
                    idx = int(r)
                except (ValueError, TypeError):
                    continue
                if 0 <= idx < len(all_ref_msgs) and idx not in seen_ref_idx:
                    seen_ref_idx.add(idx)
                    valid_refs.append(idx)
                    ref_messages.append(all_ref_msgs[idx])

            elapsed = round(time.time() - start_time, 1)
            yield f"data: {json.dumps({'type':'done','answer':answer,'references':valid_refs,'ref_messages':ref_messages,'elapsed_s':elapsed,'context_msgs':len(all_ref_msgs)}, ensure_ascii=False)}\n\n"
            return

        # ── Detect reformatting/follow-up to a recent report ──
        # If user is just asking to reformat (table, list, summarize), and previous
        # assistant response was long (report-like), skip tools — just answer from context
        _reformat_kw = ("table", "list them", "put it in", "reformat", "summarize",
            "in a table", "tabular", "as a table", "shorter", "bullet points",
            "can you list", "can u list", "show me all", "give me a table")
        is_reformat = any(kw in user_msg.lower() for kw in _reformat_kw)
        prev_was_report = (len(history) >= 2 and
            any(h.get("role") == "assistant" and len(str(h.get("content",""))) > 2500
                for h in history[-4:]))

        if is_reformat and prev_was_report:
            # Direct GPT call — no tools, just reformat from conversation context
            yield f"data: {json.dumps({'type':'status','message':'Reformatting from conversation context...'})}\n\n"
            try:
                stream = client.chat.completions.create(
                    model="gpt-4o",
                    messages=messages,
                    max_tokens=4096,
                    temperature=0.15,
                    stream=True,
                )
                full_content = ""
                for chunk_resp in stream:
                    delta = chunk_resp.choices[0].delta
                    if delta.content:
                        full_content += delta.content
                        yield f"data: {json.dumps({'type':'token','content':delta.content}, ensure_ascii=False)}\n\n"
            except Exception as e:
                yield f"data: {json.dumps({'type':'error','message':str(e)})}\n\n"
                return

            answer = full_content
            raw_refs = []
            if "---REFS---" in full_content:
                parts = full_content.split("---REFS---", 1)
                answer = parts[0].rstrip()
                raw_refs = [r.strip() for r in parts[1].strip().split(",") if r.strip()]
            valid_refs, ref_messages = [], []
            elapsed = round(time.time() - start_time, 1)
            yield f"data: {json.dumps({'type':'done','answer':answer,'references':valid_refs,'ref_messages':ref_messages,'elapsed_s':elapsed,'context_msgs':0}, ensure_ascii=False)}\n\n"
            return

        # ── NORMAL (non-comprehensive): agentic tool-calling ──
        for iteration in range(12):
            try:
                stream = client.chat.completions.create(
                    model="gpt-4o",
                    messages=messages,
                    tools=[_SEARCH_INTEL_TOOL],
                    max_tokens=4096,
                    temperature=0.2,
                    stream=True,
                )
            except Exception as e:
                yield f"data: {json.dumps({'type':'error','message':str(e)})}\n\n"
                return

            full_content = ""
            tool_calls_acc = {}
            finish_reason = None

            for chunk_resp in stream:
                choice = chunk_resp.choices[0]
                if choice.finish_reason:
                    finish_reason = choice.finish_reason
                delta = choice.delta

                if delta.content:
                    full_content += delta.content
                    yield f"data: {json.dumps({'type':'token','content':delta.content}, ensure_ascii=False)}\n\n"

                if delta.tool_calls:
                    for tc_delta in delta.tool_calls:
                        idx = tc_delta.index
                        if idx not in tool_calls_acc:
                            tool_calls_acc[idx] = {"id": "", "name": "", "arguments": ""}
                        if tc_delta.id:
                            tool_calls_acc[idx]["id"] = tc_delta.id
                        if tc_delta.function:
                            if tc_delta.function.name:
                                tool_calls_acc[idx]["name"] = tc_delta.function.name
                            if tc_delta.function.arguments:
                                tool_calls_acc[idx]["arguments"] += tc_delta.function.arguments

            if finish_reason == "tool_calls" and tool_calls_acc:
                assistant_tc = []
                for idx_key in sorted(tool_calls_acc.keys()):
                    tc = tool_calls_acc[idx_key]
                    assistant_tc.append({
                        "id": tc["id"],
                        "type": "function",
                        "function": {"name": tc["name"], "arguments": tc["arguments"]}
                    })
                messages.append({
                    "role": "assistant",
                    "content": full_content or None,
                    "tool_calls": assistant_tc
                })

                for idx_key in sorted(tool_calls_acc.keys()):
                    tc = tool_calls_acc[idx_key]
                    try:
                        args = json.loads(tc["arguments"])
                    except Exception:
                        args = {"query": ""}

                    query = args.get("query", "")
                    severity = args.get("severity", "all")
                    days_back = args.get("days_back", 365)

                    yield f"data: {json.dumps({'type':'status','message':f'Searching: {query}...'})}\n\n"

                    count, formatted = _execute_search_tool(
                        query, severity, days_back, seen_ids, all_ref_msgs, all_msgs
                    )

                    messages.append({
                        "role": "tool",
                        "tool_call_id": tc["id"],
                        "content": formatted
                    })

                continue
            else:
                break

        # Parse references from final text
        answer = full_content
        raw_refs = []
        if "---REFS---" in full_content:
            parts = full_content.split("---REFS---", 1)
            answer = parts[0].rstrip()
            ref_str = parts[1].strip()
            raw_refs = [r.strip() for r in ref_str.split(",") if r.strip()]

        valid_refs, ref_messages, seen_ref_idx = [], [], set()
        for r in raw_refs:
            try:
                idx = int(r)
            except (ValueError, TypeError):
                continue
            if 0 <= idx < len(all_ref_msgs) and idx not in seen_ref_idx:
                seen_ref_idx.add(idx)
                valid_refs.append(idx)
                ref_messages.append(all_ref_msgs[idx])

        elapsed = round(time.time() - start_time, 1)
        yield f"data: {json.dumps({'type':'done','answer':answer,'references':valid_refs,'ref_messages':ref_messages,'elapsed_s':elapsed,'context_msgs':len(all_ref_msgs)}, ensure_ascii=False)}\n\n"

    return Response(
        generate(),
        mimetype="text/event-stream",
        headers={
            "Cache-Control": "no-cache",
            "X-Accel-Buffering": "no",
            "Connection": "keep-alive",
        }
    )


@app.route("/api/ai/log")
def api_ai_log():
    """Return last N lines of AI agent log with colour-coded level tags."""
    lines = int(request.args.get("lines", 80))
    log_path = OUTPUT_DIR / "ai_agent.log"
    if not log_path.exists():
        return jsonify({"lines": [], "size": 0})
    try:
        all_lines = log_path.read_text(encoding="utf-8", errors="replace").splitlines()
        tail = all_lines[-lines:]
        return jsonify({"lines": tail, "total": len(all_lines), "size": log_path.stat().st_size})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/ai/analyze", methods=["POST"])
def api_ai_analyze():
    """Launch ai_agent.py as a background daemon process."""
    import subprocess, psutil
    # Check if already running
    for p in psutil.process_iter(['pid', 'cmdline']):
        try:
            if p.info['cmdline'] and 'ai_agent.py' in ' '.join(p.info['cmdline']):
                return jsonify({"error": "agent already running", "pid": p.pid}), 409
        except Exception:
            pass
    try:
        proc = subprocess.Popen(
            ["python", "ai_agent.py"],
            stdout=open(OUTPUT_DIR / "ai_agent.log", "a"),
            stderr=subprocess.STDOUT,
            cwd=str(Path(__file__).parent),
        )
        return jsonify({"started": True, "pid": proc.pid})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/ai/stop", methods=["POST"])
def api_ai_stop():
    """Stop the ai_agent.py daemon."""
    import psutil
    killed = []
    for p in psutil.process_iter(['pid', 'cmdline']):
        try:
            if p.info['cmdline'] and 'ai_agent.py' in ' '.join(p.info['cmdline']):
                p.kill()
                killed.append(p.pid)
        except Exception:
            pass
    return jsonify({"stopped": killed})


# ══════════════════════════════════════════════════════════════════════════════
# SYSTEM CONFIG + ORCHESTRATOR STATUS
# ══════════════════════════════════════════════════════════════════════════════

ENV_FILE_PATH = Path(__file__).parent / ".env"
ORCH_STATUS_FILE = OUTPUT_DIR / "orchestrator_status.json"


def _load_env_file():
    """Load .env file as a dict."""
    if not ENV_FILE_PATH.exists():
        return {}
    out = {}
    for line in ENV_FILE_PATH.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        out[k.strip()] = v.strip().strip('"').strip("'")
    return out


def _save_env_key(key, value):
    """Write or update a key in the .env file."""
    lines = []
    if ENV_FILE_PATH.exists():
        lines = ENV_FILE_PATH.read_text(encoding="utf-8").splitlines()
    found = False
    new_lines = []
    for line in lines:
        if line.strip().startswith(f"{key}=") or line.strip().startswith(f"{key} ="):
            new_lines.append(f"{key}={value}")
            found = True
        else:
            new_lines.append(line)
    if not found:
        new_lines.append(f"{key}={value}")
    ENV_FILE_PATH.write_text("\n".join(new_lines) + "\n", encoding="utf-8")
    os.environ[key] = value


@app.route("/api/system/status")
def api_system_status():
    """Return orchestrator component status + env config presence."""
    import psutil

    # Check which processes are running
    procs = {"viewer": False, "monitor": False, "ai_agent": False, "orchestrator": False}
    for p in psutil.process_iter(['pid', 'cmdline']):
        try:
            cmd = ' '.join(p.info['cmdline'] or [])
            if 'viewer.py' in cmd:           procs["viewer"]       = True
            if 'telegram_monitor.py' in cmd: procs["monitor"]      = True
            if 'ai_agent.py' in cmd:         procs["ai_agent"]     = True
            if 'orchestrator.py' in cmd:     procs["orchestrator"] = True
        except Exception:
            pass

    env = _load_env_file()
    agent_state = {}
    if AI_STATE_FILE.exists():
        try:
            agent_state = json.loads(AI_STATE_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass

    brief = None
    if AI_BRIEF_FILE.exists():
        try:
            brief = json.loads(AI_BRIEF_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass

    return jsonify({
        "processes": procs,
        "has_openai_key": bool(env.get("OPENAI_API_KEY") or os.environ.get("OPENAI_API_KEY")),
        "agent_stats": agent_state,
        "latest_brief": brief,
    })


@app.route("/api/system/config", methods=["POST"])
def api_system_config():
    """Save API keys and config to .env file."""
    data = request.get_json(force=True) or {}
    saved = []
    allowed_keys = ["OPENAI_API_KEY", "TG_API_ID", "TG_API_HASH", "TG_PHONE"]
    for key in allowed_keys:
        val = str(data.get(key, "")).strip()
        if val:
            _save_env_key(key, val)
            saved.append(key)
    return jsonify({"ok": True, "saved": saved,
                    "note": "Keys saved to .env — restart AI agent to activate"})


@app.route("/api/ai/apply", methods=["POST"])
def api_ai_apply():
    """Apply latest AI keyword suggestions to keywords.json."""
    if not AI_SUGGESTIONS.exists():
        return jsonify({"error": "no suggestions available"}), 404
    try:
        data   = json.loads(AI_SUGGESTIONS.read_text(encoding="utf-8"))
        latest = data.get("latest", {})
        new_crit = [k for k in latest.get("new_critical_keywords", []) if k]
        new_med  = [k for k in latest.get("new_medium_keywords",   []) if k]

        kw_data = {"critical": [], "medium": []}
        if KEYWORDS_FILE.exists():
            try:
                kw_data = json.loads(KEYWORDS_FILE.read_text(encoding="utf-8"))
            except Exception:
                pass

        existing_crit = set(k.lower() for k in kw_data.get("critical", []))
        existing_med  = set(k.lower() for k in kw_data.get("medium",   []))

        added_crit = [k for k in new_crit if k.lower() not in existing_crit]
        added_med  = [k for k in new_med  if k.lower() not in existing_med]

        kw_data.setdefault("critical", []).extend(added_crit)
        kw_data.setdefault("medium",   []).extend(added_med)
        KEYWORDS_FILE.write_text(
            json.dumps(kw_data, indent=2, ensure_ascii=False), encoding="utf-8")

        return jsonify({"ok": True, "added_critical": len(added_crit),
                        "added_medium": len(added_med)})
    except Exception as e:
        return jsonify({"error": str(e)}), 500


@app.route("/api/discovery/fetch")
def api_discovery_fetch():
    username = request.args.get("username", "").strip()
    limit    = min(int(request.args.get("limit", 100)), 500)
    save     = request.args.get("save", "false").lower() == "true"
    if not username or not TELETHON_OK:
        return jsonify({"error": "need username + telethon", "messages": []})
    try:
        try:
            asyncio.get_event_loop()
        except RuntimeError:
            asyncio.set_event_loop(asyncio.new_event_loop())
        with TGSync(SESSION, API_ID, API_HASH) as client:
            raw = list(client.iter_messages(username, limit=limit))
        raw.sort(key=lambda m: m.id)
        messages = []
        for m in raw:
            text = m.text or ""
            priority, hits = _score_text(text)
            messages.append({
                "message_id":       m.id,
                "channel_username": username,
                "channel":          username,
                "timestamp_utc":    m.date.isoformat() if m.date else "",
                "timestamp_irst":   "",
                "text_preview":     text,
                "priority":         priority,
                "keyword_hits":     hits,
                "iocs":             {},
                "has_media":        bool(m.media),
                "live":             True,
            })
        if save:
            seen = set()
            try:
                with open(OUTPUT_DIR / "messages.jsonl", encoding="utf-8") as f:
                    for line in f:
                        try:
                            rec = json.loads(line)
                            seen.add(f"{rec.get('channel_username')}_{rec.get('message_id')}")
                        except Exception:
                            pass
            except FileNotFoundError:
                pass
            with open(OUTPUT_DIR / "messages.jsonl", "a", encoding="utf-8") as f:
                for msg in messages:
                    key = f"{msg['channel_username']}_{msg['message_id']}"
                    if key not in seen:
                        f.write(json.dumps(msg, ensure_ascii=False) + "\n")
            _msg_cache["data"] = None  # Invalidate cache
        return jsonify({"messages": messages, "total": len(messages)})
    except Exception as e:
        return jsonify({"error": str(e), "messages": []})


# ═══════════════════════════════════════════════════════════════════════════════
# HTML TEMPLATE
# ═══════════════════════════════════════════════════════════════════════════════

HTML = r"""<!DOCTYPE html>
<html lang="en">
<head>
<meta charset="utf-8">
<title>Scanwave CyberIntel</title>
<style>
*{margin:0;padding:0;box-sizing:border-box}
html,body{height:100%;overflow:hidden}
body{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Roboto,sans-serif;background:#0d1117;color:#e6edf3;display:flex;flex-direction:column}

/* ── TOP BAR ── */
.topbar{background:#0a0f17;border-bottom:2px solid #da3633;padding:0 20px;display:flex;align-items:center;gap:14px;height:46px;flex-shrink:0;position:relative}
.topbar-logo{font-size:13px;font-weight:800;color:#f0f6fc;letter-spacing:.4px;white-space:nowrap;display:flex;align-items:center;gap:6px}
.topbar-logo .shield{color:#da3633;font-size:16px}
.topbar-logo .brand{color:#da3633}
.live-dot{width:7px;height:7px;border-radius:50%;background:#238636;display:inline-block;box-shadow:0 0 6px #238636;animation:pulse 2s infinite}
@keyframes pulse{0%,100%{box-shadow:0 0 4px #238636}50%{box-shadow:0 0 12px #2ea043}}
.live-dot.dead{background:#da3633;box-shadow:0 0 6px #da3633;animation:none}
.alert-ticker{flex:1;font-size:11px;color:#8b949e;overflow:hidden;white-space:nowrap;text-overflow:ellipsis;padding:0 12px}
.alert-ticker .ticker-hot{color:#ff7b7b;font-weight:600}
.topbar-summary{font-size:11px;color:#8b949e;white-space:nowrap;display:flex;gap:10px}
.ts{display:flex;align-items:center;gap:4px}
.ts .val{color:#f0f6fc;font-weight:700;font-size:12px}
.ts .val.red{color:#ff7b7b}
.ts .val.amber{color:#e3b341}
.ts .val.green{color:#3fb950}
.new-badge{background:#da3633;color:#fff;font-size:9px;font-weight:800;padding:1px 5px;border-radius:10px;animation:pulse-red 1.5s infinite}
@keyframes pulse-red{0%,100%{opacity:1}50%{opacity:.6}}

/* ── NAV TABS ── */
.nav-tabs{display:flex;height:100%;margin-left:6px}
.nav-tab{height:100%;padding:0 16px;font-size:12px;font-weight:600;color:#8b949e;background:none;border:none;border-bottom:3px solid transparent;cursor:pointer;letter-spacing:.3px;transition:all .15s;display:flex;align-items:center;gap:6px}
.nav-tab:hover{color:#e6edf3;background:rgba(255,255,255,.04)}
.nav-tab.active{color:#f0f6fc;border-bottom-color:#388bfd}
.nav-tab .tab-badge{font-size:9px;font-weight:800;padding:1px 5px;border-radius:10px;background:#da3633;color:#fff}
.nav-tab .tab-badge.amber{background:#9a6e00}

/* ── LAYOUT ── */
.page{flex:1;display:flex;flex-direction:column;overflow:hidden}
.tab-panel{display:none;flex:1;flex-direction:column;overflow:hidden}
.tab-panel.active{display:flex}

/* ══════════════════════════════════════
   MONITOR TAB
══════════════════════════════════════ */
.monitor-layout{display:flex;flex:1;overflow:hidden}

/* ── SIDEBAR ── */
.sidebar{width:270px;background:#0d1117;border-right:1px solid #21262d;display:flex;flex-direction:column;flex-shrink:0}
.sidebar-head{padding:8px 14px;font-size:10px;font-weight:700;color:#8b949e;text-transform:uppercase;letter-spacing:.8px;border-bottom:1px solid #21262d;display:flex;justify-content:space-between;align-items:center}
.sidebar-sort{font-size:10px;color:#388bfd;font-weight:600;cursor:default}
.ch-list{overflow-y:auto;flex:1}
.ch-list::-webkit-scrollbar{width:4px}
.ch-list::-webkit-scrollbar-thumb{background:#21262d;border-radius:2px}
.ch-item{padding:9px 14px;cursor:pointer;border-left:3px solid transparent;border-bottom:1px solid #0d1117;transition:background .12s;position:relative}
.ch-item:hover{background:#161b22}
.ch-item.active{background:#1a2d4a;border-left-color:#388bfd}
.ch-item.has-crit{border-left-color:#6e1a1a}
.ch-item.active{border-left-color:#388bfd!important}
.ch-name{font-size:12px;font-weight:600;color:#f0f6fc;margin-bottom:1px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;max-width:220px}
.ch-sub{font-size:10px;color:#6e7681;margin-bottom:4px;font-style:italic}
.ch-badges{display:flex;gap:4px;align-items:center;flex-wrap:wrap}
.ch-count{font-size:10px;color:#6e7681}
.ch-last{font-size:9px;color:#6e7681;margin-top:2px}
.ch-last.hot{color:#ff7b7b}
.ch-tier-label{font-size:9px;color:#484f58;margin-bottom:2px;font-style:italic}
.bdg{font-size:9px;font-weight:700;padding:1px 6px;border-radius:8px;color:#fff}
.bdg.c{background:#da3633}
.bdg.m{background:#9a6e00}

/* ── SIDEBAR TABS ── */
.s-tabs{display:flex;border-bottom:1px solid #21262d;flex-shrink:0;background:#0a0f17}
.s-tab{flex:1;padding:7px 4px;font-size:11px;font-weight:600;color:#8b949e;background:none;border:none;cursor:pointer;letter-spacing:.3px;transition:color .12s;border-bottom:2px solid transparent}
.s-tab:hover{color:#e6edf3}
.s-tab.active{color:#f0f6fc;border-bottom-color:#388bfd}
.disc-bar{padding:7px 10px;display:flex;align-items:center;gap:6px;border-bottom:1px solid #21262d;flex-shrink:0;flex-wrap:wrap}
.disc-bar button{font-size:11px;padding:3px 10px}
.disc-st{font-size:10px;color:#8b949e;margin-left:auto}
.disc-item{padding:8px 12px;border-bottom:1px solid #21262d;cursor:pointer;border-left:3px solid transparent}
.disc-item:hover{background:#1c2128}
.disc-item.hi{border-left-color:#da3633}
.disc-item.med{border-left-color:#9a6e00}
.disc-name{font-size:12px;font-weight:600;color:#f0f6fc;margin-bottom:1px}
.disc-sub{font-size:10px;color:#8b949e;margin-bottom:2px}
.disc-kws{font-size:9px;color:#6e7681}
.disc-acts{display:flex;gap:5px;margin-top:4px}
.disc-acts button{font-size:10px;padding:2px 8px}

/* ── CHAT PANEL ── */
.chat{flex:1;display:flex;flex-direction:column;overflow:hidden}
.chat-head{padding:10px 16px;background:#161b22;border-bottom:1px solid #21262d;display:flex;align-items:center;gap:10px;flex-shrink:0}
.chat-head .title{font-size:13px;font-weight:700;color:#f0f6fc}
.chat-head .sub{font-size:11px;color:#6e7681}
.chat-head .spacer{flex:1}
.stat-pill{font-size:10px;color:#8b949e;background:#21262d;padding:2px 9px;border-radius:10px}
.stat-pill.red{background:#3d0000;color:#ff7b7b;border:1px solid #6e1a1a}
.filters{padding:7px 14px;background:#0d1117;border-bottom:1px solid #21262d;display:flex;gap:7px;align-items:center;flex-wrap:wrap;flex-shrink:0}
.fl{font-size:11px;color:#6e7681}
select,input{background:#161b22;border:1px solid #21262d;color:#e6edf3;padding:3px 7px;border-radius:5px;font-size:11px}
select:focus,input:focus{outline:none;border-color:#388bfd}
input[type=text]{width:140px}
input[type=number]{width:46px}
button{background:#161b22;border:1px solid #21262d;color:#e6edf3;padding:3px 10px;border-radius:5px;font-size:11px;cursor:pointer;transition:background .12s}
button:hover{background:#21262d;border-color:#388bfd}
button.danger{border-color:#6e1a1a;color:#ff7b7b}
button.danger:hover{background:#2a0d0d}
button.primary{background:#1a2d4a;border-color:#388bfd;color:#79c0ff}
button.primary:hover{background:#1f3a5e}

/* ── MESSAGES ── */
.msgs{flex:1;overflow-y:auto;padding:14px;display:flex;flex-direction:column;gap:9px}
.msgs::-webkit-scrollbar{width:5px}
.msgs::-webkit-scrollbar-thumb{background:#21262d;border-radius:3px}
.date-sep{text-align:center;font-size:10px;color:#6e7681;padding:3px 0;position:relative}
.date-sep::before{content:'';position:absolute;left:0;right:0;top:50%;height:1px;background:#21262d}
.date-sep span{background:#0d1117;padding:0 10px;position:relative}

.bubble{border-radius:7px;padding:9px 13px;border:1px solid #21262d;background:#161b22;transition:filter .1s}
.bubble.CRITICAL{background:#130a0a;border-color:#5a1212;border-left:3px solid #da3633}
.bubble.MEDIUM{background:#110e00;border-color:#5a3d00;border-left:3px solid #e3b341}
.bubble.LOW{background:#161b22;border-color:#21262d}
.bubble{cursor:pointer}
.bubble:hover{filter:brightness(1.1)}
.bubble.target-msg{outline:2px solid #388bfd;outline-offset:2px;box-shadow:0 0 0 4px rgba(56,139,253,.1)}
.target-label{font-size:9px;color:#388bfd;font-weight:700;margin-bottom:4px;letter-spacing:.4px}

.b-meta{display:flex;align-items:center;gap:7px;flex-wrap:wrap;margin-bottom:4px}
.ptag{font-size:9px;font-weight:700;padding:2px 6px;border-radius:3px;letter-spacing:.5px}
.ptag.CRITICAL{background:#da3633;color:#fff}
.ptag.MEDIUM{background:#9a6e00;color:#fff}
.ptag.LOW{background:#21262d;color:#6e7681}
.crit-toggle{display:flex;gap:3px;align-items:center}
.ctbtn{font-size:9px;padding:2px 8px;background:#161b22;border:1px solid #30363d;color:#8b949e;border-radius:12px;cursor:pointer;transition:all .15s}
.ctbtn:hover{border-color:#58a6ff;color:#58a6ff}
.ctbtn.active{background:#3d1a1a;border-color:#da3633;color:#ff6060}
.ctbtn[data-sub="CYBER"].active{background:#1a2d1a;border-color:#3fb950;color:#3fb950}
.ctbtn[data-sub="NATIONAL"].active{background:#1a2040;border-color:#58a6ff;color:#58a6ff}
.b-channel{font-size:10px;color:#388bfd;font-weight:600;background:#0d1628;padding:1px 6px;border-radius:3px}
.b-time{font-size:10px;color:#6e7681}
.b-irst{font-size:9px;color:#484f58;background:#161b22;padding:1px 5px;border-radius:2px}

.kws{display:flex;flex-wrap:wrap;gap:3px;margin-bottom:5px}
.kw{font-size:10px;padding:1px 6px;border-radius:3px;background:#1c2128;border:1px solid #21262d;color:#6e7681;font-family:'SF Mono',Consolas,monospace;cursor:pointer;transition:border-color .1s}
.kw:hover{border-color:#388bfd;color:#79c0ff}
.kw.hot{background:#120606;border-color:#da3633;color:#ff7b7b}
.kw.hot:hover{background:#1a0808}
.b-text{font-size:12px;line-height:1.65;color:#c9d1d9;word-break:break-word;white-space:pre-wrap;direction:auto}
#chat-src-toggle.has-new{background:#1f6feb33;border-color:#58a6ff;animation:pulse-src .8s ease-in-out 3}
@keyframes pulse-src{0%,100%{box-shadow:none}50%{box-shadow:0 0 6px #58a6ff}}
.stream-cursor{display:inline-block;width:2px;height:14px;background:#58a6ff;margin-left:2px;vertical-align:text-bottom;animation:blink-cursor .7s infinite}
@keyframes blink-cursor{0%,100%{opacity:1}50%{opacity:0}}
.typing-dots::after{content:'...';animation:dot-anim 1.5s infinite}
@keyframes dot-anim{0%{content:'.'}33%{content:'..'}66%{content:'...'}}

.iocs{margin-top:7px;padding-top:7px;border-top:1px solid #21262d;display:flex;flex-direction:column;gap:3px}
.ioc-row{display:flex;align-items:flex-start;gap:5px;flex-wrap:wrap}
.ai-card{margin-top:7px;padding:6px 8px;background:#0d1b2a;border:1px solid #58a6ff22;border-radius:4px;border-left:3px solid #58a6ff}
.ioc-lbl{font-size:9px;font-weight:700;color:#6e7681;text-transform:uppercase;letter-spacing:.4px;min-width:44px;padding-top:2px}
.ioc-val{font-family:'SF Mono',Consolas,monospace;font-size:10px;color:#3fb950;background:#0a1b0a;padding:1px 6px;border-radius:2px;border:1px solid #1a3a1a;cursor:pointer;transition:all .1s}
.ioc-val:hover{border-color:#3fb950;color:#7ee787}

.empty{flex:1;display:flex;align-items:center;justify-content:center;flex-direction:column;gap:10px;color:#484f58}
.empty .ico{font-size:32px}
.empty p{font-size:12px}
.loading-msg{text-align:center;color:#484f58;padding:20px;font-size:12px}

/* ── STATUSBAR ── */
.statusbar{padding:4px 16px;background:#0a0f17;border-top:1px solid #21262d;font-size:10px;color:#484f58;display:flex;gap:14px;flex-shrink:0}

/* ══════════════════════════════════════
   DASHBOARD TAB
══════════════════════════════════════ */
.dashboard{display:flex;flex-direction:column;flex:1;overflow:hidden;background:#0d1117}
.dash-cards{display:flex;gap:0;flex-shrink:0;border-bottom:1px solid #21262d;background:#0a0f17}
.dash-card{flex:1;padding:10px 16px;border-right:1px solid #21262d;cursor:default}
.sys-proc{font-size:9px;padding:2px 8px;border-radius:10px;background:#21262d;color:#484f58;white-space:nowrap}
.dash-card:last-child{border-right:none}
.dc-label{font-size:9px;font-weight:700;color:#484f58;text-transform:uppercase;letter-spacing:.6px;margin-bottom:2px}
.dc-value{font-size:22px;font-weight:800;color:#f0f6fc;line-height:1}
.dc-value.red{color:#ff7b7b}
.dc-value.amber{color:#e3b341}
.dc-value.green{color:#3fb950}
.dc-value.blue{color:#79c0ff}
.dc-sub{font-size:10px;color:#6e7681;margin-top:1px}

.dash-body{display:flex;flex:1;overflow:hidden;gap:0}

/* keyword heatmap + global feed split */
.dash-left{display:flex;flex-direction:column;width:420px;flex-shrink:0;border-right:1px solid #21262d;overflow:hidden}
.dash-right{flex:1;display:flex;flex-direction:column;overflow:hidden}

/* heatmap panel */
.hm-head{padding:8px 14px;font-size:10px;font-weight:700;color:#8b949e;text-transform:uppercase;letter-spacing:.6px;border-bottom:1px solid #21262d;display:flex;justify-content:space-between;align-items:center;flex-shrink:0;background:#0a0f17}
.hm-body{overflow-y:auto;padding:10px 12px;flex:1}
.hm-body::-webkit-scrollbar{width:4px}
.hm-body::-webkit-scrollbar-thumb{background:#21262d;border-radius:2px}
.kw-grid{display:flex;flex-wrap:wrap;gap:5px;align-items:flex-start}
.kw-chip{cursor:pointer;border-radius:4px;padding:3px 8px;font-size:11px;font-family:'SF Mono',Consolas,monospace;border:1px solid;transition:all .15s;white-space:nowrap}
.kw-chip:hover{transform:scale(1.06);z-index:1}
/* sizes */
.kw-chip.sz1{font-size:10px;padding:2px 6px}
.kw-chip.sz2{font-size:11px;padding:3px 7px}
.kw-chip.sz3{font-size:12px;padding:3px 9px}
.kw-chip.sz4{font-size:13px;padding:4px 10px;font-weight:600}
.kw-chip.sz5{font-size:14px;padding:4px 12px;font-weight:700}
/* criticality colors */
.kw-chip.c-red{background:#1a0404;border-color:#6e1a1a;color:#ff7b7b}
.kw-chip.c-amber{background:#140d00;border-color:#6e4000;color:#e3b341}
.kw-chip.c-blue{background:#030d1a;border-color:#1a3d6e;color:#79c0ff}
.kw-chip.c-gray{background:#1a1f27;border-color:#30363d;color:#8b949e}

/* activity heatmap */
.act-section{flex-shrink:0;border-top:1px solid #21262d;max-height:180px;overflow:hidden;background:#0a0f17}
.act-head{padding:7px 14px;font-size:10px;font-weight:700;color:#8b949e;text-transform:uppercase;letter-spacing:.6px;border-bottom:1px solid #21262d;display:flex;justify-content:space-between}
.act-irst-note{font-size:9px;color:#484f58;font-weight:400}
.act-grid-wrap{overflow-x:auto;padding:6px 10px 8px}
.act-grid{display:grid;grid-template-columns:36px repeat(24,1fr);gap:2px;min-width:600px}
.act-label{font-size:9px;color:#484f58;display:flex;align-items:center;justify-content:flex-end;padding-right:4px}
.act-hour-label{font-size:8px;color:#484f58;text-align:center;height:10px;display:flex;align-items:center;justify-content:center}
.act-cell{height:16px;border-radius:2px;background:#161b22;cursor:default;position:relative}
.act-cell:hover::after{content:attr(data-tip);position:absolute;bottom:110%;left:50%;transform:translateX(-50%);background:#1c2128;border:1px solid #30363d;color:#e6edf3;font-size:9px;padding:2px 6px;border-radius:3px;white-space:nowrap;z-index:10;pointer-events:none}
/* IRST work-hours overlay (09-18 = working hours for Iranian timezone) */
.act-cell.work-hour{outline:1px solid rgba(255,255,100,.1)}

/* Global feed */
.gf-head{padding:8px 14px;font-size:10px;font-weight:700;color:#8b949e;text-transform:uppercase;letter-spacing:.6px;border-bottom:1px solid #21262d;flex-shrink:0;background:#0a0f17;display:flex;align-items:center;gap:8px}
.gf-search{flex:1;padding:4px 9px;background:#161b22;border:1px solid #21262d;border-radius:4px;color:#e6edf3;font-size:11px}
.gf-search:focus{outline:none;border-color:#388bfd}
.gf-filter{padding:3px 7px;background:#161b22;border:1px solid #21262d;border-radius:4px;color:#e6edf3;font-size:11px}
.gf-msgs{overflow-y:auto;flex:1;padding:10px 12px;display:flex;flex-direction:column;gap:7px}
.gf-msgs::-webkit-scrollbar{width:5px}
.gf-msgs::-webkit-scrollbar-thumb{background:#21262d;border-radius:3px}
.gf-count{font-size:10px;color:#484f58;padding:0 4px}

/* Campaign cards */
.camp-section{flex-shrink:0;border-bottom:1px solid #21262d;background:#070b11}
.camp-head{padding:7px 14px;font-size:10px;font-weight:700;color:#da3633;text-transform:uppercase;letter-spacing:.6px;border-bottom:1px solid #21262d}
.camp-scroll{display:flex;gap:8px;padding:8px 12px;overflow-x:auto}
.camp-scroll::-webkit-scrollbar{height:4px}
.camp-scroll::-webkit-scrollbar-thumb{background:#21262d;border-radius:2px}
.camp-card{flex-shrink:0;background:#1a0404;border:1px solid #6e1a1a;border-radius:6px;padding:7px 10px;min-width:160px;max-width:200px;cursor:pointer;transition:background .12s}
.camp-card:hover{background:#220808}
.camp-kw{font-size:12px;font-weight:700;color:#ff7b7b;font-family:monospace;margin-bottom:3px}
.camp-meta{font-size:9px;color:#6e7681}
.camp-chs{font-size:9px;color:#484f58;margin-top:2px}
.no-camps{font-size:11px;color:#484f58;padding:8px 14px}

/* ══════════════════════════════════════
   IOC INTEL TAB
══════════════════════════════════════ */
.ioc-page{display:flex;flex-direction:column;flex:1;overflow:hidden}
.ioc-toolbar{padding:9px 16px;background:#0a0f17;border-bottom:1px solid #21262d;display:flex;gap:9px;align-items:center;flex-shrink:0;flex-wrap:wrap}
.ioc-toolbar .fl{font-size:11px;color:#6e7681}
.ioc-type-filter button{margin-right:4px;font-size:10px;padding:2px 9px}
.ioc-type-filter button.sel{background:#1a2d4a;border-color:#388bfd;color:#79c0ff}
.ioc-search{padding:4px 9px;background:#161b22;border:1px solid #21262d;border-radius:4px;color:#e6edf3;font-size:11px;width:180px}
.ioc-search:focus{outline:none;border-color:#388bfd}
.ioc-export{margin-left:auto}
.ioc-table-wrap{overflow:auto;flex:1}
.ioc-table{width:100%;border-collapse:collapse;font-size:12px}
.ioc-table th{position:sticky;top:0;background:#0a0f17;padding:8px 12px;text-align:left;font-size:10px;font-weight:700;color:#484f58;text-transform:uppercase;letter-spacing:.5px;border-bottom:1px solid #21262d;cursor:pointer;white-space:nowrap;user-select:none}
.ioc-table th:hover{color:#8b949e}
.ioc-table th .sort-arrow{font-size:9px;margin-left:3px}
.ioc-table td{padding:7px 12px;border-bottom:1px solid #0d1117;vertical-align:top}
.ioc-table tr:hover td{background:#161b22}
.ioc-type-badge{font-size:9px;font-weight:700;padding:2px 7px;border-radius:3px;letter-spacing:.3px;font-family:monospace}
.ioc-type-badge.ip{background:#031a0d;color:#3fb950;border:1px solid #1a4a2d}
.ioc-type-badge.domain{background:#03091a;color:#79c0ff;border:1px solid #1a2d4a}
.ioc-type-badge.url{background:#0d0a00;color:#e3b341;border:1px solid #4a3800}
.ioc-type-badge.hash{background:#0d0a00;color:#d2a8ff;border:1px solid #3d2467}
.ioc-type-badge.email{background:#1a0303;color:#ff7b7b;border:1px solid #4a1515}
.ioc-val-cell{font-family:'SF Mono',Consolas,monospace;color:#3fb950;max-width:320px;word-break:break-all}
.ioc-count-cell{font-weight:700;color:#f0f6fc;text-align:right}
.ioc-channels-cell{font-size:10px;color:#6e7681;max-width:200px}
.ioc-ch-tag{display:inline-block;background:#161b22;border:1px solid #21262d;border-radius:2px;padding:0px 4px;font-size:9px;margin:1px 2px;color:#8b949e;font-family:monospace}
.ioc-last-cell{font-size:10px;color:#484f58;white-space:nowrap}
.ioc-copy{font-size:9px;padding:1px 6px;cursor:pointer;border:1px solid #21262d;background:transparent;color:#484f58;border-radius:2px;transition:all .1s}
.ioc-copy:hover{border-color:#3fb950;color:#3fb950}
.ioc-table-empty{text-align:center;padding:40px;color:#484f58;font-size:12px}

/* ══════════════════════════════════════
   TIMELINE TAB
══════════════════════════════════════ */
.timeline-page{display:flex;flex-direction:column;flex:1;overflow:hidden}
.tl-toolbar{padding:9px 16px;background:#0a0f17;border-bottom:1px solid #21262d;display:flex;gap:9px;align-items:center;flex-shrink:0;flex-wrap:wrap}
.tl-feed{overflow-y:auto;flex:1;padding:14px 20px;display:flex;flex-direction:column;gap:0}
.tl-feed::-webkit-scrollbar{width:5px}
.tl-feed::-webkit-scrollbar-thumb{background:#21262d;border-radius:3px}
.tl-day{font-size:10px;font-weight:700;color:#484f58;text-transform:uppercase;letter-spacing:.6px;padding:14px 0 7px;display:flex;align-items:center;gap:10px}
.tl-day::after{content:'';flex:1;height:1px;background:#21262d}
.tl-item{display:flex;gap:12px;padding:7px 0;border-bottom:1px solid #0d1117;align-items:flex-start}
.tl-time-col{width:90px;flex-shrink:0;text-align:right}
.tl-time{font-size:11px;color:#6e7681;font-family:monospace}
.tl-irst{font-size:9px;color:#484f58;font-family:monospace}
.tl-line{width:2px;background:#21262d;flex-shrink:0;position:relative;margin-top:2px}
.tl-line.crit{background:#da3633}
.tl-line.med{background:#9a6e00}
.tl-line::before{content:'';position:absolute;top:4px;left:50%;transform:translateX(-50%);width:8px;height:8px;border-radius:50%;background:inherit}
.tl-body{flex:1;cursor:pointer;min-width:0}
.tl-body:hover .tl-btext{color:#e6edf3}
.tl-bheader{display:flex;align-items:center;gap:6px;margin-bottom:3px;flex-wrap:wrap}
.tl-ptag{font-size:9px;font-weight:700;padding:1px 5px;border-radius:2px}
.tl-ptag.CRITICAL{background:#da3633;color:#fff}
.tl-ptag.MEDIUM{background:#9a6e00;color:#fff}
.tl-channel{font-size:10px;color:#388bfd;font-weight:600;font-family:monospace;background:#0d1628;padding:1px 5px;border-radius:2px}
.tl-kws{display:flex;gap:3px;flex-wrap:wrap;margin-bottom:3px}
.tl-kw{font-size:9px;padding:1px 5px;border-radius:2px;background:#1c2128;color:#6e7681;font-family:monospace}
.tl-kw.hot{background:#120606;color:#ff7b7b}
.tl-btext{font-size:11px;color:#8b949e;line-height:1.5;word-break:break-word;white-space:pre-wrap;direction:auto;max-height:120px;overflow:hidden;position:relative}
.tl-btext.expanded{max-height:none}
.tl-expand{font-size:9px;color:#388bfd;cursor:pointer;margin-top:2px;background:none;border:none;padding:0}
.tl-iocs{margin-top:4px}

/* ── GLOBAL SEARCH MODAL ── */
.gs-item:hover,.gs-item.gs-selected{background:#1c2128}
.gs-item{transition:background .08s}

/* ── CHANNEL IOC PANEL ── */
.cioc-filter{background:#21262d;border:1px solid #30363d;color:#8b949e;border-radius:4px;padding:2px 8px;cursor:pointer;font-size:10px;transition:all .1s}
.cioc-filter.sel{background:#1a2d4a;border-color:#2d4a6e;color:#58a6ff}
.cioc-filter:hover{background:#30363d;color:#e6edf3}

/* ── CONTEXT MODAL ── */
.ctx-overlay{position:fixed;inset:0;background:rgba(0,0,0,.85);z-index:500;display:flex;align-items:center;justify-content:center;backdrop-filter:blur(3px)}
.ctx-panel{background:#161b22;border:1px solid #30363d;border-radius:10px;width:min(840px,96vw);max-height:88vh;display:flex;flex-direction:column;overflow:hidden;box-shadow:0 24px 72px rgba(0,0,0,.8)}
.ctx-head{padding:12px 16px;border-bottom:1px solid #21262d;display:flex;align-items:center;gap:10px;flex-shrink:0;background:#0a0f17}
.ctx-head h3{font-size:12px;font-weight:700;flex:1;color:#f0f6fc;letter-spacing:.2px}
.ctx-meta{font-size:10px;color:#484f58}
.ctx-close{background:none;border:1px solid #21262d;color:#6e7681;font-size:14px;cursor:pointer;padding:2px 8px;border-radius:4px;line-height:1.4;transition:all .1s}
.ctx-close:hover{color:#e6edf3;background:#21262d;border-color:#6e7681}
.ctx-body{overflow-y:auto;padding:12px;display:flex;flex-direction:column;gap:8px}
.ctx-body::-webkit-scrollbar{width:5px}
.ctx-body::-webkit-scrollbar-thumb{background:#21262d;border-radius:3px}

/* ── TOAST NOTIFICATION ── */
.toast{position:fixed;bottom:20px;right:20px;z-index:999;background:#161b22;border:1px solid #30363d;border-radius:7px;padding:10px 16px;font-size:12px;color:#e6edf3;box-shadow:0 8px 24px rgba(0,0,0,.6);animation:slide-in .3s ease;pointer-events:none}
.toast.crit{border-color:#da3633;background:#130a0a;color:#ff7b7b}
@keyframes slide-in{from{transform:translateY(20px);opacity:0}to{transform:translateY(0);opacity:1}}
/* ── MARKDOWN RENDERING (chat) ── */
.md-render{font-size:12px;line-height:1.65;color:#c9d1d9}
.md-render h1,.md-render h2,.md-render h3,.md-render h4{color:#e6edf3;margin:14px 0 6px;font-weight:700;border-bottom:1px solid #21262d;padding-bottom:4px}
.md-render h1{font-size:17px;border-bottom:2px solid #388bfd}
.md-render h2{font-size:14px;border-bottom-color:#30363d}
.md-render h3{font-size:13px;border-bottom:none}
.md-render h4{font-size:12px;border-bottom:none;color:#8b949e}
.md-render p{margin:5px 0}
.md-render strong{color:#e6edf3}
.md-render em{color:#b1bac4}
.md-render a{color:#58a6ff;text-decoration:none}
.md-render a:hover{text-decoration:underline}
.md-render hr{border:none;border-top:1px solid #21262d;margin:12px 0}
.md-render ul,.md-render ol{margin:4px 0;padding-left:20px}
.md-render li{margin:2px 0}
.md-render li::marker{color:#484f58}
.md-render blockquote{border-left:3px solid #388bfd;margin:8px 0;padding:4px 12px;background:#161b2244;color:#8b949e}
.md-render code{background:#0d1117;padding:1px 5px;border-radius:3px;font-family:'SF Mono',Consolas,monospace;font-size:11px;color:#79c0ff}
.md-render pre{background:#0d1117;border:1px solid #21262d;border-radius:6px;padding:10px 12px;margin:8px 0;overflow-x:auto}
.md-render pre code{background:none;padding:0;font-size:11px;color:#e6edf3}
/* Tables — the wow factor */
.md-render table{width:100%;border-collapse:collapse;margin:10px 0;font-size:11px;border:1px solid #30363d;border-radius:6px;overflow:hidden}
.md-render thead{background:linear-gradient(135deg,#161b22 0%,#0d1117 100%)}
.md-render thead th{padding:8px 10px;text-align:left;font-weight:700;color:#58a6ff;font-size:10px;text-transform:uppercase;letter-spacing:.5px;border-bottom:2px solid #388bfd}
.md-render tbody tr{border-bottom:1px solid #21262d;transition:background .15s}
.md-render tbody tr:nth-child(even){background:#161b2266}
.md-render tbody tr:hover{background:#1f6feb15}
.md-render td{padding:6px 10px;color:#c9d1d9;vertical-align:top}
.md-render td:first-child{color:#e6edf3;font-weight:500}
/* REF tag styling */
.md-render .ref-tag{background:#1f6feb22;color:#58a6ff;padding:0 4px;border-radius:3px;font-size:10px;font-weight:600;cursor:help;white-space:nowrap}
/* ══════════════════════════════════════
   APT TRACKER TAB
══════════════════════════════════════ */
.apt-page{display:flex;flex:1;overflow:hidden}
.apt-sidebar{width:230px;border-right:1px solid #21262d;overflow-y:auto;background:#0a0f17;flex-shrink:0;display:flex;flex-direction:column}
.apt-sidebar-head{padding:10px 12px;border-bottom:1px solid #21262d;flex-shrink:0}
.apt-sidebar-head input{width:100%;background:#0d1117;border:1px solid #21262d;border-radius:4px;padding:5px 9px;color:#e6edf3;font-size:11px}
.apt-sidebar-head input:focus{outline:none;border-color:#388bfd}
.apt-sidebar-list{flex:1;overflow-y:auto}
.apt-main{flex:1;overflow-y:auto;padding:16px 20px;display:flex;flex-direction:column;gap:14px}
.apt-main-empty{flex:1;display:flex;align-items:center;justify-content:center;color:#484f58;font-size:12px;flex-direction:column;gap:8px}
.apt-lookup{width:290px;border-left:1px solid #21262d;overflow-y:auto;background:#0a0f17;flex-shrink:0;padding:0;display:flex;flex-direction:column}
.apt-lookup-head{padding:10px 12px;border-bottom:1px solid #21262d;font-size:11px;font-weight:700;color:#8b949e;letter-spacing:.5px;flex-shrink:0}
.apt-lookup-body{padding:12px;flex:1;overflow-y:auto;display:flex;flex-direction:column;gap:10px}
/* APT Cards */
.apt-card{padding:9px 11px;border-bottom:1px solid #161b22;border-left:3px solid transparent;cursor:pointer;transition:background .12s}
.apt-card:hover{background:#161b22}
.apt-card.active{background:#0d1b2a;border-left-color:#388bfd}
.apt-card.t1{border-left-color:#da3633}
.apt-card.t2{border-left-color:#e3b341}
.apt-card.t3{border-left-color:#484f58}
.apt-card .apt-name{font-size:11px;font-weight:700;color:#e6edf3;display:flex;align-items:center;gap:6px}
.apt-card .apt-stats{font-size:9px;color:#6e7681;margin-top:3px;display:flex;gap:8px;align-items:center}
.apt-dot{width:6px;height:6px;border-radius:50%;display:inline-block;flex-shrink:0}
.apt-dot.active{background:#3fb950;box-shadow:0 0 4px #3fb950}
.apt-dot.recent{background:#e3b341;box-shadow:0 0 4px #e3b341}
.apt-dot.stale{background:#484f58}
.tier-badge{font-size:8px;font-weight:800;padding:1px 5px;border-radius:2px;letter-spacing:.5px;flex-shrink:0}
.tier-badge.t1{background:#da3633;color:#fff}
.tier-badge.t2{background:#9a6e00;color:#fff}
.tier-badge.t3{background:#21262d;color:#8b949e}
/* APT Detail */
.apt-header{background:#161b22;border:1px solid #30363d;border-radius:8px;padding:14px 18px}
.apt-header-top{display:flex;align-items:center;gap:10px;flex-wrap:wrap}
.apt-header-name{font-size:18px;font-weight:800;color:#f0f6fc}
.apt-header-meta{display:flex;gap:12px;margin-top:8px;flex-wrap:wrap}
.apt-header-meta .stat{background:#0d1117;border:1px solid #21262d;border-radius:4px;padding:4px 10px;font-size:10px;text-align:center}
.apt-header-meta .stat .val{font-size:16px;font-weight:800;display:block}
.apt-header-meta .stat .lbl{color:#6e7681;font-size:9px;text-transform:uppercase;letter-spacing:.5px}
.apt-header-channels{font-size:10px;color:#8b949e;margin-top:8px;font-family:'SF Mono',Consolas,monospace}
/* Sector bars */
.apt-section{background:#161b22;border:1px solid #21262d;border-radius:6px;padding:12px 14px}
.apt-section-title{font-size:10px;font-weight:700;color:#6e7681;text-transform:uppercase;letter-spacing:.5px;margin-bottom:8px;border-bottom:1px solid #21262d;padding-bottom:5px}
.sector-bar-row{display:flex;align-items:center;gap:8px;margin:4px 0}
.sector-bar-label{font-size:10px;color:#8b949e;width:80px;text-align:right;flex-shrink:0}
.sector-bar-track{flex:1;height:18px;background:#0d1117;border-radius:3px;overflow:hidden;position:relative}
.sector-bar-fill{height:100%;border-radius:3px;transition:width .5s ease;min-width:1px}
.sector-bar-fill.gov{background:linear-gradient(90deg,#da3633,#f85149)}
.sector-bar-fill.mil{background:linear-gradient(90deg,#f85149,#ff7b7b)}
.sector-bar-fill.bank{background:linear-gradient(90deg,#9a6e00,#e3b341)}
.sector-bar-fill.tel{background:linear-gradient(90deg,#1f6feb,#58a6ff)}
.sector-bar-fill.media{background:linear-gradient(90deg,#8957e5,#a371f7)}
.sector-bar-fill.energy{background:linear-gradient(90deg,#238636,#3fb950)}
.sector-bar-fill.infra{background:linear-gradient(90deg,#484f58,#6e7681)}
.sector-bar-fill.other{background:linear-gradient(90deg,#21262d,#30363d)}
.sector-bar-val{position:absolute;right:6px;top:1px;font-size:9px;font-weight:700;color:#fff;text-shadow:0 1px 2px rgba(0,0,0,.5)}
/* APT IOC table */
.apt-ioc-table{width:100%;border-collapse:collapse;font-size:11px}
.apt-ioc-table th{padding:6px 10px;text-align:left;font-size:9px;font-weight:700;color:#484f58;text-transform:uppercase;letter-spacing:.5px;border-bottom:1px solid #21262d;background:#0d1117;position:sticky;top:0}
.apt-ioc-table td{padding:5px 10px;border-bottom:1px solid #161b22;color:#c9d1d9}
.apt-ioc-table tr:hover{background:#161b2266}
.apt-ioc-type{font-size:9px;font-weight:700;padding:1px 6px;border-radius:2px;display:inline-block}
.apt-ioc-type.ipv4{background:#0a1b0a;color:#3fb950;border:1px solid #1a3a1a}
.apt-ioc-type.domain{background:#0d1b2a;color:#58a6ff;border:1px solid #1f3350}
.apt-ioc-type.url{background:#0d1b2a;color:#79c0ff;border:1px solid #1f3350}
.apt-ioc-type.hash{background:#1a0d2e;color:#a371f7;border:1px solid #2d1b4e}
.apt-ioc-type.email{background:#1a1500;color:#e3b341;border:1px solid #3d2e00}
.apt-ioc-type.cve{background:#1a0000;color:#f85149;border:1px solid #5a1212}
.apt-ioc-val{font-family:'SF Mono',Consolas,monospace;font-size:11px;cursor:pointer;transition:color .1s}
.apt-ioc-val:hover{color:#58a6ff}
/* IOC Lookup panel */
.lookup-input{display:flex;gap:6px}
.lookup-input input{flex:1;background:#0d1117;border:1px solid #30363d;border-radius:4px;padding:7px 10px;color:#e6edf3;font-size:11px;font-family:'SF Mono',Consolas,monospace}
.lookup-input input:focus{outline:none;border-color:#388bfd}
.lookup-input button{white-space:nowrap}
.lookup-type-badge{font-size:9px;padding:2px 6px;border-radius:3px;background:#21262d;color:#8b949e;text-align:center}
.lookup-card{background:#0d1117;border:1px solid #21262d;border-radius:6px;padding:10px;margin-top:0}
.lookup-card-title{font-size:9px;font-weight:700;color:#6e7681;text-transform:uppercase;letter-spacing:.5px;margin-bottom:6px}
.abuse-score{font-size:32px;font-weight:800;text-align:center;margin:6px 0;line-height:1}
.abuse-score.clean{color:#3fb950}
.abuse-score.suspicious{color:#e3b341}
.abuse-score.malicious{color:#da3633}
.abuse-detail{font-size:10px;color:#8b949e;display:flex;flex-direction:column;gap:3px}
.abuse-detail .row{display:flex;justify-content:space-between}
.abuse-detail .row .val{color:#c9d1d9;font-weight:600;font-family:monospace}
.verdict-badge{text-align:center;padding:6px 12px;border-radius:4px;font-size:12px;font-weight:700;letter-spacing:1.5px}
.verdict-badge.CLEAN{background:#0a1b0a;border:1px solid #238636;color:#3fb950}
.verdict-badge.SUSPICIOUS{background:#1a1500;border:1px solid #9a6e00;color:#e3b341}
.verdict-badge.MALICIOUS{background:#1a0000;border:1px solid #da3633;color:#f85149}
.verdict-badge.UNKNOWN{background:#161b22;border:1px solid #30363d;color:#8b949e}
/* Attack timeline entries */
.atk-entry{display:flex;gap:8px;padding:5px 0;border-bottom:1px solid #161b22;font-size:11px;align-items:flex-start}
.atk-date{color:#6e7681;font-family:monospace;flex-shrink:0;width:75px;font-size:10px}
.atk-type{font-size:9px;font-weight:700;padding:1px 6px;border-radius:2px;flex-shrink:0}
.atk-type.DDoS{background:#1a0000;color:#f85149}
.atk-type.Defacement{background:#1a0d2e;color:#a371f7}
.atk-type.Breach,.atk-type.Hack{background:#1a1500;color:#e3b341}
.atk-type.Leak{background:#0a1b0a;color:#3fb950}
.atk-target{color:#c9d1d9;font-family:monospace}

/* ─── Responsive ─── */
@media (max-width:1400px) {
  .sidebar{width:220px}
  .dash-left{width:340px}
  .apt-sidebar{width:200px}
  .ch-name{max-width:170px}
}
@media (max-width:1100px) {
  .sidebar{width:180px}
  .dash-left{width:280px}
  .apt-sidebar{width:170px}
  .ch-name{max-width:130px}
  .apt-right-panel{display:none!important}
}
@media (max-width:900px) {
  .sidebar{width:160px}
  .dash-left{width:100%;border-right:none;max-height:40vh}
  .dash-right{min-height:60vh}
  .monitor-layout{flex-direction:column}
  .apt-sidebar{width:100%;max-height:30vh;border-right:none;border-bottom:1px solid #21262d}
  .apt-main{flex:1}
  .ch-name{max-width:110px}
}
@media (max-width:700px) {
  .sidebar{width:120px;font-size:10px}
  .topbar{flex-wrap:wrap;height:auto;padding:4px 8px}
  .topbar .nav-btn{font-size:9px;padding:3px 6px}
  .filters{flex-wrap:wrap;gap:4px}
  .bubble{padding:6px 8px}
  #bl-table{min-width:700px}
}
</style>
<script src="https://cdn.jsdelivr.net/npm/marked@15/marked.min.js"></script>
</head>
<body>

<!-- TOP BAR -->
<div class="topbar">
  <div class="topbar-logo">
    <span class="shield">🛡</span>
    Scanwave&nbsp;<span class="brand">CYBERINTEL</span>
    &nbsp;<span class="live-dot" id="live-dot"></span>
  </div>

  <nav class="nav-tabs">
    <button class="nav-tab active" id="nav-monitor"   onclick="switchMainTab('monitor')">📡 MONITOR</button>
    <button class="nav-tab"        id="nav-dashboard" onclick="switchMainTab('dashboard')">📊 DASHBOARD <span class="tab-badge" id="camp-badge" style="display:none">!</span></button>
    <button class="nav-tab"        id="nav-ioc"       onclick="switchMainTab('ioc')">🛡 BLOCKLIST</button>
    <button class="nav-tab"        id="nav-timeline"  onclick="switchMainTab('timeline')">📅 TIMELINE</button>
    <button class="nav-tab"        id="nav-chat"      onclick="switchMainTab('chat')">💬 CHAT</button>
    <button class="nav-tab"        id="nav-apt"       onclick="switchMainTab('apt')">🎯 APT TRACKER</button>
    <button class="nav-tab"        id="nav-admin"     onclick="switchMainTab('admin')" style="margin-left:12px;border-left:1px solid #21262d;padding-left:20px">⚙ ADMIN</button>
  </nav>

  <div class="alert-ticker" id="ticker">Loading intelligence feed...</div>

  <div class="topbar-summary">
    <div class="ts"><span class="val red" id="ts-crit">—</span><span>CRIT</span></div>
    <div class="ts"><span class="val amber" id="ts-med">—</span><span>MED</span></div>
    <div class="ts"><span class="val blue" id="ts-ioc">—</span><span>IOC</span></div>
    <div class="ts"><span class="val green" id="ts-ch">—</span><span>CH</span></div>
    <div class="ts" id="ts-rate-wrap" title="Critical alerts in last 1 hour" style="display:flex;align-items:center;gap:3px;background:#0a0f17;border:1px solid #da363333;border-radius:4px;padding:2px 6px">
      <span class="val" id="ts-rate" style="color:#3fb950;font-size:11px">0</span>
      <span style="font-size:9px;color:#484f58">crit/hr</span>
      <span id="ts-alert-dot" class="live-dot" style="width:5px;height:5px"></span>
    </div>
    <button onclick="openGSearch()" title="Global search (Ctrl+K)"
      style="background:#21262d;border:1px solid #30363d;color:#8b949e;border-radius:5px;padding:3px 9px;cursor:pointer;font-size:11px;display:flex;align-items:center;gap:5px;transition:all .15s"
      onmouseover="this.style.background='#30363d';this.style.color='#e6edf3'"
      onmouseout="this.style.background='#21262d';this.style.color='#8b949e'">
      🔍 <span style="font-size:9px;opacity:.7">Ctrl+K</span>
    </button>
  </div>
</div>

<!-- MAIN PAGE AREA -->
<div class="page">

  <!-- ══ MONITOR TAB ══ -->
  <div id="tab-monitor" class="tab-panel active">
    <div class="monitor-layout">

      <!-- Sidebar -->
      <div class="sidebar">
        <div class="s-tabs">
          <button class="s-tab active" id="t-mon"  onclick="switchSideTab('mon')">Monitored</button>
          <button class="s-tab"        id="t-disc" onclick="switchSideTab('disc')">Discovery</button>
        </div>
        <div id="panel-mon" style="display:flex;flex-direction:column;flex:1;overflow:hidden">
          <div class="sidebar-head">
            Channels
            <span class="sidebar-sort">↓ last critical</span>
          </div>
          <button id="all-ch-btn" onclick="selectAllChannels(this)"
            style="margin:4px 8px;padding:5px 10px;background:#1f3350;border:1px solid #1f6feb55;
                   border-radius:4px;color:#58a6ff;font-size:10px;font-weight:700;cursor:pointer;text-align:left">
            🌐 ALL CHANNELS — live feed
          </button>
          <div class="ch-list" id="ch-list"><div class="loading-msg">Loading...</div></div>
        </div>
        <div id="panel-disc" style="display:none;flex-direction:column;flex:1;overflow:hidden">
          <div class="disc-bar">
            <button id="btn-full-scan" onclick="runScan(false)">Full Scan</button>
            <button onclick="runScan(true)">Quick</button>
            <span class="disc-st" id="disc-st">Idle</span>
          </div>
          <div class="ch-list" id="disc-list"><div class="loading-msg">Run a scan or results appear here.</div></div>
        </div>
      </div>

      <!-- Chat panel -->
      <div class="chat">
        <div class="chat-head" id="chat-head">
          <div>
            <div class="title" id="chat-title">Select a channel</div>
            <div class="sub"   id="chat-sub">← choose from sidebar</div>
          </div>
          <div class="spacer"></div>
          <span class="stat-pill" id="chat-stat" style="display:none"></span>
        </div>
        <!-- Threat Actor Profile Strip -->
        <div id="threat-profile" style="display:none;background:#0a0f17;border-bottom:1px solid #21262d;padding:8px 14px;font-size:11px;color:#8b949e">
          <div style="display:flex;gap:10px;align-items:center;flex-wrap:wrap">
            <span id="tp-tier-badge" style="font-size:9px;font-weight:800;padding:2px 6px;border-radius:3px"></span>
            <span id="tp-label" style="font-weight:600;color:#e6edf3"></span>
            <span id="tp-threat" style="font-size:9px;font-weight:700;padding:2px 6px;border-radius:3px"></span>
            <span id="tp-status-badge"></span>
            <div class="spacer"></div>
            <span id="tp-stats" style="color:#6e7681;font-size:10px"></span>
          </div>
        </div>
        <div class="filters" id="filter-bar" style="display:none">
          <span class="fl">Priority</span>
          <select id="f-priority" onchange="applyFilters()">
            <option value="ALL">All</option>
            <option value="CRITICAL">Critical</option>
            <option value="MEDIUM">Medium</option>
            <option value="LOW">Low</option>
          </select>
          <div class="crit-toggle" id="crit-toggle-monitor">
            <button class="ctbtn active" data-sub="ALL"      onclick="setCritSub('monitor','ALL')">🔴 All</button>
            <button class="ctbtn"        data-sub="CYBER"    onclick="setCritSub('monitor','CYBER')">💻 Cyber</button>
            <button class="ctbtn"        data-sub="NATIONAL" onclick="setCritSub('monitor','NATIONAL')">🛡 NatSec</button>
          </div>
          <span class="fl">From</span>
          <input type="date" id="f-since" onchange="applyFilters()">
          <span class="fl">To</span>
          <input type="date" id="f-until" onchange="applyFilters()">
          <span class="fl">Search</span>
          <input type="text" id="f-search" placeholder="keyword / text…" oninput="applyFilters()">
          <button onclick="resetFilters()">Reset</button>
          <button onclick="scrollBottom()">↓ Latest</button>
          <button onclick="exportCurrentChannel()" title="Export messages as CSV">⬇ CSV</button>
          <span class="fl" style="margin-left:4px;border-left:1px solid #21262d;padding-left:10px">Context</span>
          <input type="number" id="ctx-before" value="5" min="1" max="100">
          <span class="fl">↑</span>
          <input type="number" id="ctx-after" value="5" min="1" max="100">
          <span class="fl">↓</span>
        </div>
        <div class="msgs" id="msgs">
          <div class="empty">
            <div class="ico">📡</div>
            <p>Select a channel to view messages</p>
          </div>
        </div>
        <div class="statusbar" id="statusbar" style="display:none">
          <span id="sb-text"></span>
          <span id="sb-new"></span>
        </div>
      </div>
    </div>
  </div>

  <!-- ══ DASHBOARD TAB ══ -->
  <div id="tab-dashboard" class="tab-panel">

    <!-- ESCALATION BANNER — shown only when urgency HIGH or CRITICAL -->
    <div id="escalation-banner" style="display:none;margin:0 0 16px 0;padding:14px 18px;
         background:#3d0000;border:2px solid #ff2020;border-radius:6px;
         font-family:monospace;font-size:13px;color:#ff6060;">
      <span style="font-size:16px;font-weight:bold;color:#ff2020;">⚠ ESCALATION ALERT</span>
      &nbsp;|&nbsp;<span id="esc-urgency" style="font-weight:bold;"></span>
      &nbsp;|&nbsp;<span id="esc-summary"></span>
      <div style="margin-top:6px;font-size:11px;color:#ff9090;">
        <b>Recommended Action:</b> <span id="esc-action"></span>
        &nbsp;|&nbsp;<span id="esc-checked"></span>
      </div>
    </div>

    <div class="dashboard">
      <!-- Stat cards -->
      <div class="dash-cards">
        <div class="dash-card">
          <div class="dc-label">Total Messages</div>
          <div class="dc-value" id="dc-total">—</div>
          <div class="dc-sub">collected</div>
        </div>
        <div class="dash-card">
          <div class="dc-label">Critical Alerts</div>
          <div class="dc-value red" id="dc-crit">—</div>
          <div class="dc-sub">Jordan-targeted</div>
        </div>
        <div class="dash-card">
          <div class="dc-label">Medium Alerts</div>
          <div class="dc-value amber" id="dc-med">—</div>
          <div class="dc-sub">watch list</div>
        </div>
        <div class="dash-card">
          <div class="dc-label">IOCs Extracted</div>
          <div class="dc-value blue" id="dc-ioc">—</div>
          <div class="dc-sub">IPs · domains · URLs</div>
        </div>
        <div class="dash-card">
          <div class="dc-label">Channels</div>
          <div class="dc-value green" id="dc-ch">—</div>
          <div class="dc-sub" id="dc-ch-sub">monitored groups</div>
        </div>
        <div class="dash-card">
          <div class="dc-label">Campaigns</div>
          <div class="dc-value red" id="dc-camp">—</div>
          <div class="dc-sub">coordinated attacks</div>
        </div>
      </div>

      <!-- Campaign row (if any) -->
      <div class="camp-section" id="camp-section" style="display:none">
        <div class="camp-head">⚡ COORDINATED CAMPAIGNS — multiple channels targeting same keyword on same day</div>
        <div class="camp-scroll" id="camp-scroll"></div>
      </div>

      <!-- Threat Actor Matrix -->
      <div id="matrix-section" style="flex-shrink:0;border-bottom:1px solid #21262d;padding:8px 14px 10px;display:none">
        <div style="display:flex;align-items:center;gap:10px;margin-bottom:6px">
          <span style="font-size:10px;font-weight:700;color:#8b949e;text-transform:uppercase;letter-spacing:.5px">THREAT ACTOR MATRIX</span>
          <span style="font-size:9px;color:#484f58">Actor × Target Category · Critical messages only</span>
          <span id="matrix-badge" style="font-size:9px;background:#da363322;color:#da3633;border:1px solid #da363344;border-radius:10px;padding:1px 7px"></span>
        </div>
        <div id="matrix-table" style="overflow-x:auto;max-height:220px;overflow-y:auto"></div>
      </div>

      <!-- Body split -->
      <div class="dash-body">
        <!-- Left: heatmap + activity -->
        <div class="dash-left">
          <div class="hm-head">
            <span>Keyword Intelligence Heatmap</span>
            <span style="font-size:9px;color:#484f58;font-weight:400">Click to filter feed →</span>
          </div>
          <div class="hm-body" id="hm-body">
            <div class="loading-msg">Loading…</div>
          </div>
          <!-- 30-day trend chart -->
          <div style="flex-shrink:0;border-top:1px solid #21262d;background:#0a0f17;padding:8px 14px 6px">
            <div style="font-size:10px;font-weight:700;color:#8b949e;text-transform:uppercase;letter-spacing:.6px;margin-bottom:6px">
              30-Day Alert Trend
            </div>
            <canvas id="trend-canvas" height="60" style="width:100%;display:block"></canvas>
            <div style="display:flex;gap:10px;margin-top:3px;font-size:9px;color:#484f58">
              <span style="color:#da3633">■ Critical</span>
              <span style="color:#e3b341">■ Medium</span>
            </div>
          </div>
          <!-- Activity heatmap -->
          <div class="act-section">
            <div class="act-head">
              <span>Operator Activity (IRST)</span>
              <span class="act-irst-note">UTC+3:30 · shaded = working hours 08-20</span>
            </div>
            <div class="act-grid-wrap">
              <div class="act-grid" id="act-grid">
                <div class="loading-msg" style="grid-column:1/-1">Loading…</div>
              </div>
            </div>
          </div>
        </div>

        <!-- Right: briefing + global feed -->
        <div class="dash-right">
          <!-- 24h Briefing strip -->
          <div id="briefing-strip" style="flex-shrink:0;background:#070b11;border-bottom:1px solid #21262d;padding:8px 14px;display:none">
            <div style="display:flex;gap:16px;align-items:center;flex-wrap:wrap">
              <span style="font-size:10px;font-weight:700;color:#da3633;text-transform:uppercase;letter-spacing:.5px">24H BRIEFING</span>
              <span id="bf-crit" style="font-size:11px;color:#ff7b7b"></span>
              <span id="bf-trend" style="font-size:10px;padding:1px 8px;border-radius:3px"></span>
              <span id="bf-iocs" style="font-size:11px;color:#79c0ff"></span>
              <span id="bf-ch"   style="font-size:11px;color:#3fb950"></span>
              <span style="flex:1"></span>
              <button onclick="window.location='/api/messages/export?priority=CRITICAL'" class="primary" style="font-size:10px;padding:2px 9px">⬇ Export Criticals</button>
              <button onclick="window.location='/api/messages/export?priority=ALL'" style="font-size:10px;padding:2px 9px">⬇ Export All</button>
            </div>
            <div id="bf-entities" style="margin-top:5px;display:flex;flex-wrap:wrap;gap:4px"></div>
            <div id="bf-newest" style="margin-top:6px;display:none"></div>
          </div>
          <div class="gf-head">
            <span>GLOBAL FEED</span>
            <input class="gf-search" id="gf-search" type="text" placeholder="Search all channels…" oninput="gfSearch()">
            <select class="gf-filter" id="gf-priority" onchange="gfSearch()">
              <option value="ALL">All priority</option>
              <option value="CRITICAL">Critical</option>
              <option value="MEDIUM">Medium</option>
              <option value="LOW">Low</option>
            </select>
            <div class="crit-toggle" id="crit-toggle-feed">
              <button class="ctbtn active" data-sub="ALL"      onclick="setCritSub('feed','ALL')">🔴 All</button>
              <button class="ctbtn"        data-sub="CYBER"    onclick="setCritSub('feed','CYBER')">💻 Cyber</button>
              <button class="ctbtn"        data-sub="NATIONAL" onclick="setCritSub('feed','NATIONAL')">🛡 NatSec</button>
            </div>
            <span class="gf-count" id="gf-count"></span>
            <button onclick="clearGFFilter()" style="font-size:10px;padding:2px 8px">Clear</button>
          </div>
          <div class="gf-msgs" id="gf-msgs">
            <div class="loading-msg">Loading global feed…</div>
          </div>
        </div>
      </div>
    </div>
  </div>

  <!-- ══ IOC INTEL TAB ══ -->
  <div id="tab-ioc" class="tab-panel">
    <div style="display:flex;flex-direction:column;height:100%;overflow:hidden">
      <!-- Toolbar -->
      <div style="padding:12px 20px;background:#0a0f17;border-bottom:1px solid #21262d;display:flex;align-items:center;gap:10px;flex-wrap:wrap;flex-shrink:0">
        <span style="font-size:13px;font-weight:700;color:#da3633">🛡 BLOCKLIST</span>
        <span style="font-size:10px;color:#484f58">External IOCs verified via AbuseIPDB</span>
        <div style="flex:1"></div>
        <select id="bl-apt-filter" onchange="loadBlocklist()" style="background:#161b22;border:1px solid #30363d;color:#e6edf3;padding:4px 8px;border-radius:4px;font-size:10px">
          <option value="">All APT Groups</option>
        </select>
        <select id="bl-type-filter" onchange="loadBlocklist()" style="background:#161b22;border:1px solid #30363d;color:#e6edf3;padding:4px 8px;border-radius:4px;font-size:10px">
          <option value="">All Types</option>
          <option value="ipv4">IPv4</option>
          <option value="domain">Domain</option>
          <option value="url">URL</option>
          <option value="hash_md5">Hash MD5</option>
          <option value="hash_sha256">Hash SHA256</option>
          <option value="cve">CVE</option>
        </select>
        <select id="bl-verdict-filter" onchange="loadBlocklist()" style="background:#161b22;border:1px solid #30363d;color:#e6edf3;padding:4px 8px;border-radius:4px;font-size:10px">
          <option value="">All Verdicts</option>
          <option value="MALICIOUS">MALICIOUS</option>
          <option value="SUSPICIOUS">SUSPICIOUS</option>
          <option value="CLEAN">CLEAN</option>
        </select>
        <input type="text" id="bl-search" placeholder="Search IOCs..." oninput="loadBlocklist()" style="background:#0d1117;border:1px solid #30363d;border-radius:4px;padding:4px 8px;color:#e6edf3;font-size:10px;width:160px">
        <button onclick="window.location='/api/blocklist/export?verdict='+encodeURIComponent(document.getElementById('bl-verdict-filter').value)" style="background:#238636;border:none;color:#fff;padding:5px 12px;border-radius:4px;cursor:pointer;font-size:10px;font-weight:700">EXPORT CSV</button>
        <button onclick="copyBlocklistIPs()" style="background:#21262d;border:1px solid #30363d;color:#8b949e;padding:5px 12px;border-radius:4px;cursor:pointer;font-size:10px;font-weight:700">COPY ALL IPs</button>
        <button onclick="generateReport(this)" style="background:#1f6feb;border:none;color:#fff;padding:5px 12px;border-radius:4px;cursor:pointer;font-size:10px;font-weight:700">📄 GENERATE REPORT</button>
      </div>
      <!-- Stats -->
      <div id="bl-stats" style="padding:8px 20px;background:#161b22;border-bottom:1px solid #21262d;display:flex;gap:20px;font-size:10px;flex-shrink:0"></div>
      <!-- Table -->
      <div style="flex:1;overflow-y:auto;padding:0">
        <table style="width:100%;border-collapse:collapse;font-size:10px;table-layout:fixed" id="bl-table">
          <colgroup>
            <col style="width:130px">
            <col style="width:55px">
            <col style="width:auto">
            <col style="width:80px">
            <col style="width:50px">
            <col style="width:50px">
            <col style="width:50px">
            <col style="width:150px">
            <col style="width:40px">
          </colgroup>
          <thead style="position:sticky;top:0;background:#0d1117;z-index:1">
            <tr style="border-bottom:1px solid #30363d;color:#8b949e;font-size:9px;text-transform:uppercase">
              <th style="text-align:left;padding:6px 8px">APT Group</th>
              <th style="text-align:left;padding:6px">Type</th>
              <th style="text-align:left;padding:6px">Value</th>
              <th style="text-align:center;padding:6px">Verdict</th>
              <th style="text-align:center;padding:6px">Score</th>
              <th style="text-align:left;padding:6px">CC</th>
              <th style="text-align:left;padding:6px">Src</th>
              <th style="text-align:left;padding:6px">Context</th>
              <th style="padding:6px"></th>
            </tr>
          </thead>
          <tbody id="bl-tbody">
            <tr><td colspan="9" style="text-align:center;padding:40px;color:#484f58">Loading blocklist...</td></tr>
          </tbody>
        </table>
      </div>
    </div>
  </div>

  <!-- ══ TIMELINE TAB ══ -->
  <div id="tab-timeline" class="tab-panel">
    <div class="timeline-page">
      <div class="tl-toolbar">
        <span class="fl">Priority:</span>
        <select id="tl-priority" onchange="loadTimeline()">
          <option value="CRITICAL">Critical only</option>
          <option value="MEDIUM">Medium &amp; Critical</option>
          <option value="ALL">All</option>
        </select>
        <div class="crit-toggle" id="crit-toggle-timeline" style="margin-left:4px">
          <button class="ctbtn active" data-sub="ALL"      onclick="setCritSub('timeline','ALL')">🔴 All</button>
          <button class="ctbtn"        data-sub="CYBER"    onclick="setCritSub('timeline','CYBER')">💻 Cyber</button>
          <button class="ctbtn"        data-sub="NATIONAL" onclick="setCritSub('timeline','NATIONAL')">🛡 NatSec</button>
        </div>
        <span class="fl">From:</span>
        <input type="date" id="tl-since" onchange="loadTimeline()">
        <span class="fl">To:</span>
        <input type="date" id="tl-until" onchange="loadTimeline()">
        <span class="fl">Channel:</span>
        <input type="text" id="tl-channel" placeholder="@username" oninput="loadTimeline()" style="width:110px">
        <span class="fl">Search:</span>
        <input type="text" id="tl-search" placeholder="keyword / text…" oninput="loadTimeline()" style="width:140px">
        <button onclick="resetTLFilters()">Reset</button>
        <span id="tl-count" style="font-size:10px;color:#484f58;margin-left:6px"></span>
      </div>
      <div class="tl-feed" id="tl-feed">
        <div class="loading-msg">Loading timeline…</div>
      </div>
    </div>
  </div>

  <!-- ══ ADMIN TAB ══ -->
  <div id="tab-admin" class="tab-panel" style="overflow-y:auto;padding:18px 24px;gap:18px;display:none;flex-direction:column">

    <!-- Live System Health Row -->
    <div style="background:#070b11;border:1px solid #21262d;border-radius:6px;padding:12px 16px">
      <div style="display:flex;align-items:center;gap:12px;flex-wrap:wrap">
        <span style="font-size:10px;font-weight:700;color:#484f58;text-transform:uppercase;letter-spacing:.5px;min-width:90px">System Health</span>
        <div style="display:flex;gap:8px;flex-wrap:wrap;flex:1">
          <div id="sys-proc-viewer"  class="sys-proc">Viewer —</div>
          <div id="sys-proc-monitor" class="sys-proc">Monitor —</div>
          <div id="sys-proc-ai"      class="sys-proc">AI Agent —</div>
          <div id="sys-proc-orch"    class="sys-proc">Orchestrator —</div>
        </div>
        <div style="font-size:9px;color:#484f58">
          Start all: <code style="color:#e3b341">python orchestrator.py</code>
        </div>
        <button onclick="refreshSystemHealth()" style="font-size:9px;padding:2px 8px;background:#0d1117;border:1px solid #30363d;color:#8b949e;border-radius:3px;cursor:pointer">↻</button>
      </div>
      <!-- OpenAI API key config -->
      <div id="sys-apikey-row" style="display:none;margin-top:8px;padding-top:8px;border-top:1px solid #21262d11">
        <div style="display:flex;align-items:center;gap:8px">
          <span style="font-size:9px;color:#e3b341;white-space:nowrap">⚠ OPENAI_API_KEY not set — AI agent disabled</span>
          <input id="sys-apikey-input" type="password" placeholder="sk-..." style="flex:1;background:#161b22;border:1px solid #e3b34144;border-radius:3px;padding:3px 8px;color:#e6edf3;font-size:10px;font-family:monospace">
          <button onclick="saveApiKey()" style="padding:3px 10px;font-size:10px;background:#1a2d0d;border:1px solid #3fb95044;color:#3fb950;border-radius:3px;cursor:pointer">Save &amp; Start AI</button>
        </div>
      </div>
    </div>

    <!-- Status Row -->
    <div style="display:grid;grid-template-columns:repeat(auto-fit,minmax(160px,1fr));gap:12px">
      <div class="dash-card"><div class="dc-label">Monitor</div><div class="dc-value" id="adm-monitor-status" style="font-size:14px">—</div><div class="dc-sub">process state</div></div>
      <div class="dash-card"><div class="dc-label">Total Messages</div><div class="dc-value" id="adm-total">—</div><div class="dc-sub">in database</div></div>
      <div class="dash-card"><div class="dc-label">Critical</div><div class="dc-value red" id="adm-crit">—</div></div>
      <div class="dash-card"><div class="dc-label">IOCs</div><div class="dc-value blue" id="adm-iocs">—</div></div>
      <div class="dash-card"><div class="dc-label">Last Message</div><div class="dc-value green" id="adm-last" style="font-size:11px">—</div></div>
      <div class="dash-card"><div class="dc-label">Cursor</div><div class="dc-value" id="adm-cursor" style="font-size:10px;color:#484f58">—</div><div class="dc-sub">auto-resume point</div></div>
    </div>

    <!-- Two column layout -->
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:18px">

      <!-- LEFT: Channel Manager -->
      <div style="background:#0d1117;border:1px solid #21262d;border-radius:6px;padding:16px">
        <div style="font-size:11px;font-weight:700;color:#8b949e;text-transform:uppercase;letter-spacing:.5px;margin-bottom:12px">Channel Manager</div>

        <!-- Add channel form -->
        <div style="background:#070b11;border:1px solid #21262d;border-radius:5px;padding:12px;margin-bottom:12px">
          <div style="font-size:10px;color:#58a6ff;font-weight:600;margin-bottom:8px">ADD / UPDATE CHANNEL</div>
          <div style="display:grid;grid-template-columns:1fr 1fr;gap:6px;margin-bottom:6px">
            <input id="adm-ch-user"  type="text" placeholder="@username" style="background:#161b22;border:1px solid #30363d;border-radius:4px;padding:5px 8px;color:#e6edf3;font-size:11px">
            <input id="adm-ch-label" type="text" placeholder="Display label" style="background:#161b22;border:1px solid #30363d;border-radius:4px;padding:5px 8px;color:#e6edf3;font-size:11px">
          </div>
          <div style="display:grid;grid-template-columns:1fr 1fr 1fr;gap:6px;margin-bottom:8px">
            <select id="adm-ch-tier" style="background:#161b22;border:1px solid #30363d;border-radius:4px;padding:5px 8px;color:#e6edf3;font-size:11px">
              <option value="1">Tier 1 — Direct</option>
              <option value="2">Tier 2 — Aligned</option>
              <option value="3" selected>Tier 3 — Broader</option>
            </select>
            <select id="adm-ch-threat" style="background:#161b22;border:1px solid #30363d;border-radius:4px;padding:5px 8px;color:#e6edf3;font-size:11px">
              <option value="CRITICAL">CRITICAL</option>
              <option value="HIGH">HIGH</option>
              <option value="MEDIUM" selected>MEDIUM</option>
              <option value="LOW">LOW</option>
            </select>
            <select id="adm-ch-status" style="background:#161b22;border:1px solid #30363d;border-radius:4px;padding:5px 8px;color:#e6edf3;font-size:11px">
              <option value="active" selected>Active</option>
              <option value="banned">Banned</option>
            </select>
          </div>
          <button class="primary" onclick="admAddChannel()" style="width:100%;padding:6px;font-size:11px">+ Add Channel &amp; Queue Join</button>
        </div>

        <!-- Backfill form -->
        <div style="background:#070b11;border:1px solid #21262d;border-radius:5px;padding:12px;margin-bottom:12px">
          <div style="font-size:10px;color:#e3b341;font-weight:600;margin-bottom:8px">BACKFILL MESSAGES</div>
          <div style="display:grid;grid-template-columns:2fr 1fr;gap:6px;margin-bottom:6px">
            <input id="adm-bf-channel" type="text" placeholder="@username or select above" style="background:#161b22;border:1px solid #30363d;border-radius:4px;padding:5px 8px;color:#e6edf3;font-size:11px">
            <input id="adm-bf-limit"   type="number" value="500" min="50" max="2000" style="background:#161b22;border:1px solid #30363d;border-radius:4px;padding:5px 8px;color:#e6edf3;font-size:11px">
          </div>
          <input id="adm-bf-since" type="text" placeholder="Since date (optional, e.g. 2026-01-01)" style="background:#161b22;border:1px solid #30363d;border-radius:4px;padding:5px 8px;color:#e6edf3;font-size:11px;width:100%;box-sizing:border-box;margin-bottom:6px">
          <button onclick="admQueueBackfill()" style="width:100%;padding:6px;font-size:11px;background:#1a2d1a;border:1px solid #3fb95055;color:#3fb950;border-radius:4px;cursor:pointer">⬇ Queue Backfill (processed within 60s)</button>
          <div id="adm-bf-status" style="font-size:10px;color:#484f58;margin-top:4px"></div>
        </div>

        <!-- Maintenance -->
        <div style="background:#070b11;border:1px solid #21262d;border-radius:5px;padding:12px">
          <div style="font-size:10px;color:#da3633;font-weight:600;margin-bottom:8px">MAINTENANCE</div>
          <div style="display:flex;gap:8px;flex-wrap:wrap">
            <button onclick="admCompact()" style="flex:1;padding:6px;font-size:11px;background:#1a0d0d;border:1px solid #da363355;color:#da3633;border-radius:4px;cursor:pointer">⚡ Compact DB</button>
            <button onclick="window.location='/api/messages/export?priority=ALL'" style="flex:1;padding:6px;font-size:11px">⬇ Export All CSV</button>
            <button onclick="window.location='/api/iocs/export'" style="flex:1;padding:6px;font-size:11px">⬇ Export IOCs</button>
          </div>
          <div id="adm-compact-status" style="font-size:10px;color:#484f58;margin-top:4px"></div>
        </div>
      </div>

      <!-- RIGHT: Keyword Manager + Log Tail -->
      <div style="display:flex;flex-direction:column;gap:12px">

        <!-- Keyword manager -->
        <div style="background:#0d1117;border:1px solid #21262d;border-radius:6px;padding:16px;flex:1">
          <div style="display:flex;align-items:center;gap:10px;margin-bottom:10px">
            <span style="font-size:11px;font-weight:700;color:#8b949e;text-transform:uppercase;letter-spacing:.5px">Keyword Lists</span>
            <span style="font-size:9px;color:#484f58">Restart monitor after saving</span>
            <div style="flex:1"></div>
            <button class="primary" onclick="admSaveKeywords()" style="padding:4px 12px;font-size:11px">💾 Save</button>
          </div>
          <div style="display:grid;grid-template-columns:1fr 1fr;gap:10px">
            <div>
              <div style="font-size:9px;color:#da3633;font-weight:700;margin-bottom:4px;text-transform:uppercase">CRITICAL <span id="adm-kw-crit-count" style="color:#484f58"></span></div>
              <textarea id="adm-kw-crit" oninput="admKwCount()" style="width:100%;height:280px;background:#070b11;border:1px solid #da363333;border-radius:4px;color:#e6edf3;font-size:10px;padding:6px;font-family:monospace;resize:vertical;box-sizing:border-box" placeholder="One keyword per line..."></textarea>
            </div>
            <div>
              <div style="font-size:9px;color:#e3b341;font-weight:700;margin-bottom:4px;text-transform:uppercase">MEDIUM <span id="adm-kw-med-count" style="color:#484f58"></span></div>
              <textarea id="adm-kw-med" oninput="admKwCount()" style="width:100%;height:280px;background:#070b11;border:1px solid #e3b34133;border-radius:4px;color:#e6edf3;font-size:10px;padding:6px;font-family:monospace;resize:vertical;box-sizing:border-box" placeholder="One keyword per line..."></textarea>
            </div>
          </div>
          <div id="adm-kw-status" style="font-size:10px;color:#484f58;margin-top:6px"></div>
        </div>

        <!-- Monitor log tail -->
        <div style="background:#0d1117;border:1px solid #21262d;border-radius:6px;padding:16px">
          <div style="font-size:11px;font-weight:700;color:#8b949e;text-transform:uppercase;letter-spacing:.5px;margin-bottom:8px">Monitor Log (last 30 lines)</div>
          <pre id="adm-log" style="background:#070b11;border:1px solid #21262d;border-radius:4px;padding:8px;font-size:9px;color:#8b949e;overflow-y:auto;max-height:180px;margin:0;white-space:pre-wrap;word-break:break-all"></pre>
        </div>

        <!-- Backfill queue status -->
        <div style="background:#0d1117;border:1px solid #21262d;border-radius:6px;padding:16px">
          <div style="font-size:11px;font-weight:700;color:#8b949e;text-transform:uppercase;letter-spacing:.5px;margin-bottom:8px">Backfill Queue</div>
          <div id="adm-bfq" style="font-size:10px;color:#484f58">Loading…</div>
        </div>
      </div>
    </div>

    <!-- Channel table -->
    <div style="background:#0d1117;border:1px solid #21262d;border-radius:6px;padding:16px">
      <div style="display:flex;align-items:center;gap:10px;margin-bottom:10px">
        <span style="font-size:11px;font-weight:700;color:#8b949e;text-transform:uppercase;letter-spacing:.5px">All Monitored Channels</span>
        <span id="adm-ch-count" style="font-size:10px;color:#484f58"></span>
      </div>
      <div style="overflow-x:auto">
        <table style="border-collapse:collapse;width:100%;font-size:10px">
          <thead>
            <tr style="background:#070b11;border-bottom:1px solid #21262d">
              <th style="padding:5px 10px;text-align:left;color:#484f58">Username</th>
              <th style="padding:5px 10px;text-align:left;color:#484f58">Label</th>
              <th style="padding:5px 8px;text-align:center;color:#484f58">Tier</th>
              <th style="padding:5px 8px;text-align:center;color:#484f58">Threat</th>
              <th style="padding:5px 8px;text-align:center;color:#484f58">Status</th>
              <th style="padding:5px 8px;text-align:center;color:#484f58">Actions</th>
            </tr>
          </thead>
          <tbody id="adm-ch-tbody"><tr><td colspan="6" style="padding:12px;text-align:center;color:#484f58">Loading…</td></tr></tbody>
        </table>
      </div>
    </div>

    <!-- AI Agent Panel -->
    <div style="background:#0d1117;border:1px solid #58a6ff44;border-radius:6px;padding:16px">
      <div style="display:flex;align-items:center;gap:10px;margin-bottom:12px">
        <span style="font-size:11px;font-weight:700;color:#58a6ff;text-transform:uppercase;letter-spacing:.5px">🤖 AI Intelligence Agent</span>
        <span style="font-size:9px;color:#484f58">4 autonomous loops: critical enrichment · keyword learning · channel vetting · threat brief</span>
        <div style="flex:1"></div>
        <span id="ai-status-badge" style="font-size:9px;padding:2px 8px;border-radius:3px;background:#1a0d0d;color:#da3633">NOT RUNNING</span>
        <button id="ai-start-btn" onclick="aiStart()" style="font-size:10px;padding:3px 12px;background:#0d2a0d;border:1px solid #3fb95044;color:#3fb950;border-radius:4px;cursor:pointer">▶ Start Agent</button>
        <button onclick="aiStop()" style="font-size:10px;padding:3px 10px;background:#1a0d0d;border:1px solid #da363344;color:#da3633;border-radius:4px;cursor:pointer">■ Stop</button>
      </div>
      <!-- Agent stats row -->
      <div style="display:grid;grid-template-columns:repeat(5,1fr);gap:8px;margin-bottom:12px">
        <div style="background:#070b11;border:1px solid #21262d;border-radius:4px;padding:8px;text-align:center">
          <div style="font-size:18px;font-weight:700;color:#58a6ff" id="ai-stat-enriched">0</div>
          <div style="font-size:8px;color:#484f58;margin-top:2px">ALERTS ENRICHED</div>
        </div>
        <div style="background:#070b11;border:1px solid #21262d;border-radius:4px;padding:8px;text-align:center">
          <div style="font-size:18px;font-weight:700;color:#3fb950" id="ai-stat-kw">0</div>
          <div style="font-size:8px;color:#484f58;margin-top:2px">KEYWORDS ADDED</div>
        </div>
        <div style="background:#070b11;border:1px solid #21262d;border-radius:4px;padding:8px;text-align:center">
          <div style="font-size:18px;font-weight:700;color:#e3b341" id="ai-stat-approved">0</div>
          <div style="font-size:8px;color:#484f58;margin-top:2px">CHANNELS APPROVED</div>
        </div>
        <div style="background:#070b11;border:1px solid #21262d;border-radius:4px;padding:8px;text-align:center">
          <div style="font-size:18px;font-weight:700;color:#da3633" id="ai-stat-dismissed">0</div>
          <div style="font-size:8px;color:#484f58;margin-top:2px">DISMISSED</div>
        </div>
        <div style="background:#070b11;border:1px solid #21262d;border-radius:4px;padding:8px;text-align:center">
          <div style="font-size:18px;font-weight:700;color:#8b949e" id="ai-stat-briefs">0</div>
          <div style="font-size:8px;color:#484f58;margin-top:2px">BRIEFS GENERATED</div>
        </div>
      </div>
      <!-- Loop status -->
      <div style="display:grid;grid-template-columns:repeat(4,1fr);gap:6px;margin-bottom:12px">
        <div style="background:#070b11;border:1px solid #21262d;border-radius:4px;padding:6px">
          <div style="font-size:8px;color:#58a6ff;font-weight:700;margin-bottom:2px">LOOP 1 — ENRICH</div>
          <div style="font-size:8px;color:#484f58">Enriches CRITICAL alerts with attribution, attack type, recommended action every 30s</div>
        </div>
        <div style="background:#070b11;border:1px solid #21262d;border-radius:4px;padding:6px">
          <div style="font-size:8px;color:#3fb950;font-weight:700;margin-bottom:2px">LOOP 2 — KEYWORDS</div>
          <div style="font-size:8px;color:#484f58" id="ai-loop2-last">Auto-adds new attack terms from messages every 2h (confidence ≥ 80%)</div>
        </div>
        <div style="background:#070b11;border:1px solid #21262d;border-radius:4px;padding:6px">
          <div style="font-size:8px;color:#e3b341;font-weight:700;margin-bottom:2px">LOOP 3 — VET CHANNELS</div>
          <div style="font-size:8px;color:#484f58">AI reads channel posts, auto-approves/dismisses every 5min</div>
        </div>
        <div style="background:#070b11;border:1px solid #21262d;border-radius:4px;padding:6px">
          <div style="font-size:8px;color:#8b949e;font-weight:700;margin-bottom:2px">LOOP 4 — BRIEF</div>
          <div style="font-size:8px;color:#484f58" id="ai-loop4-last">Generates structured threat intel brief every 6h</div>
        </div>
      </div>
      <!-- Latest threat brief -->
      <div id="ai-brief-panel" style="display:none;background:#070b11;border:1px solid #58a6ff22;border-radius:4px;padding:10px">
        <div style="font-size:9px;font-weight:700;color:#58a6ff;margin-bottom:6px">LATEST THREAT BRIEF</div>
        <div style="display:flex;gap:8px;align-items:baseline;margin-bottom:6px">
          <span id="ai-brief-level" style="font-size:12px;font-weight:700"></span>
          <span id="ai-brief-time" style="font-size:8px;color:#484f58"></span>
          <span id="ai-brief-msgs" style="font-size:8px;color:#484f58"></span>
        </div>
        <div id="ai-brief-summary" style="font-size:10px;color:#8b949e;margin-bottom:8px"></div>
        <div style="display:grid;grid-template-columns:1fr 1fr;gap:8px">
          <div>
            <div style="font-size:8px;color:#484f58;margin-bottom:3px">TARGETED SECTORS</div>
            <div id="ai-brief-sectors" style="font-size:9px;color:#e6edf3"></div>
          </div>
          <div>
            <div style="font-size:8px;color:#484f58;margin-bottom:3px">RECOMMENDED ACTIONS</div>
            <div id="ai-brief-actions" style="font-size:9px;color:#e6edf3"></div>
          </div>
        </div>
      </div>
      <div style="font-size:9px;color:#484f58;margin-top:8px">
        Requires <code style="font-size:8px;color:#e3b341">OPENAI_API_KEY</code> env var ·
        Start: <code style="font-size:8px;color:#e3b341">set OPENAI_API_KEY=sk-...</code> then click ▶ Start Agent
      </div>
    </div>

    <!-- Hunt Leads Panel (LOOP 5 output) -->
    <div style="background:#0d1117;border:1px solid #21262d;border-radius:6px;padding:16px;margin-top:16px">
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px">
        <div>
          <span style="font-size:11px;font-weight:700;color:#d29922">🎯 THREAT HUNTER — GROUP LEADS</span>
          <span id="hunt-count" style="font-size:9px;color:#484f58;margin-left:8px"></span>
        </div>
        <button onclick="loadHuntLeads()" style="font-size:9px;padding:2px 8px;background:#161b22;border:1px solid #30363d;color:#8b949e;border-radius:3px;cursor:pointer">↻ Refresh</button>
      </div>
      <div id="hunt-leads-list" style="font-size:10px;color:#8b949e">Loading...</div>
    </div>

    <!-- Network Graph Summary Panel (LOOP 7 output) -->
    <div style="background:#0d1117;border:1px solid #21262d;border-radius:6px;padding:16px;margin-top:16px">
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px">
        <div>
          <span style="font-size:11px;font-weight:700;color:#3fb950">🕸 CHANNEL NETWORK GRAPH</span>
          <span id="network-stats" style="font-size:9px;color:#484f58;margin-left:8px"></span>
        </div>
        <button onclick="loadNetworkGraph()" style="font-size:9px;padding:2px 8px;background:#161b22;border:1px solid #30363d;color:#8b949e;border-radius:3px;cursor:pointer">↻ Refresh</button>
      </div>
      <div id="network-top-unknown" style="font-size:10px;color:#8b949e">Loading...</div>
    </div>

    <!-- AI Agent Live Log Panel -->
    <div style="background:#0d1117;border:1px solid #21262d;border-radius:6px;padding:16px">
      <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:10px">
        <div>
          <span style="font-size:11px;font-weight:700;color:#58a6ff">🤖 AI AGENT — LIVE LOG</span>
          <span id="ai-log-count" style="font-size:9px;color:#484f58;margin-left:8px"></span>
        </div>
        <div style="display:flex;gap:6px;align-items:center">
          <label style="font-size:9px;color:#484f58;display:flex;align-items:center;gap:4px;cursor:pointer">
            <input type="checkbox" id="ai-log-autoscroll" checked style="cursor:pointer"> auto-scroll
          </label>
          <select id="ai-log-filter" onchange="loadAILog()" style="font-size:9px;padding:2px 6px;background:#161b22;border:1px solid #30363d;color:#8b949e;border-radius:3px">
            <option value="ALL">All</option>
            <option value="ENRICH">Enrichments</option>
            <option value="LOOP2">Keywords</option>
            <option value="LOOP3">Channel Vetting</option>
            <option value="LOOP4">Threat Brief</option>
            <option value="LOOP5">Threat Hunter</option>
            <option value="LOOP6">Escalation</option>
            <option value="LOOP7">Network Graph</option>
            <option value="ERROR">Errors</option>
          </select>
          <button onclick="loadAILog()" style="font-size:9px;padding:2px 8px;background:#161b22;border:1px solid #30363d;color:#8b949e;border-radius:3px;cursor:pointer">↻ Refresh</button>
        </div>
      </div>
      <div id="ai-log-box" style="background:#070b11;border:1px solid #21262d;border-radius:4px;padding:8px;font-size:9px;font-family:monospace;color:#8b949e;overflow-y:auto;height:320px;white-space:pre-wrap;word-break:break-all">Loading…</div>
    </div>

    <!-- Discovery Engine Panel -->
    <div style="background:#0d1117;border:1px solid #21262d;border-radius:6px;padding:16px">
      <div style="display:flex;align-items:center;gap:10px;margin-bottom:12px">
        <span style="font-size:11px;font-weight:700;color:#8b949e;text-transform:uppercase;letter-spacing:.5px">🔍 Live Discovery Engine</span>
        <span style="font-size:9px;color:#484f58">Auto-discovers new hacktivist channels from forwards, mentions &amp; periodic search</span>
        <div style="flex:1"></div>
        <button onclick="loadDiscoveredChannels()" style="font-size:10px;padding:3px 10px;background:#0d1117;border:1px solid #30363d;color:#8b949e;border-radius:4px;cursor:pointer">↻ Refresh</button>
      </div>
      <div style="display:flex;gap:10px;margin-bottom:10px;flex-wrap:wrap">
        <div style="font-size:10px;color:#484f58">Filter:
          <select id="disc-filter" onchange="loadDiscoveredChannels()" style="background:#161b22;border:1px solid #30363d;border-radius:3px;padding:2px 6px;color:#e6edf3;font-size:10px;margin-left:4px">
            <option value="all">All</option>
            <option value="pending_review" selected>Pending Review</option>
            <option value="approved">Approved</option>
            <option value="dismissed">Dismissed</option>
          </select>
        </div>
        <span id="disc-count" style="font-size:10px;color:#484f58"></span>
      </div>
      <div id="disc-engine-list" style="max-height:320px;overflow-y:auto">
        <div style="color:#484f58;font-size:10px;text-align:center;padding:20px">Loading…</div>
      </div>
    </div>

  </div><!-- #tab-admin -->

  <!-- ═══════════════════════════ APT TRACKER TAB ═══════════════════════════ -->
  <div id="tab-apt" class="tab-panel" style="display:none;flex-direction:column;height:calc(100vh - 42px);overflow:hidden">
    <div class="apt-page">
      <!-- LEFT SIDEBAR — APT List -->
      <div class="apt-sidebar">
        <div class="apt-sidebar-head">
          <div style="font-size:13px;font-weight:700;color:#58a6ff;margin-bottom:8px">🎯 APT TRACKER</div>
          <input type="text" id="apt-filter-input" placeholder="Filter threat actors..." oninput="aptFilterSidebar()"
                 style="width:100%;background:#0d1117;border:1px solid #30363d;border-radius:4px;padding:5px 8px;color:#e6edf3;font-size:11px;box-sizing:border-box">
        </div>
        <div id="apt-sidebar-list" style="flex:1;overflow-y:auto"></div>
      </div>

      <!-- MAIN PANEL — APT Detail -->
      <div class="apt-main" id="apt-detail-panel">
        <div style="text-align:center;color:#484f58;margin-top:80px">
          <div style="font-size:48px;margin-bottom:12px">🎯</div>
          <div style="font-size:14px;color:#6e7681">Select a threat actor from the sidebar</div>
        </div>
      </div>

      <!-- RIGHT SIDEBAR — IOC Lookup -->
      <div class="apt-lookup">
        <div style="font-size:12px;font-weight:700;color:#e6edf3;margin-bottom:8px">IOC LOOKUP</div>
        <div class="lookup-input">
          <input type="text" id="apt-ioc-input" placeholder="IP, domain, hash, CVE..."
                 onkeydown="if(event.key==='Enter')aptLookupIOC()">
          <button onclick="aptLookupIOC()" style="background:#238636;border:none;color:#fff;padding:6px 10px;border-radius:4px;cursor:pointer;font-size:10px;font-weight:700;white-space:nowrap">LOOKUP</button>
        </div>
        <div id="apt-ioc-type-badge" style="font-size:9px;color:#8b949e;margin-bottom:8px"></div>
        <div id="apt-lookup-result"></div>

        <div style="border-top:1px solid #21262d;margin-top:14px;padding-top:12px">
          <div style="font-size:10px;color:#484f58">IOC lookup checks local intelligence database and verifies IPs/domains via AbuseIPDB. Click any IOC in the detail panel to auto-lookup.</div>
        </div>
      </div>
    </div>
  </div><!-- #tab-apt -->

  <!-- ═══════════════════════════════ CHAT TAB ══════════════════════════════ -->
  <div id="tab-chat" class="tab-panel" style="display:none;flex-direction:column;height:calc(100vh - 42px);overflow:hidden">

    <!-- Header bar -->
    <div style="background:#0a0f17;border-bottom:1px solid #21262d;padding:10px 20px;display:flex;align-items:center;gap:10px;flex-shrink:0">
      <span style="font-size:13px;font-weight:700;color:#58a6ff">💬 THREAT INTEL CHAT</span>
      <span style="font-size:10px;color:#484f58">Ask anything about monitored channels and threat activity</span>
      <div style="flex:1"></div>
      <button onclick="exportChatReport()" style="font-size:10px;padding:3px 10px;background:#0d1117;border:1px solid #30363d;color:#8b949e;border-radius:4px;cursor:pointer">📋 Export</button>
      <button onclick="clearChat()" style="font-size:10px;padding:3px 10px;background:#1a0d0d;border:1px solid #da363355;color:#da3633;border-radius:4px;cursor:pointer">🗑 Clear</button>
      <button id="chat-src-toggle" onclick="toggleSourcesPanel()" style="font-size:10px;padding:3px 10px;background:#161b22;border:1px solid #30363d;color:#58a6ff;border-radius:4px;cursor:pointer">📎 SOURCES</button>
    </div>

    <!-- Body: chat + sources side by side -->
    <div style="display:flex;flex:1;overflow:hidden;min-height:0">

      <!-- Left: conversation -->
      <div style="flex:1;display:flex;flex-direction:column;min-width:0;border-right:1px solid #21262d">
        <!-- Message list -->
        <div id="chat-messages" style="flex:1;overflow-y:auto;padding:16px 20px;display:flex;flex-direction:column;gap:12px">
          <div id="chat-empty" style="margin:auto;text-align:center;color:#484f58;font-size:12px">
            <div style="font-size:28px;margin-bottom:8px">💬</div>
            <div style="font-weight:600;margin-bottom:4px;color:#6e7681">Threat Intelligence Assistant</div>
            <div>Ask about channels, attack targets, threat actors, IOCs, or any intel.</div>
            <div style="margin-top:12px;display:flex;flex-wrap:wrap;gap:6px;justify-content:center" id="chat-suggestions">
              <button onclick="chatSuggest(this)" style="font-size:10px;padding:4px 10px;background:#161b22;border:1px solid #30363d;color:#8b949e;border-radius:12px;cursor:pointer">What activity targets Jordanian banks?</button>
              <button onclick="chatSuggest(this)" style="font-size:10px;padding:4px 10px;background:#161b22;border:1px solid #30363d;color:#8b949e;border-radius:12px;cursor:pointer">Summarize the latest CRITICAL alerts</button>
              <button onclick="chatSuggest(this)" style="font-size:10px;padding:4px 10px;background:#161b22;border:1px solid #30363d;color:#8b949e;border-radius:12px;cursor:pointer">Which threat actors are most active?</button>
              <button onclick="chatSuggest(this)" style="font-size:10px;padding:4px 10px;background:#161b22;border:1px solid #30363d;color:#8b949e;border-radius:12px;cursor:pointer">Show DDoS attacks in the last week</button>
              <button onclick="chatSuggest(this)" style="font-size:10px;padding:4px 10px;background:#161b22;border:1px solid #30363d;color:#8b949e;border-radius:12px;cursor:pointer">Any government websites targeted?</button>
            </div>
          </div>
        </div>
        <!-- Input area -->
        <div style="border-top:1px solid #21262d;padding:12px 16px;background:#0a0f17;flex-shrink:0">
          <div style="display:flex;gap:8px;align-items:flex-end">
            <textarea id="chat-input" rows="2" placeholder="Ask anything about threat intelligence... (Enter to send, Shift+Enter for newline)"
              style="flex:1;background:#161b22;border:1px solid #30363d;border-radius:6px;color:#e6edf3;font-size:12px;padding:8px 10px;resize:none;font-family:inherit;line-height:1.4"
              onkeydown="chatInputKeydown(event)"></textarea>
            <button id="chat-send-btn" onclick="sendChatMessage()"
              style="padding:8px 16px;background:#1f6feb;border:none;border-radius:6px;color:#fff;font-size:12px;font-weight:600;cursor:pointer;white-space:nowrap;height:52px">
              Send ▶
            </button>
          </div>
          <div style="font-size:9px;color:#484f58;margin-top:4px">
            <span id="chat-model-info">gpt-4o · smart context retrieval</span>
            <span id="chat-threat-pulse" style="margin-left:8px"></span>
          </div>
        </div>
      </div><!-- left -->

      <!-- Right: sources panel (hidden by default, toggled by button) -->
      <div id="chat-sources-panel" style="width:340px;flex-shrink:0;display:none;flex-direction:column;overflow:hidden">
        <div style="padding:10px 14px;border-bottom:1px solid #21262d;background:#0a0f17;flex-shrink:0;display:flex;align-items:center;gap:6px">
          <span style="font-size:11px;font-weight:700;color:#8b949e">📎 SOURCES</span>
          <span id="chat-src-count" style="font-size:9px;color:#484f58"></span>
        </div>
        <div id="chat-sources" style="flex:1;overflow-y:auto;padding:10px">
          <div style="color:#484f58;font-size:11px;text-align:center;margin-top:40px">Sources appear here after each answer</div>
        </div>
      </div><!-- right -->

    </div><!-- body -->
  </div><!-- #tab-chat -->

</div><!-- .page -->

<!-- CHANNEL IOC PANEL (slide-in from right) -->
<div id="ch-ioc-overlay" style="display:none;position:fixed;inset:0;background:rgba(0,0,0,.7);z-index:550;display:none" onclick="if(event.target===this)closeChannelIOC()">
  <div id="ch-ioc-panel" style="position:absolute;top:0;right:0;width:min(480px,95vw);height:100vh;background:#161b22;border-left:1px solid #30363d;display:flex;flex-direction:column;box-shadow:-24px 0 72px rgba(0,0,0,.8)">
    <div style="padding:12px 16px;border-bottom:1px solid #21262d;background:#0a0f17;display:flex;align-items:center;gap:10px;flex-shrink:0">
      <span style="font-weight:700;font-size:13px;color:#f0f6fc" id="ch-ioc-title">Channel IOCs</span>
      <span id="ch-ioc-count" style="font-size:10px;color:#484f58"></span>
      <div style="flex:1"></div>
      <button onclick="exportChannelIOCs()" style="background:#21262d;border:1px solid #30363d;color:#8b949e;border-radius:4px;padding:2px 9px;cursor:pointer;font-size:10px">⬇ CSV</button>
      <span onclick="closeChannelIOC()" style="cursor:pointer;color:#6e7681;font-size:18px;padding:0 4px">✕</span>
    </div>
    <!-- Type filter -->
    <div style="padding:6px 16px;border-bottom:1px solid #21262d;display:flex;gap:4px;flex-wrap:wrap;flex-shrink:0">
      <button class="cioc-filter sel" data-type="ALL"    onclick="setCIOCFilter('ALL')">All</button>
      <button class="cioc-filter"     data-type="ipv4"   onclick="setCIOCFilter('ipv4')">IP</button>
      <button class="cioc-filter"     data-type="domain" onclick="setCIOCFilter('domain')">Domain</button>
      <button class="cioc-filter"     data-type="url"    onclick="setCIOCFilter('url')">URL</button>
      <button class="cioc-filter"     data-type="email"  onclick="setCIOCFilter('email')">Email</button>
      <button class="cioc-filter"     data-type="hash_md5" onclick="setCIOCFilter('hash_md5')">MD5</button>
      <button class="cioc-filter"     data-type="hash_sha256" onclick="setCIOCFilter('hash_sha256')">SHA256</button>
      <input type="text" id="ch-ioc-search" placeholder="filter value…" oninput="renderCIOCList()"
        style="background:#21262d;border:1px solid #30363d;color:#e6edf3;border-radius:4px;padding:2px 8px;font-size:11px;flex:1;min-width:100px;margin-left:4px">
    </div>
    <div id="ch-ioc-list" style="overflow-y:auto;flex:1;padding:4px 0"></div>
  </div>
</div>

<!-- KEYBOARD SHORTCUT HELP OVERLAY (? key) -->
<div id="help-overlay" style="display:none;position:fixed;inset:0;background:rgba(0,0,0,.85);z-index:700;display:none;align-items:center;justify-content:center" onclick="if(event.target===this)closeHelp()">
  <div style="background:#161b22;border:1px solid #30363d;border-radius:10px;width:min(580px,94vw);padding:24px;box-shadow:0 24px 72px rgba(0,0,0,.9)">
    <div style="display:flex;justify-content:space-between;align-items:center;margin-bottom:16px">
      <h3 style="margin:0;font-size:14px;font-weight:700;color:#f0f6fc">Keyboard Shortcuts</h3>
      <span onclick="closeHelp()" style="cursor:pointer;color:#6e7681;font-size:18px;padding:0 4px">✕</span>
    </div>
    <div style="display:grid;grid-template-columns:1fr 1fr;gap:0 24px;font-size:11px">
      <div style="color:#484f58;font-weight:700;text-transform:uppercase;font-size:9px;letter-spacing:.6px;padding:4px 0;border-bottom:1px solid #21262d;margin-bottom:6px">Navigation</div>
      <div style="color:#484f58;font-weight:700;text-transform:uppercase;font-size:9px;letter-spacing:.6px;padding:4px 0;border-bottom:1px solid #21262d;margin-bottom:6px">Actions</div>
      <div style="display:flex;flex-direction:column;gap:5px">
        <div><kbd style="background:#21262d;border:1px solid #30363d;border-radius:3px;padding:1px 6px;font-size:10px;color:#e6edf3">1</kbd> Monitor tab</div>
        <div><kbd style="background:#21262d;border:1px solid #30363d;border-radius:3px;padding:1px 6px;font-size:10px;color:#e6edf3">2</kbd> Dashboard tab</div>
        <div><kbd style="background:#21262d;border:1px solid #30363d;border-radius:3px;padding:1px 6px;font-size:10px;color:#e6edf3">3</kbd> IOC Intel tab</div>
        <div><kbd style="background:#21262d;border:1px solid #30363d;border-radius:3px;padding:1px 6px;font-size:10px;color:#e6edf3">4</kbd> Timeline tab</div>
        <div style="margin-top:4px"><kbd style="background:#21262d;border:1px solid #30363d;border-radius:3px;padding:1px 6px;font-size:10px;color:#e6edf3">j</kbd> Scroll down messages</div>
        <div><kbd style="background:#21262d;border:1px solid #30363d;border-radius:3px;padding:1px 6px;font-size:10px;color:#e6edf3">k</kbd> Scroll up messages</div>
      </div>
      <div style="display:flex;flex-direction:column;gap:5px">
        <div><kbd style="background:#21262d;border:1px solid #30363d;border-radius:3px;padding:1px 6px;font-size:10px;color:#e6edf3">Ctrl+K</kbd> Global search</div>
        <div><kbd style="background:#21262d;border:1px solid #30363d;border-radius:3px;padding:1px 6px;font-size:10px;color:#e6edf3">/</kbd> Focus tab search</div>
        <div><kbd style="background:#21262d;border:1px solid #30363d;border-radius:3px;padding:1px 6px;font-size:10px;color:#e6edf3">?</kbd> This help panel</div>
        <div><kbd style="background:#21262d;border:1px solid #30363d;border-radius:3px;padding:1px 6px;font-size:10px;color:#e6edf3">Esc</kbd> Close modals</div>
        <div style="margin-top:4px"><kbd style="background:#21262d;border:1px solid #30363d;border-radius:3px;padding:1px 6px;font-size:10px;color:#e6edf3">↑↓</kbd> Navigate search results</div>
        <div><kbd style="background:#21262d;border:1px solid #30363d;border-radius:3px;padding:1px 6px;font-size:10px;color:#e6edf3">Enter</kbd> Open selected result</div>
      </div>
    </div>
    <div style="margin-top:16px;padding-top:12px;border-top:1px solid #21262d;font-size:10px;color:#484f58">
      Live refresh every 15s · Click any keyword chip to filter · Click channel to select · Drag IOC columns to sort
    </div>
  </div>
</div>

<!-- GLOBAL SEARCH MODAL (Ctrl+K) -->
<div id="gsearch-overlay" style="display:none;position:fixed;inset:0;background:rgba(0,0,0,.88);z-index:600;display:none;align-items:flex-start;justify-content:center;backdrop-filter:blur(4px);padding-top:80px" onclick="if(event.target===this)closeGSearch()">
  <div style="background:#161b22;border:1px solid #30363d;border-radius:10px;width:min(760px,95vw);max-height:75vh;display:flex;flex-direction:column;box-shadow:0 32px 80px rgba(0,0,0,.9);overflow:hidden">
    <!-- Search input -->
    <div style="display:flex;align-items:center;gap:8px;padding:10px 14px;border-bottom:1px solid #21262d;background:#0a0f17">
      <span style="color:#6e7681;font-size:14px">🔍</span>
      <input id="gs-input" type="text" placeholder="Search across all channels… (keyword, IP, domain, hash)" autocomplete="off"
        style="flex:1;background:transparent;border:none;outline:none;color:#e6edf3;font-size:14px;font-family:inherit"
        oninput="gsSearch()" onkeydown="gsKeydown(event)">
      <div style="display:flex;gap:6px;align-items:center">
        <select id="gs-priority" onchange="gsSearch()" style="background:#21262d;border:1px solid #30363d;color:#e6edf3;border-radius:4px;padding:2px 6px;font-size:11px">
          <option value="ALL">All</option><option value="CRITICAL">Critical</option><option value="MEDIUM">Medium</option>
        </select>
        <span onclick="closeGSearch()" style="cursor:pointer;color:#6e7681;padding:2px 8px;font-size:16px">✕</span>
      </div>
    </div>
    <!-- Results list -->
    <div id="gs-results" style="overflow-y:auto;flex:1;padding:4px 0"></div>
    <!-- Footer -->
    <div style="padding:6px 14px;border-top:1px solid #21262d;background:#0a0f17;font-size:10px;color:#484f58;display:flex;gap:16px">
      <span>↑↓ navigate</span><span>Enter jump to channel</span><span>Esc close</span>
      <div class="spacer"></div>
      <span id="gs-count" style="color:#6e7681"></span>
    </div>
  </div>
</div>

<!-- CONTEXT MODAL -->
<div id="ctx-overlay" class="ctx-overlay" style="display:none" onclick="if(event.target===this)closeContext()">
  <div class="ctx-panel">
    <div class="ctx-head">
      <h3 id="ctx-title">Message Context</h3>
      <span class="ctx-meta" id="ctx-meta"></span>
      <button class="ctx-close" onclick="closeContext()">✕</button>
    </div>
    <div class="ctx-body" id="ctx-body">
      <div class="loading-msg">Loading…</div>
    </div>
  </div>
</div>

<script>
// ═══════════════════════════════════════════════════
// GLOBALS
// ═══════════════════════════════════════════════════
const HOT_KWS = new Set([
  'الاردن','الأردن','jordan','اردني','أردني','.jo','.gov.jo','.mil.jo',
  'hacked','breached','defaced','leak','dump','wiper','destroy','تسريب','تم اختراق',
  'arab bank','البنك العربي','bank of jordan','بنك الأردن','housing bank','بنك الإسكان',
  'ministry of interior','وزارة الداخلية','ministry of defense','وزارة الدفاع',
  'royal court','الديوان الملكي','prime minister','رئاسة الوزراء',
  'jordan islamic bank','البنك الإسلامي الأردني','jcbank','jmis'
]);
const WEEKDAYS = ['Mon','Tue','Wed','Thu','Fri','Sat','Sun'];

let currentCh      = null;
let allMsgs        = [];
let dashData       = null;
let gfMsgs         = [];
let gfKeyword      = '';
let iocData        = [];
let iocSortKey     = 'count';
let iocSortAsc     = false;
let iocTypeFilter  = 'ALL';
let _scanPoll      = null;
let _prevCritCount = null;
let _lastMsgTs     = '';
let _channelsData  = [];   // cached channels list for threat profile lookups

function esc(s) {
  return String(s||'').replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;').replace(/"/g,'&quot;');
}
function relTime(ts) {
  if (!ts) return '';
  const d = Date.now() - new Date(ts).getTime();
  if (d < 60000)  return 'just now';
  if (d < 3600000) return Math.floor(d/60000)+'m ago';
  if (d < 86400000) return Math.floor(d/3600000)+'h ago';
  return Math.floor(d/86400000)+'d ago';
}

// ═══════════════════════════════════════════════════
// MAIN TAB SWITCHING
// ═══════════════════════════════════════════════════
let currentMainTab = 'monitor';
function switchMainTab(tab) {
  currentMainTab = tab;
  ['monitor','dashboard','ioc','timeline','chat','admin','apt'].forEach(t => {
    const tp = document.getElementById('tab-'+t);
    const np = document.getElementById('nav-'+t);
    if (tp) tp.classList.toggle('active', t===tab);
    if (np) np.classList.toggle('active', t===tab);
  });
  // tabs that use flex layout
  const adminPanel = document.getElementById('tab-admin');
  if (adminPanel) adminPanel.style.display = tab === 'admin' ? 'flex' : 'none';
  const chatPanel = document.getElementById('tab-chat');
  if (chatPanel) chatPanel.style.display = tab === 'chat' ? 'flex' : 'none';
  const aptPanel = document.getElementById('tab-apt');
  if (aptPanel) aptPanel.style.display = tab === 'apt' ? 'flex' : 'none';
  if (tab === 'dashboard') loadDashboard();
  if (tab === 'ioc')       loadBlocklist();
  if (tab === 'timeline')  loadTimeline();
  if (tab === 'apt')       loadAPTTab();
  if (tab === 'admin')     loadAdminPanel();
  else                     stopAILogRefresh();
  if (tab === 'chat')      loadChatTab();
}

// ═══════════════════════════════════════════════════
// MONITOR TAB
// ═══════════════════════════════════════════════════
loadChannels().then(() => {
  // Auto-load the global all-channels feed on startup
  selectAllChannels(document.getElementById('all-ch-btn'));
});
updateLiveRate();
setInterval(refreshLoop, 15000);

async function refreshLoop() {
  await loadChannels();
  if (currentMainTab === 'dashboard') {
    loadDashboard();
    checkEscalation();
  }
  if (currentMainTab === 'timeline') {
    loadTimeline(true);  // silent incremental — only prepend new messages
  }
  if (currentMainTab === 'ioc') {
    loadIOCData();
  }
  if (currentMainTab === 'admin') {
    loadAdminPanelStatus();  // only update system health stats, no heavy panel rebuilds
    checkEscalation();
  }
  checkNewMessages();
  updateLiveRate();
}

async function updateLiveRate() {
  try {
    const r = await fetch('/api/stats/summary');
    const s = await r.json();
    const rate = s.critical_1h || 0;
    const el   = document.getElementById('ts-rate');
    const dot  = document.getElementById('ts-alert-dot');
    if (el) {
      el.textContent = rate;
      el.style.color = rate > 0 ? '#ff7b7b' : '#3fb950';
    }
    if (dot) {
      dot.style.background  = rate > 0 ? '#da3633' : '#238636';
      dot.style.boxShadow   = rate > 0 ? '0 0 8px #da3633' : '0 0 6px #238636';
      dot.style.animation   = rate > 0 ? 'pulse-red 1s infinite' : 'pulse 2s infinite';
    }
    // Wrap border flashes red when active
    const wrap = document.getElementById('ts-rate-wrap');
    if (wrap) wrap.style.borderColor = rate > 0 ? '#da363388' : '#da363333';
  } catch(e) {}
}

async function loadChannels() {
  try {
    const r  = await fetch('/api/channels');
    const ch = await r.json();
    _channelsData = ch;
    renderChannels(ch);
    const total    = ch.reduce((s,c)=>s+c.count,0);
    const critical = ch.reduce((s,c)=>s+c.critical,0);
    const medium   = ch.reduce((s,c)=>s+c.medium,0);
    document.getElementById('ts-ch').textContent   = ch.length;
    document.getElementById('ts-crit').textContent = critical;
    document.getElementById('ts-med').textContent  = medium;

    // Detect new criticals
    if (_prevCritCount !== null && critical > _prevCritCount) {
      const diff = critical - _prevCritCount;
      showToast(`⚠ ${diff} new CRITICAL alert${diff>1?'s':''}`, true);
      document.getElementById('nav-monitor').querySelector('.tab-badge') ||
        document.getElementById('nav-monitor').insertAdjacentHTML('beforeend',
          '<span class="tab-badge" id="monitor-badge">NEW</span>');
    }
    _prevCritCount = critical;
    updateTitle(critical);

    // Ticker
    if (ch.length) {
      const topCh = ch.filter(c=>c.critical>0).sort((a,b)=>b.last_critical_date.localeCompare(a.last_critical_date));
      if (topCh.length) {
        const t = topCh[0];
        const ago = relTime(t.last_critical_date);
        document.getElementById('ticker').innerHTML =
          `Latest critical: <span class="ticker-hot">@${esc(t.channel_username)}</span> — ${ago} — ${t.critical} alert${t.critical>1?'s':''}`;
      }
    }
    document.getElementById('live-dot').className = 'live-dot';
  } catch(e) {
    document.getElementById('live-dot').className = 'live-dot dead';
  }
}

async function checkNewMessages() {
  if (!currentCh) return;
  const priority = document.getElementById('f-priority').value;
  const since    = document.getElementById('f-since').value;
  let url = currentCh === '__ALL__'
    ? `/api/messages/all?limit=5000&priority=${priority}`
    : `/api/messages/${encodeURIComponent(currentCh)}?priority=${priority}`;
  if (since) url += `&since=${since}`;
  const r = await fetch(url).catch(()=>null);
  if (!r) return;
  const msgs = await r.json();
  // Compare newest timestamp — works even when both arrays hit the 5000 cap
  const newestTs = arr => arr.reduce((best,m) => (m.timestamp_utc||'') > best ? m.timestamp_utc : best, '');
  const hasNew = msgs.length > allMsgs.length || newestTs(msgs) > newestTs(allMsgs);
  if (hasNew) {
    const diff = msgs.length - allMsgs.length;
    allMsgs = msgs;
    renderMessages(applyLocalFilters(allMsgs), 'msgs');
    const label = currentCh === '__ALL__' ? 'all channels' : `@${currentCh}`;
    const newCount = diff > 0 ? `+${diff}` : 'new';
    showToast(`${newCount} message${diff!==1?'s':''} from ${label}`, false);
    if (currentCh === '__ALL__') {
      document.getElementById('all-ch-btn').textContent =
        `🌐 ALL CHANNELS — ${msgs.length} messages`;
    }
    scrollBottom();
  }
}

const TIER_COLORS = {1:'#da3633', 2:'#e3b341', 3:'#3fb950', 0:'#484f58'};
const TIER_LABELS = {1:'T1', 2:'T2', 3:'T3', 0:'?'};

function renderChannels(channels) {
  const el = document.getElementById('ch-list');
  if (!channels.length) {
    el.innerHTML = '<div class="loading-msg">No data. Run --backfill first.</div>';
    return;
  }
  el.innerHTML = channels.map(c => {
    const hasCrit  = c.critical > 0;
    const lastCrit = c.last_critical_date;
    const ago      = relTime(lastCrit || c.last_date);
    const tier     = c.tier || 0;
    const tierCol  = TIER_COLORS[tier] || '#484f58';
    const tierLbl  = TIER_LABELS[tier] || '?';
    const silent    = c.days_silent > 30 ? `⚠ ${c.days_silent}d silent` : '';
    const tierLabel = c.tier_label ? `<div class="ch-tier-label">${esc(c.tier_label)}</div>` : '';
    const isBanned  = c.status === 'banned';

    // Mini 7-day sparkline (critical msgs per day, last 7 days)
    const spark = c.spark_7d || [0,0,0,0,0,0,0];
    const maxSpark = Math.max(...spark, 1);
    const sparkH = 14, sparkW = 56;
    const barW = Math.floor(sparkW / 7) - 1;
    const sparkBars = spark.map((v, i) => {
      const h = Math.max(1, Math.round((v / maxSpark) * sparkH));
      const x = i * (barW + 1);
      const y = sparkH - h;
      const col = v === 0 ? '#21262d' : v === maxSpark ? '#da3633' : '#7d3f3f';
      return `<rect x="${x}" y="${y}" width="${barW}" height="${h}" fill="${col}" rx="0.5"/>`;
    }).join('');
    const sparkSvg = !isBanned ? `<svg width="${sparkW}" height="${sparkH}" style="display:block;margin-top:4px;flex-shrink:0" title="7-day critical activity">${sparkBars}</svg>` : '';

    const bannedBadge = isBanned
      ? `<span style="font-size:8px;font-weight:800;padding:1px 5px;border-radius:2px;background:#6e1a1a;color:#ff6b6b;border:1px solid #da363355;letter-spacing:0.5px">BANNED</span>`
      : '';
    return `
    <div class="ch-item ${currentCh===c.channel_username?'active':''} ${hasCrit?'has-crit':''}"
         onclick="selectChannel('${esc(c.channel_username)}','${esc(c.channel)}',this)"
         style="border-left-color:${isBanned?'#6e1a1a':hasCrit?'#da3633':tierCol};opacity:${isBanned?0.6:1}">
      <div style="display:flex;align-items:center;gap:5px;margin-bottom:1px;flex-wrap:wrap">
        <span style="font-size:8px;font-weight:800;padding:1px 4px;border-radius:2px;background:${tierCol}22;color:${tierCol};border:1px solid ${tierCol}44">${tierLbl}</span>
        <div class="ch-name" style="${isBanned?'text-decoration:line-through;color:#6e7681':''}">${esc(c.channel)}</div>
        ${bannedBadge}
      </div>
      <div class="ch-sub">@${esc(c.channel_username)}</div>
      ${tierLabel}
      <div style="display:flex;align-items:flex-end;justify-content:space-between;gap:4px">
        <div class="ch-badges" style="flex:1">
          <span class="ch-count">${c.count} msgs</span>
          ${c.critical?`<span class="bdg c">${c.critical} CRIT</span>`:''}
          ${c.medium?`<span class="bdg m">${c.medium} MED</span>`:''}
          ${isBanned?`<span style="font-size:9px;color:#ff6b6b80;font-style:italic">channel removed by Telegram</span>`:''}
        </div>
        ${sparkSvg}
      </div>
      <div class="ch-last ${hasCrit&&!isBanned?'hot':''}">${ago}${silent&&!isBanned?` <span style="color:#e3b341;font-size:9px"> ${silent}</span>`:''}</div>
    </div>`;
  }).join('');
}

async function selectAllChannels(btn) {
  currentCh = '__ALL__';
  document.getElementById('chat-title').textContent = 'All Channels — Live Feed';
  document.getElementById('chat-sub').textContent   = 'Combined feed · all priorities · newest first';
  document.getElementById('filter-bar').style.display = 'flex';
  document.getElementById('statusbar').style.display  = 'flex';
  document.getElementById('chat-stat').style.display  = 'none';
  document.querySelectorAll('.ch-item').forEach(e => e.classList.remove('active'));
  document.getElementById('all-ch-btn').style.background = '#1f6feb33';
  document.getElementById('all-ch-btn').style.borderColor = '#1f6feb';
  // Hide threat profile
  const tp = document.getElementById('threat-profile');
  if (tp) tp.style.display = 'none';
  document.getElementById('msgs').innerHTML = '<div class="loading-msg">Loading all messages…</div>';
  const priority = document.getElementById('f-priority').value;
  const since    = document.getElementById('f-since').value;
  let url = `/api/messages/all?limit=5000&priority=${priority}`;
  if (since) url += `&since=${since}`;
  try {
    const r = await fetch(url);
    allMsgs = await r.json();
    renderMessages(applyLocalFilters(allMsgs), 'msgs');
    scrollBottom();
    document.getElementById('all-ch-btn').textContent =
      `🌐 ALL CHANNELS — ${allMsgs.length} messages`;
  } catch(e) {
    document.getElementById('msgs').innerHTML = '<div class="loading-msg">Error loading messages.</div>';
  }
}

async function selectChannel(username, title, el) {
  // Reset the ALL button styling when a specific channel is selected
  const allBtn = document.getElementById('all-ch-btn');
  if (allBtn) {
    allBtn.style.background = '#1f3350';
    allBtn.style.borderColor = '#1f6feb55';
    allBtn.textContent = '🌐 ALL CHANNELS — live feed';
  }
  currentCh = username;
  document.getElementById('chat-title').textContent = title || username;
  document.getElementById('chat-sub').textContent   = '@'+username;
  document.getElementById('filter-bar').style.display = 'flex';
  document.getElementById('statusbar').style.display  = 'flex';
  document.getElementById('chat-stat').style.display  = 'inline-block';
  document.querySelectorAll('.ch-item').forEach(e=>e.classList.remove('active'));
  el.classList.add('active');
  document.getElementById('sb-new').textContent = '';
  // Show threat actor profile strip
  const chData = _channelsData.find(c => c.channel_username === username);
  if (chData) showThreatProfile(chData);
  await fetchMessages(username);
}

function showThreatProfile(c) {
  const TIER_COLORS = {1:'#da3633', 2:'#e3b341', 3:'#3fb950', 0:'#484f58'};
  const THREAT_COLORS = {'CRITICAL':'#da3633','HIGH':'#e3b341','MEDIUM':'#3fb950','LOW':'#484f58'};
  const tier    = c.tier || 0;
  const tierCol = TIER_COLORS[tier] || '#484f58';
  const thrCol  = THREAT_COLORS[c.threat_level] || '#484f58';
  const isBanned = c.status === 'banned';

  document.getElementById('tp-tier-badge').textContent = tier ? `TIER ${tier}` : '?';
  document.getElementById('tp-tier-badge').style.cssText =
    `font-size:9px;font-weight:800;padding:2px 6px;border-radius:3px;background:${tierCol}22;color:${tierCol};border:1px solid ${tierCol}44`;
  document.getElementById('tp-label').textContent = c.tier_label || c.channel || username;
  document.getElementById('tp-threat').textContent = c.threat_level || 'UNKNOWN';
  document.getElementById('tp-threat').style.cssText =
    `font-size:9px;font-weight:700;padding:2px 6px;border-radius:3px;background:${thrCol}22;color:${thrCol};border:1px solid ${thrCol}44`;

  const statusBadge = document.getElementById('tp-status-badge');
  if (isBanned) {
    statusBadge.innerHTML = `<span style="font-size:9px;font-weight:800;padding:2px 6px;border-radius:3px;background:#6e1a1a;color:#ff6b6b;border:1px solid #da363355">BANNED — channel removed by Telegram</span>`;
  } else {
    statusBadge.innerHTML = `<span style="font-size:9px;padding:2px 6px;border-radius:3px;background:#1a3a1a;color:#3fb950;border:1px solid #3fb95044">ACTIVE</span>`;
  }

  const silentTxt = c.days_silent > 0 ? ` · ${c.days_silent}d silent` : '';
  document.getElementById('tp-stats').textContent =
    `${c.count} msgs · ${c.critical} critical · ${c.medium} medium${silentTxt}`;

  // IOC button in threat profile strip
  const existingIocBtn = document.getElementById('tp-ioc-btn');
  if (existingIocBtn) existingIocBtn.remove();
  const iocBtn = document.createElement('button');
  iocBtn.id = 'tp-ioc-btn';
  iocBtn.textContent = '🔗 Channel IOCs';
  iocBtn.style.cssText = 'background:#1a2d4a;border:1px solid #2d4a6e;color:#58a6ff;border-radius:4px;padding:2px 9px;cursor:pointer;font-size:10px;margin-left:8px';
  iocBtn.onclick = () => loadChannelIOCPanel(c.channel_username);
  document.getElementById('tp-stats').parentNode.appendChild(iocBtn);

  // OSINT pivot links
  const un = c.channel_username;
  const existingOsint = document.getElementById('tp-osint');
  if (existingOsint) existingOsint.remove();
  const osintDiv = document.createElement('div');
  osintDiv.id = 'tp-osint';
  osintDiv.style.cssText = 'display:flex;gap:6px;align-items:center;margin-top:4px;flex-wrap:wrap';
  const links = [
    {label:'Telegram', url:`https://t.me/${un}`, col:'#2aabee'},
    {label:'TGStat',   url:`https://tgstat.com/channel/@${un}`, col:'#3fb950'},
    {label:'IntelX',   url:`https://intelx.io/?s=%40${un}`, col:'#e3b341'},
    {label:'Shodan',   url:`https://www.shodan.io/search?query=%40${un}`, col:'#ff7b7b'},
  ];
  osintDiv.innerHTML = '<span style="font-size:9px;color:#484f58;font-weight:600">OSINT:</span>' +
    links.map(l =>
      `<a href="${l.url}" target="_blank" rel="noopener"
        style="font-size:9px;padding:1px 7px;border-radius:3px;background:${l.col}18;color:${l.col};border:1px solid ${l.col}33;text-decoration:none;cursor:pointer"
        onmouseover="this.style.background='${l.col}33'" onmouseout="this.style.background='${l.col}18'"
        >${l.label}</a>`
    ).join('');
  document.getElementById('threat-profile').appendChild(osintDiv);
  document.getElementById('threat-profile').style.display = 'block';
}

async function fetchMessages(username) {
  const priority = document.getElementById('f-priority').value;
  const since    = document.getElementById('f-since').value;
  document.getElementById('msgs').innerHTML = '<div class="loading-msg">Loading messages…</div>';
  try {
    let url = `/api/messages/${encodeURIComponent(username)}?priority=${priority}`;
    if (since) url += `&since=${since}`;
    const r = await fetch(url);
    allMsgs = await r.json();
    renderMessages(applyLocalFilters(allMsgs), 'msgs');
    scrollBottom();
  } catch(e) {
    document.getElementById('msgs').innerHTML = '<div class="loading-msg">Error loading messages.</div>';
  }
}

// ── Critical Subtype Toggle ──────────────────────────────────────────────────
const critSubState = { monitor: 'ALL', timeline: 'ALL', feed: 'ALL' };

function setCritSub(location, sub) {
  critSubState[location] = sub;
  document.querySelectorAll(`#crit-toggle-${location} .ctbtn`).forEach(b => {
    b.classList.toggle('active', b.dataset.sub === sub);
  });
  if (location === 'monitor')  applyFilters();
  if (location === 'timeline') loadTimeline();
  if (location === 'feed')     gfSearch();
}
// ─────────────────────────────────────────────────────────────────────────────

function applyFilters() { if (currentCh) renderMessages(applyLocalFilters(allMsgs), 'msgs'); }

function applyLocalFilters(msgs) {
  const priority = document.getElementById('f-priority').value;
  const since    = document.getElementById('f-since').value;
  const until    = document.getElementById('f-until').value;
  const search   = document.getElementById('f-search').value.toLowerCase();
  const sub      = critSubState.monitor;
  return msgs.filter(m => {
    if (priority !== 'ALL' && m.priority !== priority) return false;
    if (since  && m.timestamp_utc < since)        return false;
    if (until  && m.timestamp_utc > until+' 99')  return false;
    if (search) {
      const h = ((m.text_preview||'')+' '+(m.keyword_hits||[]).join(' ')).toLowerCase();
      if (!h.includes(search)) return false;
    }
    // Critical subtype filter — only filters CRITICAL messages
    if (sub !== 'ALL' && m.priority === 'CRITICAL') {
      const ms = m.critical_subtype || 'GENERAL';
      if (ms !== sub && ms !== 'BOTH') return false;
    }
    return true;
  });
}

function resetFilters() {
  document.getElementById('f-priority').value = 'ALL';
  document.getElementById('f-since').value    = '';
  document.getElementById('f-until').value    = '';
  document.getElementById('f-search').value   = '';
  if (currentCh) fetchMessages(currentCh);
}

function scrollBottom() {
  const el = document.getElementById('msgs');
  el.scrollTop = el.scrollHeight;
}

let _msgFullList = [];   // All sorted messages for lazy load
let _msgRendered = 0;    // How many already rendered
const _MSG_BATCH = 100;  // Initial + each lazy batch
let _msgScrollBound = false;

function _onMsgScroll(e) {
  const el = e.target;
  // When scrolled UP past 20% from top, load older messages (prepend)
  if (el.scrollTop < el.scrollHeight * 0.2 && _msgRendered < _msgFullList.length) {
    const prevH = el.scrollHeight;
    _renderMoreMessages(el);
    // Keep scroll position stable
    el.scrollTop += (el.scrollHeight - prevH);
  }
}

function _renderMoreMessages(el) {
  const end = _msgFullList.length;
  const start = Math.max(0, end - _msgRendered - _MSG_BATCH);
  const batch = _msgFullList.slice(start, end - _msgRendered);
  if (!batch.length) return;
  _msgRendered += batch.length;
  const html = _buildMsgHTML(batch, 'msgs', true);
  el.insertAdjacentHTML('afterbegin', html);
}

function renderMessages(msgs, containerId) {
  const el = document.getElementById(containerId);
  if (!msgs.length) {
    el.innerHTML = '<div class="empty"><div class="ico">🔍</div><p>No messages match filters</p></div>';
    if (containerId==='msgs') updateStat(0,0,0);
    return;
  }
  // Always render oldest-first so date separators flow chronologically (newest at bottom)
  const list = containerId === 'msgs'
    ? [...msgs].sort((a,b) => (a.timestamp_utc||'') < (b.timestamp_utc||'') ? -1 : 1)
    : msgs;

  // For main feed: lazy load — show last 100, prepend more on scroll up
  if (containerId === 'msgs' && list.length > _MSG_BATCH) {
    _msgFullList = list;
    const initial = list.slice(-_MSG_BATCH);
    _msgRendered = initial.length;
    el.innerHTML = _buildMsgHTML(initial, containerId, false);
    el.scrollTop = el.scrollHeight;
    if (!_msgScrollBound) {
      el.addEventListener('scroll', _onMsgScroll);
      _msgScrollBound = true;
    }
    const crit = msgs.filter(m=>m.priority==='CRITICAL').length;
    const med  = msgs.filter(m=>m.priority==='MEDIUM').length;
    updateStat(msgs.length, crit, med);
    return;
  }

  let html = _buildMsgHTML(list, containerId, false);
  el.innerHTML = html;
  if (containerId === 'msgs') {
    _msgFullList = list;
    _msgRendered = list.length;
    el.scrollTop = el.scrollHeight;
    const crit = msgs.filter(m=>m.priority==='CRITICAL').length;
    const med  = msgs.filter(m=>m.priority==='MEDIUM').length;
    updateStat(msgs.length, crit, med);
  }
}

function _buildMsgHTML(list, containerId, isPrepend) {
  let html = '', lastDate = '';
  list.forEach(m => {
    const dt      = new Date(m.timestamp_utc);
    const dateStr = dt.toLocaleDateString('en-GB',{day:'2-digit',month:'short',year:'numeric'});
    const timeStr = dt.toLocaleTimeString('en-GB',{hour:'2-digit',minute:'2-digit'}) + ' UTC';
    const irst    = m.timestamp_irst || '';
    const p       = m.priority || 'LOW';
    const kws     = m.keyword_hits || [];
    const iocs    = m.iocs || {};
    const text    = m.text_preview || '';
    const ch      = m.channel_username || m.channel || '';
    const showCh  = containerId !== 'msgs';

    if (containerId === 'msgs' && dateStr !== lastDate) {
      html += `<div class="date-sep"><span>${dateStr}</span></div>`;
      lastDate = dateStr;
    }
    const kwHtml = kws.length ? `<div class="kws">${
      kws.map(k=>`<span class="kw ${HOT_KWS.has(k.toLowerCase())?'hot':''}" onclick="event.stopPropagation();filterByKeyword('${esc(k)}')">${esc(k)}</span>`).join('')
    }</div>` : '';
    const iocHtml = Object.keys(iocs).length ? `<div class="iocs">${
      Object.entries(iocs).map(([type,vals])=>`
        <div class="ioc-row">
          <span class="ioc-lbl">${esc(type)}</span>
          ${vals.map(v=>`<span class="ioc-val" onclick="event.stopPropagation();copyVal('${esc(v)}')">${esc(v)}</span>`).join('')}
        </div>`).join('')
    }</div>` : '';
    // AI enrichment badge + inline card
    const ai  = m.ai_enrichment || null;
    const aiHtml = ai ? (() => {
      const atk    = ai.attack_type || '';
      const grp    = ai.group_attribution || '';
      const sec    = ai.target_sector || '';
      const act    = ai.recommended_action || '';
      const conf   = ai.confidence || 0;
      const sev    = ai.severity || '';
      const sevCol = {CRITICAL:'#da3633',HIGH:'#e3b341',MEDIUM:'#3fb950',LOW:'#484f58'}[sev]||'#58a6ff';
      return `<div class="ai-card" onclick="event.stopPropagation()">
        <div style="display:flex;gap:6px;align-items:center;flex-wrap:wrap;margin-bottom:3px">
          <span style="font-size:8px;padding:1px 5px;background:#58a6ff22;color:#58a6ff;border-radius:3px;font-weight:700">🤖 AI</span>
          ${grp ? `<span style="font-size:9px;color:#e6edf3;font-weight:600">${esc(grp)}</span>` : ''}
          ${atk ? `<span style="font-size:8px;color:#8b949e">${esc(atk)}</span>` : ''}
          ${sec ? `<span style="font-size:8px;padding:1px 4px;background:#21262d;color:#8b949e;border-radius:2px">${esc(sec)}</span>` : ''}
          <span style="font-size:8px;color:${sevCol}">${esc(sev)}</span>
          <span style="font-size:8px;color:#484f58">conf:${conf}%</span>
        </div>
        ${act && act!=='None' ? `<div style="font-size:8px;color:#e3b341">→ ${esc(act)}</div>` : ''}
        ${ai.summary ? `<div style="font-size:9px;color:#8b949e;margin-top:2px;font-style:italic">${esc(ai.summary)}</div>` : ''}
      </div>`;
    })() : '';
    // Critical subtype badge
    const subBadgeColors = { CYBER:'#3fb950', NATIONAL:'#58a6ff', BOTH:'#d29922', GENERAL:'#da3633' };
    const critSub = m.critical_subtype;
    const subBadge = (p === 'CRITICAL' && critSub)
      ? `<span style="font-size:8px;padding:1px 5px;border-radius:10px;background:${subBadgeColors[critSub]||'#da3633'}22;color:${subBadgeColors[critSub]||'#da3633'};border:1px solid ${subBadgeColors[critSub]||'#da3633'}44">${critSub==='BOTH'?'💻🛡':critSub==='CYBER'?'💻':critSub==='NATIONAL'?'🛡':'!'}</span>`
      : '';
    // Language badge + translate button for non-English messages
    const lang = m.language;
    const langBadge = (lang && lang !== 'ar' && lang !== 'en')
      ? `<span style="font-size:8px;padding:1px 4px;background:#1a1a2e;color:#818cf8;border-radius:2px" title="Language: ${esc(lang)}">${esc(lang.toUpperCase())}</span>`
      : '';
    const showTranslate = lang && lang !== 'en';
    const translateBtn = showTranslate
      ? `<button onclick="event.stopPropagation();translateMsg(this,${JSON.stringify(text)})" style="font-size:8px;padding:1px 6px;background:#161b22;border:1px solid #30363d;color:#818cf8;border-radius:3px;cursor:pointer;margin-left:2px">🌐</button>`
      : '';
    html += `
      <div class="bubble ${p}" onclick="openContext(${m.message_id||0},'${esc(ch)}')">
        <div class="b-meta">
          <span class="ptag ${p}">${p}</span>
          ${subBadge}
          ${showCh ? `<span class="b-channel">@${esc(ch)}</span>` : ''}
          <span class="b-time">${timeStr} · ${dateStr}</span>
          ${irst ? `<span class="b-irst">${esc(irst)}</span>` : ''}
          ${langBadge}${translateBtn}
          ${ai ? `<span style="font-size:8px;padding:1px 5px;background:#58a6ff22;color:#58a6ff;border-radius:3px;margin-left:auto">🤖 AI enriched</span>` : ''}
        </div>
        ${kwHtml}
        <div class="b-text">${esc(text)}</div>
        <div class="translate-result" style="display:none;margin-top:5px;padding:5px 8px;background:#0d1117;border-left:2px solid #818cf8;font-size:10px;color:#c9d1d9;font-style:italic"></div>
        ${iocHtml}
        ${aiHtml}
      </div>`;
  });
  return html;
}

function updateStat(total, crit, med) {
  const pill = document.getElementById('chat-stat');
  pill.textContent  = `${total} msgs · ${crit} crit · ${med} med`;
  pill.className    = 'stat-pill' + (crit>0?' red':'');
  document.getElementById('sb-text').textContent = `${total} messages · ${crit} critical · ${med} medium`;
}

function copyVal(v) { navigator.clipboard.writeText(v).catch(()=>{}); showToast('Copied: '+v); }

function exportCurrentChannel() {
  if (!currentCh) return;
  const p = document.getElementById('f-priority').value;
  const s = document.getElementById('f-search').value;
  let url  = `/api/messages/export?priority=${p}`;
  if (s) url += `&search=${encodeURIComponent(s)}`;
  // Trigger download via hidden link
  const a = document.createElement('a');
  a.href = url; a.download = ''; document.body.appendChild(a); a.click(); a.remove();
}

function showToast(msg, isCrit=false) {
  const t = document.createElement('div');
  t.className = 'toast' + (isCrit?' crit':'');
  t.textContent = msg;
  document.body.appendChild(t);
  setTimeout(()=>t.remove(), 3500);
}

// ── Sidebar tabs ──
let _scanPollDisc = null;
function switchSideTab(tab) {
  const isDisc = tab==='disc';
  document.getElementById('panel-mon').style.display  = isDisc?'none':'flex';
  document.getElementById('panel-disc').style.display = isDisc?'flex':'none';
  document.getElementById('t-mon').classList.toggle('active',!isDisc);
  document.getElementById('t-disc').classList.toggle('active',isDisc);
  if (isDisc) { loadDiscovery(); checkScanStatus(); }
}

async function loadDiscovery() {
  try {
    const r  = await fetch('/api/discovery/list');
    const ch = await r.json();
    renderDiscovery(ch);
  } catch(e) {
    document.getElementById('disc-list').innerHTML = '<div class="loading-msg">Error loading discovery data.</div>';
  }
}

function renderDiscovery(channels) {
  const el = document.getElementById('disc-list');
  if (!channels||!channels.length) {
    el.innerHTML = '<div class="loading-msg">No results. Run a scan first.</div>';
    return;
  }
  const sorted = [...channels].sort((a,b)=>(b.score||0)-(a.score||0));
  el.innerHTML = sorted.map(ch=>{
    const uname = ch.username||'';
    const stars = '★'.repeat(Math.min(ch.score||0,5))||'☆';
    const cls   = (ch.score||0)>=3?'hi':(ch.score||0)>=1?'med':'';
    const kws   = (ch.relevance_matches||[]).slice(0,4).join(', ');
    return `<div class="disc-item ${cls}">
      <div class="disc-name">${esc(ch.title||uname)}</div>
      <div class="disc-sub">@${esc(uname)} &nbsp;·&nbsp; <span style="color:#f0f6fc">${stars} ${ch.score||0}pts</span></div>
      <div class="disc-kws">${esc(kws)}</div>
      <div class="disc-acts">
        ${uname?`<button onclick="fetchDiscChannel('${esc(uname)}','${esc(ch.title||uname)}')">View</button>`:''}
        ${uname?`<button onclick="fetchDiscChannel('${esc(uname)}','${esc(ch.title||uname)}',true)">View &amp; Save</button>`:''}
      </div>
    </div>`;
  }).join('');
}

async function runScan(quick) {
  document.getElementById('disc-st').textContent = '🔄 Starting…';
  document.getElementById('btn-full-scan').disabled = true;
  await fetch('/api/discovery/scan',{method:'POST',headers:{'Content-Type':'application/json'},body:JSON.stringify({quick})});
  if (_scanPollDisc) clearInterval(_scanPollDisc);
  _scanPollDisc = setInterval(async()=>{
    const st = await (await fetch('/api/discovery/status')).json();
    if (!st.running) {
      clearInterval(_scanPollDisc); _scanPollDisc=null;
      document.getElementById('disc-st').textContent='✓ Done';
      document.getElementById('btn-full-scan').disabled=false;
      loadDiscovery();
    } else {
      document.getElementById('disc-st').textContent='🔄 Scanning…';
    }
  },3000);
}

async function checkScanStatus() {
  try {
    const st = await (await fetch('/api/discovery/status')).json();
    const el = document.getElementById('disc-st');
    el.textContent = st.running ? '🔄 Scanning…' : st.last_run ? `Last: ${new Date(st.last_run).toLocaleDateString()}` : 'Idle';
  } catch(e){}
}

async function fetchDiscChannel(username, title, save=false) {
  currentCh = username;
  document.getElementById('chat-title').textContent = title||username;
  document.getElementById('chat-sub').textContent   = '@'+username+' · live fetch';
  document.getElementById('filter-bar').style.display='flex';
  document.getElementById('statusbar').style.display='flex';
  document.getElementById('chat-stat').style.display='inline-block';
  document.getElementById('msgs').innerHTML='<div class="loading-msg">Fetching from Telegram…</div>';
  try {
    const r = await fetch(`/api/discovery/fetch?username=${encodeURIComponent(username)}&limit=100&save=${save}`);
    const d = await r.json();
    if (d.error) { document.getElementById('msgs').innerHTML=`<div class="loading-msg">Error: ${esc(d.error)}</div>`; return; }
    allMsgs = d.messages||[];
    renderMessages(applyLocalFilters(allMsgs),'msgs');
    if (save) document.getElementById('chat-sub').textContent+=' · saved ✓';
  } catch(e) {
    document.getElementById('msgs').innerHTML='<div class="loading-msg">Error fetching channel.</div>';
  }
}

// ═══════════════════════════════════════════════════
// CONTEXT MODAL
// ═══════════════════════════════════════════════════
let ctxChannel = null;
async function openContext(msgId, channelOverride) {
  const ch = channelOverride || currentCh;
  if (!ch || msgId===0) return;
  ctxChannel = ch;
  const before = Math.max(1,parseInt(document.getElementById('ctx-before').value)||5);
  const after  = Math.max(1,parseInt(document.getElementById('ctx-after').value)||5);
  document.getElementById('ctx-overlay').style.display='flex';
  document.getElementById('ctx-title').textContent='Context — @'+ch;
  document.getElementById('ctx-body').innerHTML='<div class="loading-msg">Loading context…</div>';
  document.getElementById('ctx-meta').textContent='';
  try {
    const r = await fetch(`/api/messages/${encodeURIComponent(ch)}/${encodeURIComponent(msgId)}/context?before=${before}&after=${after}`);
    const d = await r.json();
    if (!d.messages||!d.messages.length) {
      document.getElementById('ctx-body').innerHTML='<div class="loading-msg">No context found.</div>';
      return;
    }
    const src = d.source==='live'?'🟢 live':'🟡 stored';
    document.getElementById('ctx-meta').textContent=`${before}↑ ${after}↓ · ${d.total} total · ${src}`;
    renderContextMsgs(d.messages, d.target_idx);
  } catch(e) {
    document.getElementById('ctx-body').innerHTML='<div class="loading-msg">Error loading context.</div>';
  }
}

function closeContext() { document.getElementById('ctx-overlay').style.display='none'; }

// ── Channel IOC Panel ─────────────────────────────────────────────────────────
let _ciocData    = [];
let _ciocChannel = '';
let _ciocFilter  = 'ALL';

async function loadChannelIOCPanel(username) {
  _ciocChannel = username;
  _ciocFilter  = 'ALL';
  document.getElementById('ch-ioc-overlay').style.display = 'flex';
  document.getElementById('ch-ioc-title').textContent = `IOCs — @${username}`;
  document.getElementById('ch-ioc-list').innerHTML = '<div style="padding:24px;text-align:center;color:#484f58">Loading…</div>';
  document.querySelectorAll('.cioc-filter').forEach(b => b.classList.toggle('sel', b.dataset.type==='ALL'));
  try {
    const r = await fetch(`/api/channel/${encodeURIComponent(username)}/iocs`);
    const d = await r.json();
    _ciocData = d.iocs || [];
    document.getElementById('ch-ioc-count').textContent = `${_ciocData.length} unique IOCs · ${d.msg_count} msgs`;
    renderCIOCList();
  } catch(e) {
    document.getElementById('ch-ioc-list').innerHTML = '<div style="padding:24px;text-align:center;color:#da3633">Error loading IOCs</div>';
  }
}

function closeChannelIOC() {
  document.getElementById('ch-ioc-overlay').style.display = 'none';
}

function setCIOCFilter(type) {
  _ciocFilter = type;
  document.querySelectorAll('.cioc-filter').forEach(b => b.classList.toggle('sel', b.dataset.type === type));
  renderCIOCList();
}

function renderCIOCList() {
  const search  = (document.getElementById('ch-ioc-search').value || '').toLowerCase();
  const filtered = _ciocData.filter(ioc => {
    if (_ciocFilter !== 'ALL' && ioc.type !== _ciocFilter) return false;
    if (search && !ioc.value.toLowerCase().includes(search) && !ioc.type.includes(search)) return false;
    return true;
  });
  const TYPE_COLORS = {ipv4:'#ff7b7b',domain:'#58a6ff',url:'#79c0ff',email:'#3fb950',hash_md5:'#e3b341',hash_sha256:'#e3b341',cve:'#da3633'};
  const el = document.getElementById('ch-ioc-list');
  if (!filtered.length) {
    el.innerHTML = '<div style="padding:24px;text-align:center;color:#484f58">No IOCs match filter</div>';
    return;
  }
  el.innerHTML = filtered.slice(0, 200).map(ioc => {
    const col = TYPE_COLORS[ioc.type] || '#8b949e';
    return `<div style="display:flex;align-items:center;gap:8px;padding:6px 16px;border-bottom:1px solid #21262d;font-size:11px">
      <span style="font-size:8px;font-weight:700;padding:1px 5px;border-radius:2px;background:${col}18;color:${col};border:1px solid ${col}33;white-space:nowrap">${esc(ioc.type)}</span>
      <span style="flex:1;font-family:monospace;color:#e6edf3;word-break:break-all;font-size:10px">${esc(ioc.value)}</span>
      <span style="font-size:9px;color:#484f58;flex-shrink:0">${ioc.count}×</span>
      <button onclick="navigator.clipboard.writeText('${esc(ioc.value)}')" title="Copy"
        style="background:transparent;border:none;color:#6e7681;cursor:pointer;font-size:12px;padding:0 2px;flex-shrink:0">⎘</button>
    </div>`;
  }).join('');
}

function exportChannelIOCs() {
  const rows = [['type','value','count']];
  _ciocData.forEach(ioc => rows.push([ioc.type, ioc.value, ioc.count]));
  const csv = rows.map(r => r.map(v => `"${String(v).replace(/"/g,'""')}"`).join(',')).join('\n');
  const a = document.createElement('a');
  a.href = 'data:text/csv;charset=utf-8,' + encodeURIComponent(csv);
  a.download = `iocs_${_ciocChannel}_${new Date().toISOString().slice(0,10)}.csv`;
  a.click();
}

function renderContextMsgs(msgs, targetIdx) {
  const el = document.getElementById('ctx-body');
  let html='';
  msgs.forEach((m,i)=>{
    const dt      = new Date(m.timestamp_utc);
    const timeStr = dt.toLocaleString('en-GB',{day:'2-digit',month:'short',year:'numeric',hour:'2-digit',minute:'2-digit'})+' UTC';
    const p       = m.priority||'LOW';
    const kws     = m.keyword_hits||[];
    const iocs    = m.iocs||{};
    const text    = m.text_preview||'';
    const isTarget= i===targetIdx;
    const kwHtml  = kws.length?`<div class="kws">${kws.map(k=>`<span class="kw ${HOT_KWS.has(k.toLowerCase())?'hot':''}">${esc(k)}</span>`).join('')}</div>`:'';
    const iocHtml = Object.keys(iocs).length?`<div class="iocs">${Object.entries(iocs).map(([type,vals])=>`<div class="ioc-row"><span class="ioc-lbl">${esc(type)}</span>${vals.map(v=>`<span class="ioc-val" onclick="copyVal('${esc(v)}')">${esc(v)}</span>`).join('')}</div>`).join('')}</div>`:'';
    html+=`<div class="bubble ${p}${isTarget?' target-msg':''}">
      ${isTarget?'<div class="target-label">▶ SELECTED MESSAGE</div>':''}
      <div class="b-meta"><span class="ptag ${p}">${p}</span><span class="b-time">${timeStr}</span>${m.timestamp_irst?`<span class="b-irst">${esc(m.timestamp_irst)}</span>`:''}</div>
      ${kwHtml}
      <div class="b-text">${esc(text)}</div>
      ${iocHtml}
    </div>`;
  });
  el.innerHTML=html;
  const targetEl=el.querySelector('.target-msg');
  if (targetEl) setTimeout(()=>targetEl.scrollIntoView({block:'center',behavior:'smooth'}),50);
}

// ── Keyboard shortcuts ──────────────────────────────────────────────────────
document.addEventListener('keydown', e => {
  const tag = document.activeElement.tagName.toLowerCase();
  const inInput = tag === 'input' || tag === 'select' || tag === 'textarea';

  // Ctrl+K / Cmd+K → global search (always, even in input)
  if ((e.ctrlKey || e.metaKey) && e.key === 'k') {
    e.preventDefault();
    openGSearch();
    return;
  }

  if (e.key === 'Escape') {
    // Close modals in priority order
    if (document.getElementById('help-overlay').style.display === 'flex')    { closeHelp();    return; }
    if (document.getElementById('gsearch-overlay').style.display === 'flex') { closeGSearch(); return; }
    closeContext();
    return;
  }

  if (!inInput) {
    // Tab switching: 1-4
    if (e.key === '1') { switchMainTab('monitor');   return; }
    if (e.key === '2') { switchMainTab('dashboard'); return; }
    if (e.key === '3') { switchMainTab('ioc');       return; }
    if (e.key === '4') { switchMainTab('timeline');  return; }
    // Help overlay: ?
    if (e.key === '?') { e.preventDefault(); openHelp(); return; }
    // Focus search: /
    if (e.key === '/') {
      e.preventDefault();
      const search = currentMainTab==='dashboard' ? document.getElementById('gf-search')
                   : currentMainTab==='ioc'       ? document.getElementById('ioc-search')
                   : currentMainTab==='timeline'  ? document.getElementById('tl-search')
                   : document.getElementById('f-search');
      if (search) { search.focus(); search.select(); }
      return;
    }
    // Scroll messages: j/k
    if (e.key === 'j') {
      const el = document.getElementById('msgs');
      if (el) el.scrollTop += 120;
    }
    if (e.key === 'k') {
      const el = document.getElementById('msgs');
      if (el) el.scrollTop -= 120;
    }
  }
});

// ── Global Search Modal (Ctrl+K) ──────────────────────────────────────────────
let _gsResults   = [];
let _gsSelected  = -1;
let _gsDebounce  = null;

function openGSearch() {
  const overlay = document.getElementById('gsearch-overlay');
  overlay.style.display = 'flex';
  const inp = document.getElementById('gs-input');
  inp.value = '';
  inp.focus();
  document.getElementById('gs-results').innerHTML = '<div style="padding:24px;text-align:center;color:#484f58;font-size:12px">Type to search across all channels…</div>';
  document.getElementById('gs-count').textContent = '';
  _gsSelected = -1;
}

function closeGSearch() {
  document.getElementById('gsearch-overlay').style.display = 'none';
}

function openHelp() {
  document.getElementById('help-overlay').style.display = 'flex';
}
function closeHelp() {
  document.getElementById('help-overlay').style.display = 'none';
}

function gsKeydown(e) {
  if (e.key === 'ArrowDown') { e.preventDefault(); gsSelect(_gsSelected+1); }
  else if (e.key === 'ArrowUp') { e.preventDefault(); gsSelect(_gsSelected-1); }
  else if (e.key === 'Enter') { gsOpen(); }
  else if (e.key === 'Escape') { closeGSearch(); }
}

function gsSelect(idx) {
  const items = document.querySelectorAll('.gs-item');
  if (!items.length) return;
  _gsSelected = Math.max(0, Math.min(idx, items.length-1));
  items.forEach((el,i) => el.classList.toggle('gs-selected', i===_gsSelected));
  items[_gsSelected].scrollIntoView({block:'nearest'});
}

function gsOpen() {
  if (_gsSelected < 0 || !_gsResults[_gsSelected]) return;
  const m = _gsResults[_gsSelected];
  closeGSearch();
  switchMainTab('monitor');
  // Navigate to the channel
  const chItem = [...document.querySelectorAll('.ch-item')].find(
    el => el.getAttribute('onclick') && el.getAttribute('onclick').includes(m.channel_username));
  if (chItem) { chItem.click(); }
  else {
    selectChannel(m.channel_username, m.channel, document.createElement('div'));
  }
}

function gsSearch() {
  clearTimeout(_gsDebounce);
  _gsDebounce = setTimeout(_gsDoSearch, 180);
}

async function _gsDoSearch() {
  const q        = document.getElementById('gs-input').value.trim();
  const priority = document.getElementById('gs-priority').value;
  if (q.length < 2) {
    document.getElementById('gs-results').innerHTML =
      '<div style="padding:24px;text-align:center;color:#484f58;font-size:12px">Type at least 2 characters…</div>';
    document.getElementById('gs-count').textContent = '';
    return;
  }
  try {
    const r = await fetch(`/api/messages/all?search=${encodeURIComponent(q)}&priority=${priority}&limit=80`);
    const msgs = await r.json();
    _gsResults  = msgs;
    _gsSelected = -1;
    renderGSResults(msgs, q);
  } catch(e) {
    document.getElementById('gs-results').innerHTML =
      '<div style="padding:24px;text-align:center;color:#da3633;font-size:12px">Search error</div>';
  }
}

function renderGSResults(msgs, q) {
  const el = document.getElementById('gs-results');
  document.getElementById('gs-count').textContent = `${msgs.length} result${msgs.length!==1?'s':''}`;
  if (!msgs.length) {
    el.innerHTML = '<div style="padding:24px;text-align:center;color:#484f58;font-size:12px">No results found</div>';
    return;
  }
  const PCOL = {CRITICAL:'#da3633',MEDIUM:'#e3b341',LOW:'#3fb950'};
  el.innerHTML = msgs.map((m,i) => {
    const p   = m.priority || 'LOW';
    const col = PCOL[p] || '#484f58';
    const ts  = m.timestamp_utc ? new Date(m.timestamp_utc).toLocaleString() : '';
    const txt = esc(m.text_preview||'').substring(0,180);
    const kws = (m.keyword_hits||[]).map(k=>`<span style="background:#1a2d4a;color:#58a6ff;font-size:9px;padding:1px 4px;border-radius:3px;margin-right:2px">${esc(k)}</span>`).join('');
    return `<div class="gs-item" data-idx="${i}" onclick="gsSelectAndOpen(${i})"
      style="padding:10px 14px;border-bottom:1px solid #21262d;cursor:pointer;position:relative">
      <div style="display:flex;gap:8px;align-items:center;margin-bottom:4px">
        <span style="font-size:9px;font-weight:700;padding:1px 6px;border-radius:3px;background:${col}22;color:${col};border:1px solid ${col}44">${p}</span>
        <span style="font-size:10px;font-weight:600;color:#388bfd">@${esc(m.channel_username)}</span>
        <span style="font-size:9px;color:#484f58">${ts}</span>
        <div style="flex:1"></div>
        ${kws}
      </div>
      <div style="font-size:11px;color:#8b949e;line-height:1.45">${txt}</div>
    </div>`;
  }).join('');
  // Hover styling
  el.querySelectorAll('.gs-item').forEach(item => {
    item.addEventListener('mouseover', () => gsSelect(parseInt(item.dataset.idx)));
  });
}

function gsSelectAndOpen(idx) {
  _gsSelected = idx;
  gsOpen();
}

// ── Browser tab title with critical count ────────────────────────────────────
let _titleCrit = 0;
function updateTitle(crit) {
  _titleCrit = crit;
  document.title = crit > 0 ? `(${crit} 🔴) Scanwave CyberIntel` : 'Scanwave CyberIntel';
}

// ═══════════════════════════════════════════════════
// DASHBOARD TAB
// ═══════════════════════════════════════════════════
async function loadDashboard() {
  try {
    const r = await fetch('/api/dashboard');
    dashData = await r.json();
    document.getElementById('dc-total').textContent = dashData.total.toLocaleString();
    document.getElementById('dc-crit').textContent  = dashData.critical.toLocaleString();
    document.getElementById('dc-med').textContent   = dashData.medium.toLocaleString();
    document.getElementById('dc-ioc').textContent   = dashData.ioc_count.toLocaleString();
    const configured = dashData.total_configured || dashData.channel_count;
    const banned     = dashData.banned_count || 0;
    document.getElementById('dc-ch').textContent    = configured;
    document.getElementById('dc-ch-sub').textContent = `${dashData.channel_count} active · ${banned} banned`;
    document.getElementById('dc-camp').textContent  = (dashData.campaigns||[]).length;
    document.getElementById('ts-ioc').textContent   = dashData.ioc_count.toLocaleString();
    iocData = dashData.iocs || [];
    renderKeywordHeatmap(dashData.keywords||[]);
    renderActivityHeatmap(dashData.activity_matrix||{});
    renderCampaigns(dashData.campaigns||[]);
    setTimeout(loadTrendChart, 100); // slight delay to ensure canvas is rendered
  } catch(e) {
    console.error('Dashboard load error',e);
  }
  // Load global feed, briefing, and threat matrix in parallel
  await Promise.all([
    gfKeyword ? Promise.resolve() : loadGlobalFeed('','ALL'),
    loadBriefing(),
    loadThreatMatrix(),
  ]);
}

async function loadBriefing() {
  try {
    const r = await fetch('/api/briefing');
    const b = await r.json();
    const s = b.summary;
    const strip = document.getElementById('briefing-strip');
    strip.style.display = 'block';
    document.getElementById('bf-crit').textContent =
      `${s.critical_alerts_24h} critical / ${s.total_messages_24h} msgs in last 24h`;
    const trendEl = document.getElementById('bf-trend');
    trendEl.textContent = s.trend;
    trendEl.style.background = s.trend==='ESCALATING'?'#3d0000':s.trend==='DECREASING'?'#0d2200':'#1a1200';
    trendEl.style.color      = s.trend==='ESCALATING'?'#ff7b7b':s.trend==='DECREASING'?'#3fb950':'#e3b341';
    trendEl.style.border     = `1px solid ${s.trend==='ESCALATING'?'#6e1a1a':s.trend==='DECREASING'?'#1a4a1a':'#4a3800'}`;
    document.getElementById('bf-iocs').textContent = `${s.fresh_ioc_count} new IOCs`;
    document.getElementById('bf-ch').textContent   = `${s.active_channels_24h} active channels`;
    // Top entities
    if (b.top_targeted_entities && b.top_targeted_entities.length) {
      document.getElementById('bf-entities').innerHTML =
        '<span style="font-size:9px;color:#484f58;margin-right:4px">TOP TARGETED:</span>' +
        b.top_targeted_entities.slice(0,10).map(([kw,cnt])=>
          `<span style="font-size:9px;background:#120606;border:1px solid #6e1a1a;color:#ff7b7b;padding:1px 6px;border-radius:3px;cursor:pointer" onclick="filterByKeyword('${esc(kw)}')">${esc(kw)} (${cnt})</span>`
        ).join('');
    }
    // Newest critical alerts
    const nc   = b.newest_critical || [];
    const ncEl = document.getElementById('bf-newest');
    if (nc.length) {
      ncEl.style.display = 'block';
      ncEl.innerHTML =
        '<div style="font-size:9px;color:#484f58;font-weight:600;margin-bottom:4px;text-transform:uppercase;letter-spacing:.5px">&#x1F534; Latest Critical Alerts (24h)</div>' +
        nc.slice(0, 4).map(m => {
          const ts   = m.timestamp_utc ? new Date(m.timestamp_utc).toLocaleString() : '';
          const kws  = (m.keyword_hits || []).slice(0, 4).map(k =>
            `<span style="background:#1a1200;color:#e3b341;font-size:8px;padding:1px 4px;border-radius:2px;margin-right:2px">${esc(k)}</span>`
          ).join('');
          const txt      = esc((m.text_preview || '').substring(0, 160));
          const firstKw  = (m.keyword_hits || [])[0] || '';
          const onclick  = firstKw
            ? `filterByKeyword('${esc(firstKw).replace(/'/g,"\\'")}')` : 'void(0)';
          return `<div style="background:#0d1117;border:1px solid #da363344;border-radius:4px;padding:5px 9px;margin-bottom:3px;cursor:pointer" onclick="${onclick}">
            <div style="display:flex;gap:8px;align-items:center;margin-bottom:2px;flex-wrap:wrap">
              <span style="font-size:9px;font-weight:600;color:#58a6ff">@${esc(m.channel_username||'')}</span>
              <span style="font-size:9px;color:#484f58">${ts}</span>
              <div style="flex:1"></div>
              ${kws}
            </div>
            <div style="font-size:10px;color:#8b949e;line-height:1.35;overflow:hidden;max-height:2.7em">${txt}</div>
          </div>`;
        }).join('');
    } else {
      ncEl.style.display = 'none';
    }
  } catch(e) { console.error('Briefing error',e); }
}

function renderKeywordHeatmap(keywords) {
  const el = document.getElementById('hm-body');
  if (!keywords.length) { el.innerHTML='<div class="loading-msg">No keyword data yet.</div>'; return; }
  const maxW = Math.max(...keywords.map(k=>k.weight),1);
  let html = '<div class="kw-grid">';
  keywords.slice(0,80).forEach(k=>{
    const ratio = k.weight / maxW;
    const sz  = ratio > .8?'sz5':ratio>.6?'sz4':ratio>.4?'sz3':ratio>.2?'sz2':'sz1';
    const critRatio = k.total>0 ? k.critical/k.total : 0;
    const col = critRatio>.6?'c-red':critRatio>.3?'c-amber':k.total>5?'c-blue':'c-gray';
    const tip = `${k.keyword}: ${k.critical} critical / ${k.medium} medium / ${k.total} total`;
    html+=`<span class="kw-chip ${sz} ${col}" title="${esc(tip)}" onclick="filterByKeyword('${esc(k.keyword)}')">${esc(k.keyword)}</span>`;
  });
  html += '</div>';
  el.innerHTML = html;
}

async function loadTrendChart() {
  try {
    const r    = await fetch('/api/trend?days=30');
    const data = await r.json();
    const canvas = document.getElementById('trend-canvas');
    if (!canvas) return;
    const W = canvas.offsetWidth || 380;
    canvas.width  = W;
    const H = 60;
    canvas.height = H;
    const ctx = canvas.getContext('2d');
    const n   = data.length;
    const maxV = Math.max(1, ...data.map(d => d.CRITICAL + d.MEDIUM));
    const bw  = W / n;
    ctx.clearRect(0, 0, W, H);
    // Background gridlines
    ctx.strokeStyle = '#21262d';
    ctx.lineWidth = 0.5;
    [0.25,0.5,0.75,1].forEach(f => {
      const y = H - f * H;
      ctx.beginPath(); ctx.moveTo(0, y); ctx.lineTo(W, y); ctx.stroke();
    });
    // Medium bars (bottom layer)
    data.forEach((d, i) => {
      const medH = (d.MEDIUM / maxV) * (H - 2);
      ctx.fillStyle = '#9a6e0066';
      ctx.fillRect(i * bw + 1, H - medH, bw - 2, medH);
    });
    // Critical bars (top)
    data.forEach((d, i) => {
      const critH = (d.CRITICAL / maxV) * (H - 2);
      ctx.fillStyle = d.CRITICAL > 0 ? '#da3633' : '#21262d44';
      ctx.fillRect(i * bw + 1, H - critH, bw - 2, critH);
    });
    // Date labels every 7 days
    ctx.fillStyle = '#484f58';
    ctx.font = '8px monospace';
    data.forEach((d, i) => {
      if (i % 7 === 0) ctx.fillText(d.date.slice(5), i * bw + 2, H - 1);
    });
  } catch(e) {}
}

function renderActivityHeatmap(matrix) {
  const el = document.getElementById('act-grid');
  const maxVal = Math.max(1, ...WEEKDAYS.flatMap(wd=>(matrix[wd]||Array(24).fill(0))));
  let html = '';
  // Hour labels row
  html += '<div></div>'; // empty corner
  for (let h=0;h<24;h++) {
    html += `<div class="act-hour-label">${h}</div>`;
  }
  WEEKDAYS.forEach(wd=>{
    const hours = matrix[wd] || Array(24).fill(0);
    html += `<div class="act-label">${wd}</div>`;
    hours.forEach((cnt,h)=>{
      const intensity = cnt/maxVal;
      const r = Math.round(218*intensity); const g = Math.round(54*intensity); const b = Math.round(51*intensity);
      const bg = cnt>0 ? `rgb(${r},${g},${b})` : '#0d1117';
      const isWork = h>=8 && h<=20;
      html+=`<div class="act-cell${isWork?' work-hour':''}" style="background:${bg}" data-tip="${wd} ${h}:00 IRST — ${cnt} msgs"></div>`;
    });
  });
  el.innerHTML = html;
}

function renderCampaigns(campaigns) {
  const sec  = document.getElementById('camp-section');
  const scrl = document.getElementById('camp-scroll');
  const badge= document.getElementById('camp-badge');
  if (!campaigns.length) {
    sec.style.display='none';
    badge.style.display='none';
    return;
  }
  sec.style.display='block';
  badge.style.display='inline';
  badge.textContent = campaigns.length;
  scrl.innerHTML = campaigns.map(c=>`
    <div class="camp-card" onclick="filterByKeyword('${esc(c.keyword)}')">
      <div class="camp-kw">${esc(c.keyword)}</div>
      <div class="camp-meta">${c.count} channels · ${c.date}</div>
      <div class="camp-chs">${c.channels.map(ch=>'@'+ch).join(' · ')}</div>
    </div>`).join('');
}

// ── Threat Actor Matrix ──────────────────────────────────────────────────────
async function loadThreatMatrix() {
  try {
    const r = await fetch('/api/threat_matrix');
    const d = await r.json();
    renderThreatMatrix(d);
  } catch(e) { console.error('Matrix error', e); }
}

function renderThreatMatrix(data) {
  const sec    = document.getElementById('matrix-section');
  const cats   = data.categories || [];
  const actors = data.actors || [];
  if (!actors.length) { sec.style.display = 'none'; return; }
  sec.style.display = 'block';
  const badge = document.getElementById('matrix-badge');
  if (badge) badge.textContent = `${actors.length} actors`;

  const TIER_COL = {1:'#da3633', 2:'#e3b341', 3:'#3fb950', 0:'#484f58'};
  const maxCell  = Math.max(1, ...actors.flatMap(a => cats.map(c => a[c] || 0)));

  let html = `<table style="border-collapse:collapse;font-size:10px;min-width:100%">
    <thead><tr style="background:#0a0f17;position:sticky;top:0;z-index:1">
      <th style="padding:4px 10px;text-align:left;font-size:9px;color:#484f58;font-weight:600;border-bottom:1px solid #21262d;white-space:nowrap">Threat Actor</th>
      <th style="padding:4px 6px;font-size:9px;color:#484f58;font-weight:600;border-bottom:1px solid #21262d;text-align:center">Tier</th>
      ${cats.map(c=>`<th style="padding:4px 8px;font-size:9px;color:#484f58;font-weight:600;text-align:center;border-bottom:1px solid #21262d;white-space:nowrap">${esc(c)}</th>`).join('')}
      <th style="padding:4px 8px;font-size:9px;color:#484f58;font-weight:600;text-align:right;border-bottom:1px solid #21262d">Total</th>
    </tr></thead><tbody>`;
  actors.forEach((a,idx) => {
    const tc  = TIER_COL[a.tier] || '#484f58';
    const rowBg = idx % 2 === 0 ? '#0d1117' : '#070b11';
    html += `<tr style="background:${rowBg}">
      <td style="padding:3px 10px;color:#e6edf3;white-space:nowrap;max-width:200px;overflow:hidden;text-overflow:ellipsis" title="${esc(a.channel)}">${esc(a.label||a.channel)}</td>
      <td style="padding:3px 6px;text-align:center"><span style="font-size:8px;padding:1px 5px;border-radius:3px;background:${tc}22;color:${tc};border:1px solid ${tc}44;font-weight:700">T${a.tier||'?'}</span></td>
      ${cats.map(c => {
        const v   = a[c] || 0;
        const int = v / maxCell;
        const bg  = v > 0 ? `rgba(218,54,51,${(int * 0.75 + 0.1).toFixed(2)})` : 'transparent';
        const col = v > 0 ? '#fff' : '#30363d';
        return `<td style="padding:3px 8px;text-align:center;background:${bg};color:${col};font-weight:${v>0?'600':'400'}" title="${esc(c)}: ${v}">${v||'·'}</td>`;
      }).join('')}
      <td style="padding:3px 8px;text-align:right;color:#e3b341;font-weight:700">${a.total}</td>
    </tr>`;
  });
  html += '</tbody></table>';
  document.getElementById('matrix-table').innerHTML = html;
}

async function loadGlobalFeed(keyword, priority) {
  const p = priority || document.getElementById('gf-priority').value || 'ALL';
  const s = document.getElementById('gf-search').value || '';
  let url = `/api/messages/all?limit=500&priority=${p}`;
  if (keyword) url += `&keyword=${encodeURIComponent(keyword)}`;
  if (s)       url += `&search=${encodeURIComponent(s)}`;
  const sub = critSubState.feed;
  if (sub !== 'ALL') url += `&critical_subtype=${sub}`;
  try {
    const r = await fetch(url);
    gfMsgs  = await r.json();
    document.getElementById('gf-count').textContent = `${gfMsgs.length} msgs`;
    renderMessages(gfMsgs, 'gf-msgs');
  } catch(e) {}
}

function filterByKeyword(kw) {
  gfKeyword = kw;
  document.getElementById('gf-search').value = kw;
  switchMainTab('dashboard');
  loadGlobalFeed(kw, 'ALL');
}

function gfSearch() {
  const s = document.getElementById('gf-search').value;
  const p = document.getElementById('gf-priority').value;
  gfKeyword = s;
  loadGlobalFeed(s, p);
}

async function translateMsg(btn, text) {
  const bubble = btn.closest('.bubble');
  const container = bubble ? bubble.querySelector('.translate-result') : null;
  if (!container) return;
  btn.disabled = true;
  btn.textContent = '⏳';
  try {
    const r = await fetch('/api/translate', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({text}),
    });
    const d = await r.json();
    if (d.translation) {
      container.style.display = 'block';
      container.textContent = '🌐 ' + d.translation;
      btn.textContent = '✓';
    } else {
      btn.textContent = '⚠';
      btn.title = d.error || 'Translation failed';
    }
  } catch(e) {
    btn.textContent = '⚠';
    btn.title = e.message;
  }
}

function clearGFFilter() {
  gfKeyword = '';
  document.getElementById('gf-search').value = '';
  document.getElementById('gf-priority').value = 'ALL';
  loadGlobalFeed('','ALL');
}

// ═══════════════════════════════════════════════════
// IOC INTEL TAB
// ═══════════════════════════════════════════════════
async function loadIOCData() {
  if (iocData.length) { renderIOCTable(); return; }
  try {
    const r = await fetch('/api/dashboard');
    const d = await r.json();
    iocData = d.iocs || [];
    document.getElementById('ts-ioc').textContent = d.ioc_count.toLocaleString();
    renderIOCTable();
  } catch(e){}
}

function iocFilterType(type) {
  iocTypeFilter = type;
  document.querySelectorAll('.ioc-type-filter button').forEach(b=>{
    b.classList.toggle('sel', b.dataset.type===type);
  });
  renderIOCTable();
}

function iocSort(key) {
  if (iocSortKey===key) { iocSortAsc=!iocSortAsc; }
  else { iocSortKey=key; iocSortAsc=key!=='count'&&key!=='last_seen'; }
  document.querySelectorAll('[id^=sort-]').forEach(e=>e.textContent='');
  const arrow = document.getElementById('sort-'+key);
  if (arrow) arrow.textContent = iocSortAsc?'▲':'▼';
  renderIOCTable();
}

function matchesTypeFilter(type, filter) {
  if (filter === 'ALL') return true;
  if (filter === 'ip')   return type === 'ipv4' || type === 'ipv6' || type.includes('ip');
  if (filter === 'hash') return type.startsWith('hash');
  if (filter === 'cve')  return type === 'cve';
  return type === filter;
}

function renderIOCTable() {
  const search = (document.getElementById('ioc-search').value||'').toLowerCase();
  let rows = iocData.filter(r=>{
    if (!matchesTypeFilter(r.type, iocTypeFilter)) return false;
    if (search && !r.value.toLowerCase().includes(search) &&
        !r.channels.join(' ').toLowerCase().includes(search)) return false;
    return true;
  });
  rows.sort((a,b)=>{
    let av=a[iocSortKey]||'', bv=b[iocSortKey]||'';
    if (typeof av==='number') return iocSortAsc?av-bv:bv-av;
    return iocSortAsc?String(av).localeCompare(String(bv)):String(bv).localeCompare(String(av));
  });
  document.getElementById('ioc-count').textContent = `${rows.length} IOCs`;
  const tbody = document.getElementById('ioc-tbody');
  if (!rows.length) {
    tbody.innerHTML='<tr><td colspan="6" class="ioc-table-empty">No IOCs match filters</td></tr>';
    return;
  }
  tbody.innerHTML = rows.slice(0,1000).map(r=>{
    const chs = (r.channels||[]).map(c=>`<span class="ioc-ch-tag">@${esc(c)}</span>`).join('');
    const dt  = r.last_seen ? new Date(r.last_seen).toLocaleDateString('en-GB',{day:'2-digit',month:'short',year:'numeric'}) : '—';
    return `<tr>
      <td><span class="ioc-type-badge ${r.type}">${esc(r.type)}</span></td>
      <td class="ioc-val-cell">${esc(r.value)}</td>
      <td class="ioc-count-cell">${r.count}</td>
      <td class="ioc-channels-cell">${chs}</td>
      <td class="ioc-last-cell">${dt}</td>
      <td><button class="ioc-copy" onclick="copyVal('${esc(r.value)}')">📋</button></td>
    </tr>`;
  }).join('');
}

// ═══════════════════════════════════════════════════
// TIMELINE TAB
// ═══════════════════════════════════════════════════
let tlMsgCache = [];  // cache of all currently displayed timeline messages (for incremental diff)

function buildTLItemHtml(m) {
  const dt      = new Date(m.timestamp_utc);
  const timeStr = dt.toLocaleTimeString('en-GB',{hour:'2-digit',minute:'2-digit'});
  const p       = m.priority||'LOW';
  const ch      = m.channel_username||m.channel||'';
  const kws     = m.keyword_hits||[];
  const iocs    = m.iocs||{};
  const text    = m.text_preview||'';
  const msgId   = m.message_id||0;
  const lang    = m.language;
  const critSub = m.critical_subtype;

  const kwHtml  = kws.map(k=>`<span class="tl-kw ${HOT_KWS.has(k.toLowerCase())?'hot':''}">${esc(k)}</span>`).join('');
  const iocHtml = Object.keys(iocs).length?`<div class="tl-iocs">${
    Object.entries(iocs).flatMap(([t,vs])=>vs.map(v=>`<span class="ioc-val" onclick="copyVal('${esc(v)}')">${esc(v)}</span>`)).join(' ')
  }</div>`:'';
  const isLong  = text.length > 300;
  const id      = `tlmsg-${msgId}-${ch}`;

  // Subtype badge
  const subBC = {CYBER:'#3fb950',NATIONAL:'#58a6ff',BOTH:'#d29922',GENERAL:'#da3633'};
  const subBadge = (p==='CRITICAL' && critSub)
    ? `<span style="font-size:8px;padding:1px 4px;border-radius:8px;background:${subBC[critSub]||'#da3633'}22;color:${subBC[critSub]||'#da3633'};border:1px solid ${subBC[critSub]||'#da3633'}44">${critSub==='BOTH'?'💻🛡':critSub==='CYBER'?'💻':critSub==='NATIONAL'?'🛡':'!'}</span>`
    : '';
  // Language badge + translate button
  const langBadge = (lang && lang!=='ar' && lang!=='en')
    ? `<span style="font-size:8px;padding:1px 3px;background:#1a1a2e;color:#818cf8;border-radius:2px">${esc(lang.toUpperCase())}</span>`
    : '';
  const showTranslate = lang && lang !== 'en';
  const translateBtn = showTranslate
    ? `<button onclick="event.stopPropagation();translateMsg(this,${JSON.stringify(text)})" style="font-size:8px;padding:1px 5px;background:#161b22;border:1px solid #30363d;color:#818cf8;border-radius:3px;cursor:pointer">🌐</button>`
    : '';
  // AI enrichment card
  const ai = m.ai_enrichment||null;
  const aiHtml = ai ? (()=>{
    const atk=ai.attack_type||'', grp=ai.group_attribution||'', sec=ai.target_sector||'';
    const act=ai.recommended_action||'', conf=ai.confidence||0, sev=ai.severity||'';
    const sevCol={CRITICAL:'#da3633',HIGH:'#e3b341',MEDIUM:'#3fb950',LOW:'#484f58'}[sev]||'#58a6ff';
    return `<div class="ai-card" onclick="event.stopPropagation()" style="margin-top:4px">
      <div style="display:flex;gap:5px;align-items:center;flex-wrap:wrap;margin-bottom:2px">
        <span style="font-size:8px;padding:1px 4px;background:#58a6ff22;color:#58a6ff;border-radius:3px;font-weight:700">🤖 AI</span>
        ${grp?`<span style="font-size:9px;color:#e6edf3;font-weight:600">${esc(grp)}</span>`:''}
        ${atk?`<span style="font-size:8px;color:#8b949e">${esc(atk)}</span>`:''}
        ${sec?`<span style="font-size:8px;padding:1px 3px;background:#21262d;color:#8b949e;border-radius:2px">${esc(sec)}</span>`:''}
        <span style="font-size:8px;color:${sevCol}">${esc(sev)}</span>
        <span style="font-size:8px;color:#484f58">conf:${conf}%</span>
      </div>
      ${act&&act!=='None'?`<div style="font-size:8px;color:#e3b341">→ ${esc(act)}</div>`:''}
      ${ai.summary?`<div style="font-size:9px;color:#8b949e;margin-top:1px;font-style:italic">${esc(ai.summary)}</div>`:''}
    </div>`;
  })() : '';

  return `<div class="tl-item">
    <div class="tl-time-col">
      <div class="tl-time">${timeStr} UTC</div>
      ${m.timestamp_irst?`<div class="tl-irst">${esc(m.timestamp_irst.slice(11,16))} IRST</div>`:''}
    </div>
    <div class="tl-line ${p==='CRITICAL'?'crit':p==='MEDIUM'?'med':''}"></div>
    <div class="tl-body" onclick="openContext(${msgId},'${esc(ch)}')">
      <div class="tl-bheader">
        <span class="tl-ptag ${p}">${p}</span>
        ${subBadge}
        <span class="tl-channel">@${esc(ch)}</span>
        ${langBadge}${translateBtn}
      </div>
      ${kwHtml?`<div class="tl-kws">${kwHtml}</div>`:''}
      <div class="tl-btext" id="${id}">${esc(text)}</div>
      <div class="translate-result" style="display:none;margin-top:4px;padding:4px 7px;background:#0d1117;border-left:2px solid #818cf8;font-size:10px;color:#c9d1d9;font-style:italic"></div>
      ${isLong?`<button class="tl-expand" onclick="event.stopPropagation();tlExpand('${id}')">Show more ↓</button>`:''}
      ${iocHtml}
      ${aiHtml}
    </div>
  </div>`;
}

async function loadTimeline(silent = false) {
  const priority = document.getElementById('tl-priority').value;
  const since    = document.getElementById('tl-since').value;
  const until    = document.getElementById('tl-until').value;
  const channel  = document.getElementById('tl-channel').value.replace('@','');
  const search   = document.getElementById('tl-search').value;

  if (!silent) {
    document.getElementById('tl-feed').innerHTML='<div class="loading-msg">Loading timeline…</div>';
    tlMsgCache = [];
  }

  let url = `/api/messages/all?limit=2000`;
  if (priority !== 'ALL') url += `&priority=${priority}`;
  if (since)   url += `&since=${since}`;
  if (until)   url += `&until=${until}`;
  if (channel) url += `&channel=${encodeURIComponent(channel)}`;
  if (search)  url += `&search=${encodeURIComponent(search)}`;
  if (critSubState.timeline !== 'ALL') url += `&critical_subtype=${critSubState.timeline}`;

  try {
    const r    = await fetch(url);
    const msgs = await r.json();
    if (silent && tlMsgCache.length) {
      // Incremental: only add messages not already in the cache
      const existingIds = new Set(tlMsgCache.map(m=>`${m.channel_username}:${m.message_id}`));
      const newMsgs = msgs.filter(m=>!existingIds.has(`${m.channel_username}:${m.message_id}`));
      if (newMsgs.length) {
        tlMsgCache = msgs;
        document.getElementById('tl-count').textContent = `${msgs.length} messages`;
        prependTimelineItems(newMsgs);
      }
      // If nothing new → do nothing, no visual change
    } else {
      tlMsgCache = msgs;
      document.getElementById('tl-count').textContent = `${msgs.length} messages`;
      renderTimeline(msgs);
    }
  } catch(e) {
    if (!silent) document.getElementById('tl-feed').innerHTML='<div class="loading-msg">Error loading timeline.</div>';
  }
}

function prependTimelineItems(newMsgs) {
  const el = document.getElementById('tl-feed');
  const empty = el.querySelector('.empty');
  if (empty) el.innerHTML = '';
  // Sort newest-first (same order as renderTimeline)
  const sorted = [...newMsgs].sort((a,b)=>(a.timestamp_utc||'')>(b.timestamp_utc||'')?-1:1);
  let html = `<div class="tl-day" style="color:#3fb950;border-color:#3fb950">↑ ${sorted.length} new message${sorted.length>1?'s':''}</div>`;
  sorted.forEach(m=>{ html += buildTLItemHtml(m); });
  el.insertAdjacentHTML('afterbegin', html);
}

function renderTimeline(msgs) {
  const el = document.getElementById('tl-feed');
  if (!msgs.length) {
    el.innerHTML='<div class="empty"><div class="ico">📅</div><p>No messages match filters</p></div>';
    return;
  }
  let html='', lastDay='';
  msgs.forEach(m=>{
    const dt     = new Date(m.timestamp_utc);
    const dayStr = dt.toLocaleDateString('en-GB',{day:'2-digit',month:'short',year:'numeric'});
    if (dayStr!==lastDay) {
      html+=`<div class="tl-day">${dayStr}</div>`;
      lastDay=dayStr;
    }
    html += buildTLItemHtml(m);
  });
  el.innerHTML=html;
}

function tlExpand(id) {
  const el=document.getElementById(id);
  if (el) { el.classList.toggle('expanded'); el.nextElementSibling.textContent=el.classList.contains('expanded')?'Show less ↑':'Show more ↓'; }
}

function resetTLFilters() {
  document.getElementById('tl-priority').value='CRITICAL';
  document.getElementById('tl-since').value='';
  document.getElementById('tl-until').value='';
  document.getElementById('tl-channel').value='';
  document.getElementById('tl-search').value='';
  loadTimeline();
}

// Bootstrap timeline with defaults
loadTimeline();

// ═══════════════════════════════════════════════════
// ADMIN PANEL
// ═══════════════════════════════════════════════════
const TIER_COL_A = {1:'#da3633',2:'#e3b341',3:'#3fb950',0:'#484f58'};
const THREAT_COL = {CRITICAL:'#da3633',HIGH:'#e3b341',MEDIUM:'#3fb950',LOW:'#484f58'};

async function loadAdminPanelStatus() {
  try {
    const r = await fetch('/api/admin/status');
    const d = await r.json();
    // Status cards
    const mon = document.getElementById('adm-monitor-status');
    mon.textContent = d.monitor_running ? 'RUNNING' : 'STOPPED';
    mon.style.color = d.monitor_running ? '#3fb950' : '#da3633';
    document.getElementById('adm-total').textContent = (d.db.total||0).toLocaleString();
    document.getElementById('adm-crit').textContent  = (d.db.critical||0).toLocaleString();
    document.getElementById('adm-iocs').textContent  = (d.db.iocs||0).toLocaleString();
    document.getElementById('adm-last').textContent  = d.db.last_message ? new Date(d.db.last_message).toLocaleString() : '—';
    const cursor = d.cursor||{};
    document.getElementById('adm-cursor').textContent = cursor.last_run_stopped
      ? new Date(cursor.last_run_stopped).toLocaleString() : 'none';
    // Log tail
    document.getElementById('adm-log').textContent = (d.log_tail||[]).join('\n');
    // Backfill queue
    renderBFQueue(d.backfill_queue||{});
  } catch(e) { console.error('Admin status error', e); }
  // Load channels and keywords in parallel
  await Promise.all([loadAdminChannels(), loadAdminKeywords()]);
}

function renderBFQueue(bfq) {
  const el = document.getElementById('adm-bfq');
  const pending   = bfq.pending   || [];
  const completed = (bfq.completed || []).slice(-5);
  if (!pending.length && !completed.length) { el.textContent = 'Queue empty'; return; }
  let html = '';
  if (pending.length) {
    html += `<div style="color:#e3b341;margin-bottom:4px">Pending (${pending.length}):</div>`;
    html += pending.map(r => `<div style="padding:2px 0;color:#8b949e">@${esc(r.channel)} — ${r.limit} msgs</div>`).join('');
  }
  if (completed.length) {
    html += `<div style="color:#3fb950;margin-top:6px;margin-bottom:4px">Recent completed:</div>`;
    html += completed.map(r => `<div style="padding:2px 0;color:#484f58">@${esc(r.channel)} — ${esc(r.status)}</div>`).join('');
  }
  el.innerHTML = html;
}

async function loadAdminChannels() {
  try {
    const r = await fetch('/api/admin/channels');
    const cfg = await r.json();
    const entries = Object.entries(cfg);
    document.getElementById('adm-ch-count').textContent = `${entries.length} channels`;
    const tbody = document.getElementById('adm-ch-tbody');
    tbody.innerHTML = entries.sort((a,b) => (a[1].tier||9) - (b[1].tier||9)).map(([un, meta]) => {
      const tc = TIER_COL_A[meta.tier]||'#484f58';
      const ht = THREAT_COL[meta.threat]||'#484f58';
      const isBanned = meta.status === 'banned';
      return `<tr style="border-bottom:1px solid #21262d11;${isBanned?'opacity:.5':''}">
        <td style="padding:4px 10px;color:#58a6ff;font-family:monospace">@${esc(un)}</td>
        <td style="padding:4px 10px;color:#e6edf3">${esc(meta.label||un)}</td>
        <td style="padding:4px 8px;text-align:center"><span style="font-size:8px;padding:1px 5px;border-radius:3px;background:${tc}22;color:${tc};border:1px solid ${tc}44">T${meta.tier||'?'}</span></td>
        <td style="padding:4px 8px;text-align:center"><span style="font-size:8px;padding:1px 5px;border-radius:3px;background:${ht}22;color:${ht}">${esc(meta.threat||'')}</span></td>
        <td style="padding:4px 8px;text-align:center"><span style="font-size:8px;color:${isBanned?'#da3633':'#3fb950'}">${isBanned?'BANNED':'active'}</span></td>
        <td style="padding:4px 8px;text-align:center;display:flex;gap:4px;justify-content:center">
          <button onclick="admFillChannel('${esc(un)}')" style="font-size:9px;padding:2px 7px;background:#1a2d1a;border:1px solid #3fb95044;color:#3fb950;border-radius:3px;cursor:pointer">Backfill</button>
          <button onclick="admDeleteChannel('${esc(un)}')" style="font-size:9px;padding:2px 7px;background:#1a0d0d;border:1px solid #da363344;color:#da3633;border-radius:3px;cursor:pointer">Remove</button>
        </td>
      </tr>`;
    }).join('');
  } catch(e) {}
}

async function loadAdminKeywords() {
  try {
    const r = await fetch('/api/admin/keywords');
    const d = await r.json();
    document.getElementById('adm-kw-crit').value = (d.critical||[]).join('\n');
    document.getElementById('adm-kw-med').value  = (d.medium||[]).join('\n');
    admKwCount();
  } catch(e) {}
}

function admKwCount() {
  const cc = document.getElementById('adm-kw-crit').value.split('\n').filter(l=>l.trim()).length;
  const mc = document.getElementById('adm-kw-med').value.split('\n').filter(l=>l.trim()).length;
  document.getElementById('adm-kw-crit-count').textContent = `(${cc})`;
  document.getElementById('adm-kw-med-count').textContent  = `(${mc})`;
}

async function admSaveKeywords() {
  const crit = document.getElementById('adm-kw-crit').value.split('\n').map(l=>l.trim()).filter(Boolean);
  const med  = document.getElementById('adm-kw-med').value.split('\n').map(l=>l.trim()).filter(Boolean);
  const r = await fetch('/api/admin/keywords', {method:'POST',headers:{'Content-Type':'application/json'},
    body: JSON.stringify({critical: crit, medium: med})});
  const d = await r.json();
  const el = document.getElementById('adm-kw-status');
  el.textContent = d.ok ? `Saved: ${d.critical} critical, ${d.medium} medium. ${d.note}` : 'Error saving';
  el.style.color = d.ok ? '#3fb950' : '#da3633';
}

async function admAddChannel() {
  const username = document.getElementById('adm-ch-user').value.trim().replace(/^@/,'');
  const label    = document.getElementById('adm-ch-label').value.trim() || username;
  const tier     = parseInt(document.getElementById('adm-ch-tier').value);
  const threat   = document.getElementById('adm-ch-threat').value;
  const status   = document.getElementById('adm-ch-status').value;
  if (!username) { alert('Username required'); return; }
  const r = await fetch('/api/admin/channels', {method:'POST',headers:{'Content-Type':'application/json'},
    body: JSON.stringify({username, label, tier, threat, status})});
  const d = await r.json();
  if (d.ok) {
    showToast(`Added @${username} — queued for join`, false);
    document.getElementById('adm-ch-user').value = '';
    document.getElementById('adm-ch-label').value = '';
    document.getElementById('adm-bf-channel').value = username;
    loadAdminChannels();
  } else {
    showToast(`Error: ${d.error}`, true);
  }
}

async function admDeleteChannel(username) {
  if (!confirm(`Remove @${username} from monitoring config?`)) return;
  await fetch(`/api/admin/channels/${encodeURIComponent(username)}`, {method:'DELETE'});
  loadAdminChannels();
}

function admFillChannel(username) {
  document.getElementById('adm-bf-channel').value = username;
  document.getElementById('adm-bf-limit').value   = '500';
  document.getElementById('adm-bf-since').value   = '';
  document.getElementById('adm-bf-channel').scrollIntoView({behavior:'smooth'});
}

async function admQueueBackfill() {
  const channel = document.getElementById('adm-bf-channel').value.trim().replace(/^@/,'');
  const limit   = parseInt(document.getElementById('adm-bf-limit').value) || 500;
  const since   = document.getElementById('adm-bf-since').value.trim();
  if (!channel) { showToast('Enter a channel username', true); return; }
  const body = {channel, limit};
  if (since) body.since = since + 'T00:00:00+00:00';
  const r = await fetch('/api/admin/backfill', {method:'POST',headers:{'Content-Type':'application/json'},
    body: JSON.stringify(body)});
  const d = await r.json();
  const el = document.getElementById('adm-bf-status');
  el.textContent = d.ok ? `Queued @${channel} (${limit} msgs) — monitor picks up within 60s` : `Error: ${d.error}`;
  el.style.color = d.ok ? '#3fb950' : '#da3633';
  if (d.ok) setTimeout(loadAdminPanel, 3000);
}

async function admCompact() {
  const el = document.getElementById('adm-compact-status');
  el.textContent = 'Compacting…'; el.style.color = '#e3b341';
  const r = await fetch('/api/admin/compact', {method:'POST'});
  const d = await r.json();
  el.textContent = d.ok ? `Done: ${d.unique} unique msgs (${d.critical} critical)` : `Error: ${d.error}`;
  el.style.color = d.ok ? '#3fb950' : '#da3633';
  if (d.ok) setTimeout(loadAdminPanel, 500);
}

// ═══════════════════════════════════════════════════
// DISCOVERY ENGINE UI
// ═══════════════════════════════════════════════════

async function loadDiscoveredChannels() {
  const el = document.getElementById('disc-engine-list');
  const cnt = document.getElementById('disc-count');
  const filterVal = document.getElementById('disc-filter').value;
  try {
    const r = await fetch('/api/admin/discovered');
    const data = await r.json();
    const entries = Object.values(data);
    const filtered = filterVal === 'all' ? entries :
                     entries.filter(e => (e.status||'pending_review') === filterVal);
    // Sort: score descending
    filtered.sort((a,b) => (b.score||0) - (a.score||0));
    cnt.textContent = `${filtered.length} / ${entries.length} total`;
    if (!filtered.length) {
      el.innerHTML = '<div style="color:#484f58;font-size:10px;text-align:center;padding:20px">No entries in this category.</div>';
      return;
    }
    el.innerHTML = filtered.map(ch => {
      const score = ch.score || 0;
      const scoreColor = score >= 60 ? '#da3633' : score >= 30 ? '#e3b341' : '#484f58';
      const status = ch.status || 'pending_review';
      const statusColor = status === 'approved' ? '#3fb950' :
                          status === 'dismissed' ? '#484f58' : '#e3b341';
      const autoTag = ch.auto_added ?
        '<span style="font-size:8px;padding:1px 5px;background:#da363322;color:#da3633;border-radius:3px;margin-left:4px">AUTO</span>' : '';
      const ts = ch.discovered_at ? new Date(ch.discovered_at).toLocaleString() : '';
      const isPending = status === 'pending_review';
      return `<div style="display:flex;align-items:center;gap:8px;padding:6px 8px;border-bottom:1px solid #21262d11;${status==='dismissed'?'opacity:.4':''}">
        <div style="font-size:18px;font-weight:700;color:${scoreColor};min-width:30px;text-align:center">${score}</div>
        <div style="flex:1;min-width:0">
          <div style="color:#58a6ff;font-family:monospace;font-size:11px">@${esc(ch.username||'')}${autoTag}</div>
          <div style="color:#484f58;font-size:9px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis">
            ${esc(ch.reason||'')} · ${ts}
          </div>
        </div>
        <span style="font-size:8px;padding:1px 6px;border-radius:3px;border:1px solid ${statusColor}44;color:${statusColor}">${status.replace('_',' ')}</span>
        ${isPending ? `
        <button onclick="discApprove('${esc(ch.username||'')}')" style="font-size:9px;padding:2px 7px;background:#1a2d1a;border:1px solid #3fb95044;color:#3fb950;border-radius:3px;cursor:pointer">✓ Add</button>
        <button onclick="discDismiss('${esc(ch.username||'')}')" style="font-size:9px;padding:2px 7px;background:#1a0d0d;border:1px solid #da363344;color:#da3633;border-radius:3px;cursor:pointer">✕</button>
        ` : ''}
      </div>`;
    }).join('');
  } catch(e) {
    el.innerHTML = '<div style="color:#da3633;font-size:10px;padding:10px">Error loading discovery data.</div>';
  }
}

async function discApprove(username) {
  const r = await fetch(`/api/admin/discovered/approve/${encodeURIComponent(username)}`,
    {method:'POST', headers:{'Content-Type':'application/json'},
     body: JSON.stringify({tier:3, threat:'MEDIUM', label:username})});
  const d = await r.json();
  if (d.ok) {
    showToast(`@${username} approved — queued for monitoring`, false);
    loadDiscoveredChannels();
    loadAdminChannels();
  } else {
    showToast(`Error: ${d.error}`, true);
  }
}

async function discDismiss(username) {
  await fetch(`/api/admin/discovered/dismiss/${encodeURIComponent(username)}`,
    {method:'POST', headers:{'Content-Type':'application/json'}, body:'{}'});
  loadDiscoveredChannels();
}

// ═══════════════════════════════════════════════════
// SYSTEM HEALTH
// ═══════════════════════════════════════════════════

async function refreshSystemHealth() {
  try {
    const r = await fetch('/api/system/status');
    const d = await r.json();
    const procs = d.processes || {};
    const colors = {true: {bg:'#1a2d1a', color:'#3fb950', text:'● UP'},
                    false:{bg:'#1a0d0d', color:'#da3633', text:'○ DOWN'}};
    function setProc(id, up, label) {
      const el = document.getElementById(id);
      if (!el) return;
      const c = colors[up];
      el.textContent = `${label} ${c.text}`;
      el.style.background = c.bg;
      el.style.color = c.color;
    }
    setProc('sys-proc-viewer',  procs.viewer,       'Viewer');
    setProc('sys-proc-monitor', procs.monitor,      'Monitor');
    setProc('sys-proc-ai',      procs.ai_agent,     'AI Agent');
    setProc('sys-proc-orch',    procs.orchestrator,  'Orchestrator');

    // Show API key input if missing
    const keyRow = document.getElementById('sys-apikey-row');
    if (keyRow) keyRow.style.display = d.has_openai_key ? 'none' : 'block';
  } catch(e) {}
}

async function saveApiKey() {
  const key = document.getElementById('sys-apikey-input').value.trim();
  if (!key || !key.startsWith('sk-')) {
    showToast('Enter a valid OpenAI key (starts with sk-)', true);
    return;
  }
  const r = await fetch('/api/system/config', {
    method:'POST', headers:{'Content-Type':'application/json'},
    body: JSON.stringify({OPENAI_API_KEY: key})
  });
  const d = await r.json();
  if (d.ok) {
    document.getElementById('sys-apikey-input').value = '';
    showToast('API key saved — starting AI agent…', false);
    document.getElementById('sys-apikey-row').style.display = 'none';
    await aiStart();
    setTimeout(refreshSystemHealth, 3000);
  }
}

// Load discovery data whenever admin panel opens
async function loadAdminPanel() {
  await loadAdminPanelStatus();
  await Promise.all([loadDiscoveredChannels(), loadAIStatus(), refreshSystemHealth()]);
  startAILogRefresh();
  // Load new intelligence panels
  checkEscalation();
  loadHuntLeads();
  loadNetworkGraph();
}

// ═══════════════════════════════════════════════════
// AI AGENT UI
// ═══════════════════════════════════════════════════

let _aiStatusInterval = null;
let _aiLogInterval   = null;
const BRIEF_COLORS = {CRITICAL:'#da3633',HIGH:'#e3b341',MEDIUM:'#3fb950',LOW:'#484f58'};

// ─── AI LOG ─────────────────────────────────────────
async function loadAILog() {
  const box    = document.getElementById('ai-log-box');
  const filter = (document.getElementById('ai-log-filter')?.value || 'ALL');
  const auto   = document.getElementById('ai-log-autoscroll')?.checked;
  try {
    const r = await fetch('/api/ai/log?lines=200');
    const d = await r.json();
    if (d.error) { box.textContent = 'Error: ' + d.error; return; }
    let lines = d.lines || [];
    // Filter
    if (filter !== 'ALL') {
      const kw = filter === 'ERROR'   ? ['ERROR','Traceback','failed','exception'] :
                 filter === 'ENRICH'  ? ['ENRICH','enrich','APPROV','approv','enriched'] :
                 filter === 'LOOP2'   ? ['LOOP2','keyword','Keyword'] :
                 filter === 'LOOP3'   ? ['LOOP3','channel vet','Channel vet','auto-appr','auto-dism'] :
                 filter === 'LOOP4'   ? ['LOOP4','brief','Brief'] : [];
      lines = lines.filter(l => kw.some(k => l.includes(k)));
    }
    // Colour-code
    const html = lines.map(l => {
      const esc_l = l.replace(/&/g,'&amp;').replace(/</g,'&lt;').replace(/>/g,'&gt;');
      let color = '#8b949e';
      if (/error|ERROR|traceback|Traceback|failed|exception/i.test(l))  color = '#da3633';
      else if (/ENRICH|enriched|APPROV|approv/i.test(l))                color = '#3fb950';
      else if (/LOOP[234]|keyword|brief|channel.vet/i.test(l))          color = '#e3b341';
      else if (/HTTP Request|httpx|GET|POST/i.test(l))                  color = '#388bfd';
      else if (/HEARTBEAT|heartbeat|RUNNING|running/i.test(l))          color = '#6e7681';
      return `<span style="color:${color}">${esc_l}</span>`;
    }).join('\\n');
    box.innerHTML = html || '<span style="color:#484f58">— no matching log lines —</span>';
    document.getElementById('ai-log-count').textContent =
      `${lines.length} lines · total ${d.total || 0}`;
    if (auto) box.scrollTop = box.scrollHeight;
  } catch(e) { box.textContent = 'Could not load log: ' + e; }
}

function startAILogRefresh()  {
  loadAILog();
  if (!_aiLogInterval) _aiLogInterval = setInterval(loadAILog, 5000);
}
function stopAILogRefresh()   {
  clearInterval(_aiLogInterval); _aiLogInterval = null;
}
// ────────────────────────────────────────────────────

async function loadAIStatus() {
  try {
    const r = await fetch('/api/ai/status');
    const d = await r.json();
    // Badge
    const badge = document.getElementById('ai-status-badge');
    if (d.agent_running) {
      badge.textContent = '● RUNNING';
      badge.style.background = '#1a2d1a';
      badge.style.color = '#3fb950';
    } else {
      badge.textContent = 'NOT RUNNING';
      badge.style.background = '#1a0d0d';
      badge.style.color = '#da3633';
    }
    // Stats
    document.getElementById('ai-stat-enriched').textContent  = d.enrichments_done  || 0;
    document.getElementById('ai-stat-kw').textContent        = d.keywords_added     || 0;
    document.getElementById('ai-stat-approved').textContent  = d.channels_autoapproved || 0;
    document.getElementById('ai-stat-dismissed').textContent = d.channels_autodismissed || 0;
    document.getElementById('ai-stat-briefs').textContent    = d.briefs_generated   || 0;
    // Last run times
    if (d.last_kw_run) {
      document.getElementById('ai-loop2-last').textContent =
        `Last run: ${new Date(d.last_kw_run).toLocaleTimeString()} · next in ~2h`;
    }
    if (d.last_brief_run) {
      document.getElementById('ai-loop4-last').textContent =
        `Last brief: ${new Date(d.last_brief_run).toLocaleTimeString()} · next in ~6h`;
    }
    // Threat brief
    if (d.latest_brief) renderAIBrief(d.latest_brief);
  } catch(e) {}
}

function renderAIBrief(brief) {
  const panel = document.getElementById('ai-brief-panel');
  if (!brief) { panel.style.display = 'none'; return; }
  panel.style.display = 'block';
  const lvl = brief.overall_threat_level || '?';
  const color = BRIEF_COLORS[lvl] || '#8b949e';
  document.getElementById('ai-brief-level').innerHTML =
    `<span style="color:${color}">▲ ${esc(lvl)}</span>`;
  document.getElementById('ai-brief-time').textContent =
    brief.generated_at ? new Date(brief.generated_at).toLocaleString() : '';
  document.getElementById('ai-brief-msgs').textContent =
    brief.messages_analyzed ? `(${brief.messages_analyzed} msgs)` : '';
  document.getElementById('ai-brief-summary').textContent = brief.executive_summary || '';
  // Sectors
  const sectors = (brief.targeted_sectors||[]);
  document.getElementById('ai-brief-sectors').innerHTML =
    sectors.length ? sectors.map(s =>
      `<div>${esc(s.sector)} <span style="color:${BRIEF_COLORS[s.threat_level]||'#484f58'}">[${esc(s.threat_level||'')}]</span></div>`
    ).join('') : '<div style="color:#484f58">None identified</div>';
  // Actions
  const actions = (brief.recommended_actions||[]);
  document.getElementById('ai-brief-actions').innerHTML =
    actions.length ? actions.map(a => `<div>→ ${esc(a)}</div>`).join('') : '';
}

// ── Escalation Banner ────────────────────────────────────────────────────────
async function checkEscalation() {
  try {
    const r = await fetch('/api/escalation/status');
    const d = await r.json();
    const banner = document.getElementById('escalation-banner');
    if (!banner) return;
    const urgency = d.urgency || 'NONE';
    if (urgency === 'CRITICAL' || urgency === 'HIGH') {
      banner.style.display = 'block';
      const uc = urgency === 'CRITICAL' ? '#ff2020' : '#f0883e';
      document.getElementById('esc-urgency').style.color = uc;
      document.getElementById('esc-urgency').textContent = urgency;
      document.getElementById('esc-summary').textContent = d.summary || '';
      document.getElementById('esc-action').textContent = d.recommended_action || '';
      document.getElementById('esc-checked').textContent = d.checked_at
        ? `Updated: ${new Date(d.checked_at).toLocaleTimeString()}` : '';
    } else {
      banner.style.display = 'none';
    }
  } catch(e) {}
}

// ── Hunt Leads Panel ─────────────────────────────────────────────────────────
async function loadHuntLeads() {
  try {
    const r = await fetch('/api/hunting/leads');
    const d = await r.json();
    const leads = d.group_leads || [];
    const countEl = document.getElementById('hunt-count');
    const listEl = document.getElementById('hunt-leads-list');
    if (!listEl) return;
    if (countEl) countEl.textContent = `${leads.length} leads found`;
    if (!leads.length) {
      listEl.innerHTML = '<span style="color:#484f58">No leads yet — LOOP 5 runs every 3 hours</span>';
      return;
    }
    listEl.innerHTML = leads.slice(0, 20).map(g => {
      const conf = g.confidence || 0;
      const cc = conf >= 80 ? '#3fb950' : conf >= 60 ? '#d29922' : '#8b949e';
      const uname = g.username ? `<a href="https://t.me/${esc(g.username)}" target="_blank" ` +
        `style="color:#58a6ff;text-decoration:none">@${esc(g.username)}</a>` : '';
      return `<div style="border-bottom:1px solid #21262d;padding:6px 0;display:flex;gap:10px;align-items:start">
        <span style="color:${cc};font-weight:700;min-width:32px">${conf}%</span>
        <div>
          <span style="color:#e6edf3;font-weight:600">${esc(g.name||'?')}</span>
          ${uname ? ' · ' + uname : ''}
          <span style="color:#484f58;font-size:9px;margin-left:6px">${esc(g.relationship||'')}</span>
          <div style="color:#8b949e;font-size:10px;margin-top:2px">${esc(g.evidence||'')}</div>
          <div style="color:#484f58;font-size:9px">${esc(g.reason_to_monitor||'')}</div>
        </div>
      </div>`;
    }).join('');
  } catch(e) {
    const el = document.getElementById('hunt-leads-list');
    if (el) el.innerHTML = `<span style="color:#da3633">Error: ${esc(String(e))}</span>`;
  }
}

// ── Network Graph Panel ───────────────────────────────────────────────────────
async function loadNetworkGraph() {
  try {
    const r = await fetch('/api/network/graph');
    const d = await r.json();
    const statsEl = document.getElementById('network-stats');
    const listEl  = document.getElementById('network-top-unknown');
    if (!listEl) return;
    const ts = d.generated_at ? new Date(d.generated_at).toLocaleTimeString() : 'never';
    if (statsEl) statsEl.textContent =
      `${d.unknown_channels_scored||0} scored · ${d.newly_queued||0} queued · ${ts}`;
    const top = d.top_unknown || [];
    if (!top.length) {
      listEl.innerHTML = '<span style="color:#484f58">No data yet — LOOP 7 runs every hour</span>';
      return;
    }
    listEl.innerHTML = '<div style="display:flex;flex-wrap:wrap;gap:6px">' +
      top.slice(0, 30).map(u => {
        const score = u.graph_score || 0;
        const cc = score >= 15 ? '#ff6060' : score >= 8 ? '#f0883e' : '#8b949e';
        return `<span style="background:#161b22;border:1px solid #30363d;border-radius:3px;` +
          `padding:2px 7px;font-size:9px">` +
          `<span style="color:${cc}">★${score}</span> ` +
          `<a href="https://t.me/${esc(u.username)}" target="_blank" ` +
          `style="color:#58a6ff;text-decoration:none">@${esc(u.username)}</a></span>`;
      }).join('') + '</div>';
  } catch(e) {
    const el = document.getElementById('network-top-unknown');
    if (el) el.innerHTML = `<span style="color:#da3633">Error: ${esc(String(e))}</span>`;
  }
}

async function aiStart() {
  const btn = document.getElementById('ai-start-btn');
  btn.disabled = true;
  btn.textContent = 'Starting…';
  try {
    const r = await fetch('/api/ai/analyze', {method:'POST',
      headers:{'Content-Type':'application/json'}, body:'{}'});
    const d = await r.json();
    if (d.error) {
      showToast(`AI: ${d.error}`, true);
    } else {
      showToast(`AI agent started (PID ${d.pid}) — all 7 loops running`, false);
      // Start polling
      if (_aiStatusInterval) clearInterval(_aiStatusInterval);
      _aiStatusInterval = setInterval(loadAIStatus, 10000);
    }
  } catch(e) {
    showToast(`Error starting AI agent: ${e}`, true);
  }
  btn.disabled = false;
  btn.textContent = '▶ Start Agent';
  setTimeout(loadAIStatus, 2000);
}

async function aiStop() {
  const r = await fetch('/api/ai/stop', {method:'POST',
    headers:{'Content-Type':'application/json'}, body:'{}'});
  const d = await r.json();
  showToast(`AI agent stopped (PIDs: ${d.stopped.join(', ')})`, false);
  if (_aiStatusInterval) { clearInterval(_aiStatusInterval); _aiStatusInterval = null; }
  setTimeout(loadAIStatus, 1000);
}

// Kept for backward compat but unused in new design
async function aiApplySuggestions() {}
async function aiRunAnalysis() { aiStart(); }

// ═══════════════════════════════════════════════════════════════════════════
// CHAT TAB
// ═══════════════════════════════════════════════════════════════════════════

let _chatHistory = [];   // [{role, content, references, ref_messages, timestamp}]
let _chatStreaming = false;

async function loadChatTab() {
  // Session-only: show existing bubbles or empty state
  const box = document.getElementById('chat-messages');
  const empty = document.getElementById('chat-empty');
  if (_chatHistory.length === 0) {
    box.querySelectorAll('.chat-bubble').forEach(el => el.remove());
    if (empty) empty.style.display = 'block';
  } else {
    if (empty) empty.style.display = 'none';
  }
  // Dynamic suggestions from recent CRITICALs
  try {
    const sugBox = document.getElementById('chat-suggestions');
    if (sugBox && !sugBox.dataset.loaded) {
      const r = await fetch('/api/messages/all?priority=CRITICAL&limit=10');
      const msgs = await r.json();
      if (msgs.length) {
        const channels = [...new Set(msgs.slice(0,10).map(m => m.channel_username).filter(Boolean))].slice(0,2);
        for (const ch of channels) {
          const btn = document.createElement('button');
          btn.onclick = function(){chatSuggest(this)};
          btn.textContent = 'What is @' + ch + ' doing?';
          btn.style.cssText = 'font-size:10px;padding:4px 10px;background:#1a0d0d;border:1px solid #da363355;color:#ff7b7b;border-radius:12px;cursor:pointer';
          sugBox.appendChild(btn);
        }
        // Report suggestion buttons
        const reportSugs = ['Generate a threat report for the last 24 hours', 'Write a report on all DDoS activity'];
        for (const txt of reportSugs) {
          const btn = document.createElement('button');
          btn.onclick = function(){chatSuggest(this)};
          btn.textContent = txt;
          btn.style.cssText = 'font-size:10px;padding:4px 10px;background:#0d1628;border:1px solid #1f6feb55;color:#58a6ff;border-radius:12px;cursor:pointer';
          sugBox.appendChild(btn);
        }
        sugBox.dataset.loaded = '1';
      }
    }
  } catch(e) {}
  // Threat pulse indicator
  updateThreatPulse();
}

async function sendChatMessage() {
  if (_chatStreaming) return;
  const input = document.getElementById('chat-input');
  const msg = (input.value || '').trim();
  if (!msg) return;
  input.value = '';
  input.style.height = '';
  _chatStreaming = true;

  const box   = document.getElementById('chat-messages');
  const empty = document.getElementById('chat-empty');
  const btn   = document.getElementById('chat-send-btn');
  if (empty) empty.style.display = 'none';

  const userBubble = _buildBubble('user', msg, [], [], new Date().toISOString());
  box.appendChild(userBubble);
  box.scrollTop = box.scrollHeight;

  const aiBubbleWrap = document.createElement('div');
  aiBubbleWrap.className = 'chat-bubble';
  aiBubbleWrap.style.cssText = 'display:flex;gap:8px;align-items:flex-start;max-width:85%';
  aiBubbleWrap.innerHTML = `
    <div style="width:28px;height:28px;background:#1f3350;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:13px;flex-shrink:0">🤖</div>
    <div style="flex:1;min-width:0">
      <div class="stream-content" style="background:#161b22;border:1px solid #30363d;border-radius:2px 10px 10px 10px;padding:10px 14px;font-size:12px;color:#c9d1d9;line-height:1.5">
        <span class="typing-dots">Thinking</span>
      </div>
      <div class="stream-ts" style="font-size:9px;color:#484f58;margin-top:2px"></div>
    </div>`;
  box.appendChild(aiBubbleWrap);
  box.scrollTop = box.scrollHeight;
  btn.disabled = true; btn.textContent = '...';

  const histForApi = _chatHistory.map(m => ({role: m.role, content: m.content}));
  let fullText = '';
  const contentEl = aiBubbleWrap.querySelector('.stream-content');
  const tsEl = aiBubbleWrap.querySelector('.stream-ts');
  let searchCount = 0;

  try {
    const response = await fetch('/api/chat/stream', {
      method: 'POST',
      headers: {'Content-Type':'application/json'},
      body: JSON.stringify({message: msg, history: histForApi})
    });

    if (!response.ok) {
      let errMsg = 'Request failed (' + response.status + ')';
      try { const ed = await response.json(); errMsg = ed.error || errMsg; } catch(e){}
      contentEl.innerHTML = '<span style="color:#da3633">Error: ' + esc(errMsg) + '</span>';
      btn.disabled = false; btn.textContent = 'Send ▶'; _chatStreaming = false;
      return;
    }

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';

    while (true) {
      const {done, value} = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, {stream: true});

      const lines = buffer.split('\n');
      buffer = lines.pop();

      for (const line of lines) {
        if (!line.startsWith('data: ')) continue;
        const jsonStr = line.slice(6);
        if (!jsonStr) continue;
        try {
          const evt = JSON.parse(jsonStr);
          if (evt.type === 'status') {
            searchCount++;
            contentEl.innerHTML = '<div style="color:#58a6ff;font-size:11px"><span class="typing-dots">Searching</span></div>'
              + '<div style="font-size:10px;color:#8b949e;margin-top:4px">' + esc(evt.message) + '</div>'
              + '<div style="font-size:9px;color:#484f58;margin-top:2px">' + searchCount + ' search' + (searchCount>1?'es':'') + ' completed</div>';
            box.scrollTop = box.scrollHeight;
          } else if (evt.type === 'token') {
            fullText += evt.content;
            const displayText = fullText.split('---REFS---')[0];
            contentEl.innerHTML = _formatMarkdown(displayText) + '<span class="stream-cursor"></span>';
            box.scrollTop = box.scrollHeight;
          } else if (evt.type === 'done') {
            const answer = evt.answer || fullText.split('---REFS---')[0].trim();
            contentEl.innerHTML = _formatMarkdown(answer);
            const refCount = (evt.references || []).length;
            if (refCount > 0) {
              const refBtn = document.createElement('button');
              refBtn.setAttribute('data-refs', JSON.stringify(evt.ref_messages || []).replace(/'/g,"&#39;"));
              refBtn.style.cssText = 'margin-top:8px;font-size:9px;padding:3px 9px;background:#161b22;border:1px solid #30363d;color:#58a6ff;border-radius:4px;cursor:pointer;display:block';
              refBtn.textContent = '📎 ' + refCount + ' source' + (refCount>1?'s':'') + ' cited';
              refBtn.onclick = function() { chatShowSources(this); };
              contentEl.appendChild(refBtn);
              if (evt.ref_messages && evt.ref_messages.length) {
                renderSources(evt.ref_messages);
                const srcToggle = document.getElementById('chat-src-toggle');
                if (srcToggle) srcToggle.classList.add('has-new');
              }
            }
            const tsInfo = new Date().toLocaleTimeString([], {hour:'2-digit',minute:'2-digit'})
              + ' · ' + (evt.elapsed_s || '?') + 's · ' + (evt.context_msgs || '?') + ' msgs analyzed'
              + (searchCount > 0 ? ' · ' + searchCount + ' searches' : '');
            tsEl.textContent = tsInfo;
            _chatHistory.push({role:'user', content:msg, references:[], ref_messages:[], timestamp: new Date().toISOString()});
            _chatHistory.push({role:'assistant', content:answer, references:evt.references||[], ref_messages:evt.ref_messages||[], timestamp:new Date().toISOString()});
          } else if (evt.type === 'error') {
            contentEl.innerHTML = '<span style="color:#da3633">Error: ' + esc(evt.message) + '</span>';
          }
        } catch(parseErr) { /* skip malformed SSE events */ }
      }
    }
  } catch(e) {
    contentEl.innerHTML = '<span style="color:#da3633">Network error: ' + esc(e.message) + '</span>';
  }
  btn.disabled = false; btn.textContent = 'Send ▶';
  _chatStreaming = false;
  box.scrollTop = box.scrollHeight;
}

function _formatMarkdown(text) {
  if (!text) return '';
  // Use marked.js if available, fallback to basic formatting
  if (typeof marked !== 'undefined') {
    try {
      // Protect [REF:N] tags from markdown parsing
      let safe = text.replace(/\[REF:(\d+)\]/g, '%%REF_$1%%');
      const html = marked.parse(safe, {breaks: true, gfm: true});
      // Restore [REF:N] tags with styled spans
      const final = html.replace(/%%REF_(\d+)%%/g,
        '<span class="ref-tag" title="Source reference $1">[REF:$1]</span>');
      return '<div class="md-render">' + final + '</div>';
    } catch(e) { /* fallback below */ }
  }
  // Fallback: basic escaping + bold + refs
  let html = esc(text);
  html = html.replace(/\*\*(.*?)\*\*/g, '<strong style="color:#e6edf3">$1</strong>');
  html = html.replace(/\[REF:(\d+)\]/g, '<span class="ref-tag" title="Source reference $1">[REF:$1]</span>');
  html = html.replace(/\n/g, '<br>');
  return html;
}

function _buildBubble(role, content, refs, refMsgs, timestamp) {
  const wrap = document.createElement('div');
  wrap.className = 'chat-bubble';
  const isUser = role === 'user';
  const ts = timestamp ? new Date(timestamp).toLocaleTimeString([], {hour:'2-digit',minute:'2-digit'}) : '';

  if (isUser) {
    wrap.style.cssText = 'display:flex;justify-content:flex-end;';
    wrap.innerHTML = `
      <div style="max-width:75%">
        <div style="background:#1f6feb22;border:1px solid #1f6feb55;border-radius:10px 10px 2px 10px;padding:10px 14px;font-size:12px;color:#e6edf3;white-space:pre-wrap">${esc(content)}</div>
        <div style="font-size:9px;color:#484f58;text-align:right;margin-top:2px">${esc(ts)}</div>
      </div>`;
  } else {
    const formatted = _formatMarkdown(content);
    const refCount = refs.length;
    const refBtnHtml = refCount > 0
      ? `<button onclick="chatShowSources(this)" data-refs='${JSON.stringify(refMsgs).replace(/'/g,"&#39;")}' style="margin-top:8px;font-size:9px;padding:3px 9px;background:#161b22;border:1px solid #30363d;color:#58a6ff;border-radius:4px;cursor:pointer">📎 ${refCount} source${refCount>1?'s':''} cited</button>`
      : '';
    wrap.style.cssText = 'display:flex;gap:8px;align-items:flex-start;max-width:85%';
    wrap.innerHTML = `
      <div style="width:28px;height:28px;background:#1f3350;border-radius:50%;display:flex;align-items:center;justify-content:center;font-size:13px;flex-shrink:0">🤖</div>
      <div style="flex:1;min-width:0">
        <div style="background:#161b22;border:1px solid #30363d;border-radius:2px 10px 10px 10px;padding:10px 14px;font-size:12px;color:#c9d1d9;line-height:1.5">
          ${formatted}
          ${refBtnHtml}
        </div>
        <div style="font-size:9px;color:#484f58;margin-top:2px">${esc(ts)}</div>
      </div>`;
  }
  return wrap;
}

function chatShowSources(btn) {
  try {
    const msgs = JSON.parse(btn.getAttribute('data-refs') || '[]');
    renderSources(msgs);
    // Scroll sources panel to top
    const sp = document.getElementById('chat-sources');
    if (sp) sp.scrollTop = 0;
  } catch(e) {}
}

function renderSources(refMsgs) {
  const panel = document.getElementById('chat-sources');
  const count = document.getElementById('chat-src-count');
  if (!panel) return;
  if (!refMsgs || refMsgs.length === 0) {
    panel.innerHTML = '<div style="color:#484f58;font-size:11px;text-align:center;margin-top:40px">No sources</div>';
    if (count) count.textContent = '';
    return;
  }
  if (count) count.textContent = `${refMsgs.length} message${refMsgs.length>1?'s':''}`;
  const PCOL = {CRITICAL:'#da3633',HIGH:'#e3b341',MEDIUM:'#3fb950',LOW:'#484f58'};
  panel.innerHTML = refMsgs.map((m,i) => {
    const pri   = m.priority || 'LOW';
    const col   = PCOL[pri] || '#484f58';
    const ch    = esc(m.channel || m.channel_username || '?');
    const uname = esc(m.channel_username || '');
    const ts    = (m.timestamp_utc || '').substring(0,16).replace('T',' ');
    const text  = esc((m.text_preview || '').substring(0,350));
    const mid   = m.message_id || '?';
    const ae    = m.ai_enrichment || {};
    const enrichHtml = ae.summary
      ? `<div style="margin-top:6px;padding:5px 7px;background:#0a0f17;border-radius:3px;border-left:2px solid #388bfd;font-size:9px;color:#8b949e"><strong style="color:#388bfd">AI:</strong> ${esc(ae.summary.substring(0,200))}</div>`
      : '';
    const toggleId = 'src-text-' + mid + '-' + i;
    return `<div style="background:#161b22;border:1px solid #21262d;border-radius:6px;padding:10px;margin-bottom:8px;cursor:pointer" onclick="document.getElementById('${toggleId}').style.display=document.getElementById('${toggleId}').style.display==='none'?'block':'none'">
      <div style="display:flex;align-items:center;gap:6px;margin-bottom:4px">
        <span style="font-size:8px;font-weight:700;color:${col};background:${col}22;padding:1px 5px;border-radius:3px">${pri}</span>
        <span style="font-size:10px;font-weight:600;color:#e6edf3">${ch}</span>
        <span style="font-size:9px;color:#484f58">@${uname}</span>
        <div style="flex:1"></div>
        <span style="font-size:9px;color:#484f58">${ts}</span>
      </div>
      <div id="${toggleId}" style="font-size:10px;color:#8b949e;line-height:1.4;white-space:pre-wrap;word-break:break-word">
        ${text}${enrichHtml}
      </div>
      <div style="font-size:8px;color:#484f58;margin-top:4px">MSG ID: ${mid}</div>
    </div>`;
  }).join('');
}

function clearChat() {
  if (!confirm('Clear conversation?')) return;
  _chatHistory = [];
  const box = document.getElementById('chat-messages');
  box.querySelectorAll('.chat-bubble').forEach(el => el.remove());
  const empty = document.getElementById('chat-empty');
  if (empty) empty.style.display = 'block';
  renderSources([]);
  const count = document.getElementById('chat-src-count');
  if (count) count.textContent = '';
}

function toggleSourcesPanel() {
  const panel = document.getElementById('chat-sources-panel');
  const btn = document.getElementById('chat-src-toggle');
  if (!panel) return;
  const isHidden = panel.style.display === 'none';
  panel.style.display = isHidden ? 'flex' : 'none';
  if (btn) {
    btn.textContent = isHidden ? '📎 SOURCES ✕' : '📎 SOURCES';
    btn.classList.remove('has-new');
  }
}

function updateThreatPulse() {
  fetch('/api/channels').then(r=>r.json()).then(data=>{
    const el = document.getElementById('chat-threat-pulse');
    if (!el) return;
    const totalCrit = data.reduce((s,c) => s + (c.critical_24h || 0), 0);
    let color, label;
    if (totalCrit >= 10) { color='#da3633'; label='ELEVATED'; }
    else if (totalCrit >= 3) { color='#e3b341'; label='GUARDED'; }
    else { color='#3fb950'; label='NOMINAL'; }
    el.innerHTML = '<span style="display:inline-flex;align-items:center;gap:3px"><span style="width:5px;height:5px;border-radius:50%;background:'+color+'"></span><span style="color:'+color+';font-size:8px;font-weight:700">'+label+'</span></span>';
  }).catch(()=>{});
}

function exportChatReport() {
  if (!_chatHistory.length) { alert('No conversation to export'); return; }
  let md = '# Scanwave CyberIntel - Chat Report\n';
  md += 'Generated: ' + new Date().toISOString() + '\n\n---\n\n';
  for (const m of _chatHistory) {
    const ts = m.timestamp ? new Date(m.timestamp).toLocaleString() : '';
    if (m.role === 'user') {
      md += '## Analyst Query (' + ts + ')\n' + m.content + '\n\n';
    } else {
      md += '## Intelligence Response (' + ts + ')\n' + m.content + '\n\n';
      if (m.references && m.references.length) {
        md += '**Sources cited:** ' + m.references.length + ' messages\n\n';
      }
    }
    md += '---\n\n';
  }
  const blob = new Blob([md], {type:'text/markdown'});
  const a = document.createElement('a');
  a.href = URL.createObjectURL(blob);
  a.download = 'intel_chat_report_' + new Date().toISOString().slice(0,10) + '.md';
  a.click();
}

function chatSuggest(btn) {
  const input = document.getElementById('chat-input');
  if (input) { input.value = btn.textContent; input.focus(); }
}

function chatInputKeydown(e) {
  if (e.key === 'Enter' && !e.shiftKey) {
    e.preventDefault();
    if (!_chatStreaming) sendChatMessage();
  }
}

// ═══════════════════════════ APT TRACKER JS ═══════════════════════════════

let _aptProfiles = [];
let _selectedAPT = null;
let _aptLoaded = false;

async function loadAPTTab() {
  if (_aptLoaded && _aptProfiles.length > 0) return;
  const list = document.getElementById('apt-sidebar-list');
  if (list) list.innerHTML = '<div style="padding:20px;text-align:center;color:#484f58;font-size:11px">Loading APT profiles...</div>';
  try {
    const resp = await fetch('/api/apt/profiles');
    _aptProfiles = await resp.json();
    _aptLoaded = true;
    renderAPTSidebar(_aptProfiles);
    if (_aptProfiles.length > 0 && !_selectedAPT) {
      selectAPT(_aptProfiles[0].name);
    }
  } catch(e) {
    if (list) list.innerHTML = '<div style="padding:20px;color:#da3633;font-size:11px">Failed to load: ' + esc(e.message) + '</div>';
  }
}

function renderAPTSidebar(profiles) {
  const list = document.getElementById('apt-sidebar-list');
  if (!list) return;
  let currentTier = 0;
  let html = '';
  profiles.forEach(p => {
    if (p.tier !== currentTier) {
      currentTier = p.tier;
      const tierLabel = currentTier === 1 ? 'TIER 1 — DIRECT THREAT' : currentTier === 2 ? 'TIER 2 — ECOSYSTEM' : 'TIER 3 — PERIPHERAL';
      const tierColor = currentTier === 1 ? '#da3633' : currentTier === 2 ? '#e3b341' : '#484f58';
      html += '<div style="padding:6px 10px;font-size:8px;font-weight:800;color:' + tierColor + ';letter-spacing:1px;border-bottom:1px solid #21262d;background:#0d1117;position:sticky;top:0;z-index:1">' + tierLabel + '</div>';
    }
    const isActive = _selectedAPT === p.name;
    const dotClass = p.status === 'active' ? 'active' : 'stale';
    html += '<div class="apt-card t' + p.tier + (isActive ? ' active' : '') + '" onclick="selectAPT(\'' + esc(p.name.replace(/'/g,"\\'")) + '\')" data-apt="' + esc(p.name) + '">';
    html += '<div class="apt-name">' + esc(p.name) + '</div>';
    html += '<div class="apt-meta">';
    html += '<span class="apt-dot ' + dotClass + '"></span>';
    html += '<span class="tier-badge t' + p.tier + '">T' + p.tier + '</span>';
    if (p.critical_count > 0) html += '<span style="color:#da3633;font-weight:700">' + p.critical_count + ' CRIT</span>';
    if (p.ioc_count > 0) html += '<span style="color:#58a6ff">' + p.ioc_count + ' IOC</span>';
    if (p.jordan_attacks > 0) html += '<span style="color:#f85149">🇯🇴' + p.jordan_attacks + '</span>';
    html += '</div></div>';
  });
  list.innerHTML = html;
}

function aptFilterSidebar() {
  const q = (document.getElementById('apt-filter-input').value || '').toLowerCase();
  const cards = document.querySelectorAll('.apt-card');
  cards.forEach(c => {
    const name = (c.getAttribute('data-apt') || '').toLowerCase();
    c.style.display = (!q || name.includes(q)) ? '' : 'none';
  });
}

async function selectAPT(name) {
  _selectedAPT = name;
  // Update sidebar active state
  document.querySelectorAll('.apt-card').forEach(c => {
    c.classList.toggle('active', c.getAttribute('data-apt') === name);
  });
  const panel = document.getElementById('apt-detail-panel');
  if (!panel) return;
  panel.innerHTML = '<div style="text-align:center;padding:40px;color:#484f58"><div class="spinner" style="margin:0 auto 12px"></div>Loading ' + esc(name) + '...</div>';

  try {
    const resp = await fetch('/api/apt/' + encodeURIComponent(name) + '/detail');
    const data = await resp.json();
    renderAPTDetail(data, name);
  } catch(e) {
    panel.innerHTML = '<div style="color:#da3633;padding:20px">Error: ' + esc(e.message) + '</div>';
  }
}

function renderAPTDetail(data, name) {
  const panel = document.getElementById('apt-detail-panel');
  if (!panel) return;

  // Find profile for tier info
  const profile = _aptProfiles.find(p => p.name === name) || {};
  const tier = profile.tier || 3;
  const threat = profile.threat || 'MEDIUM';
  const status = profile.status || 'unknown';
  const tierColor = tier === 1 ? '#da3633' : tier === 2 ? '#e3b341' : '#484f58';
  const statusColor = status === 'active' ? '#3fb950' : '#484f58';

  let html = '';

  // ─── Header card ───
  html += '<div class="apt-header">';
  html += '<div class="apt-header-name">' + esc(name) + ' <span class="tier-badge t' + tier + '">TIER ' + tier + '</span>';
  html += ' <span style="font-size:10px;padding:2px 8px;border-radius:3px;background:' + statusColor + '22;color:' + statusColor + ';font-weight:700;border:1px solid ' + statusColor + '44">' + status.toUpperCase() + '</span>';
  html += '</div>';
  html += '<div class="apt-header-channels">Channels: ' + (data.channels || []).map(c => '@' + c).join(', ') + '</div>';
  html += '<div id="apt-summary-bio" style="margin:8px 0;padding:8px 12px;background:#161b2288;border-left:3px solid #388bfd;color:#8b949e;font-size:10px;line-height:1.5;font-style:italic;display:none"></div>';
  html += '<div style="display:flex;gap:20px;margin-top:10px;flex-wrap:wrap">';
  html += _aptStatBox('Total Messages', data.total_msgs, '#58a6ff');
  html += _aptStatBox('CRITICAL', data.critical_count, '#da3633');
  html += _aptStatBox('MEDIUM', data.medium_count, '#e3b341');
  html += '<div style="text-align:center"><div id="apt-ioc-count" style="font-size:20px;font-weight:800;color:#a371f7">...</div><div style="font-size:8px;color:#6e7681;text-transform:uppercase;letter-spacing:.5px">Intel IOCs</div></div>';
  html += _aptStatBox('Jordan Attacks', (data.attacks || []).length, '#f85149');
  html += '</div>';
  html += '<div style="font-size:9px;color:#484f58;margin-top:6px">First seen: ' + (data.first_seen || 'N/A').slice(0,10) + ' | Last seen: ' + (data.last_seen || 'N/A').slice(0,10) + '</div>';
  html += '</div>';

  // ─── Two-column layout for sectors + attack types ───
  html += '<div style="display:flex;gap:14px">';

  // Sector breakdown
  const sectors = data.sectors || {};
  const sectorKeys = Object.keys(sectors);
  if (sectorKeys.length > 0) {
    const maxSector = Math.max(...Object.values(sectors));
    html += '<div style="flex:1;background:#161b22;border:1px solid #30363d;border-radius:8px;padding:12px 14px">';
    html += '<div style="font-size:11px;font-weight:700;color:#e6edf3;margin-bottom:8px">TARGET SECTORS</div>';
    const sectorColors = {Government:'#da3633',Military:'#f85149',Banking:'#e3b341',Finance:'#e3b341',Telecom:'#388bfd',Media:'#a371f7',Energy:'#3fb950',Infrastructure:'#6e7681',Education:'#58a6ff',Aviation:'#79c0ff',Healthcare:'#56d364'};
    sectorKeys.slice(0,8).forEach(s => {
      const pct = Math.round((sectors[s] / maxSector) * 100);
      const col = sectorColors[s] || '#388bfd';
      html += '<div class="sector-bar-wrap"><span class="sector-bar-label">' + esc(s) + '</span>';
      html += '<div style="flex:1;background:#21262d;border-radius:2px;overflow:hidden"><div style="width:' + pct + '%;height:16px;background:' + col + ';border-radius:2px;transition:width .4s"></div></div>';
      html += '<span style="font-size:10px;color:#8b949e;width:30px;text-align:right">' + sectors[s] + '</span></div>';
    });
    html += '</div>';
  }

  // Attack types
  const atypes = data.attack_types || {};
  const atypeKeys = Object.keys(atypes);
  if (atypeKeys.length > 0) {
    const maxA = Math.max(...Object.values(atypes));
    html += '<div style="flex:1;background:#161b22;border:1px solid #30363d;border-radius:8px;padding:12px 14px">';
    html += '<div style="font-size:11px;font-weight:700;color:#e6edf3;margin-bottom:8px">ATTACK TYPES</div>';
    const atkColors = {DDoS:'#da3633',Defacement:'#f85149',Hack:'#e3b341',Leak:'#a371f7','Data Breach':'#a371f7',Phishing:'#388bfd',Ransomware:'#f85149',Wiper:'#da3633'};
    atypeKeys.slice(0,8).forEach(a => {
      const pct = Math.round((atypes[a] / maxA) * 100);
      const col = atkColors[a] || '#388bfd';
      html += '<div class="sector-bar-wrap"><span class="sector-bar-label">' + esc(a) + '</span>';
      html += '<div style="flex:1;background:#21262d;border-radius:2px;overflow:hidden"><div style="width:' + pct + '%;height:16px;background:' + col + ';border-radius:2px;transition:width .4s"></div></div>';
      html += '<span style="font-size:10px;color:#8b949e;width:30px;text-align:right">' + atypes[a] + '</span></div>';
    });
    html += '</div>';
  }
  html += '</div>';

  // ─── External Threat Intelligence ───
  html += '<div style="background:#161b22;border:1px solid #30363d;border-radius:8px;padding:12px 14px">';
  html += '<div style="display:flex;align-items:center;justify-content:space-between;margin-bottom:8px">';
  html += '<div style="font-size:11px;font-weight:700;color:#a371f7">EXTERNAL THREAT INTELLIGENCE</div>';
  html += '<span style="font-size:9px;color:#484f58">Sources: OTX, ThreatFox, GPT-4o | Verified via AbuseIPDB</span>';
  html += '</div>';
  html += '<div id="apt-research-results"><div style="text-align:center;padding:15px;color:#484f58;font-size:11px"><div class="spinner" style="margin:0 auto 8px"></div>Loading threat intelligence...</div></div>';
  html += '</div>';

  // Auto-fetch researched IOCs for this APT
  setTimeout(() => _loadAPTResearch(name), 100);

  // ─── Jordan Attacks Timeline ───
  const attacks = data.attacks || [];
  if (attacks.length > 0) {
    html += '<div style="background:#161b22;border:1px solid #30363d;border-radius:8px;padding:12px 14px">';
    html += '<div style="font-size:11px;font-weight:700;color:#f85149;margin-bottom:8px">🇯🇴 JORDAN-TARGETING ATTACKS (' + attacks.length + ')</div>';
    html += '<div style="max-height:200px;overflow-y:auto">';
    attacks.slice(0, 30).forEach(a => {
      html += '<div style="display:flex;gap:8px;align-items:center;padding:4px 0;border-bottom:1px solid #0d1117;font-size:10px">';
      html += '<span style="color:#484f58;font-family:monospace;width:80px;flex-shrink:0">' + esc(a.date) + '</span>';
      html += '<span style="color:#f85149;font-weight:600;width:140px;flex-shrink:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">' + esc(a.target) + '</span>';
      html += '<span style="font-size:8px;color:#e3b341;background:#e3b34118;padding:1px 5px;border-radius:2px">' + esc(a.type) + '</span>';
      html += '<span style="color:#6e7681;flex:1;overflow:hidden;text-overflow:ellipsis;white-space:nowrap">' + esc(a.summary) + '</span>';
      html += '</div>';
    });
    html += '</div></div>';
  }

  // ─── Activity Timeline ───
  const tl = data.timeline || [];
  if (tl.length > 0) {
    html += '<div style="background:#161b22;border:1px solid #30363d;border-radius:8px;padding:12px 14px">';
    html += '<div style="font-size:11px;font-weight:700;color:#e6edf3;margin-bottom:8px">ACTIVITY TIMELINE</div>';
    const maxTL = Math.max(...tl.map(t => (t.critical || 0) + (t.medium || 0) + (t.low || 0)));
    html += '<div style="display:flex;align-items:flex-end;gap:3px;height:80px">';
    tl.forEach(t => {
      const total = (t.critical || 0) + (t.medium || 0) + (t.low || 0);
      const h = maxTL > 0 ? Math.max(2, Math.round((total / maxTL) * 70)) : 2;
      const col = (t.critical || 0) > 0 ? '#da3633' : (t.medium || 0) > 0 ? '#e3b341' : '#388bfd';
      html += '<div title="' + t.month + ': ' + total + ' msgs (' + (t.critical||0) + ' CRIT)" style="flex:1;min-width:8px;background:' + col + ';height:' + h + 'px;border-radius:2px 2px 0 0;cursor:pointer"></div>';
    });
    html += '</div>';
    html += '<div style="display:flex;justify-content:space-between;font-size:8px;color:#484f58;margin-top:2px"><span>' + (tl[0]||{}).month + '</span><span>' + (tl[tl.length-1]||{}).month + '</span></div>';
    html += '</div>';
  }

  // ─── Recent Critical Messages ───
  const msgs = data.recent_messages || [];
  if (msgs.length > 0) {
    html += '<div style="background:#161b22;border:1px solid #30363d;border-radius:8px;padding:12px 14px">';
    html += '<div style="font-size:11px;font-weight:700;color:#e6edf3;margin-bottom:8px">RECENT CRITICAL MESSAGES (' + msgs.length + ')</div>';
    html += '<div style="max-height:250px;overflow-y:auto">';
    msgs.slice(0, 15).forEach(m => {
      html += '<div style="padding:6px 8px;border-bottom:1px solid #0d1117;font-size:10px">';
      html += '<div style="display:flex;gap:6px;align-items:center;margin-bottom:3px">';
      html += '<span style="font-size:8px;font-weight:700;color:#da3633;background:#da363318;padding:1px 5px;border-radius:2px">CRIT</span>';
      html += '<span style="color:#58a6ff;font-weight:600">@' + esc(m.channel) + '</span>';
      html += '<span style="color:#484f58;font-size:9px">' + (m.timestamp || '').slice(0,16).replace('T',' ') + '</span>';
      html += '</div>';
      html += '<div style="color:#8b949e;line-height:1.4;word-break:break-word">' + esc(m.text) + '</div>';
      const iocKeys = Object.keys(m.iocs || {});
      if (iocKeys.length > 0) {
        html += '<div style="margin-top:3px;display:flex;gap:4px;flex-wrap:wrap">';
        iocKeys.forEach(k => {
          (m.iocs[k] || []).forEach(v => {
            html += '<span style="font-size:8px;font-family:monospace;background:#0d1117;border:1px solid #21262d;padding:1px 5px;border-radius:2px;color:#79c0ff">' + esc(k) + ':' + esc(v) + '</span>';
          });
        });
        html += '</div>';
      }
      html += '</div>';
    });
    html += '</div></div>';
  }

  panel.innerHTML = html;
}

function _aptStatBox(label, value, color) {
  return '<div style="text-align:center"><div style="font-size:20px;font-weight:800;color:' + color + '">' + (value || 0) + '</div><div style="font-size:8px;color:#6e7681;text-transform:uppercase;letter-spacing:.5px">' + label + '</div></div>';
}

async function _loadAPTResearch(name) {
  const container = document.getElementById('apt-research-results');
  if (!container) return;
  try {
    const resp = await fetch('/api/apt/' + encodeURIComponent(name) + '/research');
    const data = await resp.json();
    // Populate summary bio
    const bioDiv = document.getElementById('apt-summary-bio');
    if (bioDiv && data.summary) {
      bioDiv.textContent = data.summary;
      bioDiv.style.display = 'block';
    }
    // Update IOC count stat box
    const iocCount = document.getElementById('apt-ioc-count');
    if (iocCount && data.stats) iocCount.textContent = data.stats.total || 0;
    _renderResearchedIOCs(data, container);
  } catch(e) {
    container.innerHTML = '<div style="color:#484f58;font-size:10px;padding:10px">Research data not yet available. Background scan in progress.</div>';
  }
}

function _renderResearchedIOCs(data, container) {
  const iocs = data.iocs || [];
  const stats = data.stats || {};
  let html = '';

  // Stats
  html += '<div style="display:flex;gap:12px;margin-bottom:8px;flex-wrap:wrap;align-items:center">';
  html += '<span style="font-size:10px;color:#da3633;font-weight:700">' + (stats.malicious||0) + ' MALICIOUS</span>';
  html += '<span style="font-size:10px;color:#e3b341;font-weight:700">' + (stats.suspicious||0) + ' SUSPICIOUS</span>';
  html += '<span style="font-size:10px;color:#3fb950">' + (stats.clean||0) + ' CLEAN</span>';
  html += '<span style="font-size:9px;color:#484f58">' + (stats.total||0) + ' total from ' + (data.sources_queried||[]).join(', ') + '</span>';
  if (data.cached) html += '<span style="font-size:8px;color:#484f58;background:#21262d;padding:1px 5px;border-radius:2px">cached</span>';
  html += '</div>';

  if (iocs.length === 0) {
    html += '<div style="font-size:10px;color:#484f58;padding:8px;text-align:center">No IOCs found from external sources. Background research may still be running.</div>';
    container.innerHTML = html;
    return;
  }

  // Filter
  html += '<input type="text" id="apt-research-filter" oninput="aptFilterResearch()" placeholder="Filter IOCs..." style="width:100%;background:#0d1117;border:1px solid #21262d;border-radius:4px;padding:4px 8px;color:#e6edf3;font-size:10px;margin-bottom:6px;box-sizing:border-box">';

  // Table
  html += '<div style="max-height:300px;overflow-y:auto">';
  html += '<table style="width:100%;border-collapse:collapse;font-size:10px"><thead><tr style="border-bottom:1px solid #30363d;color:#8b949e;font-size:9px;text-transform:uppercase"><th style="text-align:left;padding:4px 6px">Type</th><th style="text-align:left;padding:4px 6px">Value</th><th style="text-align:center;padding:4px 6px">Verdict</th><th style="text-align:center;padding:4px 6px">Score</th><th style="text-align:left;padding:4px 6px">Source</th><th style="padding:4px"></th></tr></thead><tbody>';
  const tc = {ipv4:'#da3633',domain:'#e3b341',url:'#388bfd',hash_md5:'#a371f7',hash_sha256:'#a371f7',cve:'#f85149'};
  const vc = {MALICIOUS:'#da3633',SUSPICIOUS:'#e3b341',CLEAN:'#3fb950',UNVERIFIED:'#484f58'};
  iocs.forEach(ioc => {
    const tCol = tc[ioc.type] || '#8b949e';
    const vCol = vc[ioc.abuse_verdict] || '#8b949e';
    html += '<tr class="research-row" data-val="' + esc((ioc.value||'').toLowerCase()) + '" style="border-bottom:1px solid #161b22">';
    html += '<td style="padding:4px 6px"><span style="font-size:8px;font-weight:700;color:' + tCol + ';background:' + tCol + '18;padding:1px 5px;border-radius:2px;text-transform:uppercase">' + esc(ioc.type) + '</span></td>';
    html += '<td style="padding:4px 6px;font-family:monospace;color:#e6edf3;word-break:break-all;cursor:pointer" title="' + esc(ioc.context||'') + '" onclick="aptLookupFromTable(\'' + esc(ioc.value.replace(/'/g,"\\'")) + '\')">' + esc(ioc.value) + '</td>';
    html += '<td style="padding:4px 6px;text-align:center"><span style="font-size:8px;font-weight:700;color:' + vCol + ';background:' + vCol + '18;padding:1px 4px;border-radius:2px">' + (ioc.abuse_verdict||'--') + '</span></td>';
    html += '<td style="padding:4px 6px;text-align:center;color:' + vCol + ';font-weight:700">' + (ioc.abuse_score >= 0 ? ioc.abuse_score + '%' : '--') + '</td>';
    html += '<td style="padding:4px 6px;font-size:8px;color:#6e7681">' + esc(ioc.source||'') + '</td>';
    html += '<td style="padding:4px"><button onclick="event.stopPropagation();navigator.clipboard.writeText(\'' + esc(ioc.value.replace(/'/g,"\\'")) + '\')" style="background:none;border:1px solid #21262d;color:#8b949e;padding:2px 5px;border-radius:3px;cursor:pointer;font-size:9px">copy</button></td>';
    html += '</tr>';
  });
  html += '</tbody></table></div>';
  container.innerHTML = html;
}

function aptFilterResearch() {
  const q = (document.getElementById('apt-research-filter')?.value || '').toLowerCase();
  document.querySelectorAll('.research-row').forEach(r => {
    r.style.display = (!q || (r.getAttribute('data-val')||'').includes(q)) ? '' : 'none';
  });
}

function aptLookupFromTable(value) {
  const input = document.getElementById('apt-ioc-input');
  if (input) input.value = value;
  aptLookupIOC();
}

async function aptLookupIOC() {
  const input = document.getElementById('apt-ioc-input');
  const resultDiv = document.getElementById('apt-lookup-result');
  const typeBadge = document.getElementById('apt-ioc-type-badge');
  if (!input || !resultDiv) return;
  const value = input.value.trim();
  if (!value) return;

  resultDiv.innerHTML = '<div style="text-align:center;padding:20px;color:#484f58"><div class="spinner" style="margin:0 auto 8px"></div>Looking up...</div>';
  if (typeBadge) typeBadge.textContent = '';

  try {
    const resp = await fetch('/api/apt/ioc/lookup', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({value: value, type: 'auto'})
    });
    const data = await resp.json();
    if (data.error) {
      resultDiv.innerHTML = '<div style="color:#da3633;font-size:11px">' + esc(data.error) + '</div>';
      return;
    }
    renderLookupResult(data);
  } catch(e) {
    resultDiv.innerHTML = '<div style="color:#da3633;font-size:11px">Error: ' + esc(e.message) + '</div>';
  }
}

function renderLookupResult(data) {
  const resultDiv = document.getElementById('apt-lookup-result');
  const typeBadge = document.getElementById('apt-ioc-type-badge');
  if (!resultDiv) return;

  const typeColors = {ipv4:'#da3633',domain:'#e3b341',url:'#388bfd',hash_md5:'#a371f7',hash_sha256:'#a371f7',email:'#3fb950',cve:'#f85149',subnet:'#da3633'};
  const col = typeColors[data.type] || '#8b949e';
  if (typeBadge) typeBadge.innerHTML = 'Detected type: <span style="color:' + col + ';font-weight:700">' + esc(data.type.toUpperCase()) + '</span>';

  let html = '';

  // Local DB results
  html += '<div class="lookup-result">';
  html += '<div style="font-size:10px;font-weight:700;color:#e6edf3;margin-bottom:6px">LOCAL DATABASE</div>';
  if (data.local && data.local.found) {
    html += '<div style="font-size:11px;color:#3fb950;margin-bottom:4px">Found in ' + data.local.count + ' message(s)</div>';
    if (data.local.apts.length > 0) {
      html += '<div style="margin-bottom:4px">';
      data.local.apts.forEach(apt => {
        html += '<span style="display:inline-block;font-size:9px;font-weight:700;color:#f85149;background:#f8514918;padding:1px 6px;border-radius:3px;margin:1px 2px">' + esc(apt) + '</span>';
      });
      html += '</div>';
    }
    html += '<div style="font-size:9px;color:#8b949e">Channels: ' + data.local.channels.join(', ') + '</div>';
    html += '<div style="font-size:9px;color:#484f58;margin-top:2px">First: ' + (data.local.first_seen || '').slice(0,10) + ' | Last: ' + (data.local.last_seen || '').slice(0,10) + '</div>';

    // Message snippets
    if (data.local.messages && data.local.messages.length > 0) {
      html += '<div style="margin-top:6px;max-height:120px;overflow-y:auto">';
      data.local.messages.slice(0,5).forEach(m => {
        html += '<div style="font-size:9px;padding:3px 0;border-bottom:1px solid #0d1117;color:#6e7681">';
        html += '<span style="color:#58a6ff">@' + esc(m.channel) + '</span> ';
        html += '<span style="color:#484f58">' + (m.timestamp || '').slice(0,16).replace('T',' ') + '</span><br>';
        html += '<span style="color:#8b949e">' + esc(m.summary_snippet) + '</span>';
        html += '</div>';
      });
      html += '</div>';
    }
  } else {
    html += '<div style="font-size:10px;color:#484f58">Not found in local intelligence database</div>';
  }
  html += '</div>';

  // AbuseIPDB results
  if (data.abuseipdb) {
    const a = data.abuseipdb;
    const score = a.abuseConfidenceScore || 0;
    const scoreClass = score <= 25 ? 'clean' : score <= 70 ? 'suspicious' : 'malicious';
    html += '<div class="lookup-result" style="margin-top:8px">';
    html += '<div style="font-size:10px;font-weight:700;color:#e6edf3;margin-bottom:4px">ABUSEIPDB INTELLIGENCE</div>';
    html += '<div class="abuse-score ' + scoreClass + '">' + score + '%</div>';
    html += '<div style="text-align:center;font-size:9px;color:#6e7681;margin-bottom:8px">Abuse Confidence Score</div>';

    const flagUrl = a.countryCode ? 'https://flagsapi.com/' + a.countryCode + '/flat/24.png' : '';
    html += '<div style="font-size:10px;display:grid;grid-template-columns:70px 1fr;gap:2px 8px;color:#8b949e">';
    html += '<span style="color:#6e7681">Country</span><span>' + (flagUrl ? '<img src="' + flagUrl + '" style="width:14px;height:10px;vertical-align:middle;margin-right:4px">' : '') + esc(a.countryCode || 'N/A') + '</span>';
    html += '<span style="color:#6e7681">ISP</span><span style="word-break:break-word">' + esc(a.isp || 'N/A') + '</span>';
    html += '<span style="color:#6e7681">Domain</span><span>' + esc(a.domain || 'N/A') + '</span>';
    html += '<span style="color:#6e7681">Reports</span><span style="color:' + (a.totalReports > 10 ? '#f85149' : '#8b949e') + '">' + (a.totalReports || 0) + '</span>';
    html += '<span style="color:#6e7681">Last Report</span><span>' + (a.lastReportedAt || 'Never').slice(0,10) + '</span>';
    html += '<span style="color:#6e7681">Usage</span><span>' + esc(a.usageType || 'N/A') + '</span>';
    html += '</div>';
    html += '</div>';
  } else if (data.abuseipdb_error) {
    html += '<div class="lookup-result" style="margin-top:8px">';
    html += '<div style="font-size:10px;font-weight:700;color:#e6edf3;margin-bottom:4px">ABUSEIPDB</div>';
    html += '<div style="font-size:10px;color:#da3633">' + esc(data.abuseipdb_error) + '</div>';
    html += '</div>';
  }

  // Verdict
  if (data.verdict) {
    html += '<div class="verdict-badge ' + data.verdict + '" style="margin-top:10px">' + data.verdict + '</div>';
  }

  resultDiv.innerHTML = html;
}

async function aptAIScan() {
  if (!_selectedAPT) {
    document.getElementById('apt-ai-scan-status').innerHTML = '<span style="color:#e3b341">Select an APT first</span>';
    return;
  }
  const btn = document.getElementById('apt-ai-scan-btn');
  const statusDiv = document.getElementById('apt-ai-scan-status');
  const resultsDiv = document.getElementById('apt-ai-scan-results');
  btn.disabled = true;
  btn.textContent = '⏳ Scanning...';
  statusDiv.innerHTML = '<span style="color:#58a6ff">Running AI deep scan on ' + esc(_selectedAPT) + '...</span>';
  resultsDiv.innerHTML = '';

  try {
    const resp = await fetch('/api/apt/ioc/ai-extract', {
      method: 'POST',
      headers: {'Content-Type': 'application/json'},
      body: JSON.stringify({apt_name: _selectedAPT})
    });
    const data = await resp.json();
    if (data.error) {
      statusDiv.innerHTML = '<span style="color:#da3633">' + esc(data.error) + '</span>';
      btn.disabled = false;
      btn.textContent = '🤖 RUN AI EXTRACTION';
      return;
    }
    statusDiv.innerHTML = '<span style="color:#3fb950">Scanned ' + data.messages_scanned + ' messages (' + data.chunks_processed + ' chunks). Found ' + data.total_found + ' IOCs, ' + data.new_iocs.length + ' new.</span>';

    if (data.new_iocs && data.new_iocs.length > 0) {
      let rhtml = '<div style="font-size:10px;font-weight:700;color:#a371f7;margin:6px 0 4px">NEW IOCs DISCOVERED</div>';
      rhtml += '<div style="max-height:200px;overflow-y:auto">';
      const tc = {ipv4:'#da3633',domain:'#e3b341',url:'#388bfd',hash_md5:'#a371f7',hash_sha256:'#a371f7',cve:'#f85149',email:'#3fb950'};
      data.new_iocs.forEach(ioc => {
        const c = tc[ioc.type] || '#8b949e';
        rhtml += '<div style="padding:3px 0;border-bottom:1px solid #0d1117;font-size:9px">';
        rhtml += '<span style="font-weight:700;color:' + c + ';background:' + c + '18;padding:1px 4px;border-radius:2px;text-transform:uppercase;font-size:8px">' + esc(ioc.type) + '</span> ';
        rhtml += '<span style="font-family:monospace;color:#e6edf3">' + esc(ioc.value) + '</span>';
        if (ioc.context) rhtml += '<br><span style="color:#6e7681">' + esc(ioc.context) + '</span>';
        rhtml += '</div>';
      });
      rhtml += '</div>';
      resultsDiv.innerHTML = rhtml;
    }
  } catch(e) {
    statusDiv.innerHTML = '<span style="color:#da3633">Error: ' + esc(e.message) + '</span>';
  }
  btn.disabled = false;
  btn.textContent = '🤖 RUN AI EXTRACTION';
}

// ═══════════════════════════ BLOCKLIST JS ═══════════════════════════════

let _blocklistData = null;
let _blDebounce = null;

async function loadBlocklist() {
  clearTimeout(_blDebounce);
  _blDebounce = setTimeout(_doLoadBlocklist, 150);
}

async function _doLoadBlocklist() {
  const aptF = document.getElementById('bl-apt-filter')?.value || '';
  const typeF = document.getElementById('bl-type-filter')?.value || '';
  const verdictF = document.getElementById('bl-verdict-filter')?.value || '';
  const search = document.getElementById('bl-search')?.value || '';
  const params = new URLSearchParams();
  if (aptF) params.set('apt', aptF);
  if (typeF) params.set('type', typeF);
  if (verdictF) params.set('verdict', verdictF);
  if (search) params.set('q', search);

  try {
    const resp = await fetch('/api/blocklist?' + params.toString());
    const data = await resp.json();
    _blocklistData = data;
    renderBlocklist(data);
    _populateAPTFilter(data.apt_summary);
  } catch(e) {
    const tbody = document.getElementById('bl-tbody');
    if (tbody) tbody.innerHTML = '<tr><td colspan="9" style="color:#da3633;padding:20px">Error: ' + esc(e.message) + '</td></tr>';
  }
}

function _populateAPTFilter(summary) {
  const sel = document.getElementById('bl-apt-filter');
  if (!sel) return;
  const cur = sel.value;
  while (sel.options.length > 1) sel.remove(1);
  Object.keys(summary).sort().forEach(name => {
    const opt = document.createElement('option');
    opt.value = name;
    opt.textContent = name + ' (' + summary[name].total + ')';
    sel.add(opt);
  });
  sel.value = cur;
}

function renderBlocklist(data) {
  const tbody = document.getElementById('bl-tbody');
  const statsDiv = document.getElementById('bl-stats');
  if (!tbody) return;

  const summary = data.apt_summary || {};
  const aptCount = Object.keys(summary).length;
  const totalMal = Object.values(summary).reduce((s,a) => s + (a.malicious||0), 0);
  const totalSus = Object.values(summary).reduce((s,a) => s + (a.suspicious||0), 0);

  if (statsDiv) {
    statsDiv.innerHTML =
      '<span style="color:#8b949e">APT Groups: <b style="color:#58a6ff">' + aptCount + '</b></span>' +
      '<span style="color:#da3633;font-weight:700">' + totalMal + ' MALICIOUS</span>' +
      '<span style="color:#e3b341;font-weight:700">' + totalSus + ' SUSPICIOUS</span>' +
      '<span style="color:#8b949e">Showing: <b style="color:#e6edf3">' + data.total + '</b></span>';
  }

  const iocs = data.iocs || [];
  if (iocs.length === 0) {
    tbody.innerHTML = '<tr><td colspan="9" style="text-align:center;padding:40px;color:#484f58">No IOCs found. Background research auto-populates this — check back in a few minutes.</td></tr>';
    return;
  }

  const tc = {ipv4:'#da3633',domain:'#e3b341',url:'#388bfd',hash_md5:'#a371f7',hash_sha256:'#a371f7',cve:'#f85149'};
  const vc = {MALICIOUS:'#da3633',SUSPICIOUS:'#e3b341',CLEAN:'#3fb950',UNVERIFIED:'#484f58'};

  let html = '';
  iocs.forEach(ioc => {
    const tCol = tc[ioc.type] || '#8b949e';
    const vCol = vc[ioc.abuse_verdict] || '#8b949e';
    // Truncate APT names: show first 2, then "+N more"
    const aptFull = ioc.apt || '';
    const aptParts = aptFull.split(', ');
    const aptShort = aptParts.length <= 2 ? aptFull : aptParts.slice(0,2).join(', ') + ' +' + (aptParts.length-2);
    const firstApt = aptParts[0] || '';
    html += '<tr style="border-bottom:1px solid #161b22">';
    html += '<td style="padding:4px 8px;max-width:140px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;color:#58a6ff;font-size:9px;font-weight:600;cursor:pointer" title="' + esc(aptFull) + '" onclick="switchMainTab(\'apt\');setTimeout(()=>selectAPT(\'' + esc(firstApt.replace(/'/g,"\\'")) + '\'),200)">' + esc(aptShort) + '</td>';
    html += '<td style="padding:4px 6px"><span style="font-size:8px;font-weight:700;color:' + tCol + ';background:' + tCol + '18;padding:1px 5px;border-radius:2px;text-transform:uppercase">' + esc(ioc.type) + '</span></td>';
    html += '<td style="padding:4px 6px;font-family:monospace;color:#e6edf3;white-space:nowrap">' + esc(ioc.value) + '</td>';
    html += '<td style="padding:4px 6px;text-align:center"><span style="font-size:8px;font-weight:700;color:' + vCol + ';background:' + vCol + '18;padding:1px 4px;border-radius:2px">' + (ioc.abuse_verdict||'--') + '</span></td>';
    html += '<td style="padding:4px 6px;text-align:center;color:' + vCol + ';font-weight:700;font-size:10px">' + (ioc.abuse_score >= 0 ? ioc.abuse_score + '%' : '--') + '</td>';
    html += '<td style="padding:4px 6px;font-size:9px;color:#8b949e">' + esc(ioc.abuse_country||'') + '</td>';
    html += '<td style="padding:4px 6px;font-size:8px;color:#6e7681">' + esc(ioc.source||'') + '</td>';
    html += '<td style="padding:4px 6px;font-size:9px;color:#6e7681;max-width:180px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap" title="' + esc(ioc.context||'') + '">' + esc(ioc.context||'') + '</td>';
    html += '<td style="padding:4px"><button onclick="navigator.clipboard.writeText(\'' + esc(ioc.value.replace(/'/g,"\\'")) + '\')" style="background:none;border:1px solid #21262d;color:#8b949e;padding:2px 5px;border-radius:3px;cursor:pointer;font-size:9px">copy</button></td>';
    html += '</tr>';
  });
  tbody.innerHTML = html;
}

function copyBlocklistIPs() {
  if (!_blocklistData) return;
  const ips = (_blocklistData.iocs || [])
    .filter(i => i.type === 'ipv4' && i.abuse_verdict !== 'CLEAN')
    .map(i => i.value);
  navigator.clipboard.writeText(ips.join('\\n'));
  alert('Copied ' + ips.length + ' IP addresses to clipboard.');
}

async function generateReport(btn) {
  const orig = btn.textContent;
  btn.disabled = true;
  btn.textContent = 'Generating...';
  btn.style.opacity = '0.6';
  try {
    const resp = await fetch('/api/blocklist/report');
    if (!resp.ok) throw new Error('Report generation failed');
    const blob = await resp.blob();
    const url = URL.createObjectURL(blob);
    const a = document.createElement('a');
    a.href = url;
    a.download = resp.headers.get('Content-Disposition')?.split('filename=')[1] || 'ScanWave_Report.docx';
    document.body.appendChild(a);
    a.click();
    a.remove();
    URL.revokeObjectURL(url);
  } catch(e) {
    alert('Error generating report: ' + e.message);
  } finally {
    btn.disabled = false;
    btn.textContent = orig;
    btn.style.opacity = '1';
  }
}

</script>
</body>
</html>"""


@app.route("/")
def index():
    return Response(HTML, mimetype="text/html", headers={
        "Cache-Control": "no-cache, no-store, must-revalidate",
        "Pragma": "no-cache",
        "Expires": "0",
    })


if __name__ == "__main__":
    print("=" * 60)
    print("  Scanwave CyberIntel Platform")
    print("  http://localhost:5000")
    print("=" * 60)
    # Start auto-research background thread
    _research_thread = threading.Thread(target=_auto_research_loop, daemon=True)
    _research_thread.start()
    print("[RESEARCH] Auto-research background thread started")
    app.run(debug=False, host="0.0.0.0", port=5000, threaded=True)
