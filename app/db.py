from pathlib import Path

import aiosqlite

from app.config import settings

SCHEMA = """
CREATE TABLE IF NOT EXISTS device_state (
    mac TEXT PRIMARY KEY,
    hostname TEXT,
    vendor TEXT,
    ip TEXT,
    ssid TEXT,
    ap_identity TEXT,
    ap_label TEXT,
    floor TEXT,
    floor_label TEXT,
    signal TEXT,
    connected INTEGER NOT NULL DEFAULT 0,
    missing_since TEXT,
    connected_since TEXT,
    first_seen TEXT NOT NULL,
    last_seen TEXT NOT NULL
);

CREATE TABLE IF NOT EXISTS events (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    mac TEXT NOT NULL,
    hostname TEXT,
    vendor TEXT,
    event_type TEXT NOT NULL,
    ssid TEXT,
    ap_label TEXT,
    floor_label TEXT,
    previous_ssid TEXT,
    previous_ap_label TEXT,
    timestamp TEXT NOT NULL
);

CREATE INDEX IF NOT EXISTS idx_events_timestamp ON events(timestamp);
CREATE INDEX IF NOT EXISTS idx_events_mac ON events(mac);
CREATE INDEX IF NOT EXISTS idx_device_state_last_seen ON device_state(last_seen);
"""

_connection: aiosqlite.Connection | None = None


async def get_db() -> aiosqlite.Connection:
    global _connection
    if _connection is None:
        db_path = Path(settings.db_path)
        db_path.parent.mkdir(parents=True, exist_ok=True)
        _connection = await aiosqlite.connect(db_path)
        _connection.row_factory = aiosqlite.Row
        await _connection.executescript(SCHEMA)
        await _connection.commit()
    return _connection


async def close_db() -> None:
    global _connection
    if _connection is not None:
        await _connection.close()
        _connection = None
