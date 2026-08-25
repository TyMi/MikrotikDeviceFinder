from datetime import datetime

from app.db import get_db
from app.floors import FLOORS
from app.naming import display_name
from app.timewindow import WINDOW_OPTIONS, resolve_window

_UNKNOWN_FLOOR = {"floor": "??", "label": "Unbekannter Standort", "order": 99}


def _row_to_client(row: dict, now: datetime, event_count: int) -> dict:
    active = bool(row["connected"])
    client = {
        "mac": row["mac"],
        "display_name": display_name(row["hostname"], row["vendor"], row["mac"]),
        "ip": row["ip"],
        "ssid": row["ssid"],
        "ap_label": row["ap_label"],
        "signal": row["signal"] if active else None,
        "active": active,
        "event_count": event_count,
    }
    if active:
        since = datetime.fromisoformat(row["connected_since"])
        client["connected_since_label"] = since.strftime("%H:%M Uhr")
        client["status_label"] = "seit " + since.strftime("%H:%M Uhr")
    else:
        last_seen = datetime.fromisoformat(row["last_seen"])
        client["status_label"] = "zuletzt verbunden: " + last_seen.strftime("%d.%m. %H:%M Uhr")
    return client


async def build_overview(window: str = "24h", show_inactive: bool = True) -> dict:
    window = resolve_window(window)
    now = datetime.now()
    cutoff = now - WINDOW_OPTIONS[window]

    db = await get_db()
    if show_inactive:
        cursor = await db.execute(
            "SELECT * FROM device_state WHERE connected = 1 OR last_seen >= ? ORDER BY last_seen DESC",
            (cutoff.isoformat(),),
        )
    else:
        cursor = await db.execute("SELECT * FROM device_state WHERE connected = 1 ORDER BY last_seen DESC")
    rows = await cursor.fetchall()

    cursor = await db.execute(
        "SELECT mac, COUNT(*) AS cnt FROM events WHERE timestamp >= ? GROUP BY mac", (cutoff.isoformat(),)
    )
    event_counts = {r["mac"]: r["cnt"] for r in await cursor.fetchall()}

    ssid_set: set[str] = set()
    clients_by_floor: dict[str, list[dict]] = {f["floor"]: [] for f in FLOORS}
    clients_by_floor[_UNKNOWN_FLOOR["floor"]] = []
    floor_meta = {f["floor"]: f for f in FLOORS}
    floor_meta[_UNKNOWN_FLOOR["floor"]] = _UNKNOWN_FLOOR

    total_active = 0

    for row in rows:
        floor = row["floor"] if row["floor"] in clients_by_floor else _UNKNOWN_FLOOR["floor"]
        client = _row_to_client(row, now, event_counts.get(row["mac"], 0))
        ssid_set.add(client["ssid"] or "(kein SSID)")
        clients_by_floor[floor].append(client)
        if client["active"]:
            total_active += 1

    ssid_order = sorted(ssid_set)

    floors_out = []
    for floor_key in [f["floor"] for f in FLOORS] + [_UNKNOWN_FLOOR["floor"]]:
        clients = clients_by_floor[floor_key]
        if floor_key == _UNKNOWN_FLOOR["floor"] and not clients:
            continue
        by_ssid: dict[str, list[dict]] = {ssid: [] for ssid in ssid_order}
        for c in clients:
            by_ssid[c["ssid"] or "(kein SSID)"].append(c)
        for bucket in by_ssid.values():
            bucket.sort(key=lambda c: (not c["active"], c["display_name"].lower()))
        floors_out.append(
            {
                "floor": floor_key,
                "label": floor_meta[floor_key]["label"],
                "client_count": len(clients),
                "ssids": by_ssid,
            }
        )

    return {
        "generated_at_label": now.strftime("%H:%M:%S Uhr"),
        "window": window,
        "show_inactive": show_inactive,
        "ssid_order": ssid_order,
        "floors": floors_out,
        "total_clients": total_active,
        "total_shown": len(rows),
    }
