"""
Email Labeling Model Training Script

This script trains a machine learning model to classify emails based on
their content, subject, sender, attachments, and other features.
"""

import os
import sys
from pathlib import Path
from typing import List, Dict, Any
import numpy as np
from scipy.sparse import hstack
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import classification_report, accuracy_score
import joblib

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.attachment_processor import AttachmentProcessor


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

    def prepare_text_features(self, emails: List[Dict[str, Any]]) -> List[str]:
        """Combine all text content from email and attachments"""
        texts = []

        for email in emails:
            # Combine subject and body (support both 'body' and 'body_content' keys)
            subject = email["Subject"]
            body = email["Message"]
            sender = email["Sender"]
            attachment_names = email["attachments"]

            text_parts = [subject, body, sender]
            if attachment_names:
                text_parts.append(",".join(attachment_names))

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
            from_email = email["Sender"]
            domain = from_email.split("@")[-1] if "@" in from_email else ""

            # Count attachments
            num_attachments = len(email["attachments"])
            has_attachments = 1 if num_attachments > 0 else 0

            # Attachment text length
            attachment_text_length = 0
            if email.get("attachment_texts"):
                attachment_text_length = sum(
                    len(text) for text in email.get("attachment_texts", [])
                )

            # Importance
            importance = email.get("importance", "normal")
            is_high_importance = 1 if importance == "high" else 0

            # Feature vector
            feat = [
                is_high_importance,
                has_attachments,
                num_attachments,
                len(domain),  # Domain length as feature
                attachment_text_length,
            ]
            features.append(feat)

        return np.array(features)

    def train(self, labeled_emails: List[Dict[str, Any]]):
        """Train the model on labeled email data"""
        if not labeled_emails:
            raise ValueError("No labeled emails provided for training")

        # Filter emails with labels
        emails = [e for e in labeled_emails if "Tags" in e]
        labels = [",".join(e["Tags"]) for e in emails]

        if not emails:
            raise ValueError("No emails with labels found")

        print(f"Found {len(emails)} labeled emails for training")

        # Process attachments
        if self.attachment_processor:
            for email in emails:
                if email.get("hasAttachments", False) and email.get("attachments"):
                    attachment_texts = []
                    if "attachment_texts" not in email:
                        # Process only if missing
                        for attachment in email.get("attachments", []):
                            if (
                                "text_content" in attachment
                                and attachment["text_content"]
                            ):
                                attachment_texts.append(attachment["text_content"])
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
        X = hstack([X_text, X_additional])

        # Encode labels
        y = np.array([self.label_encoder[label] for label in labels])

        # Split data
        training_config = self.config.get("training", {})
        test_size = training_config.get("test_size", 0.2)
        random_state = training_config.get("random_state", 42)

        # Check if stratification is possible (each class needs at least 2 samples)
        stratify = None
        if training_config.get("stratify", True):
            from collections import Counter

            label_counts = Counter(labels)
            min_samples_per_class = min(label_counts.values())

            if min_samples_per_class >= 2:
                stratify = y
                print(
                    f"Using stratified split (min samples per class: {min_samples_per_class})"
                )
            else:
                print(
                    f"Warning: Cannot use stratified split. Some classes have only {min_samples_per_class} sample(s)."
                )
                print(f"Label distribution: {dict(label_counts)}")
                print("Using non-stratified split instead.")

        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=test_size, random_state=random_state, stratify=stratify
        )

        # Train model
        n_train_samples = (
            X_train.shape[0] if hasattr(X_train, "shape") else len(X_train)
        )
        print(f"\nTraining model on {n_train_samples} samples...")
        self.model.fit(X_train, y_train)

        # Evaluate
        y_pred = self.model.predict(X_test)
        accuracy = accuracy_score(y_test, y_pred)

        print(f"\nModel Accuracy: {accuracy:.4f}")
        print("\nClassification Report:")

        # Get unique classes present in test set
        unique_test_classes = sorted(set(y_test) | set(y_pred))
        target_names = [self.reverse_label_encoder[i] for i in unique_test_classes]

        print(
            classification_report(
                y_test,
                y_pred,
                labels=unique_test_classes,
                target_names=target_names,
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
        X = hstack([X_text, X_additional])

        # Predict
        prediction_idx = self.model.predict(X)[0]
        probabilities = self.model.predict_proba(X)[0]

        label = self.reverse_label_encoder[prediction_idx]
        confidence = float(max(probabilities))

        # Convert all probabilities to native Python types for JSON serialization
        all_probs = {}
        for i, prob in enumerate(probabilities):
            label_name = self.reverse_label_encoder[i]
            # Ensure it's a native Python float
            all_probs[label_name] = float(prob)

        return {
            "label": str(label),
            "confidence": confidence,
            "all_probabilities": all_probs,
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
