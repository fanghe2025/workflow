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
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.model_selection import train_test_split
from sklearn.ensemble import RandomForestClassifier
from sklearn.multioutput import MultiOutputClassifier
from sklearn.metrics import classification_report, accuracy_score, hamming_loss
from sklearn.preprocessing import MultiLabelBinarizer
import joblib

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.attachment_processor import AttachmentProcessor
from core.constants import NO_LABEL


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
        prediction_config = self.config.get("prediction", {})
        self.prediction_threshold = prediction_config.get("threshold", 0.1)

        model_config = self.config.get("model", {})
        base_classifier = RandomForestClassifier(
            n_estimators=model_config.get("n_estimators", 100),
            max_depth=model_config.get("max_depth", 20),
            random_state=model_config.get("random_state", 42),
            n_jobs=-1,
        )
        self.model = MultiOutputClassifier(base_classifier, n_jobs=-1)
        self.label_binarizer = MultiLabelBinarizer()
        self.label_list = []  # Store list of all unique labels
        self.is_trained = False
        self.attachment_processor = (
            AttachmentProcessor()
            if self.config.get("attachment_processing", {}).get("enabled", False)
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
            other_recipients = email["OtherRecipients"]
            
            # text_parts = [subject, body, sender]
            text_parts = [subject, sender]
            if other_recipients:
                text_parts.append(",".join(other_recipients))
            if attachment_names:
                text_parts.append(",".join(attachment_names))
            text_parts.append(body)

            # Add attachment text if available
            if self.attachment_processor and email.get("attachment_texts"):
                attachment_texts = email.get("attachment_texts", [])
                if attachment_texts:
                    text_parts.append("\n\n".join(attachment_texts))

            # Combine all text
            full_text = " ".join(text_parts)
            texts.append(full_text)

        return texts

    def train(self, labeled_emails: List[Dict[str, Any]]):
        """Train the model on labeled email data"""
        if not labeled_emails:
            raise ValueError("No labeled emails provided for training")

        # Filter emails with labels
        emails = [e for e in labeled_emails if "Tags" in e and e["Tags"]]
        labels = [e["Tags"] for e in emails]  # Keep as list of lists

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

        # Get all unique labels and create binarizer
        all_unique_labels = sorted(
            set(label for label_list in labels for label in label_list)
        )
        self.label_list = all_unique_labels

        # Fit binarizer on the actual label lists from training data
        self.label_binarizer.fit(labels)

        print(f"Unique labels: {all_unique_labels}")
        print(f"Total unique labels: {len(all_unique_labels)}")

        # Prepare text features
        print("Vectorizing text content...")
        texts = self.prepare_text_features(emails)
        X = self.vectorizer.fit_transform(texts)

        # Encode labels as binary matrix (multi-label format)
        y = self.label_binarizer.transform(labels)

        # Split data
        training_config = self.config.get("training", {})
        test_size = training_config.get("test_size", 0.2)
        random_state = training_config.get("random_state", 42)

        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=test_size, random_state=random_state
        )

        # Train model
        n_train_samples = (
            X_train.shape[0] if hasattr(X_train, "shape") else len(X_train)
        )
        print(f"\nTraining model on {n_train_samples} samples...")
        self.model.fit(X_train, y_train)

        # Evaluate
        y_pred = self.model.predict(X_test)

        # Calculate metrics for multi-label classification
        hamming = hamming_loss(y_test, y_pred)
        # Subset accuracy (exact match)
        subset_accuracy = accuracy_score(y_test, y_pred)

        print(f"\nHamming Loss: {hamming:.4f} (lower is better)")
        print(f"Subset Accuracy (exact match): {subset_accuracy:.4f}")
        print("\nPer-Label Classification Report:")

        # Print classification report for each label
        for i, label_name in enumerate(self.label_list):
            y_test_label = y_test[:, i]
            y_pred_label = y_pred[:, i]

            # Check if both classes are present
            unique_classes = sorted(set(y_test_label) | set(y_pred_label))

            if len(unique_classes) == 1:
                # Only one class present, skip detailed report
                print(f"\n--- Label: {label_name} ---")
                print(
                    f"  All samples predicted as: {'Present' if unique_classes[0] == 1 else 'Not Present'}"
                )
                print(f"  Accuracy: {accuracy_score(y_test_label, y_pred_label):.4f}")
            else:
                # Both classes present, print full report
                print(f"\n--- Label: {label_name} ---")
                print(
                    classification_report(
                        y_test_label,
                        y_pred_label,
                        target_names=["Not " + label_name, label_name],
                        labels=[0, 1],
                        zero_division=0,
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
        X = self.vectorizer.transform(texts)

        # Predict (returns binary matrix for multi-label)
        # prediction_binary = self.model.predict(X)[0]
        probabilities = self.model.predict_proba(X)  # List of arrays, one per label

        # Calculate probabilities for all labels
        all_probs = {}
        label_prob_pairs = []
        for i, label_name in enumerate(self.label_list):
            # Get probability for this label being present
            # probabilities[i] is shape (1, 2) for binary classification
            # [0][1] is probability of label being present, [0][0] is probability of not present
            prob_array = probabilities[i]
            if prob_array.shape[1] > 1:
                label_prob = float(
                    prob_array[0][1]
                )  # Probability of label being present
            else:
                label_prob = float(prob_array[0][0])
            all_probs[label_name] = label_prob
            label_prob_pairs.append((label_name, label_prob))

        # Sort by probability (descending) and get top 3 labels
        label_prob_pairs.sort(key=lambda x: x[1], reverse=True)
        top_labels = [
            label
            for label, prob in label_prob_pairs[:3]
            if prob > self.prediction_threshold
        ]

        return {
            "labels": top_labels,
            "all_probabilities": all_probs,
        }

    def save(self):
        """Save the trained model"""
        os.makedirs(os.path.dirname(self.model_path), exist_ok=True)
        model_data = {
            "model": self.model,
            "vectorizer": self.vectorizer,
            "label_binarizer": self.label_binarizer,
            "label_list": self.label_list,
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

        # Handle backward compatibility with old models
        if "label_binarizer" in model_data:
            self.label_binarizer = model_data["label_binarizer"]
            self.label_list = model_data["label_list"]
        else:
            # Old format - convert to new format
            self.label_encoder = model_data.get("label_encoder", {})
            self.reverse_label_encoder = model_data.get("reverse_label_encoder", {})
            self.label_list = sorted(self.reverse_label_encoder.values())
            # Create a new binarizer (will need retraining for multi-label)
            self.label_binarizer = MultiLabelBinarizer()
            print(
                "Warning: Old model format detected. Multi-label support may be limited."
            )

        self.is_trained = True
        print(f"Model loaded from {self.model_path}")
