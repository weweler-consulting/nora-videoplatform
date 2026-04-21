# Einladungs-Flow mit Zustimmung (DSGVO-konform)

## Ziel
Aktuell: Admin klickt "Einladen" → Passwort wird im Klartext per Mail verschickt → User kann sofort einloggen. Kein Opt-in, keine AGB-Zustimmung.

Neu: Admin klickt "Einladen" → User bekommt Mail mit signiertem Token-Link → User öffnet Link → setzt **eigenes** Passwort + bestätigt **AGB & Datenschutz** → Account wird aktiviert und User landet direkt im Kurs.

## Design-Entscheidungen
- `hashed_password` bleibt NOT NULL, aber wird initial auf Leerstring `""` gesetzt. Login schlägt dann schon rein durch `verify_password` fehl.
- Zusätzlich prüft Login: wenn `invite_token` gesetzt → 403 mit klarer Meldung "Einladung noch nicht bestätigt".
- Token ist `secrets.token_urlsafe(32)`, gültig 7 Tage.
- Auf `/accept-invite?token=…` sieht User seinen Namen, die Kurstitel, E-Mail (read-only), setzt Passwort (min. 8 Zeichen), klickt AGB/Datenschutz-Checkbox.
- Bei Annahme: JWT wird zurückgegeben, User ist direkt eingeloggt.
- Stripe-Webhook nutzt denselben Flow — kein automatisch generiertes Passwort mehr.
- Existiert der User schon + ist aktiv: nur Enrollment hinzufügen, KEINE neue Invite-Mail (Bestandskundin, neuer Kurs).
- Existiert der User schon + hat offenen Invite: Token erneuern (7 Tage zurücksetzen), Mail neu schicken.

## Backend

- [x] `app/models/user.py`: Felder `invite_token`, `invite_token_expires`, `invite_accepted_at`, `terms_accepted_at` hinzufügen.
- [x] `app/main.py`: ALTER TABLE für die vier neuen Spalten + Index.
- [x] `app/core/email.py`: `send_invite_email` neu mit `(to_email, to_name, course_title, invite_url)`. Template: Button "Einladung annehmen", 7-Tage-Hinweis.
- [x] `app/core/auth.py`: `verify_password` gegen leeren Hash abgesichert.
- [x] `app/schemas/auth.py`: `InviteInfoResponse`, `AcceptInviteRequest`. Register-Passwort min_length=8.
- [x] `app/api/auth.py`:
  - Login: 403 wenn `invite_token` gesetzt und nicht akzeptiert.
  - `GET /invite/{token}` public → email/name/course_titles.
  - `POST /invite/accept` → setzt Passwort, Timestamps, JWT zurück.
- [x] `app/api/users.py`: InviteRequest ohne Passwort, Token-Flow, invite_url in Response, Refresh-Flow für offene Invites.
- [x] `app/api/stripe_webhook.py`: Invite-Token-Flow, keine generierten Passwörter mehr.

## Frontend

- [x] `frontend/src/lib/api.ts`: `getInvite`, `acceptInvite`, `inviteUser` ohne Passwort.
- [x] `frontend/src/pages/AcceptInvite.tsx`: Neue Seite mit Passwort + AGB-Checkbox.
- [x] `frontend/src/App.tsx`: Route `/accept-invite` public.
- [x] `frontend/src/pages/admin/AdminUsers.tsx`: Passwort-Feld raus, Result-Card zeigt Invite-Link.

## Verify

- [x] Python AST-parse aller geänderten Dateien OK
- [x] Frontend `tsc && vite build` OK
- [x] Alle Aufrufer von `send_invite_email` auf neue 4-Arg-Signatur umgestellt
- [ ] **Live-Test fehlt**: Lokal kein Docker/uvicorn vorhanden → muss auf Staging/Prod getestet werden
  - Admin lädt neuen User ein → Mail kommt an → Link funktioniert → Passwort setzen + AGB ticken → Dashboard
  - Bestandskunde bekommt zweiten Kurs zugewiesen → kein neuer Invite, direkt zugreifbar
  - Ungültiger/abgelaufener Token → Fehlerseite
  - Login mit pending invite → 403 mit korrekter Meldung

## Hinweise / bewusst offen

- Migration läuft beim App-Start automatisch (existierendes Muster, ohne Alembic). Bestandsnutzer: `invite_token`, `terms_accepted_at` bleiben NULL — Login funktioniert weiter.
- `hashed_password` bleibt NOT NULL, bei Invite-Erstellung wird Leerstring gesetzt. `verify_password` returnt False auf Leerstring — Login blockt.
- AGB/Datenschutz-Links zeigen auf `noraweweler.de/agbs` bzw. `noraweweler.de/datenschutz` (analog zum bestehenden Login-Footer).
- Resend-Flow funktioniert auch für Stripe-Webhook (gleiche `send_invite_email`-Funktion).
