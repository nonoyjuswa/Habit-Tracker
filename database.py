"""
database.py — the "Model" layer.

Everything that touches SQLite lives here. The UI never writes raw SQL;
it just calls these functions.

Uses ONE shared connection for the app's whole lifetime (rather than
opening/closing a new connection per call) — this avoids SQLite "database
is locked" errors that can happen from rapid connection churn, especially
on Windows.

Tables:
  notes          -> many rows per day allowed, each with its own timestamp
  habits         -> the habits you're tracking + their keyword variations
  habit_records  -> one row per (habit, date): was it detected that day
"""

import sqlite3
import re

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
    _connection = sqlite3.connect(DB_PATH, timeout=10)
    _connection.row_factory = sqlite3.Row
    _connection.execute("PRAGMA foreign_keys = ON")
    _connection.execute("PRAGMA journal_mode = WAL")   # better concurrent access
    _connection.execute("PRAGMA busy_timeout = 5000")  # wait up to 5s instead of erroring

    _connection.executescript(
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
            category TEXT NOT NULL,         -- 'Health' | 'Skills' | 'Money'
            keywords TEXT NOT NULL DEFAULT '' -- comma-separated variations
        );

        CREATE TABLE IF NOT EXISTS habit_records (
            habit_id INTEGER NOT NULL REFERENCES habits(id) ON DELETE CASCADE,
            date TEXT NOT NULL,
            detected INTEGER NOT NULL DEFAULT 0,   -- 0/1, driven only by keyword detection
            PRIMARY KEY (habit_id, date)
        );
        """
    )
    _connection.commit()


def close_db():
    """Call on app shutdown to release the file cleanly."""
    global _connection
    if _connection is not None:
        _connection.close()
        _connection = None


# ---------- Notes ----------

def add_note(note_date: str, note_time: str, description: str):
    """Adds a note. Multiple notes per day are allowed and stack by
    timestamp. Note text itself is never edited once saved."""
    conn = _conn()
    try:
        conn.execute(
            "INSERT INTO notes (date, time, description) VALUES (?, ?, ?)",
            (note_date, note_time, description),
        )
    except sqlite3.IntegrityError as e:
        raise RuntimeError(
            "Your habit_journal.db file has an outdated schema (likely from "
            "an earlier version of this app) and needs to be deleted so it "
            "can be recreated. Close the app, delete habit_journal.db "
            "(and -wal/-shm files next to it if present), then run again.\n"
            f"Original error: {e}"
        )
    conn.commit()
    # Recompute detection for this day across ALL of its notes (not just
    # this new one) — so a match in an earlier note today still counts.
    for habit in get_habits():
        detected = _detect_for_date(note_date, habit["keywords"])
        _upsert_record(habit["id"], note_date, detected)


def get_notes_for_date(note_date: str):
    """Returns all notes for a given day, oldest first."""
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
    rescan_habit(habit_id)  # populate history against existing notes
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
    rescan_habit(habit_id)  # keyword list changed -> re-check this habit only


def get_habits():
    rows = _conn().execute("SELECT * FROM habits ORDER BY id ASC").fetchall()
    return [dict(r) for r in rows]


def get_habit(habit_id: int):
    row = _conn().execute("SELECT * FROM habits WHERE id = ?", (habit_id,)).fetchone()
    return dict(row) if row else None


# ---------- Habit records (the per-day shaded/unshaded cells) ----------

def get_habit_records(habit_id: int) -> dict:
    """Returns {date_str: {'detected': bool}}"""
    rows = _conn().execute(
        "SELECT * FROM habit_records WHERE habit_id = ?", (habit_id,)
    ).fetchall()
    return {r["date"]: {"detected": bool(r["detected"])} for r in rows}


def rescan_habit(habit_id: int):
    """Re-checks every day that has at least one note against this habit's
    current keyword list, aggregating across ALL of that day's notes."""
    habit = get_habit(habit_id)
    if not habit:
        return
    for note_date in get_all_dates_with_notes():
        detected = _detect_for_date(note_date, habit["keywords"])
        _upsert_record(habit_id, note_date, detected)


def _detect_for_date(note_date: str, keywords_csv: str) -> bool:
    """True if ANY note on this day matches the habit's keywords."""
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
    """Whole-word, case-insensitive match so 'cat' doesn't match 'category'."""
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