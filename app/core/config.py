from typing import Optional

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "sqlite+aiosqlite:///./nora.db"
    secret_key: str = "change-me-in-production"
    access_token_expire_minutes: int = 60 * 24 * 7  # 7 days

    # CRM-Sync (Check-in-Antworten → nora-crm). Wenn nicht gesetzt, ist der
    # Sync-Loop ein No-op und Outbox-Zeilen bleiben offen (kein Datenverlust).
    crm_webhook_url: Optional[str] = None        # NORA_CRM_WEBHOOK_URL
    crm_checkin_secret: Optional[str] = None     # NORA_CRM_CHECKIN_SECRET

    model_config = {"env_prefix": "NORA_"}


settings = Settings()

if settings.secret_key == "change-me-in-production" or len(settings.secret_key) < 32:
    raise RuntimeError(
        "NORA_SECRET_KEY ist nicht sicher konfiguriert. "
        "Setze NORA_SECRET_KEY auf einen zufaelligen Wert mit mindestens 32 Zeichen "
        "(z.B. via `openssl rand -hex 32`)."
    )
