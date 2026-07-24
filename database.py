"""
database.py — the "Model" layer.

Everything that touches SQLite lives here. The UI never writes raw SQL;
it just calls these functions.

--- Schema migrations ---
The database file stores its own schema_version number. On startup,
init_db() checks that version and runs only the migrations needed to
bring an existing file up to date — your actual notes/habits/records are
preserved, only the table structure changes. This means future schema
changes never require deleting your data.

To add a new schema change later:
  1. Bump CURRENT_SCHEMA_VERSION by 1
  2. Write a _migrate_vN_to_vM(conn) function that alters the schema
  3. Add it to the MIGRATIONS dict keyed by the version it upgrades TO
That's it — existing users' files upgrade automatically next launch.
"""

import sqlite3
import re

DB_PATH = "habit_journal.db"

CURRENT_SCHEMA_VERSION = 2
# v1 = original schema (notes.date UNIQUE)
# v2 = notes.date no longer unique (multiple stacked notes per day)

_connection = None  # single shared connection, created by init_db()


def _conn():
    if _connection is None:
        raise RuntimeError("Call init_db() before using the database.")
    return _connection


# ---------- Setup + migrations ----------

def init_db():
    global _connection
    if _connection is not None:
        return  # already initialized

    conn = sqlite3.connect(DB_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    conn.execute("PRAGMA journal_mode = WAL")
    conn.execute("PRAGMA busy_timeout = 5000")

    notes_table_existed_before = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='notes'"
    ).fetchone() is not None

    # Create tables at their LATEST definition if they don't exist yet.
    # (For a brand-new db, this alone produces the current schema directly.)
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,             -- 'YYYY-MM-DD' — many notes per day allowed
            time TEXT NOT NULL,             -- 'HH:MM'
            description TEXT NOT NULL
        );

        CREATE TABLE IF NOT EXISTS habits (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            category TEXT NOT NULL,
            keywords TEXT NOT NULL DEFAULT ''
        );

        CREATE TABLE IF NOT EXISTS habit_records (
            habit_id INTEGER NOT NULL REFERENCES habits(id) ON DELETE CASCADE,
            date TEXT NOT NULL,
            detected INTEGER NOT NULL DEFAULT 0,
            PRIMARY KEY (habit_id, date)
        );

        CREATE TABLE IF NOT EXISTS schema_version (
            id INTEGER PRIMARY KEY CHECK (id = 1),
            version INTEGER NOT NULL
        );
        """
    )
    conn.commit()

    version_row = conn.execute("SELECT version FROM schema_version WHERE id = 1").fetchone()

    if version_row is None:
        if notes_table_existed_before:
            # This file predates schema versioning entirely — treat it as
            # version 1 and run every migration up to current.
            # (_run_migrations also stamps schema_version as it goes.)
            _run_migrations(conn, from_version=1)
        else:
            # Brand-new file, already created at the latest schema above —
            # just stamp it, no migration needed.
            conn.execute(
                "INSERT INTO schema_version (id, version) VALUES (1, ?)",
                (CURRENT_SCHEMA_VERSION,),
            )
            conn.commit()
    else:
        _run_migrations(conn, from_version=version_row["version"])

    _connection = conn


def _run_migrations(conn, from_version: int):
    """Applies every migration needed to go from `from_version` up to
    CURRENT_SCHEMA_VERSION, in order, updating the stored version after
    each successful step."""
    for v in range(from_version + 1, CURRENT_SCHEMA_VERSION + 1):
        migration_fn = MIGRATIONS.get(v)
        if migration_fn:
            migration_fn(conn)
        conn.execute(
            "INSERT INTO schema_version (id, version) VALUES (1, ?) "
            "ON CONFLICT(id) DO UPDATE SET version = ?",
            (v, v),
        )
        conn.commit()
    # Safety net: guarantee a row exists at CURRENT_SCHEMA_VERSION even if
    # the loop above had nothing to do (e.g. from_version already current).
    conn.execute(
        "INSERT INTO schema_version (id, version) VALUES (1, ?) "
        "ON CONFLICT(id) DO UPDATE SET version = ?",
        (CURRENT_SCHEMA_VERSION, CURRENT_SCHEMA_VERSION),
    )
    conn.commit()


def _migrate_v1_to_v2_remove_notes_unique(conn):
    """v1 -> v2: notes.date was UNIQUE (one note per day). Rebuild the
    table without that constraint so multiple notes per day can stack,
    copying every existing row across untouched."""
    conn.execute("ALTER TABLE notes RENAME TO notes_old_v1")
    conn.execute(
        """CREATE TABLE notes (
               id INTEGER PRIMARY KEY AUTOINCREMENT,
               date TEXT NOT NULL,
               time TEXT NOT NULL,
               description TEXT NOT NULL
           )"""
    )
    conn.execute(
        "INSERT INTO notes (id, date, time, description) "
        "SELECT id, date, time, description FROM notes_old_v1"
    )
    conn.execute("DROP TABLE notes_old_v1")


MIGRATIONS = {
    2: _migrate_v1_to_v2_remove_notes_unique,
    # Add future migrations here, e.g. 3: _migrate_v2_to_v3_add_spirit_category
}


def close_db():
    global _connection
    if _connection is not None:
        _connection.close()
        _connection = None


# ---------- Notes ----------

def add_note(note_date: str, note_time: str, description: str):
    """Adds a note. Multiple notes per day are allowed and stack by
    timestamp. Note text itself is never edited once saved."""
    conn = _conn()
    conn.execute(
        "INSERT INTO notes (date, time, description) VALUES (?, ?, ?)",
        (note_date, note_time, description),
    )
    conn.commit()
    for habit in get_habits():
        detected = _detect_for_date(note_date, habit["keywords"])
        _upsert_record(habit["id"], note_date, detected)


def get_notes_for_date(note_date: str):
    rows = _conn().execute(
        "SELECT * FROM notes WHERE date = ? ORDER BY time ASC, id ASC", (note_date,)
    ).fetchall()
    return [dict(r) for r in rows]


def get_all_notes():
    rows = _conn().execute(
        "SELECT * FROM notes ORDER BY date ASC, time ASC, id ASC"
    ).fetchall()
    return [dict(r) for r in rows]


def get_all_dates_with_notes():
    rows = _conn().execute("SELECT DISTINCT date FROM notes ORDER BY date ASC").fetchall()
    return [r["date"] for r in rows]


# ---------- Habits ----------

def add_habit(name: str, category: str, keywords: list[str]):
    conn = _conn()
    cur = conn.execute(
        "INSERT INTO habits (name, category, keywords) VALUES (?, ?, ?)",
        (name, category, ",".join(k.strip() for k in keywords if k.strip())),
    )
    conn.commit()
    habit_id = cur.lastrowid
    rescan_habit(habit_id)
    return habit_id


def delete_habit(habit_id: int):
    conn = _conn()
    conn.execute("DELETE FROM habits WHERE id = ?", (habit_id,))
    conn.commit()


def update_habit_keywords(habit_id: int, keywords: list[str]):
    conn = _conn()
    conn.execute(
        "UPDATE habits SET keywords = ? WHERE id = ?",
        (",".join(k.strip() for k in keywords if k.strip()), habit_id),
    )
    conn.commit()
    rescan_habit(habit_id)


def get_habits():
    rows = _conn().execute("SELECT * FROM habits ORDER BY id ASC").fetchall()
    return [dict(r) for r in rows]


def get_habit(habit_id: int):
    row = _conn().execute("SELECT * FROM habits WHERE id = ?", (habit_id,)).fetchone()
    return dict(row) if row else None


# ---------- Habit records ----------

def get_habit_records(habit_id: int) -> dict:
    rows = _conn().execute(
        "SELECT * FROM habit_records WHERE habit_id = ?", (habit_id,)
    ).fetchall()
    return {r["date"]: {"detected": bool(r["detected"])} for r in rows}


def rescan_habit(habit_id: int):
    habit = get_habit(habit_id)
    if not habit:
        return
    for note_date in get_all_dates_with_notes():
        detected = _detect_for_date(note_date, habit["keywords"])
        _upsert_record(habit_id, note_date, detected)


def _detect_for_date(note_date: str, keywords_csv: str) -> bool:
    return any(
        _text_matches_keywords(n["description"], keywords_csv)
        for n in get_notes_for_date(note_date)
    )


def _upsert_record(habit_id: int, record_date: str, detected: bool):
    conn = _conn()
    conn.execute(
        """INSERT INTO habit_records (habit_id, date, detected)
           VALUES (?, ?, ?)
           ON CONFLICT(habit_id, date) DO UPDATE SET detected = ?""",
        (habit_id, record_date, int(detected), int(detected)),
    )
    conn.commit()


def _text_matches_keywords(text: str, keywords_csv: str) -> bool:
    if not keywords_csv:
        return False
    text_lower = text.lower()
    for kw in keywords_csv.split(","):
        kw = kw.strip().lower()
        if not kw:
            continue
        if re.search(rf"\b{re.escape(kw)}\b", text_lower):
            return True
    return False