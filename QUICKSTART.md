# Quick Start Guide

Get up and running with the Email Workflow Automation project in 5 minutes.

## Step 1: Install Dependencies

```bash
# Install Python packages
pip install -r requirements.txt

# Install n8n globally
npm install -g n8n
```

## Step 2: Configure Email Access

You have two options for email access:

### Option A: IMAP (No Azure Required) - Recommended for Quick Start

**Works with Gmail, Outlook.com, Yahoo, and most email providers**

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

### Option B: Azure Outlook API (Requires Azure Account)

1. Copy the example config:
   ```bash
   cp config/outlook_config.json.example config/outlook_config.json
   ```

2. Get your Azure credentials:
   - Go to https://portal.azure.com
   - Create an App Registration
   - Add permissions: `Mail.Read`, `Mail.ReadWrite`, `Files.Read`
   - Create a client secret
   - Copy Client ID, Tenant ID, and Client Secret

3. Edit `config/outlook_config.json` with your credentials

## Step 3: Start Services

### Terminal 1: Start n8n
```bash
n8n start
```
Open http://localhost:5678

### Terminal 2: Start ML API Server
```bash
python api/ml_api_server.py
```
The API will be available at http://localhost:5000

## Step 4: Import n8n Workflow

1. In n8n UI, click "Import from File"
2. Select `workflows/outlook_email_processor.json`
3. Configure Outlook OAuth2 credentials in the workflow nodes
4. Activate the workflow

## Step 5: Collect and Label Emails

### If using IMAP (Option A):

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

### If using Azure/n8n (Option B):

1. Wait for emails to be collected (workflow runs every minute)
2. Check `data/processed_emails/` for collected emails
3. Process attachments (if needed):
   ```bash
   python scripts/process_attachments.py
   ```
4. Label emails:
   ```bash
   python scripts/label_emails.py
   ```

## Step 6: Train the Model

```bash
python ml_training/train_model.py
```

The model will be saved to `models/email_classifier.pkl`

## Step 7: Test Predictions

The workflow will automatically predict labels for new emails. You can also test manually:

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

- **n8n OAuth error**: Make sure redirect URI matches in Azure portal
- **API not responding**: Check if port 5000 is available
- **No emails collected**: 
  - If using IMAP: Run `python scripts/imap_email_reader.py` manually to test
  - If using n8n: Verify Outlook credentials in n8n
- **Model training fails**: Ensure you have labeled emails in `data/labeled_emails.json`

## Next Steps

- Review `config/training_config.json` to customize model parameters
- Add more labeled emails to improve accuracy
- Customize the n8n workflow for your specific needs
- Enable auto-categorization in Outlook (uncomment the last node in workflow)
