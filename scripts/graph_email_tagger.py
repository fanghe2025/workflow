"""
Microsoft Graph API Email Reader and Tagger

This script uses Microsoft Graph API to:
1. Read emails from Outlook/Office 365
2. Predict labels using the trained ML model
3. Add tags/categories to emails based on predictions
"""

import os
import sys
import json
import logging
from pathlib import Path
from typing import List, Dict, Any, Optional
import requests
from msal import ConfidentialClientApplication, PublicClientApplication

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class GraphEmailTagger:
    """Microsoft Graph API client for reading emails and adding tags"""

    def __init__(
        self,
        client_id: str,
        client_secret: Optional[str] = None,
        tenant_id: Optional[str] = None,
        authority_url: Optional[str] = None,
        user_principal_name: Optional[str] = None,
        ml_api_url: str = "http://localhost:5000",
    ):
        """
        Initialize Graph API client

        Args:
            client_id: Azure AD application (client) ID
            client_secret: Azure AD application secret (for app-only auth)
            tenant_id: Azure AD tenant ID or tenant domain (for app-only auth)
            authority_url: Full Entra ID authority URL (e.g., https://login.microsoftonline.com/{tenant_id})
                          If provided, takes precedence over tenant_id
            user_principal_name: User email/UPN for app-only auth (required when using client_secret)
            ml_api_url: URL of the ML API server for predictions
        """
        self.client_id = client_id
        self.client_secret = client_secret
        self.tenant_id = tenant_id
        self.user_principal_name = user_principal_name
        self.ml_api_url = ml_api_url
        self.access_token = None
        self.graph_endpoint = "https://graph.microsoft.com/v1.0"

        # Determine authority URL for modern Entra ID authentication
        if authority_url:
            # Use provided full authority URL (modern Entra ID format)
            authority = authority_url
        elif tenant_id:
            # Build authority URL from tenant ID (supports both GUID and tenant domain)
            if tenant_id.startswith("https://"):
                # Already a full URL
                authority = tenant_id
            else:
                # Modern Entra ID single-tenant authority format
                authority = f"https://login.microsoftonline.com/{tenant_id}"
        else:
            # Default to common endpoint for multi-tenant
            authority = "https://login.microsoftonline.com/common"

        # Initialize MSAL app
        if client_secret:
            # App-only authentication (service principal) - modern client credential flow
            self.app = ConfidentialClientApplication(
                client_id=client_id,
                client_credential=client_secret,
                authority=authority,
            )
            self.auth_type = "app_only"
        else:
            # Interactive authentication (delegated permissions)
            self.app = PublicClientApplication(
                client_id=client_id,
                authority=authority,
            )
            self.auth_type = "delegated"

    def _get_user_endpoint_base(self) -> str:
        """
        Get the correct endpoint base based on authentication type.
        For app-only auth, use /users/{userPrincipalName}/ instead of /me/
        User principal name is URL-encoded to handle special characters.
        
        Returns:
            Endpoint base string (e.g., "/me" or "/users/user%40domain.com")
        """
        if self.auth_type == "app_only":
            if not self.user_principal_name:
                raise ValueError(
                    "user_principal_name is required for app-only authentication. "
                    "Provide the email address of the user whose mailbox to access."
                )
            return f"/users/{self.user_principal_name}"
        else:
            return "/me"

    def authenticate(self, scopes: List[str] = None) -> bool:
        """
        Authenticate and get access token

        Args:
            scopes: List of permission scopes (default: Mail.ReadWrite)

        Returns:
            True if authentication successful, False otherwise
        """
        if scopes is None:
            scopes = ["Mail.ReadWrite"]

        try:
            if self.auth_type == "app_only":
                # App-only authentication - must use .default scope for client credential flows
                result = self.app.acquire_token_for_client(scopes=["https://graph.microsoft.com/.default"])
            else:
                # Interactive authentication
                accounts = self.app.get_accounts()
                if accounts:
                    # Try to get token silently
                    result = self.app.acquire_token_silent(scopes, account=accounts[0])
                    if not result:
                        # If silent fails, do interactive login
                        result = self.app.acquire_token_interactive(scopes=scopes)
                else:
                    # No cached account, do interactive login
                    result = self.app.acquire_token_interactive(scopes=scopes)

            if "access_token" in result:
                self.access_token = result["access_token"]
                logger.info("Authentication successful")
                return True
            else:
                error = result.get("error_description", result.get("error", "Unknown error"))
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

    def read_emails(
        self,
        folder: str = "inbox",
        limit: int = 10,
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
        endpoint_base = self._get_user_endpoint_base()
        url = f"{self.graph_endpoint}{endpoint_base}/mailFolders/{folder}/messages"
        params = {
            "$top": limit,
            "$select": "id,subject,from,body,conversationId,receivedDateTime,hasAttachments,importance,categories",
            "$orderby": "receivedDateTime desc",
        }

        if filter_query:
            params["$filter"] = filter_query

        try:
            logger.debug(f"Requesting URL: {url}")
            response = requests.get(url, headers=self.get_headers(), params=params)
            response.raise_for_status()
            data = response.json()
            emails = data.get("value", [])

            logger.info(f"Retrieved {len(emails)} emails from {folder}")
            return emails
        except requests.exceptions.HTTPError as e:
            logger.error(f"HTTP error reading emails: {e}")
            logger.error(f"Request URL: {url}")
            if e.response is not None:
                logger.error(f"Status code: {e.response.status_code}")
                logger.error(f"Response: {e.response.text}")
                try:
                    error_data = e.response.json()
                    if "error" in error_data:
                        error_info = error_data["error"]
                        logger.error(f"Error code: {error_info.get('code')}")
                        logger.error(f"Error message: {error_info.get('message')}")
                except:
                    pass
            return []
        except requests.exceptions.RequestException as e:
            logger.error(f"Error reading emails: {e}")
            logger.error(f"Request URL: {url}")
            if hasattr(e, "response") and e.response is not None:
                logger.error(f"Response: {e.response.text}")
            return []

    def get_email_attachments(self, message_id: str) -> List[Dict[str, Any]]:
        """
        Get attachments for an email

        Args:
            message_id: Email message ID

        Returns:
            List of attachment dictionaries
        """
        endpoint_base = self._get_user_endpoint_base()
        url = f"{self.graph_endpoint}{endpoint_base}/messages/{message_id}/attachments"
        try:
            response = requests.get(url, headers=self.get_headers())
            response.raise_for_status()
            data = response.json()
            attachments = data.get("value", [])
            return attachments
        except requests.exceptions.RequestException as e:
            logger.warning(f"Error getting attachments for {message_id}: {e}")
            return []

    def predict_label(self, email: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        """
        Get label prediction from ML model

        Args:
            email: Email dictionary

        Returns:
            Prediction dictionary with label and confidence, or None if error
        """
        # Prepare email data for prediction
        email_data = {
            "subject": email.get("subject", ""),
            "body": email.get("body", {}).get("content", ""),
            "from": email.get("from", {}).get("emailAddress", {}).get("address", ""),
            "hasAttachments": email.get("hasAttachments", False),
            "importance": email.get("importance", "normal"),
        }

        # Get attachments if available
        if email.get("hasAttachments"):
            attachments = self.get_email_attachments(email["id"])
            email_data["attachments"] = [
                {
                    "id": att.get("id"),
                    "name": att.get("name"),
                    "contentType": att.get("contentType"),
                    "size": att.get("size"),
                }
                for att in attachments
            ]

        # Call ML API
        try:
            response = requests.post(
                f"{self.ml_api_url}/api/predict",
                json=email_data,
                headers={"Content-Type": "application/json"},
                timeout=30,
            )
            response.raise_for_status()
            prediction = response.json()
            logger.info(
                f"Prediction for '{email.get('subject', 'No subject')}': {prediction.get('label')} (confidence: {prediction.get('confidence', 0):.2f})"
            )
            return prediction
        except requests.exceptions.RequestException as e:
            logger.error(f"Error getting prediction: {e}")
            if hasattr(e, "response") and e.response is not None:
                logger.error(f"Response: {e.response.text}")
            return None

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
        endpoint_base = self._get_user_endpoint_base()
        url = f"{self.graph_endpoint}{endpoint_base}/messages/{message_id}"
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
                logger.info(f"Category '{category}' already exists for email {message_id}")
                return True
        except requests.exceptions.RequestException as e:
            logger.error(f"Error adding category: {e}")
            if hasattr(e, "response") and e.response is not None:
                logger.error(f"Response: {e.response.text}")
            return False

    def process_emails(
        self,
        folder: str = "inbox",
        limit: int = 10,
        filter_query: Optional[str] = None,
        min_confidence: float = 0.5,
    ) -> Dict[str, Any]:
        """
        Process emails: read, predict labels, and add tags

        Args:
            folder: Mail folder to process
            limit: Maximum number of emails to process
            filter_query: OData filter query
            min_confidence: Minimum confidence threshold for adding tags

        Returns:
            Summary dictionary with processing results
        """
        logger.info(f"Processing emails from {folder} (limit: {limit})")

        # Read emails
        emails = self.read_emails(folder=folder, limit=limit, filter_query=filter_query)
        if not emails:
            logger.warning("No emails found")
            return {"processed": 0, "tagged": 0, "errors": 0}

        # Process each email
        results = {"processed": 0, "tagged": 0, "errors": 0, "skipped": 0}
        for email in emails:
            try:
                results["processed"] += 1
                email_id = email.get("id")
                subject = email.get("subject", "No subject")

                logger.info(f"Processing email: {subject}")

                # Get prediction
                prediction = self.predict_label(email)
                if not prediction:
                    results["errors"] += 1
                    continue

                label = prediction.get("label")
                confidence = prediction.get("confidence", 0)

                # Only add tag if confidence is above threshold
                if confidence >= min_confidence:
                    success = self.add_category(email_id, label)
                    if success:
                        results["tagged"] += 1
                    else:
                        results["errors"] += 1
                else:
                    logger.info(
                        f"Skipping tag for '{subject}' - confidence {confidence:.2f} below threshold {min_confidence}"
                    )
                    results["skipped"] += 1

            except Exception as e:
                logger.error(f"Error processing email {email.get('id', 'unknown')}: {e}")
                results["errors"] += 1

        logger.info(
            f"Processing complete: {results['processed']} processed, {results['tagged']} tagged, {results['skipped']} skipped, {results['errors']} errors"
        )
        return results


def load_config(config_path: str = "config/graph_config.json") -> Dict[str, Any]:
    """Load Graph API configuration from JSON file"""
    config_file = Path(config_path)
    if not config_file.exists():
        logger.warning(f"Config file not found: {config_path}")
        return {}

    try:
        with open(config_file, "r") as f:
            return json.load(f)
    except Exception as e:
        logger.error(f"Error loading config: {e}")
        return {}


def main():
    """Main function"""
    # Load config
    config = load_config("config/graph_config.json")

    # Get credentials from config or environment variables
    client_id = config.get("client_id")
    client_secret = config.get("client_secret")
    tenant_id = config.get("tenant_id")
    authority_url = config.get("authority_url")
    user_principal_name = config.get("user_principal_name")
    ml_api_url = config.get("ml_api_url", "http://localhost:5000")

    if not client_id:
        logger.error(
            "Client ID is required. Provide via config file or GRAPH_CLIENT_ID environment variable."
        )
        logger.info(
            "\nTo set up Microsoft Graph API access:\n"
            "1. Go to https://portal.azure.com\n"
            "2. Navigate to Microsoft Entra ID > App registrations\n"
            "3. Create a new app registration or use existing one\n"
            "4. Note the Application (client) ID\n"
            "5. For app-only auth: Create a client secret and note the Tenant ID\n"
            "6. Add API permissions: Mail.ReadWrite (Application permissions)\n"
            "7. Grant admin consent\n"
            "\nConfig options:\n"
            "  - tenant_id: Tenant ID (GUID) or tenant domain\n"
            "  - authority_url: Full Entra ID authority URL (e.g., https://login.microsoftonline.com/{tenant_id})\n"
            "    If authority_url is provided, it takes precedence over tenant_id\n"
            "  - user_principal_name: User email/UPN (REQUIRED for app-only auth)\n"
        )
        return 1

    # Initialize tagger
    tagger = GraphEmailTagger(
        client_id=client_id,
        client_secret=client_secret,
        tenant_id=tenant_id,
        authority_url=authority_url,
        user_principal_name=user_principal_name,
        ml_api_url=ml_api_url,
    )

    # Authenticate
    if not tagger.authenticate():
        logger.error("Authentication failed")
        return 1

    # Process emails
    results = tagger.process_emails(
        folder=config.get("folder", "inbox"),
        limit=config.get("limit", 10),
        filter_query=config.get("filter"),
        min_confidence=config.get("min_confidence", 0.5),
    )

    # Print summary
    print("\n" + "=" * 50)
    print("Processing Summary")
    print("=" * 50)
    print(f"Processed: {results['processed']}")
    print(f"Tagged: {results['tagged']}")
    print(f"Skipped (low confidence): {results['skipped']}")
    print(f"Errors: {results['errors']}")
    print("=" * 50)

    return 0 if results["errors"] == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
