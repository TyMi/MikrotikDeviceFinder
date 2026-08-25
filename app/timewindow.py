from datetime import timedelta

WINDOW_OPTIONS: dict[str, timedelta] = {
    "1h": timedelta(hours=1),
    "6h": timedelta(hours=6),
    "24h": timedelta(hours=24),
    "7d": timedelta(days=7),
    "30d": timedelta(days=30),
}

DEFAULT_WINDOW = "24h"


def resolve_window(window: str | None) -> str:
    return window if window in WINDOW_OPTIONS else DEFAULT_WINDOW
