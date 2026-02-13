"""
Email Labeling Model Training Script

This script trains a machine learning model to classify emails based on
their content, subject, sender, attachments, and other features.
"""

import os
import sys
import re
from pathlib import Path
from typing import List, Dict, Any
import numpy as np
from scipy.sparse import hstack, csr_matrix
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.model_selection import train_test_split, KFold
from sklearn.preprocessing import MultiLabelBinarizer, LabelEncoder
from sklearn.multiclass import OneVsRestClassifier
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (
    accuracy_score,
    classification_report,
    hamming_loss,
    f1_score,
    precision_score,
    recall_score,
)
import joblib

# Try to import NLTK for better text preprocessing
try:
    import nltk
    from nltk.stem import PorterStemmer, WordNetLemmatizer
    from nltk.corpus import stopwords
    NLTK_AVAILABLE = True
    try:
        nltk.data.find('tokenizers/punkt')
        nltk.data.find('corpora/stopwords')
        nltk.data.find('corpora/wordnet')
    except LookupError:
        # Download required NLTK data
        try:
            nltk.download('punkt', quiet=True)
            nltk.download('stopwords', quiet=True)
            nltk.download('wordnet', quiet=True)
        except:
            NLTK_AVAILABLE = False
except ImportError:
    NLTK_AVAILABLE = False

# Try to import XGBoost and LightGBM for better performance
try:
    import xgboost as xgb
    XGBOOST_AVAILABLE = True
except ImportError:
    XGBOOST_AVAILABLE = False

try:
    import lightgbm as lgb
    LIGHTGBM_AVAILABLE = True
except ImportError:
    LIGHTGBM_AVAILABLE = False

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
        
        # Improved vectorizers with better settings
        vectorizer_config = self.config.get("vectorizer", {})
        
        # Main vectorizer for combined text
        self.vectorizer = TfidfVectorizer(
            max_features=vectorizer_config.get("max_features", 20000),  # Increased to 20000
            ngram_range=tuple(vectorizer_config.get("ngram_range", [1, 3])),  # Extended to trigrams
            stop_words="english",
            min_df=vectorizer_config.get("min_df", 2),
            max_df=vectorizer_config.get("max_df", 0.95),
            sublinear_tf=True,  # Apply sublinear TF scaling
            norm="l2",  # L2 normalization
            analyzer='word',
        )
        
        # Separate vectorizer for subject (often more important)
        self.subject_vectorizer = TfidfVectorizer(
            max_features=vectorizer_config.get("subject_max_features", 5000),
            ngram_range=(1, 3),
            stop_words="english",
            min_df=1,
            max_df=0.95,
            sublinear_tf=True,
            norm="l2",
        )
        
        # Initialize text preprocessing
        self.stemmer = PorterStemmer() if NLTK_AVAILABLE else None
        self.lemmatizer = WordNetLemmatizer() if NLTK_AVAILABLE else None
        self.stop_words = set(stopwords.words('english')) if NLTK_AVAILABLE else set()

        model_config = self.config.get("model", {})
        model_type = model_config.get("type", "xgboost" if XGBOOST_AVAILABLE else "lightgbm" if LIGHTGBM_AVAILABLE else "random_forest").lower()
        
        # Create base classifier based on config
        base_classifier = self._create_base_classifier(model_type, model_config)
        
        # Using OneVsRestClassifier for multi-label classification
        self.model = OneVsRestClassifier(base_classifier, n_jobs=-1)
        
        # Prediction threshold for multi-label classification
        self.prediction_threshold = self.config.get("prediction", {}).get("threshold", 0.3)
        
        self.label_encoder = {}
        self.reverse_label_encoder = {}
        self.domain_encoder = LabelEncoder()
        self.is_trained = False
        self.attachment_processor = (
            AttachmentProcessor()
            if self.config.get("attachment_processing", {}).get("enabled", True)
            else None
        )
    
    def _create_base_classifier(self, model_type: str, model_config: Dict[str, Any]):
        """Create the base classifier based on model type"""
        random_state = model_config.get("random_state", 42)
        
        if model_type == "xgboost" and XGBOOST_AVAILABLE:
            return xgb.XGBClassifier(
                n_estimators=model_config.get("n_estimators", 300),  # Increased
                max_depth=model_config.get("max_depth", 8),  # Increased
                learning_rate=model_config.get("learning_rate", 0.05),  # Lower for better convergence
                subsample=model_config.get("subsample", 0.8),
                colsample_bytree=model_config.get("colsample_bytree", 0.8),
                min_child_weight=model_config.get("min_child_weight", 3),
                gamma=model_config.get("gamma", 0.1),
                reg_alpha=model_config.get("reg_alpha", 0.1),
                reg_lambda=model_config.get("reg_lambda", 1.0),
                random_state=random_state,
                n_jobs=-1,
                eval_metric="mlogloss",
                tree_method="hist",  # Faster training
            )
        elif model_type == "lightgbm" and LIGHTGBM_AVAILABLE:
            return lgb.LGBMClassifier(
                n_estimators=model_config.get("n_estimators", 300),  # Increased
                max_depth=model_config.get("max_depth", 8),  # Increased
                learning_rate=model_config.get("learning_rate", 0.05),  # Lower for better convergence
                subsample=model_config.get("subsample", 0.8),
                colsample_bytree=model_config.get("colsample_bytree", 0.8),
                min_child_samples=model_config.get("min_child_samples", 20),
                reg_alpha=model_config.get("reg_alpha", 0.1),
                reg_lambda=model_config.get("reg_lambda", 1.0),
                random_state=random_state,
                n_jobs=-1,
                verbose=-1,
                class_weight='balanced',  # Handle imbalanced classes
            )
        else:
            # Default to RandomForest with improved parameters
            return RandomForestClassifier(
                n_estimators=model_config.get("n_estimators", 200),  # Increased from 100
                max_depth=model_config.get("max_depth", None),  # None allows full depth
                min_samples_split=model_config.get("min_samples_split", 5),
                min_samples_leaf=model_config.get("min_samples_leaf", 2),
                max_features=model_config.get("max_features", "sqrt"),
                random_state=random_state,
                n_jobs=-1,
            )

    def _preprocess_text(self, text: str, use_stemming: bool = False) -> str:
        """Clean and preprocess text for better feature extraction"""
        if not text:
            return ""
        
        # Convert to lowercase
        text = text.lower()
        
        # Remove URLs - simplified and more robust pattern
        text = re.sub(r'https?://\S+', ' ', text)
        
        # Remove email addresses
        text = re.sub(r'\S+@\S+', ' ', text)
        
        # Remove special characters but keep spaces and basic punctuation
        text = re.sub(r'[^\w\s]', ' ', text)
        
        # Tokenize and process if NLTK is available
        if NLTK_AVAILABLE and (self.stemmer or self.lemmatizer):
            try:
                from nltk.tokenize import word_tokenize
                tokens = word_tokenize(text)
                
                # Remove stopwords and process
                processed_tokens = []
                for token in tokens:
                    if token not in self.stop_words and len(token) > 2:
                        if use_stemming and self.stemmer:
                            token = self.stemmer.stem(token)
                        elif self.lemmatizer:
                            token = self.lemmatizer.lemmatize(token)
                        processed_tokens.append(token)
                
                text = ' '.join(processed_tokens)
            except:
                # Fallback to simple processing
                pass
        
        # Remove extra whitespace
        text = re.sub(r'\s+', ' ', text)
        
        return text.strip()

    def prepare_text_features(self, emails: List[Dict[str, Any]], return_separate: bool = False) -> List[str]:
        """Combine all text content from email and attachments with improved preprocessing"""
        texts = []
        subjects = []

        for email in emails:
            # Get and preprocess text components
            subject = self._preprocess_text(str(email.get("Subject", "")), use_stemming=False)
            body = self._preprocess_text(str(email.get("Message", "")), use_stemming=False)
            sender = self._preprocess_text(str(email.get("Sender", "")))
            
            # Store subject separately for separate vectorization
            subjects.append(subject if subject else "")
            
            # Separate subject and body for better feature extraction
            # Subject is often more important, so we weight it
            text_parts = []
            
            # Add subject multiple times to give it more weight
            if subject:
                text_parts.extend([subject] * 3)  # Weight subject 3x
            
            # Add body
            if body:
                text_parts.append(body)
            
            # Add sender domain (extracted separately)
            if sender and "@" in sender:
                domain = sender.split("@")[-1]
                text_parts.append(domain)
            
            # Add attachment names
            attachment_names = email.get("attachments", [])
            if attachment_names:
                # Extract file extensions and names
                attachment_text = " ".join([str(name) for name in attachment_names])
                text_parts.append(attachment_text)

            # Add attachment text if available
            if self.attachment_processor and email.get("attachment_texts"):
                attachment_texts = email.get("attachment_texts", [])
                if attachment_texts:
                    combined_attachment_text = "\n\n".join(attachment_texts)
                    text_parts.append(self._preprocess_text(combined_attachment_text))

            # Combine all text
            full_text = " ".join(text_parts)
            texts.append(full_text)

        if return_separate:
            return texts, subjects
        return texts

    def prepare_additional_features(self, emails: List[Dict[str, Any]], fit: bool = False) -> np.ndarray:
        """Extract additional non-text features with improved engineering"""
        features = []
        domains = []

        for email in emails:
            # Extract domain from sender
            from_email = str(email.get("Sender", ""))
            domain = from_email.split("@")[-1] if "@" in from_email else "unknown"
            domains.append(domain)

            # Text length features
            subject = str(email.get("Subject", ""))
            body = str(email.get("Message", ""))
            subject_length = len(subject)
            body_length = len(body)
            total_text_length = subject_length + body_length
            
            # Word counts
            subject_word_count = len(subject.split())
            body_word_count = len(body.split())
            total_word_count = subject_word_count + body_word_count

            # Count attachments
            attachments = email.get("attachments", [])
            num_attachments = len(attachments)
            has_attachments = 1 if num_attachments > 0 else 0

            # Attachment features
            attachment_text_length = 0
            attachment_file_extensions = set()
            if email.get("attachment_texts"):
                attachment_text_length = sum(
                    len(text) for text in email.get("attachment_texts", [])
                )
            
            # Extract file extensions from attachment names
            for att in attachments:
                if isinstance(att, str):
                    if "." in att:
                        ext = att.split(".")[-1].lower()
                        attachment_file_extensions.add(ext)
                elif isinstance(att, dict) and "name" in att:
                    name = att["name"]
                    if "." in name:
                        ext = name.split(".")[-1].lower()
                        attachment_file_extensions.add(ext)
            
            num_unique_extensions = len(attachment_file_extensions)
            has_pdf = 1 if "pdf" in attachment_file_extensions else 0
            has_doc = 1 if any(ext in attachment_file_extensions for ext in ["doc", "docx"]) else 0
            has_excel = 1 if any(ext in attachment_file_extensions for ext in ["xls", "xlsx"]) else 0

            # Importance
            importance = email.get("importance", "normal")
            is_high_importance = 1 if importance == "high" else 0

            # Email structure features
            has_exclamation = 1 if "!" in subject else 0
            has_question = 1 if "?" in subject else 0
            has_urgent_keywords = 1 if any(
                word in subject.lower() or word in body.lower()
                for word in ["urgent", "asap", "immediately", "important"]
            ) else 0

            # Feature vector
            feat = [
                is_high_importance,
                has_attachments,
                num_attachments,
                num_unique_extensions,
                has_pdf,
                has_doc,
                has_excel,
                attachment_text_length,
                subject_length,
                body_length,
                total_text_length,
                subject_word_count,
                body_word_count,
                total_word_count,
                has_exclamation,
                has_question,
                has_urgent_keywords,
            ]
            features.append(feat)

        # Encode domains if fitting
        if fit:
            self.domain_encoder.fit(domains)
        
        # Encode domains
        try:
            encoded_domains = self.domain_encoder.transform(domains).reshape(-1, 1)
        except:
            # If domain not seen during training, use -1
            encoded_domains = np.array([[-1] if d not in self.domain_encoder.classes_ else self.domain_encoder.transform([d])[0] for d in domains]).reshape(-1, 1)
        
        # Combine features
        feature_array = np.array(features)
        combined_features = np.hstack([feature_array, encoded_domains])
        
        return combined_features

    def train(self, labeled_emails: List[Dict[str, Any]]):
        """Train the model on labeled email data"""
        if not labeled_emails:
            raise ValueError("No labeled emails provided for training")

        # Filter emails with labels
        emails = [e for e in labeled_emails if "Tags" in e]
        labels = [e["Tags"] for e in emails]

        if not emails:
            raise ValueError("No emails with labels found")

        print(f"Found {len(emails)} labeled emails for training")

        # Binarize labels for multi-label classification
        mlb = MultiLabelBinarizer()
        y = mlb.fit_transform(labels)
        print(f"Labels ({len(mlb.classes_)}): {mlb.classes_}")

        # Process attachments if necessary
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

        # Save the reverse label encoder for later use
        self.reverse_label_encoder = {i: label for i, label in enumerate(mlb.classes_)}
        self.label_encoder = {label: i for i, label in enumerate(mlb.classes_)}

        # Prepare text features
        print("Vectorizing text content...")
        texts, subjects = self.prepare_text_features(emails, return_separate=True)
        
        # Fit vectorizers
        X_text = self.vectorizer.fit_transform(texts)
        X_subject = self.subject_vectorizer.fit_transform(subjects)
        
        # Combine text features (weight subject more)
        X = hstack([X_text, X_subject * 2])  # Subject features weighted 2x

        # Split data into training and test sets
        training_config = self.config.get("training", {})
        test_size = training_config.get("test_size", 0.2)
        random_state = training_config.get("random_state", 42)
        use_cross_validation = training_config.get("use_cross_validation", False)
        cv_folds = training_config.get("cv_folds", 5)

        X_train, X_test, y_train, y_test = train_test_split(
            X, y, test_size=test_size, random_state=random_state
        )

        # Train model
        n_train_samples = (
            X_train.shape[0] if hasattr(X_train, "shape") else len(X_train)
        )
        print(f"\nTraining model on {n_train_samples} samples...")
        self.model.fit(X_train, y_train)

        # Cross-validation if enabled
        if use_cross_validation and n_train_samples > cv_folds:
            print(f"\nPerforming {cv_folds}-fold cross-validation...")
            # For multi-label, we'll use a simple KFold
            cv_scores = []
            kf = KFold(n_splits=cv_folds, shuffle=True, random_state=random_state)
            
            for train_idx, val_idx in kf.split(X_train):
                X_cv_train, X_cv_val = X_train[train_idx], X_train[val_idx]
                y_cv_train, y_cv_val = y_train[train_idx], y_train[val_idx]
                
                # Train on fold
                fold_model = OneVsRestClassifier(
                    self.model.estimator.__class__(**self.model.estimator.get_params())
                )
                fold_model.fit(X_cv_train, y_cv_train)
                
                # Evaluate
                y_cv_pred = fold_model.predict(X_cv_val)
                f1_macro = f1_score(y_cv_val, y_cv_pred, average='macro', zero_division=0)
                cv_scores.append(f1_macro)
            
            print(f"Cross-validation F1 (macro): {np.mean(cv_scores):.4f} (+/- {np.std(cv_scores) * 2:.4f})")

        # Evaluate the model
        print("\nEvaluating on test set...")
        y_pred = self.model.predict(X_test)
        
        # Calculate multiple metrics for multi-label classification
        accuracy = accuracy_score(y_test, y_pred)
        hamming = hamming_loss(y_test, y_pred)
        f1_macro = f1_score(y_test, y_pred, average='macro', zero_division=0)
        f1_micro = f1_score(y_test, y_pred, average='micro', zero_division=0)
        precision_macro = precision_score(y_test, y_pred, average='macro', zero_division=0)
        recall_macro = recall_score(y_test, y_pred, average='macro', zero_division=0)

        print(f"\nModel Performance Metrics:")
        print(f"  Accuracy: {accuracy:.4f}")
        print(f"  Hamming Loss: {hamming:.4f} (lower is better)")
        print(f"  F1 Score (macro): {f1_macro:.4f}")
        print(f"  F1 Score (micro): {f1_micro:.4f}")
        print(f"  Precision (macro): {precision_macro:.4f}")
        print(f"  Recall (macro): {recall_macro:.4f}")
        print("\nClassification Report:")
        print(classification_report(y_test, y_pred, target_names=mlb.classes_, zero_division=0))

        self.is_trained = True

        # Save model
        self.save()

    def predict(self, email: Dict[str, Any]) -> Dict[str, Any]:
        """Predict labels for a single email (multi-label)"""
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

        # Prepare text features
        texts, subjects = self.prepare_text_features([email], return_separate=True)
        
        # Transform with vectorizers
        X_text = self.vectorizer.transform(texts)
        X_subject = self.subject_vectorizer.transform(subjects)
        
        # Combine features
        X = hstack([X_text, X_subject * 2])  # Subject features weighted 2x

        # Predict probabilities
        y_proba = self.model.predict_proba(X)
        
        # Use threshold-based prediction for better multi-label classification
        # For OneVsRestClassifier, predict_proba returns a list of arrays (one per class)
        # Each array has shape (n_samples, 2) for binary classification
        if isinstance(y_proba, list):
            # Extract positive class probabilities for each label
            y_proba_array = np.array([prob[0, 1] if prob.shape[1] > 1 else prob[0, 0] for prob in y_proba])
        else:
            # If it's already an array (shouldn't happen with OneVsRestClassifier, but handle it)
            if y_proba.ndim == 2:
                y_proba_array = y_proba[0, 1:] if y_proba.shape[1] > 1 else y_proba[0, :]
            else:
                y_proba_array = y_proba[0] if y_proba.ndim > 0 else y_proba
        
        # Apply threshold
        y_pred_binary = (y_proba_array >= self.prediction_threshold).astype(int)
        
        # Also get standard predictions as fallback
        y_pred = self.model.predict(X)

        # Convert predictions to tags using threshold-based predictions
        predicted_labels = [
            self.reverse_label_encoder[i]
            for i in range(len(y_pred_binary))
            if y_pred_binary[i] == 1 and i in self.reverse_label_encoder and self.reverse_label_encoder[i] != "No label"
        ]
        
        # If no labels predicted, use standard prediction as fallback
        if not predicted_labels:
            predicted_labels = [
                self.reverse_label_encoder[i]
                for i in range(len(y_pred[0]))
                if y_pred[0][i] == 1 and i in self.reverse_label_encoder and self.reverse_label_encoder[i] != "No label"
            ]

        return predicted_labels

    def save(self):
        """Save the trained model"""
        os.makedirs(os.path.dirname(self.model_path), exist_ok=True)
        model_data = {
            "model": self.model,
            "vectorizer": self.vectorizer,
            "subject_vectorizer": self.subject_vectorizer,
            "label_encoder": self.label_encoder,
            "reverse_label_encoder": self.reverse_label_encoder,
            "domain_encoder": self.domain_encoder,
            "prediction_threshold": self.prediction_threshold,
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
        self.subject_vectorizer = model_data.get("subject_vectorizer", self.vectorizer)  # Fallback for old models
        self.label_encoder = model_data["label_encoder"]
        self.reverse_label_encoder = model_data["reverse_label_encoder"]
        self.domain_encoder = model_data.get("domain_encoder", LabelEncoder())
        self.prediction_threshold = model_data.get("prediction_threshold", 0.3)
        self.is_trained = True
        print(f"Model loaded from {self.model_path}")
