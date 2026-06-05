"""Signierte 1-Klick-Tokens für die Live-Call-Freigabe (approve/dismiss).
JWT über settings.secret_key — stateless, kein DB-Token nötig. Idempotenz/
Einmaligkeit kommt aus dem Import-Status, nicht aus dem Token."""
from datetime import timedelta

import jwt

from app.core.config import settings
from app.core.time import utc_now

_ALGO = "HS256"
_EXP_DAYS = 30


def create_action_token(import_id: str, action: str) -> str:
    payload = {"lci": import_id, "act": action, "exp": utc_now() + timedelta(days=_EXP_DAYS)}
    return jwt.encode(payload, settings.secret_key, algorithm=_ALGO)


def verify_action_token(token: str, expected_action: str) -> str | None:
    """Gibt die import_id zurück, wenn Token gültig + Aktion passt; sonst None."""
    try:
        data = jwt.decode(token, settings.secret_key, algorithms=[_ALGO])
    except jwt.PyJWTError:
        return None
    if data.get("act") != expected_action:
        return None
    return data.get("lci")
