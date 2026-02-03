# Quick Start Guide

Get up and running with the Email Workflow Automation project in 5 minutes.

## Step 1: Install Dependencies

```bash
# Install Python packages
pip install -r requirements.txt
```

## Step 2: Configure Outlook Email Access

1. Copy the example config:
   ```bash
   cp config/imap_config.json.example config/imap_config.json
   ```

2. Edit `config/imap_config.json` with your Outlook credentials:
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

3. **Enable IMAP in Outlook:**
   - Go to Outlook.com settings (https://outlook.live.com/mail)
   - Navigate to **Settings** > **Mail** > **Sync email**
   - Enable **IMAP access**
   - If your account requires it, generate an App Password from your Microsoft account security settings

5. Test email reading:
   ```bash
   python scripts/imap_email_reader.py --limit 5
   ```

6. Test email sending:
   ```bash
   python scripts/smtp_email_writer.py --to recipient@example.com --subject "Test" --body "Hello"
   ```

## Step 3: Start ML API Server
```bash
python api/ml_api_server.py
```
The API will be available at http://localhost:5000

## Step 4: Collect and Label Emails

1. Collect emails using the IMAP reader:
   ```bash
   # Fetch last 50 emails
   python scripts/imap_email_reader.py --limit 50 --download-attachments
   
   # Or fetch emails since a specific date
   python scripts/imap_email_reader.py --since 01-Jan-2024 --download-attachments
   ```

2. Check `data/processed_emails/` for collected emails

3. Process attachments (if needed):
   ```bash
   python scripts/process_attachments.py
   ```

4. Label emails:
   ```bash
   python scripts/label_emails.py
   ```

## Step 5: Train the Model

```bash
python ml_training/train_model.py
```

The model will be saved to `models/email_classifier.pkl`

## Step 6: Test Predictions

You can test predictions manually:

```bash
curl -X POST http://localhost:5000/api/predict \
  -H "Content-Type: application/json" \
  -d '{
    "subject": "Meeting request",
    "body": "Can we meet tomorrow?",
    "from": "colleague@example.com"
  }'
```

## Troubleshooting

- **IMAP connection error**: 
  - Verify your Outlook email and password are correct
  - Check that IMAP is enabled in Outlook.com settings
  - Some Office 365 accounts may require an App Password instead of your regular password
  - Verify the IMAP server is set to `outlook.office365.com` and port `993`

- **SMTP sending fails**:
  - Check SMTP server is set to `smtp.office365.com` and port `587`
  - Ensure `use_tls` is set to `true`
  - Some accounts may require an App Password for SMTP

- **API not responding**: Check if port 5000 is available
- **No emails collected**: Run `python scripts/imap_email_reader.py` manually to test
- **Model training fails**: Ensure you have labeled emails in `data/labeled_emails.json`

## Next Steps

- Review `config/training_config.json` to customize model parameters
- Add more labeled emails to improve accuracy
- Set up automated email collection (e.g., cron job or scheduled task)
- See `IMAP_SETUP.md` for advanced configuration options
