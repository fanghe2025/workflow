"""
ML API Server for Email Labeling

Flask API server that provides prediction endpoints for the trained email labeling model.
"""

import os
import sys
import json
from pathlib import Path
from flask import Flask, request, jsonify
from flask_cors import CORS
import logging

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from ml_training.train_model import EmailLabelingModel

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = Flask(__name__)
CORS(app)

# Global model instance
model = None


def load_model():
    """Load the trained model"""
    global model
    try:
        # Load config to get model path
        config_path = Path("config/training_config.json")
        if config_path.exists():
            with open(config_path, "r") as f:
                config = json.load(f)
            model_path = config.get("paths", {}).get(
                "model_output", "models/email_classifier.pkl"
            )
        else:
            model_path = "models/email_classifier.pkl"

        if not os.path.exists(model_path):
            logger.warning(f"Model file not found: {model_path}")
            return False

        model = EmailLabelingModel(
            model_path=model_path, config=config if config_path.exists() else {}
        )
        model.load()
        logger.info("Model loaded successfully")
        return True
    except Exception as e:
        logger.error(f"Error loading model: {e}")
        return False


@app.route("/health", methods=["GET"])
def health():
    """Health check endpoint"""
    return jsonify(
        {"status": "healthy", "model_loaded": model is not None and model.is_trained}
    )


@app.route("/api/predict", methods=["POST"])
def predict():
    """Predict label for an email"""
    if model is None or not model.is_trained:
        return jsonify({"error": "Model not loaded or not trained"}), 503

    try:
        data = request.get_json()
        if not data:
            return jsonify({"error": "No JSON data provided"}), 400

        # Validate required fields
        if "subject" not in data and "body" not in data:
            return jsonify({"error": "Email must have at least subject or body"}), 400

        # Predict
        prediction = model.predict(data)

        return jsonify(prediction)

    except Exception as e:
        logger.error(f"Error during prediction: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/predict/batch", methods=["POST"])
def predict_batch():
    """Predict labels for multiple emails"""
    if model is None or not model.is_trained:
        return jsonify({"error": "Model not loaded or not trained"}), 503

    try:
        data = request.get_json()
        if not data or "emails" not in data:
            return jsonify({"error": "No emails array provided"}), 400

        emails = data["emails"]
        if not isinstance(emails, list):
            return jsonify({"error": "emails must be an array"}), 400

        predictions = []
        for email in emails:
            try:
                prediction = model.predict(email)
                predictions.append(
                    {"email_id": email.get("id", "unknown"), **prediction}
                )
            except Exception as e:
                logger.warning(
                    f"Error predicting for email {email.get('id', 'unknown')}: {e}"
                )
                predictions.append(
                    {"email_id": email.get("id", "unknown"), "error": str(e)}
                )

        return jsonify({"predictions": predictions})

    except Exception as e:
        logger.error(f"Error during batch prediction: {e}")
        return jsonify({"error": str(e)}), 500


@app.route("/api/model/info", methods=["GET"])
def model_info():
    """Get information about the loaded model"""
    if model is None or not model.is_trained:
        return jsonify({"error": "Model not loaded or not trained"}), 503

    return jsonify(
        {
            "is_trained": model.is_trained,
            "labels": list(model.label_encoder.keys()) if model.label_encoder else [],
            "model_path": model.model_path,
        }
    )


if __name__ == "__main__":
    # Load model on startup
    logger.info("Starting ML API server...")
    if load_model():
        port = int(os.environ.get("PORT", 5000))
        logger.info(f"Server starting on port {port}")
        app.run(host="0.0.0.0", port=port, debug=False)
    else:
        logger.error("Failed to load model. Server not started.")
        sys.exit(1)
