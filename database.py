"""
database.py — the "Model" layer.

Everything that touches SQLite lives here. The UI never writes raw SQL;
it just calls these functions.

Schema history and upgrade logic live in migrations.py, not here — this
file stays focused purely on how the app talks to data today.
"""

import sqlite3
import re

import migrations

DB_PATH = "habit_journal.db"

_connection = None  # single shared connection, created by init_db()


def _conn():
    if _connection is None:
        raise RuntimeError("Call init_db() before using the database.")
    return _connection


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
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT NOT NULL,
            time TEXT NOT NULL,
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

    migrations.run_migrations(conn, notes_table_existed_before)

    _connection = conn


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