"""
Common utility functions for email processing scripts
"""

import re
from pathlib import Path
from typing import Dict, Any
import json


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
