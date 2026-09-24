from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    mikrotik_host: str = "192.0.2.31"
    mikrotik_user: str = "capsman-api"
    mikrotik_password: str = ""
    # Self-signed CA ist bei MikroTik der Normalfall (siehe
    # router/create_capsman_api_user.rsc) - Default bleibt deshalb "nicht
    # pruefen", statt out-of-the-box jede Standard-Installation zu brechen.
    # Wer die vom Skript erzeugte CA exportiert, kann sie ueber
    # mikrotik_ca_file pinnen und verify_tls=true setzen.
    mikrotik_verify_tls: bool = False
    mikrotik_ca_file: str | None = None

    opnsense_host: str = "192.0.2.1"
    opnsense_scheme: str = "https"
    opnsense_api_key: str = ""
    opnsense_api_secret: str = ""
    # Default "true": der OPNsense-API-Key traegt schreibnahe Rechte
    # (Dnsmasq-Settings-Privileg), Zertifikatspruefung sollte daher nicht
    # standardmaessig abgeschaltet sein. Bei selbstsigniertem Zertifikat
    # ueber opnsense_ca_file pinnen statt verify_tls=false zu setzen.
    opnsense_verify_tls: bool = True
    opnsense_ca_file: str | None = None

    poll_interval_seconds: int = 30
    roaming_tolerance_seconds: int = 75
    retention_days: int = 30
    db_path: str = "data/history.db"
    floors_config_path: str = "config/floors.json"


settings = Settings()
