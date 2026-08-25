import asyncio
import logging
from datetime import datetime, timedelta

from app.config import settings
from app.db import get_db
from app.floors import AP_TO_FLOOR, resolve_ap_identity
from app.hostnames import get_opnsense_leases
from app.mikrotik import MikrotikClient
from app.vendor import lookup_vendor

logger = logging.getLogger(__name__)

_UNKNOWN_FLOOR = {"floor": "??", "label": "Unbekannter Standort"}

_last_cleanup: datetime | None = None


async def _log_event(
    db,
    *,
    mac: str,
    hostname: str | None,
    vendor: str | None,
    event_type: str,
    ssid: str | None,
    ap_label: str | None,
    floor_label: str | None,
    previous_ssid: str | None,
    previous_ap_label: str | None,
    timestamp: datetime,
) -> None:
    await db.execute(
        "INSERT INTO events (mac, hostname, vendor, event_type, ssid, ap_label, floor_label, "
        "previous_ssid, previous_ap_label, timestamp) VALUES (?,?,?,?,?,?,?,?,?,?)",
        (
            mac,
            hostname,
            vendor,
            event_type,
            ssid,
            ap_label,
            floor_label,
            previous_ssid,
            previous_ap_label,
            timestamp.isoformat(),
        ),
    )


async def poll_once(now: datetime | None = None) -> None:
    now = now or datetime.now()
    client = MikrotikClient()
    registration_table = await client.get_registration_table()
    arp_table = await client.get_arp_table()
    opnsense_leases = await get_opnsense_leases()
    mac_to_ip = {e["mac-address"].upper(): e["address"] for e in arp_table if e.get("mac-address")}

    db = await get_db()

    seen_macs: set[str] = set()

    for entry in registration_table:
        mac = entry.get("mac-address", "").upper()
        if not mac:
            continue
        seen_macs.add(mac)

        ssid = entry.get("ssid") or "(kein SSID)"
        interface = entry.get("interface", "")
        signal = entry.get("signal")
        ap_identity = resolve_ap_identity(interface)
        if ap_identity is not None:
            floor = AP_TO_FLOOR[ap_identity]["floor"]
            floor_label = AP_TO_FLOOR[ap_identity]["label"]
            ap_label = AP_TO_FLOOR[ap_identity]["label"]
        else:
            floor = _UNKNOWN_FLOOR["floor"]
            floor_label = _UNKNOWN_FLOOR["label"]
            ap_label = interface or "unbekannt"

        lease = opnsense_leases.get(mac, {})
        hostname = lease.get("hostname")
        vendor = None if hostname else await lookup_vendor(mac)
        ip = lease.get("ip") or mac_to_ip.get(mac)

        cursor = await db.execute("SELECT * FROM device_state WHERE mac = ?", (mac,))
        row = await cursor.fetchone()

        if row is None:
            await db.execute(
                "INSERT INTO device_state (mac, hostname, vendor, ip, ssid, ap_identity, ap_label, "
                "floor, floor_label, signal, connected, missing_since, connected_since, first_seen, last_seen) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,1,NULL,?,?,?)",
                (mac, hostname, vendor, ip, ssid, ap_identity, ap_label, floor, floor_label, signal,
                 now.isoformat(), now.isoformat(), now.isoformat()),
            )
            await _log_event(
                db, mac=mac, hostname=hostname, vendor=vendor, event_type="connect",
                ssid=ssid, ap_label=ap_label, floor_label=floor_label,
                previous_ssid=None, previous_ap_label=None, timestamp=now,
            )
            continue

        was_connected = bool(row["connected"])
        was_pending_missing = row["missing_since"] is not None
        moved = row["ssid"] != ssid or row["ap_identity"] != ap_identity

        if was_connected and not was_pending_missing:
            if moved:
                await _log_event(
                    db, mac=mac, hostname=hostname, vendor=vendor, event_type="switch",
                    ssid=ssid, ap_label=ap_label, floor_label=floor_label,
                    previous_ssid=row["ssid"], previous_ap_label=row["ap_label"], timestamp=now,
                )
            await db.execute(
                "UPDATE device_state SET hostname=?, vendor=?, ip=?, ssid=?, ap_identity=?, ap_label=?, "
                "floor=?, floor_label=?, signal=?, last_seen=? WHERE mac=?",
                (hostname, vendor, ip, ssid, ap_identity, ap_label, floor, floor_label, signal, now.isoformat(), mac),
            )
        elif was_connected and was_pending_missing:
            # Kurz weg (z.B. beim Roaming), aber innerhalb der Toleranz zurueckgekehrt.
            if moved:
                await _log_event(
                    db, mac=mac, hostname=hostname, vendor=vendor, event_type="switch",
                    ssid=ssid, ap_label=ap_label, floor_label=floor_label,
                    previous_ssid=row["ssid"], previous_ap_label=row["ap_label"], timestamp=now,
                )
            await db.execute(
                "UPDATE device_state SET hostname=?, vendor=?, ip=?, ssid=?, ap_identity=?, ap_label=?, "
                "floor=?, floor_label=?, signal=?, missing_since=NULL, last_seen=? WHERE mac=?",
                (hostname, vendor, ip, ssid, ap_identity, ap_label, floor, floor_label, signal, now.isoformat(), mac),
            )
        else:
            # War wirklich getrennt -> jetzt ein echter Neuverbindungs-Event.
            await _log_event(
                db, mac=mac, hostname=hostname, vendor=vendor, event_type="connect",
                ssid=ssid, ap_label=ap_label, floor_label=floor_label,
                previous_ssid=None, previous_ap_label=None, timestamp=now,
            )
            await db.execute(
                "UPDATE device_state SET hostname=?, vendor=?, ip=?, ssid=?, ap_identity=?, ap_label=?, "
                "floor=?, floor_label=?, signal=?, connected=1, missing_since=NULL, connected_since=?, "
                "last_seen=? WHERE mac=?",
                (hostname, vendor, ip, ssid, ap_identity, ap_label, floor, floor_label, signal,
                 now.isoformat(), now.isoformat(), mac),
            )

    # Geraete, die gerade nicht mehr gemeldet wurden.
    cursor = await db.execute("SELECT * FROM device_state WHERE connected = 1")
    connected_rows = await cursor.fetchall()
    tolerance = timedelta(seconds=settings.roaming_tolerance_seconds)

    for row in connected_rows:
        if row["mac"] in seen_macs:
            continue
        if row["missing_since"] is None:
            await db.execute("UPDATE device_state SET missing_since=? WHERE mac=?", (now.isoformat(), row["mac"]))
            continue

        missing_since = datetime.fromisoformat(row["missing_since"])
        if now - missing_since >= tolerance:
            await _log_event(
                db, mac=row["mac"], hostname=row["hostname"], vendor=row["vendor"], event_type="disconnect",
                ssid=row["ssid"], ap_label=row["ap_label"], floor_label=row["floor_label"],
                previous_ssid=None, previous_ap_label=None, timestamp=now,
            )
            await db.execute(
                "UPDATE device_state SET connected=0, missing_since=NULL WHERE mac=?", (row["mac"],)
            )

    await db.commit()


async def cleanup_old_data(now: datetime | None = None) -> None:
    now = now or datetime.now()
    cutoff = now - timedelta(days=settings.retention_days)
    db = await get_db()
    await db.execute("DELETE FROM events WHERE timestamp < ?", (cutoff.isoformat(),))
    await db.execute("DELETE FROM device_state WHERE connected = 0 AND last_seen < ?", (cutoff.isoformat(),))
    await db.commit()


async def _maybe_cleanup(now: datetime) -> None:
    global _last_cleanup
    if _last_cleanup is None or now - _last_cleanup >= timedelta(days=1):
        await cleanup_old_data(now)
        _last_cleanup = now


async def run_forever() -> None:
    while True:
        now = datetime.now()
        try:
            await poll_once(now)
            await _maybe_cleanup(now)
        except Exception:
            logger.exception("Fehler beim Polling des CAPsMAN-Controllers")
        await asyncio.sleep(settings.poll_interval_seconds)
