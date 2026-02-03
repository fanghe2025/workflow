# Quick Start Guide

Get up and running with the Email Workflow Automation project in 5 minutes.

## Step 1: Install Dependencies

```bash
# Install Python packages
pip install -r requirements.txt
```

## Step 2: Configure Email Access

**Works with Gmail, Outlook.com, and most email providers**

1. Copy the example config:
   ```bash
   cp config/imap_config.json.example config/imap_config.json
   ```

2. Edit `config/imap_config.json` with your email credentials:
   ```json
   {
     "imap_server": "imap.gmail.com",
     "imap_port": 993,
     "smtp_server": "smtp.gmail.com",
     "smtp_port": 587,
     "username": "your-email@gmail.com",
     "password": "your-app-password"
   }
   ```

3. **For Gmail users:**
   - Enable 2-Factor Authentication
   - Generate an App Password: https://myaccount.google.com/apppasswords
   - Use the App Password (not your regular password)

4. **For Outlook.com users:**
   - Enable IMAP in account settings
   - Use your regular password or an App Password

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
  - Verify your email and password are correct
  - For Gmail: Make sure you're using an App Password, not your regular password
  - Check that IMAP is enabled in your email account settings
  - Verify the IMAP server address and port are correct for your provider

- **SMTP sending fails**:
  - Check SMTP server settings match your email provider
  - Ensure TLS/SSL settings are correct (usually TLS for port 587)
  - For Gmail: Use App Password, not regular password

- **API not responding**: Check if port 5000 is available
- **No emails collected**: Run `python scripts/imap_email_reader.py` manually to test
- **Model training fails**: Ensure you have labeled emails in `data/labeled_emails.json`

## Next Steps

- Review `config/training_config.json` to customize model parameters
- Add more labeled emails to improve accuracy
- Set up automated email collection (e.g., cron job or scheduled task)
- See `IMAP_SETUP.md` for advanced configuration options
