# Testing / Verification Guide

A structured checklist for verifying a setup works - both for a first-time
deployment and as a regression check after changing code or config. Replace
the placeholder addresses (`192.0.2.x`, ports) with your own.

## 1. Local development smoke test

1.1. Install and start the app:

```bash
python3 -m venv .venv
.venv/bin/pip install -r requirements.txt
cp .env.example .env                               # fill in your credentials
cp config/floors.example.json config/floors.json    # adjust to your APs
.venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8000
```

1.2. Confirm clean startup - no `ModuleNotFoundError`, no traceback, and the
log ends with `Uvicorn running on http://0.0.0.0:8000`.

1.3. Confirm the floors config loaded without error (a bad/missing
`config/floors.json` raises `FileNotFoundError` at import time, so a clean
startup already proves this - no separate check needed unless you're
editing `app/floors.py` itself, see §8).

## 2. MikroTik CAPsMAN connectivity

2.1. Confirm the REST API user works and returns data (adjust host/path to
your RouterOS package - `interface/wifi/registration-table` for the new
"wifi" package, `caps-man/registration-table` for the legacy one):

```bash
curl -k -u capsman-api:<password> \
  https://192.0.2.31/rest/interface/wifi/registration-table
```

Expect a JSON array of currently-connected clients (`mac-address`, `ssid`,
`interface`, `signal`, `uptime`). A `401` with correct credentials usually
means the RouterOS user is missing the `rest-api` group policy (see
`router/create_capsman_api_user.rsc`), not a wrong password.

2.2. Confirm the app's own poller reaches the same endpoint - check the
running app's logs for `Fehler beim Polling des CAPsMAN-Controllers`
(`app/poller.py`); absence of that message across at least one poll
interval (`POLL_INTERVAL_SECONDS`, default 30s) means it's working.

## 3. OPNsense / DHCP-lease connectivity

3.1. Confirm the dnsmasq leases endpoint works (adjust if you adapted
`app/hostnames.py` for a different DHCP backend):

```bash
curl -u <key>:<secret> \
  "http://192.0.2.1/api/dnsmasq/leases/search?current=1&rowCount=1000"
```

Expect `{"rows": [...]}` with `hwaddr`, `address`, `hostname` per lease. A
`403 Forbidden` (not `404`) means the endpoint exists but the API user's
group is missing the required privilege.

3.2. In the app's live overview data, confirm at least some devices resolve
to a real hostname rather than falling back to `<Vendor> (<MAC>)` or the
raw MAC - see §5.2.

## 4. Floors configuration

4.1. Validate your `config/floors.json` is well-formed JSON and matches the
schema in `config/floors.example.json` (`floors` array + `access_points`
object) - a syntax error surfaces as a startup crash, see §1.2.

4.2. Confirm every AP identity you expect to see is actually present as a
prefix in `access_points` - CAPsMAN reports wireless interfaces as
`<ap-identity>_<band>` (e.g. `ap-ground_2GHz2`); an AP whose identity isn't
listed falls into the "Unbekannter Standort" / unknown-floor bucket instead
of its intended floor. Cross-check against a live poll (§2.1's `interface`
field) if something looks misplaced.

## 5. Backend API checks

With the app running (locally or in Docker):

5.1. Overview endpoint:

```bash
curl "http://localhost:8000/api/overview?window=24h&show_inactive=true"
```

Check: `total_clients`/`total_shown` are non-zero if devices are actually
connected; every floor from your config appears; `ssid_order` lists the
SSIDs you expect.

5.2. Name resolution: pick one client from the response and confirm
`display_name` is a real hostname (not just `<MAC>`) if that device sends a
DHCP hostname - if every device shows a raw MAC, re-check §3 and the OUI
vendor DB (`WARNING:app.vendor:...` in the logs means it failed to
download/cache, usually a missing `~/.cache` directory or no outbound
internet access on first start).

5.3. Search endpoint:

```bash
curl "http://localhost:8000/api/search?q=<part-of-a-known-hostname-or-mac>&window=7d"
```

5.4. Per-device history (grab a `mac` from §5.1's response):

```bash
curl "http://localhost:8000/api/device/<MAC>/history?window=24h"
```

Expect at least one `connect` event if that device has been online since
the app started.

## 6. Frontend checks (manual, in a browser)

6.1. Page loads, floors render top-to-bottom in the configured order, SSIDs
render as columns.

6.2. Time-range selector, inactive-devices toggle, and SSID filter dropdown
all update the grid without a full page reload.

6.3. Floor sections collapse/expand and stay collapsed across the 30s
auto-refresh.

6.4. "Details (N)" button on a client card expands an event-history list
matching §5.4's data.

6.5. Search panel returns results independent of the main grid's
time-range setting.

## 7. Docker / production deployment

7.1. Build and start:

```bash
docker compose build
docker compose up -d
docker compose logs --tail 30
```

Check: no `ModuleNotFoundError` (usually means a dependency was added to
`.venv` during development but never synced to `requirements.txt`), no
vendor-DB warning, no poller traceback.

7.2. Confirm the container's clock/timezone is correct, not UTC-by-default:

```bash
docker exec <container-name> date
```

7.3. Confirm the app is reachable only through your reverse proxy, not
directly on the LAN - the app should be bound to `127.0.0.1` inside the
container (see `docker-compose.yml`'s `command`), and a request straight to
the host's app port from another machine should fail while a request
through the proxy succeeds.

7.4. Confirm `./data` (SQLite) and `./config` (floors mapping) are actually
mounted and persist - restart the container and confirm history/config
survive:

```bash
docker compose restart
curl "http://localhost:8000/api/overview?window=30d"   # history still present
```

## 8. Regression checklist after changing code/config

Use this whenever you touch `app/floors.py`, `app/config.py`, or the
floors-config format itself, to make sure existing deployments don't
silently change behavior:

8.1. Snapshot the current `/api/overview?window=24h` response (floor, AP
label, MAC, `display_name` per client) before the change.

8.2. Apply the change, rebuild/restart.

8.3. Re-fetch the same endpoint and diff the floor/AP-label/MAC/name lines
against the snapshot - they should be identical unless the change was
specifically meant to alter grouping.

8.4. Re-run §2 and §3 connectivity checks (a rebuild can surface unrelated
regressions, e.g. a missing dependency or a broken cache path).

8.5. Grep any newly-added or newly-published files for real
IPs/hostnames/credentials before committing/publishing, e.g.:

```bash
grep -rn "192\.168\." README.md examples/ .env.example
```
