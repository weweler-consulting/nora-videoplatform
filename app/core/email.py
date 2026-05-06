import os
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart


def get_smtp_config() -> dict | None:
    """Get SMTP config — prefers Resend, falls back to Cloudron."""
    resend_key = os.environ.get("RESEND_API_KEY")
    if resend_key:
        return {
            "server": "smtp.resend.com",
            "port": 465,
            "username": "resend",
            "password": resend_key,
            "from_addr": os.environ.get("MAIL_FROM", "Nora Weweler <nora@noraweweler.de>"),
        }
    # Fallback: Cloudron built-in SMTP
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


def _wrap_in_brand_template(body_html: str, unsubscribe_url: str | None = None) -> str:
    """Wrap body HTML in the Nora Weweler brand email template."""
    unsubscribe_footer = ""
    if unsubscribe_url:
        unsubscribe_footer = (
            f'<p style="margin: 8px 0 0 0; font-size: 11px; color: #aaa; text-align: center;">'
            f'<a href="{unsubscribe_url}" style="color: #aaa; text-decoration: underline;">Abmelden</a>'
            f"</p>"
        )

    return f"""<!DOCTYPE html>
<html lang="de">
<head>
  <meta charset="UTF-8">
  <meta name="viewport" content="width=device-width, initial-scale=1.0">
  <style>
    @import url('https://fonts.googleapis.com/css2?family=Almarai:wght@300;400;700&display=swap');
  </style>
</head>
<body style="margin: 0; padding: 0; background-color: #e3e3e3; font-family: 'Almarai', Arial, sans-serif;">
  <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="background-color: #e3e3e3;">
    <tr>
      <td align="center" style="padding: 40px 20px;">
        <table role="presentation" width="600" cellspacing="0" cellpadding="0" border="0" style="background-color: #fffef5; border-radius: 8px; overflow: hidden; box-shadow: 0 4px 20px rgba(0,0,0,0.08);">
          <tr>
            <td style="background-color: #fffef5; padding: 40px 50px 30px 50px; text-align: center;">
              <img src="https://noraweweler.de/images/nw-logo.webp" alt="Nora Weweler" width="90" style="display: block; margin: 0 auto 15px auto;">
              <p style="margin: 0; font-size: 12px; color: #D47479; letter-spacing: 3px; text-transform: uppercase;">
                Deine Kursplattform
              </p>
            </td>
          </tr>
          <tr>
            <td style="padding: 0 50px;">
              <table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0">
                <tr>
                  <td style="border-bottom: 2px solid #D47479; width: 60px;"></td>
                  <td></td>
                </tr>
              </table>
            </td>
          </tr>
          <tr>
            <td style="padding: 30px 50px 0 50px;">
              <table role="presentation" cellspacing="0" cellpadding="0" border="0">
                <tr>
                  <td style="vertical-align: middle; padding-right: 18px;">
                    <img src="https://noraweweler.de/nora-profile.001.jpeg" alt="Nora" width="70" height="70" style="border-radius: 50%; display: block; object-fit: cover;">
                  </td>
                  <td style="vertical-align: middle;">
                    <p style="margin: 0; font-size: 16px; font-weight: 700; color: #303030;">Nora Weweler</p>
                    <p style="margin: 2px 0 0 0; font-size: 13px; color: #888;">Deine Glukose Balance Mentorin</p>
                  </td>
                </tr>
              </table>
            </td>
          </tr>
          <tr>
            <td style="padding: 35px 50px 30px 50px; font-size: 15px; color: #303030; line-height: 1.8;">
              {body_html}
            </td>
          </tr>
          <tr>
            <td style="background-color: #f8f8f5; padding: 25px 50px; border-top: 1px solid #e3e3e3;">
              <p style="margin: 0; font-size: 13px; color: #888; text-align: center;">
                Nora Weweler Ern&auml;hrungsberatung<br>
                <a href="https://www.noraweweler.de" style="color: #D47479; text-decoration: none;">www.noraweweler.de</a>
              </p>
              {unsubscribe_footer}
            </td>
          </tr>
        </table>
      </td>
    </tr>
  </table>
</body>
</html>"""


def _cta_button(href: str, label: str) -> str:
    """Primary CTA button in brand style."""
    return (
        f'<table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="margin: 28px 0;">'
        f"<tr><td align=\"center\">"
        f'<a href="{href}" style="display: inline-block; background-color: #D47479; color: #ffffff; '
        f"padding: 16px 45px; border-radius: 4px; text-decoration: none; font-size: 15px; "
        f'font-weight: 700; letter-spacing: 1px; text-transform: uppercase;">{label}</a>'
        f"</td></tr></table>"
    )


def send_invite_email(
    to_email: str,
    to_name: str,
    course_title: str,
    invite_url: str,
) -> bool:
    """Send invite email with accept-invite link. Returns True if sent, False if SMTP not configured."""
    config = get_smtp_config()
    if not config:
        return False

    subject = f"Dein Zugang zum {course_title} ist da"

    text = f"""Hallo {to_name},

dein Zugang zum {course_title} ist bereit.

Klick auf den Button unten, vergib dein persoenliches Passwort, und du bist drin.

{invite_url}

Der Link ist 7 Tage gueltig.

Falls du diese Einladung nicht erwartet hast, kannst du diese E-Mail ignorieren.

Liebe Gruesse
Nora

P.S. Deinen Kurs erreichst du jederzeit unter kurse.noraweweler.de - speichere dir die Adresse gleich als Lesezeichen."""

    body_html = f"""<p style="margin: 0 0 16px 0;">Hallo {to_name},</p>
<p style="margin: 0 0 16px 0;">dein Zugang zum <strong>{course_title}</strong> ist bereit. 🌱</p>
<p style="margin: 0 0 8px 0;">Klick auf den Button unten, vergib dein pers&ouml;nliches Passwort, und du bist drin.</p>
{_cta_button(invite_url, "Einladung annehmen")}
<p style="margin: 0 0 8px 0; color: #888; font-size: 13px;">Der Link ist 7 Tage g&uuml;ltig.</p>
<p style="margin: 0 0 16px 0; color: #888; font-size: 13px;">Falls der Button nicht funktioniert, kopiere diese Adresse in deinen Browser:<br><a href="{invite_url}" style="color: #D47479; word-break: break-all;">{invite_url}</a></p>
<p style="margin: 24px 0 16px 0; color: #aaa; font-size: 12px;">Falls du diese Einladung nicht erwartet hast, kannst du diese E-Mail ignorieren.</p>
<p style="margin: 0 0 16px 0;">Liebe Gr&uuml;&szlig;e<br>Nora</p>
<p style="margin: 24px 0 0 0; padding: 14px 18px; background-color: #fdf2f4; border-left: 3px solid #D47479; font-size: 13px; color: #555; line-height: 1.65;"><strong style="color: #303030;">P.S.</strong> Deinen Kurs erreichst du jederzeit unter <a href="https://kurse.noraweweler.de" style="color: #D47479; font-weight: 700; text-decoration: none;">kurse.noraweweler.de</a> &mdash; speichere dir die Adresse gleich als Lesezeichen.</p>"""

    html = _wrap_in_brand_template(body_html)

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = config["from_addr"]
    msg["To"] = to_email
    msg.attach(MIMEText(text, "plain", "utf-8"))
    msg.attach(MIMEText(html, "html", "utf-8"))

    _send_smtp(config, msg)
    return True


def _send_smtp(config: dict, msg: MIMEMultipart):
    if config["port"] == 465:
        with smtplib.SMTP_SSL(config["server"], config["port"]) as smtp:
            smtp.login(config["username"], config["password"])
            smtp.send_message(msg)
    else:
        with smtplib.SMTP(config["server"], config["port"]) as smtp:
            try:
                smtp.starttls()
            except smtplib.SMTPNotSupportedError:
                pass  # Cloudron internal SMTP on port 2525 doesn't need TLS
            smtp.login(config["username"], config["password"])
            smtp.send_message(msg)


def send_course_added_email(
    to_email: str,
    to_name: str,
    course_title: str,
    login_url: str,
) -> bool:
    """Notify an existing, activated user that a new course has been added to their account."""
    config = get_smtp_config()
    if not config:
        return False

    subject = f"Dein neuer Kurs {course_title} ist freigeschaltet"

    text = f"""Hallo {to_name},

dein neuer Kurs {course_title} ist ab sofort in deinem Account verfuegbar.

Logg dich einfach ein und leg los:
{login_url}

Liebe Gruesse
Nora"""

    body_html = f"""<p style="margin: 0 0 16px 0;">Hallo {to_name},</p>
<p style="margin: 0 0 16px 0;">dein neuer Kurs <strong>{course_title}</strong> ist ab sofort in deinem Account verf&uuml;gbar. 🌱</p>
<p style="margin: 0 0 8px 0;">Logg dich einfach ein und leg los:</p>
{_cta_button(login_url, "Jetzt einloggen")}
<p style="margin: 0 0 16px 0; color: #888; font-size: 13px;">Falls der Button nicht funktioniert: <a href="{login_url}" style="color: #D47479;">{login_url}</a></p>
<p style="margin: 24px 0 0 0;">Liebe Gr&uuml;&szlig;e<br>Nora</p>"""

    html = _wrap_in_brand_template(body_html)

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = config["from_addr"]
    msg["To"] = to_email
    msg.attach(MIMEText(text, "plain", "utf-8"))
    msg.attach(MIMEText(html, "html", "utf-8"))

    _send_smtp(config, msg)
    return True


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

    body_html = f"""<p style="margin: 0 0 16px 0;">Hallo {to_name},</p>
<p style="margin: 0 0 16px 0;">gute Neuigkeiten! Ein neues Modul in deinem Kurs <strong>&quot;{course_title}&quot;</strong> wurde freigeschaltet:</p>
<table role="presentation" width="100%" cellspacing="0" cellpadding="0" border="0" style="margin: 24px 0;">
  <tr>
    <td style="background-color: #fdf2f4; border-radius: 6px; padding: 22px; text-align: center;">
      <p style="margin: 0; font-size: 17px; font-weight: 700; color: #b85a5f;">{module_title}</p>
    </td>
  </tr>
</table>
{_cta_button(login_url, "Jetzt weitermachen")}
<p style="margin: 24px 0 0 0;">Liebe Gr&uuml;&szlig;e<br>Nora</p>"""

    html = _wrap_in_brand_template(body_html)

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

    body_html = f"""<p style="margin: 0 0 16px 0;">Hallo {to_name},</p>
<p style="margin: 0 0 8px 0;">du hast angefordert, dein Passwort zur&uuml;ckzusetzen.</p>
{_cta_button(reset_url, "Neues Passwort vergeben")}
<p style="margin: 0 0 8px 0; color: #888; font-size: 13px;">Der Link ist 1 Stunde g&uuml;ltig.</p>
<p style="margin: 24px 0 16px 0; color: #aaa; font-size: 12px;">Falls du diese Anfrage nicht gestellt hast, kannst du diese E-Mail ignorieren.</p>
<p style="margin: 0;">Liebe Gr&uuml;&szlig;e<br>Nora</p>"""

    html = _wrap_in_brand_template(body_html)

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = config["from_addr"]
    msg["To"] = to_email
    msg.attach(MIMEText(text, "plain", "utf-8"))
    msg.attach(MIMEText(html, "html", "utf-8"))

    _send_smtp(config, msg)
    return True


def send_email_change_verification(to_email: str, to_name: str, confirm_url: str) -> bool:
    """Send verification link for an email-address change request."""
    config = get_smtp_config()
    if not config:
        return False

    subject = "Bestätige deine neue E-Mail-Adresse"

    text = f"""Hallo {to_name},

du hast angefordert, die E-Mail-Adresse für deinen Zugang auf {to_email} zu ändern.

Klicke auf den folgenden Link, um die Änderung zu bestätigen:

{confirm_url}

Der Link ist 1 Stunde gültig.

Falls du diese Anfrage nicht gestellt hast, kannst du diese E-Mail ignorieren — es wird nichts geändert.

Liebe Grüße
Nora"""

    body_html = f"""<p style="margin: 0 0 16px 0;">Hallo {to_name},</p>
<p style="margin: 0 0 8px 0;">du hast angefordert, die E-Mail-Adresse f&uuml;r deinen Zugang auf <strong>{to_email}</strong> zu &auml;ndern.</p>
{_cta_button(confirm_url, "E-Mail-Adresse bestätigen")}
<p style="margin: 0 0 8px 0; color: #888; font-size: 13px;">Der Link ist 1 Stunde g&uuml;ltig.</p>
<p style="margin: 24px 0 16px 0; color: #aaa; font-size: 12px;">Falls du diese Anfrage nicht gestellt hast, kannst du diese E-Mail ignorieren — es wird nichts ge&auml;ndert.</p>
<p style="margin: 0;">Liebe Gr&uuml;&szlig;e<br>Nora</p>"""

    html = _wrap_in_brand_template(body_html)

    msg = MIMEMultipart("alternative")
    msg["Subject"] = subject
    msg["From"] = config["from_addr"]
    msg["To"] = to_email
    msg.attach(MIMEText(text, "plain", "utf-8"))
    msg.attach(MIMEText(html, "html", "utf-8"))

    _send_smtp(config, msg)
    return True
