import json
import os

from core.duckdb import DatabaseConnection
from typing import List, Dict, Any, Optional

from config import env


def load_emails(
    default_tag_name=None,
    year: Optional[int] = None,
    folder: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Load labeled emails from DuckDB or JSON file.

    Args:
        default_tag_name: Tag to use when thread has no tags.
        year: If set, only load emails from this year (by e.Timestamp).
        folder: If set, only load emails from this folder (inbox, archive, etc.).

    Returns:
        List of labeled email dictionaries.
    """
    if not os.path.exists(env.DUCKDB_PATH):
        print(f"Warning: DuckDB file not found")
        return []

    db = DatabaseConnection(db_path=env.DUCKDB_PATH, auto_init=False)
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
    WHERE 1=1
    """
    params = []
    if year is not None:
        query += " AND YEAR(e.Timestamp) = ?"
        params.append(year)
    if folder is not None:
        query += " AND t.current_folder = ?"
        params.append(folder)
    query += """
    QUALIFY ROW_NUMBER() OVER (PARTITION BY e.ThreadID ORDER BY e.Timestamp ASC) = 1
    """
    result = conn.execute(query, params).fetchall()
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
    print(f"All unique tags({len(all_unique_labels)}): {all_unique_labels}")
    return all_unique_labels
