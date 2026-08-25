import httpx

from app.config import settings


class MikrotikClient:
    def __init__(self) -> None:
        self._base_url = f"https://{settings.mikrotik_host}/rest"
        self._auth = (settings.mikrotik_user, settings.mikrotik_password)

    async def _get(self, path: str) -> list | dict:
        async with httpx.AsyncClient(verify=settings.mikrotik_verify_tls, timeout=10) as client:
            response = await client.get(f"{self._base_url}/{path}", auth=self._auth)
            response.raise_for_status()
            return response.json()

    async def get_registration_table(self) -> list[dict]:
        """WLAN-Clients: mac-address, ssid, interface (=> AP), signal, uptime, ..."""
        return await self._get("interface/wifi/registration-table")

    async def get_arp_table(self) -> list[dict]:
        """MAC-zu-IP-Zuordnung, soweit dem Router bekannt (nicht vollstaendig fuer WLAN-Clients)."""
        return await self._get("ip/arp")
