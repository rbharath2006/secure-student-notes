
"""Create a consistent SQLite backup of the Student Notes database."""

import sqlite3
from datetime import datetime
from pathlib import Path

from database.db import DATABASE

BACKUP_DIR = Path(__file__).parent / "backups"


def backup_database():
    if not DATABASE.is_file():
        raise FileNotFoundError(f"Database not found: {DATABASE}")

    BACKUP_DIR.mkdir(parents=True, exist_ok=True)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    backup_path = BACKUP_DIR / f"student_notes_{timestamp}.sqlite3"

    try:
        with sqlite3.connect(DATABASE) as source:
            with sqlite3.connect(backup_path) as destination:
                source.backup(destination)

                integrity = destination.execute(
                    "PRAGMA integrity_check"
                ).fetchone()[0]

                if integrity != "ok":
                    raise RuntimeError(
                        f"Backup integrity check failed: {integrity}"
                    )

        print("Backup created successfully.")
        print(f"Location: {backup_path.resolve()}")
        print(f"Integrity: {integrity}")

    except Exception:
        # Remove an incomplete backup, never the original database.
        if backup_path.exists():
            backup_path.unlink()
        raise


if __name__ == "__main__":
    backup_database()
