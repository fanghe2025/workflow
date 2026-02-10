"""
Download All Emails to DuckDB

This script downloads all emails from Microsoft Graph API and stores them
in DuckDB with raw text content.

Usage:
    python scripts/download_emails_to_duckdb.py
"""

import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.common import load_config
from core.graph_api_client import GraphAPIClient
from core.email_downloader import EmailDownloader


def main():
    """Main function"""
    # Load config
    config = load_config("config/graph_config.json")

    # Get credentials from config
    client_id = config.get("client_id")
    client_secret = config.get("client_secret")
    tenant_id = config.get("tenant_id")
    user_email = config.get("user_email")

    if not client_id or not client_secret or not tenant_id:
        print("Credentials are required. Provide via config file")
        return 1

    # Initialize tagger
    api_client = GraphAPIClient(
        client_id=client_id,
        client_secret=client_secret,
        tenant_id=tenant_id,
        user_email=user_email,
    )

    # Authenticate
    if not api_client.authenticate():
        return 1

    # Download and store emails
    db_path = config.get("db_path", "data/emails.duckdb")
    attachments_dir = config.get("attachments_dir", "data/attachments")
    filter_query = config.get("filter")
    batch_size = config.get("batch_size", 100)

    downloader = EmailDownloader(
        api_client, db_path=db_path, attachments_dir=attachments_dir
    )

    try:
        for folder in ("inbox", "archive"):
            downloader.download_and_store(
                folder=folder,
                filter_query=filter_query,
                batch_size=batch_size,
            )
    finally:
        downloader.close()


if __name__ == "__main__":
    sys.exit(main())
