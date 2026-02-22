"""
Sanitization utilities for hiding credentials and PII.

- Hashes email addresses with MD5 (each address maps to a stable hash)
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


def replace_emails_in_text(
    text: str, additional_emails: Optional[List[str]] = None
) -> str:
    """
    Replace all email addresses in text with their MD5 hashes.

    Args:
        text: Body or any string that may contain email addresses
        additional_emails: Extra addresses to replace (e.g. from recipient list)

    Returns:
        Text with each email replaced by its 32-char MD5 hex hash
    """
    if not text:
        return ""

    seen: Dict[str, str] = {}

    def replacer(match: re.Match) -> str:
        addr = match.group(0)
        key = addr.lower().strip()
        if key not in seen:
            seen[key] = hash_email(addr)
        return seen[key]

    result = _EMAIL_PATTERN.sub(replacer, text)

    if additional_emails:
        for addr in additional_emails:
            if not addr or not isinstance(addr, str):
                continue
            key = addr.lower().strip()
            if key and key not in seen:
                seen[key] = hash_email(addr)
            h = seen.get(key, hash_email(addr))
            # Replace this specific address in result (handle case variations)
            result = re.sub(
                re.escape(addr),
                h,
                result,
                flags=re.IGNORECASE,
            )

    return result


def sanitize_email_for_storage(email: Dict[str, Any]) -> Dict[str, Any]:
    """
    Sanitize an email dict for storage: hash sender, recipients, and emails in body.

    Modifies a copy of the dict; does not mutate the original.
    """
    import copy

    email = copy.deepcopy(email)

    # Collect all email addresses we need to hash
    all_emails: List[str] = []

    from_info = email.get("from", {}).get("emailAddress", {})
    sender = from_info.get("address", "")
    if sender:
        all_emails.append(sender)

    for key in ("toRecipients", "ccRecipients", "bccRecipients"):
        for r in email.get(key, []):
            addr = r.get("emailAddress", {}).get("address", "")
            if addr:
                all_emails.append(addr)

    # Hash body content
    body = email.get("body", {})
    if isinstance(body, dict):
        content = body.get("content", "")
        if content:
            body["content"] = replace_emails_in_text(content, all_emails)

    # Hash addresses in recipient structures
    from_info = email.get("from", {}).get("emailAddress", {})
    if from_info.get("address"):
        from_info["address"] = hash_email(from_info["address"])

    for key in ("toRecipients", "ccRecipients", "bccRecipients"):
        for r in email.get(key, []):
            addr_obj = r.get("emailAddress", {})
            if addr_obj.get("address"):
                addr_obj["address"] = hash_email(addr_obj["address"])

    return email


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
