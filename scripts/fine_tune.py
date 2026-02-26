import argparse
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from config import env
from core.llm_tag_model import LLMTagModel


def delete_file():
    llm = LLMTagModel(env.OPENAI_API_KEY)
    llm._remove_train_data(env.FINE_TUNE_FILE_ID)


def start_job():
    llm = LLMTagModel(env.OPENAI_API_KEY)
    llm._start_job(file_id=env.FINE_TUNE_FILE_ID)


def get_job():
    llm = LLMTagModel(env.OPENAI_API_KEY)
    llm._get_job(env.FINE_TUNE_JOB_ID)


def list_jobs():
    llm = LLMTagModel(env.OPENAI_API_KEY)
    llm._list_jobs()


def resume_job():
    llm = LLMTagModel(env.OPENAI_API_KEY)
    llm._resume_job(env.FINE_TUNE_JOB_ID)


def cancel_job():
    llm = LLMTagModel(env.OPENAI_API_KEY)
    llm._cancel_job(env.FINE_TUNE_JOB_ID)


def delete_model():
    llm = LLMTagModel(env.OPENAI_API_KEY)
    llm._delete_model(env.FINE_TUNE_MODEL_ID)


def main(args):
    """Main training function"""

    if args.delete_file:
        delete_file()
    elif args.start_job:
        start_job()
    elif args.get_job:
        get_job()
    elif args.list_jobs:
        list_jobs()
    elif args.resume_job:
        resume_job()
    elif args.cancel_job:
        cancel_job()


if __name__ == "__main__":
    arg_parser = argparse.ArgumentParser(description="Reddit scraper")
    arg_parser.add_argument("--delete-file", action="store_true")
    arg_parser.add_argument("--start-job", action="store_true")
    arg_parser.add_argument("--get-job", action="store_true")
    arg_parser.add_argument("--list-jobs", action="store_true")
    arg_parser.add_argument("--resume-job", action="store_true")
    arg_parser.add_argument("--cancel-job", action="store_true")
    args = arg_parser.parse_args()

    sys.exit(main(args))
