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


def clean_message(message: str) -> str:
    """Clean a message by removing the closing and replies"""
    mail_message = EmailReplyParser().read(text=message)
    message = []
    for reply in mail_message.replies:
        res = clean_body(reply.full_body)
        message.append(res)

    return "\n".join(message)


def clean_body(email_body: str) -> str:
    if not email_body:
        return ""

    # Remove > quote markers
    text = re.sub(r"^\s*>+\s?", "", email_body, flags=re.MULTILINE)

    # remove external email
    # text = re.sub(
    #     r"^.*external email.*$", "", text, flags=re.IGNORECASE | re.MULTILINE
    # ).strip()

    # remove -------------------------
    text = text.replace("-------------------------", "")

    # remove mailto lines
    text = re.sub(
        r"^.*mailto:.*$", "", text, flags=re.IGNORECASE | re.MULTILINE
    ).strip()

    # Remove greeting line (if first line starts with Hi/Hello/etc.)
    # text = re.sub(
    #     r"^(hi|hello|hey|dear)\b.*$",
    #     "",
    #     text.strip(),
    #     flags=re.IGNORECASE | re.MULTILINE,
    # )

    # Remove closing phrases and everything after
    text = re.split(
        r"\n\s*(best regards|kind regards|warm regards|regards|"
        r"thanks and regards|many thanks|thank you|thanks|"
        r"sincerely|yours sincerely|yours faithfully|"
        r"best|cheers)\b.*",
        text,
        flags=re.IGNORECASE,
    )[0].strip()

    # remove a links
    text = re.sub(r"<https://[^>]*>", "", text)

    # Remove extra blank lines
    # text = re.sub(r'\n\s*\n', '\n', text).strip()
    text = text.replace("\n", " ").replace("  ", " ")

    return text


def clean_email_body(email_body: str) -> str:
    if not email_body:
        return ""

    # Remove email headers: From:, Sent:, To:, Subject:
    # Match lines that start with these headers (case-insensitive)
    pattern = r"^(From:|Sent:|To:|Cc:|Subject:|Telephone:|Email:|-EXTERNAL EMAIL-|EXTERNAL EMAIL|LIONS GATE INTERNATIONAL).*$"
    lines = email_body.split("\r\n")
    cleaned_lines = []
    skip_until_delimiter = False

    for line in lines:
        line = line.replace("\n", "").strip()

        # Skip empty lines
        if not line:
            continue

        # Check if we should start skipping (found [Premeire Digital Services])
        if "[Premeire Digital Services]" in line:
            skip_until_delimiter = True
            continue

        # Check if we found the delimiter (stop skipping)
        if skip_until_delimiter and "_____________________" in line:
            skip_until_delimiter = False

        # Skip lines while in removal mode
        if skip_until_delimiter:
            continue

        # Skip email headers
        if re.match(pattern, line, re.IGNORECASE):
            continue

        if "m:" in line.lower() and "e:" in line.lower():
            continue

        cleaned_lines.append(line)

    return "\n".join(cleaned_lines).strip()
