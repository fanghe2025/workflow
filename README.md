# Email Workflow Automation with ML Labeling

This project reads and processes Outlook emails (including attachments) using Microsoft Graph API and trains a machine learning model to automatically label emails based on their content.

## Features

- ✅ **Outlook Email Processing**: Reads emails from Outlook.com and Office 365 accounts
- ✅ **Attachment Support**: Downloads and extracts text from PDFs, Word docs, Excel files, and more
- ✅ **ML-Based Labeling**: Trains a model on labeled emails to predict categories
- ✅ **REST API**: Flask API server for real-time predictions

## Project Structure

```
.
├── api/                    # ML API server
│   └── ml_api_server.py   # Flask API for predictions
├── config/                 # Configuration files
│   ├── graph_config.json.example
│   ├── smtp_config.json.example
│   └── training_config.json
├── data/                   # Data storage (gitignored)
│   ├── processed_emails/  # Emails collected from Microsoft Graph API
│   ├── attachments/        # Downloaded attachments
│   └── labeled_emails.json # Labeled training data
├── ml_training/            # ML training scripts
│   └── train_model.py     # Model training script
├── models/                 # Trained models (gitignored)
│   └── email_classifier.pkl
├── scripts/                # Utility scripts
│   ├── graph_email_tagger.py
│   ├── smtp_email_writer.py
│   ├── process_attachments.py
│   └── label_emails.py
├── utils/                  # Utility modules
│   └── attachment_processor.py
├── requirements.txt        # Python dependencies
└── README.md
```

## Prerequisites

1. **Python 3.8+**
   ```bash
   python --version  # Should be 3.8 or higher
   ```

2. **Microsoft 365 / Azure AD Account**
   - Office 365 or Microsoft 365 account
   - Azure AD app registration with Microsoft Graph API permissions
   - Application permissions: Mail.ReadWrite

## Installation

### 1. Clone and Setup

```bash
# Install Python dependencies
pip install -r requirements.txt
```

### 2. Configure Microsoft Graph API Access

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
   - Create a new app registration or use existing one
   - Note the Application (client) ID
   - Create a client secret and note the Tenant ID
   - Add API permissions: Mail.ReadWrite (Application permissions)
   - Grant admin consent

### 3. Configure Training Settings

Edit `config/training_config.json` to customize:
- Model parameters (Random Forest)
- Text vectorization settings
- Attachment processing options

### 4. Start ML API Server

```bash
python api/ml_api_server.py
```

The API will run on `http://localhost:5000`

## Usage

### Collecting and Processing Emails

1. **Read and tag emails from your inbox**:
   ```bash
   # Process emails and add ML-predicted tags
   python scripts/graph_email_tagger.py
   ```
   
   This will read emails from Microsoft Graph API, predict labels using the ML model, and add tags to emails.

2. **Process attachments** (if not downloaded automatically):
   ```bash
   python scripts/process_attachments.py --emails data/processed_emails
   ```

2. **Send emails** (optional):
   ```bash
   # First, create config/smtp_config.json from config/smtp_config.json.example
   python scripts/smtp_email_writer.py --to recipient@example.com --subject "Test" --body "Hello"
   ```

### Training the Model

1. **Label emails** for training:
   ```bash
   python scripts/label_emails.py --emails data/processed_emails
   ```
   
   This interactive script helps you label emails. You can also manually edit `data/labeled_emails.json`.

2. **Train the model**:
   ```bash
   python ml_training/train_model.py
   ```
   
   The trained model will be saved to `models/email_classifier.pkl`

### Using Predictions

You can use the ML API to predict labels for emails:

1. **Use the API directly**:
   ```bash
   curl -X POST http://localhost:5000/api/predict \
     -H "Content-Type: application/json" \
     -d '{
       "subject": "Meeting tomorrow",
       "body": "Let us meet at 2pm",
       "from": "colleague@example.com"
     }'
   ```

2. **Batch predictions**:
   ```bash
   curl -X POST http://localhost:5000/api/predict/batch \
     -H "Content-Type: application/json" \
     -d '{
       "emails": [
         {"subject": "Email 1", "body": "Content 1"},
         {"subject": "Email 2", "body": "Content 2"}
       ]
     }'
   ```

## Email Data Format

Emails are stored in JSON format with the following structure:

```json
{
  "id": "email-id",
  "subject": "Email subject",
  "from": "sender@example.com",
  "to": ["recipient@example.com"],
  "body": "Email body content",
  "receivedDateTime": "2024-01-01T00:00:00Z",
  "hasAttachments": true,
  "attachments": [
    {
      "id": "attachment-id",
      "name": "document.pdf",
      "contentType": "application/pdf",
      "size": 12345,
      "file_path": "data/attachments/email-id/document.pdf",
      "text_content": "Extracted text from attachment"
    }
  ],
  "importance": "normal",
  "label": "category_name"  // Added during labeling
}
```

## Supported Attachment Types

The attachment processor supports:
- **PDF** (.pdf) - Text extraction
- **Word Documents** (.docx, .doc) - Text extraction
- **Excel Files** (.xlsx, .xls) - Cell content extraction
- **Text Files** (.txt) - Direct text reading

## API Endpoints

### Health Check
```
GET /health
```

### Predict Label
```
POST /api/predict
Content-Type: application/json

{
  "subject": "Email subject",
  "body": "Email body",
  "from": "sender@example.com",
  "hasAttachments": false,
  "attachments": []
}
```

### Batch Predict
```
POST /api/predict/batch
Content-Type: application/json

{
  "emails": [
    { "subject": "...", "body": "..." },
    { "subject": "...", "body": "..." }
  ]
}
```

### Model Info
```
GET /api/model/info
```

## Configuration

### Training Configuration (`config/training_config.json`)

- `model`: Random Forest classifier parameters
- `vectorizer`: TF-IDF vectorization settings
- `training`: Train/test split and validation settings
- `attachment_processing`: Attachment extraction options

### Microsoft Graph Configuration (`config/graph_config.json`)

- `client_id`: Azure AD application (client) ID
- `client_secret`: Azure AD application secret (for app-only auth)
- `tenant_id`: Azure AD tenant ID
- `user_principal_name`: User email/UPN (required for app-only auth)
- `ml_api_url`: ML API server URL (default: http://localhost:5000)

## Troubleshooting

### Email Access Issues

- **Microsoft Graph API authentication error**: 
  - Verify your client_id, client_secret, and tenant_id are correct
  - Ensure Mail.ReadWrite application permission is granted
  - Verify admin consent has been granted for the app
  - Check that user_principal_name is correct and user exists in tenant

- **Attachments not downloading**: Check file permissions and disk space
- **API calls failing**: Ensure ML API server is running on port 5000

### ML Training Issues

- **No labeled emails**: Use `scripts/label_emails.py` to label emails first
- **Low accuracy**: Add more labeled training data
- **Memory errors**: Reduce `max_features` in training config

### Attachment Processing Issues

- **PDF extraction fails**: Ensure PyPDF2 is installed correctly
- **Word doc extraction fails**: Check python-docx installation
- **Large files**: Adjust `max_file_size_mb` in training config

## Development

### Adding New Features

1. **New attachment types**: Extend `utils/attachment_processor.py`
2. **Model improvements**: Modify `ml_training/train_model.py`
3. **API endpoints**: Add routes to `api/ml_api_server.py`

### Testing

```bash
# Test attachment processing
python -c "from utils.attachment_processor import AttachmentProcessor; p = AttachmentProcessor(); print(p.process_attachment('test.pdf'))"

# Test model training
python ml_training/train_model.py

# Test API
python api/ml_api_server.py
# Then test endpoints with curl or Postman
```

## License

This project is provided as-is for workflow automation and ML training purposes.
