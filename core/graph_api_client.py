"""
Microsoft Graph API Email Reader and Tagger

This script uses Microsoft Graph API to:
1. Read emails from Outlook/Office 365
2. Predict labels using the trained ML model
3. Add tags/categories to emails based on predictions
"""

import sys
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
import requests
from msal import ConfidentialClientApplication

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class GraphAPIClient:
    """Microsoft Graph API client"""

    def __init__(
        self,
        client_id: str,
        client_secret: str,
        tenant_id: str,
        user_email: str,
    ):
        """
        Initialize Graph API client

        Args:
            client_id: Azure AD application (client) ID
            client_secret: Azure AD application secret (for app-only auth)
            tenant_id: Azure AD tenant ID or tenant domain (for app-only auth)
            user_email: User email
        """
        self.client_id = client_id
        self.client_secret = client_secret
        self.tenant_id = tenant_id
        self.user_email = user_email
        self.access_token = None
        self.graph_endpoint = "https://graph.microsoft.com/v1.0"

        # Initialize MSAL app
        self.app = ConfidentialClientApplication(
            client_id=client_id,
            client_credential=client_secret,
            authority=f"https://login.microsoftonline.com/{tenant_id}",
        )

    def authenticate(self) -> bool:
        """
        Authenticate and get access token

        Args:
            scopes: List of permission scopes (default: Mail.ReadWrite)

        Returns:
            True if authentication successful, False otherwise
        """
        try:
            result = self.app.acquire_token_for_client(
                scopes=["https://graph.microsoft.com/.default"]
            )

            if "access_token" in result:
                self.access_token = result["access_token"]
                logger.info("Authentication successful")
                return True
            else:
                error = result.get(
                    "error_description", result.get("error", "Unknown error")
                )
                logger.error(f"Authentication failed: {error}")
                return False
        except Exception as e:
            logger.error(f"Authentication error: {e}")
            return False

    def get_headers(self) -> Dict[str, str]:
        """Get HTTP headers with access token"""
        if not self.access_token:
            raise ValueError("Not authenticated. Call authenticate() first.")
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json",
            "Prefer": 'outlook.body-content-type="text"',
        }

    def get_all_mail_folders(self) -> List[Dict[str, Any]]:
        """
        Get all mail folders from the mailbox

        Returns:
            List of folder dictionaries with id, displayName, etc.
        """
        url = f"{self.graph_endpoint}/users/{self.user_email}/mailFolders"
        all_folders = []

        try:
            while True:
                params = {
                    "$select": "id,displayName,parentFolderId,childFolderCount,unreadItemCount,totalItemCount",
                }

                logger.info(f"Fetching mail folders...")
                response = requests.get(url, headers=self.get_headers(), params=params)
                response.raise_for_status()
                data = response.json()
                folders = data.get("value", [])

                if not folders:
                    break

                all_folders.extend(folders)

                # Check if there are more folders using nextLink
                next_link = data.get("@odata.nextLink")
                if not next_link:
                    break

                url = next_link

        except requests.exceptions.HTTPError as e:
            logger.error(f"HTTP error reading mail folders: {e}")
            if e.response is not None:
                logger.error(f"Status code: {e.response.status_code}")
                logger.error(f"Response: {e.response.text}")
        except requests.exceptions.RequestException as e:
            logger.error(f"Error reading mail folders: {e}")

        logger.info(f"Total mail folders retrieved: {len(all_folders)}")
        return all_folders

    def read_emails(
        self,
        folder: str = "inbox",
        batch_size: int = 100,
        limit: Optional[int] = None,
        filter_query: Optional[str] = None,
    ) -> List[Dict[str, Any]]:
        """
        Read emails from specified folder

        Args:
            folder: Mail folder (inbox, sentitems, etc.)
            limit: Maximum number of emails to retrieve
            filter_query: OData filter query (e.g., "receivedDateTime ge 2024-01-01T00:00:00Z")

        Returns:
            List of email dictionaries
        """

        base_url = f"{self.graph_endpoint}/users/{self.user_email}/mailFolders/{folder}/messages"
        all_emails: List[Dict[str, Any]] = []
        url = base_url
        page = 0
        use_next_link = False

        while True:
            params = None
            if not use_next_link:
                params = {
                    "$top": batch_size,
                    # Superset of fields used previously in both readers
                    "$select": "id,subject,from,body,conversationId,receivedDateTime,hasAttachments,importance,categories,isRead",
                    "$orderby": "receivedDateTime desc",
                }

                if filter_query:
                    params["$filter"] = filter_query

            try:
                page += 1
                logger.info(f"Fetching page {page} (batch size: {batch_size})...")
                response = requests.get(url, headers=self.get_headers(), params=params)
                response.raise_for_status()
                data = response.json()
                emails = data.get("value", [])

                if not emails:
                    break

                all_emails.extend(emails)

                # If we only need a limited number of emails, stop once we have enough
                if limit is not None and len(all_emails) >= limit:
                    all_emails = all_emails[:limit]
                    break

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
                    try:
                        error_data = e.response.json()
                        if "error" in error_data:
                            error_info = error_data["error"]
                            logger.error(f"Error code: {error_info.get('code')}")
                            logger.error(f"Error message: {error_info.get('message')}")
                    except Exception:
                        # If we cannot parse structured error information,
                        # fall back to the raw response text that was already logged.
                        pass
                break
            except requests.exceptions.RequestException as e:
                logger.error(f"Error reading emails: {e}")
                break

        logger.info(f"Total emails retrieved from {folder}: {len(all_emails)}")
        return all_emails

    def get_email_attachments(self, message_id: str) -> List[Dict[str, Any]]:
        """
        Get attachments for an email

        Args:
            message_id: Email message ID

        Returns:
            List of attachment dictionaries
        """
        url = f"{self.graph_endpoint}/users/{self.user_email}/messages/{message_id}/attachments"
        try:
            response = requests.get(url, headers=self.get_headers())
            response.raise_for_status()
            data = response.json()
            attachments = data.get("value", [])
            return attachments
        except requests.exceptions.RequestException as e:
            logger.warning(f"Error getting attachments for {message_id}: {e}")
            return []

    def add_category(self, message_id: str, category: str) -> bool:
        """
        Add a category/tag to an email

        Args:
            message_id: Email message ID
            category: Category name to add

        Returns:
            True if successful, False otherwise
        """
        # First, get current categories
        url = f"{self.graph_endpoint}/users/{self.user_email}/messages/{message_id}"
        try:
            response = requests.get(url, headers=self.get_headers())
            response.raise_for_status()
            message = response.json()
            current_categories = message.get("categories", [])

            # Add new category if not already present
            if category not in current_categories:
                current_categories.append(category)

                # Update message with new categories
                patch_data = {"categories": current_categories}
                patch_response = requests.patch(
                    url, headers=self.get_headers(), json=patch_data
                )
                patch_response.raise_for_status()
                logger.info(f"Added category '{category}' to email {message_id}")
                return True
            else:
                logger.info(
                    f"Category '{category}' already exists for email {message_id}"
                )
                return True
        except requests.exceptions.RequestException as e:
            logger.error(f"Error adding category: {e}")
            if hasattr(e, "response") and e.response is not None:
                logger.error(f"Response: {e.response.text}")
            return False

    def download_attachment(self, email_id: str, attachment_id: str) -> Optional[bytes]:
        """
        Download attachment content from Graph API.

        Args:
            email_id: Email ID.
            attachment_id: Attachment ID.

        Returns:
            Attachment content as bytes, or None if error.
        """
        url = (
            f"{self.graph_endpoint}/users/{self.user_email}/messages/"
            f"{email_id}/attachments/{attachment_id}/$value"
        )
        try:
            response = requests.get(url, headers=self.get_headers())
            response.raise_for_status()
            return response.content
        except requests.exceptions.RequestException as e:
            logger.warning(
                f"Error downloading attachment {attachment_id} from {email_id}: {e}"
            )
            return None
