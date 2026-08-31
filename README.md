# MikrotikDeviceFinder

![Built with AI](https://img.shields.io/badge/Built_with-AI-success)

A small self-hosted web app that shows, across a fleet of MikroTik CAPsMAN
access points, which WLAN clients are currently (and historically) connected
to which access point and SSID - grouped by floor.

> **Language note:** the application UI and all code comments are in
> German. Only this documentation is in English. If you'd like an
> English-language UI, that would require translating the frontend
> (`app/templates`, `app/static`) and a handful of backend-generated labels
> (`app/aggregate.py`, `app/history.py`) - not currently done.

## Features

- Live overview: floors stacked vertically, SSIDs side by side as columns.
- Name resolution chain: DHCP hostname (via OPNsense) → OUI vendor name →
  raw MAC address as a last-resort fallback.
- Disconnected devices are shown greyed out at their last known position
  (visibility window follows the selected time-range filter), toggleable.
- Time-range filter (1h / 6h / 24h / 7d / 30d, default 24h) drives both the
  visibility of inactive devices and the per-device history lookback.
- SSID multi-select filter (default: all), individually collapsible floor
  sections (default: expanded).
- Per-device history: connect / disconnect / AP-or-SSID-switch events with
  timestamps.
- Independent search (own time range) across hostname / vendor / MAC.
- No login - this is meant for trusted internal networks only.

## Architecture

```
CAPsMAN controller (REST API)  ──┐
                                  ├─▶  background poller (every 30s)  ──▶  SQLite  ──▶  FastAPI  ──▶  browser
DHCP server (leases API)       ──┘
```

- The poller (`app/poller.py`) runs as its own `asyncio` task, independent
  of incoming web requests (started in the FastAPI `lifespan`). Web requests
  only ever read from SQLite, never hit the devices directly - the UI stays
  responsive even if a source is briefly unreachable.
- **CAPsMAN** is polled for the currently-connected client list (MAC, SSID,
  AP interface, signal strength, uptime) via the RouterOS 7 REST API
  (`/rest/interface/wifi/registration-table` - the new "wifi" package, not
  the legacy `caps-man` menu; adjust if you're on an older RouterOS/package).
- **DHCP/hostname resolution**: CAPsMAN itself has no concept of IP
  addresses, so MAC→IP→hostname has to come from your DHCP server. This
  project was built against an OPNsense box running the dnsmasq DHCP plugin
  (`/api/dnsmasq/leases/search`) - see `app/hostnames.py`. If your DHCP
  server is different (ISC dhcpd, Kea, pfSense, a plain router, ...), you'll
  need to adapt that one module; everything else is independent of it.
- If neither a hostname nor an OUI vendor match is found, the raw MAC
  address is shown.

## Data model (SQLite, `app/db.py`)

- **`device_state`**: current state per MAC (hostname, vendor, IP, SSID, AP,
  floor, `connected`, `connected_since`, `last_seen`).
- **`events`**: append-only log of `connect` / `disconnect` / `switch`
  events (timestamp, SSID/AP before/after).
- **Roaming tolerance** (`ROAMING_TOLERANCE_SECONDS`, default 75s ≈ 2 poll
  cycles): a device that briefly disappears (e.g. while roaming between two
  APs) is not treated as disconnected - if it reappears elsewhere in time,
  it's logged as a single `switch` event instead, and `connected_since` is
  not reset.
- **Retention** (`RETENTION_DAYS`, default 30): runs opportunistically once
  a day inside the poll loop, deleting old events and long-disconnected
  `device_state` rows.

## Configuration (`.env`)

| Variable | Meaning | Default |
| --- | --- | --- |
| `MIKROTIK_HOST` | IP of the CAPsMAN controller | `192.0.2.31` |
| `MIKROTIK_USER` / `MIKROTIK_PASSWORD` | Read-only API user (see `router/create_capsman_api_user.rsc`) | - |
| `MIKROTIK_VERIFY_TLS` | Verify the router's TLS cert (usually self-signed → `false`) | `false` |
| `OPNSENSE_HOST` | IP of your OPNsense box | `192.0.2.1` |
| `OPNSENSE_SCHEME` | `http` or `https` | `http` |
| `OPNSENSE_API_KEY` / `OPNSENSE_API_SECRET` | dnsmasq leases API user | - |
| `OPNSENSE_VERIFY_TLS` | Verify OPNsense's TLS cert | `false` |
| `POLL_INTERVAL_SECONDS` | Seconds between polls | `30` |
| `ROAMING_TOLERANCE_SECONDS` | See above | `75` |
| `RETENTION_DAYS` | See above | `30` |
| `DB_PATH` | Path to the SQLite file | `data/history.db` |
| `FLOORS_CONFIG_PATH` | Path to your floor/AP-mapping JSON (see below) | `config/floors.json` |

`.env.example` has a filled-in template with placeholder addresses.

### Floor / access-point mapping

Which physical AP belongs to which floor is not hardcoded - it's loaded at
startup from a JSON file (`app/floors.py`, path from `FLOORS_CONFIG_PATH`).
See `config/floors.example.json` for the format:

```json
{
  "floors": [
    {"floor": "GF", "label": "Ground Floor", "order": 0}
  ],
  "access_points": {
    "ap-ground": {"floor": "GF", "label": "Ground Floor (Main AP)"}
  }
}
```

`floors` defines the display order top-to-bottom. `access_points` maps each
AP's CAPsMAN identity to a floor; an AP identity is matched as a prefix of
the wireless interface name reported by CAPsMAN (e.g. AP identity `ap-ground`
matches an interface named `ap-ground_2GHz2`). Copy the example, rename your APs'
identities to match your own naming, and point `FLOORS_CONFIG_PATH` at it.

## Local development

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env                              # fill in your credentials
cp config/floors.example.json config/floors.json   # adjust to your APs
.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
```

## Production deployment

Ships as a single Docker container (`docker-compose.yml`):

```bash
docker compose build
docker compose up -d
```

- Binds to `127.0.0.1:8090` by default inside the container - put a reverse
  proxy in front of it for LAN/HTTPS access (see
  `examples/reverse-proxy.Caddyfile.example` for a minimal Caddy site
  config), don't expose it directly.
- The SQLite database lives in the `./data` volume, so it survives
  container restarts/rebuilds.
- Everything - web server, background poller, SQLite - runs in this one
  container; no separate DB or worker process/container is needed.
- The image pins its timezone to `Europe/Berlin` (`Dockerfile`/
  `docker-compose.yml`) so timestamps are correct without extra effort for
  the author's own deployment - change the `TZ` build arg/environment
  variable to your own timezone (or `UTC`) if you deploy this elsewhere.

## MikroTik / OPNsense prerequisites

- **MikroTik**: create a dedicated, read-only API user - see
  `router/create_capsman_api_user.rsc` (RouterOS terminal script, fill in
  the placeholders at the top). Note the `rest-api` group policy is
  required in addition to `read`/`web`/`api` - without it RouterOS returns a
  generic 401 that looks identical to a wrong password.
- **OPNsense with dnsmasq**: create a dedicated user/group with the
  "Services: Dnsmasq DNS/DHCP: Settings" privilege (the dnsmasq plugin
  doesn't expose a narrower read-only "leases" privilege), generate an API
  key/secret for it. Endpoint used: `/api/dnsmasq/leases/search`.
- If you use a different DHCP backend, you'll need to write your own
  equivalent of `app/hostnames.py`.

## Known limitations

- **MAC randomization** (iOS/Android "private Wi-Fi address"): a device
  that rotates its MAC per network (or periodically) breaks history
  continuity under the old MAC. Mitigation: display/search prefers the
  (comparatively stable) DHCP hostname over the MAC when available - this
  can't be fully solved without unreliable heuristics.
- No signal-strength time series, only the current reading plus
  connect/disconnect/switch events.
- Built and tested against a specific combination of RouterOS 7 (new "wifi"
  package) and OPNsense+dnsmasq. Other combinations will very likely need
  adjustments to `app/mikrotik.py` and/or `app/hostnames.py`.

## Testing

See [`TESTING.md`](TESTING.md) for a numbered checklist covering local
setup, MikroTik/OPNsense connectivity, the floors config, API/frontend
checks, Docker deployment, and a regression checklist for future changes.

## License

MIT - see [`LICENSE`](LICENSE).
