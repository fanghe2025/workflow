"""
Common utility functions for email processing scripts
"""

import re


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
