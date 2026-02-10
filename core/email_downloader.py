import logging
import json
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from core.db import DatabaseConnection
from core.graph_api_client import GraphAPIClient
from utils.common import clean_email_body


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
            check_email = "SELECT ID FROM emails WHERE ID = ?"
            email_exists = self.conn.execute(check_email, [email_id]).fetchone()
            if not email_exists:
                logger.error(
                    f"Email {email_id} does not exist in database. Cannot insert attachment."
                )
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
            return True
        except Exception as e:
            logger.error(
                f"Error storing attachment {attachment.get('id', 'unknown')}: {e}"
            )
            return False

    def download_and_store_attachments(
        self, email_id: str, message_id: str, download: bool = False
    ) -> Tuple[int, List[str]]:
        """
        Download and store all attachments for an email

        Args:
            email_id: Email ID (for database reference)
            message_id: Message ID (for Graph API)
            download: If True, download attachment files. If False, only collect metadata and names.

        Returns:
            Tuple of (number of attachments stored, list of attachment file names)
        """
        if not email_id or not message_id:
            return 0, []

        # Get attachment list
        attachments = self.api_client.get_email_attachments(message_id)
        if not attachments:
            return 0, []

        if download:
            logger.info(
                f"Downloading {len(attachments)} attachments for email {email_id}"
            )
        else:
            logger.info(
                f"Collecting metadata for {len(attachments)} attachments for email {email_id}"
            )

        stored_count = 0
        attachment_names: List[str] = []
        for attachment in attachments:
            attachment_id = attachment.get("id")
            attachment_name = attachment.get("name")

            if not download:
                # Only collect metadata, don't download files
                if attachment_name:
                    attachment_names.append(attachment_name)
                # Store metadata in database without file path
                if self.store_attachment(email_id, attachment, None):
                    stored_count += 1
                    logger.debug(f"Stored attachment metadata: {attachment_name}")
                    self.conn.commit()
                continue

            # Get expected file path
            file_path_obj = self.get_attachment_file_path(
                email_id, attachment_id, attachment_name
            )
            file_path = str(file_path_obj)

            # Check if file already exists
            if file_path_obj.exists():
                logger.debug(
                    f"Attachment file already exists, skipping download: {attachment_name}"
                )
                # File exists, use it directly
            else:
                # Download attachment content from Graph API
                content = self.download_attachment(message_id, attachment_id)
                if not content:
                    logger.warning(f"Failed to download attachment {attachment_name}")
                    # Still store metadata even if download failed
                    self.store_attachment(email_id, attachment, None)
                    # Still add name to list even if download failed
                    if attachment_name:
                        attachment_names.append(attachment_name)
                    continue

                # Save file to disk
                saved_path = self.save_attachment_file(
                    email_id, attachment_id, attachment_name, content
                )
                if not saved_path:
                    logger.warning(f"Failed to save attachment {attachment_name}")
                    # Still store metadata even if save failed
                    self.store_attachment(email_id, attachment, None)
                    # Still add name to list even if save failed
                    if attachment_name:
                        attachment_names.append(attachment_name)
                    continue
                file_path = saved_path

            # Store in database
            if self.store_attachment(email_id, attachment, file_path):
                stored_count += 1
                if attachment_name:
                    attachment_names.append(attachment_name)
                logger.debug(f"Stored attachment: {attachment_name}")
                # Commit after each attachment to ensure data is persisted
                self.conn.commit()

        return stored_count, attachment_names

    def _ensure_thread_exists(
        self,
        thread_id: str,
        email_timestamp: str,
        current_folder: Optional[str] = None,
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
                INSERT INTO threads (ThreadID, CreatedAt, ProcessedTimestamp, current_folder, Tags, Additional_tags)
                VALUES (?, ?, NULL, ?, '[]', '[]')
                """
                self.conn.execute(
                    insert_sql, [thread_id, email_timestamp, current_folder]
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
            # Extract body content
            body = email.get("body", {})
            body_content = body.get("content", "")

            if body_content:
                body_content = clean_email_body(body_content)

            # Extract from address
            from_info = email.get("from", {}).get("emailAddress", {})
            sender = from_info.get("address", "")

            # Parse dates
            received_at = email.get("receivedDateTime")

            # Get isRead status (default to False if not provided)
            is_read = email.get("isRead", False)

            # Store raw JSON
            raw_json = json.dumps(email)

            email_id = email.get("id")
            thread_id = email.get("conversationId")

            # Ensure thread exists and update its current_folder
            if thread_id:
                self._ensure_thread_exists(
                    thread_id, received_at, current_folder=current_folder
                )

            # Check if email exists
            check_sql = "SELECT ID FROM emails WHERE ID = ?"
            existing = self.conn.execute(check_sql, [email_id]).fetchone()

            # Download and store attachments if present, and collect attachment names
            attachment_count = 0
            attachment_names: List[str] = []
            if email.get("hasAttachments", False):
                message_id = email.get("id")
                # If email doesn't exist yet, insert it first (without attachments) for foreign key constraint
                if not existing:
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
                            "[]",  # Empty attachments initially
                            raw_json,
                        ],
                    )
                    # Commit email first to ensure it's available for foreign key constraint
                    self.conn.commit()

                # Now download attachments (email exists, so foreign key constraint is satisfied)
                attachment_count, attachment_names = (
                    self.download_and_store_attachments(email_id, message_id)
                )

            # Store attachments as JSON array
            attachments_json = (
                json.dumps(attachment_names) if attachment_names else "[]"
            )

            if existing:
                # Update existing email with IsRead and attachment names
                update_sql = """
                UPDATE emails SET
                    IsRead = ?,
                    attachments = ?
                WHERE ID = ?
                """
                self.conn.execute(
                    update_sql,
                    [
                        is_read,
                        attachments_json,
                        email_id,
                    ],
                )
            else:
                # Update the email we just inserted with attachment names (if any)
                if attachment_names:
                    update_sql = """
                    UPDATE emails SET
                        attachments = ?
                    WHERE ID = ?
                    """
                    self.conn.execute(
                        update_sql,
                        [
                            attachments_json,
                            email_id,
                        ],
                    )

            # Commit email updates
            self.conn.commit()

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

            success, attachment_count = self.store_email(email, current_folder=folder)
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

    def close(self) -> None:
        """Close database connection."""
        self.db.close()
