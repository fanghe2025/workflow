# Email Workflow Automation with ML Labeling

This project uses **n8n** for workflow automation to read and process Outlook emails (including attachments) and trains a machine learning model to automatically label emails based on their content.

## Features

- ✅ **Outlook Email Processing**: Automatically monitors and processes incoming emails
- ✅ **Attachment Support**: Downloads and extracts text from PDFs, Word docs, Excel files, and more
- ✅ **ML-Based Labeling**: Trains a model on labeled emails to predict categories
- ✅ **REST API**: Flask API server for real-time predictions
- ✅ **Automated Workflow**: n8n workflow handles the entire pipeline

## Project Structure

```
.
├── api/                    # ML API server
│   └── ml_api_server.py   # Flask API for predictions
├── config/                 # Configuration files
│   ├── outlook_config.json.example
│   ├── training_config.json
│   └── n8n_config.json
├── data/                   # Data storage (gitignored)
│   ├── processed_emails/  # Emails collected by n8n
│   ├── attachments/        # Downloaded attachments
│   └── labeled_emails.json # Labeled training data
├── ml_training/            # ML training scripts
│   └── train_model.py     # Model training script
├── models/                 # Trained models (gitignored)
│   └── email_classifier.pkl
├── scripts/                # Utility scripts
│   ├── process_attachments.py
│   └── label_emails.py
├── utils/                  # Utility modules
│   └── attachment_processor.py
├── workflows/              # n8n workflow configurations
│   └── outlook_email_processor.json
├── requirements.txt        # Python dependencies
└── README.md
```

## Prerequisites

1. **Node.js and n8n**
   ```bash
   npm install -g n8n
   ```

2. **Python 3.8+**
   ```bash
   python --version  # Should be 3.8 or higher
   ```

3. **Microsoft Outlook API Access**
   - Azure App Registration
   - Client ID and Client Secret
   - Tenant ID
   - Required permissions: `Mail.Read`, `Mail.ReadWrite`, `Files.Read`

## Installation

### 1. Clone and Setup

```bash
# Install Python dependencies
pip install -r requirements.txt
```

### 2. Configure Outlook API

1. Go to [Azure Portal](https://portal.azure.com)
2. Navigate to **Azure Active Directory** > **App registrations**
3. Create a new app registration
4. Add API permissions:
   - `Microsoft Graph` > `Mail.Read`
   - `Microsoft Graph` > `Mail.ReadWrite`
   - `Microsoft Graph` > `Files.Read`
5. Create a client secret
6. Copy `config/outlook_config.json.example` to `config/outlook_config.json`
7. Fill in your credentials:
   ```json
   {
     "client_id": "your-client-id",
     "client_secret": "your-client-secret",
     "tenant_id": "your-tenant-id"
   }
   ```

### 3. Configure Training Settings

Edit `config/training_config.json` to customize:
- Model parameters (Random Forest)
- Text vectorization settings
- Attachment processing options

### 4. Start n8n

```bash
n8n start
```

Navigate to `http://localhost:5678` and:
1. Import the workflow from `workflows/outlook_email_processor.json`
2. Configure Outlook OAuth2 credentials in n8n
3. Test the workflow

### 5. Start ML API Server

```bash
python api/ml_api_server.py
```

The API will run on `http://localhost:5000`

## Usage

### Workflow: Collecting and Processing Emails

1. **Start n8n workflow**: The workflow will automatically:
   - Monitor your Outlook inbox
   - Download new emails
   - Download and save attachments
   - Process email data
   - Call ML API for predictions
   - Save processed emails to `data/processed_emails/`

2. **Process attachments** (optional, if not done automatically):
   ```bash
   python scripts/process_attachments.py --emails data/processed_emails
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

The n8n workflow automatically calls the ML API for each email. You can also:

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

### n8n Configuration (`config/n8n_config.json`)

- `workflow`: Polling interval and processing options
- `api`: ML API endpoint settings
- `storage`: Data storage paths

## Troubleshooting

### n8n Workflow Issues

- **OAuth2 not working**: Ensure credentials are correctly configured in n8n
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
