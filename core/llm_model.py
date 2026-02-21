"""
LLM-based Email Tag Recommender

Uses OpenAI (or compatible API) to recommend tags for emails based on content.
Supports two modes: chat completions (gpt-4o-mini) or embeddings (text-embedding-3-small).
"""

import json
import logging
import os
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

import numpy as np

logger = logging.getLogger(__name__)


def load_known_tags(data_path: Optional[str] = None) -> List[str]:
    """Load known tags from labeled_emails.json if it exists."""
    paths = []
    if data_path:
        paths.append(Path(data_path))
    paths.extend([
        Path("data/labeled_emails.json"),
        Path(__file__).parent.parent / "data" / "labeled_emails.json",
    ])
    for path in paths:
        if path.exists():
            try:
                with open(path, encoding="utf-8") as f:
                    data = json.load(f)
                labels = {
                    e.get("label") for e in data
                    if isinstance(e, dict) and e.get("label")
                }
                labels.discard(None)
                return sorted(labels)
            except (json.JSONDecodeError, KeyError) as e:
                logger.debug("Could not load tags from %s: %s", path, e)
    return []


class LLMTagModel:
    """
    LLM-based model for recommending email tags.
    Uses OpenAI API; no training required.
    """

    def __init__(
        self,
        model: str = "gpt-4o-mini",
        embedding_model: str = "text-embedding-3-small",
        max_tags: int = 5,
        known_tags: Optional[List[str]] = None,
        api_key: Optional[str] = None,
        config: Optional[Dict[str, Any]] = None,
        use_embeddings: bool = True,
    ):
        """
        Args:
            model: OpenAI chat model name (used when use_embeddings=False).
            embedding_model: OpenAI embedding model (used when use_embeddings=True).
            max_tags: Maximum number of tags to return.
            known_tags: If provided, constrain suggestions to these tags only.
                       Required for embedding mode.
            api_key: OpenAI API key; defaults to OPENAI_API_KEY env.
            config: Optional config dict; may override model, max_tags, etc.
            use_embeddings: If True, use text-embedding-3-small for similarity-based
                           tag recommendation. If False, use chat completions.
        """
        self.config = config or {}
        llm_config = self.config.get("llm", {})
        self.model = llm_config.get("model", model)
        self.embedding_model = llm_config.get(
            "embedding_model", embedding_model
        )
        self.max_tags = llm_config.get("max_tags", max_tags)
        self.known_tags = known_tags or llm_config.get("known_tags")
        self.use_embeddings = llm_config.get("use_embeddings", use_embeddings)
        self._api_key = api_key or os.environ.get("OPENAI_API_KEY")
        self._client = None
        self._tag_embeddings: Optional[Tuple[List[str], np.ndarray]] = None

    def _get_client(self):
        """Lazy-load OpenAI client."""
        if self._client is None:
            try:
                from openai import OpenAI
            except ImportError as e:
                raise ImportError(
                    "openai package required. Run: pip install openai"
                ) from e
            if not self._api_key:
                raise ValueError(
                    "OPENAI_API_KEY not set. Add it to your environment or .env."
                )
            self._client = OpenAI(api_key=self._api_key)
        return self._client

    def _embed(self, text: str) -> np.ndarray:
        """Get embedding vector for text using OpenAI embeddings API."""
        client = self._get_client()
        response = client.embeddings.create(
            model=self.embedding_model,
            input=text,
        )
        return np.array(response.data[0].embedding, dtype=np.float32)

    def _embed_batch(self, texts: List[str]) -> np.ndarray:
        """Get embedding vectors for multiple texts."""
        if not texts:
            return np.zeros((0, 0), dtype=np.float32)
        client = self._get_client()
        response = client.embeddings.create(
            model=self.embedding_model,
            input=texts,
        )
        # API returns in request order
        by_index = {d.index: d.embedding for d in response.data}
        return np.array([by_index[i] for i in range(len(texts))], dtype=np.float32)

    def _get_tag_embeddings(self) -> Tuple[List[str], np.ndarray]:
        """Get or compute embeddings for known tags. Uses 'Email category: {tag}' as text."""
        if self._tag_embeddings is not None:
            return self._tag_embeddings
        if not self.known_tags:
            return [], np.zeros((0, 0), dtype=np.float32)
        tag_texts = [f"Email category: {tag}" for tag in self.known_tags]
        embeddings = self._embed_batch(tag_texts)
        self._tag_embeddings = (self.known_tags, embeddings)
        return self._tag_embeddings

    @staticmethod
    def _cosine_similarity(a: np.ndarray, b: np.ndarray) -> float:
        """Cosine similarity between two vectors."""
        norm_a = np.linalg.norm(a)
        norm_b = np.linalg.norm(b)
        if norm_a == 0 or norm_b == 0:
            return 0.0
        return float(np.dot(a, b) / (norm_a * norm_b))

    def _predict_embedding(self, email: Dict[str, Any]) -> Dict[str, Any]:
        """Predict tags using embedding similarity (requires known_tags)."""
        email_text = self._build_email_text(email)
        if not email_text.strip():
            return {"labels": [], "all_probabilities": {}, "confidence": 0.0}

        tags, tag_embeds = self._get_tag_embeddings()
        if not tags:
            logger.warning(
                "Embedding mode requires known_tags; falling back to empty prediction"
            )
            return {"labels": [], "all_probabilities": {}, "confidence": 0.0}

        email_embed = self._embed(email_text)
        similarities = [
            (tag, self._cosine_similarity(email_embed, tag_embeds[i]))
            for i, tag in enumerate(tags)
        ]
        similarities.sort(key=lambda x: x[1], reverse=True)

        top = similarities[: self.max_tags]
        labels = [t[0] for t in top]
        all_probs = {t[0]: max(0.0, t[1]) for t in top}
        confidence = float(top[0][1]) if top else 0.0

        return {
            "labels": labels,
            "all_probabilities": all_probs,
            "confidence": confidence,
        }

    def _build_email_text(self, email: Dict[str, Any]) -> str:
        """Build plain text from email dict for the prompt."""
        parts = []
        subject = email.get("Subject", email.get("subject", ""))
        body = email.get("Message", email.get("body", ""))
        sender = email.get("Sender", email.get("from", ""))
        if subject:
            parts.append(f"Subject: {subject}")
        if sender:
            parts.append(f"From: {sender}")
        recipients = email.get("OtherRecipients", [])
        if recipients:
            parts.append(f"To/CC: {', '.join(recipients)}")
        attachments = email.get("attachments", [])
        if attachments:
            names = [a.get("name", a) if isinstance(a, dict) else a for a in attachments]
            parts.append(f"Attachments: {', '.join(str(n) for n in names)}")
        if body:
            parts.append(f"Body:\n{body}")
        return "\n\n".join(parts) if parts else ""

    def predict(self, email: Dict[str, Any]) -> Dict[str, Any]:
        """
        Recommend tags for an email.

        Args:
            email: Dict with Subject, Message, Sender, attachments, OtherRecipients
                   (or subject, body, from). At least subject or body should be set.

        Returns:
            Dict with keys:
                - labels: List of recommended tag strings
                - all_probabilities: Dict mapping each tag to score (similarity or 1.0)
                - confidence: Similarity of top tag (embedding) or 1.0 (chat)
        """
        if self.use_embeddings and self.known_tags:
            return self._predict_embedding(email)
        # Chat mode (or embedding mode without known_tags)

        email_text = self._build_email_text(email)
        if not email_text.strip():
            return {
                "labels": [],
                "all_probabilities": {},
                "confidence": 0.0,
            }

        if self.known_tags:
            tags_instruction = (
                f"Choose ONLY from these tags (comma-separated, no others): "
                f"{', '.join(self.known_tags)}"
            )
        else:
            tags_instruction = (
                "Suggest 1–5 short, lowercase tags (e.g. meeting, invoice, urgent). "
                "Return ONLY a comma-separated list of tags, no explanation."
            )

        system_prompt = (
            "You recommend tags/categories for emails based on their content. "
            "Be concise and practical."
        )
        user_prompt = f"Recommend tags for this email:\n\n{email_text}\n\n{tags_instruction}"

        client = self._get_client()
        response = client.chat.completions.create(
            model=self.model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.2,
        )

        raw = (response.choices[0].message.content or "").strip()
        tags = [t.strip() for t in raw.split(",") if t.strip()][: self.max_tags]
        all_probs = {tag: 1.0 for tag in tags}

        return {
            "labels": tags,
            "all_probabilities": all_probs,
            "confidence": 1.0 if tags else 0.0,
        }

    def predict_batch(self, emails: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Predict tags for multiple emails."""
        return [self.predict(e) for e in emails]
