# Outlook Email Setup Guide

This guide shows you how to read and write Outlook emails using IMAP/SMTP.

## Quick Setup

### 1. Create Configuration File

```bash
cp config/imap_config.json.example config/imap_config.json
```

### 2. Configure Outlook

Edit `config/imap_config.json` with your Outlook settings:

```json
{
  "imap_server": "outlook.office365.com",
  "imap_port": 993,
  "smtp_server": "smtp.office365.com",
  "smtp_port": 587,
  "use_tls": true,
  "username": "your-email@outlook.com",
  "password": "your-password"
}
```

**Outlook.com Setup Steps:**
1. Go to Outlook.com settings: https://outlook.live.com/mail
2. Navigate to **Settings** (gear icon) > **Mail** > **Sync email**
3. Enable **IMAP access**
4. If your account requires it, generate an App Password:
   - Go to https://account.microsoft.com/security
   - Under "App passwords", create a new app password
   - Use the generated password instead of your regular password

## Usage

### Read Emails

```bash
# Fetch last 10 emails
python scripts/imap_email_reader.py --limit 10

# Fetch emails with attachments downloaded
python scripts/imap_email_reader.py --limit 50 --download-attachments

# Fetch emails since a specific date
python scripts/imap_email_reader.py --since 01-Jan-2024

# Read from a specific folder (e.g., "Sent", "Drafts")
python scripts/imap_email_reader.py --folder "Sent" --limit 20
```

### Send Emails

```bash
# Send a simple email
python scripts/smtp_email_writer.py \
  --to recipient@example.com \
  --subject "Test Email" \
  --body "This is a test email"

# Send with HTML body
python scripts/smtp_email_writer.py \
  --to recipient@example.com \
  --subject "Test Email" \
  --body "Plain text version" \
  --body-html "<h1>HTML version</h1><p>This is HTML</p>"

# Send with attachments
python scripts/smtp_email_writer.py \
  --to recipient@example.com \
  --subject "Report" \
  --body "Please find attached report" \
  --attachment file1.pdf file2.docx

# Send with CC and BCC
python scripts/smtp_email_writer.py \
  --to recipient@example.com \
  --cc cc@example.com \
  --bcc bcc@example.com \
  --subject "Meeting Notes" \
  --body "Meeting notes attached"
```

## Integration with Workflow

The IMAP reader saves emails in the same JSON format, so they work seamlessly with the rest of the system:

1. **Read emails**: `python scripts/imap_email_reader.py --limit 50 --download-attachments`
2. **Process attachments**: `python scripts/process_attachments.py`
3. **Label emails**: `python scripts/label_emails.py`
4. **Train model**: `python ml_training/train_model.py`

## Troubleshooting

### Connection Errors

- **"Authentication failed"**: 
  - Verify your Outlook email and password are correct
  - Some Office 365 accounts require an App Password instead of your regular password
  - Check that IMAP is enabled in Outlook.com settings

- **"Connection refused"**:
  - Verify IMAP server is set to `outlook.office365.com` and port `993`
  - Verify SMTP server is set to `smtp.office365.com` and port `587`
  - Check firewall settings
  - Some networks block IMAP/SMTP ports

- **"SSL/TLS error"**:
  - Ensure `use_tls` is set to `true`
  - Outlook.com uses TLS (port 587 for SMTP, 993 for IMAP)

### Outlook.com Specific Issues

- **IMAP not working**: 
  - Make sure IMAP is enabled in Outlook.com settings (Settings > Mail > Sync email)
  - Some accounts may need to enable IMAP from the Outlook web interface

- **Modern Authentication**: 
  - Some Office 365 accounts may require an App Password instead of your regular password
  - Generate an App Password from https://account.microsoft.com/security
  - Use the App Password in your config file

- **Office 365 Business/Enterprise accounts**:
  - May have additional security requirements
  - Contact your IT administrator if IMAP access is restricted

## Security Notes

- **Never commit** `config/imap_config.json` to version control (it's in .gitignore)
- Use App Passwords instead of regular passwords when possible
- Consider using environment variables for sensitive credentials
- App Passwords can be revoked and regenerated if compromised

## Alternative: Environment Variables

For better security, you can use environment variables instead of the config file:

```bash
export IMAP_SERVER="outlook.office365.com"
export IMAP_USERNAME="your-email@outlook.com"
export IMAP_PASSWORD="your-password"
```

Then modify the scripts to read from environment variables.
