"""
SMTP Email Writer - Send emails without Azure credentials

This script sends emails using SMTP protocol, which works with most email providers
(Gmail, Outlook.com, Yahoo, etc.) without requiring Azure credentials.

Usage:
    python scripts/smtp_email_writer.py --config config/imap_config.json --to recipient@example.com --subject "Test" --body "Email body"
"""

import smtplib
import json
import os
import sys
import argparse
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from pathlib import Path
from typing import List, Optional


def connect_smtp(config: dict) -> smtplib.SMTP:
    """Connect to SMTP server"""
    server = config.get("smtp_server")
    port = config.get("smtp_port", 587)
    username = config.get("username")
    password = config.get("password")
    use_tls = config.get("use_tls", True)
    
    if not all([server, username, password]):
        raise ValueError("Missing required SMTP configuration: server, username, password")
    
    print(f"Connecting to {server}:{port}...")
    mail = smtplib.SMTP(server, port)
    
    if use_tls:
        mail.starttls()
    
    mail.login(username, password)
    print("Connected successfully!")
    
    return mail


def send_email(
    mail: smtplib.SMTP,
    from_addr: str,
    to_addrs: List[str],
    subject: str,
    body: str,
    body_html: Optional[str] = None,
    attachments: Optional[List[str]] = None,
    cc: Optional[List[str]] = None,
    bcc: Optional[List[str]] = None,
):
    """Send email via SMTP"""
    # Create message
    if body_html:
        msg = MIMEMultipart("alternative")
    else:
        msg = MIMEMultipart()
    
    msg["From"] = from_addr
    msg["To"] = ", ".join(to_addrs)
    msg["Subject"] = subject
    
    if cc:
        msg["Cc"] = ", ".join(cc)
    
    # Add body
    if body_html:
        part1 = MIMEText(body, "plain")
        part2 = MIMEText(body_html, "html")
        msg.attach(part1)
        msg.attach(part2)
    else:
        msg.attach(MIMEText(body, "plain"))
    
    # Add attachments
    if attachments:
        for file_path in attachments:
            if os.path.exists(file_path):
                with open(file_path, "rb") as f:
                    part = MIMEBase("application", "octet-stream")
                    part.set_payload(f.read())
                    encoders.encode_base64(part)
                    part.add_header(
                        "Content-Disposition",
                        f'attachment; filename= "{os.path.basename(file_path)}"',
                    )
                    msg.attach(part)
    
    # Send email
    recipients = to_addrs.copy()
    if cc:
        recipients.extend(cc)
    if bcc:
        recipients.extend(bcc)
    
    mail.send_message(msg, to_addrs=recipients)
    print(f"Email sent successfully to {', '.join(to_addrs)}")


def main():
    parser = argparse.ArgumentParser(description="Send emails using SMTP")
    parser.add_argument(
        "--config",
        type=str,
        default="config/imap_config.json",
        help="Path to email configuration file",
    )
    parser.add_argument(
        "--to",
        type=str,
        required=True,
        help="Recipient email address(es), comma-separated",
    )
    parser.add_argument(
        "--subject",
        type=str,
        required=True,
        help="Email subject",
    )
    parser.add_argument(
        "--body",
        type=str,
        required=True,
        help="Email body (plain text)",
    )
    parser.add_argument(
        "--body-html",
        type=str,
        help="Email body (HTML)",
    )
    parser.add_argument(
        "--cc",
        type=str,
        help="CC email address(es), comma-separated",
    )
    parser.add_argument(
        "--bcc",
        type=str,
        help="BCC email address(es), comma-separated",
    )
    parser.add_argument(
        "--attachment",
        type=str,
        nargs="+",
        help="Attachment file path(s)",
    )
    parser.add_argument(
        "--from",
        type=str,
        dest="from_addr",
        help="From email address (defaults to username in config)",
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
        # Connect to SMTP
        mail = connect_smtp(config)
        
        # Parse recipients
        to_addrs = [addr.strip() for addr in args.to.split(",")]
        cc = [addr.strip() for addr in args.cc.split(",")] if args.cc else None
        bcc = [addr.strip() for addr in args.bcc.split(",")] if args.bcc else None
        
        # Get from address
        from_addr = args.from_addr or config.get("username")
        
        # Send email
        send_email(
            mail=mail,
            from_addr=from_addr,
            to_addrs=to_addrs,
            subject=args.subject,
            body=args.body,
            body_html=args.body_html,
            attachments=args.attachment,
            cc=cc,
            bcc=bcc,
        )
        
        # Close connection
        mail.quit()
    
    except Exception as e:
        print(f"Error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
