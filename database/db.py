
import sqlite3
from pathlib import Path


DATABASE = Path(__file__).parent / "notes.db"


def get_db_connection():
    connection = sqlite3.connect(DATABASE)
    connection.row_factory = sqlite3.Row

    # Enforce foreign-key relationships for this connection.
    connection.execute("PRAGMA foreign_keys = ON")

    return connection
