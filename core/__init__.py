"""
Core classes for the email workflow project.

This package exposes:
  - DatabaseConnection: DuckDB connection manager and schema initializer
  - EmailDownloader: High-level API for downloading emails into DuckDB
"""

from .db import DatabaseConnection
from .email_downloader import EmailDownloader

__all__ = ["DatabaseConnection", "EmailDownloader"]
