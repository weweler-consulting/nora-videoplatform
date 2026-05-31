# Hardening: Stripe-Webhook Idempotenz — stiller Zahlungsverlust (F1)

Aufgeschrieben: 2026-05-31 · Priorität: hoch (Geld-Pfad, Live-Betrieb) · noch offen

## Problem

In `app/api/stripe_webhook.py` wird das Stripe-Event **als „verarbeitet" markiert
und committed, BEVOR** die Enrollments geschrieben sind:

1. Pre-Check (Produkt → Kurs match) → ok
2. `StripeProcessedEvent` einfügen + **commit** (eigene Transaktion)
3. `_handle_checkout_completed` → User anlegen, Enrollments, **commit**

Crasht Schritt 3 (DB-Hiccup, Deploy-Restart genau im Fenster, etc.), ist das Event
in Schritt 2 schon als verarbeitet markiert. Stripe schickt zwar einen Retry — der
trifft beim erneuten Claim auf den `IntegrityError` und wird als
`{"duplicate": True}` mit 200 quittiert. **Ergebnis: Kundin hat gezahlt, bekommt
keinen Zugang, kein weiterer Retry, kein Alarm.**

Betrifft ALLE Produkte (auch Frühstücks-Code), vorbestehend — nicht durch die
Bundle-Änderung eingeführt.

Risiko-Fenster ist schmal (nur Exception zwischen den zwei Commits), aber der
Schaden ist maximal (stiller Zahlungsverlust).

## Lösungsoptionen

- **A (sauber):** Event-Claim und Enrollment in EINER Transaktion committen — Event
  gilt erst als verarbeitet, wenn die Freischaltung wirklich drin ist. Idempotenz
  bleibt über die Unique-PK von `stripe_processed_events` erhalten.
- **B (Sicherheitsnetz):** Bei Exception nach dem Claim das Event wieder freigeben
  (Row löschen) ODER in eine Dead-Letter-Tabelle schreiben + Alarm-Mail an Nora.
- **C (Monitoring):** Täglicher Abgleich Stripe-Zahlungen ↔ Enrollments, Diff melden.

Empfehlung: **A**, mit Tests, als eigener PR (nicht in launch-kritische Changes
mischen). B als günstiges Sicherheitsnetz zusätzlich denkbar.

## Warum nicht sofort gefixt

Eingriff in die Idempotenz-/Transaktions-Grenze auf einem Live-Geld-Pfad. Hastig
umgebaut ist das riskanter als der Bug selbst (Gefahr: Doppel-Verarbeitung).
Gehört in einen fokussierten, getesteten PR.
