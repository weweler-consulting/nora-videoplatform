"""Einmaliger OAuth-Consent → Refresh-Token für den Live-Call-Import.

Voraussetzung: die heruntergeladene OAuth-Client-Secret-JSON (Desktop-App) aus der
Google Cloud Console (APIs & Dienste → Anmeldedaten → OAuth-Client-ID, Typ Desktop).

  python3 scripts/google_oauth_setup.py ~/Downloads/client_secret_xxx.json

Öffnet den Browser → als nora@noraweweler.de anmelden → Drive-Lesezugriff bestätigen.
Am Ende werden Client-ID, Secret und Refresh-Token als ENV-Zeilen ausgegeben.
"""
import json
import sys

from google_auth_oauthlib.flow import InstalledAppFlow

SCOPES = ["https://www.googleapis.com/auth/drive.readonly"]


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python3 scripts/google_oauth_setup.py <client_secret.json>", file=sys.stderr)
        sys.exit(1)
    secrets_path = sys.argv[1]

    flow = InstalledAppFlow.from_client_secrets_file(secrets_path, SCOPES)
    creds = flow.run_local_server(port=0, access_type="offline", prompt="consent")

    with open(secrets_path) as fh:
        installed = json.load(fh).get("installed", {})

    print("\n=== ENV-Variablen (lokal für den Spike + später auf dem Kurse-Container) ===")
    print(f"NORA_GOOGLE_OAUTH_CLIENT_ID='{installed.get('client_id')}'")
    print(f"NORA_GOOGLE_OAUTH_CLIENT_SECRET='{installed.get('client_secret')}'")
    print(f"NORA_GOOGLE_OAUTH_REFRESH_TOKEN='{creds.refresh_token}'")


if __name__ == "__main__":
    main()
