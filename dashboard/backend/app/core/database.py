import datetime
import sqlite3
from typing import Generator
from app.config import VAULT_DB_PATH


def get_db_connection() -> sqlite3.Connection:
    """Retorna una conexión a SQLite configurada con Row factory y WAL mode."""
    conn = sqlite3.connect(str(VAULT_DB_PATH), check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    return conn


def init_db():
    """Inicializa el esquema de tablas en SQLite."""
    conn = get_db_connection()
    with conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS dashboard_sessions (
                token_hash TEXT PRIMARY KEY,
                username TEXT NOT NULL,
                expires_at INTEGER NOT NULL
            );
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS api_keys (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                provider TEXT NOT NULL UNIQUE,
                label TEXT NOT NULL,
                service_type TEXT NOT NULL,
                encrypted_key TEXT NOT NULL,
                base_url TEXT,
                model_name TEXT,
                is_active INTEGER DEFAULT 1,
                last_checked TEXT,
                status TEXT DEFAULT 'untested',
                status_message TEXT,
                created_at TEXT,
                updated_at TEXT
            );
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS dashboard_settings (
                key TEXT PRIMARY KEY,
                value TEXT,
                updated_at TEXT
            );
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS engagement_metadata (
                id TEXT PRIMARY KEY,
                engagement_type TEXT NOT NULL,
                tags TEXT,
                favorite INTEGER DEFAULT 0,
                archived INTEGER DEFAULT 0,
                updated_at TEXT
            );
        """)

        conn.execute("""
            CREATE TABLE IF NOT EXISTS proxy_audit_log (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                provider TEXT NOT NULL,
                model TEXT NOT NULL,
                service_type TEXT NOT NULL,
                status TEXT NOT NULL,
                latency_ms INTEGER,
                tokens_used INTEGER DEFAULT 0,
                error_message TEXT,
                created_at TEXT
            );
        """)
    conn.close()


def get_db() -> Generator[sqlite3.Connection, None, None]:
    """Dependency generator para endpoints de FastAPI."""
    conn = get_db_connection()
    try:
        yield conn
    finally:
        conn.close()
