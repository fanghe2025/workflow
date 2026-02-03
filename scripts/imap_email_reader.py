"""
IMAP Email Reader - Alternative to Azure Outlook API

This script reads emails using IMAP protocol, which works with most email providers
(Gmail, Outlook.com, Yahoo, etc.) without requiring Azure credentials.

Usage:
    python scripts/imap_email_reader.py --config config/imap_config.json
"""

import imaplib
import email
import json
import os
import sys
import argparse
from pathlib import Path
from email.header import decode_header
from email.utils import parsedate_to_datetime
from typing import List, Dict, Any, Optional
from datetime import datetime


def decode_mime_words(s):
    """Decode MIME encoded words in email headers"""
    if not s:
        return ""
    decoded_parts = decode_header(s)
    decoded_str = ""
    for part, encoding in decoded_parts:
        if isinstance(part, bytes):
            decoded_str += part.decode(encoding or "utf-8", errors="ignore")
        else:
            decoded_str += part
    return decoded_str


def extract_email_body(msg) -> str:
    """Extract text body from email message"""
    body = ""
    
    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            content_disposition = str(part.get("Content-Disposition", ""))
            
            # Skip attachments
            if "attachment" in content_disposition:
                continue
            
            # Prefer text/plain, fallback to text/html
            if content_type == "text/plain":
                try:
                    payload = part.get_payload(decode=True)
                    if payload:
                        charset = part.get_content_charset() or "utf-8"
                        body = payload.decode(charset, errors="ignore")
                        break
                except Exception as e:
                    print(f"Error decoding text/plain: {e}")
            
            elif content_type == "text/html" and not body:
                try:
                    payload = part.get_payload(decode=True)
                    if payload:
                        charset = part.get_content_charset() or "utf-8"
                        html_body = payload.decode(charset, errors="ignore")
                        # Simple HTML stripping (you might want to use BeautifulSoup)
                        from bs4 import BeautifulSoup
                        soup = BeautifulSoup(html_body, "html.parser")
                        body = soup.get_text(separator=" ", strip=True)
                except Exception as e:
                    print(f"Error decoding text/html: {e}")
    else:
        # Not multipart
        try:
            payload = msg.get_payload(decode=True)
            if payload:
                charset = msg.get_content_charset() or "utf-8"
                body = payload.decode(charset, errors="ignore")
        except Exception as e:
            print(f"Error decoding body: {e}")
    
    return body


def parse_email(msg, email_id: str) -> Dict[str, Any]:
    """Parse email message into structured format"""
    # Extract headers
    subject = decode_mime_words(msg.get("Subject", ""))
    from_addr = decode_mime_words(msg.get("From", ""))
    to_addrs = decode_mime_words(msg.get("To", ""))
    date_str = msg.get("Date", "")
    
    # Parse date
    received_datetime = None
    if date_str:
        try:
            received_datetime = parsedate_to_datetime(date_str).isoformat()
        except Exception:
            received_datetime = datetime.now().isoformat()
    
    # Extract email addresses
    from_email = ""
    if from_addr:
        # Try to extract email from "Name <email@domain.com>" format
        if "<" in from_addr and ">" in from_addr:
            from_email = from_addr.split("<")[1].split(">")[0].strip()
        else:
            from_email = from_addr.strip()
    
    to_emails = []
    if to_addrs:
        # Split multiple recipients
        for addr in to_addrs.split(","):
            addr = addr.strip()
            if "<" in addr and ">" in addr:
                to_emails.append(addr.split("<")[1].split(">")[0].strip())
            else:
                to_emails.append(addr.strip())
    
    # Extract body
    body = extract_email_body(msg)
    
    # Check for attachments
    has_attachments = False
    attachments = []
    
    if msg.is_multipart():
        for part in msg.walk():
            content_disposition = str(part.get("Content-Disposition", ""))
            if "attachment" in content_disposition:
                has_attachments = True
                filename = part.get_filename()
                if filename:
                    filename = decode_mime_words(filename)
                    attachments.append({
                        "name": filename,
                        "contentType": part.get_content_type(),
                        "size": len(part.get_payload(decode=True) or b""),
                    })
    
    return {
        "id": email_id,
        "subject": subject,
        "from": from_email,
        "to": to_emails,
        "body": body,
        "receivedDateTime": received_datetime or datetime.now().isoformat(),
        "hasAttachments": has_attachments,
        "attachments": attachments,
        "importance": "normal",  # IMAP doesn't always provide this
    }


def download_attachments(msg, email_id: str, output_dir: str) -> List[Dict[str, Any]]:
    """Download attachments from email message"""
    attachments = []
    output_path = Path(output_dir) / email_id
    output_path.mkdir(parents=True, exist_ok=True)
    
    if msg.is_multipart():
        for part in msg.walk():
            content_disposition = str(part.get("Content-Disposition", ""))
            if "attachment" in content_disposition:
                filename = part.get_filename()
                if filename:
                    filename = decode_mime_words(filename)
                    file_path = output_path / filename
                    
                    try:
                        payload = part.get_payload(decode=True)
                        if payload:
                            with open(file_path, "wb") as f:
                                f.write(payload)
                            
                            attachments.append({
                                "id": f"{email_id}_{filename}",
                                "name": filename,
                                "contentType": part.get_content_type(),
                                "size": len(payload),
                                "file_path": str(file_path),
                            })
                    except Exception as e:
                        print(f"Error saving attachment {filename}: {e}")
    
    return attachments


def connect_imap(config: Dict[str, Any]) -> imaplib.IMAP4_SSL:
    """Connect to IMAP server"""
    server = config.get("imap_server")
    port = config.get("imap_port", 993)
    username = config.get("username")
    password = config.get("password")
    
    if not all([server, username, password]):
        raise ValueError("Missing required IMAP configuration: server, username, password")
    
    print(f"Connecting to {server}:{port}...")
    mail = imaplib.IMAP4_SSL(server, port)
    mail.login(username, password)
    print("Connected successfully!")
    
    return mail


def fetch_emails(
    mail: imaplib.IMAP4_SSL,
    folder: str = "INBOX",
    limit: Optional[int] = None,
    since_date: Optional[str] = None,
    download_attachments: bool = False,
    attachments_dir: str = "data/attachments",
) -> List[Dict[str, Any]]:
    """Fetch emails from IMAP server"""
    mail.select(folder)
    
    # Build search criteria
    search_criteria = "ALL"
    if since_date:
        # Format: (SINCE 01-Jan-2024)
        search_criteria = f'(SINCE {since_date})'
    
    # Search for emails
    status, messages = mail.search(None, search_criteria)
    if status != "OK":
        print(f"Error searching emails: {status}")
        return []
    
    email_ids = messages[0].split()
    
    # Reverse to get newest first, apply limit
    if limit:
        email_ids = email_ids[-limit:]
    email_ids.reverse()
    
    emails = []
    print(f"Found {len(email_ids)} emails. Fetching...")
    
    for i, email_id in enumerate(email_ids):
        try:
            # Fetch email
            status, msg_data = mail.fetch(email_id, "(RFC822)")
            if status != "OK":
                continue
            
            # Parse email
            msg = email.message_from_bytes(msg_data[0][1])
            email_data = parse_email(msg, email_id.decode())
            
            # Download attachments if requested
            if download_attachments and email_data["hasAttachments"]:
                attachments = download_attachments(msg, email_data["id"], attachments_dir)
                email_data["attachments"] = attachments
            
            emails.append(email_data)
            
            if (i + 1) % 10 == 0:
                print(f"Processed {i + 1}/{len(email_ids)} emails...")
        
        except Exception as e:
            print(f"Error processing email {email_id}: {e}")
            continue
    
    return emails


def save_emails(emails: List[Dict[str, Any]], output_dir: str):
    """Save emails to JSON files"""
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    
    for email_data in emails:
        filename = f"email_{email_data['id'].replace(' ', '_')}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        file_path = output_path / filename
        
        with open(file_path, "w", encoding="utf-8") as f:
            json.dump(email_data, f, indent=2, ensure_ascii=False)
    
    print(f"Saved {len(emails)} emails to {output_dir}")


def main():
    parser = argparse.ArgumentParser(description="Read emails using IMAP")
    parser.add_argument(
        "--config",
        type=str,
        default="config/imap_config.json",
        help="Path to IMAP configuration file",
    )
    parser.add_argument(
        "--folder",
        type=str,
        default="INBOX",
        help="IMAP folder to read from (default: INBOX)",
    )
    parser.add_argument(
        "--limit",
        type=int,
        help="Maximum number of emails to fetch",
    )
    parser.add_argument(
        "--since",
        type=str,
        help="Fetch emails since date (format: DD-MMM-YYYY, e.g., 01-Jan-2024)",
    )
    parser.add_argument(
        "--download-attachments",
        action="store_true",
        help="Download email attachments",
    )
    parser.add_argument(
        "--output",
        type=str,
        default="data/processed_emails",
        help="Output directory for email JSON files",
    )
    
    args = parser.parse_args()
    
    # Load configuration
    if not os.path.exists(args.config):
        print(f"Error: Configuration file not found: {args.config}")
        print("Please create it from config/imap_config.json.example")
        sys.exit(1)
    
    with open(args.config, "r", encoding="utf-8") as f:
        config = json.load(f)
    
    try:
        # Connect to IMAP
        mail = connect_imap(config)
        
        # Fetch emails
        emails = fetch_emails(
            mail=mail,
            folder=args.folder,
            limit=args.limit,
            since_date=args.since,
            download_attachments=args.download_attachments,
            attachments_dir="data/attachments",
        )
        
        # Save emails
        if emails:
            save_emails(emails, args.output)
            print(f"\nSuccessfully processed {len(emails)} emails!")
        else:
            print("No emails found.")
        
        # Close connection
        mail.close()
        mail.logout()
    
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
