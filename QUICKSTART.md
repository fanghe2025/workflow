# Quick Start Guide

Get up and running with the Email Workflow Automation project in 5 minutes.

## Step 1: Install Dependencies

```bash
# Install Python packages
pip install -r requirements.txt

# Install n8n globally
npm install -g n8n
```

## Step 2: Configure Outlook API

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

- **n8n OAuth error**: Make sure redirect URI matches in Azure portal
- **API not responding**: Check if port 5000 is available
- **No emails collected**: Verify Outlook credentials in n8n
- **Model training fails**: Ensure you have labeled emails in `data/labeled_emails.json`

## Next Steps

- Review `config/training_config.json` to customize model parameters
- Add more labeled emails to improve accuracy
- Customize the n8n workflow for your specific needs
- Enable auto-categorization in Outlook (uncomment the last node in workflow)
