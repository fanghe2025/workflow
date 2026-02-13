"""
Common utility functions for email processing scripts
"""

import re
from pathlib import Path
from typing import Dict, Any
import json

from mailparser_reply import EmailReplyParser


def load_config(config_path: str = "config/graph_config.json") -> Dict[str, Any]:
    """Load Graph API configuration from JSON file"""
    config_file = Path(config_path)
    if not config_file.exists():
        print(f"Config file not found: {config_path}")
        return {}

    try:
        with open(config_file, "r") as f:
            return json.load(f)
    except Exception as e:
        print(f"Error loading config: {e}")
        return {}


def remove_from_closing(text):
    return re.split(
        r'\n\s*(best regards|kind regards|warm regards|regards|'
        r'thanks and regards|many thanks|thank you|thanks|'
        r'sincerely|yours sincerely|yours faithfully|'
        r'best|cheers)\b.*',
        text,
        flags=re.IGNORECASE
    )[0].strip()


def clean_message(message: str) -> str:
    """Clean a message by removing the closing and replies"""
    mail_message = EmailReplyParser().read(text=message)
    message = []
    for reply in mail_message.replies:
        res = clean_email_body(reply.full_body)
        message.append(res)

    return "\n".join(message)


def clean_email_body(email_body: str) -> str:
    if not email_body:
        return ""

    # Remove > quote markers
    text = re.sub(r'^\s*>+\s?', '', email_body, flags=re.MULTILINE)

    # remove external email
    text = re.sub(
        r'^.*external email.*$',
        '',
        text,
        flags=re.IGNORECASE | re.MULTILINE
    ).strip()

    # remove -------------------------
    text = text.replace("-------------------------", "")

    # remove mailto lines
    text = re.sub(
        r'^.*mailto:.*$',
        '',
        text,
        flags=re.IGNORECASE | re.MULTILINE
    ).strip()

    # Remove greeting line (if first line starts with Hi/Hello/etc.)
    text = re.sub(
        r'^(hi|hello|hey|dear)\b.*$',
        '',
        text.strip(),
        flags=re.IGNORECASE | re.MULTILINE
    )

    # Remove closing phrases and everything after
    text = re.split(
        r'\n\s*(best regards|all the best|kind regards|warm regards|regards|'
        r'thanks and regards|many thanks|thank you|thanks|'
        r'sincerely|yours sincerely|yours faithfully|'
        r'best|cheers)\b.*',
        text,
        flags=re.IGNORECASE
    )[0].strip()

    # Remove extra blank lines
    text = re.sub(r'\n\s*\n', '\n', text).strip()

    return text
