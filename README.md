# Habit Journal

A daily journal that auto-detects your habits from what you write, and
shows each one as a GitHub-style 53-week grid.

## Running it

```
pip install customtkinter
python main.py
```

A `habit_journal.db` SQLite file will be created next to `main.py` on first run.

## How the files map to what we designed

- `database.py` — the **Model**. All SQLite access, keyword matching
  (whole-word, case-insensitive), and the rescan logic live here.
- `date_utils.py` — calendar/date helpers (the 53-week grid layout, recent-days list).
- `habit_grid.py` — the reusable GitHub-style grid widget (one per habit).
- `journal_view.py` — the **Journal** tab: horizontal day timeline + note entry.
  Today is editable until you register a note; every day before that is locked
  forever — notes are never edited after the fact.
- `habits_view.py` — the **Habits** tab: add/delete habits, add keyword
  variations, and view/override each habit's grid.
- `main.py` — the **Controller**/entry point that wires the two tabs together.

## The rules we locked in

1. Notes are locked once written — no editing note text, ever.
2. You can only add a note for today (no backdating over an existing day).
3. Habit cells CAN be manually toggled (click a cell in the Habits tab) —
   this is the safety net for missed keyword matches.
4. Adding/editing a habit's keywords triggers a **rescan of that habit only**
   against all saved notes — but any cell you manually overrode is
   protected and never gets silently overwritten by a rescan.
5. All three habits (Health, Skills, Money) are binary (done/not done) for
   this version — hour-based intensity and the "Spirit" category are
   deliberately deferred to a future version.

## Known v1 limits (on purpose, not bugs)

- Only 3 categories are wired into the UI dropdown right now (Health,
  Skills, Money) — add more by editing `CATEGORIES` in `habits_view.py`.
- The journal timeline shows the last 30 days; older history isn't
  browsable yet from that view (though it's all still in the database).
