"""
Common utility functions for email processing scripts
"""

import re
from bs4 import BeautifulSoup


def html_to_text(html_content: str) -> str:
    """
    Convert HTML content to plain text

    Args:
        html_content: HTML string

    Returns:
        Plain text string
    """
    if not html_content:
        return ""

    try:
        soup = BeautifulSoup(html_content, "html.parser")
        # Get text and clean up whitespace
        text = soup.get_text(separator=" ", strip=True)
        # Normalize multiple spaces/newlines to single spaces
        text = re.sub(r"\s+", " ", text)
        return text.strip()
    except Exception as e:
        # Return original content if parsing fails
        return html_content
