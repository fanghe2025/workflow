"""
Helper script to label emails for training.

This script helps you manually label emails collected from your email account.
"""

import json
import os
import sys
from pathlib import Path
from typing import List, Dict, Any


def load_emails(emails_path: str) -> List[Dict[str, Any]]:
    """Load emails from JSON file or directory"""
    emails_path = Path(emails_path)

    if emails_path.is_file():
        with open(emails_path, "r", encoding="utf-8") as f:
            data = json.load(f)
            if isinstance(data, list):
                return data
            else:
                return [data]

    elif emails_path.is_dir():
        emails = []
        for json_file in emails_path.glob("*.json"):
            with open(json_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                if isinstance(data, list):
                    emails.extend(data)
                else:
                    emails.append(data)
        return emails

    return []


def save_labeled_emails(emails: List[Dict[str, Any]], output_path: str):
    """Save labeled emails to JSON file"""
    os.makedirs(os.path.dirname(output_path), exist_ok=True)

    # Filter only emails with labels
    labeled = [e for e in emails if e.get("label")]

    with open(output_path, "w", encoding="utf-8") as f:
        json.dump(labeled, f, indent=2, ensure_ascii=False)

    print(f"Saved {len(labeled)} labeled emails to {output_path}")


def interactive_label(emails: List[Dict[str, Any]], existing_labels: List[str] = None):
    """Interactively label emails"""
    if existing_labels is None:
        existing_labels = []

    print(f"\nFound {len(emails)} emails to label")
    print("Commands:")
    print("  - Enter label name to assign label")
    print("  - 'skip' to skip email")
    print("  - 'quit' to save and exit")
    print("  - 'list' to see existing labels")
    print()

    labeled_count = 0
    skipped_count = 0

    for i, email in enumerate(emails):
        if email.get("label"):
            print(f"[{i+1}/{len(emails)}] Already labeled: {email.get('label')}")
            labeled_count += 1
            continue

        print(f"\n[{i+1}/{len(emails)}] Email:")
        print(f"  Subject: {email.get('subject', 'N/A')[:80]}")
        print(f"  From: {email.get('from', 'N/A')}")
        print(f"  Body preview: {email.get('body', '')[:200]}...")
        if email.get("hasAttachments"):
            print(f"  Attachments: {len(email.get('attachments', []))}")

        while True:
            label = input("\nEnter label (or 'skip'/'quit'/'list'): ").strip()

            if label.lower() == "quit":
                return emails, labeled_count, skipped_count

            if label.lower() == "skip":
                skipped_count += 1
                break

            if label.lower() == "list":
                if existing_labels:
                    print(f"Existing labels: {', '.join(existing_labels)}")
                else:
                    print("No existing labels yet")
                continue

            if label:
                email["label"] = label
                if label not in existing_labels:
                    existing_labels.append(label)
                labeled_count += 1
                break

    return emails, labeled_count, skipped_count


def main():
    """Main labeling function"""
    import argparse

    parser = argparse.ArgumentParser(description="Label emails for ML training")
    parser.add_argument(
        "--emails",
        type=str,
        default="data/processed_emails",
        help="Path to email JSON file or directory",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="data/labeled_emails.json",
        help="Output path for labeled emails",
    )
    parser.add_argument(
        "--labels", type=str, nargs="+", help="Pre-defined labels to use"
    )

    args = parser.parse_args()

    # Load emails
    print(f"Loading emails from {args.emails}...")
    emails = load_emails(args.emails)

    if not emails:
        print("No emails found!")
        return

    # Get existing labels from output file if it exists
    existing_labels = []
    if os.path.exists(args.output):
        with open(args.output, "r", encoding="utf-8") as f:
            existing = json.load(f)
            existing_labels = list(
                set(e.get("label") for e in existing if e.get("label"))
            )

    if args.labels:
        existing_labels.extend(args.labels)
        existing_labels = list(set(existing_labels))

    # Interactive labeling
    emails, labeled, skipped = interactive_label(emails, existing_labels)

    # Save labeled emails
    save_labeled_emails(emails, args.output)

    print(f"\nLabeling complete!")
    print(f"  Labeled: {labeled}")
    print(f"  Skipped: {skipped}")
    print(f"  Total: {len(emails)}")


if __name__ == "__main__":
    main()
