"""
Sanitization utilities for hiding credentials and PII.

- Hashes email addresses with MD5 (each address maps to a stable hash)
- Hashes phone numbers with MD5 (digits-normalized)
- Redacts credential fields when needed for logging
"""

import hashlib
import re
from typing import Dict, Any, List, Optional

# Regex to match email addresses (covers most common formats)
_EMAIL_PATTERN = re.compile(
    r"[a-zA-Z0-9._%+-]+@[a-zA-Z0-9.-]+\.[a-zA-Z]{2,}",
    re.IGNORECASE,
)

# Regex to match phone numbers (international and common formats)
_PHONE_PATTERN = re.compile(
    r"\+?\d{1,4}[-.\s]?\(?\d{2,4}\)?[-.\s]?\d{2,4}[-.\s]?\d{2,4}(?:[-.\s]?\d{2,4})?"
)

# Config keys that contain secrets (should not be logged or exposed)
_CREDENTIAL_KEYS = frozenset(
    {"client_secret", "api_key", "password", "access_token", "refresh_token"}
)


def _looks_like_hash(s: str) -> bool:
    """True if string looks like an MD5 hash (32 hex chars)."""
    return (
        isinstance(s, str)
        and len(s) == 32
        and all(c in "0123456789abcdef" for c in s.lower())
    )


def hash_email(email: str) -> str:
    """Return MD5 hash of a lowercase-normalized email address. Idempotent for already-hashed values."""
    if not email or not isinstance(email, str):
        return ""
    if _looks_like_hash(email):
        return email
    normalized = email.strip().lower()
    return hashlib.md5(normalized.encode("utf-8")).hexdigest()


def hash_emails(emails: List[str]) -> List[str]:
    """Return list of MD5 hashes for each email. Empty/invalid become empty strings. Idempotent for hashes."""
    return [hash_email(e) for e in emails if e]


def _normalize_phone(phone: str) -> str:
    """Extract digits only from phone string."""
    return "".join(c for c in phone if c.isdigit())


def replace_pii_in_text(text: str) -> str:
    """
    Replace all email addresses and phone numbers in text with their MD5 hashes.

    Args:
        text: Body or any string that may contain emails or phones

    Returns:
        Text with each email and phone replaced by its 32-char MD5 hex hash
    """
    if not text:
        return ""

    email_seen: Dict[str, str] = {}

    def email_replacer(match: re.Match) -> str:
        addr = match.group(0)
        key = addr.lower().strip()
        if key not in email_seen:
            email_seen[key] = hash_email(addr)
        return email_seen[key]

    result = _EMAIL_PATTERN.sub(email_replacer, text)

    phone_seen: Dict[str, str] = {}

    def phone_replacer(match: re.Match) -> str:
        raw = match.group(0)
        normalized = _normalize_phone(raw)
        if len(normalized) < 10 or len(normalized) > 15:
            return raw
        if normalized not in phone_seen:
            phone_seen[normalized] = hashlib.md5(normalized.encode("utf-8")).hexdigest()
        return phone_seen[normalized]

    return _PHONE_PATTERN.sub(phone_replacer, result)


def redact_credentials(config: Dict[str, Any]) -> Dict[str, Any]:
    """
    Return a copy of config with credential values redacted (for safe logging).
    """
    out = {}
    for k, v in config.items():
        key_lower = k.lower()
        if key_lower in _CREDENTIAL_KEYS and v:
            out[k] = "***REDACTED***"
        elif isinstance(v, dict):
            out[k] = redact_credentials(v)
        else:
            out[k] = v
    return out
