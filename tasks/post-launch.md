# Post-Launch Backlog

Alles aus dem Go-Live-Audit, was bewusst nicht vor Launch gemacht wurde. Sortiert nach Risiko/Dringlichkeit. Go-Live-Blocker (Punkt 1–9) sind alle durch und deployed.

## 🔒 Security-Härtung (erste 2–4 Wochen)

- [ ] **JWT-TTL von 7 Tagen auf 24h kürzen + Refresh-Token einführen**
  `app/core/config.py:7` — aktuell 10080 Minuten. Ohne Refresh-Token fliegen Teilnehmerinnen sonst ständig raus. Plan: Access-Token 1h, Refresh-Token 30d in HttpOnly-Cookie.

- [ ] **PBKDF2 → bcrypt oder argon2 wechseln**
  `app/core/auth.py:21-30` — 100k PBKDF2-Rounds ist 2024 grenzwertig, OWASP empfiehlt 600k+. Migration: beim nächsten Login des Users rehashen, alte Hashes verifizieren weiterhin. `bcrypt` oder `argon2-cffi` einziehen.

- [ ] **JWT aus `localStorage` in HttpOnly-Cookie verlagern**
  `frontend/src/lib/api.ts:4` — XSS-anfällig. Braucht CSRF-Token-Handling dazu. Größerer Umbau (auch Backend).

- [ ] **Password-Reset-Token als "used" markieren**
  `app/api/auth.py:99-109` — Token wird auf NULL gesetzt nach Einlösen, aber keine Tracking-Spalte `used_at`. Defense-in-Depth, nicht akut.

- [ ] **Session-Invalidation bei Passwort-Change**
  `app/api/auth.py:change_password` — alte JWTs bleiben nach Passwort-Wechsel gültig bis Ablauf. Fix: JWT-Blacklist-Tabelle ODER `token_version`-Spalte auf User, die im JWT-Claim landet.

- [ ] **Bunny.net Upload: File-Type + Size-Validation**
  `app/api/upload.py` — derzeit kein Check auf Dateityp oder Größe beim `/create-video`. Direkt-Upload per TUS ist offen. Beschränken: nur `video/*`, max. N GB.

- [ ] **Security-Header in nginx.conf**
  `frontend/nginx.conf` — leer. Cloudron setzt HSTS, aber X-Frame-Options, X-Content-Type-Options, CSP fehlen. Minimum: `X-Frame-Options: DENY`, `X-Content-Type-Options: nosniff`.

## 📊 Ops / Monitoring (erste 1–2 Monate)

- [ ] **Sentry oder vergleichbares Error-Tracking**
  Aktuell: `logger.error(...)` landet in Cloudron-Logs, niemand liest die proaktiv. 500er-Fehler sind stumm. Sentry-SDK + DSN via ENV.

- [ ] **Alembic-Migrationen statt Ad-hoc-ALTER**
  `app/main.py:22-34` — jede neue Spalte braucht derzeit einen hardcoded `ALTER TABLE` mit `except: pass`. Funktioniert, aber bei komplexeren Schema-Changes (Renames, Data-Migrations, Indizes) fährt man blind. Alembic einführen **bevor** die DB große Datenmengen hat.

- [ ] **Backup-Strategie für Bunny-Videos**
  Cloudron-Postgres wird gebackupped, aber Bunny-Content nicht. Bei Bunny-Account-Verlust sind alle Videos weg. Plan: Stream-Export-Liste zyklisch ziehen (Bunny-API).

- [ ] **Vite: Source-Maps in Production-Build deaktivieren**
  `frontend/vite.config.ts` — aktuell default. `build.sourcemap = false` setzen, damit Original-Code nicht aus Prod-Bundle rekonstruierbar ist.

- [ ] **Frontend: `VITE_API_URL` als Build-Var**
  Falls Frontend mal separat (z.B. Vercel) deployed wird.

## ⚖️ Compliance / DSGVO

- [ ] **DSGVO-Datenexport**
  Teilnehmerin hat Recht auf Datenauskunft. Endpunkt `GET /api/v1/auth/me/export` → JSON-Download aller personenbezogenen Daten.

- [ ] **DSGVO-Löschung (Recht auf Vergessen)**
  Admin-Delete-User löscht aktuell hart. Für DSGVO-Requests sauberer: Anonymisierung (Email + Name werden zu Hash) statt Delete, damit Enrollment/Progress-Historie für Statistik erhalten bleibt. ODER: hartes Delete akzeptieren, dann muss `cascade` sauber sein (ist es laut Model).

- [ ] **Audit-Log für Admin-Aktionen**
  Invites, User-Deaktivierungen, Passwort-Resets — derzeit nirgends nachvollziehbar. Tabelle `admin_audit_log` mit `who/what/when/target`.

- [ ] **E-Mail-Verifikation bei Self-Registration**
  `app/api/auth.py:register` — aktuell wird jede E-Mail ohne Bestätigung akzeptiert. Nur relevant, falls `/register` jemals öffentlich angeboten wird (aktuell nicht, Invites-only-Flow).

## 💡 Nice-to-have (wenn Zeit / wenn Bedarf auftaucht)

- [ ] Password-Strength-Meter im Accept-Invite-Formular
- [ ] Passwort-Reset-Link: Verifikation, ob E-Mail existiert, nicht preisgeben (derzeit: identische Response unabhängig davon — ist aktuell schon richtig implementiert ✅)
- [ ] Resend-Webhook für Bounces/Complaints → User bei hartem Bounce automatisch deaktivieren
- [ ] Unsubscribe-Header in allen Mails (Deliverability / CAN-SPAM-äquivalent)
- [ ] Template-Engine (Jinja2) statt f-Strings für E-Mail-HTML
- [ ] Dev-Mode `MAIL_MOCK=true` für lokales Testen ohne echten Versand

---

**Letzter Stand:** Post-Launch-Backlog nach Abschluss der 9-Punkte-Go-Live-Liste. Go-Live-Commits: `9449f52`, `d156d21`, `cfdbc4c`, `f769bfc`.
