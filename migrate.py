#!/usr/bin/env python3
"""
Scanwave CyberIntel — JSONL → SQLite Migration
================================================
Idempotent: safe to run multiple times (INSERT OR IGNORE).
Original JSONL/JSON files are NEVER deleted.

Usage:  python migrate.py
"""

import json
import sys
import time
from pathlib import Path

# Ensure utf-8 output on Windows
if sys.platform == "win32":
    sys.stdout.reconfigure(encoding="utf-8")
    sys.stderr.reconfigure(encoding="utf-8")

# Add project root to path
PROJECT_ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(PROJECT_ROOT))

from app.database import init_db, get_conn, execute, executemany
from app.config import DATA_DIR, DB_PATH

# ── Critical subtype classification (copied from viewer.py) ─────────────────
_CYBER_SIGNALS = {
    "ddos", "d-dos", "defacement", "defaced", "data leak", "data breach", "databreach",
    "ransomware", "ransom", "malware", "trojan", "botnet", "exploit", "sql injection",
    "sqlmap", "webshell", "backdoor", "rootkit", "c2", "c&c", "command and control",
    "brute force", "credential stuffing", "credential dump",
    "pwned", "owned",
    "data breach", "breached", "data dump", "database dump", "wiper", "zero-day", "0day",
    "root access", "full access", "rce", "remote code execution",
    "phishing", "spear phishing", "xss", "cross-site",
    "تسريب بيانات", "تسريب معلومات", "قرصنة", "هاكر", "هاكرز",
    "فيروس", "هجوم سيبراني", "هجوم الكتروني", "هجوم إلكتروني",
    "دي دوس", "برامج خبيثة", "رانسوم", "فدية",
    "تم اختراق", "تم قرصنة", "تهكير",
    ".jo", ".gov.jo", ".com.jo", ".edu.jo", ".org.jo",
    "check-host", "dienet", "connection timed out", "connection refused",
    "layer7", "layer4", "http flood",
}
_AMBIGUOUS_CYBER = {"اختراق", "hacked", "hacking", "hack"}
_NATIONAL_SIGNALS = {
    "irgc", "iranian", "khamenei", "خامنئي", "حرس الثوري", "فاطميون",
    "soleimani", "سليماني", "quds force", "الحرس الثوري",
    "hezbollah", "حزب الله", "hamas", "حماس", "qassam", "قسام", "houthi", "حوثي",
    "انصار الله", "مقاومة", "جهاد اسلامي",
    "military", "عسكري", "troops", "army", "القوات المسلحة",
    "الجيش الاردني", "jordan armed forces", "القوات الجوية", "air force",
    "us base", "nato", "ain al asad", "العديد", "المفرق",
    ".mil.jo",
    "استخبارات", "intelligence", "gendarmerie", "الدرك",
    "border guard", "حرس الحدود", "مكافحة الإرهاب", "counter terrorism",
    "الأمن العام", "security directorate", "muwaffaq", "الموفق",
    "warfare", "warzone", "at war", "of war", "حرب", "missile", "صاروخ", "escalation", "تصعيد",
    "airstrike", "air strike", "عملية عسكرية", "military operation",
}

_SERVICE_SIGNALS = {
    "service", "services", "for sale", "for hire", "hire", "buy", "sell", "selling",
    "pricing", "price", "order", "contact us", "dm for", "dm me",
    "blackhat", "black hat", "professional hacking", "hacking service", "blackhat service",
    "we hack", "hack for", "hacker for",
    "we offer", "we provide", "available now", "24/7",
    "guaranteed results", "confidential", "affordable", "discount",
    "package", "combo", "premium", "vip",
    "خدمات", "خدمة", "للبيع", "للإيجار", "اشتري", "نبيع",
    "اسعار", "سعر", "اطلب", "تواصل معنا", "راسلنا",
    "نقدم", "نوفر", "متاح الآن", "خدمات احترافية",
    "خدمات هک", "سرویس", "فروش", "قیمت", "سفارش",
    "تماس بگیرید", "ارائه می‌دهیم",
}

_JORDAN_REFS = {
    "jordan", "jordanian", "amman",
    "الاردن", "الأردن", "أردن", "اردن", "اردني", "أردني", "الأردني", "الاردني",
    "عمان", "عمّان",
    "اردن", "اُردن",
    ".jo", ".gov.jo", ".com.jo", ".edu.jo", ".org.jo", ".mil.jo",
}


def _compute_critical_subtype(keyword_hits, text=""):
    """Classify a CRITICAL message by subtype."""
    if not keyword_hits:
        return "GENERAL"
    hits = [kw.lower() for kw in keyword_hits]
    txt = text.lower() if text else ""

    strong_cyber = any(sig in hit for hit in hits for sig in _CYBER_SIGNALS)
    ambig_cyber = any(sig in hit for hit in hits for sig in _AMBIGUOUS_CYBER)
    is_national = any(sig in hit for hit in hits for sig in _NATIONAL_SIGNALS)

    if not is_national and txt:
        is_national = any(sig in txt for sig in _NATIONAL_SIGNALS)

    is_cyber = strong_cyber
    if ambig_cyber and not is_national:
        is_cyber = True

    # Demote service/sale ads unless Jordan is mentioned
    if is_cyber and not is_national and txt:
        if sum(1 for sig in _SERVICE_SIGNALS if sig in txt) >= 2:
            if not any(ref in txt for ref in _JORDAN_REFS):
                return "GENERAL"

    if is_cyber and is_national:
        return "BOTH"
    if is_cyber:
        return "CYBER"
    if is_national:
        return "NATIONAL"
    return "GENERAL"


def migrate_messages():
    """Migrate messages.jsonl → messages table."""
    f = DATA_DIR / "messages.jsonl"
    if not f.exists():
        print("  [SKIP] messages.jsonl not found")
        return 0

    conn = get_conn()
    inserted = 0
    skipped = 0

    with open(f, "r", encoding="utf-8") as fh:
        batch = []
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                m = json.loads(line)
            except json.JSONDecodeError:
                skipped += 1
                continue

            priority = m.get("priority", "low")
            keyword_hits = m.get("keyword_hits", [])
            text_preview = m.get("text_preview", "")

            # Compute critical_subtype during migration
            if priority == "CRITICAL":
                subtype = _compute_critical_subtype(keyword_hits, text_preview)
            else:
                subtype = None

            batch.append((
                m.get("channel_username", ""),
                m.get("message_id", 0),
                m.get("timestamp_utc", ""),
                text_preview,
                m.get("full_text"),       # May be None
                priority,
                subtype,
                json.dumps(keyword_hits) if keyword_hits else None,
                json.dumps(m.get("matched_keywords")) if m.get("matched_keywords") else None,
                json.dumps(m.get("iocs")) if m.get("iocs") else None,
                m.get("language"),
                1 if m.get("has_media") else 0,
                m.get("media_path") or m.get("media_type"),
                1 if m.get("backfill") else 0,
                json.dumps(m, ensure_ascii=False),
            ))

            if len(batch) >= 1000:
                conn.executemany("""
                    INSERT OR IGNORE INTO messages
                    (channel_username, message_id, timestamp_utc, text_preview, full_text,
                     priority, critical_subtype, keyword_hits, matched_keywords, iocs,
                     language, has_media, media_path, backfill, raw_json)
                    VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
                """, batch)
                conn.commit()
                inserted += len(batch)
                batch = []

        if batch:
            conn.executemany("""
                INSERT OR IGNORE INTO messages
                (channel_username, message_id, timestamp_utc, text_preview, full_text,
                 priority, critical_subtype, keyword_hits, matched_keywords, iocs,
                 language, has_media, media_path, backfill, raw_json)
                VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
            """, batch)
            conn.commit()
            inserted += len(batch)

    # Rebuild FTS index
    print("  Rebuilding FTS index...")
    conn.execute("INSERT INTO messages_fts(messages_fts) VALUES('rebuild')")
    conn.commit()

    actual = conn.execute("SELECT COUNT(*) FROM messages").fetchone()[0]
    print(f"  Processed {inserted} lines, {actual} unique messages in DB (dupes ignored)")
    return actual


def migrate_enriched_alerts():
    """Migrate enriched_alerts.jsonl → enriched_alerts table."""
    f = DATA_DIR / "enriched_alerts.jsonl"
    if not f.exists():
        print("  [SKIP] enriched_alerts.jsonl not found")
        return 0

    conn = get_conn()
    batch = []
    with open(f, "r", encoding="utf-8") as fh:
        for line in fh:
            line = line.strip()
            if not line:
                continue
            try:
                m = json.loads(line)
            except json.JSONDecodeError:
                continue

            enrichment = m.get("ai_enrichment", {})
            batch.append((
                m.get("channel_username", ""),
                m.get("message_id", 0),
                json.dumps(enrichment, ensure_ascii=False) if enrichment else None,
            ))

    if batch:
        conn.executemany("""
            INSERT OR IGNORE INTO enriched_alerts
            (channel_username, original_message_id, enrichment_json)
            VALUES (?,?,?)
        """, batch)
        conn.commit()

    count = conn.execute("SELECT COUNT(*) FROM enriched_alerts").fetchone()[0]
    print(f"  {count} enriched alerts migrated")
    return count


def migrate_channels():
    """Migrate CHANNEL_TIERS + channels_config.json → channels table."""
    # Import CHANNEL_TIERS from viewer.py by parsing
    # (avoid importing the whole Flask app)
    channels_config_file = DATA_DIR / "channels_config.json"
    channels = {}

    # Load channels_config.json (this is the merged result of CHANNEL_TIERS + user edits)
    if channels_config_file.exists():
        try:
            channels = json.loads(channels_config_file.read_text(encoding="utf-8"))
        except Exception:
            pass

    # Also include any from CHANNEL_TIERS that might not be in config file
    # We import the dict from viewer.py module level
    try:
        # Read viewer.py and extract CHANNEL_TIERS dict via exec
        viewer_path = PROJECT_ROOT / "viewer.py"
        with open(viewer_path, "r", encoding="utf-8") as f:
            content = f.read()
        # Find the CHANNEL_TIERS block
        start = content.index("CHANNEL_TIERS = {")
        # Find matching closing brace
        depth = 0
        end = start
        for i, ch in enumerate(content[start:], start):
            if ch == '{':
                depth += 1
            elif ch == '}':
                depth -= 1
                if depth == 0:
                    end = i + 1
                    break
        tier_code = content[start:end]
        tier_ns = {}
        exec(tier_code, tier_ns)
        tiers = tier_ns.get("CHANNEL_TIERS", {})
        # Merge: config file overrides CHANNEL_TIERS
        merged = {k: dict(v) for k, v in tiers.items()}
        merged.update(channels)
        channels = merged
    except Exception as e:
        print(f"  [WARN] Could not parse CHANNEL_TIERS from viewer.py: {e}")

    conn = get_conn()
    batch = []
    for username, meta in channels.items():
        batch.append((
            username,
            meta.get("label", ""),
            meta.get("tier", 3),
            meta.get("status", "active"),
            meta.get("threat", "MEDIUM"),
            meta.get("apt_group"),
            meta.get("description"),
            json.dumps({k: v for k, v in meta.items()
                       if k not in ("label", "tier", "status", "threat", "apt_group", "description")},
                      ensure_ascii=False),
        ))

    if batch:
        conn.executemany("""
            INSERT OR IGNORE INTO channels
            (username, display_name, tier, status, threat, apt_group, description, metadata_json)
            VALUES (?,?,?,?,?,?,?,?)
        """, batch)
        conn.commit()

    count = conn.execute("SELECT COUNT(*) FROM channels").fetchone()[0]
    print(f"  {count} channels migrated")
    return count


def migrate_keywords():
    """Migrate keywords.json → keywords table."""
    f = DATA_DIR / "keywords.json"
    if not f.exists():
        print("  [SKIP] keywords.json not found")
        return 0

    conn = get_conn()
    data = json.loads(f.read_text(encoding="utf-8"))
    batch = []
    for priority, words in data.items():
        if isinstance(words, list):
            for word in words:
                batch.append((str(word).strip(), priority))

    if batch:
        conn.executemany("""
            INSERT OR IGNORE INTO keywords (word, priority) VALUES (?,?)
        """, batch)
        conn.commit()

    count = conn.execute("SELECT COUNT(*) FROM keywords").fetchone()[0]
    print(f"  {count} keywords migrated")
    return count


def migrate_discovered_channels():
    """Migrate discovered_channels.json → discovered_channels table."""
    f = DATA_DIR / "discovered_channels.json"
    if not f.exists():
        print("  [SKIP] discovered_channels.json not found")
        return 0

    conn = get_conn()
    data = json.loads(f.read_text(encoding="utf-8"))
    batch = []

    items = data.values() if isinstance(data, dict) else data
    for entry in items:
        if isinstance(entry, dict):
            batch.append((
                entry.get("username", ""),
                entry.get("display_name") or entry.get("title", ""),
                entry.get("source") or entry.get("reason", "").split(":")[0] if entry.get("reason") else None,
                entry.get("score", 0),
                entry.get("reason", ""),
                entry.get("discovered_at", ""),
                entry.get("status", "pending"),
                json.dumps({k: v for k, v in entry.items()
                           if k not in ("username", "display_name", "title", "source",
                                       "score", "reason", "discovered_at", "status")},
                          ensure_ascii=False),
            ))

    if batch:
        conn.executemany("""
            INSERT OR IGNORE INTO discovered_channels
            (username, display_name, source, score, reason, discovered_at, status, metadata_json)
            VALUES (?,?,?,?,?,?,?,?)
        """, batch)
        conn.commit()

    count = conn.execute("SELECT COUNT(*) FROM discovered_channels").fetchone()[0]
    print(f"  {count} discovered channels migrated")
    return count


def migrate_apt_research():
    """Migrate apt_ioc_research.json → apt_research table."""
    f = DATA_DIR / "apt_ioc_research.json"
    if not f.exists():
        print("  [SKIP] apt_ioc_research.json not found")
        return 0

    conn = get_conn()
    data = json.loads(f.read_text(encoding="utf-8"))
    batch = []

    for apt_name, info in data.items():
        researched_at = info.get("researched_at", "")
        for ioc in info.get("iocs", []):
            batch.append((
                apt_name,
                ioc.get("type", ""),
                ioc.get("value", ""),
                ioc.get("source", ""),
                ioc.get("context", ""),
                ioc.get("abuse_verdict"),
                ioc.get("abuse_score", -1),
                ioc.get("abuse_country"),
                researched_at,
            ))

    if batch:
        conn.executemany("""
            INSERT OR IGNORE INTO apt_research
            (apt_name, ioc_type, ioc_value, source, context,
             abuse_verdict, abuse_score, abuse_country, researched_at)
            VALUES (?,?,?,?,?,?,?,?,?)
        """, batch)
        conn.commit()

    count = conn.execute("SELECT COUNT(*) FROM apt_research").fetchone()[0]
    print(f"  {count} APT IOCs migrated from {len(data)} groups")
    return count


def migrate_abuseipdb_cache():
    """Migrate abuseipdb_cache.json → abuseipdb_cache table."""
    f = DATA_DIR / "abuseipdb_cache.json"
    if not f.exists():
        print("  [SKIP] abuseipdb_cache.json not found")
        return 0

    conn = get_conn()
    data = json.loads(f.read_text(encoding="utf-8"))
    batch = []

    for key, entry in data.items():
        d = entry.get("data", entry)
        ip = d.get("ipAddress", key)
        batch.append((
            ip,
            d.get("abuseConfidenceScore", 0),
            d.get("countryCode", ""),
            d.get("isp", ""),
            d.get("usageType", ""),
            d.get("domain", ""),
            json.dumps(entry, ensure_ascii=False),
        ))

    if batch:
        conn.executemany("""
            INSERT OR IGNORE INTO abuseipdb_cache
            (ip, score, country, isp, usage_type, domain, response_json)
            VALUES (?,?,?,?,?,?,?)
        """, batch)
        conn.commit()

    count = conn.execute("SELECT COUNT(*) FROM abuseipdb_cache").fetchone()[0]
    print(f"  {count} AbuseIPDB cache entries migrated")
    return count


def main():
    print("=" * 60)
    print("  Scanwave CyberIntel — JSONL → SQLite Migration")
    print("=" * 60)
    print(f"  Database: {DB_PATH}")
    print(f"  Data dir: {DATA_DIR}")
    print()

    t0 = time.time()

    # Initialize database (creates tables if needed)
    print("[1/7] Initializing database schema...")
    init_db(DB_PATH)
    print("  Done.")
    print()

    print("[2/7] Migrating messages...")
    migrate_messages()
    print()

    print("[3/7] Migrating enriched alerts...")
    migrate_enriched_alerts()
    print()

    print("[4/7] Migrating channels...")
    migrate_channels()
    print()

    print("[5/7] Migrating keywords...")
    migrate_keywords()
    print()

    print("[6/7] Migrating discovered channels...")
    migrate_discovered_channels()
    print()

    print("[7/7] Migrating APT research + AbuseIPDB cache...")
    migrate_apt_research()
    migrate_abuseipdb_cache()
    print()

    # Recompute critical_subtype for all CRITICAL messages (picks up filter changes)
    print("[8/8] Recomputing critical subtypes...")
    conn = get_conn()
    rows = conn.execute(
        "SELECT id, keyword_hits, text_preview, full_text FROM messages WHERE priority = 'CRITICAL'"
    ).fetchall()
    updated = 0
    for row in rows:
        kw_raw = row[1]
        kw = json.loads(kw_raw) if kw_raw else []
        text = row[2] or row[3] or ""
        new_sub = _compute_critical_subtype(kw, text)
        conn.execute("UPDATE messages SET critical_subtype = ? WHERE id = ?", (new_sub, row[0]))
        updated += 1
    conn.commit()
    print(f"  {updated} CRITICAL messages recomputed")
    # Show distribution
    dist = conn.execute(
        "SELECT critical_subtype, COUNT(*) FROM messages WHERE priority='CRITICAL' GROUP BY critical_subtype"
    ).fetchall()
    for sub, cnt in dist:
        print(f"    {sub or 'NULL'}: {cnt}")
    print()

    # Backfill media_path for existing downloaded media files
    print("[9/9] Backfilling media_path from existing files...")
    # Clear invalid media_path values (old migration stored media_type like "MessageMediaWebPage")
    conn.execute("UPDATE messages SET media_path = NULL WHERE media_path IS NOT NULL AND media_path NOT LIKE 'media/%'")
    conn.commit()
    media_root = DATA_DIR / "media"
    media_updated = 0
    if media_root.exists():
        for d in sorted(media_root.iterdir()):
            if not d.is_dir() or "_" not in d.name:
                continue
            # Directory name is {channel}_{message_id}
            parts = d.name.rsplit("_", 1)
            if len(parts) != 2:
                continue
            channel, msg_id_str = parts
            try:
                msg_id = int(msg_id_str)
            except ValueError:
                continue
            files = [f for f in d.iterdir() if f.is_file()]
            if files:
                rel_path = f"media/{d.name}/{files[0].name}"
                conn.execute(
                    "UPDATE messages SET media_path=?, has_media=1 WHERE channel_username=? AND message_id=?",
                    (rel_path, channel, msg_id)
                )
                media_updated += 1
        conn.commit()
    print(f"  {media_updated} messages linked to media files")
    print()

    elapsed = time.time() - t0
    print("=" * 60)
    print(f"  Migration complete in {elapsed:.1f}s")
    print(f"  Database: {DB_PATH} ({DB_PATH.stat().st_size / 1024 / 1024:.1f} MB)")
    print("  Original JSONL files preserved as backup.")
    print("=" * 60)


if __name__ == "__main__":
    main()
