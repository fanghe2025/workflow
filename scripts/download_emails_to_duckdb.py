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


def update_thread_tags(downloader: EmailDownloader):
    """Update tags in threads table, replacing 'Broadcast' with 'Broadcast-Linear'"""

    # Get all threads with tags
    sql = "SELECT ThreadID, Tags FROM threads WHERE Tags != '[]'"
    threads = downloader.conn.execute(sql).fetchall()

    print(f"Found {len(threads)} threads with tags")
    updated_count = 0

    for thread_id, tags_str in threads:
        if not tags_str:
            continue

        try:
            # Parse tags (format: "[tag1, tag2]" or similar)
            tags = [t.strip() for t in tags_str.strip("[]").split(",") if t.strip()]

            # Replace "Broadcast" with "Broadcast-Linear"
            updated_tags = []
            changed = False
            for tag in tags:
                if tag == "Broadcast":
                    updated_tags.append("Broadcast-Linear")
                    changed = True
                else:
                    updated_tags.append(tag)

            if changed:
                # Reconstruct tags string in the same format
                # Check if original had brackets
                if tags_str.strip().startswith("[") and tags_str.strip().endswith("]"):
                    new_tags_str = "[" + ", ".join(updated_tags) + "]"
                else:
                    new_tags_str = ", ".join(updated_tags)

                # Update the thread
                update_sql = "UPDATE threads SET Tags = ? WHERE ThreadID = ?"
                downloader.conn.execute(update_sql, [new_tags_str, thread_id])
                updated_count += 1

        except Exception as e:
            print(f"Error processing thread {thread_id}: {e}")
            continue

    downloader.conn.commit()
    print(
        f"Updated {updated_count} threads (replaced 'Broadcast' with 'Broadcast-Linear')"
    )


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
        elif args.update_tags:
            update_thread_tags(downloader)
        elif args.save_xlsx:
            downloader.save_xlsx()
        else:
            for folder in ("inbox", "archive"):
                downloader.download_and_store(
                    folder=folder,
                    filter_query=filter_query,
                    batch_size=batch_size,
                    limit=1000,
                )
    finally:
        downloader.close()


if __name__ == "__main__":
    arg_parser = argparse.ArgumentParser(description="Reddit scraper")
    arg_parser.add_argument("--update-attachments", action="store_true")
    arg_parser.add_argument("--update-tags", action="store_true")
    arg_parser.add_argument("--save-xlsx", action="store_true")
    args = arg_parser.parse_args()

    sys.exit(main(args))
