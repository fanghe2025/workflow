import argparse
import json
import os
import random
import sys

from pathlib import Path
from typing import List, Dict, Any, Optional

from dotenv import load_dotenv

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.constants import NO_LABEL
from core.email_labeling_model import EmailLabelingModel
from core.llm_tag_model import LLMTagModel
from utils.db import load_emails


load_dotenv()
api_key = os.getenv("OPENAI_API_KEY")
db_path = os.getenv("DUCKDB_PATH", "data/emails.duckdb")
fine_tune_file_id = os.getenv("FINE_TUNE_FILE_ID")
fine_tune_job_id = os.getenv("FINE_TUNE_JOB_ID")


def limit_samples_per_tag(
    emails: List[Dict[str, Any]], max_per_tag: int, random_state: Optional[int] = 42
) -> List[Dict[str, Any]]:
    """
    Limit training data to at most max_per_tag emails per tag.
    Emails can have multiple tags; each email is included if it's sampled for any tag.

    Args:
        emails: List of labeled email dicts (must have "Tags" key)
        max_per_tag: Maximum number of emails to use per tag
        random_state: Random seed for reproducible sampling

    Returns:
        Subset of emails
    """
    if max_per_tag is None or max_per_tag <= 0:
        return emails

    rng = random.Random(random_state)

    # Build tag -> emails mapping (by index to preserve uniqueness)
    tag_to_indices: Dict[str, set] = {}
    for i, email in enumerate(emails):
        tags = email.get("Tags", [])
        if not tags:
            continue
        for tag in tags:
            if tag not in tag_to_indices:
                tag_to_indices[tag] = set()
            tag_to_indices[tag].add(i)

    # For each tag, sample at most max_per_tag email indices
    selected_indices = set()
    for tag, indices in tag_to_indices.items():
        indices_list = list(indices)
        if len(indices_list) <= max_per_tag:
            selected_indices.update(indices_list)
        else:
            selected_indices.update(rng.sample(indices_list, max_per_tag))

    return [emails[i] for i in sorted(selected_indices)]


def train_with_random_forest(emails):
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
    model_path = paths.get("model_output", "models/email_classifier.pkl")

    # Create directories
    Path("data").mkdir(exist_ok=True)
    Path("models").mkdir(exist_ok=True)

    emails = load_emails(db_path, default_tag_name=NO_LABEL)

    # Limit to max_samples_per_tag if configured
    training_cfg = config.get("training", {})
    max_per_tag = training_cfg.get("max_samples_per_tag")
    if max_per_tag is not None and max_per_tag > 0:
        random_state = training_cfg.get("random_state", 42)
        before = len(emails)
        emails = limit_samples_per_tag(emails, max_per_tag, random_state)
        print(
            f"Limited to {max_per_tag} samples per tag: {before} -> {len(emails)} emails"
        )

    if not emails:
        print("No emails found.")
        return

    # Initialize and train model
    model = EmailLabelingModel(model_path=model_path, config=config)

    try:
        model.train(emails)
        print("\nTraining completed successfully!")
    except Exception as e:
        print(f"Error during training: {e}")


def train_with_fine_tune(upload=False, start_job=False):
    if not api_key:
        print("OPENAI_API_KEY not set. Cannot upload or start job.", file=sys.stderr)
        return 1

    emails = load_emails(db_path)

    llm = LLMTagModel(api_key)
    out_path = llm._write_train_data(emails, path="data/finetune_data.jsonl")

    # upload
    if not upload:
        return
    file_id = llm._upload_train_data(out_path)

    # create job
    if not start_job:
        return
    llm._start_job(file_id=file_id)


def main(args):
    """Main training function"""

    if args.random_forest:
        train_with_random_forest()
    elif args.fine_tune:
        train_with_fine_tune()


if __name__ == "__main__":
    arg_parser = argparse.ArgumentParser(description="Reddit scraper")
    arg_parser.add_argument("--random-forest", action="store_true")
    arg_parser.add_argument("--fine-tune", action="store_true")
    args = arg_parser.parse_args()

    sys.exit(main(args))
