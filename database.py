"""
Persistent storage for the bedside monitor.

Schema:
  sessions  – one row per application run
  readings  – timestamped sensor + risk-score snapshots
  alerts    – timestamped clinical alert events
"""

import csv
import sqlite3
import time
from pathlib import Path

DB_PATH = Path(__file__).parent / "monitor_data.db"


def _connect() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    return conn


def initialize_db() -> None:
    with _connect() as conn:
        conn.executescript("""
            CREATE TABLE IF NOT EXISTS sessions (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                started_at REAL    NOT NULL,
                ended_at   REAL
            );

            CREATE TABLE IF NOT EXISTS readings (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id    INTEGER NOT NULL,
                timestamp     REAL    NOT NULL,
                light_raw     INTEGER,
                noise_raw     INTEGER,
                hydration_pct REAL,
                risk_score    INTEGER,
                FOREIGN KEY (session_id) REFERENCES sessions(id)
            );

            CREATE TABLE IF NOT EXISTS alerts (
                id         INTEGER PRIMARY KEY AUTOINCREMENT,
                session_id INTEGER NOT NULL,
                timestamp  REAL    NOT NULL,
                alert_type TEXT    NOT NULL,
                severity   TEXT    NOT NULL,
                message    TEXT    NOT NULL,
                FOREIGN KEY (session_id) REFERENCES sessions(id)
            );

            CREATE INDEX IF NOT EXISTS idx_readings_session
                ON readings(session_id, timestamp);
            CREATE INDEX IF NOT EXISTS idx_alerts_session
                ON alerts(session_id, timestamp);
        """)


def start_session() -> int:
    with _connect() as conn:
        cur = conn.execute(
            "INSERT INTO sessions (started_at) VALUES (?)", (time.time(),)
        )
        return cur.lastrowid


def end_session(session_id: int) -> None:
    with _connect() as conn:
        conn.execute(
            "UPDATE sessions SET ended_at = ? WHERE id = ?",
            (time.time(), session_id),
        )


def log_reading(
    session_id: int,
    light: int,
    noise: int,
    hydration_pct: float,
    risk_score: int,
) -> None:
    with _connect() as conn:
        conn.execute(
            "INSERT INTO readings "
            "(session_id, timestamp, light_raw, noise_raw, hydration_pct, risk_score) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            (session_id, time.time(), light, noise, hydration_pct, risk_score),
        )


def log_alert(
    session_id: int,
    alert_type: str,
    severity: str,
    message: str,
) -> None:
    with _connect() as conn:
        conn.execute(
            "INSERT INTO alerts (session_id, timestamp, alert_type, severity, message) "
            "VALUES (?, ?, ?, ?, ?)",
            (session_id, time.time(), alert_type, severity, message),
        )


def get_recent_readings(session_id: int, limit: int = 120) -> list:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT timestamp, light_raw, noise_raw, hydration_pct, risk_score "
            "FROM readings WHERE session_id = ? ORDER BY timestamp DESC LIMIT ?",
            (session_id, limit),
        ).fetchall()
    return list(reversed(rows))


def get_session_stats(session_id: int) -> dict:
    with _connect() as conn:
        row = conn.execute(
            "SELECT COUNT(*) as total, "
            "AVG(risk_score) as avg_risk, "
            "MAX(risk_score) as peak_risk, "
            "AVG(hydration_pct) as avg_hydration "
            "FROM readings WHERE session_id = ?",
            (session_id,),
        ).fetchone()
    return dict(row) if row else {}


def export_session_csv(session_id: int, path: str) -> None:
    with _connect() as conn:
        rows = conn.execute(
            "SELECT timestamp, light_raw, noise_raw, hydration_pct, risk_score "
            "FROM readings WHERE session_id = ? ORDER BY timestamp",
            (session_id,),
        ).fetchall()
    with open(path, "w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(
            ["timestamp_unix", "light_raw", "noise_raw", "hydration_pct", "risk_score"]
        )
        for r in rows:
            writer.writerow(list(r))
