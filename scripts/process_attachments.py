"""
Standalone script to process attachments from collected emails.

This script can be run separately to extract text from attachments
that were collected from your email account.
"""

import json
import os
import sys
from pathlib import Path
from typing import List, Dict, Any

sys.path.insert(0, str(Path(__file__).parent.parent))

from core.attachment_processor import AttachmentProcessor


def process_emails_with_attachments(
    emails_path: str, output_path: str = None, attachments_dir: str = "data/attachments"
):
    """
    Process all emails and extract text from their attachments.

    Args:
        emails_path: Path to JSON file with email data
        output_path: Optional path to save processed emails
        attachments_dir: Directory where attachments are stored
    """
    processor = AttachmentProcessor()

    # Load emails
    if not os.path.exists(emails_path):
        print(f"Error: {emails_path} not found")
        return

    with open(emails_path, "r", encoding="utf-8") as f:
        emails = json.load(f)

    if not isinstance(emails, list):
        # Single email object
        emails = [emails]

    print(f"Processing {len(emails)} emails...")

    processed_count = 0
    for email in emails:
        if not email.get("hasAttachments", False):
            continue

        attachments = email.get("attachments", [])
        if not attachments:
            continue

        attachment_texts = []
        for attachment in attachments:
            file_path = attachment.get("file_path")
            if not file_path:
                # Try to construct path
                email_id = email.get("id", "unknown")
                attachment_name = attachment.get("name") or attachment.get(
                    "attachmentName"
                )
                if attachment_name:
                    file_path = os.path.join(attachments_dir, email_id, attachment_name)

            if file_path and os.path.exists(file_path):
                result = processor.process_attachment(
                    file_path=file_path, content_type=attachment.get("contentType")
                )

                if result.get("text_content"):
                    attachment_texts.append(result["text_content"])
                    attachment["text_content"] = result["text_content"]
                    attachment["processed"] = True
                else:
                    attachment["processed"] = False
                    if result.get("error"):
                        attachment["processing_error"] = result["error"]
            else:
                attachment["processed"] = False
                attachment["processing_error"] = f"File not found: {file_path}"

        if attachment_texts:
            email["attachment_texts"] = attachment_texts
            processed_count += 1

    print(f"Processed attachments for {processed_count} emails")

    # Save processed emails
    if output_path:
        os.makedirs(os.path.dirname(output_path), exist_ok=True)
        with open(output_path, "w", encoding="utf-8") as f:
            json.dump(emails, f, indent=2, ensure_ascii=False)
        print(f"Saved processed emails to {output_path}")
    else:
        # Overwrite original file
        with open(emails_path, "w", encoding="utf-8") as f:
            json.dump(emails, f, indent=2, ensure_ascii=False)
        print(f"Updated {emails_path}")


def process_directory(directory: str):
    """Process all email JSON files in a directory"""
    directory = Path(directory)
    if not directory.exists():
        print(f"Error: Directory {directory} not found")
        return

    json_files = list(directory.glob("*.json"))
    print(f"Found {len(json_files)} email files to process")

    for json_file in json_files:
        print(f"\nProcessing {json_file.name}...")
        process_emails_with_attachments(str(json_file))


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Process email attachments")
    parser.add_argument(
        "--emails", type=str, help="Path to email JSON file or directory"
    )
    parser.add_argument(
        "--output",
        type=str,
        help="Output path (optional, defaults to overwriting input)",
    )
    parser.add_argument(
        "--attachments-dir",
        type=str,
        default="data/attachments",
        help="Directory where attachments are stored",
    )

    args = parser.parse_args()

    if args.emails:
        emails_path = Path(args.emails)
        if emails_path.is_dir():
            process_directory(str(emails_path))
        else:
            process_emails_with_attachments(
                str(emails_path), args.output, args.attachments_dir
            )
    else:
        # Default: process all emails in data/processed_emails
        default_dir = "data/processed_emails"
        if os.path.exists(default_dir):
            process_directory(default_dir)
        else:
            print(f"Error: {default_dir} not found")
            print("Usage: python scripts/process_attachments.py --emails <path>")
