def display_name(hostname: str | None, vendor: str | None, mac: str) -> str:
    if hostname:
        return hostname
    if vendor:
        return f"{vendor} ({mac})"
    return mac
