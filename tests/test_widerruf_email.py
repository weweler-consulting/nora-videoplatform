"""Widerrufsbelehrung in der Kauf-Bestätigungsmail (Textform-Pflicht § 312f BGB).

Bei echten Käufen (Stripe-Webhook) muss die Mail die vollständige
Widerrufsbelehrung als Text enthalten. Bei manuellen CRM-Einladungen, die
denselben send_invite_email nutzen, darf sie NICHT erscheinen.
"""
import app.core.email as email


def _capture(monkeypatch):
    sent = {}
    monkeypatch.setattr(email, "get_smtp_config", lambda: {"from_addr": "Nora <nora@noraweweler.de>"})
    monkeypatch.setattr(email, "_send_smtp", lambda config, msg: sent.__setitem__("msg", msg))
    return sent


def _bodies(msg):
    parts = {}
    for part in msg.walk():
        ct = part.get_content_type()
        if ct in ("text/plain", "text/html"):
            parts[ct] = part.get_payload(decode=True).decode("utf-8")
    return parts


def test_invite_email_with_widerruf_contains_belehrung(monkeypatch):
    sent = _capture(monkeypatch)
    ok = email.send_invite_email("k@example.com", "Test", "Kurs", "https://kurse.noraweweler.de/x", with_widerruf=True)
    assert ok
    b = _bodies(sent["msg"])
    assert "Widerrufsbelehrung" in b["text/plain"]
    assert "vierzehn Tagen" in b["text/plain"]
    assert "Muster-Widerrufsformular" in b["text/plain"]
    assert "Widerrufsbelehrung" in b["text/html"]
    assert "Muster-Widerrufsformular" in b["text/html"]


def test_invite_email_default_has_no_widerruf(monkeypatch):
    sent = _capture(monkeypatch)
    email.send_invite_email("k@example.com", "Test", "Kurs", "https://kurse.noraweweler.de/x")
    b = _bodies(sent["msg"])
    assert "Widerrufsbelehrung" not in b["text/plain"]
    assert "Widerrufsbelehrung" not in b["text/html"]


def test_course_added_email_with_widerruf_contains_belehrung(monkeypatch):
    sent = _capture(monkeypatch)
    email.send_course_added_email("k@example.com", "Test", "Kurs", "https://kurse.noraweweler.de/login", with_widerruf=True)
    b = _bodies(sent["msg"])
    assert "Widerrufsbelehrung" in b["text/plain"]
    assert "Widerrufsbelehrung" in b["text/html"]
