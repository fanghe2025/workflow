"""
LLM-based Email Tag Recommender

Uses OpenAI (or compatible API) to recommend tags for emails based on content.
Supports two modes: chat completions (gpt-4o-mini).
"""

import json
import logging
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

from utils.db import get_all_tags
from utils.sanitize import hash_email, hash_emails, replace_pii_in_text

logger = logging.getLogger(__name__)


SYSTEM_CONTENT = (
    "You are an email tagging classifier. "
    "Choose 0 to 4 tags from ALLOWED_TAGS. "
    "If none apply, return an empty list. "
    'Output ONLY valid JSON like: {"tags": ["tagA", "tagB"]}.'
)


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
        self._model = model
        self._api_key = api_key
        self._client = None
        self._all_tags = None

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
                    "content": SYSTEM_CONTENT,
                },
                {
                    "role": "user",
                    "content": f"ALLOWED_TAGS: {self._all_tags}\n\n{user_content}",
                },
                {
                    "role": "assistant",
                    "content": json.dumps({"tags": email["Tags"]}, ensure_ascii=False),
                },
            ]
        }

    def _write_train_data(self, emails: List[Dict[str, Any]], path: str):
        """Write jsonl file for train data"""
        self._all_tags = get_all_tags(emails)
        out_path = Path(path)
        with open(out_path, "w", encoding="utf-8") as f:
            for email in emails:
                ex = self._email_to_finetune_example(email)
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
        print(f"Deleted fine tune file: {file_id}")

    def _start_job(self, file_id):
        client = self._get_client()
        job = client.fine_tuning.jobs.create(
            model=self._model,
            training_file=file_id,
            suffix="email-tags",
        )
        print(f"Fine-tuning job created: {job.id}")
        print(f"  Status: {job.status}")
        print(f"  Monitor: https://platform.openai.com/fine_tuning/jobs/{job.id}")

    def _get_job(self, job_id):
        client = self._get_client()
        job = client.fine_tuning.jobs.retrieve(job_id)

        print("Fine-tune job ------------------------------")
        print(f"  ID: {job.id}")
        print(f"  Status: {job.status}")
        print(f"  Model: {job.fine_tuned_model}")
        if job.error:
            print(f"  Error: {job.error.message}")

        return job

    def _cancel_job(self, job_id):
        job = self._get_job(job_id)
        if job.status in ["queued", "running"]:
            client = self._get_client()
            client.fine_tuning.jobs.cancel(job.id)
            print(f"Canceled Fine-tune job: {job.id}")
        else:
            print(f"Cannot cancel. Job status: {job.status}")

    def predict(self, email: Dict[str, Any]) -> Dict[str, Any]:
        """
        Recommend tags for an email.

        Args:
            email: Dict with Subject, Message, Sender, attachments, OtherRecipients

        Returns:
            Dict with keys:
                - labels: List of recommended tag strings
                - all_probabilities: Dict mapping each tag to score (similarity or 1.0)
                - confidence: 1.0 (chat)
        """

        email_text = self._build_email_text(email)

        client = self._get_client()
        response = client.responses.create(
            model=self._model,
            input=[
                {
                    "role": "system",
                    "content": SYSTEM_CONTENT,
                },
                {
                    "role": "user",
                    "content": f"ALLOWED_TAGS: {self._all_tags}\n\n{email_text}",
                },
            ],
            text={
                "format": {
                    "type": "json_schema",
                    "name": "email_tags",
                    "schema": {
                        "type": "object",
                        "properties": {
                            "tags": {
                                "type": "array",
                                "items": {"type": "string", "enum": self._all_tags},
                                "maxItems": 4,
                            }
                        },
                        "required": ["tags"],
                        "additionalProperties": False,
                    },
                }
            },
            temperature=0,
        )

        # Parse and return the tags from the model's output
        data = json.loads(response.output_text)
        return data["tags"]

    def predict_batch(self, emails: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """Predict tags for multiple emails."""
        return [self.predict(e) for e in emails]
