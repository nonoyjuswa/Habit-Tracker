"""
migrations.py — the database's version history.

This file only grows when the TABLE STRUCTURE changes (a column added,
removed, or a constraint changed) — never for everyday feature/logic work.
Once a migration is written and working, you should rarely need to open
this file again; it's write-once, then left alone.

To add a new schema change in the future:
  1. Bump CURRENT_SCHEMA_VERSION by 1
  2. Write a _migrate_vN_to_vM(conn) function that alters the schema
  3. Add it to MIGRATIONS, keyed by the version it upgrades TO
Existing users' database files upgrade automatically on their next launch —
run_migrations() below handles figuring out what (if anything) needs to run.
"""

CURRENT_SCHEMA_VERSION = 2
# v1 = original schema (notes.date UNIQUE — one note per day)
# v2 = notes.date no longer unique (multiple stacked notes per day allowed)


def _migrate_v1_to_v2_remove_notes_unique(conn):
    """v1 -> v2: rebuild the notes table without the UNIQUE constraint on
    date, so multiple notes per day can stack. Copies every existing row
    across untouched."""
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


def run_migrations(conn, notes_table_existed_before: bool):
    """Brings whatever database file is on disk up to CURRENT_SCHEMA_VERSION.
    Safe to call every launch — does nothing if already up to date."""
    version_row = conn.execute("SELECT version FROM schema_version WHERE id = 1").fetchone()

    if version_row is None:
        if notes_table_existed_before:
            # File predates schema versioning entirely — treat it as
            # version 1 and run every migration up to current.
            _apply_from(conn, from_version=1)
        else:
            # Brand-new file, already created at the latest schema —
            # just stamp it, no migration needed.
            conn.execute(
                "INSERT INTO schema_version (id, version) VALUES (1, ?)",
                (CURRENT_SCHEMA_VERSION,),
            )
            conn.commit()
    else:
        _apply_from(conn, from_version=version_row["version"])


def _apply_from(conn, from_version: int):
    for v in range(from_version + 1, CURRENT_SCHEMA_VERSION + 1):
        migration_fn = MIGRATIONS.get(v)
        if migration_fn:
            migration_fn(conn)
        _stamp_version(conn, v)
    # Safety net: guarantee a row exists at CURRENT_SCHEMA_VERSION even if
    # the loop above had nothing to do (e.g. from_version already current).
    _stamp_version(conn, CURRENT_SCHEMA_VERSION)


def _stamp_version(conn, version: int):
    conn.execute(
        "INSERT INTO schema_version (id, version) VALUES (1, ?) "
        "ON CONFLICT(id) DO UPDATE SET version = ?",
        (version, version),
    )
    conn.commit()