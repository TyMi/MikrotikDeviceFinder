import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles

from app.aggregate import build_overview
from app.db import close_db, get_db
from app.history import get_device_history, search_devices
from app.poller import run_forever
from app.vendor import ensure_vendor_db

_poller_task: asyncio.Task | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _poller_task
    await ensure_vendor_db()
    await get_db()
    _poller_task = asyncio.create_task(run_forever())
    yield
    if _poller_task is not None:
        _poller_task.cancel()
        try:
            await _poller_task
        except asyncio.CancelledError:
            pass
    await close_db()


app = FastAPI(title="MikrotikDeviceFinder", lifespan=lifespan)
app.mount("/static", StaticFiles(directory="app/static"), name="static")


@app.get("/", response_class=HTMLResponse)
async def index() -> HTMLResponse:
    with open("app/templates/index.html", encoding="utf-8") as f:
        return HTMLResponse(f.read())


@app.get("/api/overview")
async def api_overview(window: str = "24h", show_inactive: bool = True) -> dict:
    return await build_overview(window=window, show_inactive=show_inactive)


@app.get("/api/device/{mac}/history")
async def api_device_history(mac: str, window: str = "24h") -> dict:
    result = await get_device_history(mac, window=window)
    if result is None:
        raise HTTPException(status_code=404, detail="Geraet unbekannt")
    return result


@app.get("/api/search")
async def api_search(q: str = "", window: str = "7d") -> dict:
    if not q.strip():
        return {"query": q, "window": window, "results": []}
    results = await search_devices(q, window=window)
    return {"query": q, "window": window, "results": results}
