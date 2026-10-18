import asyncio

import httpx

from app import hostnames


class _FakeClient:
    """Stands in for httpx.AsyncClient; returns a canned response or raises."""

    def __init__(self, payload=None, error=None):
        self._payload = payload
        self._error = error

    def __call__(self, *args, **kwargs):
        return self

    async def __aenter__(self):
        return self

    async def __aexit__(self, *exc):
        return False

    async def get(self, url, **kwargs):
        if self._error:
            raise self._error
        return httpx.Response(200, json=self._payload, request=httpx.Request("GET", url))


def test_leases_are_parsed_and_placeholders_dropped(monkeypatch):
    payload = {
        "rows": [
            {"hwaddr": "aa:bb:cc:dd:ee:01", "hostname": "laptop", "address": "192.0.2.10"},
            {"hwaddr": "aa:bb:cc:dd:ee:02", "hostname": "*", "address": "192.0.2.11"},
            {"hwaddr": "", "hostname": "ignored", "address": "192.0.2.12"},
        ]
    }
    monkeypatch.setattr(hostnames.httpx, "AsyncClient", _FakeClient(payload=payload))

    leases = asyncio.run(hostnames.get_opnsense_leases())

    assert leases == {
        "AA:BB:CC:DD:EE:01": {"hostname": "laptop", "ip": "192.0.2.10"},
        "AA:BB:CC:DD:EE:02": {"hostname": None, "ip": "192.0.2.11"},
    }
    assert asyncio.run(hostnames.get_hostnames_by_mac()) == {"AA:BB:CC:DD:EE:01": "laptop"}


def test_fetch_failure_returns_none_not_empty(monkeypatch):
    monkeypatch.setattr(hostnames.httpx, "AsyncClient", _FakeClient(error=httpx.ConnectError("down")))

    assert asyncio.run(hostnames.get_opnsense_leases()) is None
    assert asyncio.run(hostnames.get_hostnames_by_mac()) == {}


def test_missing_credentials_skip_the_request(monkeypatch):
    monkeypatch.setattr(hostnames.settings, "opnsense_api_key", "")
    assert asyncio.run(hostnames.get_opnsense_leases()) == {}
