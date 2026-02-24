import json
import os

from core.duckdb import DatabaseConnection
from typing import List, Dict, Any


def load_emails(
    db_path="data/emails.duckdb", default_tag_name=None
) -> List[Dict[str, Any]]:
    """
    Load labeled emails from DuckDB or JSON file

    Args:
        data_path: Path to JSON file (legacy support)

    Returns:
        List of labeled email dictionaries
    """
    # Prefer DuckDB if provided
    if not os.path.exists(db_path):
        print(f"Warning: DuckDB file not found: {db_path}")
        return []

    db = DatabaseConnection(db_path=db_path, auto_init=False)
    conn = db.connect()
    # Query emails with labels from threads table
    # Get the first email (oldest Timestamp) for each thread
    query = """
    SELECT 
        e.Subject,
        e.Message,
        e.Sender,
        e.OtherRecipients,
        e.attachments,
        t.Tags
    FROM emails e
    LEFT JOIN threads t ON e.ThreadID = t.ThreadID
    QUALIFY ROW_NUMBER() OVER (PARTITION BY e.ThreadID ORDER BY e.Timestamp ASC) = 1
    """
    result = conn.execute(query).fetchall()
    columns = [
        "Subject",
        "Message",
        "Sender",
        "OtherRecipients",
        "attachments",
        "Tags",
    ]

    emails = []
    for row in result:
        email = dict(zip(columns, row))

        # Parse tags from JSON array string
        tags = (email["Tags"] or "").strip()
        tags = [t.strip() for t in tags.strip("[]").split(",") if t.strip()]
        email["Tags"] = tags or ([default_tag_name] if default_tag_name else [])

        # Parse attachments from JSON array string
        attachments = email["attachments"]
        try:
            attachments = json.loads(attachments)
        except Exception as e:
            attachments = []
        email["attachments"] = attachments

        other_recipients = email["OtherRecipients"]
        try:
            other_recipients = json.loads(other_recipients)
        except Exception as e:
            other_recipients = []
        email["OtherRecipients"] = other_recipients

        emails.append(email)

    print(f"Loaded {len(emails)} labeled emails from DuckDB")
    conn.close()
    return emails


def get_all_tags(emails=None):
    if not emails:
        emails = load_emails()
    labels = [e["Tags"] for e in emails]
    all_unique_labels = sorted(
        set(label for label_list in labels for label in label_list)
    )
    return all_unique_labels
