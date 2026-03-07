import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart


def get_smtp_config() -> dict | None:
    """Get SMTP config from Cloudron environment variables."""
    server = os.environ.get("CLOUDRON_MAIL_SMTP_SERVER")
    port = os.environ.get("CLOUDRON_MAIL_SMTP_PORT")
    username = os.environ.get("CLOUDRON_MAIL_SMTP_USERNAME")
    password = os.environ.get("CLOUDRON_MAIL_SMTP_PASSWORD")
    from_addr = os.environ.get("CLOUDRON_MAIL_FROM")
    if not all([server, port, username, password, from_addr]):
        return None
    return {
        "server": server,
        "port": int(port),
        "username": username,
        "password": password,
        "from_addr": from_addr,
    }


def send_invite_email(
    to_email: str,
    to_name: str,
    course_title: str,
    password: str,
    login_url: str,
) -> bool:
    """Send invite email. Returns True if sent, False if SMTP not configured."""
    config = get_smtp_config()
    if not config:
        return False

    subject = f"Dein Zugang zum Kurs \"{course_title}\""

    text = f"""Hallo {to_name},

du hast Zugang zum Kurs "{course_title}" erhalten!

Hier sind deine Zugangsdaten:

Link: {login_url}
E-Mail: {to_email}
Passwort: {password}

Bitte aendere dein Passwort nach dem ersten Login unter Einstellungen.

Liebe Gruesse
Nora"""

    html = f"""<div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; max-width: 500px; margin: 0 auto; padding: 32px;">
  <h2 style="color: #d4768c; font-weight: 300; font-style: italic; margin-bottom: 24px;">Nora Weweler</h2>
  <p>Hallo {to_name},</p>
  <p>du hast Zugang zum Kurs <strong>"{course_title}"</strong> erhalten!</p>
  <div style="background: #fdf2f4; border-radius: 12px; padding: 20px; margin: 24px 0;">
    <p style="margin: 0 0 8px;"><strong>Link:</strong> <a href="{login_url}" style="color: #d4768c;">{login_url}</a></p>
    <p style="margin: 0 0 8px;"><strong>E-Mail:</strong> {to_email}</p>
    <p style="margin: 0;"><strong>Passwort:</strong> {password}</p>
  </div>
  <p style="color: #888; font-size: 14px;">Bitte &auml;ndere dein Passwort nach dem ersten Login unter Einstellungen.</p>
  <p>Liebe Gr&uuml;&szlig;e<br>Nora</p>
</div>"""

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = config["from_addr"]
    msg["To"] = to_email
    msg.attach(MIMEText(text, "plain", "utf-8"))
    msg.attach(MIMEText(html, "html", "utf-8"))

    _send_smtp(config, msg)
    return True


def _send_smtp(config: dict, msg: MIMEMultipart):
    with smtplib.SMTP(config["server"], config["port"]) as smtp:
        try:
            smtp.starttls()
        except smtplib.SMTPNotSupportedError:
            pass  # Cloudron internal SMTP on port 2525 doesn't need TLS
        smtp.login(config["username"], config["password"])
        smtp.send_message(msg)


def send_module_unlocked_email(
    to_email: str,
    to_name: str,
    module_title: str,
    course_title: str,
    login_url: str,
) -> bool:
    """Send notification that a new module has been unlocked."""
    config = get_smtp_config()
    if not config:
        return False

    subject = f"Neues Modul freigeschaltet: {module_title}"

    text = f"""Hallo {to_name},

gute Neuigkeiten! Ein neues Modul in deinem Kurs "{course_title}" wurde freigeschaltet:

{module_title}

Schau gleich rein und mach weiter:
{login_url}

Liebe Gruesse
Nora"""

    html = f"""<div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; max-width: 500px; margin: 0 auto; padding: 32px;">
  <h2 style="color: #d4768c; font-weight: 300; font-style: italic; margin-bottom: 24px;">Nora Weweler</h2>
  <p>Hallo {to_name},</p>
  <p>gute Neuigkeiten! Ein neues Modul in deinem Kurs <strong>&quot;{course_title}&quot;</strong> wurde freigeschaltet:</p>
  <div style="background: #fdf2f4; border-radius: 12px; padding: 20px; margin: 24px 0; text-align: center;">
    <p style="margin: 0; font-size: 18px; font-weight: 600; color: #b85a5f;">{module_title}</p>
  </div>
  <div style="text-align: center; margin: 32px 0;">
    <a href="{login_url}" style="background: #D47479; color: white; padding: 12px 32px; border-radius: 8px; text-decoration: none; font-weight: 500;">Jetzt weitermachen</a>
  </div>
  <p>Liebe Gr&uuml;&szlig;e<br>Nora</p>
</div>"""

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = config["from_addr"]
    msg["To"] = to_email
    msg.attach(MIMEText(text, "plain", "utf-8"))
    msg.attach(MIMEText(html, "html", "utf-8"))

    _send_smtp(config, msg)
    return True


def send_password_reset_email(to_email: str, to_name: str, reset_url: str) -> bool:
    """Send password reset email. Returns True if sent."""
    config = get_smtp_config()
    if not config:
        return False

    subject = "Passwort zurücksetzen"

    text = f"""Hallo {to_name},

du hast angefordert, dein Passwort zurückzusetzen.

Klicke auf den folgenden Link, um ein neues Passwort zu vergeben:

{reset_url}

Der Link ist 1 Stunde gültig.

Falls du diese Anfrage nicht gestellt hast, kannst du diese E-Mail ignorieren.

Liebe Grüße
Nora"""

    html = f"""<div style="font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', sans-serif; max-width: 500px; margin: 0 auto; padding: 32px;">
  <h2 style="color: #d4768c; font-weight: 300; font-style: italic; margin-bottom: 24px;">Nora Weweler</h2>
  <p>Hallo {to_name},</p>
  <p>du hast angefordert, dein Passwort zur&uuml;ckzusetzen.</p>
  <div style="text-align: center; margin: 32px 0;">
    <a href="{reset_url}" style="background: #D47479; color: white; padding: 12px 32px; border-radius: 8px; text-decoration: none; font-weight: 500;">Neues Passwort vergeben</a>
  </div>
  <p style="color: #888; font-size: 14px;">Der Link ist 1 Stunde g&uuml;ltig.</p>
  <p style="color: #888; font-size: 14px;">Falls du diese Anfrage nicht gestellt hast, kannst du diese E-Mail ignorieren.</p>
  <p>Liebe Gr&uuml;&szlig;e<br>Nora</p>
</div>"""

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = config["from_addr"]
    msg["To"] = to_email
    msg.attach(MIMEText(text, "plain", "utf-8"))
    msg.attach(MIMEText(html, "html", "utf-8"))

    _send_smtp(config, msg)
    return True
