# Quick Start Guide

Get up and running with the Email Workflow Automation project in 5 minutes.

## Step 1: Install Dependencies

```bash
# Install Python packages
pip install -r requirements.txt
```

## Step 2: Configure Microsoft Graph API Access

1. Copy the example config:
   ```bash
   cp config/graph_config.json.example config/graph_config.json
   ```

2. Edit `config/graph_config.json` with your Azure AD app credentials:
   ```json
   {
     "client_id": "your-azure-ad-application-client-id",
     "client_secret": "your-azure-ad-application-secret",
     "tenant_id": "your-azure-ad-tenant-id",
     "user_principal_name": "user@domain.com",
     "ml_api_url": "http://localhost:5000"
   }
   ```

3. **Set up Azure AD App Registration:**
   - Go to https://portal.azure.com
   - Navigate to Microsoft Entra ID > App registrations
   - Create a new app registration
   - Note the Application (client) ID
   - Create a client secret and note the Tenant ID
   - Add API permissions: Mail.ReadWrite (Application permissions)
   - Grant admin consent

4. Test email processing:
   ```bash
   python scripts/graph_email_tagger.py
   ```

5. Test email sending (optional):
   ```bash
   # First create config/smtp_config.json from config/smtp_config.json.example
   python scripts/smtp_email_writer.py --to recipient@example.com --subject "Test" --body "Hello"
   ```

## Step 3: Start ML API Server
```bash
python api/ml_api_server.py
```
The API will be available at http://localhost:5000

## Step 4: Collect and Label Emails

1. Process emails using Microsoft Graph API:
   ```bash
   # Process emails and add ML-predicted tags
   python scripts/graph_email_tagger.py
   ```

2. Check `data/processed_emails/` for collected emails (if saved)

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

- **Microsoft Graph API authentication error**: 
  - Verify your client_id, client_secret, and tenant_id are correct
  - Ensure Mail.ReadWrite application permission is granted
  - Verify admin consent has been granted
  - Check that user_principal_name is correct

- **API not responding**: Check if port 5000 is available
- **No emails processed**: Check Microsoft Graph API permissions and user access
- **Model training fails**: Ensure you have labeled emails in `data/labeled_emails.json`

## Next Steps

- Review `config/training_config.json` to customize model parameters
- Add more labeled emails to improve accuracy
- Set up automated email processing (e.g., cron job or scheduled task)
- Configure email processing settings in `config/graph_config.json`
