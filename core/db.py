"""
Database Model Definitions for Email Workflow

This module contains all database schema definitions and table creation logic
for the DuckDB email storage system.
"""

import logging
import duckdb
from pathlib import Path

logger = logging.getLogger(__name__)


class DatabaseConnection:
    """
    Database connection manager for DuckDB email storage

    This class manages DuckDB connections and provides context manager support
    for automatic connection handling.
    """

    def __init__(self, db_path: str, auto_init: bool = True):
        """
        Initialize database connection manager

        Args:
            db_path: Path to DuckDB database file
            auto_init: If True, automatically initialize tables on connection
        """
        self.db_path = db_path
        db_dir = Path(self.db_path).parent
        db_dir.mkdir(parents=True, exist_ok=True)

        self.conn = None
        if auto_init:
            self.connect()
            self.initialize_database()

    def connect(self) -> duckdb.DuckDBPyConnection:
        """
        Connect to DuckDB database and initialize tables if needed

        Returns:
            DuckDB connection object
        """
        if not self.conn:
            self.conn = duckdb.connect(self.db_path)
            logger.info(f"Connected to DuckDB database: {self.db_path}")
        return self.conn

    def initialize_database(self) -> None:
        """
        Create all database tables if they don't exist
        """
        if not self.conn:
            raise RuntimeError("Database not connected. Call connect() first.")
        # Create threads table first
        create_threads_table_sql = """
        CREATE TABLE IF NOT EXISTS threads (
            ThreadID VARCHAR PRIMARY KEY,
            CreatedAt TIMESTAMP,
            ProcessedTimestamp TIMESTAMP,
            current_folder VARCHAR,
            Tags VARCHAR,
            Additional_tags VARCHAR
        )
        """
        self.conn.execute(create_threads_table_sql)
        logger.info("Created/verified threads table")

        # Create emails table with new schema
        create_table_sql = """
        CREATE TABLE IF NOT EXISTS emails (
            ID VARCHAR PRIMARY KEY,
            ThreadID VARCHAR,
            Timestamp TIMESTAMP,
            Sender VARCHAR,
            Subject VARCHAR,
            Message TEXT,
            OtherRecipients VARCHAR,
            IsRead BOOLEAN,
            has_attachments BOOLEAN,
            attachments TEXT,
            raw_json TEXT,
            downloaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (ThreadID) REFERENCES threads(ThreadID)
        )
        """
        self.conn.execute(create_table_sql)

        # Create attachments table
        create_attachments_table_sql = """
        CREATE TABLE IF NOT EXISTS attachments (
            attachment_id VARCHAR PRIMARY KEY,
            email_id VARCHAR,
            name VARCHAR,
            content_type VARCHAR,
            size INTEGER,
            file_path VARCHAR,
            downloaded_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (email_id) REFERENCES emails(ID)
        )
        """
        self.conn.execute(create_attachments_table_sql)
        logger.info("Created/verified attachments table")

    def close(self) -> None:
        """Close database connection"""
        if self.conn:
            self.conn.close()
            self.conn = None
            logger.info("Database connection closed")

    def __enter__(self) -> duckdb.DuckDBPyConnection:
        """Context manager entry"""
        return self.connect()

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Context manager exit"""
        self.close()

    def __del__(self):
        """Cleanup on deletion"""
        self.close()
