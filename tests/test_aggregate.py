import asyncio
from datetime import datetime, timedelta

from app.aggregate import build_overview
from app.db import close_db, get_db


async def _seed_and_build(**kwargs):
    db = await get_db()
    now = datetime.now()
    rows = [
        # (mac, hostname, ssid, ap_label, floor, connected, last_seen)
        ("AA:00:00:00:00:01", "alpha", "home", "Office", "GF", 1, now),
        ("AA:00:00:00:00:02", None, "home", "Basement", "BF", 0, now - timedelta(hours=2)),
        ("AA:00:00:00:00:03", "ghost", "home", "Nowhere", "ZZ", 1, now),
        ("AA:00:00:00:00:04", "stale", "home", "Office", "GF", 0, now - timedelta(days=3)),
    ]
    for mac, host, ssid, ap, floor, connected, last_seen in rows:
        await db.execute(
            "INSERT INTO device_state (mac, hostname, vendor, ssid, ap_label, floor, signal, connected,"
            " connected_since, first_seen, last_seen) VALUES (?, ?, NULL, ?, ?, ?, '-50', ?, ?, ?, ?)",
            (mac, host, ssid, ap, floor, connected, last_seen.isoformat(), last_seen.isoformat(), last_seen.isoformat()),
        )
    await db.commit()
    try:
        return await build_overview(**kwargs)
    finally:
        await db.execute("DELETE FROM device_state")
        await db.commit()
        await close_db()


def test_overview_groups_by_floor_and_counts_active():
    overview = asyncio.run(_seed_and_build(window="24h", show_inactive=True))

    floors = {f["floor"]: f for f in overview["floors"]}
    # "stale" is outside the 24h window; the unknown floor "ZZ" lands in "??".
    assert overview["total_shown"] == 3
    assert overview["total_clients"] == 2
    assert floors["GF"]["client_count"] == 1
    assert floors["BF"]["client_count"] == 1
    assert floors["??"]["client_count"] == 1


def test_overview_hides_inactive_clients_on_request():
    overview = asyncio.run(_seed_and_build(window="24h", show_inactive=False))

    assert overview["total_shown"] == 2
    assert all(c["active"] for f in overview["floors"] for bucket in f["ssids"].values() for c in bucket)
