from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    database_url: str = "sqlite+aiosqlite:///./nora.db"
    secret_key: str = "change-me-in-production"
    access_token_expire_minutes: int = 60 * 24 * 7  # 7 days

    model_config = {"env_prefix": "NORA_"}


settings = Settings()

if settings.secret_key == "change-me-in-production" or len(settings.secret_key) < 32:
    raise RuntimeError(
        "NORA_SECRET_KEY ist nicht sicher konfiguriert. "
        "Setze NORA_SECRET_KEY auf einen zufaelligen Wert mit mindestens 32 Zeichen "
        "(z.B. via `openssl rand -hex 32`)."
    )
