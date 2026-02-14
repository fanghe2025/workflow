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

from core.constants import NO_LABEL
from core.email_labeling_model import EmailLabelingModel
from utils.graph import get_authenticated_api_client
from utils.common import clean_email_body
from typing import List, Dict



def clean_no_label(
    labels: List[str], all_probs: Dict[str, float]
) -> List[str]:
    """Remove 'No Label' from predicted labels if better alternatives exist"""
    if not labels:
        return labels

    if NO_LABEL not in labels or len(labels) == 1:
        return labels

    if labels[0] == NO_LABEL:
        no_label_prob = all_probs[NO_LABEL]
        second_prob = all_probs[labels[1]]
        if no_label_prob - second_prob < 0.1:
            return [labels[1]]
        if no_label_prob - second_prob > 0.3:
            return [labels[0]]
    cleaned = []
    for label in labels:
        if label == NO_LABEL:
            break
        cleaned.append(label)
    return cleaned


def main():
    """Main predict function"""

    api_client = get_authenticated_api_client()
    if not api_client:
        print("Failed to authenticate API client")
        return 1

    # categories = api_client.get_category_list()
    # print(categories)
    emails = api_client.read_emails()

    # Initialize and predict model
    model = EmailLabelingModel(model_path="models/email_classifier.pkl")
    model.load()

    try:
        print(f"{'Original Tags':<50} | {'Predicted Tags'}")
        print("-" * 100)
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
            predicted_labels = []
            cleaned = clean_no_label(prediction["labels"], prediction["all_probabilities"])
            for label in cleaned:
                prob = prediction["all_probabilities"][label]
                if label == NO_LABEL:
                    label = ""
                # predicted_labels.append(f"{label}({prob:.4f})")
                predicted_labels.append(label)
            print(f"{str(tags):<50} | {str(predicted_labels):<50}")
            print("-" * 100)
        print("\nTraining completed successfully!")
    except Exception as e:
        print(f"Error during training: {e}")


if __name__ == "__main__":
    sys.exit(main())
