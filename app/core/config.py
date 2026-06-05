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

    # Google Drive (Live-Call-Import). Wenn nicht gesetzt, ist der Import-Loop
    # ein No-op (kein Service-Account → nichts zu tun).
    google_sa_json: Optional[str] = None             # NORA_GOOGLE_SA_JSON (JSON-String)
    google_impersonate_subject: Optional[str] = None # NORA_GOOGLE_IMPERSONATE_SUBJECT
    meet_recordings_folder_id: Optional[str] = None  # NORA_MEET_RECORDINGS_FOLDER_ID

    model_config = {"env_prefix": "NORA_"}

    @property
    def google_sa_info(self) -> Optional[dict]:
        """Geparster Service-Account-Key oder None, wenn nicht konfiguriert."""
        import json
        if not self.google_sa_json:
            return None
        return json.loads(self.google_sa_json)


settings = Settings()

if settings.secret_key == "change-me-in-production" or len(settings.secret_key) < 32:
    raise RuntimeError(
        "NORA_SECRET_KEY ist nicht sicher konfiguriert. "
        "Setze NORA_SECRET_KEY auf einen zufaelligen Wert mit mindestens 32 Zeichen "
        "(z.B. via `openssl rand -hex 32`)."
    )
