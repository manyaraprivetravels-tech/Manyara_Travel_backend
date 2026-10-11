

import logging

import httpx

from app.core.config import settings

logger = logging.getLogger("email")

RESEND_URL = "https://api.resend.com/emails"


def _send_email(to: str, subject: str, text: str, html: str | None = None) -> bool:
    payload = {
        "from": settings.EMAIL_FROM,
        "to": [to],
        "subject": subject,
        "text": text,
    }
    if html:
        payload["html"] = html
    if settings.EMAIL_REPLY_TO:
        payload["reply_to"] = settings.EMAIL_REPLY_TO

    try:
        response = httpx.post(
            RESEND_URL,
            headers={"Authorization": f"Bearer {settings.RESEND_API_KEY}"},
            json=payload,
            timeout=10,
        )
        response.raise_for_status()
        logger.info("Email sent to %s (id=%s)", to, response.json().get("id"))
        return True
    except httpx.HTTPStatusError as exc:
        logger.error(
            "Resend rejected email to %s: %s %s",
            to,
            exc.response.status_code,
            exc.response.text,
        )
    except httpx.TimeoutException:
        logger.error("Timed out sending email to %s", to)
    except Exception:
        logger.exception("Unexpected error sending email to %s", to)
    return False


def send_password_reset_email(recipient_email: str, otp: str) -> None:
    logger.info("Sending password reset email to %s", recipient_email)

    text = (
        "Hello,\n\n"
        "We received a request to reset your Manyara Prive Vacations account password.\n\n"
        f"Your verification code is: {otp}\n\n"
        f"This code is valid for {settings.OTP_EXPIRY_MINUTES} minutes.\n"
        "If you did not request this, please ignore this email.\n"
        "For your security, never share this code with anyone.\n\n"
        "Regards,\n"
        "Manyara Prive Vacations Team"
    )

    html = f"""
    <div style="font-family:Arial,sans-serif;max-width:480px;margin:auto;padding:24px;">
      <h2 style="color:#9f1d4a;margin:0 0 12px;">Manyara Privé Vacations</h2>
      <p>We received a request to reset your account password.</p>
      <p>Your verification code is:</p>
      <p style="font-size:32px;letter-spacing:8px;font-weight:bold;margin:16px 0;">{otp}</p>
      <p>This code is valid for {settings.OTP_EXPIRY_MINUTES} minutes.</p>
      <p style="color:#666;font-size:13px;">
        If you did not request this, you can safely ignore this email.
        Never share this code with anyone.
      </p>
    </div>
    """

    _send_email(
        to=recipient_email,
        subject="Manyara Prive Vacations - Password Reset Code",
        text=text,
        html=html,
    )

    



























# import smtplib
# from email.message import EmailMessage

# from app.core.config import settings


# def send_password_reset_email(
#     recipient_email: str,
#     otp: str,
# ) -> None:
#     message = EmailMessage()

#     message["Subject"] = "Manyara Prive Vacations - Password Reset Verification Code"
#     message["From"] = settings.EMAIL_FROM
#     message["To"] = recipient_email

#     message.set_content(
#         f"""
# Hello,

# We received a request to reset your Manyara Prive Vacations account password.

# Your password reset verification code is:

# {otp}

# This verification code is valid for 2 minutes.

# If you did not request a password reset, please ignore this email.

# For security reasons, do not share this code with anyone.

# Regards,
# Manyara Prive Vacations Team
# """.strip()
#     )

#     with smtplib.SMTP(
#         settings.SMTP_HOST,
#         settings.SMTP_PORT,
#     ) as server:

#         if settings.SMTP_USE_TLS:
#             server.starttls()

#         server.login(
#             settings.SMTP_USERNAME,
#             settings.SMTP_PASSWORD,
#         )

#         server.send_message(message)