"""
Load config and env values for use across the project.

Usage:
    from config import config, env, get_env, load_config_file

    # Training config (config/training_config.json)
    config["training"]["test_size"]
    config["fine_tune"]["n_epochs"]
    config["paths"]["db_path"]

    # Environment variables (from .env / os.environ)
    env.OPENAI_API_KEY
    env.DUCKDB_PATH
    env.GRAPH_CLIENT_ID
    env.ML_API_URL

    get_env("MY_VAR", default="fallback")
    load_config_file("config/some_other.json")
"""

import json
import os
from pathlib import Path
from typing import Any, Dict

from dotenv import load_dotenv

_CONFIG_DIR = Path(__file__).resolve().parent
TRAINING_CONFIG_PATH = _CONFIG_DIR / "training_config.json"


def load_config_file(path: Path | str) -> Dict[str, Any]:
    """Load any JSON config file. Returns {} if file missing or invalid."""
    path = Path(path)
    if not path.exists():
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


def load_training_config(path: Path | str | None = None) -> Dict[str, Any]:
    """Load training config from JSON. Returns {} if file missing or invalid."""
    path = path or TRAINING_CONFIG_PATH
    path = Path(path)
    if not path.exists():
        return {}
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except Exception:
        return {}


# Singleton (loaded once on first import)
config = load_training_config()


def get_env(key: str, default: Any = None) -> Any:
    """Get an environment variable with optional default."""
    return os.getenv(key, default)


class _Env:
    """Environment variables with defaults. Use via the `env` instance. Loads .env on init."""

    def __init__(self) -> None:
        load_dotenv()

    # OpenAI / fine-tune
    @property
    def OPENAI_API_KEY(self) -> str:
        return os.getenv("OPENAI_API_KEY", "")

    @property
    def DUCKDB_PATH(self) -> str:
        return os.getenv("DUCKDB_PATH", "data/emails.duckdb")

    @property
    def FINE_TUNE_FILE_ID(self) -> str:
        return os.getenv("FINE_TUNE_FILE_ID", "")

    @property
    def FINE_TUNE_JOB_ID(self) -> str:
        return os.getenv("FINE_TUNE_JOB_ID", "")

    @property
    def FINE_TUNE_MODEL_ID(self) -> str:
        return os.getenv("FINE_TUNE_MODEL_ID", "")

    @property
    def MAX_SAMPLES_PER_TAG(self) -> str | None:
        v = os.getenv("MAX_SAMPLES_PER_TAG", "").strip()
        return v if v else None

    # Microsoft Graph (moved from graph_config.json)
    @property
    def GRAPH_CLIENT_ID(self) -> str:
        return os.getenv("GRAPH_CLIENT_ID", "")

    @property
    def GRAPH_CLIENT_SECRET(self) -> str:
        return os.getenv("GRAPH_CLIENT_SECRET", "")

    @property
    def GRAPH_TENANT_ID(self) -> str:
        return os.getenv("GRAPH_TENANT_ID", "")

    @property
    def GRAPH_USER_EMAIL(self) -> str:
        return os.getenv("GRAPH_USER_EMAIL", "")

    @property
    def ML_API_URL(self) -> str:
        return os.getenv("ML_API_URL", "http://localhost:5000")

    @property
    def ATTACHMENTS_DIR(self) -> str:
        return os.getenv("ATTACHMENTS_DIR", "data/attachments")

    @property
    def GRAPH_FILTER(self) -> str | None:
        v = os.getenv("GRAPH_FILTER", "").strip()
        return v if v else None

    @property
    def BATCH_SIZE(self) -> int:
        v = os.getenv("BATCH_SIZE", "100").strip()
        try:
            return int(v)
        except ValueError:
            return 100


env = _Env()
