def verify_arg(verify_tls: bool, ca_file: str | None) -> bool | str:
    """Baut den httpx-`verify`-Wert: CA-Datei hat Vorrang (Zertifikat-Pinning
    statt Pruefung komplett abzuschalten), sonst der einfache Bool-Wert."""
    if ca_file:
        return ca_file
    return verify_tls
