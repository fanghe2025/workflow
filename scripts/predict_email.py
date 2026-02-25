"""
Microsoft Graph API Email Reader and Tagger

This script uses Microsoft Graph API to:
1. Read emails from Outlook/Office 365
2. Predict labels using the trained ML model
3. Add tags/categories to emails based on predictions
"""

import argparse
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.constants import NO_LABEL
from core.email_labeling_model import EmailLabelingModel
from core.llm_tag_model import LLMTagModel
from utils.graph import get_authenticated_api_client
from utils.common import clean_message
from utils.db import get_all_tags
from typing import List, Dict

load_dotenv()
api_key = os.getenv("OPENAI_API_KEY")
fine_tune_job_id = os.getenv("FINE_TUNE_JOB_ID")
fine_tune_model_id = os.getenv("FINE_TUNE_MODEL_ID")


def clean_no_label(labels: List[str], all_probs: Dict[str, float]) -> List[str]:
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


def read_emails():
    api_client = get_authenticated_api_client()
    if not api_client:
        print("Failed to authenticate API client")
        return 1

    # categories = api_client.get_category_list()
    # print(categories)
    emails = api_client.read_emails()
    cleaned_emails = []
    for email in emails:
        bcc_recipients = [
            recipient.get("emailAddress", {}).get("address", "")
            for recipient in email.get("bccRecipients", [])
        ]
        cc_recipients = [
            recipient.get("emailAddress", {}).get("address", "")
            for recipient in email.get("ccRecipients", [])
        ]
        data = {
            "Subject": email.get("subject"),
            "Message": clean_message(email.get("body", {}).get("content", "")),
            "Sender": email.get("from", {}).get("emailAddress", {}).get("address", ""),
            "OtherRecipients": bcc_recipients + cc_recipients,
            "attachments": [],
            "Tags": email.get("categories", []),
        }
        if email.get("hasAttachments", False):
            attachments = api_client.get_email_attachments(email["id"])
            for attachment in attachments:
                data["attachments"].append(attachment.get("name"))
        cleaned_emails.append(data)

    return cleaned_emails


def predict_with_random_forest(emails):
    # Initialize and predict model
    model = EmailLabelingModel(model_path="models/email_classifier.pkl")
    model.load()

    try:
        print(f"{'Original Tags':<50} | {'Predicted Tags'}")
        print("-" * 100)
        for email in emails:
            prediction = model.predict(email)
            predicted_labels = []
            cleaned = clean_no_label(
                prediction["labels"], prediction["all_probabilities"]
            )
            for label in cleaned:
                prob = prediction["all_probabilities"][label]
                if label == NO_LABEL:
                    label = ""
                # predicted_labels.append(f"{label}({prob:.4f})")
                predicted_labels.append(label)
            print(f"{str(email['Tags']):<50} | {str(predicted_labels):<50}")
            print("-" * 100)
        print("\nTraining completed successfully!")
    except Exception as e:
        print(f"Error during training: {e}")


def predict_with_fine_tune(emails):
    llm = LLMTagModel(api_key, model=fine_tune_model_id)
    llm._all_tags = get_all_tags()
    print(f"{'Original Tags':<50} | {'Predicted Tags'}")
    print("-" * 100)
    for email in emails:
        predicted_tags = llm.predict(email)
        print(f"{str(email['Tags']):<50} | {str(predicted_tags):<50}")


def main(args):
    """Main predict function"""
    emails = read_emails()
    if args.random_forest:
        predict_with_random_forest(emails)
    elif args.fine_tune:
        predict_with_fine_tune(emails)


if __name__ == "__main__":
    arg_parser = argparse.ArgumentParser(description="Reddit scraper")
    arg_parser.add_argument("--random-forest", action="store_true")
    arg_parser.add_argument("--fine-tune", action="store_true")
    args = arg_parser.parse_args()

    sys.exit(main(args))
