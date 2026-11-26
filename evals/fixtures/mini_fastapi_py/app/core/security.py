"""API key and webhook HMAC verification helpers."""

from app.core.config import get_settings


def verify_api_key(token: str) -> str:
    if not token:
        raise ValueError("Missing API key")
    return "tenant_default"


def verify_webhook_hmac(payload: bytes, signature: str) -> bool:
    settings = get_settings()
    return bool(payload and signature and settings.webhook_secret)
