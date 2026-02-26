"""
Common utility functions for email processing scripts
"""

import re

from mailparser_reply import EmailReplyParser

from utils.sanitize import replace_pii_in_text


def clean_message(message: str) -> str:
    """Clean a message by removing the closing and replies; replace emails and phone numbers with MD5 hashes."""
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
    # text = re.sub(
    #     r"^.*mailto:.*$", "", text, flags=re.IGNORECASE | re.MULTILINE
    # ).strip()

    # Remove greeting line (if first line starts with Hi/Hello/etc.)
    # text = re.sub(
    #     r"^(hi|hello|hey|dear)\b.*$",
    #     "",
    #     text.strip(),
    #     flags=re.IGNORECASE | re.MULTILINE,
    # )

    # Remove closing phrases and everything after
    pattern = re.compile(
        r"^\s*(best regards|kind regards|warm regards|with regards|regards|"
        r"thanks and regards|many thanks|thank you|thanks|"
        r"sincerely|yours sincerely|yours faithfully|"
        r"best|cheers|\[premeire digital services\])[\s!,/]*$",
        re.IGNORECASE | re.MULTILINE,
    )
    match = pattern.search(text)
    if match:
        text = text[: match.start()].strip()

    # remove a links
    text = re.sub(r"<https://[^>]*>", "", text)

    # Remove extra blank lines
    # text = re.sub(r"\n\s*\n", "\n", text).strip()
    text = text.replace("\n", " ").replace("  ", " ")

    # Hide PII: replace email addresses and phone numbers with MD5 hashes
    text = replace_pii_in_text(text)

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
