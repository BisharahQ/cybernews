"""
Scanwave CyberIntel Platform — SQLite Database Layer
=====================================================
WAL mode for concurrent reads + single writer.
Thread-local connections for Flask thread safety.
"""

import sqlite3
import threading
from pathlib import Path

_local = threading.local()
_db_path = None  # Set by init_db()

SCHEMA_SQL = """
-- ── Messages (replaces messages.jsonl, alerts.jsonl, iocs.jsonl) ────────────
CREATE TABLE IF NOT EXISTS messages (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    channel_username TEXT NOT NULL,
    message_id INTEGER NOT NULL,
    timestamp_utc TEXT NOT NULL,
    text_preview TEXT,
    full_text TEXT,
    priority TEXT DEFAULT 'low',
    critical_subtype TEXT,
    keyword_hits TEXT,
    matched_keywords TEXT,
    iocs TEXT,
    language TEXT,
    has_media INTEGER DEFAULT 0,
    media_path TEXT,
    backfill INTEGER DEFAULT 0,
    raw_json TEXT,
    UNIQUE(channel_username, message_id)
);
CREATE INDEX IF NOT EXISTS idx_msg_timestamp ON messages(timestamp_utc);
CREATE INDEX IF NOT EXISTS idx_msg_channel ON messages(channel_username);
CREATE INDEX IF NOT EXISTS idx_msg_priority ON messages(priority);
CREATE INDEX IF NOT EXISTS idx_msg_subtype ON messages(critical_subtype);
CREATE INDEX IF NOT EXISTS idx_msg_backfill ON messages(backfill);

-- ── Full-text search ────────────────────────────────────────────────────────
CREATE VIRTUAL TABLE IF NOT EXISTS messages_fts USING fts5(
    text_preview, full_text,
    content='messages', content_rowid='id'
);

-- FTS sync triggers
CREATE TRIGGER IF NOT EXISTS msg_fts_ai AFTER INSERT ON messages BEGIN
    INSERT INTO messages_fts(rowid, text_preview, full_text)
    VALUES (new.id, new.text_preview, new.full_text);
END;
CREATE TRIGGER IF NOT EXISTS msg_fts_ad AFTER DELETE ON messages BEGIN
    INSERT INTO messages_fts(messages_fts, rowid, text_preview, full_text)
    VALUES ('delete', old.id, old.text_preview, old.full_text);
END;
CREATE TRIGGER IF NOT EXISTS msg_fts_au AFTER UPDATE ON messages BEGIN
    INSERT INTO messages_fts(messages_fts, rowid, text_preview, full_text)
    VALUES ('delete', old.id, old.text_preview, old.full_text);
    INSERT INTO messages_fts(rowid, text_preview, full_text)
    VALUES (new.id, new.text_preview, new.full_text);
END;

-- ── Enriched alerts ─────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS enriched_alerts (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    channel_username TEXT,
    original_message_id INTEGER,
    enrichment_json TEXT,
    created_at TEXT DEFAULT (datetime('now')),
    UNIQUE(channel_username, original_message_id)
);

-- ── Channels (replaces channels_config.json + CHANNEL_TIERS) ────────────────
CREATE TABLE IF NOT EXISTS channels (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    display_name TEXT,
    tier INTEGER DEFAULT 3,
    status TEXT DEFAULT 'active',
    threat TEXT DEFAULT 'MEDIUM',
    apt_group TEXT,
    description TEXT,
    added_at TEXT DEFAULT (datetime('now')),
    metadata_json TEXT
);

-- ── Keywords (replaces keywords.json) ───────────────────────────────────────
CREATE TABLE IF NOT EXISTS keywords (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    word TEXT NOT NULL,
    priority TEXT NOT NULL,
    category TEXT,
    added_at TEXT DEFAULT (datetime('now')),
    source TEXT DEFAULT 'manual',
    UNIQUE(word, priority)
);

-- ── Discovered channels ─────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS discovered_channels (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT UNIQUE NOT NULL,
    display_name TEXT,
    source TEXT,
    score INTEGER DEFAULT 0,
    reason TEXT,
    discovered_at TEXT DEFAULT (datetime('now')),
    status TEXT DEFAULT 'pending',
    metadata_json TEXT
);

-- ── APT IOC research cache ──────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS apt_research (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    apt_name TEXT NOT NULL,
    ioc_type TEXT,
    ioc_value TEXT NOT NULL,
    source TEXT,
    context TEXT,
    abuse_verdict TEXT,
    abuse_score INTEGER,
    abuse_country TEXT,
    researched_at TEXT DEFAULT (datetime('now')),
    UNIQUE(apt_name, ioc_value)
);
CREATE INDEX IF NOT EXISTS idx_apt_research_apt ON apt_research(apt_name);
CREATE INDEX IF NOT EXISTS idx_apt_research_verdict ON apt_research(abuse_verdict);

-- ── AbuseIPDB cache ─────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS abuseipdb_cache (
    ip TEXT PRIMARY KEY,
    score INTEGER,
    country TEXT,
    isp TEXT,
    usage_type TEXT,
    domain TEXT,
    response_json TEXT,
    cached_at TEXT DEFAULT (datetime('now'))
);

-- ── AI agent state ──────────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS ai_agent_state (
    key TEXT PRIMARY KEY,
    value_json TEXT,
    updated_at TEXT DEFAULT (datetime('now'))
);

-- ── Timing analysis (replaces timing_analysis.jsonl) ────────────────────────
CREATE TABLE IF NOT EXISTS timing_analysis (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    channel_username TEXT,
    message_id INTEGER,
    data_json TEXT,
    created_at TEXT DEFAULT (datetime('now'))
);
"""


def init_db(db_path):
    """Initialize the database: create tables, enable WAL mode."""
    global _db_path
    _db_path = str(db_path)

    Path(db_path).parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    conn.execute("PRAGMA busy_timeout=5000")
    conn.executescript(SCHEMA_SQL)
    conn.commit()
    conn.close()


def get_conn():
    """Get a thread-local database connection."""
    if not hasattr(_local, "conn") or _local.conn is None:
        if _db_path is None:
            raise RuntimeError("Database not initialized. Call init_db() first.")
        conn = sqlite3.connect(_db_path)
        conn.row_factory = sqlite3.Row
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout=5000")
        _local.conn = conn
    return _local.conn


def close_conn():
    """Close the thread-local connection (call on thread exit)."""
    if hasattr(_local, "conn") and _local.conn is not None:
        _local.conn.close()
        _local.conn = None


def query(sql, params=(), one=False):
    """Execute a SELECT query and return rows as dicts."""
    conn = get_conn()
    cur = conn.execute(sql, params)
    rows = cur.fetchall()
    if one:
        return dict(rows[0]) if rows else None
    return [dict(r) for r in rows]


def execute(sql, params=()):
    """Execute an INSERT/UPDATE/DELETE and return lastrowid."""
    conn = get_conn()
    cur = conn.execute(sql, params)
    conn.commit()
    return cur.lastrowid


def executemany(sql, param_list):
    """Execute a batch INSERT/UPDATE."""
    conn = get_conn()
    conn.executemany(sql, param_list)
    conn.commit()


def execute_script(sql):
    """Execute a multi-statement SQL script."""
    conn = get_conn()
    conn.executescript(sql)
    conn.commit()
