"""Einmaliger OAuth-Consent → Refresh-Token für den Live-Call-Import.

Voraussetzung: die heruntergeladene OAuth-Client-Secret-JSON (Desktop-App) aus der
Google Cloud Console (APIs & Dienste → Anmeldedaten → OAuth-Client-ID, Typ Desktop).

  python3 scripts/google_oauth_setup.py ~/Downloads/client_secret_xxx.json

Öffnet den Browser → als nora@noraweweler.de anmelden → Drive-Lesezugriff bestätigen.
Schreibt Client-ID, Secret, Refresh-Token + Folder-ID in eine geschützte ENV-Datei
(Default ~/.nora_live_call_env, chmod 600) — der Token wird NICHT ausgegeben.
"""
import json
import os
import sys

from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]
DEFAULT_FOLDER_ID = "1rruYIZ956dNjllrenSGleL4UoZHZuM9h"


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python3 scripts/google_oauth_setup.py <client_secret.json> [out_env_file]", file=sys.stderr)
        sys.exit(1)
    secrets_path = sys.argv[1]
    out_path = sys.argv[2] if len(sys.argv) > 2 else os.path.expanduser("~/.nora_live_call_env")

    flow = InstalledAppFlow.from_client_secrets_file(secrets_path, SCOPES)
    creds = flow.run_local_server(port=0, access_type="offline", prompt="consent")

    with open(secrets_path) as fh:
        data = json.load(fh)
    client = data.get("installed") or data.get("web") or {}

    lines = [
        f"export NORA_GOOGLE_OAUTH_CLIENT_ID='{client.get('client_id')}'",
        f"export NORA_GOOGLE_OAUTH_CLIENT_SECRET='{client.get('client_secret')}'",
        f"export NORA_GOOGLE_OAUTH_REFRESH_TOKEN='{creds.refresh_token}'",
        f"export NORA_MEET_RECORDINGS_FOLDER_ID='{DEFAULT_FOLDER_ID}'",
    ]
    # Direkt mit 0600 anlegen (kein chmod-TOCTOU-Fenster mit Default-umask).
    fd = os.open(out_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w") as fh:
        fh.write("\n".join(lines) + "\n")
    os.chmod(out_path, 0o600)  # falls Datei schon existierte (O_CREAT-mode greift dann nicht)

    if not creds.refresh_token:
        print("\n⚠️  Kein Refresh-Token erhalten — App ggf. schon autorisiert. Zugriff unter "
              "myaccount.google.com/permissions entfernen und erneut laufen lassen.")
    print(f"\n✅ Fertig. ENV geschrieben nach {out_path} (chmod 600, nicht committen).")
    print(f"   Quelle es vor dem Spike:  set -a; source {out_path}; set +a")


if __name__ == "__main__":
    main()
