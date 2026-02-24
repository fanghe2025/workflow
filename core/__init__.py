"""
Core classes for the email workflow project.

This package exposes:
  - DatabaseConnection: DuckDB connection manager and schema initializer
  - EmailDownloader: High-level API for downloading emails into DuckDB
  - LLMTagModel: LLM-based email tag recommender (OpenAI)
"""

from .duckdb import DatabaseConnection
from .email_downloader import EmailDownloader
from .llm_tag_model import LLMTagModel

__all__ = ["DatabaseConnection", "EmailDownloader", "LLMTagModel"]
