"""Servicio de envío de emails via Resend."""
import asyncio
import logging
import os

import resend

logger = logging.getLogger(__name__)


def init_resend():
    resend.api_key = os.environ.get("RESEND_API_KEY", "")


def get_sender_email() -> str:
    return os.environ.get("SENDER_EMAIL", "onboarding@resend.dev")


async def send_email(to: str, subject: str, body_html: str) -> bool:
    """Envía un email. Retorna False en modo stub (sin API key)."""
    if not resend.api_key:
        logger.info(f"[EMAIL STUB] To:{to} Subject:{subject}")
        return False
    try:
        params = {
            "from": get_sender_email(),
            "to": [to],
            "subject": subject,
            "html": body_html,
        }
        await asyncio.to_thread(resend.Emails.send, params)
        return True
    except Exception as e:
        logger.error(f"Email error: {e}")
        return False
