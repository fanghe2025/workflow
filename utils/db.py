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


def load_emails_recent_per_tag(
    limit_per_tag: int = 100,
    year: Optional[int] = None,
    default_tag_name: Optional[str] = None,
) -> List[Dict[str, Any]]:
    """
    Load labeled emails from DuckDB, keeping the most recent `limit_per_tag` emails per tag.
    One row per thread (newest email in thread). Each email can have multiple tags.

    Args:
        limit_per_tag: Max number of emails to include per tag (default 100).
        year: If set, only emails from this year.
        default_tag_name: Tag to use when thread has no tags.

    Returns:
        List of email dicts (each has "Tags" and "Timestamp").
    """
    if not os.path.exists(env.DUCKDB_PATH):
        print("Warning: DuckDB file not found")
        return []

    db = DatabaseConnection(db_path=env.DUCKDB_PATH, auto_init=False)
    conn = db.connect()

    query = """
    SELECT 
        e.Subject,
        e.Message,
        e.Sender,
        e.OtherRecipients,
        e.attachments,
        t.Tags,
        e.Timestamp
    FROM emails e
    LEFT JOIN threads t ON e.ThreadID = t.ThreadID
    WHERE 1=1
    """
    params = []
    if year is not None:
        query += " AND YEAR(e.Timestamp) = ?"
        params.append(year)
    query += """
    QUALIFY ROW_NUMBER() OVER (PARTITION BY e.ThreadID ORDER BY e.Timestamp DESC) = 1
    """
    result = conn.execute(query, params).fetchall()
    conn.close()

    columns = [
        "Subject",
        "Message",
        "Sender",
        "OtherRecipients",
        "attachments",
        "Tags",
        "Timestamp",
    ]
    emails = []
    for row in result:
        email = dict(zip(columns, row))
        tags = (email["Tags"] or "").strip()
        tags = [t.strip() for t in tags.strip("[]").split(",") if t.strip()]
        email["Tags"] = tags or ([default_tag_name] if default_tag_name else [])
        try:
            email["attachments"] = (
                json.loads(email["attachments"]) if email["attachments"] else []
            )
        except Exception:
            email["attachments"] = []
        try:
            email["OtherRecipients"] = (
                json.loads(email["OtherRecipients"]) if email["OtherRecipients"] else []
            )
        except Exception:
            email["OtherRecipients"] = []
        emails.append(email)

    # Limit to recent limit_per_tag per tag (by timestamp desc)
    tag_to_indices: Dict[str, List[tuple]] = {}
    for i, email in enumerate(emails):
        ts = email.get("Timestamp")
        tags = email.get("Tags") or []
        if not tags:
            tags = ["__NO_TAG__"]
        for tag in tags:
            if tag not in tag_to_indices:
                tag_to_indices[tag] = []
            tag_to_indices[tag].append((i, ts))

    def _ts_sort_key(ts):
        if ts is None:
            return 0.0
        if hasattr(ts, "timestamp"):
            return ts.timestamp()
        return 0.0

    selected_indices = set()
    for tag, pairs in tag_to_indices.items():
        pairs.sort(key=lambda x: -_ts_sort_key(x[1]))
        for i, _ in pairs[:limit_per_tag]:
            selected_indices.add(i)

    out = [emails[i] for i in sorted(selected_indices)]
    for e in out:
        e.pop("Timestamp", None)
    print(
        f"Loaded {len(out)} labeled emails from DuckDB (recent {limit_per_tag} per tag)"
    )
    return out


def get_all_tags(emails=None):
    if not emails:
        emails = load_emails()
    labels = [e["Tags"] for e in emails]
    all_unique_labels = sorted(
        set(label for label_list in labels for label in label_list)
    )
    print(f"All unique tags({len(all_unique_labels)}): {all_unique_labels}")
    return all_unique_labels
