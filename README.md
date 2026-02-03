# Email Workflow Automation with ML Labeling

This project reads and processes Outlook emails (including attachments) using IMAP and trains a machine learning model to automatically label emails based on their content.

## Features

- ✅ **Outlook Email Processing**: Reads emails from Outlook.com and Office 365 accounts
- ✅ **Attachment Support**: Downloads and extracts text from PDFs, Word docs, Excel files, and more
- ✅ **ML-Based Labeling**: Trains a model on labeled emails to predict categories
- ✅ **REST API**: Flask API server for real-time predictions
- ✅ **Email Sending**: Send emails via SMTP

## Project Structure

```
.
├── api/                    # ML API server
│   └── ml_api_server.py   # Flask API for predictions
├── config/                 # Configuration files
│   ├── imap_config.json.example
│   └── training_config.json
├── data/                   # Data storage (gitignored)
│   ├── processed_emails/  # Emails collected from IMAP
│   ├── attachments/        # Downloaded attachments
│   └── labeled_emails.json # Labeled training data
├── ml_training/            # ML training scripts
│   └── train_model.py     # Model training script
├── models/                 # Trained models (gitignored)
│   └── email_classifier.pkl
├── scripts/                # Utility scripts
│   ├── imap_email_reader.py
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

2. **Outlook Email Account**
   - Outlook.com or Office 365 account
   - IMAP must be enabled in account settings
   - Some accounts may require an App Password instead of your regular password

## Installation

### 1. Clone and Setup

```bash
# Install Python dependencies
pip install -r requirements.txt
```

### 2. Configure Email Access (IMAP)

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
   - Go to Outlook.com settings
   - Navigate to Mail > Sync email
   - Enable IMAP access
   - If your account requires it, generate an App Password

4. See `IMAP_SETUP.md` for detailed Outlook setup instructions.

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

1. **Read emails from your inbox**:
   ```bash
   # Fetch last 50 emails with attachments
   python scripts/imap_email_reader.py --limit 50 --download-attachments
   
   # Fetch emails since a specific date
   python scripts/imap_email_reader.py --since 01-Jan-2024 --download-attachments
   ```
   
   This will save emails to `data/processed_emails/` in JSON format.

2. **Process attachments** (if not downloaded automatically):
   ```bash
   python scripts/process_attachments.py --emails data/processed_emails
   ```

3. **Send emails** (optional):
   ```bash
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

### IMAP Configuration (`config/imap_config.json`)

- `imap_server`: IMAP server address (e.g., imap.gmail.com)
- `imap_port`: IMAP port (usually 993)
- `smtp_server`: SMTP server address (e.g., smtp.gmail.com)
- `smtp_port`: SMTP port (usually 587)
- `username`: Your email address
- `password`: Your email password or App Password

## Troubleshooting

### Email Access Issues

- **IMAP connection error**: 
  - Verify your email and password are correct
  - For Gmail: Make sure you're using an App Password, not your regular password
  - Check that IMAP is enabled in your email account settings
  - Verify the IMAP server address and port are correct for your provider

- **SMTP sending fails**:
  - Check SMTP server settings match your email provider
  - Ensure TLS/SSL settings are correct (usually TLS for port 587)
  - For Gmail: Use App Password, not regular password

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
