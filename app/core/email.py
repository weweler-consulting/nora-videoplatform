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

    with smtplib.SMTP(config["server"], config["port"]) as smtp:
        smtp.starttls()
        smtp.login(config["username"], config["password"])
        smtp.send_message(msg)

    return True
