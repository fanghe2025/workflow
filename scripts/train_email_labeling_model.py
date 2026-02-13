import ast
import json
import os
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
            e.attachments,
            t.Tags
        FROM emails e
        LEFT JOIN threads t ON e.ThreadID = t.ThreadID
        WHERE t.Tags != '[]'
        QUALIFY ROW_NUMBER() OVER (PARTITION BY e.ThreadID ORDER BY e.Timestamp ASC) = 1
        """
        result = conn.execute(query).fetchall()
        columns = [
            "Subject",
            "Message",
            "Sender",
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

            emails.append(email)

        print(f"Loaded {len(emails)} labeled emails from DuckDB")
        conn.close()
        return emails

    return []


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
