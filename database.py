"""
database.py — the "Model" layer.

Everything that touches SQLite lives here. The UI never writes raw SQL;
it just calls these functions.

Tables:
  notes          -> one row per calendar day (locked once the day passes)
  habits         -> the habits you're tracking + their keyword variations
  habit_records  -> one row per (habit, date): was it detected, was it
                    manually overridden
"""

import sqlite3
import re
from datetime import date

DB_PATH = "habit_journal.db"


def get_connection():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db():
    conn = get_connection()
    conn.executescript(
        """
        CREATE TABLE IF NOT EXISTS notes (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            date TEXT UNIQUE NOT NULL,      -- 'YYYY-MM-DD'
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
    conn.commit()
    conn.close()


# ---------- Notes ----------

def add_note(note_date: str, note_time: str, description: str):
    """Adds a note for a day that doesn't have one yet. Locked afterward
    (no update function exists on purpose — notes are never edited)."""
    conn = get_connection()
    try:
        conn.execute(
            "INSERT INTO notes (date, time, description) VALUES (?, ?, ?)",
            (note_date, note_time, description),
        )
        conn.commit()
    except sqlite3.IntegrityError:
        raise ValueError(f"A note already exists for {note_date}.")
    finally:
        conn.close()
    # Run keyword detection for every habit against this new note
    for habit in get_habits():
        detected = _text_matches_keywords(description, habit["keywords"])
        _upsert_record(habit["id"], note_date, detected)


def get_note(note_date: str):
    conn = get_connection()
    row = conn.execute("SELECT * FROM notes WHERE date = ?", (note_date,)).fetchone()
    conn.close()
    return dict(row) if row else None


def get_all_notes():
    conn = get_connection()
    rows = conn.execute("SELECT * FROM notes ORDER BY date ASC").fetchall()
    conn.close()
    return [dict(r) for r in rows]


# ---------- Habits ----------

def add_habit(name: str, category: str, keywords: list[str]):
    conn = get_connection()
    cur = conn.execute(
        "INSERT INTO habits (name, category, keywords) VALUES (?, ?, ?)",
        (name, category, ",".join(k.strip() for k in keywords if k.strip())),
    )
    conn.commit()
    habit_id = cur.lastrowid
    conn.close()
    rescan_habit(habit_id)  # populate history against existing notes
    return habit_id


def delete_habit(habit_id: int):
    conn = get_connection()
    conn.execute("DELETE FROM habits WHERE id = ?", (habit_id,))
    conn.commit()
    conn.close()


def update_habit_keywords(habit_id: int, keywords: list[str]):
    conn = get_connection()
    conn.execute(
        "UPDATE habits SET keywords = ? WHERE id = ?",
        (",".join(k.strip() for k in keywords if k.strip()), habit_id),
    )
    conn.commit()
    conn.close()
    rescan_habit(habit_id)  # keyword list changed -> re-check this habit only


def get_habits():
    conn = get_connection()
    rows = conn.execute("SELECT * FROM habits ORDER BY id ASC").fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_habit(habit_id: int):
    conn = get_connection()
    row = conn.execute("SELECT * FROM habits WHERE id = ?", (habit_id,)).fetchone()
    conn.close()
    return dict(row) if row else None


# ---------- Habit records (the per-day shaded/unshaded cells) ----------

def get_habit_records(habit_id: int) -> dict:
    """Returns {date_str: {'detected': bool}}"""
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM habit_records WHERE habit_id = ?", (habit_id,)
    ).fetchall()
    conn.close()
    return {r["date"]: {"detected": bool(r["detected"])} for r in rows}


def rescan_habit(habit_id: int):
    """Re-checks ALL saved notes against this one habit's current keyword
    list. Cells are locked (no manual override), so this simply recomputes
    detection for every day from scratch."""
    habit = get_habit(habit_id)
    if not habit:
        return
    for note in get_all_notes():
        detected = _text_matches_keywords(note["description"], habit["keywords"])
        _upsert_record(habit_id, note["date"], detected)


def _upsert_record(habit_id: int, record_date: str, detected: bool):
    conn = get_connection()
    conn.execute(
        """INSERT INTO habit_records (habit_id, date, detected)
           VALUES (?, ?, ?)
           ON CONFLICT(habit_id, date) DO UPDATE SET detected = ?""",
        (habit_id, record_date, int(detected), int(detected)),
    )
    conn.commit()
    conn.close()


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
