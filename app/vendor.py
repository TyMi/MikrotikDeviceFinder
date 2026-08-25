import logging

from mac_vendor_lookup import AsyncMacLookup, VendorNotFoundError

logger = logging.getLogger(__name__)

_lookup = AsyncMacLookup()
_ready = False


async def ensure_vendor_db() -> None:
    """Laedt die IEEE-OUI-Datenbank einmalig lokal (braucht beim ersten Mal Internet).
    Schlaegt der Download fehl (z.B. Server ohne Internetzugang), bleibt die
    Vendor-Aufloesung deaktiviert und faellt auf 'Unbekanntes Geraet' zurueck.
    """
    global _ready
    try:
        await _lookup.update_vendors()
        _ready = True
    except Exception:
        logger.warning("MAC-Vendor-Datenbank konnte nicht geladen werden, Vendor-Anzeige deaktiviert.")
        _ready = False


async def lookup_vendor(mac_address: str) -> str | None:
    if not _ready:
        return None
    try:
        return await _lookup.lookup(mac_address)
    except VendorNotFoundError:
        return None
