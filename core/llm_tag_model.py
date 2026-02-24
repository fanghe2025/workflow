"""
LLM-based Email Tag Recommender

Uses OpenAI (or compatible API) to recommend tags for emails based on content.
Supports two modes: chat completions (gpt-4o-mini).
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from utils.sanitize import hash_email, hash_emails, replace_pii_in_text

logger = logging.getLogger(__name__)


class LLMTagModel:
    """
    LLM-based model for recommending email tags.
    Uses OpenAI API; use fine-tune for training.
    """

    def __init__(
        self,
        api_key: str,
        model: str = "gpt-4o-mini-2024-07-18",
    ):
        """
        Args:
            model: OpenAI chat model name.
            api_key: OpenAI API key; defaults to OPENAI_API_KEY env.
        """
        self.model = model
        self._api_key = api_key
        self._client = None

    def _get_client(self):
        """Lazy-load OpenAI client."""
        if self._client is None:
            from openai import OpenAI

            if not self._api_key:
                raise ValueError(
                    "OPENAI_API_KEY not set. Add it to your environment or .env."
                )
            self._client = OpenAI(api_key=self._api_key)
        return self._client

    def _build_email_text(self, email: Dict[str, Any]) -> str:
        """Build plain text for fine-tuning input. Hashes email addresses."""
        parts = []
        parts.append(f"Subject: {replace_pii_in_text(email['Subject'])}")
        parts.append(f"From: {hash_email(email['Sender'])}")
        if email["OtherRecipients"]:
            recipient_hashes = hash_emails(email["OtherRecipients"])
            parts.append(f"To/CC: {', '.join(recipient_hashes)}")
        if email["attachments"]:
            parts.append(f"Attachments: {', '.join(email['attachments'])}")
        parts.append(f"Body:\n{email['Message']}")

        return "\n\n".join(parts) if parts else ""

    def _email_to_finetune_example(self, email: Dict[str, Any]):
        """Convert one email to OpenAI chat fine-tuning format."""
        user_content = self._build_email_text(email)
        return {
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are an email tagging classifier. "
                        "Choose 0 to 4 tags from the allowed list. "
                        "If none apply, return an empty list. "
                        'Output ONLY valid JSON like: {"tags": ["tagA", "tagB"]}.'
                    ),
                },
                {
                    "role": "user",
                    "content": f"Recommend tags for this email:\n\n{user_content}",
                },
                {
                    "role": "assistant",
                    "content": json.dumps({"tags": email["Tags"]}, ensure_ascii=False),
                },
            ]
        }

    def _write_train_data(self, emails: List[Dict[str, Any]], path: str):
        """Write jsonl file for train data"""
        out_path = Path(path)
        with open(out_path, "w", encoding="utf-8") as f:
            for e in emails:
                ex = self._email_to_finetune_example(e)
                f.write(json.dumps(ex, ensure_ascii=False) + "\n")

        print(f"Wrote {len(emails)} examples to {out_path}")

        return out_path

    def _upload_train_data(self, path):
        """Upload train data"""
        with open(path, "rb") as f:
            client = self._get_client()
            file_resp = client.files.create(file=f, purpose="fine-tune")
        file_id = file_resp.id

        print(f"Uploaded file: {file_id}")

        return file_id

    def _remove_train_data(self, file_id):
        client = self._get_client()
        client.files.delete(file_id)
        print(f"Delete train data: {file_id}")

    def _start_job(self, file_id):
        client = self._get_client()
        job = client.fine_tuning.jobs.create(
            model=self.model,
            training_file=file_id,
            suffix="email-tags",
        )
        print(f"Fine-tuning job created: {job.id}")
        print(f"  Status: {job.status}")
        print(f"  Monitor: https://platform.openai.com/fine_tuning/jobs/{job.id}")

    def _get_job(self, job_id):
        client = self._get_client()
        job = client.fine_tuning.jobs.retrieve(job_id)

        print(f"Fine-tune job >>> ID: {job.id},  Status: {job.status}")
        if job.error:
            print(f"Error: {job.error.message}")

        return job

    def _cancel_job(self, job_id):
        client = self._get_client()
        job = client.fine_tuning.jobs.cancel(job_id)

        print(f"Canceled Fine-tune job: {job.id}")

        return job

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
                - confidence: 1.0 (chat)
        """

        email_text = self._build_email_text(email)
        if not email_text.strip():
            return {
                "labels": [],
                "all_probabilities": {},
                "confidence": 0.0,
            }

        tags_instruction = (
            "Suggest 1–5 short, lowercase tags (e.g. meeting, invoice, urgent). "
            "Return ONLY a comma-separated list of tags, no explanation."
        )

        system_prompt = (
            "You recommend tags/categories for emails based on their content. "
            "Be concise and practical."
        )
        user_prompt = (
            f"Recommend tags for this email:\n\n{email_text}\n\n{tags_instruction}"
        )

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
        tags = [t.strip() for t in raw.split(",") if t.strip()]
        all_probs = {tag: 1.0 for tag in tags}

        return {
            "labels": tags,
            "all_probabilities": all_probs,
            "confidence": 1.0 if tags else 0.0,
        }

    def predict_batch(self, emails: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Predict tags for multiple emails."""
        return [self.predict(e) for e in emails]
