"""
Microsoft Graph API Email Reader and Tagger

This script uses Microsoft Graph API to:
1. Read emails from Outlook/Office 365
2. Predict labels using the trained ML model
3. Add tags/categories to emails based on predictions
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.email_labeling_model import EmailLabelingModel
from utils.graph import get_authenticated_api_client
from utils.common import clean_email_body


def main():
    """Main predict function"""

    api_client = get_authenticated_api_client()
    if not api_client:
        print("Failed to authenticate API client")
        return 1

    emails = api_client.read_emails()

    # Initialize and predict model
    model = EmailLabelingModel(model_path="models/email_classifier.pkl")
    model.load()

    try:
        for email in emails:
            body = email.get("body", {})
            from_info = email.get("from", {}).get("emailAddress", {})
            tags = email.get("categories", [])
            data = {
                "Subject": email.get("subject"),
                "Message": clean_email_body(body.get("content", "")),
                "Sender": from_info.get("address", ""),
                "hasAttachments": email.get("hasAttachments", False),
                "attachments": [],
            }
            if email.get("hasAttachments", False):
                attachments = api_client.get_email_attachments(email["id"])
                for attachment in attachments:
                    data["attachments"].append(attachment.get("name"))
            prediction = model.predict(data)
            print(prediction)
        print("\nTraining completed successfully!")
    except Exception as e:
        print(f"Error during training: {e}")


if __name__ == "__main__":
    sys.exit(main())
