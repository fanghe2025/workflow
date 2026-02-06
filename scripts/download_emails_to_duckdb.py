"""
Download All Emails to DuckDB

This script downloads all emails from Microsoft Graph API and stores them
in DuckDB with raw text content.

Usage:
    python scripts/download_emails_to_duckdb.py
"""

import os
import sys
import json
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional, Tuple
import duckdb
import requests

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.graph_email_tagger import GraphEmailTagger, load_config
from scripts.common import html_to_text

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class EmailDownloader:
    """Download emails from Graph API and store in DuckDB"""

    def __init__(
        self,
        tagger: GraphEmailTagger,
        db_path: str = "data/emails.duckdb",
        attachments_dir: str = "data/attachments",
    ):
        """
        Initialize email downloader

        Args:
            tagger: GraphEmailTagger instance
            db_path: Path to DuckDB database file
            attachments_dir: Directory to save attachment files
        """
        self.tagger = tagger
        self.db_path = db_path
        self.attachments_dir = attachments_dir
        self.conn = None

        # Create attachments directory
        Path(attachments_dir).mkdir(parents=True, exist_ok=True)

    def connect_db(self):
        """Connect to DuckDB database"""
        # Create data directory if it doesn't exist
        db_dir = Path(self.db_path).parent
        db_dir.mkdir(parents=True, exist_ok=True)

        self.conn = duckdb.connect(self.db_path)
        self._create_table()
        logger.info(f"Connected to DuckDB database: {self.db_path}")

    def _create_table(self):
        """Create emails table if it doesn't exist"""
        create_table_sql = """
        CREATE TABLE IF NOT EXISTS emails (
            email_id VARCHAR PRIMARY KEY,
            thread_id VARCHAR,
            subject VARCHAR,
            from_email VARCHAR,
            from_name VARCHAR,
            body_content TEXT,
            tags VARCHAR,
            additional_tags VARCHAR,
            has_attachments BOOLEAN,
            received_at TIMESTAMP,
            raw_json TEXT,
            downloaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
        """
        self.conn.execute(create_table_sql)
        logger.info("Created/verified emails table")

        # Create attachments table
        create_attachments_table_sql = """
        CREATE TABLE IF NOT EXISTS attachments (
            attachment_id VARCHAR PRIMARY KEY,
            email_id VARCHAR,
            name VARCHAR,
            content_type VARCHAR,
            size INTEGER,
            file_path VARCHAR,
            downloaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (email_id) REFERENCES emails(email_id)
        )
        """
        self.conn.execute(create_attachments_table_sql)
        logger.info("Created/verified attachments table")

    def read_all_emails(
        self,
        folder: str = "inbox",
        filter_query: Optional[str] = None,
        batch_size: int = 100,
    ) -> List[Dict[str, Any]]:
        """
        Read all emails from specified folder with pagination

        Args:
            folder: Mail folder (inbox, sentitems, etc.)
            filter_query: OData filter query
            batch_size: Number of emails to fetch per request

        Returns:
            List of all email dictionaries
        """
        endpoint_base = self.tagger._get_user_endpoint_base()
        base_url = f"{self.tagger.graph_endpoint}{endpoint_base}/mailFolders/{folder}/messages"
        all_emails = []
        url = base_url
        page = 0
        use_next_link = False

        while True:
            params = None
            if not use_next_link:
                params = {
                    "$top": batch_size,
                    "$select": "id,subject,from,body,conversationId,receivedDateTime,hasAttachments,categories",
                    "$orderby": "receivedDateTime desc",
                }

                if filter_query:
                    params["$filter"] = filter_query

            try:
                page += 1
                logger.info(f"Fetching page {page} (batch size: {batch_size})...")
                response = requests.get(
                    url, headers=self.tagger.get_headers(), params=params
                )
                response.raise_for_status()
                data = response.json()
                emails = data.get("value", [])

                if not emails:
                    break

                all_emails.extend(emails)

                # Check if there are more emails using nextLink
                next_link = data.get("@odata.nextLink")
                if not next_link:
                    break

                # Use the nextLink URL directly (it already contains all parameters)
                url = next_link
                use_next_link = True

            except requests.exceptions.HTTPError as e:
                logger.error(f"HTTP error reading emails: {e}")
                if e.response is not None:
                    logger.error(f"Status code: {e.response.status_code}")
                    logger.error(f"Response: {e.response.text}")
                break
            except requests.exceptions.RequestException as e:
                logger.error(f"Error reading emails: {e}")
                break

        # Save all emails to a JSON file
        logger.info(f"Total emails retrieved: {len(all_emails)}")
        return all_emails

    def get_attachment_file_path(
        self, email_id: str, attachment_id: str, filename: str
    ) -> Path:
        """
        Get the expected file path for an attachment

        Args:
            email_id: Email ID
            attachment_id: Attachment ID
            filename: Original filename

        Returns:
            Path object for the attachment file
        """
        # Create subdirectory for email
        email_dir = Path(self.attachments_dir) / email_id
        email_dir.mkdir(parents=True, exist_ok=True)

        # Sanitize filename
        safe_filename = "".join(c for c in filename if c.isalnum() or c in "._- ")
        if not safe_filename:
            safe_filename = f"attachment_{attachment_id}"

        return email_dir / safe_filename

    def download_attachment(self, message_id: str, attachment_id: str) -> Optional[bytes]:
        """
        Download attachment content from Graph API

        Args:
            message_id: Email message ID
            attachment_id: Attachment ID

        Returns:
            Attachment content as bytes, or None if error
        """
        endpoint_base = self.tagger._get_user_endpoint_base()
        url = f"{self.tagger.graph_endpoint}{endpoint_base}/messages/{message_id}/attachments/{attachment_id}/$value"
        try:
            response = requests.get(url, headers=self.tagger.get_headers())
            response.raise_for_status()
            return response.content
        except requests.exceptions.RequestException as e:
            logger.warning(f"Error downloading attachment {attachment_id} from {message_id}: {e}")
            return None

    def save_attachment_file(
        self, email_id: str, attachment_id: str, filename: str, content: bytes
    ) -> Optional[str]:
        """
        Save attachment file to disk (only if it doesn't already exist)

        Args:
            email_id: Email ID
            attachment_id: Attachment ID
            filename: Original filename
            content: File content as bytes

        Returns:
            Path to saved file, or None if error
        """
        try:
            file_path = self.get_attachment_file_path(email_id, attachment_id, filename)

            # Skip writing if file already exists
            if file_path.exists():
                logger.debug(f"Attachment file already exists, skipping write: {file_path}")
                return str(file_path)

            # Write file
            with open(file_path, "wb") as f:
                f.write(content)

            return str(file_path)
        except Exception as e:
            logger.error(f"Error saving attachment file {filename}: {e}")
            return None

    def store_attachment(
        self, email_id: str, attachment: Dict[str, Any], file_path: Optional[str]
    ) -> bool:
        """
        Store attachment metadata in DuckDB

        Args:
            email_id: Email ID
            attachment: Attachment dictionary from Graph API
            file_path: Path to saved file

        Returns:
            True if successful, False otherwise
        """
        try:
            attachment_id = attachment.get("id")

            if not attachment_id:
                logger.error("Attachment ID is missing")
                return False

            if not email_id:
                logger.error("Email ID is missing for attachment")
                return False

            # Verify email exists before inserting attachment (foreign key constraint)
            check_email = "SELECT email_id FROM emails WHERE email_id = ?"
            email_exists = self.conn.execute(check_email, [email_id]).fetchone()
            if not email_exists:
                logger.error(f"Email {email_id} does not exist in database. Cannot insert attachment.")
                return False

            # Check if attachment already exists
            check_sql = "SELECT attachment_id FROM attachments WHERE attachment_id = ?"
            existing = self.conn.execute(check_sql, [attachment_id]).fetchone()

            if existing:
                # Update existing attachment
                update_sql = """
                UPDATE attachments SET
                    email_id = ?,
                    name = ?,
                    content_type = ?,
                    size = ?,
                    file_path = ?
                WHERE attachment_id = ?
                """
                self.conn.execute(
                    update_sql,
                    [
                        email_id,
                        attachment.get("name"),
                        attachment.get("contentType"),
                        attachment.get("size", 0),
                        file_path,
                        attachment_id,
                    ],
                )
            else:
                # Insert new attachment
                insert_sql = """
                INSERT INTO attachments (
                    email_id, attachment_id, name, content_type, size, file_path
                ) VALUES (?, ?, ?, ?, ?, ?)
                """
                self.conn.execute(
                    insert_sql,
                    [
                        email_id,
                        attachment_id,
                        attachment.get("name"),
                        attachment.get("contentType"),
                        attachment.get("size", 0),
                        file_path,
                    ],
                )
            return True
        except Exception as e:
            logger.error(f"Error storing attachment {attachment.get('id', 'unknown')}: {e}")
            return False

    def download_and_store_attachments(self, email_id: str, message_id: str) -> int:
        """
        Download and store all attachments for an email

        Args:
            email_id: Email ID (for database reference)
            message_id: Message ID (for Graph API)

        Returns:
            Number of attachments successfully downloaded and stored
        """
        if not email_id or not message_id:
            return 0

        # Get attachment list
        attachments = self.tagger.get_email_attachments(message_id)
        if not attachments:
            return 0

        logger.info(f"Downloading {len(attachments)} attachments for email {email_id}")

        stored_count = 0
        for attachment in attachments:
            attachment_id = attachment.get("id")
            attachment_name = attachment.get("name")

            # Get expected file path
            file_path_obj = self.get_attachment_file_path(email_id, attachment_id, attachment_name)
            file_path = str(file_path_obj)

            # Check if file already exists
            if file_path_obj.exists():
                logger.debug(f"Attachment file already exists, skipping download: {attachment_name}")
                # File exists, use it directly
            else:
                # Download attachment content from Graph API
                content = self.download_attachment(message_id, attachment_id)
                if not content:
                    logger.warning(f"Failed to download attachment {attachment_name}")
                    # Still store metadata even if download failed
                    self.store_attachment(email_id, attachment, None)
                    continue

                # Save file to disk
                saved_path = self.save_attachment_file(email_id, attachment_id, attachment_name, content)
                if not saved_path:
                    logger.warning(f"Failed to save attachment {attachment_name}")
                    # Still store metadata even if save failed
                    self.store_attachment(email_id, attachment, None)
                    continue
                file_path = saved_path

            # Store in database
            if self.store_attachment(email_id, attachment, file_path):
                stored_count += 1
                logger.debug(f"Stored attachment: {attachment_name}")
                # Commit after each attachment to ensure data is persisted
                self.conn.commit()

        return stored_count

    def store_email(self, email: Dict[str, Any]) -> Tuple[bool, int]:
        """
        Store email in DuckDB

        Args:
            email: Email dictionary from Graph API

        Returns:
            Tuple of (success: bool, attachment_count: int)
        """
        try:
            # Extract body content
            body = email.get("body", {})
            body_content = body.get("content", "")

            # Convert HTML to plain text if needed
            if body.get("contentType", "") == "html" and body_content:
                body_content = html_to_text(body_content)

            # Extract from address
            from_info = email.get("from", {}).get("emailAddress", {})
            from_email = from_info.get("address", "")
            from_name = from_info.get("name", "")

            # Parse dates
            received_at = email.get("receivedDateTime")

            # Convert categories list to string
            categories = email.get("categories", [])
            tags = ", ".join(categories) if categories else None

            # Store raw JSON
            raw_json = json.dumps(email)

            email_id = email.get("id")

            # Check if email exists to preserve additional_tags
            check_sql = "SELECT additional_tags FROM emails WHERE email_id = ?"
            existing = self.conn.execute(check_sql, [email_id]).fetchone()
            additional_tags = existing[0] if existing and existing[0] else None

            if existing:
                # Update existing email (preserve additional_tags)
                update_sql = """
                UPDATE emails SET
                    thread_id = ?,
                    subject = ?,
                    from_email = ?,
                    from_name = ?,
                    body_content = ?,
                    tags = ?,
                    has_attachments = ?,
                    received_at = ?,
                    raw_json = ?
                WHERE email_id = ?
                """
                self.conn.execute(
                    update_sql,
                    [
                        email.get("conversationId"),
                        email.get("subject"),
                        from_email,
                        from_name,
                        body_content,
                        tags,
                        email.get("hasAttachments", False),
                        received_at,
                        raw_json,
                        email_id,
                    ],
                )
            else:
                # Insert new email
                insert_sql = """
                INSERT INTO emails (
                    email_id, thread_id, subject, from_email, from_name,
                    body_content, tags, additional_tags, has_attachments, received_at, raw_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """
                self.conn.execute(
                    insert_sql,
                    [
                        email_id,
                        email.get("conversationId"),
                        email.get("subject"),
                        from_email,
                        from_name,
                        body_content,
                        tags,
                        additional_tags,  # Will be None for new emails
                        email.get("hasAttachments", False),
                        received_at,
                        raw_json,
                    ],
                )

            # Commit email first to ensure it's available for foreign key constraint
            self.conn.commit()

            # Download and store attachments if present
            attachment_count = 0
            if email.get("hasAttachments", False):
                message_id = email.get("id")
                attachment_count = self.download_and_store_attachments(email_id, message_id)

            return True, attachment_count
        except Exception as e:
            logger.error(f"Error storing email {email.get('id', 'unknown')}: {e}")
            return False, 0

    def download_and_store(
        self,
        folder: str = "inbox",
        filter_query: Optional[str] = None,
        batch_size: int = 100,
    ) -> Dict[str, Any]:
        """
        Download all emails and store in DuckDB

        Args:
            folder: Mail folder to download from
            filter_query: OData filter query
            batch_size: Number of emails per batch

        Returns:
            Summary dictionary with download results
        """
        logger.info(f"Starting email download from folder: {folder}")

        # Connect to database
        self.connect_db()

        # Read all emails
        emails = self.read_all_emails(
            folder=folder, filter_query=filter_query, batch_size=batch_size
        )

        if not emails:
            logger.warning("No emails found")
            return {"downloaded": 0, "stored": 0, "errors": 0, "attachments": 0}

        # Store emails
        results = {
            "downloaded": len(emails),
            "stored": 0,
            "errors": 0,
            "attachments": 0,
        }

        logger.info(f"Storing {len(emails)} emails in DuckDB...")
        for i, email in enumerate(emails, 1):
            if i % 100 == 0:
                logger.info(f"Storing email {i}/{len(emails)}...")

            success, attachment_count = self.store_email(email)
            if success:
                results["stored"] += 1
                results["attachments"] += attachment_count
            else:
                results["errors"] += 1

        # Commit transaction
        self.conn.commit()

        logger.info(
            f"Download complete: {results['downloaded']} downloaded, "
            f"{results['stored']} stored, {results['attachments']} attachments, "
            f"{results['errors']} errors"
        )

        return results

    def close(self):
        """Close database connection"""
        if self.conn:
            self.conn.close()
            logger.info("Database connection closed")


def main():
    """Main function"""
    # Load config
    config = load_config("config/graph_config.json")

    # Get credentials from config
    client_id = config.get("client_id")
    client_secret = config.get("client_secret")
    tenant_id = config.get("tenant_id")
    authority_url = config.get("authority_url")
    user_principal_name = config.get("user_principal_name")

    if not client_id:
        logger.error(
            "Client ID is required. Provide via config file or GRAPH_CLIENT_ID environment variable."
        )
        return 1

    # Initialize tagger
    tagger = GraphEmailTagger(
        client_id=client_id,
        client_secret=client_secret,
        tenant_id=tenant_id,
        authority_url=authority_url,
        user_principal_name=user_principal_name,
    )

    # Authenticate
    if not tagger.authenticate():
        logger.error("Authentication failed")
        return 1

    # Download and store emails
    db_path = config.get("db_path", "data/emails.duckdb")
    attachments_dir = config.get("attachments_dir", "data/attachments")
    folder = config.get("folder", "inbox")
    filter_query = config.get("filter")
    batch_size = config.get("batch_size", 100)

    downloader = EmailDownloader(tagger, db_path=db_path, attachments_dir=attachments_dir)
    try:
        results = downloader.download_and_store(
            folder=folder,
            filter_query=filter_query,
            batch_size=batch_size,
        )

        # Print summary
        print("\n" + "=" * 50)
        print("Download Summary")
        print("=" * 50)
        print(f"Downloaded: {results['downloaded']}")
        print(f"Stored: {results['stored']}")
        print(f"Attachments: {results.get('attachments', 0)}")
        print(f"Errors: {results['errors']}")
        print(f"Database: {db_path}")
        print(f"Attachments directory: {attachments_dir}")
        print("=" * 50)

        return 0 if results["errors"] == 0 else 1
    finally:
        downloader.close()


if __name__ == "__main__":
    sys.exit(main())
