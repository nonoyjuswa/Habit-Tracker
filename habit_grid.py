import tkinter as tk
import customtkinter as ctk
from date_utils import build_52_week_grid

CELL = 12
GAP = 3
LEFT_PAD = 30
TOP_PAD = 20

CATEGORY_COLORS = {
    "Health": "#39d353",
    "Skills": "#58a6ff",
    "Money": "#d2a8ff",
}
EMPTY_COLOR = "#161b22"
BORDER_COLOR = "#21262d"
TODAY_BORDER = "#22d3ee"


class HabitGrid(ctk.CTkFrame):
    """A GitHub-contribution-style grid for one habit. Click a cell to
    manually override it. Rendering is data-driven: call refresh(records)
    whenever the underlying data changes."""

    def __init__(self, master, category: str, on_cell_click, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self.category = category
        self.on_cell_click = on_cell_click
        self.weeks = build_52_week_grid()
        self.cell_lookup = {}  # canvas item id -> date_str

        width = LEFT_PAD + len(self.weeks) * (CELL + GAP) + 20
        height = TOP_PAD + 7 * (CELL + GAP) + 10

        self.canvas = tk.Canvas(
            self, width=width, height=height, bg="#0d1117", highlightthickness=0
        )
        self.canvas.pack(fill="x", expand=True)
        self.canvas.bind("<Button-1>", self._handle_click)

        self._draw_month_labels()
        self._draw_weekday_labels()

    def _draw_month_labels(self):
        last_month = None
        for w_idx, week in enumerate(self.weeks):
            first_day = week[0]
            if first_day["month_label"] != last_month:
                last_month = first_day["month_label"]
                x = LEFT_PAD + w_idx * (CELL + GAP)
                self.canvas.create_text(
                    x, 10, text=last_month, fill="#8b949e",
                    font=("Segoe UI", 8), anchor="w"
                )

    def _draw_weekday_labels(self):
        for label, row in [("Sun", 0), ("Tue", 2), ("Thu", 4), ("Sat", 6)]:
            y = TOP_PAD + row * (CELL + GAP) + CELL // 2
            self.canvas.create_text(
                5, y, text=label, fill="#8b949e", font=("Segoe UI", 7), anchor="w"
            )

    def refresh(self, records: dict):
        """records: {date_str: {'detected': bool, 'overridden': bool}}"""
        self.cell_lookup = {}
        # clear previous cells (keep month/weekday labels by tagging cells)
        self.canvas.delete("cell")

        color = CATEGORY_COLORS.get(self.category, "#39d353")
        today_str = None
        from date_utils import today_str as _today
        today_str = _today()

        for w_idx, week in enumerate(self.weeks):
            for day in week:
                x = LEFT_PAD + w_idx * (CELL + GAP)
                y = TOP_PAD + day["day_of_week"] * (CELL + GAP)

                if day["is_future"]:
                    fill = "#0d1117"
                    outline = "#161b22"
                else:
                    rec = records.get(day["date_str"])
                    active = bool(rec and rec.get("detected"))
                    fill = color if active else EMPTY_COLOR
                    outline = BORDER_COLOR

                is_today = day["date_str"] == today_str
                width = 2 if is_today else 1
                outline_color = TODAY_BORDER if is_today else outline

                item = self.canvas.create_rectangle(
                    x, y, x + CELL, y + CELL,
                    fill=fill, outline=outline_color, width=width,
                    tags="cell"
                )
                if not day["is_future"]:
                    self.cell_lookup[item] = day["date_str"]

    def _handle_click(self, event):
        item = self.canvas.find_closest(event.x, event.y)
        if item and item[0] in self.cell_lookup:
            date_str = self.cell_lookup[item[0]]
            self.on_cell_click(date_str)
