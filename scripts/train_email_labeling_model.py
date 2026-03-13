import argparse
import json
import random
import sys
from datetime import date
from pathlib import Path
from typing import List, Dict, Any, Optional

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.constants import NO_LABEL
from core.email_labeling_model import EmailLabelingModel
from core.llm_tag_model import LLMTagModel
from config import config, env
from utils.db import get_all_tags, load_emails


def limit_samples_per_tag(
    emails: List[Dict[str, Any]],
    max_per_tag: int,
    random_state: Optional[int] = 42,
) -> List[Dict[str, Any]]:
    """
    Limit training data to at most max_per_tag emails per tag.
    Emails can have multiple tags; each email is included if it's sampled for any tag.
    Emails without tags are treated as a separate label group.

    Args:
        emails: List of labeled email dicts (must have "Tags" key)
        max_per_tag: Maximum number of emails to use per tag
        random_state: Random seed for reproducible sampling

    Returns:
        Subset of emails
    """
    if max_per_tag is None or max_per_tag <= 0:
        return emails

    before = len(emails)

    rng = random.Random(random_state)

    # Build tag -> email indices mapping
    tag_to_indices: Dict[str, set] = {}

    for i, email in enumerate(emails):
        tags = email.get("Tags", [])

        if not tags:
            tags = ["__NO_TAG__"]  # Treat no-tag emails as their own class

        for tag in tags:
            if tag not in tag_to_indices:
                tag_to_indices[tag] = set()
            tag_to_indices[tag].add(i)

    # Sample per tag
    selected_indices = set()
    for tag, indices in tag_to_indices.items():
        indices_list = list(indices)
        if len(indices_list) <= max_per_tag:
            selected_indices.update(indices_list)
        else:
            selected_indices.update(rng.sample(indices_list, max_per_tag))
    print(f"Limited to {max_per_tag} samples per tag: {before} -> {len(emails)} emails")
    return [emails[i] for i in sorted(selected_indices)]


def train_with_random_forest():
    # Get paths from config (from utils.config)
    paths = config.get("paths", {})
    model_path = paths.get("model_output", "models/email_classifier.pkl")

    # Create directories
    Path("data").mkdir(exist_ok=True)
    Path("models").mkdir(exist_ok=True)

    emails = load_emails(default_tag_name=NO_LABEL)

    # Limit to max_samples_per_tag if configured
    training_cfg = config.get("training", {})
    max_per_tag = training_cfg.get("max_samples_per_tag")
    if max_per_tag is not None and max_per_tag > 0:
        random_state = training_cfg.get("random_state", 42)
        emails = limit_samples_per_tag(emails, max_per_tag, random_state)

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


def prepare_training_data(emails: List[Dict[str, Any]], n_epochs: int):
    """
    Prepare training and validation data from emails.
    When n_epochs is 1, no validation split is created (all data used for training).
    """
    if n_epochs == 1:
        print(f"Prepared training data (no validation): {len(emails)} train")
        return emails, []

    training_cfg = config.get("training", {})
    random_state = training_cfg.get("random_state", 42)
    rng = random.Random(random_state)
    indices = list(range(len(emails)))
    rng.shuffle(indices)
    n_val = max(1, int(len(emails) * training_cfg.get("test_size", 0.2)))
    val_indices = set(indices[:n_val])
    train_emails = [emails[i] for i in indices if i not in val_indices]
    validation_emails = [emails[i] for i in indices if i in val_indices]
    print(
        f"Prepared training and validation data: {len(train_emails)} train, {len(validation_emails)} validation"
    )
    return train_emails, validation_emails


def upload_and_start_job(
    model: str,
    upload: bool,
    start_job: bool,
    train_emails: List[Dict[str, Any]],
    validation_emails: List[Dict[str, Any]],
):
    fine_tune_cfg = config.get("fine_tune", {})
    train_file = fine_tune_cfg.get("train_file")
    validation_file = fine_tune_cfg.get("validation_file")
    n_epochs = fine_tune_cfg.get("n_epochs")

    llm = LLMTagModel(env.OPENAI_API_KEY, model=model)
    llm._all_tags = get_all_tags()
    llm._write_finetune_jsonl(train_emails, train_file)
    if validation_emails:
        llm._write_finetune_jsonl(validation_emails, validation_file)

    if not upload:
        return 0
    train_file_id = llm._upload_train_data(train_file)
    validation_file_id = (
        llm._upload_train_data(validation_file) if validation_emails else None
    )

    if not start_job:
        return 0
    llm._start_job(
        file_id=train_file_id,
        validation_file_id=validation_file_id,
        n_epochs=n_epochs,
    )


def train_with_fine_tune(upload=False, start_job=False):
    if not env.OPENAI_API_KEY:
        print("OPENAI_API_KEY not set. Cannot upload or start job.", file=sys.stderr)
        return 1

    emails = load_emails(folder="archive")
    if not emails:
        print("No emails found for archive folder")
        return 1

    max_samples_per_tag = config.get("training", {}).get("max_samples_per_tag")
    if max_samples_per_tag > 0:
        emails = limit_samples_per_tag(emails, max_samples_per_tag)

    n_epochs = config.get("fine_tune", {}).get("n_epochs")
    train_emails, validation_emails = prepare_training_data(emails, n_epochs)

    return upload_and_start_job(
        model="gpt-4o-mini-2024-07-18",
        upload=upload,
        start_job=start_job,
        train_emails=train_emails,
        validation_emails=validation_emails,
    )


def retrain_fine_tune(
    upload: bool = False,
    start_job: bool = False,
    emails_path: Optional[str] = None,
) -> int:
    """
    Retrain the fine-tuned model from current FINE_TUNE_MODEL_ID.
    Source: if incorrect_path is set and file exists, use that JSONL (from predict export);
    otherwise load emails from DB (this year, archive folder), convert to JSONL, then train/val split.
    """
    if not env.OPENAI_API_KEY:
        print("OPENAI_API_KEY not set. Cannot upload or start job.", file=sys.stderr)
        return 1

    use_incorrect = emails_path and Path(emails_path).exists()
    if use_incorrect:
        path = Path(emails_path)
        with open(path, "r", encoding="utf-8") as f:
            emails = json.load(f)
    else:
        this_year = date.today().year
        emails = load_emails(year=this_year, folder="archive")
    if not emails:
        print("No emails found")
        return 1

    fine_tune_cfg = config.get("fine_tune", {})
    n_epochs = fine_tune_cfg.get("n_epochs")

    train_emails, validation_emails = prepare_training_data(emails, n_epochs)

    return upload_and_start_job(
        model=env.FINE_TUNE_MODEL_ID,
        upload=upload,
        start_job=start_job,
        train_emails=train_emails,
        validation_emails=validation_emails,
    )


def main(args):
    """Main training function"""

    if args.random_forest:
        train_with_random_forest()
    elif args.fine_tune:
        train_with_fine_tune(True, True)
    elif args.retrain_fine_tune:
        return retrain_fine_tune(
            upload=True,
            start_job=True,
            emails_path=args.emails_path,
        )


if __name__ == "__main__":
    arg_parser = argparse.ArgumentParser(description="Email labeling training")
    arg_parser.add_argument("--random-forest", action="store_true")
    arg_parser.add_argument("--fine-tune", action="store_true")
    arg_parser.add_argument(
        "--retrain-fine-tune",
        action="store_true",
        help="Retrain from FINE_TUNE_MODEL_ID using DB (this year, archive) or --emails-path file",
    )
    arg_parser.add_argument(
        "--emails-path",
        type=str,
        default=None,
        metavar="PATH",
        help="Use this JSONL (e.g. data/incorrect_emails.jsonl) as retrain data; else use DB",
    )
    args = arg_parser.parse_args()

    sys.exit(main(args))
