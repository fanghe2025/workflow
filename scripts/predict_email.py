"""
Microsoft Graph API Email Reader and Tagger

This script uses Microsoft Graph API to:
1. Read emails from Outlook/Office 365
2. Predict labels using the trained ML model
3. Add tags/categories to emails based on predictions
"""

import argparse
import json
import sys
from pathlib import Path
from typing import List, Dict

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.constants import NO_LABEL
from core.email_labeling_model import EmailLabelingModel
from core.llm_tag_model import LLMTagModel
from config import env
from utils.graph import get_authenticated_api_client
from utils.common import clean_message
from utils.db import get_all_tags, load_emails_recent_per_tag


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


def predict_with_random_forest(emails, show_percent: bool = False):
    model = EmailLabelingModel(model_path="models/email_classifier.pkl")
    model.load()
    results_for_percent = []

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
                if label == NO_LABEL:
                    label = ""
                predicted_labels.append(label)
            if show_percent:
                results_for_percent.append(
                    {"correct": email.get("Tags") or [], "predicted": predicted_labels}
                )
            print(f"{str(email['Tags']):<50} | {str(predicted_labels):<50}")
            print("-" * 100)
        if show_percent and results_for_percent:
            _compute_percent_per_tag(emails, results_for_percent)
        print("\nPrediction completed successfully!")
    except Exception as e:
        print(f"Error during prediction: {e}")


def _tags_match(correct: List, predicted: List) -> bool:
    """Compare tag lists (order-independent)."""
    return sorted(correct or []) == sorted(predicted or [])


def _compute_percent_per_tag(emails: List[Dict], results: List[Dict]) -> None:
    """results: list of {"correct": [...], "predicted": [...]}."""
    tag_total: Dict[str, int] = {}
    tag_correct: Dict[str, int] = {}
    exact_match_total = 0
    exact_match_correct = 0
    for email, res in zip(emails, results):
        correct = set(res["correct"])
        predicted = set(res["predicted"])
        if _tags_match(list(correct), list(predicted)):
            exact_match_correct += 1
        exact_match_total += 1
        for t in correct:
            tag_total[t] = tag_total.get(t, 0) + 1
            if t in predicted:
                tag_correct[t] = tag_correct.get(t, 0) + 1
    print("\n--- Percent per tag (recall: correct had tag and predicted had tag) ---")
    for tag in sorted(tag_total.keys()):
        total = tag_total[tag]
        correct = tag_correct.get(tag, 0)
        pct = (100.0 * correct / total) if total else 0
        print(f"  {tag}: {correct}/{total} = {pct:.1f}%")
    if exact_match_total:
        exact_pct = 100.0 * exact_match_correct / exact_match_total
        print(
            f"\nExact match (all tags correct): {exact_match_correct}/{exact_match_total} = {exact_pct:.1f}%"
        )


def predict_with_fine_tune(emails, show_percent: bool = False):
    llm = LLMTagModel(env.OPENAI_API_KEY, model=env.FINE_TUNE_MODEL_ID)
    llm._all_tags = get_all_tags()
    incorrect_emails = []
    results_for_percent = []

    print(f"{'Original Tags':<50} | {'Predicted Tags'}")
    print("-" * 100)
    for email in emails:
        predicted_tags = llm.predict(email)
        correct_tags = email.get("Tags") or []
        if show_percent:
            results_for_percent.append(
                {"correct": correct_tags, "predicted": predicted_tags}
            )
        print(f"{str(correct_tags):<50} | {str(predicted_tags):<50}")
        if not _tags_match(correct_tags, predicted_tags):
            incorrect_emails.append(email)

    if show_percent and results_for_percent:
        _compute_percent_per_tag(emails, results_for_percent)

    if incorrect_emails:
        json_path = Path("data/incorrect_emails.json")
        with open(json_path, "w", encoding="utf-8") as f:
            json.dump(incorrect_emails, f, ensure_ascii=False, indent=2)
        print(f"Exported {len(incorrect_emails)} incorrect sample(s) to {json_path}")
    elif not show_percent:
        print(f"Incorrect predictions: {len(incorrect_emails)} / {len(emails)}")
    return incorrect_emails


def main(args):
    """Main predict function"""
    if args.from_db:
        emails = load_emails_recent_per_tag()
    else:
        emails = read_emails()
    if not emails:
        print("No emails to predict.")
        return 1
    if args.random_forest:
        predict_with_random_forest(emails, show_percent=args.percent)
    elif args.fine_tune:
        predict_with_fine_tune(emails, show_percent=args.percent)
    else:
        print("Specify --random-forest or --fine-tune")
        return 1
    return 0


if __name__ == "__main__":
    arg_parser = argparse.ArgumentParser(
        description="Email prediction (Graph API or DuckDB)"
    )
    arg_parser.add_argument(
        "--random-forest", action="store_true", help="Use random forest model"
    )
    arg_parser.add_argument(
        "--fine-tune", action="store_true", help="Use fine-tuned LLM model"
    )
    arg_parser.add_argument(
        "--from-db",
        action="store_true",
        help="Read emails from DuckDB (recent N per tag) instead of Graph API",
    )
    arg_parser.add_argument(
        "--percent",
        action="store_true",
        help="Print accuracy percent per tag and exact-match percent",
    )
    args = arg_parser.parse_args()

    sys.exit(main(args))
