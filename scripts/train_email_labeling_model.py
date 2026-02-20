import ast
import json
import os
import random
import sys

from pathlib import Path
from typing import List, Dict, Any, Optional

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.constants import NO_LABEL
from core.db import DatabaseConnection
from core.email_labeling_model import EmailLabelingModel


def load_emails_from_db(db_path: Optional[str] = None) -> List[Dict[str, Any]]:
    """
    Load labeled emails from DuckDB or JSON file

    Args:
        data_path: Path to JSON file (legacy support)
        db_path: Path to DuckDB database file

    Returns:
        List of labeled email dictionaries
    """
    # Prefer DuckDB if provided
    if db_path:
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
            tags = email["Tags"]
            try:
                tags = [t.strip() for t in tags.strip("[]").split(",") if t.strip()]
                if len(tags) == 0:
                    email["Tags"] = [NO_LABEL]
                else:
                    email["Tags"] = tags
            except Exception as e:
                email["Tags"] = [NO_LABEL]

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

    return []


def limit_samples_per_tag(
    emails: List[Dict[str, Any]], max_per_tag: int, random_state: Optional[int] = 42
) -> List[Dict[str, Any]]:
    """
    Limit training data to at most max_per_tag emails per tag.
    Emails can have multiple tags; each email is included if it's sampled for any tag.

    Args:
        emails: List of labeled email dicts (must have "Tags" key)
        max_per_tag: Maximum number of emails to use per tag
        random_state: Random seed for reproducible sampling

    Returns:
        Subset of emails
    """
    if max_per_tag is None or max_per_tag <= 0:
        return emails

    rng = random.Random(random_state)

    # Build tag -> emails mapping (by index to preserve uniqueness)
    tag_to_indices: Dict[str, set] = {}
    for i, email in enumerate(emails):
        tags = email.get("Tags", [])
        if not tags:
            continue
        for tag in tags:
            if tag not in tag_to_indices:
                tag_to_indices[tag] = set()
            tag_to_indices[tag].add(i)

    # For each tag, sample at most max_per_tag email indices
    selected_indices = set()
    for tag, indices in tag_to_indices.items():
        indices_list = list(indices)
        if len(indices_list) <= max_per_tag:
            selected_indices.update(indices_list)
        else:
            selected_indices.update(rng.sample(indices_list, max_per_tag))

    return [emails[i] for i in sorted(selected_indices)]


def main():
    """Main training function"""
    # Load configuration
    config_path = Path("config/training_config.json")
    if config_path.exists():
        with open(config_path, "r") as f:
            config = json.load(f)
    else:
        config = {}
        print("Warning: training_config.json not found. Using defaults.")

    # Get paths from config
    paths = config.get("paths", {})
    db_path = paths.get("db_path", "data/emails.duckdb")
    model_path = paths.get("model_output", "models/email_classifier.pkl")

    # Create directories
    Path("data").mkdir(exist_ok=True)
    Path("models").mkdir(exist_ok=True)

    # Load labeled emails (prefer DuckDB, fallback to JSON)
    print("Loading labeled emails...")
    emails = load_emails_from_db(db_path=db_path)

    # Limit to max_samples_per_tag if configured
    training_cfg = config.get("training", {})
    max_per_tag = training_cfg.get("max_samples_per_tag")
    if max_per_tag is not None and max_per_tag > 0:
        random_state = training_cfg.get("random_state", 42)
        before = len(emails)
        emails = limit_samples_per_tag(emails, max_per_tag, random_state)
        print(
            f"Limited to {max_per_tag} samples per tag: {before} -> {len(emails)} emails"
        )

    if not emails:
        print("No emails found.")
        return

    # Initialize and train model
    model = EmailLabelingModel(model_path=model_path, config=config)

    try:
        model.train(emails)
        print("\nTraining completed successfully!")
    except Exception as e:
        print(f"Error during training: {e}")


if __name__ == "__main__":
    main()
