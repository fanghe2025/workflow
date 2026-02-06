"""
ML API Server for Email Labeling

FastAPI server that provides prediction endpoints for the trained email labeling model.
"""

import os
import sys
import json
from pathlib import Path
from typing import List, Optional, Dict, Any
from fastapi import FastAPI, HTTPException, status
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel, Field
import logging

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from ml_training.train_model import EmailLabelingModel

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

app = FastAPI(
    title="Email Labeling ML API",
    description="API server for email labeling predictions using trained ML model",
    version="1.0.0",
)

# Configure CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

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


# Pydantic models for request/response validation
class Attachment(BaseModel):
    id: Optional[str] = None
    name: Optional[str] = None
    contentType: Optional[str] = None
    size: Optional[int] = None
    file_path: Optional[str] = None
    text_content: Optional[str] = None


class EmailRequest(BaseModel):
    subject: Optional[str] = Field(default="", description="Email subject")
    body: Optional[str] = Field(default="", description="Email body content")
    from_: Optional[str] = Field(default="", alias="from", description="Sender email address")
    hasAttachments: Optional[bool] = Field(default=False, description="Whether email has attachments")
    attachments: Optional[List[Attachment]] = Field(default_factory=list, description="Email attachments")
    importance: Optional[str] = Field(default="normal", description="Email importance level")
    id: Optional[str] = Field(default=None, description="Email ID")

    class Config:
        populate_by_name = True


class PredictionResponse(BaseModel):
    label: str = Field(description="Predicted label")
    confidence: float = Field(description="Prediction confidence score")
    all_probabilities: Dict[str, float] = Field(description="Probabilities for all labels")


class BatchEmailRequest(BaseModel):
    emails: List[EmailRequest] = Field(description="List of emails to predict")


class BatchPredictionItem(BaseModel):
    email_id: Optional[str] = None
    label: Optional[str] = None
    confidence: Optional[float] = None
    all_probabilities: Optional[Dict[str, float]] = None
    error: Optional[str] = None


class BatchPredictionResponse(BaseModel):
    predictions: List[BatchPredictionItem] = Field(description="Predictions for all emails")


class HealthResponse(BaseModel):
    status: str = Field(description="Server status")
    model_loaded: bool = Field(description="Whether model is loaded and trained")


class ModelInfoResponse(BaseModel):
    is_trained: bool = Field(description="Whether model is trained")
    labels: List[str] = Field(description="Available labels")
    model_path: str = Field(description="Path to model file")


class ErrorResponse(BaseModel):
    error: str = Field(description="Error message")


@app.get("/health", response_model=HealthResponse, tags=["Health"])
async def health():
    """Health check endpoint"""
    return HealthResponse(
        status="healthy",
        model_loaded=model is not None and model.is_trained
    )


@app.post("/api/predict", response_model=PredictionResponse, tags=["Predictions"])
async def predict(email: EmailRequest):
    """Predict label for an email"""
    if model is None or not model.is_trained:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Model not loaded or not trained"
        )

    try:
        # Validate required fields
        if not email.subject and not email.body:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail="Email must have at least subject or body"
            )

        # Convert Pydantic model to dict for model.predict()
        email_dict = email.model_dump(by_alias=True, exclude_none=True)
        # Ensure 'from' key is present (not 'from_')
        if "from_" in email_dict:
            email_dict["from"] = email_dict.pop("from_")

        # Predict
        prediction = model.predict(email_dict)

        return PredictionResponse(**prediction)

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error during prediction: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@app.post("/api/predict/batch", response_model=BatchPredictionResponse, tags=["Predictions"])
async def predict_batch(batch_request: BatchEmailRequest):
    """Predict labels for multiple emails"""
    if model is None or not model.is_trained:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Model not loaded or not trained"
        )

    try:
        predictions = []
        for email in batch_request.emails:
            try:
                # Convert Pydantic model to dict
                email_dict = email.model_dump(by_alias=True, exclude_none=True)
                if "from_" in email_dict:
                    email_dict["from"] = email_dict.pop("from_")

                prediction = model.predict(email_dict)
                predictions.append(
                    BatchPredictionItem(
                        email_id=email.id,
                        **prediction
                    )
                )
            except Exception as e:
                logger.warning(
                    f"Error predicting for email {email.id or 'unknown'}: {e}"
                )
                predictions.append(
                    BatchPredictionItem(
                        email_id=email.id,
                        error=str(e)
                    )
                )

        return BatchPredictionResponse(predictions=predictions)

    except Exception as e:
        logger.error(f"Error during batch prediction: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@app.get("/api/model/info", response_model=ModelInfoResponse, tags=["Model"])
async def model_info():
    """Get information about the loaded model"""
    if model is None or not model.is_trained:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Model not loaded or not trained"
        )

    return ModelInfoResponse(
        is_trained=model.is_trained,
        labels=list(model.label_encoder.keys()) if model.label_encoder else [],
        model_path=model.model_path,
    )


@app.on_event("startup")
async def startup_event():
    """Load model on startup"""
    logger.info("Starting ML API server...")
    if not load_model():
        logger.error("Failed to load model. Server started but model unavailable.")


if __name__ == "__main__":
    import uvicorn
    
    # Load model before starting server
    logger.info("Starting ML API server...")
    if load_model():
        port = int(os.environ.get("PORT", 5000))
        logger.info(f"Server starting on port {port}")
        uvicorn.run(app, host="0.0.0.0", port=port, log_level="info")
    else:
        logger.error("Failed to load model. Server not started.")
        sys.exit(1)
