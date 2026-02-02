"""
Email Labeling Model Training Script

This script trains a machine learning model to classify emails based on
their content, subject, sender, attachments, and other features.
"""

import json
import os
import sys
from pathlib import Path
from typing import List, Dict, Any
import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import classification_report, accuracy_score
import joblib

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from utils.attachment_processor import AttachmentProcessor


class EmailLabelingModel:
    """Machine learning model for email labeling with attachment support"""

    def __init__(
        self,
        model_path: str = "models/email_classifier.pkl",
        config: Dict[str, Any] = None,
    ):
        self.model_path = model_path
        self.config = config or {}
        self.vectorizer = TfidfVectorizer(
            max_features=self.config.get("vectorizer", {}).get("max_features", 5000),
            ngram_range=tuple(
                self.config.get("vectorizer", {}).get("ngram_range", [1, 2])
            ),
            stop_words="english",
            min_df=self.config.get("vectorizer", {}).get("min_df", 2),
            max_df=self.config.get("vectorizer", {}).get("max_df", 0.95),
        )

        model_config = self.config.get("model", {})
        self.model = RandomForestClassifier(
            n_estimators=model_config.get("n_estimators", 100),
            max_depth=model_config.get("max_depth", 20),
            random_state=model_config.get("random_state", 42),
            n_jobs=-1,
        )
        self.label_encoder = {}
        self.reverse_label_encoder = {}
        self.is_trained = False
        self.attachment_processor = (
            AttachmentProcessor()
            if self.config.get("attachment_processing", {}).get("enabled", True)
            else None
        )

    def prepare_text_features(self, emails: List[Dict[str, Any]]) -> str:
        """Combine all text content from email and attachments"""
        texts = []

        for email in emails:
            # Combine subject and body
            text_parts = [
                email.get("subject", ""),
                email.get("body", ""),
            ]

            # Add attachment text if available
            if self.attachment_processor and email.get("attachment_texts"):
                attachment_texts = email.get("attachment_texts", [])
                if attachment_texts:
                    text_parts.append("\n\n".join(attachment_texts))

            # Combine all text
            full_text = " ".join(text_parts)
            texts.append(full_text)

        return texts

    def prepare_additional_features(self, emails: List[Dict[str, Any]]) -> np.ndarray:
        """Extract additional non-text features"""
        features = []

        for email in emails:
            # Extract domain from sender
            from_email = email.get("from", "")
            domain = from_email.split("@")[-1] if "@" in from_email else ""

            # Count attachments
            num_attachments = len(email.get("attachments", []))
            has_attachments = 1 if num_attachments > 0 else 0

            # Attachment text length
            attachment_text_length = 0
            if email.get("attachment_texts"):
                attachment_text_length = sum(
                    len(text) for text in email.get("attachment_texts", [])
                )

            # Text statistics
            subject_length = len(email.get("subject", "").split())
            body_length = len(email.get("body", "").split())

            # Importance
            importance = email.get("importance", "normal")
            is_high_importance = 1 if importance == "high" else 0

            # Feature vector
            feat = [
                has_attachments,
                num_attachments,
                subject_length,
                body_length,
                attachment_text_length,
                is_high_importance,
                len(domain),  # Domain length as feature
            ]
            features.append(feat)

        return np.array(features)

    def train(self, labeled_emails: List[Dict[str, Any]]):
        """Train the model on labeled email data"""
        if not labeled_emails:
            raise ValueError("No labeled emails provided for training")

        # Filter emails with labels
        emails = [e for e in labeled_emails if "label" in e]
        labels = [e["label"] for e in emails]

        if not emails:
            raise ValueError("No emails with labels found")

        print(f"Found {len(emails)} labeled emails for training")

        # Process attachments if enabled
        if self.attachment_processor:
            print("Processing attachments...")
            for email in emails:
                if email.get("hasAttachments", False) and email.get("attachments"):
                    attachment_texts = []
                    for attachment in email.get("attachments", []):
                        # If attachment has text_content, use it
                        if "text_content" in attachment:
                            if attachment["text_content"]:
                                attachment_texts.append(attachment["text_content"])
                        # Otherwise try to process from file path
                        elif "file_path" in attachment:
                            result = self.attachment_processor.process_attachment(
                                attachment["file_path"]
                            )
                            if result.get("text_content"):
                                attachment_texts.append(result["text_content"])
                    email["attachment_texts"] = attachment_texts

        # Create label encoder
        unique_labels = sorted(set(labels))
        self.label_encoder = {label: idx for idx, label in enumerate(unique_labels)}
        self.reverse_label_encoder = {
            idx: label for label, idx in self.label_encoder.items()
        }

        print(f"Labels: {unique_labels}")

        # Prepare text features
        print("Vectorizing text content...")
        texts = self.prepare_text_features(emails)
        X_text = self.vectorizer.fit_transform(texts)

        # Prepare additional features
        print("Extracting additional features...")
        X_additional = self.prepare_additional_features(emails)

        # Combine features
        from scipy.sparse import hstack

        X = hstack([X_text, X_additional])

        # Encode labels
        y = np.array([self.label_encoder[label] for label in labels])

        # Split data
        training_config = self.config.get("training", {})
        test_size = training_config.get("test_size", 0.2)
        random_state = training_config.get("random_state", 42)
        stratify = y if training_config.get("stratify", True) else None

        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=test_size, random_state=random_state, stratify=stratify
        )

        # Train model
        print(f"\nTraining model on {len(X_train)} samples...")
        self.model.fit(X_train, y_train)

        # Evaluate
        y_pred = self.model.predict(X_test)
        accuracy = accuracy_score(y_test, y_pred)

        print(f"\nModel Accuracy: {accuracy:.4f}")
        print("\nClassification Report:")
        print(
            classification_report(
                y_test,
                y_pred,
                target_names=[
                    self.reverse_label_encoder[i] for i in range(len(unique_labels))
                ],
            )
        )

        self.is_trained = True

        # Save model
        self.save()

    def predict(self, email: Dict[str, Any]) -> Dict[str, Any]:
        """Predict label for a single email"""
        if not self.is_trained:
            raise ValueError("Model not trained. Please train the model first.")

        # Process attachments if needed
        if self.attachment_processor and email.get("hasAttachments", False):
            if "attachment_texts" not in email and email.get("attachments"):
                attachment_texts = []
                for attachment in email.get("attachments", []):
                    if "text_content" in attachment and attachment["text_content"]:
                        attachment_texts.append(attachment["text_content"])
                    elif "file_path" in attachment:
                        result = self.attachment_processor.process_attachment(
                            attachment["file_path"]
                        )
                        if result.get("text_content"):
                            attachment_texts.append(result["text_content"])
                email["attachment_texts"] = attachment_texts

        # Prepare text
        texts = self.prepare_text_features([email])
        X_text = self.vectorizer.transform(texts)

        # Additional features
        X_additional = self.prepare_additional_features([email])

        # Combine
        from scipy.sparse import hstack

        X = hstack([X_text, X_additional])

        # Predict
        prediction_idx = self.model.predict(X)[0]
        probabilities = self.model.predict_proba(X)[0]

        label = self.reverse_label_encoder[prediction_idx]
        confidence = float(max(probabilities))

        return {
            "label": label,
            "confidence": confidence,
            "all_probabilities": {
                self.reverse_label_encoder[i]: float(prob)
                for i, prob in enumerate(probabilities)
            },
        }

    def save(self):
        """Save the trained model"""
        os.makedirs(os.path.dirname(self.model_path), exist_ok=True)

        model_data = {
            "model": self.model,
            "vectorizer": self.vectorizer,
            "label_encoder": self.label_encoder,
            "reverse_label_encoder": self.reverse_label_encoder,
        }

        joblib.dump(model_data, self.model_path)
        print(f"Model saved to {self.model_path}")

    def load(self):
        """Load a trained model"""
        if not os.path.exists(self.model_path):
            raise FileNotFoundError(f"Model file not found: {self.model_path}")

        model_data = joblib.load(self.model_path)
        self.model = model_data["model"]
        self.vectorizer = model_data["vectorizer"]
        self.label_encoder = model_data["label_encoder"]
        self.reverse_label_encoder = model_data["reverse_label_encoder"]
        self.is_trained = True
        print(f"Model loaded from {self.model_path}")


def load_labeled_emails(data_path: str) -> List[Dict[str, Any]]:
    """Load labeled emails from JSON file"""
    if not os.path.exists(data_path):
        print(f"Warning: {data_path} not found. Creating empty file.")
        os.makedirs(os.path.dirname(data_path), exist_ok=True)
        with open(data_path, "w") as f:
            json.dump([], f)
        return []

    with open(data_path, "r", encoding="utf-8") as f:
        return json.load(f)


def main():
    """Main training function"""
    # Load configuration
    config_path = Path("config/training_config.json")
    if config_path.exists():
        with open(config_path, "r") as f:
            config = json.load(f)
    else:
        config = {}
        print("Warning: training_config.json not found. Using defaults.")

    # Get paths from config
    paths = config.get("paths", {})
    labeled_data_path = paths.get("labeled_data", "data/labeled_emails.json")
    model_path = paths.get("model_output", "models/email_classifier.pkl")

    # Create directories
    Path("data").mkdir(exist_ok=True)
    Path("models").mkdir(exist_ok=True)

    # Load labeled emails
    print("Loading labeled emails...")
    labeled_emails = load_labeled_emails(labeled_data_path)

    if not labeled_emails:
        print("No labeled emails found. Please label some emails first.")
        print(f"Expected format in {labeled_data_path}:")
        print(
            """
        [
          {
            "id": "email_id",
            "subject": "Email subject",
            "body": "Email body content",
            "from": "sender@example.com",
            "hasAttachments": false,
            "attachments": [],
            "importance": "normal",
            "label": "category_name"
          }
        ]
        """
        )
        return

    # Initialize and train model
    model = EmailLabelingModel(model_path=model_path, config=config)

    try:
        model.train(labeled_emails)
        print("\nTraining completed successfully!")
    except Exception as e:
        print(f"Error during training: {e}")
        import traceback

        traceback.print_exc()
        raise


if __name__ == "__main__":
    main()
