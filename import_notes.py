"""
import_notes.py — one-time bulk import from a .txt journal file into
habit_journal.db.

Expected format (repeated for each day):

    July 10 */
    the texts are here....
    /*

Run it like:
    python import_notes.py path/to/your_notes.txt

Safe to run more than once on the same file — entries whose exact text is
already saved for that date are skipped instead of duplicated.
"""

import sys
import re
from datetime import datetime

import database as db

YEAR = 2026  # all entries assumed to be from this year

BLOCK_PATTERN = re.compile(
    r"([A-Za-z]+)\s+(\d{1,2})\s*\*/\s*\n(.*?)\n\s*/\*",
    re.DOTALL,
)


def parse_file(path: str):
    """Returns a list of (date_str, description) tuples found in the file."""
    with open(path, "r", encoding="utf-8") as f:
        raw = f.read()

    entries = []
    for match in BLOCK_PATTERN.finditer(raw):
        month_name, day_str, body = match.groups()
        date_obj = _parse_month_day(month_name, int(day_str))
        if date_obj is None:
            print(f"  ! Couldn't parse date '{month_name} {day_str}' — skipped that block.")
            continue
        description = body.strip()
        if not description:
            print(f"  ! {date_obj.isoformat()} had an empty body — skipped.")
            continue
        entries.append((date_obj.isoformat(), description))
    return entries


def _parse_month_day(month_name: str, day: int):
    for fmt in ("%B", "%b"):  # full name ("July") or abbreviated ("Jul")
        try:
            month_num = datetime.strptime(month_name.strip().title(), fmt).month
            return datetime(YEAR, month_num, day).date()
        except ValueError:
            continue
    return None


def import_entries(entries):
    db.init_db()
    imported, skipped = 0, 0

    for date_str, description in entries:
        already_there = any(
            n["description"].strip() == description
            for n in db.get_notes_for_date(date_str)
        )
        if already_there:
            skipped += 1
            continue
        db.add_note(date_str, "00:00", description)
        imported += 1

    return imported, skipped


if __name__ == "__main__":
    if len(sys.argv) != 2:
        print("Usage: python import_notes.py path/to/your_notes.txt")
        sys.exit(1)

    file_path = sys.argv[1]
    print(f"Reading {file_path} ...")
    found = parse_file(file_path)
    print(f"Found {len(found)} day-blocks in the file.")

    imported, skipped = import_entries(found)
    print(f"Done. Imported {imported} new notes, skipped {skipped} already-present duplicates.")
    print("If you add new habits/keywords now, run their rescan (add or edit a habit's")
    print("keywords in the Habits tab) to backfill their grids against this imported history.")