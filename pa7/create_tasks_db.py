import os
import sqlite3
import sys

DEFAULT_DB_PATH = r"C:\Users\georg\Documents\claude-projects\taskmanager\tasks.db"

SCHEMA = """
CREATE TABLE tasks (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    title       TEXT    NOT NULL,
    assigned_to TEXT,
    due_date    TEXT,   -- stored as YYYY-MM-DD
    status      TEXT    NOT NULL DEFAULT 'open'
                CHECK (status IN ('open', 'in_progress', 'completed'))
);
"""

SAMPLE_TASKS = [
    # (title, assigned_to, due_date, status)
    ("Set up project repo",        "Alice", "2025-04-01", "completed"),
    ("Design database schema",     "Bob",   "2025-04-03", "completed"),
    ("Write unit tests",           "Alice", "2025-04-10", "open"),
    ("Add task edit form",         "Carol", "2025-04-12", "in_progress"),
    ("Style the task list page",   "Bob",   "2025-04-14", "in_progress"),
    ("Add due-date sorting",       "Carol", "2025-04-14", "open"),
    ("Fix login bug",              "Bob",   "2025-04-15", "open"),
    ("Write README",               "Alice", "2025-04-18", "open"),
    ("Add delete confirmation",    "Dave",  "2025-04-20", "in_progress"),
    ("Deploy to staging",          "Dave",  "2025-04-25", "open"),
    ("Code review: auth module",   "Alice", "2025-04-08", "completed"),
    ("Add pagination",             "Carol", "2025-04-28", "open"),
]


def main() -> None:
    db_path = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_DB_PATH

    folder = os.path.dirname(db_path)
    if folder and not os.path.isdir(folder):
        sys.exit(f"Folder does not exist: {folder}")

    if os.path.exists(db_path):
        sys.exit(f"{db_path} already exists. Delete it first if you want a fresh copy.")

    with sqlite3.connect(db_path) as conn:
        conn.executescript(SCHEMA)
        conn.executemany(
            "INSERT INTO tasks (title, assigned_to, due_date, status) VALUES (?, ?, ?, ?)",
            SAMPLE_TASKS,
        )

        print(f"Created {db_path}\n")
        print("Tasks by status:")
        for status, count in conn.execute(
            "SELECT status, COUNT(*) FROM tasks GROUP BY status ORDER BY status"
        ):
            print(f"  {status:<12} {count}")


if __name__ == "__main__":
    main()
