"""Aufloesung MAC -> Hostname/IP ueber die dnsmasq-DHCP-Leases in OPNsense.

Genutzt wird der Such-Endpoint des dnsmasq-Plugins (/api/dnsmasq/leases/search),
freigeschaltet ueber das Privileg "Services: Dnsmasq DNS/DHCP: Settings" fuer
einen dedizierten Read-only-API-User.
"""

import logging

import httpx

from app.config import settings
from app.tls import verify_arg

logger = logging.getLogger(__name__)


async def get_opnsense_leases() -> dict[str, dict] | None:
    """Liefert {MAC: {"hostname": str|None, "ip": str|None}} aus den dnsmasq-Leases.

    dnsmasq traegt "*" als Platzhalter ein, wenn ein Client keinen Hostnamen
    per DHCP mitschickt - das wird nicht als echter Name gewertet.

    Gibt None zurueck, wenn der Abruf fehlgeschlagen ist (Netzwerk/Auth/etc.) -
    bewusst unterschieden von einem leeren, aber erfolgreichen Ergebnis ({}),
    damit der Aufrufer bei einem Fehler bestehende Hostnamen NICHT ueberschreibt
    (siehe app/poller.py).
    """
    if not settings.opnsense_api_key or not settings.opnsense_api_secret:
        return {}

    url = f"{settings.opnsense_scheme}://{settings.opnsense_host}/api/dnsmasq/leases/search"
    auth = (settings.opnsense_api_key, settings.opnsense_api_secret)
    verify = verify_arg(settings.opnsense_verify_tls, settings.opnsense_ca_file)

    try:
        async with httpx.AsyncClient(verify=verify, timeout=10) as client:
            response = await client.get(url, params={"current": 1, "rowCount": 1000}, auth=auth)
            response.raise_for_status()
            data = response.json()
    except Exception:
        logger.warning("OPNsense-Leases konnten nicht abgerufen werden, bestehende Hostnamen bleiben erhalten.", exc_info=True)
        return None

    leases: dict[str, dict] = {}
    for row in data.get("rows", []):
        mac = row.get("hwaddr", "").upper()
        if not mac:
            continue
        hostname = row.get("hostname", "").strip()
        if not hostname or hostname == "*":
            hostname = None
        leases[mac] = {"hostname": hostname, "ip": row.get("address") or None}
    return leases


async def get_hostnames_by_mac() -> dict[str, str]:
    leases = await get_opnsense_leases() or {}
    return {mac: info["hostname"] for mac, info in leases.items() if info["hostname"]}
