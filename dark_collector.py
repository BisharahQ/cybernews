#!/usr/bin/env python3
"""
DARK COLLECTOR — Jordan Cyber Intel Platform
=============================================
Multi-source OSINT and dark web collection engine.
Runs as orchestrator component #4 alongside viewer, monitor, and ai_agent.

7 COLLECTION LOOPS:
  Loop 1 — PASTE SCRAPER        Pastebin + Rentry monitoring (every 60s)
  Loop 2 — BREACH MONITOR       HIBP + DeHashed credential checks (every 6h)
  Loop 3 — CERTSTREAM WATCHER   Real-time CT log monitoring (continuous)
  Loop 4 — DOMAIN SQUAT SCANNER dnstwist against .jo domains (every 12h)
  Loop 5 — GITHUB MONITOR       Code search dorks for Jordan targets (every 2h)
  Loop 6 — RANSOM LEAK TRACKER  RansomLook API + ransomwatch feeds (every 1h)
  Loop 7 — DARK WEB CRAWLER     Tor-based .onion crawling (continuous, 3s/req)

AI ANALYSIS PIPELINE:
  Every finding goes through GPT triage (relevance, classification, severity).
  HIGH/CRITICAL findings get contextualization and verification passes.
  Daily digest summarizes 24h of dark collection.

SETUP:
  pip install requests[socks] PySocks stem beautifulsoup4 certstream dnstwist pyhibp
  Optional: Install Tor service (apt install tor / choco install tor)
  Set env vars in .env:
    OPENAI_API_KEY=sk-...           (required for AI analysis)
    GITHUB_TOKEN=ghp_...            (optional, increases rate limits)
    PASTEBIN_API_KEY=...            (optional, for Pastebin PRO scraping)
    HIBP_API_KEY=...                (optional, for HIBP domain search)
    DEHASHED_API_KEY=...            (optional, for DeHashed)
    DEHASHED_EMAIL=...              (optional, for DeHashed)

USAGE:
  python dark_collector.py          (runs all loops forever)
"""

import os
import re
import json
import time
import hashlib
import threading
import logging
import random
from pathlib import Path
from datetime import datetime, timezone, timedelta
from collections import defaultdict
from urllib.parse import urlparse

# ── .env loader ───────────────────────────────────────────────────────────────
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

# ── httpx/openai compat patch ─────────────────────────────────────────────────
try:
    import httpx as _httpx
    _orig = _httpx.Client.__init__
    def _patched(self, *a, **kw):
        kw.pop("proxies", None); _orig(self, *a, **kw)
    _httpx.Client.__init__ = _patched
    _orig_a = _httpx.AsyncClient.__init__
    def _patched_a(self, *a, **kw):
        kw.pop("proxies", None); _orig_a(self, *a, **kw)
    _httpx.AsyncClient.__init__ = _patched_a
except Exception:
    pass

# ── Optional imports (graceful degradation) ───────────────────────────────────
import requests
from bs4 import BeautifulSoup

_HAS_CERTSTREAM = False
try:
    import certstream
    _HAS_CERTSTREAM = True
except ImportError:
    pass

_HAS_DNSTWIST = False
try:
    import dnstwist as _dnstwist_mod
    _HAS_DNSTWIST = True
except ImportError:
    pass

_HAS_STEM = False
try:
    from stem import Signal
    from stem.control import Controller
    _HAS_STEM = True
except ImportError:
    pass

_HAS_OPENAI = False
try:
    from openai import OpenAI
    _HAS_OPENAI = True
except ImportError:
    pass

_HAS_FEEDPARSER = False
try:
    import feedparser
    _HAS_FEEDPARSER = True
except ImportError:
    pass

# ── Paths ─────────────────────────────────────────────────────────────────────
OUTPUT_DIR         = Path("./telegram_intel")
DARK_INTEL_FILE    = OUTPUT_DIR / "dark_intel.jsonl"
STATE_FILE         = OUTPUT_DIR / "dark_collector_state.json"
KEYWORDS_FILE      = OUTPUT_DIR / "dark_keywords.json"
ONION_TARGETS_FILE = OUTPUT_DIR / "onion_targets.json"
DOMAIN_WATCH_FILE  = OUTPUT_DIR / "domain_watchlist.json"
DAILY_DIGEST_FILE  = OUTPUT_DIR / "daily_dark_digest.json"
COLLECTOR_LOG      = OUTPUT_DIR / "dark_collector.log"
OUTPUT_DIR.mkdir(exist_ok=True)

# ── Logging ───────────────────────────────────────────────────────────────────
import sys as _sys
try:
    if hasattr(_sys.stdout, "reconfigure"):
        _sys.stdout.reconfigure(encoding="utf-8", errors="replace")
except Exception:
    pass

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [DARK] %(message)s",
    handlers=[
        logging.FileHandler(COLLECTOR_LOG, encoding="utf-8"),
        logging.StreamHandler(_sys.stdout),
    ]
)
log = logging.getLogger("DARK")

# ── State management ──────────────────────────────────────────────────────────
_state_lock = threading.Lock()

def _load_state():
    if STATE_FILE.exists():
        try:
            return json.loads(STATE_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    return {
        "seen_content_hashes": [],   # SHA-256 hashes for dedup (max 50000)
        "seen_paste_keys": [],       # Pastebin paste keys already scanned
        "seen_github_results": [],   # repo:path combos already seen
        "last_paste_scan": None,
        "last_breach_scan": None,
        "last_dnstwist_scan": None,
        "last_github_scan": None,
        "last_ransom_scan": None,
        "last_dark_crawl": None,
        "last_daily_digest": None,
        "last_ahmia_search": None,
        "findings_total": 0,
        "findings_by_source": {},
        "false_positives": 0,
        "tor_circuits_rotated": 0,
    }

def _save_state(state):
    with _state_lock:
        # Cap dedup lists to prevent unbounded growth
        for key in ("seen_content_hashes", "seen_paste_keys", "seen_github_results"):
            if len(state.get(key, [])) > 50000:
                state[key] = state[key][-40000:]  # Keep most recent
        STATE_FILE.write_text(json.dumps(state, indent=2, ensure_ascii=False), encoding="utf-8")


# ── Keywords ──────────────────────────────────────────────────────────────────
def _load_keywords():
    """Load Jordan-specific keywords for dark source scanning."""
    if KEYWORDS_FILE.exists():
        try:
            return json.loads(KEYWORDS_FILE.read_text(encoding="utf-8"))
        except Exception:
            pass
    # Default keywords if file doesn't exist
    return _default_keywords()

def _default_keywords():
    return {
        "government": [
            "gov.jo", "mod.gov.jo", "moi.gov.jo", "cbj.gov.jo",
            "jordan government", "jordanian government",
            "hashemite kingdom", "royal court jordan",
            "gid.gov.jo", "nit.gov.jo",
        ],
        "telecom": [
            "zain.jo", "orange.jo", "umniah.jo", "jordantelecom",
            "jordan telecom", "umniah", "zain jordan",
        ],
        "banking": [
            "arabbank.com.jo", "arabbank", "arab bank jordan",
            "hbtf.com.jo", "housing bank jordan",
            "abj.com.jo", "ahli bank jordan",
            "central bank jordan", "cbj",
            "cairo amman bank", "bank of jordan",
        ],
        "military": [
            "jaf.mil.jo", "jordanian armed forces", "jordan military",
            "royal guard jordan", "jordan special forces",
            "jordan intelligence", "gid jordan",
        ],
        "infrastructure": [
            "nepco.com.jo", "jordan electric", "jordan water",
            "amman airport", "royal jordanian", "rj.com",
            "jordan ports", "aqaba port",
        ],
        "hacktivist": [
            "opjordan", "#opjordan", "op jordan",
            "jordan hack", "jordan ddos", "jordan deface",
            "jordan breach", "jordan leak",
        ],
        "threat_groups": [
            "dienet", "rippersec", "handala", "cyberfattah",
            "fatemiyoun", "313 team", "cyber av3ngers",
            "killnet", "noname057", "anonymous sudan",
            "lulzsec", "dark storm", "holy league",
            "mr hamza", "golden falcon", "stucx team",
            "mysterious team", "keymous", "sylhet gang",
            "islamic hacker army", "arabian ghosts",
        ],
        "generic": [
            "jordan", "amman", "hashemite", "petra", ".jo",
        ],
    }


# ── IOC Extraction ────────────────────────────────────────────────────────────
_IP_RE = re.compile(r'\b(?:\d{1,3}\.){3}\d{1,3}\b')
_DOMAIN_RE = re.compile(r'\b(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+(?:com|net|org|io|gov|mil|edu|jo|ir|iq|ps|sy|lb|my|id|bd|tr|ru|uk|de|fr|info|biz|xyz|top|cc|me)\b', re.I)
_HASH_MD5 = re.compile(r'\b[a-fA-F0-9]{32}\b')
_HASH_SHA1 = re.compile(r'\b[a-fA-F0-9]{40}\b')
_HASH_SHA256 = re.compile(r'\b[a-fA-F0-9]{64}\b')
_EMAIL_RE = re.compile(r'\b[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}\b')
_URL_RE = re.compile(r'https?://[^\s<>"\']+', re.I)

def _extract_iocs(text):
    """Extract IOCs from text content."""
    return {
        "ips": list(set(_IP_RE.findall(text)))[:50],
        "domains": list(set(_DOMAIN_RE.findall(text)))[:50],
        "emails": list(set(_EMAIL_RE.findall(text)))[:50],
        "urls": list(set(_URL_RE.findall(text)))[:50],
        "hashes": {
            "md5": list(set(_HASH_MD5.findall(text)))[:20],
            "sha1": list(set(_HASH_SHA1.findall(text)))[:20],
            "sha256": list(set(_HASH_SHA256.findall(text)))[:20],
        },
    }


# ── Content Dedup ─────────────────────────────────────────────────────────────
def _content_hash(text):
    """SHA-256 hash of normalized content for deduplication."""
    normalized = re.sub(r'\s+', ' ', text[:5000].lower().strip())
    return hashlib.sha256(normalized.encode("utf-8")).hexdigest()

def _is_seen(state, content_text):
    """Check if content was already seen."""
    h = _content_hash(content_text)
    if h in state.get("seen_content_hashes", []):
        return True
    state.setdefault("seen_content_hashes", []).append(h)
    return False


# ── JSONL Writer ──────────────────────────────────────────────────────────────
_write_lock = threading.Lock()

def _write_finding(finding):
    """Append a finding to dark_intel.jsonl (thread-safe)."""
    with _write_lock:
        with open(DARK_INTEL_FILE, "a", encoding="utf-8") as f:
            f.write(json.dumps(finding, ensure_ascii=False) + "\n")


# ── OpenAI Helper ─────────────────────────────────────────────────────────────
def _ai_call(system_prompt, user_content, model="gpt-4o-mini", max_tokens=1200):
    """Call OpenAI GPT with error handling. Returns parsed dict or None."""
    if not _HAS_OPENAI or not os.environ.get("OPENAI_API_KEY"):
        return None
    try:
        client = OpenAI(api_key=os.environ["OPENAI_API_KEY"])
        r = client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
            temperature=0.2,
            max_tokens=max_tokens,
            response_format={"type": "json_object"},
        )
        return json.loads(r.choices[0].message.content)
    except Exception as e:
        log.warning(f"AI call failed: {e}")
        return None


# ── AI System Prompts ─────────────────────────────────────────────────────────

AI_TRIAGE_SYSTEM = """You are a cyber threat intelligence analyst at Jordan's national CERT.
You are analyzing content scraped from an OSINT/dark web source.

Analyze and respond in JSON with these fields:
{
  "relevance_score": 0-100 (is this actually relevant to Jordan/Jordanian infrastructure?),
  "threat_type": "CREDENTIAL_LEAK|DATA_BREACH|ATTACK_PLANNING|TOOL_DISTRIBUTION|RANSOMWARE_VICTIM|PHISHING_INFRASTRUCTURE|ACTOR_DISCUSSION|INTELLIGENCE_VALUE|FALSE_POSITIVE",
  "severity": "CRITICAL|HIGH|MEDIUM|LOW",
  "data_freshness": "description of whether this is new/active or recycled old content",
  "actionable_intel": ["list of specific actionable items extracted"],
  "recommended_action": "what the SOC team should do with this",
  "summary": "2-3 sentence summary of the finding"
}

IMPORTANT:
- "Jordan" as a person's name = FALSE_POSITIVE (score 0)
- Generic mentions with no Jordanian org/IP/domain specifics = LOW relevance
- Specific Jordanian org names, domains, IPs = HIGH relevance
- Active credential dumps with .jo emails = CRITICAL
- Always respond in English."""

AI_CONTEXT_SYSTEM = """You are analyzing a HIGH/CRITICAL dark web intelligence finding.
Cross-reference with the known threat landscape targeting Jordan.

Known active threat groups: DieNet, RipperSec, Handala, Cyber Av3ngers, Fatemiyoun,
313 Team, Mr Hamza, Dark Storm Team, Holy League, Anonymous Islamic, CyberFattah,
LulzSec Muslims, Nation of Saviours, Arabian Ghosts, Sylhet Gang, Stucx Team.

Respond in JSON:
{
  "actor_attribution": "which known group is likely behind this and why",
  "campaign_linkage": "does this connect to any known campaign or recent attacks",
  "infrastructure_overlap": "any IOC overlap with known threat actor infrastructure",
  "predictive_assessment": "what this finding suggests about upcoming threats",
  "confidence": 0-100
}

Always respond in English."""

AI_VERIFY_SYSTEM = """You are a breach data verification specialist.
Analyze this claimed data leak and assess its authenticity.

Respond in JSON:
{
  "verdict": "LIKELY_AUTHENTIC|LIKELY_RECYCLED|LIKELY_FABRICATED|INSUFFICIENT_DATA",
  "reasoning": "detailed explanation of your assessment",
  "freshness_indicators": ["list of indicators you found"],
  "known_breach_matches": ["any known breaches this might be recycled from"],
  "confidence": 0-100
}

Key checks:
- Password hashing algorithm (bcrypt=newer, MD5=older, plaintext=suspicious)
- Date/timestamp indicators within the data
- Round numbers ("exactly 10,000 records") are suspicious
- Check if data structure matches claimed source type
Always respond in English."""

AI_DAILY_DIGEST_SYSTEM = """You are writing a classified intelligence briefing for Jordan's
national cyber defense team. Summarize the last 24 hours of multi-source dark collection.

Respond in JSON:
{
  "executive_summary": "3-5 sentences overview",
  "critical_findings": [{"title": "", "detail": "", "action_required": ""}],
  "notable_patterns": ["trends, emerging threats, actor movements"],
  "data_quality": {"false_positive_rate": "X%", "verified_count": 0, "assessment": ""},
  "collection_gaps": ["what we're NOT seeing that we should be"],
  "recommended_adjustments": ["new keywords, targets, or strategy changes"]
}

Write in concise military intelligence briefing style. Always respond in English."""

AI_SEARCH_EVOLVE_SYSTEM = """You are a dark web intelligence analyst reviewing collection results.
Based on the findings summary, suggest improvements to our collection strategy.

Respond in JSON:
{
  "new_search_terms": ["new keywords to add to our scanning"],
  "new_onion_targets": [{"url": "", "description": "", "rationale": ""}],
  "keyword_refinements": {"remove": ["false-positive-heavy keywords"], "add": ["missing keywords"]},
  "actor_pivots": [{"actor": "", "new_platforms": "", "rationale": ""}],
  "emerging_patterns": ["trends that suggest shifting tactics"]
}

Always respond in English."""


# ── Keyword Matching ──────────────────────────────────────────────────────────
def _scan_text(text, keywords_dict):
    """Scan text against keyword dictionary. Returns list of matched keywords."""
    text_lower = text.lower()
    matches = []
    for category, kw_list in keywords_dict.items():
        for kw in kw_list:
            if kw.lower() in text_lower:
                matches.append(kw)
    return list(set(matches))


def _assess_severity(matches, source_type):
    """Assess severity based on keyword matches and source type."""
    if not matches:
        return "LOW"
    has_gov = any(kw for kw in matches if "gov" in kw.lower() or "mil" in kw.lower())
    has_cred = any(kw for kw in matches if "password" in kw.lower() or "credential" in kw.lower() or "leak" in kw.lower())
    if source_type in ("darkweb_ransomware_dls",) and has_gov:
        return "CRITICAL"
    if has_gov and has_cred:
        return "CRITICAL"
    if has_gov or source_type.startswith("darkweb"):
        return "HIGH"
    if len(matches) >= 3:
        return "HIGH"
    if len(matches) >= 2:
        return "MEDIUM"
    return "LOW"


# ── AI Analysis Pipeline ─────────────────────────────────────────────────────
def _ai_analyze_finding(finding, raw_text):
    """Run AI analysis pipeline on a finding. Modifies finding in-place."""
    if not _HAS_OPENAI or not os.environ.get("OPENAI_API_KEY"):
        return finding

    # Step 1: Triage (always, GPT-4o-mini)
    triage = _ai_call(
        AI_TRIAGE_SYSTEM,
        f"Source: {finding.get('source','?')}\n"
        f"URL: {finding.get('raw_url','?')}\n"
        f"Matched keywords: {finding.get('matched_keywords',[])}\n"
        f"Content:\n{raw_text[:3000]}",
        model="gpt-4o-mini", max_tokens=800,
    )
    if triage:
        finding["ai_triage"] = triage
        finding["severity"] = triage.get("severity", finding.get("severity", "MEDIUM"))
        finding["confidence"] = triage.get("relevance_score", finding.get("confidence", 50))
        if triage.get("threat_type") == "FALSE_POSITIVE":
            finding["severity"] = "FALSE_POSITIVE"
            log.info(f"  AI: FALSE_POSITIVE — {triage.get('summary','')[:80]}")
            return finding

    # Step 2: Contextualization (HIGH/CRITICAL only, GPT-4o)
    if finding.get("severity") in ("CRITICAL", "HIGH"):
        context = _ai_call(
            AI_CONTEXT_SYSTEM,
            f"Finding: {json.dumps(triage or {}, ensure_ascii=False)}\n"
            f"Raw content:\n{raw_text[:4000]}",
            model="gpt-4o", max_tokens=800,
        )
        if context:
            finding["ai_context"] = context

    # Step 3: Fake data check (credential leaks/breaches only)
    threat_type = (triage or {}).get("threat_type", "")
    if threat_type in ("CREDENTIAL_LEAK", "DATA_BREACH"):
        verification = _ai_call(
            AI_VERIFY_SYSTEM,
            f"Claimed breach/leak:\n{raw_text[:4000]}",
            model="gpt-4o-mini", max_tokens=600,
        )
        if verification:
            finding["ai_verification"] = verification
            finding["verified"] = verification.get("verdict") == "LIKELY_AUTHENTIC"

    return finding


# ═══════════════════════════════════════════════════════════════════════════════
# LOOP 1 — PASTE SCRAPER
# ═══════════════════════════════════════════════════════════════════════════════
def loop_paste_scraper(state):
    """Monitor Pastebin + other paste sites for Jordan-relevant content."""
    log.info("[L1-Paste] Starting paste site monitoring")
    keywords = _load_keywords()

    while True:
        try:
            api_key = os.environ.get("PASTEBIN_API_KEY", "")

            if api_key:
                # Pastebin PRO Scraping API
                try:
                    resp = requests.get(
                        "https://scrape.pastebin.com/api_scraping.php?limit=250",
                        timeout=15,
                    )
                    if resp.status_code == 200:
                        pastes = resp.json() if resp.text.startswith("[") else []
                        new_count = 0
                        for paste in pastes:
                            paste_key = paste.get("key", "")
                            if paste_key in state.get("seen_paste_keys", []):
                                continue
                            state.setdefault("seen_paste_keys", []).append(paste_key)

                            # Fetch paste content
                            try:
                                content_resp = requests.get(
                                    f"https://scrape.pastebin.com/api_scrape_item.php?i={paste_key}",
                                    timeout=10,
                                )
                                if content_resp.status_code != 200:
                                    continue
                                content = content_resp.text
                            except Exception:
                                continue

                            matches = _scan_text(content, keywords)
                            if not matches:
                                continue
                            if _is_seen(state, content):
                                continue

                            finding = {
                                "source": "pastebin",
                                "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                                "severity": _assess_severity(matches, "pastebin"),
                                "title": f"Jordan-related paste: {paste.get('title','untitled')[:80]}",
                                "description": content[:500],
                                "raw_url": f"https://pastebin.com/{paste_key}",
                                "iocs": _extract_iocs(content),
                                "matched_keywords": matches,
                                "confidence": min(len(matches) * 20, 100),
                                "verified": False,
                                "tags": ["paste", "pastebin"],
                            }

                            # AI analysis
                            finding = _ai_analyze_finding(finding, content)
                            if finding.get("severity") != "FALSE_POSITIVE":
                                _write_finding(finding)
                                new_count += 1
                                state["findings_total"] = state.get("findings_total", 0) + 1
                                state.setdefault("findings_by_source", {})["pastebin"] = \
                                    state["findings_by_source"].get("pastebin", 0) + 1
                                log.info(f"[L1-Paste] FINDING: {finding['severity']} — {finding['title'][:60]}")
                            else:
                                state["false_positives"] = state.get("false_positives", 0) + 1

                            time.sleep(1)  # Rate limit: 1 req/sec

                        if new_count:
                            log.info(f"[L1-Paste] Scanned {len(pastes)} pastes, {new_count} new findings")
                except Exception as e:
                    log.warning(f"[L1-Paste] Pastebin API error: {e}")

            # Free paste scraping: monitor paste.ee recent + dpaste recent + pastehunter
            free_paste_sources = [
                ("https://api.paste.ee/v1/pastes?limit=50&order=date", "paste.ee"),
                ("https://dpaste.org/api/?format=json", "dpaste"),
            ]
            for api_url, src_name in free_paste_sources:
                try:
                    resp = requests.get(api_url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
                    if resp.status_code == 200:
                        try:
                            data = resp.json()
                            # Handle different formats
                            items = data if isinstance(data, list) else data.get("data", data.get("results", []))
                            if isinstance(items, list):
                                for item in items[:30]:
                                    content = str(item.get("raw", item.get("content", "")))
                                    if not content:
                                        continue
                                    matches = _scan_text(content, keywords)
                                    if matches and not _is_seen(state, content):
                                        finding = {
                                            "source": src_name,
                                            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                                            "severity": _assess_severity(matches, "paste"),
                                            "title": f"Jordan-related paste on {src_name}",
                                            "description": content[:500],
                                            "raw_url": api_url,
                                            "iocs": _extract_iocs(content),
                                            "matched_keywords": matches,
                                            "confidence": min(len(matches) * 20, 100),
                                            "verified": False,
                                            "tags": ["paste", src_name],
                                        }
                                        finding = _ai_analyze_finding(finding, content)
                                        if finding.get("severity") != "FALSE_POSITIVE":
                                            _write_finding(finding)
                                            state["findings_total"] = state.get("findings_total", 0) + 1
                                            log.info(f"[L1-Paste] {src_name} FINDING: {finding['title'][:60]}")
                        except (json.JSONDecodeError, ValueError):
                            pass
                except Exception as e:
                    log.debug(f"[L1-Paste] {src_name} error: {e}")
                time.sleep(2)

            # Scan clearnet leak sites and threat intel feeds directly
            clearnet_intel_urls = [
                ("https://www.ransomlook.io/recent.json", "ransomlook_clearnet"),
                ("https://raw.githubusercontent.com/joshhighet/ransomwatch/main/posts.json", "ransomwatch_feed"),
            ]
            for url, src_name in clearnet_intel_urls:
                try:
                    resp = requests.get(url, timeout=15, headers={"User-Agent": "Mozilla/5.0"})
                    if resp.status_code == 200 and resp.text.startswith(("[", "{")):
                        content = resp.text
                        matches = _scan_text(content, keywords)
                        if matches and not _is_seen(state, content[:5000]):
                            finding = {
                                "source": src_name,
                                "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                                "severity": _assess_severity(matches, "ransomleak"),
                                "title": f"Intel feed match ({src_name}): {', '.join(matches[:3])}",
                                "description": content[:500],
                                "raw_url": url,
                                "iocs": _extract_iocs(content),
                                "matched_keywords": matches,
                                "confidence": min(len(matches) * 15, 80),
                                "verified": False,
                                "tags": ["intel_feed", src_name],
                            }
                            finding = _ai_analyze_finding(finding, content[:3000])
                            if finding.get("severity") != "FALSE_POSITIVE":
                                _write_finding(finding)
                                state["findings_total"] = state.get("findings_total", 0) + 1
                except Exception as e:
                    log.debug(f"[L1-Paste] {src_name} error: {e}")
                time.sleep(2)

            # Also check Rentry for known threat actor pages (no API — just fetch known URLs)
            rentry_urls = [
                "https://rentry.co/opjordan",
                "https://rentry.co/dienet",
                "https://rentry.co/rippersec",
                "https://rentry.co/handala",
                "https://rentry.co/jordan-hack",
            ]
            for url in rentry_urls:
                try:
                    resp = requests.get(url, timeout=10, headers={"User-Agent": "Mozilla/5.0"})
                    if resp.status_code == 200 and len(resp.text) > 100:
                        matches = _scan_text(resp.text, keywords)
                        if matches and not _is_seen(state, resp.text):
                            soup = BeautifulSoup(resp.text, "html.parser")
                            text = soup.get_text(separator=" ", strip=True)
                            finding = {
                                "source": "rentry",
                                "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                                "severity": _assess_severity(matches, "rentry"),
                                "title": f"Jordan-related Rentry page: {url}",
                                "description": text[:500],
                                "raw_url": url,
                                "iocs": _extract_iocs(text),
                                "matched_keywords": matches,
                                "confidence": min(len(matches) * 15, 100),
                                "verified": False,
                                "tags": ["paste", "rentry"],
                            }
                            finding = _ai_analyze_finding(finding, text)
                            if finding.get("severity") != "FALSE_POSITIVE":
                                _write_finding(finding)
                                state["findings_total"] = state.get("findings_total", 0) + 1
                except Exception:
                    pass
                time.sleep(2)

            state["last_paste_scan"] = datetime.now(timezone.utc).isoformat()
            _save_state(state)

        except Exception as e:
            log.error(f"[L1-Paste] Loop error: {e}")

        time.sleep(60)  # Poll every 60 seconds


# ═══════════════════════════════════════════════════════════════════════════════
# LOOP 2 — BREACH MONITOR
# ═══════════════════════════════════════════════════════════════════════════════
def loop_breach_monitor(state):
    """Monitor HIBP and DeHashed for Jordanian credential exposures."""
    log.info("[L2-Breach] Starting breach monitoring")

    # Domains to monitor for credential exposures
    MONITORED_DOMAINS = [
        "gov.jo", "mod.gov.jo", "moi.gov.jo", "cbj.gov.jo",
        "arabbank.com.jo", "hbtf.com.jo", "abj.com.jo",
        "zain.jo", "orange.jo", "umniah.jo",
        "rj.com", "ju.edu.jo", "just.edu.jo",
    ]

    while True:
        try:
            hibp_key = os.environ.get("HIBP_API_KEY", "")

            # ── HIBP Breach Check ──
            if hibp_key:
                headers = {
                    "hibp-api-key": hibp_key,
                    "user-agent": "JordanCyberIntelPlatform",
                }
                for domain in MONITORED_DOMAINS:
                    try:
                        resp = requests.get(
                            f"https://haveibeenpwned.com/api/v3/breaches",
                            headers=headers, timeout=15,
                        )
                        if resp.status_code == 200:
                            breaches = resp.json()
                            # Filter for recent breaches (last 30 days)
                            cutoff = (datetime.now(timezone.utc) - timedelta(days=30)).isoformat()[:10]
                            recent = [b for b in breaches if b.get("AddedDate", "") >= cutoff]
                            for breach in recent:
                                breach_name = breach.get("Name", "unknown")
                                finding = {
                                    "source": "hibp",
                                    "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                                    "severity": "HIGH",
                                    "title": f"HIBP: New breach may contain {domain} credentials — {breach_name}",
                                    "description": breach.get("Description", "")[:500],
                                    "raw_url": f"https://haveibeenpwned.com/api/v3/breach/{breach_name}",
                                    "iocs": {"domains": [domain]},
                                    "matched_keywords": [domain],
                                    "confidence": 70,
                                    "verified": False,
                                    "tags": ["breach", "hibp", "credentials"],
                                    "breach_details": {
                                        "name": breach_name,
                                        "domain": domain,
                                        "breach_date": breach.get("BreachDate"),
                                        "pwn_count": breach.get("PwnCount"),
                                        "data_classes": breach.get("DataClasses", []),
                                    },
                                }
                                if not _is_seen(state, f"hibp_{breach_name}_{domain}"):
                                    _write_finding(finding)
                                    state["findings_total"] = state.get("findings_total", 0) + 1
                                    log.info(f"[L2-Breach] HIBP finding: {breach_name} for {domain}")
                        time.sleep(2)  # HIBP rate limit: 10 req/min
                    except Exception as e:
                        log.warning(f"[L2-Breach] HIBP error for {domain}: {e}")
                        time.sleep(2)

            # ── DeHashed Check ──
            dehashed_key = os.environ.get("DEHASHED_API_KEY", "")
            dehashed_email = os.environ.get("DEHASHED_EMAIL", "")

            if dehashed_key and dehashed_email:
                for domain in MONITORED_DOMAINS[:5]:  # Top 5 most critical
                    try:
                        resp = requests.get(
                            "https://api.dehashed.com/search",
                            params={"query": f"domain:{domain}", "size": 100},
                            auth=(dehashed_email, dehashed_key),
                            headers={"Accept": "application/json"},
                            timeout=15,
                        )
                        if resp.status_code == 200:
                            data = resp.json()
                            total = data.get("total", 0)
                            if total > 0:
                                entries = data.get("entries", [])
                                # Sample of exposed credentials
                                sample_emails = list(set(
                                    e.get("email", "") for e in entries[:10] if e.get("email")
                                ))
                                finding = {
                                    "source": "dehashed",
                                    "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                                    "severity": "HIGH" if total > 100 else "MEDIUM",
                                    "title": f"DeHashed: {total} exposed credentials for {domain}",
                                    "description": f"Found {total} credential entries for {domain}. "
                                                   f"Sample emails: {', '.join(sample_emails[:5])}",
                                    "raw_url": f"https://dehashed.com/search?query=domain:{domain}",
                                    "iocs": {"emails": sample_emails, "domains": [domain]},
                                    "matched_keywords": [domain],
                                    "confidence": 75,
                                    "verified": False,
                                    "tags": ["breach", "dehashed", "credentials"],
                                    "breach_details": {
                                        "domain": domain,
                                        "total_exposed": total,
                                        "sample_count": len(entries),
                                    },
                                }
                                content_key = f"dehashed_{domain}_{total}"
                                if not _is_seen(state, content_key):
                                    finding = _ai_analyze_finding(finding, json.dumps(entries[:20], default=str))
                                    if finding.get("severity") != "FALSE_POSITIVE":
                                        _write_finding(finding)
                                        state["findings_total"] = state.get("findings_total", 0) + 1
                                        log.info(f"[L2-Breach] DeHashed: {total} entries for {domain}")
                        time.sleep(3)
                    except Exception as e:
                        log.warning(f"[L2-Breach] DeHashed error for {domain}: {e}")

            state["last_breach_scan"] = datetime.now(timezone.utc).isoformat()
            _save_state(state)

        except Exception as e:
            log.error(f"[L2-Breach] Loop error: {e}")

        time.sleep(6 * 3600)  # Every 6 hours


# ═══════════════════════════════════════════════════════════════════════════════
# LOOP 3 — CERTSTREAM WATCHER
# ═══════════════════════════════════════════════════════════════════════════════
def loop_certstream_watcher(state):
    """Real-time Certificate Transparency log monitoring for .jo-related domains."""
    log.info("[L3-Cert] Starting CertStream monitoring")

    if not _HAS_CERTSTREAM:
        log.warning("[L3-Cert] certstream not installed (pip install certstream). Skipping.")
        return

    # Domains to watch for lookalikes
    WATCH_PATTERNS = [
        ".jo", "jordan", "amman", "hashemite",
        "gov-jo", "govjo", "g0v.jo", "gov.j0",
        "arabbank", "zain-jo", "orange-jo", "umniah",
        "cbj-jo", "mod-jo", "moi-jo",
    ]

    # Known legitimate .jo domains (whitelist)
    LEGIT_JO = set([
        "gov.jo", "com.jo", "edu.jo", "net.jo", "org.jo", "mil.jo",
    ])

    def _on_cert(message, context):
        try:
            if message.get("message_type") != "certificate_update":
                return
            data = message.get("data", {})
            leaf = data.get("leaf_cert", {})
            domains = leaf.get("all_domains", [])

            for domain in domains:
                domain_lower = domain.lower().strip("*. ")
                if not domain_lower:
                    continue

                matched = False
                match_reasons = []

                # Check for .jo TLD
                if domain_lower.endswith(".jo") or ".jo." in domain_lower:
                    matched = True
                    match_reasons.append(".jo TLD")

                # Check for Jordan-related lookalikes
                for pattern in WATCH_PATTERNS:
                    if pattern in domain_lower and not domain_lower.endswith(".jo"):
                        matched = True
                        match_reasons.append(f"pattern:{pattern}")
                        break

                if not matched:
                    continue

                # Skip known legitimate domains
                if any(domain_lower.endswith(f".{legit}") for legit in LEGIT_JO):
                    # It's a real .jo subdomain — still log it but lower severity
                    pass

                content_key = f"cert_{domain_lower}"
                if _is_seen(state, content_key):
                    continue

                issuer = leaf.get("issuer", {})
                is_letsencrypt = "Let's Encrypt" in str(issuer)

                finding = {
                    "source": "certstream",
                    "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                    "severity": "HIGH" if not domain_lower.endswith(".jo") else "INFO",
                    "title": f"New certificate: {domain_lower}",
                    "description": f"Certificate issued for {domain_lower}. "
                                   f"Match reasons: {', '.join(match_reasons)}. "
                                   f"Issuer: {issuer.get('O', 'unknown')}. "
                                   f"Let's Encrypt: {is_letsencrypt}",
                    "raw_url": f"https://crt.sh/?q={domain_lower}",
                    "iocs": {"domains": [domain_lower]},
                    "matched_keywords": match_reasons,
                    "confidence": 80 if not domain_lower.endswith(".jo") else 30,
                    "verified": False,
                    "tags": ["certificate", "phishing" if not domain_lower.endswith(".jo") else "legitimate"],
                }

                # AI analysis for suspicious (non-.jo) domains
                if not domain_lower.endswith(".jo"):
                    finding = _ai_analyze_finding(finding, f"New cert for: {domain_lower}")

                if finding.get("severity") != "FALSE_POSITIVE":
                    _write_finding(finding)
                    state["findings_total"] = state.get("findings_total", 0) + 1
                    state.setdefault("findings_by_source", {})["certstream"] = \
                        state["findings_by_source"].get("certstream", 0) + 1
                    if finding["severity"] in ("CRITICAL", "HIGH"):
                        log.info(f"[L3-Cert] ALERT: Suspicious cert — {domain_lower}")
                    _save_state(state)

        except Exception as e:
            log.debug(f"[L3-Cert] Message processing error: {e}")

    # CertStream reconnection loop
    while True:
        try:
            log.info("[L3-Cert] Connecting to CertStream...")
            certstream.listen_for_events(_on_cert, url="wss://certstream.calidog.io/")
        except Exception as e:
            log.warning(f"[L3-Cert] CertStream disconnected: {e}. Reconnecting in 30s...")
            time.sleep(30)


# ═══════════════════════════════════════════════════════════════════════════════
# LOOP 4 — DOMAIN SQUAT SCANNER
# ═══════════════════════════════════════════════════════════════════════════════
def loop_domain_squat_scanner(state):
    """Run dnstwist against high-value .jo domains to detect typosquatting."""
    log.info("[L4-DomainSquat] Starting domain squatting detection")

    if not _HAS_DNSTWIST:
        log.warning("[L4-DomainSquat] dnstwist not installed (pip install dnstwist). Skipping.")
        return

    TARGET_DOMAINS = [
        "gov.jo", "mod.gov.jo", "moi.gov.jo", "cbj.gov.jo",
        "arabbank.com.jo", "hbtf.com.jo",
        "zain.jo", "orange.jo", "umniah.jo",
    ]

    while True:
        try:
            # Load previous scan results
            prev_domains = set()
            if DOMAIN_WATCH_FILE.exists():
                try:
                    data = json.loads(DOMAIN_WATCH_FILE.read_text(encoding="utf-8"))
                    prev_domains = set(data.get("known_lookalikes", []))
                except Exception:
                    pass

            all_results = []
            new_threats = []

            for target in TARGET_DOMAINS:
                log.info(f"[L4-DomainSquat] Scanning permutations for {target}...")
                try:
                    results = _dnstwist_mod.run(
                        domain=target,
                        registered=True,
                        format="null",
                    )
                    for r in results:
                        if r.get("domain") == target:
                            continue  # Skip the original domain
                        fuzzer = r.get("fuzzer", "")
                        domain = r.get("domain", "")
                        if domain and domain not in prev_domains:
                            new_threats.append({
                                "domain": domain,
                                "target": target,
                                "fuzzer": fuzzer,
                                "dns_a": r.get("dns_a", []),
                                "dns_mx": r.get("dns_mx", []),
                            })
                        all_results.append(domain)
                except Exception as e:
                    log.warning(f"[L4-DomainSquat] Error scanning {target}: {e}")

                time.sleep(5)  # Space out DNS queries

            # Save updated watchlist
            watchlist = {
                "last_scan": datetime.now(timezone.utc).isoformat(),
                "targets_scanned": TARGET_DOMAINS,
                "known_lookalikes": list(set(all_results)),
                "total_lookalikes": len(all_results),
            }
            DOMAIN_WATCH_FILE.write_text(
                json.dumps(watchlist, indent=2, ensure_ascii=False), encoding="utf-8"
            )

            # Write findings for NEW domains only
            for threat in new_threats:
                finding = {
                    "source": "dnstwist",
                    "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                    "severity": "HIGH",
                    "title": f"New lookalike domain: {threat['domain']} (targeting {threat['target']})",
                    "description": f"Typosquat type: {threat['fuzzer']}. "
                                   f"DNS A: {threat.get('dns_a',[])}. "
                                   f"DNS MX: {threat.get('dns_mx', [])}",
                    "raw_url": f"https://who.is/whois/{threat['domain']}",
                    "iocs": {"domains": [threat["domain"]]},
                    "matched_keywords": [threat["target"]],
                    "confidence": 85,
                    "verified": False,
                    "tags": ["domain_squatting", "phishing", threat["fuzzer"]],
                }
                finding = _ai_analyze_finding(finding, json.dumps(threat))
                if finding.get("severity") != "FALSE_POSITIVE":
                    _write_finding(finding)
                    state["findings_total"] = state.get("findings_total", 0) + 1
                    log.info(f"[L4-DomainSquat] NEW: {threat['domain']} → {threat['target']}")

            if new_threats:
                log.info(f"[L4-DomainSquat] Found {len(new_threats)} new lookalike domains")
            else:
                log.info(f"[L4-DomainSquat] No new lookalikes (tracking {len(all_results)} total)")

            state["last_dnstwist_scan"] = datetime.now(timezone.utc).isoformat()
            _save_state(state)

        except Exception as e:
            log.error(f"[L4-DomainSquat] Loop error: {e}")

        time.sleep(12 * 3600)  # Every 12 hours


# ═══════════════════════════════════════════════════════════════════════════════
# LOOP 5 — GITHUB MONITOR
# ═══════════════════════════════════════════════════════════════════════════════
def loop_github_monitor(state):
    """Search GitHub for leaked credentials, attack tools, and recon targeting Jordan."""
    log.info("[L5-GitHub] Starting GitHub monitoring")

    GITHUB_DORKS = [
        # Jordan-specific
        '"gov.jo" password OR secret OR token',
        '"gov.jo" filename:.env',
        '"@gov.jo" filename:.sql',
        '"jordan" api_key OR api_secret filename:.json',
        '"#OpJordan"',
        '"jordan" ddos OR deface filename:.py',
        '"mod.gov.jo" OR "moi.gov.jo"',
        '"zain.jo" OR "orange.jo" password',
        '"arabbank" password OR token',
        '"jordan" exploit OR vulnerability filename:.py',
        '"hashemite" hack OR breach',
        # Iranian APT tools and malware
        '"MuddyWater" C2 OR payload OR beacon',
        '"Charming Kitten" OR "APT35" phishing OR credential',
        '"OilRig" OR "APT34" backdoor OR implant',
        '"APT33" OR "Elfin" OR "Peach Sandstorm"',
        '"Cyber Av3ngers" OR "CyberAv3ngers"',
        '"BiBi" wiper OR linux OR windows',
        '"Handala" hack OR leak OR wiper',
        '"MosesStaff" OR "Moses Staff" hack',
        '"BellaCiao" backdoor OR implant',
        '"SAITAMA" backdoor OR dns',
        '"MuddyC2Go" OR "PhonyC2" OR "MuddyC3"',
        '"PowerLess" backdoor stealer',
        '"Shamoon" wiper OR destruction',
        '"DarkBit" ransomware OR hack',
        '"Agrius" wiper OR fantasy',
        '"IRGC" cyber OR hack',
        '"Emennet Pasargad"',
        '"Pioneer Kitten" OR "Fox Kitten"',
        '"Mint Sandstorm" OR "Phosphorus"',
        '"Cotton Sandstorm" OR "Neptunium"',
        '"DieNet" ddos OR attack',
        '"RipperSec" ddos OR hack',
        # ICS/OT targeting
        '"SCADA" iran OR jordan',
        '"Unitronics" PLC hack',
        '"Cyber Av3ngers" water OR PLC',
    ]

    while True:
        try:
            token = os.environ.get("GITHUB_TOKEN", "")
            headers = {"Accept": "application/vnd.github.v3+json"}
            if token:
                headers["Authorization"] = f"token {token}"

            new_count = 0
            for dork in GITHUB_DORKS:
                try:
                    resp = requests.get(
                        "https://api.github.com/search/code",
                        params={"q": dork, "sort": "indexed", "order": "desc", "per_page": 30},
                        headers=headers,
                        timeout=15,
                    )

                    if resp.status_code == 403:
                        # Rate limited
                        reset = int(resp.headers.get("X-RateLimit-Reset", 0))
                        wait = max(reset - time.time(), 60)
                        log.warning(f"[L5-GitHub] Rate limited, waiting {wait:.0f}s")
                        time.sleep(wait)
                        continue

                    if resp.status_code != 200:
                        continue

                    results = resp.json()
                    items = results.get("items", [])

                    for item in items:
                        repo = item.get("repository", {}).get("full_name", "")
                        path = item.get("path", "")
                        result_key = f"{repo}:{path}"

                        if result_key in state.get("seen_github_results", []):
                            continue
                        state.setdefault("seen_github_results", []).append(result_key)

                        # Fetch file content
                        raw_url = item.get("html_url", "").replace("github.com", "raw.githubusercontent.com").replace("/blob/", "/")
                        content = ""
                        try:
                            content_resp = requests.get(raw_url, timeout=10, headers=headers)
                            if content_resp.status_code == 200:
                                content = content_resp.text[:5000]
                        except Exception:
                            pass

                        finding = {
                            "source": "github",
                            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                            "severity": "HIGH" if "password" in dork or ".env" in dork else "MEDIUM",
                            "title": f"GitHub: {repo}/{path} — matches '{dork[:40]}'",
                            "description": content[:500] if content else f"Matched dork: {dork}",
                            "raw_url": item.get("html_url", ""),
                            "iocs": _extract_iocs(content) if content else {},
                            "matched_keywords": [dork[:50]],
                            "confidence": 60,
                            "verified": False,
                            "tags": ["github", "code_search"],
                            "github_details": {
                                "repo": repo,
                                "path": path,
                                "score": item.get("score", 0),
                            },
                        }

                        # AI analysis — is this a real threat or a security researcher's repo?
                        finding = _ai_analyze_finding(finding, content or dork)
                        if finding.get("severity") != "FALSE_POSITIVE":
                            _write_finding(finding)
                            new_count += 1
                            state["findings_total"] = state.get("findings_total", 0) + 1
                            log.info(f"[L5-GitHub] FINDING: {repo}/{path}")
                        else:
                            state["false_positives"] = state.get("false_positives", 0) + 1

                    time.sleep(10)  # Respect rate limits

                except Exception as e:
                    log.warning(f"[L5-GitHub] Dork error '{dork[:30]}': {e}")
                    time.sleep(10)

            if new_count:
                log.info(f"[L5-GitHub] {new_count} new findings this cycle")

            state["last_github_scan"] = datetime.now(timezone.utc).isoformat()
            _save_state(state)

        except Exception as e:
            log.error(f"[L5-GitHub] Loop error: {e}")

        time.sleep(2 * 3600)  # Every 2 hours


# ═══════════════════════════════════════════════════════════════════════════════
# LOOP 6 — RANSOMWARE LEAK TRACKER
# ═══════════════════════════════════════════════════════════════════════════════
def loop_ransom_leak_tracker(state):
    """Track ransomware leak sites for Jordanian victims via RansomLook/ransomwatch."""
    log.info("[L6-Ransom] Starting ransomware leak tracking")
    keywords = _load_keywords()

    while True:
        try:
            # ── RansomLook API ──
            try:
                resp = requests.get(
                    "https://www.ransomlook.io/api/recent",
                    timeout=15,
                    headers={"User-Agent": "JordanCyberIntelPlatform"},
                )
                if resp.status_code == 200:
                    victims = resp.json() if isinstance(resp.json(), list) else resp.json().get("data", [])
                    for victim in victims:
                        name = victim.get("post_title", "") or victim.get("victim", "")
                        group = victim.get("group_name", "") or victim.get("group", "")
                        desc = victim.get("description", "") or ""

                        combined = f"{name} {desc}".lower()
                        matches = _scan_text(combined, keywords)

                        if matches and not _is_seen(state, f"ransom_{name}_{group}"):
                            finding = {
                                "source": "ransomlook",
                                "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                                "severity": "CRITICAL",
                                "title": f"Ransomware victim: {name} (group: {group})",
                                "description": desc[:500] if desc else f"Victim: {name}, Group: {group}",
                                "raw_url": f"https://www.ransomlook.io/group/{group}",
                                "iocs": _extract_iocs(f"{name} {desc}"),
                                "matched_keywords": matches,
                                "confidence": 90,
                                "verified": False,
                                "tags": ["ransomware", "leak_site", group.lower()],
                                "ransom_details": {
                                    "victim": name,
                                    "group": group,
                                    "discovered_date": victim.get("discovered", ""),
                                },
                            }
                            finding = _ai_analyze_finding(finding, f"Victim: {name}\nGroup: {group}\n{desc}")
                            if finding.get("severity") != "FALSE_POSITIVE":
                                _write_finding(finding)
                                state["findings_total"] = state.get("findings_total", 0) + 1
                                log.info(f"[L6-Ransom] ALERT: {name} on {group}!")
            except Exception as e:
                log.warning(f"[L6-Ransom] RansomLook API error: {e}")

            # ── ransomwatch GitHub JSON feed ──
            try:
                resp = requests.get(
                    "https://raw.githubusercontent.com/joshhighet/ransomwatch/main/posts.json",
                    timeout=15,
                )
                if resp.status_code == 200:
                    posts = resp.json()
                    recent_cutoff = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
                    for post in posts:
                        if post.get("discovered", "") < recent_cutoff:
                            continue
                        name = post.get("post_title", "")
                        group = post.get("group_name", "")
                        combined = f"{name} {post.get('description','')}".lower()
                        matches = _scan_text(combined, _load_keywords())
                        if matches and not _is_seen(state, f"rwatch_{name}_{group}"):
                            finding = {
                                "source": "ransomwatch",
                                "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                                "severity": "CRITICAL",
                                "title": f"Ransomwatch: {name} (group: {group})",
                                "description": f"Victim: {name}, Group: {group}",
                                "raw_url": f"https://ransomwatch.telemetry.ltd/#/profiles?id={group}",
                                "iocs": {},
                                "matched_keywords": matches,
                                "confidence": 85,
                                "verified": False,
                                "tags": ["ransomware", "leak_site", group.lower()],
                            }
                            _write_finding(finding)
                            state["findings_total"] = state.get("findings_total", 0) + 1
                            log.info(f"[L6-Ransom] ransomwatch: {name} on {group}")
            except Exception as e:
                log.warning(f"[L6-Ransom] ransomwatch error: {e}")

            # ── Direct clearnet leak site crawling ──
            # Crawl known threat actor leak sites that have clearnet mirrors
            clearnet_leak_sites = [
                {"name": "Handala", "url": "https://handala-hack.to", "group": "handala",
                 "watch_for": ["belectric", "jordan", "solar", "energy", "bank", "اردن"]},
                {"name": "RansomLook Handala", "url": "https://www.ransomlook.io/group/handala", "group": "handala",
                 "watch_for": ["belectric", "jordan", "solar", "energy", "اردن"]},
            ]
            for site in clearnet_leak_sites:
                try:
                    resp = requests.get(
                        site["url"], timeout=20,
                        headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; rv:128.0) Gecko/20100101 Firefox/128.0"},
                        verify=False,  # Some DDoS-Guard certs cause issues
                    )
                    if resp.status_code == 200:
                        soup = BeautifulSoup(resp.text, "html.parser")
                        text = soup.get_text(separator=" ", strip=True).lower()
                        site_matches = [w for w in site["watch_for"] if w.lower() in text]
                        generic_matches = _scan_text(text, keywords)
                        all_matches = list(set(site_matches + generic_matches))
                        if all_matches and not _is_seen(state, f"leaksite_{site['name']}_{hashlib.md5(text[:2000].encode()).hexdigest()[:12]}"):
                            sev = "CRITICAL" if any(w in site_matches for w in ["belectric", "jordan", "solar"]) else "HIGH"
                            finding = {
                                "source": "clearnet_leaksite",
                                "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                                "severity": sev,
                                "title": f"Leak site crawl ({site['name']}): {', '.join(all_matches[:5])}",
                                "description": text[:600],
                                "raw_url": site["url"],
                                "iocs": _extract_iocs(resp.text),
                                "matched_keywords": all_matches,
                                "confidence": min(len(all_matches) * 25, 100),
                                "verified": False,
                                "tags": ["leak_site", "clearnet", site["group"]],
                            }
                            finding = _ai_analyze_finding(finding, text[:3000])
                            if finding.get("severity") != "FALSE_POSITIVE":
                                _write_finding(finding)
                                state["findings_total"] = state.get("findings_total", 0) + 1
                                log.info(f"[L6-Ransom] LEAK SITE HIT: {site['name']} — {', '.join(all_matches[:3])}")
                        elif site_matches:
                            log.info(f"[L6-Ransom] Leak site {site['name']} matched {site_matches} (dedup)")
                    else:
                        log.debug(f"[L6-Ransom] {site['name']} returned {resp.status_code}")
                except Exception as e:
                    log.warning(f"[L6-Ransom] Leak site {site['name']} error: {str(e)[:80]}")
                time.sleep(5)

            # ── ransomware.live API for Iranian-linked and relevant groups ──
            try:
                for group in [
                    "handala", "dienet", "rippersec", "mosesstaff", "agrius",
                    "darkbit", "blackshadow", "pay2key", "n3tw0rm",
                    "karma", "moneybird", "homeland-justice",
                    "cybertoufa", "cyber-toufan",
                    # Major ransomware groups that may target Middle East
                    "lockbit3", "alphv", "blackcat", "akira", "play",
                    "rhysida", "medusa", "8base", "bianlian", "clop",
                    "hunters", "qilin", "ransomhub", "fog", "lynx",
                    "cactus", "inc-ransom", "cicada3301", "funksec",
                ]:
                    resp = requests.get(
                        f"https://api.ransomware.live/v2/groupvictims/{group}",
                        timeout=15, headers={"User-Agent": "JordanCyberIntelPlatform"},
                    )
                    if resp.status_code == 200:
                        victims = resp.json() if isinstance(resp.json(), list) else []
                        for v in victims[-20:]:  # Check last 20 victims
                            vname = v.get("post_title", "") or v.get("victim", "") or ""
                            vdesc = v.get("description", "") or ""
                            combined = f"{vname} {vdesc}".lower()
                            if any(w in combined for w in [
                            "jordan", "belectric", "solar", ".jo", "amman",
                            "اردن", "energy", "hashemite", "arab bank",
                            "zain", "orange telecom", "umniah",
                            "etihad", "nepco", "royal jordanian",
                        ]):
                                if not _is_seen(state, f"rwlive_{group}_{vname}"):
                                    finding = {
                                        "source": "ransomware_live",
                                        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                                        "severity": "CRITICAL",
                                        "title": f"ransomware.live: {vname} (group: {group})",
                                        "description": vdesc[:500] or f"Victim: {vname}",
                                        "raw_url": f"https://www.ransomware.live/group/{group}",
                                        "matched_keywords": [w for w in ["jordan","belectric","solar",".jo"] if w in combined],
                                        "confidence": 95,
                                        "verified": False,
                                        "tags": ["ransomware", group],
                                    }
                                    _write_finding(finding)
                                    state["findings_total"] = state.get("findings_total", 0) + 1
                                    log.info(f"[L6-Ransom] ransomware.live JORDAN HIT: {vname} on {group}!")
            except Exception as e:
                log.warning(f"[L6-Ransom] ransomware.live error: {e}")

            state["last_ransom_scan"] = datetime.now(timezone.utc).isoformat()
            _save_state(state)

        except Exception as e:
            log.error(f"[L6-Ransom] Loop error: {e}")

        time.sleep(3600)  # Every 1 hour


# ═══════════════════════════════════════════════════════════════════════════════
# LOOP 8 — THREAT INTEL FEED AGGREGATOR (abuse.ch, CISA, OTX, RSS, VirusTotal)
# ═══════════════════════════════════════════════════════════════════════════════
def loop_threat_intel_feeds(state):
    """Aggregate bulk threat intel from free feeds — the main data engine."""
    log.info("[L8-Intel] Starting threat intel feed aggregator")
    keywords = _load_keywords()

    # Flatten all keywords for fast matching
    def _flat_kw(kw_dict):
        flat = []
        for cat, kws in kw_dict.items():
            flat.extend([k.lower() for k in kws])
        return list(set(flat))

    while True:
        try:
            flat_keywords = _flat_kw(_load_keywords())
            cycle_findings = 0

            # ────────────────────────────────────────────────────────────
            # 1. abuse.ch ThreatFox — IOCs with malware family tags (FREE, no auth)
            # ────────────────────────────────────────────────────────────
            try:
                resp = requests.post(
                    "https://threatfox-api.abuse.ch/api/v1/",
                    json={"query": "get_iocs", "days": 1},
                    timeout=30,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    iocs_list = data.get("data", [])
                    if isinstance(iocs_list, list):
                        for ioc in iocs_list:
                            malware = (ioc.get("malware", "") or "").lower()
                            malware_alias = (ioc.get("malware_alias", "") or "").lower()
                            tags = " ".join(ioc.get("tags", []) or []).lower()
                            reporter = (ioc.get("reporter", "") or "").lower()
                            ioc_value = ioc.get("ioc", "")
                            combined = f"{malware} {malware_alias} {tags} {reporter} {ioc_value}"

                            matches = [kw for kw in flat_keywords if kw in combined]
                            if matches and not _is_seen(state, f"tfox_{ioc.get('id','')}"):
                                finding = {
                                    "source": "threatfox",
                                    "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                                    "severity": "HIGH" if ioc.get("threat_type") == "payload_delivery" else "MEDIUM",
                                    "title": f"ThreatFox IOC: {malware or malware_alias} — {ioc.get('threat_type','')}",
                                    "description": f"IOC: {ioc_value}\nMalware: {malware}\n"
                                                   f"Type: {ioc.get('ioc_type','')}\nThreat: {ioc.get('threat_type','')}\n"
                                                   f"Tags: {tags}\nConfidence: {ioc.get('confidence_level',0)}%\n"
                                                   f"Reporter: {reporter}\nRef: {ioc.get('reference','')}",
                                    "raw_url": ioc.get("reference", "") or f"https://threatfox.abuse.ch/ioc/{ioc.get('id','')}",
                                    "iocs": _extract_iocs(f"{ioc_value} {ioc.get('reference','')}"),
                                    "matched_keywords": matches[:10],
                                    "confidence": ioc.get("confidence_level", 50),
                                    "verified": True,
                                    "tags": ["threatfox", "abuse_ch", malware, ioc.get("threat_type", "")],
                                    "intel_details": {
                                        "malware_family": malware,
                                        "ioc_type": ioc.get("ioc_type", ""),
                                        "threat_type": ioc.get("threat_type", ""),
                                        "first_seen": ioc.get("first_seen_utc", ""),
                                        "last_seen": ioc.get("last_seen_utc", ""),
                                    },
                                }
                                _write_finding(finding)
                                cycle_findings += 1
                                state["findings_total"] = state.get("findings_total", 0) + 1
                        log.info(f"[L8-Intel] ThreatFox: scanned {len(iocs_list)} IOCs, {cycle_findings} matched")
            except Exception as e:
                log.warning(f"[L8-Intel] ThreatFox error: {e}")

            # ────────────────────────────────────────────────────────────
            # 2. abuse.ch URLhaus — malicious URLs (FREE, no auth)
            # ────────────────────────────────────────────────────────────
            urlhaus_findings = 0
            try:
                resp = requests.post(
                    "https://urlhaus-api.abuse.ch/v1/urls/recent/",
                    data={"limit": 500},
                    timeout=30,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    urls = data.get("urls", [])
                    for url_entry in urls:
                        url_val = (url_entry.get("url", "") or "").lower()
                        url_tags = " ".join(url_entry.get("tags", []) or []).lower()
                        threat = (url_entry.get("threat", "") or "").lower()
                        combined = f"{url_val} {url_tags} {threat}"

                        matches = [kw for kw in flat_keywords if kw in combined]
                        if matches and not _is_seen(state, f"urlhaus_{url_entry.get('id','')}"):
                            finding = {
                                "source": "urlhaus",
                                "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                                "severity": "HIGH",
                                "title": f"URLhaus: malicious URL — {threat or url_tags}",
                                "description": f"URL: {url_entry.get('url','')}\nThreat: {threat}\n"
                                               f"Tags: {url_tags}\nHost: {url_entry.get('host','')}\n"
                                               f"Status: {url_entry.get('url_status','')}\n"
                                               f"Added: {url_entry.get('date_added','')}",
                                "raw_url": url_entry.get("urlhaus_reference", ""),
                                "iocs": {
                                    "urls": [url_entry.get("url", "")],
                                    "domains": [url_entry.get("host", "")] if url_entry.get("host") else [],
                                    "ips": [],
                                },
                                "matched_keywords": matches[:10],
                                "confidence": 85,
                                "verified": True,
                                "tags": ["urlhaus", "abuse_ch", "malware_url", threat],
                            }
                            _write_finding(finding)
                            urlhaus_findings += 1
                            state["findings_total"] = state.get("findings_total", 0) + 1
                    if urlhaus_findings:
                        log.info(f"[L8-Intel] URLhaus: {urlhaus_findings} matched from {len(urls)} URLs")
            except Exception as e:
                log.warning(f"[L8-Intel] URLhaus error: {e}")

            # ────────────────────────────────────────────────────────────
            # 3. abuse.ch MalwareBazaar — recent malware samples (FREE, no auth)
            # ────────────────────────────────────────────────────────────
            mb_findings = 0
            try:
                resp = requests.post(
                    "https://mb-api.abuse.ch/api/v1/",
                    data={"query": "get_recent", "selector": "time"},
                    timeout=30,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    samples = data.get("data", [])
                    if isinstance(samples, list):
                        for sample in samples[:200]:
                            sig = (sample.get("signature", "") or "").lower()
                            fname = (sample.get("file_name", "") or "").lower()
                            tags = " ".join(sample.get("tags", []) or []).lower()
                            combined = f"{sig} {fname} {tags}"

                            matches = [kw for kw in flat_keywords if kw in combined]
                            if matches and not _is_seen(state, f"mbazaar_{sample.get('sha256_hash','')[:16]}"):
                                finding = {
                                    "source": "malwarebazaar",
                                    "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                                    "severity": "HIGH",
                                    "title": f"MalwareBazaar: {sig or fname} sample",
                                    "description": f"Signature: {sig}\nFilename: {fname}\n"
                                                   f"Type: {sample.get('file_type','')}\nTags: {tags}\n"
                                                   f"SHA256: {sample.get('sha256_hash','')}\n"
                                                   f"First seen: {sample.get('first_seen','')}",
                                    "raw_url": f"https://bazaar.abuse.ch/sample/{sample.get('sha256_hash','')}",
                                    "iocs": {
                                        "hashes": {
                                            "sha256": [sample.get("sha256_hash", "")],
                                            "sha1": [sample.get("sha1_hash", "")] if sample.get("sha1_hash") else [],
                                            "md5": [sample.get("md5_hash", "")] if sample.get("md5_hash") else [],
                                        },
                                    },
                                    "matched_keywords": matches[:10],
                                    "confidence": 90,
                                    "verified": True,
                                    "tags": ["malwarebazaar", "abuse_ch", "malware_sample", sig],
                                }
                                _write_finding(finding)
                                mb_findings += 1
                                state["findings_total"] = state.get("findings_total", 0) + 1
                        if mb_findings:
                            log.info(f"[L8-Intel] MalwareBazaar: {mb_findings} matched from {len(samples)} samples")
            except Exception as e:
                log.warning(f"[L8-Intel] MalwareBazaar error: {e}")

            # ────────────────────────────────────────────────────────────
            # 4. abuse.ch — Search specifically for Iranian malware families
            # ────────────────────────────────────────────────────────────
            iranian_malware_tags = [
                "MuddyWater", "APT33", "APT34", "APT35", "Charming Kitten",
                "OilRig", "Shamoon", "BiBi", "PowerLess", "BellaCiao",
                "SAITAMA", "Agrius", "MosesStaff", "CharmPower", "MuddyC2Go",
                "KARKOFF", "SIDETWIST", "Lyceum", "Hexane", "Phosphorus",
                "DarkBit", "Moneybird", "Fantasy", "Apostle",
            ]
            for malware_tag in iranian_malware_tags:
                try:
                    # ThreatFox tag search API
                    resp = requests.post(
                        "https://threatfox-api.abuse.ch/api/v1/",
                        json={"query": "search_ioc", "search_term": malware_tag},
                        timeout=15,
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        iocs_list = data.get("data", [])
                        if isinstance(iocs_list, list) and iocs_list:
                            for ioc in iocs_list:
                                ioc_id = str(ioc.get("id", ""))
                                if not _is_seen(state, f"tfox_iran_{ioc_id}"):
                                    finding = {
                                        "source": "threatfox_iranian",
                                        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                                        "severity": "CRITICAL",
                                        "title": f"Iranian APT IOC: {malware_tag} — {ioc.get('ioc','')}",
                                        "description": f"Malware: {malware_tag}\nIOC: {ioc.get('ioc','')}\n"
                                                       f"Type: {ioc.get('ioc_type','')}\n"
                                                       f"First seen: {ioc.get('first_seen_utc','')}\n"
                                                       f"Confidence: {ioc.get('confidence_level',0)}%\n"
                                                       f"Reference: {ioc.get('reference','')}",
                                        "raw_url": ioc.get("reference", "") or f"https://threatfox.abuse.ch/ioc/{ioc_id}",
                                        "iocs": _extract_iocs(str(ioc.get("ioc", ""))),
                                        "matched_keywords": [malware_tag],
                                        "confidence": ioc.get("confidence_level", 75),
                                        "verified": True,
                                        "tags": ["iranian_apt", "threatfox", malware_tag.lower()],
                                        "intel_details": {
                                            "malware_family": malware_tag,
                                            "ioc_type": ioc.get("ioc_type", ""),
                                            "first_seen": ioc.get("first_seen_utc", ""),
                                        },
                                    }
                                    _write_finding(finding)
                                    state["findings_total"] = state.get("findings_total", 0) + 1
                                    cycle_findings += 1
                    time.sleep(1)
                except Exception as e:
                    log.debug(f"[L8-Intel] ThreatFox tag '{malware_tag}' error: {e}")

            # ────────────────────────────────────────────────────────────
            # 4b. MalwareBazaar — search for Iranian malware families by tag
            # ────────────────────────────────────────────────────────────
            iranian_mb_tags = [
                "MuddyWater", "OilRig", "BiBi", "Shamoon", "BellaCiao",
                "SAITAMA", "CharmPower", "PowerLess", "Agrius", "DarkBit",
                "Phosphorus", "APT33", "APT34", "APT35", "Lyceum",
            ]
            mb_iran_findings = 0
            for tag in iranian_mb_tags:
                try:
                    resp = requests.post(
                        "https://mb-api.abuse.ch/api/v1/",
                        data={"query": "get_taginfo", "tag": tag, "limit": 25},
                        timeout=15,
                    )
                    if resp.status_code == 200:
                        data = resp.json()
                        samples = data.get("data", [])
                        if isinstance(samples, list):
                            for sample in samples:
                                sha = sample.get("sha256_hash", "")
                                if sha and not _is_seen(state, f"mb_iran_{sha[:16]}"):
                                    finding = {
                                        "source": "malwarebazaar_iranian",
                                        "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                                        "severity": "CRITICAL",
                                        "title": f"Iranian malware sample: {tag} — {sample.get('signature','unknown')}",
                                        "description": f"Tag: {tag}\nSignature: {sample.get('signature','')}\n"
                                                       f"Filename: {sample.get('file_name','')}\n"
                                                       f"Type: {sample.get('file_type','')}\n"
                                                       f"SHA256: {sha}\n"
                                                       f"First seen: {sample.get('first_seen','')}\n"
                                                       f"Tags: {', '.join(sample.get('tags',[]) or [])}",
                                        "raw_url": f"https://bazaar.abuse.ch/sample/{sha}",
                                        "iocs": {"hashes": {"sha256": [sha], "md5": [sample.get("md5_hash","")] if sample.get("md5_hash") else [], "sha1": []}},
                                        "matched_keywords": [tag],
                                        "confidence": 90,
                                        "verified": True,
                                        "tags": ["iranian_malware", "malwarebazaar", tag.lower()],
                                    }
                                    _write_finding(finding)
                                    mb_iran_findings += 1
                                    state["findings_total"] = state.get("findings_total", 0) + 1
                    time.sleep(1)
                except Exception as e:
                    log.debug(f"[L8-Intel] MalwareBazaar tag '{tag}' error: {e}")
            if mb_iran_findings:
                log.info(f"[L8-Intel] MalwareBazaar Iranian tags: {mb_iran_findings} samples found")

            # ────────────────────────────────────────────────────────────
            # 5. CISA Known Exploited Vulnerabilities (KEV) feed
            # ────────────────────────────────────────────────────────────
            try:
                resp = requests.get(
                    "https://www.cisa.gov/sites/default/files/feeds/known_exploited_vulnerabilities.json",
                    timeout=20,
                )
                if resp.status_code == 200:
                    data = resp.json()
                    vulns = data.get("vulnerabilities", [])
                    # Only check recent (last 7 days)
                    cutoff = (datetime.now(timezone.utc) - timedelta(days=7)).strftime("%Y-%m-%d")
                    kev_findings = 0
                    for vuln in vulns:
                        if vuln.get("dateAdded", "") >= cutoff:
                            desc = f"{vuln.get('vendorProject','')} {vuln.get('product','')} {vuln.get('vulnerabilityName','')} {vuln.get('shortDescription','')}"
                            matches = [kw for kw in flat_keywords if kw in desc.lower()]
                            if not matches:
                                # Still report all recent KEVs as general intel
                                matches = ["CISA_KEV"]
                            if not _is_seen(state, f"kev_{vuln.get('cveID','')}"):
                                finding = {
                                    "source": "cisa_kev",
                                    "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                                    "severity": "HIGH",
                                    "title": f"CISA KEV: {vuln.get('cveID','')} — {vuln.get('vendorProject','')} {vuln.get('product','')}",
                                    "description": f"{vuln.get('vulnerabilityName','')}\n"
                                                   f"{vuln.get('shortDescription','')}\n"
                                                   f"Action: {vuln.get('requiredAction','')}\n"
                                                   f"Due: {vuln.get('dueDate','')}\n"
                                                   f"Known ransomware use: {vuln.get('knownRansomwareCampaignUse','')}",
                                    "raw_url": f"https://nvd.nist.gov/vuln/detail/{vuln.get('cveID','')}",
                                    "iocs": {"cve": [vuln.get("cveID", "")]},
                                    "matched_keywords": matches[:5],
                                    "confidence": 95,
                                    "verified": True,
                                    "tags": ["cisa", "kev", "vulnerability", vuln.get("vendorProject", "").lower()],
                                }
                                _write_finding(finding)
                                kev_findings += 1
                                state["findings_total"] = state.get("findings_total", 0) + 1
                    if kev_findings:
                        log.info(f"[L8-Intel] CISA KEV: {kev_findings} new exploited vulns")
            except Exception as e:
                log.warning(f"[L8-Intel] CISA KEV error: {e}")

            # ────────────────────────────────────────────────────────────
            # 6. Security News RSS Feeds — cyber threat intel articles
            # ────────────────────────────────────────────────────────────
            if _HAS_FEEDPARSER:
                rss_feeds = [
                    ("https://feeds.feedburner.com/TheHackersNews", "TheHackerNews"),
                    ("https://www.bleepingcomputer.com/feed/", "BleepingComputer"),
                    ("https://krebsonsecurity.com/feed/", "KrebsOnSecurity"),
                    ("https://therecord.media/feed", "TheRecord"),
                    ("https://www.darkreading.com/rss.xml", "DarkReading"),
                    ("https://cyberscoop.com/feed/", "CyberScoop"),
                    ("https://securelist.com/feed/", "Securelist_Kaspersky"),
                    ("https://www.sentinelone.com/blog/feed/", "SentinelOne"),
                    ("https://www.mandiant.com/resources/blog/rss.xml", "Mandiant"),
                    ("https://unit42.paloaltonetworks.com/feed/", "Unit42"),
                    ("https://blog.talosintelligence.com/feeds/posts/default", "Cisco_Talos"),
                    ("https://research.checkpoint.com/feed/", "CheckPoint"),
                    ("https://www.welivesecurity.com/en/rss/feed/", "ESET"),
                    ("https://www.microsoft.com/en-us/security/blog/feed/", "Microsoft_Security"),
                    ("https://blog.google/threat-analysis-group/rss/", "Google_TAG"),
                    ("https://symantec-enterprise-blogs.security.com/blogs/threat-intelligence/rss", "Symantec"),
                ]
                rss_findings = 0
                for feed_url, feed_name in rss_feeds:
                    try:
                        feed = feedparser.parse(feed_url)
                        for entry in feed.entries[:15]:
                            title = (entry.get("title", "") or "").lower()
                            summary = (entry.get("summary", "") or entry.get("description", "") or "").lower()
                            link = entry.get("link", "")
                            combined = f"{title} {summary}"

                            matches = [kw for kw in flat_keywords if kw in combined]
                            if matches and not _is_seen(state, f"rss_{feed_name}_{hashlib.md5(title.encode()).hexdigest()[:12]}"):
                                # Determine severity from keyword categories
                                has_iran = any(kw for kw in matches if kw in [k.lower() for k in
                                    (_load_keywords().get("iranian_apt_groups", []) +
                                     _load_keywords().get("iranian_hacktivist_groups", []) +
                                     _load_keywords().get("iranian_malware_tools", []))])
                                has_jordan = any(kw for kw in matches if "jordan" in kw or ".jo" in kw)
                                sev = "CRITICAL" if (has_iran and has_jordan) else "HIGH" if has_iran else "MEDIUM"

                                finding = {
                                    "source": f"rss_{feed_name}",
                                    "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                                    "severity": sev,
                                    "title": f"{feed_name}: {entry.get('title', '')[:120]}",
                                    "description": summary[:600],
                                    "raw_url": link,
                                    "iocs": _extract_iocs(summary),
                                    "matched_keywords": matches[:15],
                                    "confidence": min(len(matches) * 20, 95),
                                    "verified": True,
                                    "tags": ["rss", "threat_intel", feed_name.lower()],
                                    "article_details": {
                                        "source": feed_name,
                                        "published": entry.get("published", ""),
                                        "author": entry.get("author", ""),
                                    },
                                }
                                _write_finding(finding)
                                rss_findings += 1
                                state["findings_total"] = state.get("findings_total", 0) + 1
                    except Exception as e:
                        log.debug(f"[L8-Intel] RSS {feed_name} error: {e}")
                    time.sleep(1)
                if rss_findings:
                    log.info(f"[L8-Intel] RSS feeds: {rss_findings} matched articles from {len(rss_feeds)} feeds")

            # ────────────────────────────────────────────────────────────
            # 7. AlienVault OTX — pulse feed (FREE with registration)
            # ────────────────────────────────────────────────────────────
            otx_key = os.environ.get("OTX_API_KEY", "")
            if otx_key:
                try:
                    headers = {"X-OTX-API-KEY": otx_key}
                    resp = requests.get(
                        "https://otx.alienvault.com/api/v1/pulses/subscribed?limit=50&modified_since=1d",
                        headers=headers, timeout=20,
                    )
                    if resp.status_code == 200:
                        pulses = resp.json().get("results", [])
                        otx_findings = 0
                        for pulse in pulses:
                            pname = (pulse.get("name", "") or "").lower()
                            pdesc = (pulse.get("description", "") or "").lower()
                            ptags = " ".join(pulse.get("tags", []) or []).lower()
                            combined = f"{pname} {pdesc} {ptags}"

                            matches = [kw for kw in flat_keywords if kw in combined]
                            if matches and not _is_seen(state, f"otx_{pulse.get('id','')}"):
                                indicators = pulse.get("indicators", [])
                                iocs_extracted = {"ips": [], "domains": [], "hashes": {"md5": [], "sha1": [], "sha256": []}, "urls": []}
                                for ind in indicators[:50]:
                                    itype = ind.get("type", "")
                                    ival = ind.get("indicator", "")
                                    if itype in ("IPv4", "IPv6"):
                                        iocs_extracted["ips"].append(ival)
                                    elif itype in ("domain", "hostname"):
                                        iocs_extracted["domains"].append(ival)
                                    elif itype == "URL":
                                        iocs_extracted["urls"].append(ival)
                                    elif itype == "FileHash-MD5":
                                        iocs_extracted["hashes"]["md5"].append(ival)
                                    elif itype == "FileHash-SHA256":
                                        iocs_extracted["hashes"]["sha256"].append(ival)

                                finding = {
                                    "source": "otx_alienvault",
                                    "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                                    "severity": "HIGH",
                                    "title": f"OTX Pulse: {pulse.get('name', '')[:120]}",
                                    "description": pdesc[:600],
                                    "raw_url": f"https://otx.alienvault.com/pulse/{pulse.get('id','')}",
                                    "iocs": iocs_extracted,
                                    "matched_keywords": matches[:15],
                                    "confidence": 80,
                                    "verified": True,
                                    "tags": ["otx", "alienvault", "pulse"] + (pulse.get("tags", []) or [])[:5],
                                    "intel_details": {
                                        "pulse_name": pulse.get("name", ""),
                                        "author": pulse.get("author_name", ""),
                                        "indicator_count": len(indicators),
                                        "created": pulse.get("created", ""),
                                    },
                                }
                                _write_finding(finding)
                                otx_findings += 1
                                state["findings_total"] = state.get("findings_total", 0) + 1
                        if otx_findings:
                            log.info(f"[L8-Intel] OTX: {otx_findings} matched pulses")
                except Exception as e:
                    log.warning(f"[L8-Intel] OTX error: {e}")

            # ────────────────────────────────────────────────────────────
            # 8. Specific Iranian threat reports from key vendors
            # ────────────────────────────────────────────────────────────
            iran_specific_urls = [
                ("https://api.ransomware.live/v2/groups", "ransomware_live_groups"),
                ("https://raw.githubusercontent.com/MISP/misp-galaxy/main/clusters/threat-actor.json", "misp_threat_actors"),
            ]
            for url, src in iran_specific_urls:
                try:
                    resp = requests.get(url, timeout=20, headers={"User-Agent": "JordanCyberIntelPlatform"})
                    if resp.status_code == 200:
                        text = resp.text.lower()
                        iran_matches = [kw for kw in flat_keywords if kw in text and
                                       kw in [k.lower() for cat in ["iranian_apt_groups", "iranian_hacktivist_groups", "iranian_malware_tools"]
                                              for k in _load_keywords().get(cat, [])]]
                        if iran_matches and not _is_seen(state, f"iranref_{src}_{hashlib.md5(text[:3000].encode()).hexdigest()[:12]}"):
                            finding = {
                                "source": src,
                                "timestamp_utc": datetime.now(timezone.utc).isoformat(),
                                "severity": "MEDIUM",
                                "title": f"Iranian threat data from {src}: {', '.join(iran_matches[:5])}",
                                "description": f"Matched {len(iran_matches)} Iranian threat keywords in {src}",
                                "raw_url": url,
                                "matched_keywords": iran_matches[:20],
                                "confidence": 60,
                                "verified": True,
                                "tags": ["iranian_intel", src],
                            }
                            _write_finding(finding)
                            state["findings_total"] = state.get("findings_total", 0) + 1
                except Exception as e:
                    log.debug(f"[L8-Intel] {src} error: {e}")

            cycle_findings = state.get("findings_total", 0)
            state["last_intel_feed_scan"] = datetime.now(timezone.utc).isoformat()
            _save_state(state)
            log.info(f"[L8-Intel] Feed cycle complete. Total platform findings: {cycle_findings}")

        except Exception as e:
            log.error(f"[L8-Intel] Loop error: {e}")

        time.sleep(1800)  # Every 30 minutes


# ═══════════════════════════════════════════════════════════════════════════════
# LOOP 7 — DARK WEB CRAWLER (Tor-based .onion monitoring)
# ═══════════════════════════════════════════════════════════════════════════════
class DarkWebCrawler:
    """Tor-based .onion site crawler with AI analysis."""

    SOCKS_PROXY = "socks5h://127.0.0.1:9050"
    CONTROL_PORT = 9051
    MIN_DELAY = 3    # Min seconds between requests
    MAX_DELAY = 7    # Max seconds (random jitter)
    CIRCUIT_ROTATE_EVERY = 10
    MAX_CONTENT_SIZE = 500_000  # 500KB max per page

    def __init__(self, state, keywords):
        self.state = state
        self.keywords = keywords
        self.session = requests.Session()
        self.session.proxies = {
            "http": self.SOCKS_PROXY,
            "https": self.SOCKS_PROXY,
        }
        # Match Tor Browser's exact User-Agent
        self.session.headers.update({
            "User-Agent": "Mozilla/5.0 (Windows NT 10.0; rv:128.0) Gecko/20100101 Firefox/128.0",
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "en-US,en;q=0.5",
        })
        self.request_count = 0
        self.tor_available = False

    def check_tor(self):
        """Verify Tor connectivity."""
        try:
            resp = self.session.get("http://check.torproject.org", timeout=30)
            if "Congratulations" in resp.text:
                self.tor_available = True
                log.info("[L7-Dark] Tor connection VERIFIED")
                return True
            else:
                log.warning("[L7-Dark] Tor connection failed — not using Tor network")
                return False
        except Exception as e:
            log.warning(f"[L7-Dark] Tor not available: {e}")
            return False

    def rotate_circuit(self):
        """Request new Tor identity."""
        if not _HAS_STEM:
            return
        try:
            with Controller.from_port(port=self.CONTROL_PORT) as ctrl:
                ctrl.authenticate()
                ctrl.signal(Signal.NEWNYM)
            self.state["tor_circuits_rotated"] = self.state.get("tor_circuits_rotated", 0) + 1
            time.sleep(5)  # Wait for new circuit
        except Exception as e:
            log.debug(f"[L7-Dark] Circuit rotation failed: {e}")

    def fetch_onion(self, url, timeout=30):
        """Fetch a .onion URL through Tor with rate limiting and circuit rotation."""
        self.request_count += 1
        if self.request_count % self.CIRCUIT_ROTATE_EVERY == 0:
            self.rotate_circuit()

        # Random delay for stealth
        delay = random.uniform(self.MIN_DELAY, self.MAX_DELAY)
        time.sleep(delay)

        try:
            resp = self.session.get(url, timeout=timeout, stream=True)
            # Limit content size
            content = resp.content[:self.MAX_CONTENT_SIZE]
            resp.close()
            return content.decode("utf-8", errors="replace")
        except Exception as e:
            log.debug(f"[L7-Dark] Fetch failed {url[:60]}: {e}")
            return None

    def scan_page(self, html, source_url, source_type):
        """Scan fetched content for Jordan-relevant intel."""
        soup = BeautifulSoup(html, "html.parser")
        # Strip scripts and styles
        for tag in soup(["script", "style"]):
            tag.decompose()
        text = soup.get_text(separator=" ", strip=True)

        if not text or len(text) < 50:
            return []

        # Content dedup
        if _is_seen(self.state, text):
            return []

        matches = _scan_text(text, self.keywords)
        if not matches:
            return []

        iocs = _extract_iocs(text)
        finding = {
            "source": f"darkweb_{source_type}",
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "severity": _assess_severity(matches, f"darkweb_{source_type}"),
            "title": f"Dark web ({source_type}): {', '.join(matches[:3])}",
            "description": text[:500],
            "raw_url": source_url,
            "iocs": iocs,
            "matched_keywords": matches,
            "confidence": min(len(matches) * 25, 100),
            "verified": False,
            "tags": [source_type, "dark_web", "tor"],
        }

        # AI analysis
        finding = _ai_analyze_finding(finding, text[:4000])
        return [finding] if finding.get("severity") != "FALSE_POSITIVE" else []

    def crawl_ransomware_dls(self):
        """Crawl ransomware data leak sites for Jordanian victims."""
        targets = self._load_targets("ransomware_dls")
        log.info(f"[L7-Dark] Crawling {len(targets)} ransomware DLS...")

        for site in targets:
            url = site.get("url", "")
            if not url:
                continue
            html = self.fetch_onion(url)
            if html:
                findings = self.scan_page(html, url, "ransomware_dls")
                for f in findings:
                    f["ransomware_group"] = site.get("group", "unknown")
                    _write_finding(f)
                    self.state["findings_total"] = self.state.get("findings_total", 0) + 1
                    log.info(f"[L7-Dark] RANSOM DLS FINDING: {f['title'][:60]}")
                # Update last_crawled
                site["last_crawled"] = datetime.now(timezone.utc).isoformat()
            else:
                site["consecutive_failures"] = site.get("consecutive_failures", 0) + 1

        self._save_targets()

    def crawl_forums(self):
        """Crawl public/guest sections of dark web forums."""
        targets = self._load_targets("forums")
        log.info(f"[L7-Dark] Crawling {len(targets)} forum targets...")

        for forum in targets:
            url = forum.get("url", "")
            if not url:
                continue
            html = self.fetch_onion(url)
            if html:
                findings = self.scan_page(html, url, "forum")
                for f in findings:
                    f["forum_name"] = forum.get("name", "unknown")
                    _write_finding(f)
                    self.state["findings_total"] = self.state.get("findings_total", 0) + 1
                    log.info(f"[L7-Dark] FORUM FINDING: {f['title'][:60]}")
                forum["last_crawled"] = datetime.now(timezone.utc).isoformat()
            else:
                forum["consecutive_failures"] = forum.get("consecutive_failures", 0) + 1

        self._save_targets()

    def crawl_paste_sites(self):
        """Crawl dark web paste sites."""
        targets = self._load_targets("paste_sites")
        log.info(f"[L7-Dark] Crawling {len(targets)} onion paste sites...")

        for site in targets:
            url = site.get("url", "")
            if not url:
                continue
            html = self.fetch_onion(url)
            if html:
                findings = self.scan_page(html, url, "onion_paste")
                for f in findings:
                    _write_finding(f)
                    self.state["findings_total"] = self.state.get("findings_total", 0) + 1
                    log.info(f"[L7-Dark] PASTE FINDING: {f['title'][:60]}")
                site["last_crawled"] = datetime.now(timezone.utc).isoformat()

        self._save_targets()

    def search_ahmia(self):
        """Use Ahmia clearnet API to discover new .onion sites related to Jordan."""
        search_terms = [
            "jordan hack", "jordan government", "gov.jo",
            "jordan bank breach", "jordan telecom", "OpJordan",
            "hashemite", "jordan military", "jordan DDoS",
        ]
        discovered = 0

        for term in search_terms:
            try:
                # Ahmia API is clearnet — direct request, no Tor
                resp = requests.get(
                    f"https://ahmia.fi/api/search/?q={term}",
                    timeout=15,
                    headers={"User-Agent": "JordanCyberIntelPlatform"},
                )
                if resp.status_code == 200:
                    try:
                        results = resp.json()
                    except Exception:
                        continue
                    items = results if isinstance(results, list) else results.get("results", [])
                    for r in items:
                        url = r.get("url", "") or r.get("onion_url", "")
                        if ".onion" in url:
                            self._add_discovered_target(url, term)
                            discovered += 1
            except Exception as e:
                log.debug(f"[L7-Dark] Ahmia search error for '{term}': {e}")
            time.sleep(3)

        if discovered:
            log.info(f"[L7-Dark] Ahmia discovered {discovered} .onion URLs")

        self.state["last_ahmia_search"] = datetime.now(timezone.utc).isoformat()

    def _load_targets(self, category):
        """Load crawl targets from onion_targets.json."""
        if ONION_TARGETS_FILE.exists():
            try:
                data = json.loads(ONION_TARGETS_FILE.read_text(encoding="utf-8"))
                return data.get(category, [])
            except Exception:
                pass
        return []

    def _save_targets(self):
        """Save updated targets back to disk."""
        if ONION_TARGETS_FILE.exists():
            try:
                data = json.loads(ONION_TARGETS_FILE.read_text(encoding="utf-8"))
            except Exception:
                data = {}
        else:
            data = {}
        ONION_TARGETS_FILE.write_text(
            json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
        )

    def _add_discovered_target(self, url, search_term):
        """Add a newly discovered .onion URL to the discovered list."""
        if ONION_TARGETS_FILE.exists():
            try:
                data = json.loads(ONION_TARGETS_FILE.read_text(encoding="utf-8"))
            except Exception:
                data = {}
        else:
            data = {}

        discovered = data.setdefault("discovered", [])
        existing_urls = {t.get("url") for t in discovered}
        if url not in existing_urls:
            discovered.append({
                "url": url,
                "found_via": search_term,
                "found_at": datetime.now(timezone.utc).isoformat(),
                "crawled": False,
            })
            ONION_TARGETS_FILE.write_text(
                json.dumps(data, indent=2, ensure_ascii=False), encoding="utf-8"
            )


def loop_dark_web_crawler(state):
    """Main loop for Tor-based dark web crawling."""
    log.info("[L7-Dark] Starting dark web crawler")
    keywords = _load_keywords()
    crawler = DarkWebCrawler(state, keywords)

    # Check Tor connectivity
    if not crawler.check_tor():
        log.warning("[L7-Dark] Tor not available. Running Ahmia-only mode (clearnet).")
        # Still run Ahmia searches even without Tor
        while True:
            try:
                crawler.search_ahmia()
                _save_state(state)
            except Exception as e:
                log.error(f"[L7-Dark] Ahmia-only loop error: {e}")
            time.sleep(4 * 3600)

    # Full crawl loop with Tor
    while True:
        try:
            log.info("[L7-Dark] === Starting dark web crawl cycle ===")

            # 1. Ransomware DLS crawl (most critical)
            crawler.crawl_ransomware_dls()

            # 2. Forum crawl
            crawler.crawl_forums()

            # 3. Paste site crawl
            crawler.crawl_paste_sites()

            # 4. Ahmia discovery (clearnet)
            crawler.search_ahmia()

            # 5. Crawl newly discovered targets
            discovered = crawler._load_targets("discovered")
            uncrawled = [t for t in discovered if not t.get("crawled")]
            if uncrawled:
                log.info(f"[L7-Dark] Crawling {len(uncrawled)} newly discovered targets...")
                for target in uncrawled[:10]:  # Max 10 per cycle
                    html = crawler.fetch_onion(target["url"])
                    if html:
                        findings = crawler.scan_page(html, target["url"], "discovered")
                        for f in findings:
                            _write_finding(f)
                            state["findings_total"] = state.get("findings_total", 0) + 1
                    target["crawled"] = True
                    target["crawled_at"] = datetime.now(timezone.utc).isoformat()
                crawler._save_targets()

            state["last_dark_crawl"] = datetime.now(timezone.utc).isoformat()
            _save_state(state)

            log.info(f"[L7-Dark] Crawl cycle complete. Total findings: {state.get('findings_total', 0)}")

        except Exception as e:
            log.error(f"[L7-Dark] Crawl cycle error: {e}")

        # Wait 2 hours before next full cycle
        time.sleep(2 * 3600)


# ═══════════════════════════════════════════════════════════════════════════════
# AI DAILY DIGEST
# ═══════════════════════════════════════════════════════════════════════════════
def loop_daily_digest(state):
    """Generate AI-powered daily intelligence digest of all dark collection findings."""
    log.info("[Digest] Starting daily digest loop")

    while True:
        try:
            # Check if it's time for a digest (every 24h)
            last = state.get("last_daily_digest")
            if last:
                try:
                    last_dt = datetime.fromisoformat(last.replace("Z", "+00:00"))
                    if datetime.now(timezone.utc) - last_dt < timedelta(hours=23):
                        time.sleep(3600)  # Check every hour
                        continue
                except Exception:
                    pass

            # Load last 24h of findings
            if not DARK_INTEL_FILE.exists():
                time.sleep(3600)
                continue

            cutoff = (datetime.now(timezone.utc) - timedelta(hours=24)).isoformat()
            recent = []
            try:
                with open(DARK_INTEL_FILE, "r", encoding="utf-8") as f:
                    for line in f:
                        line = line.strip()
                        if not line:
                            continue
                        try:
                            finding = json.loads(line)
                            if finding.get("timestamp_utc", "") >= cutoff:
                                recent.append(finding)
                        except Exception:
                            continue
            except Exception:
                pass

            if not recent:
                log.info("[Digest] No findings in last 24h, skipping digest")
                state["last_daily_digest"] = datetime.now(timezone.utc).isoformat()
                _save_state(state)
                time.sleep(3600)
                continue

            # Build summary for AI
            summary = {
                "total_findings": len(recent),
                "by_source": defaultdict(int),
                "by_severity": defaultdict(int),
                "false_positives": 0,
                "top_findings": [],
            }
            for f in recent:
                summary["by_source"][f.get("source", "?")] += 1
                summary["by_severity"][f.get("severity", "?")] += 1
                if f.get("severity") == "FALSE_POSITIVE":
                    summary["false_positives"] += 1
                if f.get("severity") in ("CRITICAL", "HIGH"):
                    summary["top_findings"].append({
                        "title": f.get("title", ""),
                        "severity": f.get("severity", ""),
                        "source": f.get("source", ""),
                        "confidence": f.get("confidence", 0),
                    })

            summary["by_source"] = dict(summary["by_source"])
            summary["by_severity"] = dict(summary["by_severity"])

            # Generate AI digest
            digest = _ai_call(
                AI_DAILY_DIGEST_SYSTEM,
                f"24-hour dark collection summary:\n{json.dumps(summary, indent=2, ensure_ascii=False)}\n\n"
                f"Top findings detail:\n{json.dumps(summary['top_findings'][:20], indent=2, ensure_ascii=False)}",
                model="gpt-4o", max_tokens=1500,
            )

            if digest:
                digest["generated_at"] = datetime.now(timezone.utc).isoformat()
                digest["stats"] = summary
                DAILY_DIGEST_FILE.write_text(
                    json.dumps(digest, indent=2, ensure_ascii=False), encoding="utf-8"
                )
                log.info(f"[Digest] Generated daily digest — {len(recent)} findings analyzed")

            # AI search term evolution
            evolve = _ai_call(
                AI_SEARCH_EVOLVE_SYSTEM,
                f"Current collection results:\n{json.dumps(summary, indent=2, ensure_ascii=False)}",
                model="gpt-4o", max_tokens=1000,
            )
            if evolve:
                # Auto-add new keywords
                new_terms = evolve.get("keyword_refinements", {}).get("add", [])
                if new_terms:
                    kw = _load_keywords()
                    existing = set()
                    for cat_list in kw.values():
                        existing.update(k.lower() for k in cat_list)
                    added = 0
                    for term in new_terms:
                        if term.lower() not in existing:
                            kw.setdefault("ai_suggested", []).append(term)
                            added += 1
                    if added:
                        KEYWORDS_FILE.write_text(
                            json.dumps(kw, indent=2, ensure_ascii=False), encoding="utf-8"
                        )
                        log.info(f"[Digest] AI added {added} new keywords")

            state["last_daily_digest"] = datetime.now(timezone.utc).isoformat()
            _save_state(state)

        except Exception as e:
            log.error(f"[Digest] Loop error: {e}")

        time.sleep(3600)  # Check every hour


# ═══════════════════════════════════════════════════════════════════════════════
# MAIN
# ═══════════════════════════════════════════════════════════════════════════════
def main():
    state = _load_state()
    log.info("=" * 60)
    log.info("DARK COLLECTOR — STARTING (8 loops + AI digest)")
    log.info(f"Findings so far: {state.get('findings_total', 0)}")
    log.info(f"False positives: {state.get('false_positives', 0)}")
    log.info(f"Tor circuits rotated: {state.get('tor_circuits_rotated', 0)}")
    log.info("=" * 60)

    # Check which optional features are available
    log.info(f"CertStream:  {'OK' if _HAS_CERTSTREAM else 'NOT INSTALLED (pip install certstream)'}")
    log.info(f"dnstwist:    {'OK' if _HAS_DNSTWIST else 'NOT INSTALLED (pip install dnstwist)'}")
    log.info(f"Tor/stem:    {'OK' if _HAS_STEM else 'NOT INSTALLED (pip install stem)'}")
    log.info(f"OpenAI:      {'OK' if _HAS_OPENAI and os.environ.get('OPENAI_API_KEY') else 'NOT AVAILABLE (no key)'}")
    log.info(f"Pastebin:    {'OK' if os.environ.get('PASTEBIN_API_KEY') else 'NO KEY (limited mode)'}")
    log.info(f"GitHub:      {'OK' if os.environ.get('GITHUB_TOKEN') else 'NO TOKEN (limited rate)'}")
    log.info(f"HIBP:        {'OK' if os.environ.get('HIBP_API_KEY') else 'NO KEY (skipping)'}")
    log.info(f"DeHashed:    {'OK' if os.environ.get('DEHASHED_API_KEY') else 'NO KEY (skipping)'}")

    # Initialize keyword file if missing
    if not KEYWORDS_FILE.exists():
        kw = _default_keywords()
        KEYWORDS_FILE.write_text(json.dumps(kw, indent=2, ensure_ascii=False), encoding="utf-8")
        log.info(f"Created {KEYWORDS_FILE} with default keywords")

    # Initialize onion targets if missing
    if not ONION_TARGETS_FILE.exists():
        targets = {
            "ransomware_dls": [],
            "forums": [],
            "paste_sites": [],
            "discovered": [],
            "notes": "Seed this file with .onion URLs. ransomware_dls URLs from: https://github.com/joshhighet/ransomwatch",
        }
        ONION_TARGETS_FILE.write_text(json.dumps(targets, indent=2, ensure_ascii=False), encoding="utf-8")
        log.info(f"Created {ONION_TARGETS_FILE} — seed with .onion URLs")

    threads = [
        threading.Thread(target=loop_paste_scraper,       args=(state,), name="L1-Paste",      daemon=True),
        threading.Thread(target=loop_breach_monitor,      args=(state,), name="L2-Breach",     daemon=True),
        threading.Thread(target=loop_certstream_watcher,  args=(state,), name="L3-CertStream", daemon=True),
        threading.Thread(target=loop_domain_squat_scanner,args=(state,), name="L4-DomainSquat",daemon=True),
        threading.Thread(target=loop_github_monitor,      args=(state,), name="L5-GitHub",     daemon=True),
        threading.Thread(target=loop_ransom_leak_tracker, args=(state,), name="L6-Ransom",     daemon=True),
        threading.Thread(target=loop_dark_web_crawler,    args=(state,), name="L7-DarkWeb",    daemon=True),
        threading.Thread(target=loop_threat_intel_feeds,  args=(state,), name="L8-IntelFeeds", daemon=True),
        threading.Thread(target=loop_daily_digest,        args=(state,), name="AI-Digest",     daemon=True),
    ]

    for t in threads:
        t.start()
        log.info(f"Started thread: {t.name}")
        time.sleep(1)  # Stagger starts

    log.info("\nAll 8 loops + AI digest running. Press Ctrl+C to stop.\n")
    try:
        while True:
            time.sleep(60)
            # Heartbeat
            log.info(
                f"[HEARTBEAT] findings={state.get('findings_total',0)} | "
                f"FP={state.get('false_positives',0)} | "
                f"tor_circuits={state.get('tor_circuits_rotated',0)} | "
                f"sources={json.dumps(state.get('findings_by_source',{}))}"
            )
    except KeyboardInterrupt:
        log.info("Shutting down dark collector...")
        _save_state(state)


if __name__ == "__main__":
    main()
