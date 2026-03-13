"""
Scanwave CyberIntel Platform — Data Access Layer
==================================================
All database queries live here. Routes and services never touch raw SQL.
Thread-safe via thread-local connections in database.py.
"""

import json
from datetime import datetime, timedelta
from .database import query, execute, executemany, get_conn


# ═══════════════════════════════════════════════════════════════════════════════
#  MESSAGES
# ═══════════════════════════════════════════════════════════════════════════════

def get_messages(channel=None, priority=None, critical_subtype=None,
                 since=None, until=None, search=None, keyword=None,
                 limit=None, offset=0, order="DESC"):
    """Get messages with optional filters. Returns list of dicts."""
    sql = "SELECT * FROM messages WHERE 1=1"
    params = []

    if channel:
        sql += " AND channel_username = ?"
        params.append(channel)
    if priority and priority != "ALL":
        sql += " AND priority = ?"
        params.append(priority)
    if critical_subtype and critical_subtype != "ALL":
        sql += " AND critical_subtype = ?"
        params.append(critical_subtype)
    if since:
        sql += " AND timestamp_utc >= ?"
        params.append(since)
    if until:
        sql += " AND timestamp_utc <= ?"
        params.append(until + " 99" if len(until) == 10 else until)
    if search:
        # Use FTS5 for text search
        sql += " AND id IN (SELECT rowid FROM messages_fts WHERE messages_fts MATCH ?)"
        # Escape FTS special chars and use prefix matching
        safe_search = search.replace('"', '""')
        params.append(f'"{safe_search}"')
    if keyword:
        sql += " AND (keyword_hits LIKE ? OR text_preview LIKE ?)"
        kw_pat = f"%{keyword}%"
        params.extend([kw_pat, kw_pat])

    sql += f" ORDER BY timestamp_utc {order}"

    if limit:
        sql += " LIMIT ? OFFSET ?"
        params.extend([limit, offset])

    return query(sql, params)


def get_messages_by_subtypes(subtypes, limit=None):
    """Get messages matching specific critical_subtypes (for chat pipeline)."""
    placeholders = ",".join("?" * len(subtypes))
    sql = f"""
        SELECT * FROM messages
        WHERE critical_subtype IN ({placeholders})
        ORDER BY timestamp_utc DESC
    """
    params = list(subtypes)
    if limit:
        sql = sql.rstrip() + " LIMIT ?"
        params.append(limit)
    return query(sql, params)


def get_message_count(channel=None, priority=None, critical_subtype=None,
                      since=None, until=None):
    """Get count of messages matching filters."""
    sql = "SELECT COUNT(*) as cnt FROM messages WHERE 1=1"
    params = []

    if channel:
        sql += " AND channel_username = ?"
        params.append(channel)
    if priority and priority != "ALL":
        sql += " AND priority = ?"
        params.append(priority)
    if critical_subtype and critical_subtype != "ALL":
        sql += " AND critical_subtype = ?"
        params.append(critical_subtype)
    if since:
        sql += " AND timestamp_utc >= ?"
        params.append(since)
    if until:
        sql += " AND timestamp_utc <= ?"
        params.append(until + " 99" if len(until) == 10 else until)

    result = query(sql, params, one=True)
    return result["cnt"] if result else 0


def search_messages_fts(search_query, limit=200):
    """Full-text search using FTS5. Returns matching messages."""
    safe = search_query.replace('"', '""')
    sql = """
        SELECT m.* FROM messages m
        JOIN messages_fts f ON m.id = f.rowid
        WHERE messages_fts MATCH ?
        ORDER BY m.timestamp_utc DESC
        LIMIT ?
    """
    return query(sql, (f'"{safe}"', limit))


def get_messages_since(hours):
    """Get messages from the last N hours (for ai_agent)."""
    cutoff = (datetime.utcnow() - timedelta(hours=hours)).isoformat()
    return query(
        "SELECT * FROM messages WHERE timestamp_utc >= ? ORDER BY timestamp_utc DESC",
        (cutoff,)
    )


def get_all_messages():
    """Get all messages ordered by timestamp. Used for dashboard stats etc."""
    return query("SELECT * FROM messages ORDER BY timestamp_utc DESC")


def get_recent_messages(limit=50):
    """Get the N most recent messages."""
    return query(
        "SELECT * FROM messages ORDER BY timestamp_utc DESC LIMIT ?",
        (limit,)
    )


def insert_message(msg_dict):
    """Insert a single message. Returns rowid or None if duplicate."""
    keyword_hits = msg_dict.get("keyword_hits", [])
    iocs = msg_dict.get("iocs")
    try:
        return execute("""
            INSERT OR IGNORE INTO messages
            (channel_username, message_id, timestamp_utc, text_preview, full_text,
             priority, critical_subtype, keyword_hits, matched_keywords, iocs,
             language, has_media, media_path, backfill, raw_json)
            VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?,?)
        """, (
            msg_dict.get("channel_username", ""),
            msg_dict.get("message_id", 0),
            msg_dict.get("timestamp_utc", ""),
            msg_dict.get("text_preview", ""),
            msg_dict.get("full_text"),
            msg_dict.get("priority", "low"),
            msg_dict.get("critical_subtype"),
            json.dumps(keyword_hits) if keyword_hits else None,
            json.dumps(msg_dict.get("matched_keywords")) if msg_dict.get("matched_keywords") else None,
            json.dumps(iocs, ensure_ascii=False) if iocs else None,
            msg_dict.get("language"),
            1 if msg_dict.get("has_media") else 0,
            msg_dict.get("media_path"),
            1 if msg_dict.get("backfill") else 0,
            json.dumps(msg_dict, ensure_ascii=False),
        ))
    except Exception:
        return None


def get_dashboard_stats():
    """Compute dashboard statistics efficiently with SQL aggregation."""
    conn = get_conn()
    stats = {}

    # Total and priority counts
    row = conn.execute("""
        SELECT
            COUNT(*) as total,
            SUM(CASE WHEN priority='CRITICAL' THEN 1 ELSE 0 END) as critical,
            SUM(CASE WHEN priority='MEDIUM' THEN 1 ELSE 0 END) as medium,
            SUM(CASE WHEN priority='low' THEN 1 ELSE 0 END) as low_count
        FROM messages
    """).fetchone()
    stats["total"] = row[0]
    stats["critical"] = row[1]
    stats["medium"] = row[2]

    # Distinct channels with messages
    stats["channel_count"] = conn.execute(
        "SELECT COUNT(DISTINCT channel_username) FROM messages"
    ).fetchone()[0]

    # Channel ranking (top 20 by message count)
    stats["ch_ranking"] = [
        {"channel": r[0], "count": r[1], "last_critical": r[2]}
        for r in conn.execute("""
            SELECT channel_username, COUNT(*) as cnt,
                   MAX(CASE WHEN priority='CRITICAL' THEN timestamp_utc ELSE NULL END) as last_crit
            FROM messages
            GROUP BY channel_username
            ORDER BY cnt DESC
            LIMIT 20
        """).fetchall()
    ]

    return stats


def get_channel_trend(channel, days=30):
    """Get daily message counts for a channel over the last N days."""
    cutoff = (datetime.utcnow() - timedelta(days=days)).strftime("%Y-%m-%d")
    return query("""
        SELECT
            SUBSTR(timestamp_utc, 1, 10) as date,
            COUNT(*) as total,
            SUM(CASE WHEN priority='CRITICAL' THEN 1 ELSE 0 END) as critical,
            SUM(CASE WHEN priority='MEDIUM' THEN 1 ELSE 0 END) as medium
        FROM messages
        WHERE channel_username = ? AND timestamp_utc >= ?
        GROUP BY SUBSTR(timestamp_utc, 1, 10)
        ORDER BY date ASC
    """, (channel, cutoff))


def get_channel_iocs(channel, limit=50):
    """Get aggregated IOCs for a channel."""
    rows = query(
        "SELECT iocs FROM messages WHERE channel_username = ? AND iocs IS NOT NULL",
        (channel,)
    )
    # Aggregate IOCs by type and value
    ioc_counts = {}  # (type, value) → count
    for row in rows:
        try:
            iocs = json.loads(row["iocs"]) if isinstance(row["iocs"], str) else row["iocs"]
            if isinstance(iocs, dict):
                for ioc_type, values in iocs.items():
                    if isinstance(values, list):
                        for val in values:
                            key = (ioc_type, str(val))
                            ioc_counts[key] = ioc_counts.get(key, 0) + 1
        except (json.JSONDecodeError, TypeError):
            pass

    # Sort by count, return top N per type
    sorted_iocs = sorted(ioc_counts.items(), key=lambda x: -x[1])[:limit]
    return [{"type": k[0], "value": k[1], "count": v} for k, v in sorted_iocs]


def compact_messages():
    """Remove duplicate messages (equivalent to old compact operation)."""
    conn = get_conn()
    # Delete duplicates keeping lowest rowid
    deleted = conn.execute("""
        DELETE FROM messages WHERE id NOT IN (
            SELECT MIN(id) FROM messages GROUP BY channel_username, message_id
        )
    """).rowcount
    conn.execute("INSERT INTO messages_fts(messages_fts) VALUES('rebuild')")
    conn.commit()
    total = conn.execute("SELECT COUNT(*) FROM messages").fetchone()[0]
    return {"deleted": deleted, "remaining": total}


# ═══════════════════════════════════════════════════════════════════════════════
#  ENRICHMENTS
# ═══════════════════════════════════════════════════════════════════════════════

def get_enrichments():
    """Get all enrichments keyed by channel_username_message_id."""
    rows = query("SELECT * FROM enriched_alerts")
    result = {}
    for r in rows:
        key = f"{r['channel_username']}_{r['original_message_id']}"
        try:
            result[key] = json.loads(r["enrichment_json"]) if r["enrichment_json"] else {}
        except (json.JSONDecodeError, TypeError):
            result[key] = {}
    return result


def get_enrichment(channel_username, message_id):
    """Get enrichment for a single message."""
    row = query(
        "SELECT enrichment_json FROM enriched_alerts WHERE channel_username=? AND original_message_id=?",
        (channel_username, message_id), one=True
    )
    if row and row.get("enrichment_json"):
        try:
            return json.loads(row["enrichment_json"])
        except (json.JSONDecodeError, TypeError):
            pass
    return {}


def upsert_enrichment(channel_username, message_id, enrichment_dict):
    """Insert or update an enrichment."""
    execute("""
        INSERT INTO enriched_alerts (channel_username, original_message_id, enrichment_json)
        VALUES (?, ?, ?)
        ON CONFLICT(channel_username, original_message_id) DO UPDATE SET
            enrichment_json = excluded.enrichment_json,
            created_at = datetime('now')
    """, (channel_username, message_id, json.dumps(enrichment_dict, ensure_ascii=False)))


# ═══════════════════════════════════════════════════════════════════════════════
#  CHANNELS
# ═══════════════════════════════════════════════════════════════════════════════

def get_channels(status=None):
    """Get all channels, optionally filtered by status. Returns dict keyed by username."""
    if status:
        rows = query("SELECT * FROM channels WHERE status = ?", (status,))
    else:
        rows = query("SELECT * FROM channels")

    result = {}
    for r in rows:
        meta = {}
        if r.get("metadata_json"):
            try:
                meta = json.loads(r["metadata_json"])
            except (json.JSONDecodeError, TypeError):
                pass
        result[r["username"]] = {
            "tier": r["tier"],
            "label": r["display_name"] or r["username"],
            "threat": r["threat"],
            "status": r["status"],
            "apt_group": r.get("apt_group"),
            "description": r.get("description"),
            **meta,
        }
    return result


def get_channel(username):
    """Get a single channel by username."""
    row = query("SELECT * FROM channels WHERE username = ?", (username,), one=True)
    if not row:
        return None
    meta = {}
    if row.get("metadata_json"):
        try:
            meta = json.loads(row["metadata_json"])
        except (json.JSONDecodeError, TypeError):
            pass
    return {
        "username": row["username"],
        "tier": row["tier"],
        "label": row["display_name"] or row["username"],
        "threat": row["threat"],
        "status": row["status"],
        "apt_group": row.get("apt_group"),
        "description": row.get("description"),
        **meta,
    }


def upsert_channel(username, **kwargs):
    """Insert or update a channel."""
    label = kwargs.get("label", kwargs.get("display_name", ""))
    tier = kwargs.get("tier", 3)
    status = kwargs.get("status", "active")
    threat = kwargs.get("threat", "MEDIUM")
    apt_group = kwargs.get("apt_group")
    description = kwargs.get("description")

    # Everything else goes into metadata_json
    known_keys = {"label", "display_name", "tier", "status", "threat", "apt_group", "description", "username"}
    extra = {k: v for k, v in kwargs.items() if k not in known_keys}

    execute("""
        INSERT INTO channels (username, display_name, tier, status, threat, apt_group, description, metadata_json)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(username) DO UPDATE SET
            display_name = excluded.display_name,
            tier = excluded.tier,
            status = excluded.status,
            threat = excluded.threat,
            apt_group = excluded.apt_group,
            description = excluded.description,
            metadata_json = excluded.metadata_json
    """, (username, label, tier, status, threat, apt_group, description,
          json.dumps(extra, ensure_ascii=False) if extra else None))


def delete_channel(username):
    """Delete a channel by username."""
    execute("DELETE FROM channels WHERE username = ?", (username,))


def get_channel_count():
    """Get total, active, and banned channel counts."""
    conn = get_conn()
    total = conn.execute("SELECT COUNT(*) FROM channels").fetchone()[0]
    banned = conn.execute("SELECT COUNT(*) FROM channels WHERE status='banned'").fetchone()[0]
    return {"total": total, "active": total - banned, "banned": banned}


# ═══════════════════════════════════════════════════════════════════════════════
#  KEYWORDS
# ═══════════════════════════════════════════════════════════════════════════════

def get_keywords(priority=None):
    """Get keywords. If priority given, returns list. Otherwise returns {critical: [], medium: []}."""
    if priority:
        rows = query("SELECT word FROM keywords WHERE priority = ? ORDER BY word", (priority,))
        return [r["word"] for r in rows]
    else:
        result = {"critical": [], "medium": []}
        rows = query("SELECT word, priority FROM keywords ORDER BY priority, word")
        for r in rows:
            p = r["priority"]
            if p in result:
                result[p].append(r["word"])
        return result


def add_keyword(word, priority, source="manual"):
    """Add a keyword."""
    execute(
        "INSERT OR IGNORE INTO keywords (word, priority, source) VALUES (?, ?, ?)",
        (word.strip(), priority, source)
    )


def remove_keyword(word, priority):
    """Remove a keyword."""
    execute("DELETE FROM keywords WHERE word = ? AND priority = ?", (word.strip(), priority))


def save_keywords(keywords_dict):
    """Replace all keywords with new dict {critical: [], medium: []}."""
    conn = get_conn()
    conn.execute("DELETE FROM keywords")
    batch = []
    for priority, words in keywords_dict.items():
        if isinstance(words, list):
            for word in words:
                batch.append((str(word).strip(), priority, "manual"))
    if batch:
        conn.executemany(
            "INSERT OR IGNORE INTO keywords (word, priority, source) VALUES (?, ?, ?)",
            batch
        )
    conn.commit()


# ═══════════════════════════════════════════════════════════════════════════════
#  DISCOVERED CHANNELS
# ═══════════════════════════════════════════════════════════════════════════════

def get_discovered_channels(status=None):
    """Get discovered channels, optionally filtered by status."""
    if status:
        rows = query(
            "SELECT * FROM discovered_channels WHERE status = ? ORDER BY discovered_at DESC",
            (status,)
        )
    else:
        rows = query("SELECT * FROM discovered_channels ORDER BY discovered_at DESC")

    result = {}
    for r in rows:
        entry = dict(r)
        if entry.get("metadata_json"):
            try:
                meta = json.loads(entry["metadata_json"])
                entry.update(meta)
            except (json.JSONDecodeError, TypeError):
                pass
        del entry["metadata_json"]
        result[r["username"]] = entry
    return result


def upsert_discovered_channel(username, **kwargs):
    """Insert or update a discovered channel."""
    known = {"display_name", "source", "score", "reason", "discovered_at", "status"}
    extra = {k: v for k, v in kwargs.items() if k not in known and k != "username"}

    execute("""
        INSERT INTO discovered_channels
        (username, display_name, source, score, reason, discovered_at, status, metadata_json)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(username) DO UPDATE SET
            display_name = COALESCE(excluded.display_name, discovered_channels.display_name),
            source = COALESCE(excluded.source, discovered_channels.source),
            score = COALESCE(excluded.score, discovered_channels.score),
            reason = COALESCE(excluded.reason, discovered_channels.reason),
            status = COALESCE(excluded.status, discovered_channels.status),
            metadata_json = COALESCE(excluded.metadata_json, discovered_channels.metadata_json)
    """, (
        username,
        kwargs.get("display_name"),
        kwargs.get("source"),
        kwargs.get("score", 0),
        kwargs.get("reason", ""),
        kwargs.get("discovered_at", datetime.utcnow().isoformat()),
        kwargs.get("status", "pending"),
        json.dumps(extra, ensure_ascii=False) if extra else None,
    ))


def update_discovered_status(username, status):
    """Update the status of a discovered channel."""
    execute(
        "UPDATE discovered_channels SET status = ? WHERE username = ?",
        (status, username)
    )


# ═══════════════════════════════════════════════════════════════════════════════
#  APT IOC RESEARCH
# ═══════════════════════════════════════════════════════════════════════════════

def get_apt_research(apt_name=None, verdict=None, ioc_type=None):
    """Get APT research IOCs with optional filters."""
    sql = "SELECT * FROM apt_research WHERE 1=1"
    params = []

    if apt_name:
        sql += " AND apt_name = ?"
        params.append(apt_name)
    if verdict:
        sql += " AND abuse_verdict = ?"
        params.append(verdict)
    if ioc_type:
        sql += " AND ioc_type = ?"
        params.append(ioc_type)

    sql += " ORDER BY researched_at DESC"
    return query(sql, params)


def upsert_apt_ioc(apt_name, ioc_value, ioc_type, source, **kwargs):
    """Insert or update an APT research IOC."""
    execute("""
        INSERT INTO apt_research
        (apt_name, ioc_type, ioc_value, source, context,
         abuse_verdict, abuse_score, abuse_country, researched_at)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(apt_name, ioc_value) DO UPDATE SET
            ioc_type = excluded.ioc_type,
            source = excluded.source,
            context = COALESCE(excluded.context, apt_research.context),
            abuse_verdict = COALESCE(excluded.abuse_verdict, apt_research.abuse_verdict),
            abuse_score = COALESCE(excluded.abuse_score, apt_research.abuse_score),
            abuse_country = COALESCE(excluded.abuse_country, apt_research.abuse_country),
            researched_at = excluded.researched_at
    """, (
        apt_name, ioc_type, ioc_value, source,
        kwargs.get("context"),
        kwargs.get("abuse_verdict"),
        kwargs.get("abuse_score", -1),
        kwargs.get("abuse_country"),
        kwargs.get("researched_at", datetime.utcnow().isoformat()),
    ))


def get_blocklist(apt=None, ioc_type=None, verdict=None, search=None, limit=1000):
    """Get deduplicated blocklist IOCs across all APTs."""
    sql = "SELECT * FROM apt_research WHERE 1=1"
    params = []

    if apt:
        sql += " AND apt_name = ?"
        params.append(apt)
    if ioc_type:
        sql += " AND ioc_type = ?"
        params.append(ioc_type)
    if verdict:
        sql += " AND abuse_verdict = ?"
        params.append(verdict)
    if search:
        sql += " AND (ioc_value LIKE ? OR context LIKE ?)"
        pat = f"%{search}%"
        params.extend([pat, pat])

    # Order by verdict severity then score
    sql += """
        ORDER BY
            CASE abuse_verdict
                WHEN 'MALICIOUS' THEN 0
                WHEN 'SUSPICIOUS' THEN 1
                WHEN 'UNVERIFIED' THEN 2
                WHEN 'CLEAN' THEN 3
                ELSE 4
            END,
            abuse_score DESC
        LIMIT ?
    """
    params.append(limit)
    return query(sql, params)


def get_apt_research_stats():
    """Get summary stats for the blocklist."""
    conn = get_conn()
    stats = {}
    stats["total_iocs"] = conn.execute("SELECT COUNT(*) FROM apt_research").fetchone()[0]
    stats["total_apts"] = conn.execute("SELECT COUNT(DISTINCT apt_name) FROM apt_research").fetchone()[0]

    for verdict in ("MALICIOUS", "SUSPICIOUS", "CLEAN", "UNVERIFIED"):
        stats[verdict.lower()] = conn.execute(
            "SELECT COUNT(*) FROM apt_research WHERE abuse_verdict = ?", (verdict,)
        ).fetchone()[0]

    return stats


def clear_apt_research(apt_name):
    """Clear all research IOCs for an APT (before re-research)."""
    execute("DELETE FROM apt_research WHERE apt_name = ?", (apt_name,))


# ═══════════════════════════════════════════════════════════════════════════════
#  ABUSEIPDB CACHE
# ═══════════════════════════════════════════════════════════════════════════════

def get_abuse_cache(ip):
    """Get cached AbuseIPDB result for an IP."""
    row = query("SELECT * FROM abuseipdb_cache WHERE ip = ?", (ip,), one=True)
    if row and row.get("response_json"):
        try:
            return json.loads(row["response_json"])
        except (json.JSONDecodeError, TypeError):
            pass
    return None


def set_abuse_cache(ip, data):
    """Cache an AbuseIPDB result."""
    d = data.get("data", data)
    execute("""
        INSERT INTO abuseipdb_cache (ip, score, country, isp, usage_type, domain, response_json)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        ON CONFLICT(ip) DO UPDATE SET
            score = excluded.score,
            country = excluded.country,
            isp = excluded.isp,
            usage_type = excluded.usage_type,
            domain = excluded.domain,
            response_json = excluded.response_json,
            cached_at = datetime('now')
    """, (
        ip,
        d.get("abuseConfidenceScore", 0),
        d.get("countryCode", ""),
        d.get("isp", ""),
        d.get("usageType", ""),
        d.get("domain", ""),
        json.dumps(data, ensure_ascii=False),
    ))


# ═══════════════════════════════════════════════════════════════════════════════
#  AI AGENT STATE
# ═══════════════════════════════════════════════════════════════════════════════

def get_ai_state(key):
    """Get AI agent state value."""
    row = query("SELECT value_json FROM ai_agent_state WHERE key = ?", (key,), one=True)
    if row and row.get("value_json"):
        try:
            return json.loads(row["value_json"])
        except (json.JSONDecodeError, TypeError):
            pass
    return None


def set_ai_state(key, value):
    """Set AI agent state value."""
    execute("""
        INSERT INTO ai_agent_state (key, value_json, updated_at)
        VALUES (?, ?, datetime('now'))
        ON CONFLICT(key) DO UPDATE SET
            value_json = excluded.value_json,
            updated_at = datetime('now')
    """, (key, json.dumps(value, ensure_ascii=False)))
