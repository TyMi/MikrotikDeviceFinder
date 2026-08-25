from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")

    mikrotik_host: str = "192.0.2.31"
    mikrotik_user: str = "capsman-api"
    mikrotik_password: str = ""
    mikrotik_verify_tls: bool = False

    opnsense_host: str = "192.0.2.1"
    opnsense_scheme: str = "http"  # manche Netze blockieren 443 fuer die REST-API; auf https umstellen, falls erreichbar
    opnsense_api_key: str = ""
    opnsense_api_secret: str = ""
    opnsense_verify_tls: bool = False

    poll_interval_seconds: int = 30
    roaming_tolerance_seconds: int = 75
    retention_days: int = 30
    db_path: str = "data/history.db"
    floors_config_path: str = "config/floors.json"


settings = Settings()
