"""
SQLite database for Deezy memory.
Provides persistent structured memory storage.
"""

import os
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import List, Optional

SCHEMA = """
-- Business profile
CREATE TABLE IF NOT EXISTS business_profile (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Products
CREATE TABLE IF NOT EXISTS products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    asin TEXT UNIQUE NOT NULL,
    title TEXT NOT NULL,
    description TEXT,
    price TEXT,
    currency TEXT DEFAULT 'USD',
    rating REAL,
    rating_count INTEGER,
    image_url TEXT,
    product_url TEXT,
    affiliate_url TEXT,
    category TEXT,
    subcategory TEXT,
    tags TEXT,  -- JSON array
    source TEXT,
    source_data TEXT,  -- JSON
    score REAL,
    score_details TEXT,  -- JSON
    is_published BOOLEAN DEFAULT FALSE,
    published_at TIMESTAMP,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Product evaluations
CREATE TABLE IF NOT EXISTS product_evaluations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER REFERENCES products(id),
    evaluator TEXT,
    relevance REAL,
    search_demand REAL,
    competition REAL,
    price_score REAL,
    commission_potential REAL,
    product_quality REAL,
    content_potential REAL,
    pinterest_potential REAL,
    uniqueness REAL,
    existing_coverage REAL,
    overall_score REAL,
    notes TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Pinterest data
CREATE TABLE IF NOT EXISTS pinterest_pins (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pin_id TEXT UNIQUE NOT NULL,
    board_id TEXT,
    title TEXT,
    description TEXT,
    image_url TEXT,
    link TEXT,
    affiliate_link TEXT,
    impressions INTEGER DEFAULT 0,
    saves INTEGER DEFAULT 0,
    outbound_clicks INTEGER DEFAULT 0,
    engagement_rate REAL,
    keywords TEXT,  -- JSON array
    is_published BOOLEAN DEFAULT FALSE,
    published_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Pin performance history
CREATE TABLE IF NOT EXISTS pin_performance (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    pin_id INTEGER REFERENCES pinterest_pins(id),
    date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    impressions INTEGER DEFAULT 0,
    saves INTEGER DEFAULT 0,
    outbound_clicks INTEGER DEFAULT 0,
    engagement_rate REAL
);

-- Pinterest boards
CREATE TABLE IF NOT EXISTS pinterest_boards (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    board_id TEXT UNIQUE NOT NULL,
    name TEXT NOT NULL,
    description TEXT,
    category TEXT,
    pin_count INTEGER DEFAULT 0,
    follower_count INTEGER DEFAULT 0,
    is_secret BOOLEAN DEFAULT FALSE,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Board analytics
CREATE TABLE IF NOT EXISTS board_analytics (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    board_id INTEGER REFERENCES pinterest_boards(id),
    date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    impressions INTEGER DEFAULT 0,
    saves INTEGER DEFAULT 0,
    outbound_clicks INTEGER DEFAULT 0,
    engagement_rate REAL,
    pin_count INTEGER DEFAULT 0,
    follower_count INTEGER DEFAULT 0
);

-- Website products (synced from website)
CREATE TABLE IF NOT EXISTS website_products (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    product_id INTEGER REFERENCES products(id),
    page TEXT,  -- index.html, best-sellers.html, etc.
    section TEXT,  -- trending, featured, category
    position INTEGER,
    html_content TEXT,
    last_checked TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_valid BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Analytics snapshots
CREATE TABLE IF NOT EXISTS analytics_snapshots (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    page_views INTEGER,
    unique_visitors INTEGER,
    bounce_rate REAL,
    avg_session_duration REAL,
    top_pages TEXT,  -- JSON
    top_referrers TEXT,  -- JSON
    conversions INTEGER,
    revenue REAL,
    source TEXT,
    raw_data TEXT  -- JSON
);

-- Tasks
CREATE TABLE IF NOT EXISTS tasks (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    description TEXT,
    objective TEXT,
    status TEXT DEFAULT 'pending',
    risk_level TEXT DEFAULT 'low',
    parent_task_id INTEGER REFERENCES tasks(id),
    assigned_tool TEXT,
    input_data TEXT,  -- JSON
    output_data TEXT,  -- JSON
    error TEXT,
    approval_required BOOLEAN DEFAULT FALSE,
    approved_by TEXT,
    approved_at TIMESTAMP,
    started_at TIMESTAMP,
    completed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Events
CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    event_type TEXT NOT NULL,
    task_id INTEGER REFERENCES tasks(id),
    source TEXT,
    payload TEXT,  -- JSON
    processed BOOLEAN DEFAULT FALSE,
    processed_at TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Agent decisions (for learning)
CREATE TABLE IF NOT EXISTS agent_decisions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id INTEGER REFERENCES tasks(id),
    context TEXT,  -- JSON
    decision TEXT,
    reasoning TEXT,
    tool_calls TEXT,  -- JSON
    outcome TEXT,
    feedback TEXT,
    confidence REAL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Strategies (learned patterns)
CREATE TABLE IF NOT EXISTS strategies (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT NOT NULL,
    description TEXT,
    category TEXT,
    is_successful BOOLEAN DEFAULT FALSE,
    success_count INTEGER DEFAULT 0,
    failure_count INTEGER DEFAULT 0,
    conditions TEXT,  -- JSON
    actions TEXT,  -- JSON
    metadata TEXT,  -- JSON
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- User instructions
CREATE TABLE IF NOT EXISTS user_instructions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    instruction TEXT NOT NULL,
    category TEXT,
    priority INTEGER DEFAULT 0,
    is_active BOOLEAN DEFAULT TRUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Agent observations
CREATE TABLE IF NOT EXISTS observations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    category TEXT,
    title TEXT,
    description TEXT,
    severity TEXT,  -- info, warning, critical
    source TEXT,
    data TEXT,  -- JSON
    acknowledged BOOLEAN DEFAULT FALSE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Agent decisions
CREATE TABLE IF NOT EXISTS decisions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    task_id INTEGER REFERENCES tasks(id),
    context TEXT,  -- JSON
    decision TEXT,
    reasoning TEXT,
    tool_calls TEXT,  -- JSON
    outcome TEXT,
    feedback TEXT,
    confidence REAL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Memories (long-term memory)
CREATE TABLE IF NOT EXISTS memories (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    category TEXT,  -- fact, preference, project, task, decision, observation, conversation
    content TEXT NOT NULL,
    tags TEXT,  -- JSON array
    importance REAL DEFAULT 1.0,  -- 0.0 to 1.0
    source TEXT,  -- user, agent, system
    access_count INTEGER DEFAULT 0,
    last_accessed TIMESTAMP,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

-- Conversation history
CREATE TABLE IF NOT EXISTS conversation_history (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id TEXT,
    role TEXT,  -- user, assistant, tool
    content TEXT NOT NULL,
    metadata TEXT,  -- JSON
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

"""


class Database:
    """SQLite database wrapper for Deezy."""

    def __init__(self, db_path: str = "data/deezy.db"):
        self.db_path = Path(db_path)
        self.db_path.parent.mkdir(parents=True, exist_ok=True)
        self._conn: Optional[sqlite3.Connection] = None
        self._init_db()

    def _get_connection(self) -> sqlite3.Connection:
        """Get or create database connection."""
        if self._conn is None:
            self._conn = sqlite3.connect(self.db_path, check_same_thread=False)
            self._conn.row_factory = sqlite3.Row
            self._conn.execute("PRAGMA foreign_keys = ON")
        return self._conn

    def _init_db(self):
        """Initialize database schema."""
        conn = self._get_connection()
        conn.executescript(SCHEMA)
        conn.commit()

    @contextmanager
    def transaction(self):
        """Context manager for database transactions."""
        conn = self._get_connection()
        try:
            yield conn
            conn.commit()
        except Exception:
            conn.rollback()
            raise

    def execute(self, query: str, params: tuple = ()) -> sqlite3.Cursor:
        """Execute a query."""
        conn = self._get_connection()
        cursor = conn.execute(query, params)
        conn.commit()
        return cursor

    def fetchone(self, query: str, params: tuple = ()) -> Optional[sqlite3.Row]:
        """Fetch a single row."""
        conn = self._get_connection()
        return conn.execute(query, params).fetchone()

    def fetchall(self, query: str, params: tuple = ()) -> List[sqlite3.Row]:
        """Fetch all rows."""
        conn = self._get_connection()
        return conn.execute(query, params).fetchall()

    def close(self):
        """Close database connection."""
        if self._conn:
            self._conn.close()
            self._conn = None


# Global database instance
_db: Optional[Database] = None


def default_db_path() -> str:
    """Database location: DEEZY_DB_PATH if set, /tmp on Vercel (read-only elsewhere), else data/deezy.db."""
    if os.environ.get("DEEZY_DB_PATH"):
        return os.environ["DEEZY_DB_PATH"]
    return "/tmp/deezy.db" if os.environ.get("VERCEL") else "data/deezy.db"


def get_db(db_path: Optional[str] = None) -> Database:
    """Get global database instance."""
    global _db
    if _db is None:
        _db = Database(db_path or default_db_path())
    return _db


def init_db(db_path: Optional[str] = None):
    """Initialize database."""
    get_db(db_path)


__all__ = [
    "Database",
    "get_db",
    "init_db",
    "default_db_path",
]
