import argparse
import os
import sys

from pathlib import Path

from dotenv import load_dotenv

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.llm_tag_model import LLMTagModel


load_dotenv()
api_key = os.getenv("OPENAI_API_KEY")
fine_tune_file_id = os.getenv("FINE_TUNE_FILE_ID")
fine_tune_job_id = os.getenv("FINE_TUNE_JOB_ID")


def delete_file():
    llm = LLMTagModel(api_key)
    llm._remove_train_data(fine_tune_file_id)


def start_job():
    llm = LLMTagModel(api_key)
    llm._start_job(file_id=fine_tune_file_id)


def get_job():
    llm = LLMTagModel(api_key)
    llm._get_job(fine_tune_job_id)


def cancel_job():
    llm = LLMTagModel(api_key)
    llm._cancel_job(fine_tune_job_id)


def main(args):
    """Main training function"""

    if args.delete_file:
        delete_file()
    elif args.start_job:
        start_job()
    elif args.get_job:
        get_job()
    elif args.cancel_job:
        cancel_job()


if __name__ == "__main__":
    arg_parser = argparse.ArgumentParser(description="Reddit scraper")
    arg_parser.add_argument("--delete-file", action="store_true")
    arg_parser.add_argument("--start-job", action="store_true")
    arg_parser.add_argument("--get-job", action="store_true")
    arg_parser.add_argument("--cancel-job", action="store_true")
    args = arg_parser.parse_args()

    sys.exit(main(args))
