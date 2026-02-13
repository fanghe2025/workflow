import logging
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from core.db import DatabaseConnection
from core.graph_api_client import GraphAPIClient
from utils.common import clean_email_body, clean_message


logger = logging.getLogger(__name__)


class EmailDownloader:
    """Download emails from Microsoft Graph API and store in DuckDB"""

    def __init__(
        self,
        api_client: GraphAPIClient,
        db_path: str = "data/emails.duckdb",
        attachments_dir: str = "data/attachments",
    ):
        """
        Initialize email downloader

        Args:
            api_client: GraphAPIClient instance
            db_path: Path to DuckDB database file
            attachments_dir: Directory to save attachment files
        """
        self.api_client = api_client
        self.attachments_dir = attachments_dir

        self.db = DatabaseConnection(db_path=db_path)
        self.conn = self.db.connect()

        # Create attachments directory
        Path(attachments_dir).mkdir(parents=True, exist_ok=True)

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
                logger.debug(
                    f"Attachment file already exists, skipping write: {file_path}"
                )
                return str(file_path)

            # Write file
            with open(file_path, "wb") as f:
                f.write(content)

            return str(file_path)
        except Exception as e:
            logger.error(f"Error saving attachment file {filename}: {e}")
            return None

    def store_attachment(
        self, email_id: str, attachment: Dict[str, Any], file_path: Optional[str] = None
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

            # Check if attachment already exists
            check_sql = "SELECT attachment_id FROM attachments WHERE attachment_id = ?"
            existing = self.conn.execute(check_sql, [attachment_id]).fetchone()

            if not existing:
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
                self.conn.commit()
            return True
        except Exception as e:
            logger.error(
                f"Error storing attachment {attachment.get('id', 'unknown')}: {e}"
            )
            return False

    def download_and_store_attachments(
        self, email_id: str, download: bool = True
    ) -> List[str]:
        """
        Download and store all attachments for an email

        Args:
            email_id: Email ID (for database reference)
            download: If True, download attachment files. If False, only collect metadata and names.

        Returns:
            Tuple of (number of attachments stored, list of attachment file names)
        """
        if not email_id:
            return []

        # Get attachment list
        attachments = self.api_client.get_email_attachments(email_id)
        if not attachments:
            return []

        attachment_names: List[str] = []
        for attachment in attachments:
            attachment_id = attachment.get("id")
            attachment_name = attachment.get("name")
            attachment_names.append(attachment_name)
            file_path = None
            if download:
                file_path_obj = self.get_attachment_file_path(
                    email_id, attachment_id, attachment_name
                )
                # Check if file already exists and download if it doesn't
                if not file_path_obj.exists():
                    content = self.api_client.download_attachment(
                        email_id, attachment_id
                    )
                    if content:
                        file_path = self.save_attachment_file(
                            email_id, attachment_id, attachment_name, content
                        )

            self.store_attachment(email_id, attachment, file_path)

        return attachment_names

    def _ensure_thread_exists(
        self,
        thread_id: str,
        email_timestamp: str,
        current_folder: Optional[str] = None,
        tags: List[str] = [],
    ) -> bool:
        """
        Ensure thread exists in threads table, creating it if needed with CreatedAt from earliest email

        Args:
            thread_id: Thread/conversation ID
            email_timestamp: Timestamp of the current email
            current_folder: Name of the folder where this email currently resides (e.g., 'inbox', 'archive')

        Returns:
            True if successful
        """
        if not thread_id:
            return True  # Skip if no thread_id

        try:
            # Check if thread exists
            check_sql = "SELECT ThreadID, CreatedAt FROM threads WHERE ThreadID = ?"
            existing = self.conn.execute(check_sql, [thread_id]).fetchone()

            if existing:
                # Thread exists, update CreatedAt if this email is earlier
                existing_created_at = existing[1]
                if existing_created_at and email_timestamp:
                    # Convert email_timestamp string to datetime for comparison
                    try:
                        # Parse ISO format timestamp string (e.g., "2024-01-01T00:00:00Z")
                        email_dt = datetime.fromisoformat(
                            email_timestamp.replace("Z", "+00:00")
                        )

                        # Convert existing_created_at to datetime if it's a string
                        if isinstance(existing_created_at, str):
                            existing_dt = datetime.fromisoformat(
                                existing_created_at.replace("Z", "+00:00")
                            )
                        else:
                            existing_dt = existing_created_at

                        # Make both datetimes timezone-aware for comparison
                        # If existing_dt is naive, assume UTC
                        if existing_dt.tzinfo is None:
                            from datetime import timezone

                            existing_dt = existing_dt.replace(tzinfo=timezone.utc)
                        # If email_dt is naive (shouldn't happen, but just in case)
                        if email_dt.tzinfo is None:
                            from datetime import timezone

                            email_dt = email_dt.replace(tzinfo=timezone.utc)

                        # Compare timezone-aware datetimes
                        if email_dt < existing_dt:
                            update_sql = (
                                "UPDATE threads SET CreatedAt = ? WHERE ThreadID = ?"
                            )
                            self.conn.execute(update_sql, [email_timestamp, thread_id])
                    except (ValueError, AttributeError, TypeError) as e:
                        logger.warning(
                            f"Error comparing timestamps for thread {thread_id}: {e}"
                        )
                # Always update current_folder if provided
                if current_folder:
                    try:
                        update_folder_sql = (
                            "UPDATE threads SET current_folder = ? WHERE ThreadID = ?"
                        )
                        self.conn.execute(
                            update_folder_sql, [current_folder, thread_id]
                        )
                    except Exception as e:
                        logger.warning(
                            f"Error updating current_folder for thread {thread_id}: {e}"
                        )
                return True
            else:
                # Create new thread
                insert_sql = """
                INSERT INTO threads (ThreadID, CreatedAt, ProcessedTimestamp, Tags, Additional_tags, current_folder)
                VALUES (?, ?, NULL, ?, '[]', ?)
                """
                self.conn.execute(
                    insert_sql, [thread_id, email_timestamp, tags, current_folder]
                )
                return True
        except Exception as e:
            logger.error(f"Error ensuring thread exists {thread_id}: {e}")
            return False

    def store_email(
        self,
        email: Dict[str, Any],
        current_folder: Optional[str] = None,
    ) -> Tuple[bool, int]:
        """
        Store email in DuckDB

        Args:
            email: Email dictionary from Graph API
            current_folder: Name of the folder where this email currently resides (e.g., 'inbox', 'archive')

        Returns:
            Tuple of (success: bool, attachment_count: int)
        """
        try:
            body = email.get("body", {})
            body_content = clean_message(body.get("content", ""))
            from_info = email.get("from", {}).get("emailAddress", {})
            sender = from_info.get("address", "")
            received_at = email.get("receivedDateTime")
            is_read = email.get("isRead", False)
            raw_json = json.dumps(email)
            tags = email.get("categories", [])

            email_id = email.get("id")
            thread_id = email.get("conversationId")
            self._ensure_thread_exists(
                thread_id, received_at, current_folder=current_folder, tags=tags
            )

            # Check if email exists
            check_sql = "SELECT ID FROM emails WHERE ID = ?"
            existing = self.conn.execute(check_sql, [email_id]).fetchone()
            if existing:
                self.conn.execute(
                    "UPDATE emails SET IsRead = ? WHERE ID = ?", [is_read, email_id]
                )
            else:
                insert_sql = """
                INSERT INTO emails (
                    ID, ThreadID, Timestamp, Sender, Subject, Message, IsRead,
                    has_attachments, attachments, raw_json
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """
                self.conn.execute(
                    insert_sql,
                    [
                        email_id,
                        thread_id,
                        received_at,
                        sender,
                        email.get("subject"),
                        body_content,
                        is_read,
                        email.get("hasAttachments", False),
                        "[]",
                        raw_json,
                    ],
                )
                self.conn.commit()
                attachment_names: List[str] = []
                if email.get("hasAttachments", False):
                    attachment_names = self.download_and_store_attachments(
                        email_id, download=False
                    )
                    self.conn.execute(
                        "UPDATE emails SET attachments = ? WHERE ID = ?",
                        [
                            json.dumps(attachment_names) if attachment_names else "[]",
                            email_id,
                        ],
                    )
            self.conn.commit()
            return True
        except Exception as e:
            logger.error(f"Error storing email {email.get('id', 'unknown')}: {e}")
            return False

    def download_and_store(
        self,
        folder: str = "inbox",
        filter_query: Optional[str] = None,
        batch_size: int = 100,
        limit: Optional[int] = None,
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

        # Read all emails
        emails = self.api_client.read_emails(
            folder=folder, filter_query=filter_query, batch_size=batch_size, limit=limit
        )

        if not emails:
            logger.warning("No emails found")
            return {"downloaded": 0, "stored": 0, "errors": 0}

        # Store emails
        results = {
            "downloaded": len(emails),
            "stored": 0,
            "errors": 0,
        }

        logger.info(f"Storing {len(emails)} emails in DuckDB...")
        for i, email in enumerate(emails, 1):
            if i % 100 == 0:
                logger.info(f"Storing email {i}/{len(emails)}...")

            success = self.store_email(email, current_folder=folder)
            if success:
                results["stored"] += 1
            else:
                results["errors"] += 1

        logger.info(
            f"Download complete: {results['downloaded']} downloaded, "
            f"{results['stored']} stored, {results['errors']} errors"
        )

        return results

    def close(self) -> None:
        """Close database connection."""
        self.db.close()
