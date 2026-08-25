from datetime import datetime

from app.db import get_db
from app.naming import display_name
from app.timewindow import WINDOW_OPTIONS, resolve_window

_EVENT_LABELS = {
    "connect": "verbunden",
    "disconnect": "getrennt",
    "switch": "AP/SSID-Wechsel",
}


def _event_to_dict(row: dict) -> dict:
    ts = datetime.fromisoformat(row["timestamp"])
    label = _EVENT_LABELS.get(row["event_type"], row["event_type"])
    detail = f"{row['ap_label']} / {row['ssid']}" if row["ssid"] else row["ap_label"]
    if row["event_type"] == "switch" and row["previous_ap_label"]:
        detail = f"{row['previous_ap_label']} / {row['previous_ssid']} -> {detail}"
    return {
        "timestamp": row["timestamp"],
        "timestamp_label": ts.strftime("%d.%m.%Y %H:%M:%S"),
        "event_type": row["event_type"],
        "event_label": label,
        "detail": detail,
    }


async def get_device_history(mac: str, window: str = "24h") -> dict | None:
    window = resolve_window(window)
    cutoff = datetime.now() - WINDOW_OPTIONS[window]
    db = await get_db()

    cursor = await db.execute("SELECT * FROM device_state WHERE mac = ?", (mac.upper(),))
    device = await cursor.fetchone()
    if device is None:
        return None

    cursor = await db.execute(
        "SELECT * FROM events WHERE mac = ? AND timestamp >= ? ORDER BY timestamp DESC",
        (mac.upper(), cutoff.isoformat()),
    )
    events = await cursor.fetchall()

    return {
        "mac": device["mac"],
        "display_name": display_name(device["hostname"], device["vendor"], device["mac"]),
        "window": window,
        "events": [_event_to_dict(e) for e in events],
    }


async def search_devices(query: str, window: str = "7d") -> list[dict]:
    window = resolve_window(window)
    cutoff = datetime.now() - WINDOW_OPTIONS[window]
    db = await get_db()

    like = f"%{query.strip().lower()}%"
    cursor = await db.execute(
        "SELECT * FROM device_state WHERE LOWER(mac) LIKE ? OR LOWER(COALESCE(hostname,'')) LIKE ? "
        "OR LOWER(COALESCE(vendor,'')) LIKE ? ORDER BY last_seen DESC",
        (like, like, like),
    )
    devices = await cursor.fetchall()

    results = []
    for device in devices:
        cursor = await db.execute(
            "SELECT * FROM events WHERE mac = ? AND timestamp >= ? ORDER BY timestamp DESC",
            (device["mac"], cutoff.isoformat()),
        )
        events = await cursor.fetchall()
        if not events:
            continue
        results.append(
            {
                "mac": device["mac"],
                "display_name": display_name(device["hostname"], device["vendor"], device["mac"]),
                "active": bool(device["connected"]),
                "events": [_event_to_dict(e) for e in events],
            }
        )
    return results
