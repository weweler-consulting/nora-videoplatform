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

    # Google Drive (Live-Call-Import) via OAuth eines Workspace-internen Clients.
    # Refresh-Token wird einmalig per scripts/google_oauth_setup.py geholt.
    # Wenn nicht vollständig gesetzt, ist der Import-Loop ein No-op.
    google_oauth_client_id: Optional[str] = None      # NORA_GOOGLE_OAUTH_CLIENT_ID
    google_oauth_client_secret: Optional[str] = None  # NORA_GOOGLE_OAUTH_CLIENT_SECRET
    google_oauth_refresh_token: Optional[str] = None  # NORA_GOOGLE_OAUTH_REFRESH_TOKEN
    meet_recordings_folder_id: Optional[str] = None   # NORA_MEET_RECORDINGS_FOLDER_ID
    live_call_notify_email: Optional[str] = None       # NORA_LIVE_CALL_NOTIFY_EMAIL

    model_config = {"env_prefix": "NORA_"}

    @property
    def google_oauth_configured(self) -> bool:
        """True, wenn Client-ID, Secret und Refresh-Token gesetzt sind."""
        return bool(
            self.google_oauth_client_id
            and self.google_oauth_client_secret
            and self.google_oauth_refresh_token
        )


settings = Settings()

if settings.secret_key == "change-me-in-production" or len(settings.secret_key) < 32:
    raise RuntimeError(
        "NORA_SECRET_KEY ist nicht sicher konfiguriert. "
        "Setze NORA_SECRET_KEY auf einen zufaelligen Wert mit mindestens 32 Zeichen "
        "(z.B. via `openssl rand -hex 32`)."
    )
