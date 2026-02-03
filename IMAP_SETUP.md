# IMAP Email Setup Guide

This guide shows you how to read and write emails **without Azure credentials** using IMAP/SMTP.

## Quick Setup

### 1. Create Configuration File

```bash
cp config/imap_config.json.example config/imap_config.json
```

### 2. Configure Your Email Provider

Edit `config/imap_config.json` with your email settings:

#### Gmail

```json
{
  "imap_server": "imap.gmail.com",
  "imap_port": 993,
  "smtp_server": "smtp.gmail.com",
  "smtp_port": 587,
  "use_tls": true,
  "username": "your-email@gmail.com",
  "password": "your-app-password"
}
```

**Gmail Setup Steps:**
1. Enable 2-Factor Authentication: https://myaccount.google.com/security
2. Generate App Password: https://myaccount.google.com/apppasswords
3. Use the 16-character App Password (not your regular password)

#### Outlook.com / Office 365

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

**Outlook.com Setup:**
1. Go to Settings > Mail > Sync email
2. Enable IMAP access
3. Use your regular password or generate an App Password

#### Yahoo Mail

```json
{
  "imap_server": "imap.mail.yahoo.com",
  "imap_port": 993,
  "smtp_server": "smtp.mail.yahoo.com",
  "smtp_port": 587,
  "use_tls": true,
  "username": "your-email@yahoo.com",
  "password": "your-app-password"
}
```

**Yahoo Setup:**
1. Go to Account Security settings
2. Generate an App Password
3. Use the App Password (not your regular password)

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

The IMAP reader saves emails in the same format as the n8n workflow, so they work seamlessly with the rest of the system:

1. **Read emails**: `python scripts/imap_email_reader.py --limit 50 --download-attachments`
2. **Process attachments**: `python scripts/process_attachments.py`
3. **Label emails**: `python scripts/label_emails.py`
4. **Train model**: `python ml_training/train_model.py`

## Troubleshooting

### Connection Errors

- **"Authentication failed"**: 
  - For Gmail/Yahoo: Make sure you're using an App Password, not your regular password
  - Check that 2FA is enabled and App Password is generated correctly

- **"Connection refused"**:
  - Verify IMAP/SMTP server addresses are correct
  - Check firewall settings
  - Some networks block IMAP/SMTP ports

- **"SSL/TLS error"**:
  - Verify `use_tls` setting matches your provider
  - Gmail/Outlook.com: Use TLS (port 587 for SMTP, 993 for IMAP)

### Gmail Specific Issues

- **"Less secure app access"**: Gmail no longer supports this. You MUST use App Passwords.
- **"Access blocked"**: You may need to allow access from your IP address in Google Account settings.

### Outlook.com Specific Issues

- **IMAP not working**: Make sure IMAP is enabled in Outlook.com settings
- **Modern Authentication**: Some Office 365 accounts may require OAuth2 (use Azure method instead)

## Security Notes

- **Never commit** `config/imap_config.json` to version control (it's in .gitignore)
- Use App Passwords instead of regular passwords when possible
- Consider using environment variables for sensitive credentials
- App Passwords can be revoked and regenerated if compromised

## Alternative: Environment Variables

For better security, you can use environment variables instead of the config file:

```bash
export IMAP_SERVER="imap.gmail.com"
export IMAP_USERNAME="your-email@gmail.com"
export IMAP_PASSWORD="your-app-password"
```

Then modify the scripts to read from environment variables.
