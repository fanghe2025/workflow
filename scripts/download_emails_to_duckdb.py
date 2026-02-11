"""
Download All Emails to DuckDB

This script downloads all emails from Microsoft Graph API and stores them
in DuckDB with raw text content.

Usage:
    python scripts/download_emails_to_duckdb.py
"""

import argparse
import json
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.common import load_config
from utils.graph import get_authenticated_api_client
from core.email_downloader import EmailDownloader


def update_attachments(downloader: EmailDownloader):
    """Update attachments in DuckDB"""

    sql = "SELECT ID FROM emails WHERE attachments = '[]' and has_attachments = 1"
    emails = downloader.conn.execute(sql).fetchall()
    print(f"Updating {len(emails)} attachments")
    for email in emails:
        email_id = email[0]
        attachment_names = downloader.download_and_store_attachments(
            email_id, download=False
        )
        downloader.conn.execute(
            "UPDATE emails SET attachments = ? WHERE ID = ?",
            [
                json.dumps(attachment_names) if attachment_names else "[]",
                email_id,
            ],
        )
        downloader.conn.commit()


def main(args):
    """Main function"""

    # Load config
    api_client = get_authenticated_api_client()
    if not api_client:
        print("Failed to authenticate API client")
        return 1

    # Download and store emails
    config = load_config("config/graph_config.json")
    db_path = config.get("db_path", "data/emails.duckdb")
    attachments_dir = config.get("attachments_dir", "data/attachments")
    filter_query = config.get("filter")
    batch_size = config.get("batch_size", 100)

    downloader = EmailDownloader(
        api_client, db_path=db_path, attachments_dir=attachments_dir
    )

    try:
        if args.update_attachments:
            update_attachments(downloader)
        else:
            for folder in ("inbox", "archive"):
                downloader.download_and_store(
                    folder=folder,
                    filter_query=filter_query,
                    batch_size=batch_size,
                )
    finally:
        downloader.close()


if __name__ == "__main__":
    arg_parser = argparse.ArgumentParser(description="Reddit scraper")
    arg_parser.add_argument("--update-attachments", action="store_true")
    args = arg_parser.parse_args()

    sys.exit(main(args))
