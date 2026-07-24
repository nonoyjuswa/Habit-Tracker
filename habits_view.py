import customtkinter as ctk
import database as db
from habit_grid import HabitGrid

CATEGORIES = ["Health", "Skills", "Money"]


class HabitsView(ctk.CTkFrame):
    def __init__(self, master, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self.selected_habit_id = None
        self.grid_widget = None

        self.grid_columnconfigure(1, weight=1)
        self.grid_rowconfigure(0, weight=1)

        # --- Left: habit list + add form ---
        left = ctk.CTkFrame(self, width=220, fg_color="#161b22")
        left.grid(row=0, column=0, sticky="nsw", padx=(0, 12))
        left.grid_propagate(False)

        ctk.CTkLabel(left, text="Your Habits", font=("Segoe UI", 14, "bold")).pack(
            anchor="w", padx=12, pady=(12, 6)
        )
        self.habit_list_frame = ctk.CTkScrollableFrame(left, fg_color="transparent", width=200, height=260)
        self.habit_list_frame.pack(fill="both", expand=True, padx=8)

        ctk.CTkButton(left, text="+ Add Habit", command=self._open_add_dialog).pack(
            fill="x", padx=12, pady=12
        )

        # --- Right: selected habit detail + grid ---
        self.right = ctk.CTkFrame(self, fg_color="#161b22")
        self.right.grid(row=0, column=1, sticky="nsew")

        self.detail_title = ctk.CTkLabel(self.right, text="Select a habit", font=("Segoe UI", 16, "bold"))
        self.detail_title.pack(anchor="w", padx=16, pady=(16, 4))

        self.keyword_label = ctk.CTkLabel(self.right, text="", text_color="#8b949e", font=("Segoe UI", 11))
        self.keyword_label.pack(anchor="w", padx=16)

        keyword_row = ctk.CTkFrame(self.right, fg_color="transparent")
        keyword_row.pack(anchor="w", padx=16, pady=(6, 12), fill="x")
        self.new_keyword_entry = ctk.CTkEntry(keyword_row, placeholder_text="Add a variation, e.g. 'coded'", width=220)
        self.new_keyword_entry.pack(side="left", padx=(0, 8))
        ctk.CTkButton(keyword_row, text="Add variation", width=110, command=self._add_keyword).pack(side="left")

        self.grid_container = ctk.CTkFrame(self.right, fg_color="transparent")
        self.grid_container.pack(fill="both", expand=True, padx=16, pady=8)

        ctk.CTkButton(
            self.right, text="Delete this habit", fg_color="#f85149", hover_color="#da3633",
            command=self._delete_selected
        ).pack(anchor="w", padx=16, pady=(0, 16))

        self.refresh_habit_list()

    # ---- Habit list ----

    def refresh_habit_list(self):
        for widget in self.habit_list_frame.winfo_children():
            widget.destroy()

        habits = db.get_habits()
        for habit in habits:
            btn = ctk.CTkButton(
                self.habit_list_frame,
                text=f"{habit['name']}  ·  {habit['category']}",
                anchor="w",
                fg_color="#21262d" if habit["id"] != self.selected_habit_id else "#238636",
                hover_color="#30363d",
                command=lambda h=habit["id"]: self._select_habit(h),
            )
            btn.pack(fill="x", pady=2)

        if self.selected_habit_id and not any(h["id"] == self.selected_habit_id for h in habits):
            self.selected_habit_id = None

        if self.selected_habit_id:
            self._render_detail(self.selected_habit_id)
        elif habits:
            self._select_habit(habits[0]["id"])
        else:
            self.detail_title.configure(text="No habits yet — add one to get started")
            self.keyword_label.configure(text="")
            if self.grid_widget:
                self.grid_widget.destroy()
                self.grid_widget = None

    def _select_habit(self, habit_id):
        self.selected_habit_id = habit_id
        self.refresh_habit_list()

    def _render_detail(self, habit_id):
        habit = db.get_habit(habit_id)
        if not habit:
            return
        self.detail_title.configure(text=f"{habit['name']}  ({habit['category']})")
        keywords = habit["keywords"] or "(none yet)"
        self.keyword_label.configure(text=f"Keywords: {keywords}")

        if self.grid_widget:
            self.grid_widget.destroy()
        self.grid_widget = HabitGrid(self.grid_container, category=habit["category"])
        self.grid_widget.pack(fill="x")
        self.grid_widget.refresh(db.get_habit_records(habit_id))

    def _add_keyword(self):
        text = self.new_keyword_entry.get().strip()
        if not text or not self.selected_habit_id:
            return
        habit = db.get_habit(self.selected_habit_id)
        existing = [k for k in habit["keywords"].split(",") if k]
        existing.append(text)
        db.update_habit_keywords(self.selected_habit_id, existing)
        self.new_keyword_entry.delete(0, "end")
        self._render_detail(self.selected_habit_id)  # rescan already ran inside update_habit_keywords

    def _delete_selected(self):
        if not self.selected_habit_id:
            return
        db.delete_habit(self.selected_habit_id)
        self.selected_habit_id = None
        self.refresh_habit_list()

    # ---- Add habit dialog ----

    def _open_add_dialog(self):
        dialog = ctk.CTkToplevel(self)
        dialog.title("Add Habit")
        dialog.geometry("340x300")
        dialog.grab_set()

        ctk.CTkLabel(dialog, text="Habit name").pack(anchor="w", padx=16, pady=(16, 0))
        name_entry = ctk.CTkEntry(dialog, width=280)
        name_entry.pack(padx=16, pady=4)

        ctk.CTkLabel(dialog, text="Category").pack(anchor="w", padx=16, pady=(8, 0))
        category_var = ctk.StringVar(value=CATEGORIES[0])
        ctk.CTkOptionMenu(dialog, values=CATEGORIES, variable=category_var, width=280).pack(padx=16, pady=4)

        ctk.CTkLabel(dialog, text="Keywords (comma-separated)").pack(anchor="w", padx=16, pady=(8, 0))
        keywords_entry = ctk.CTkEntry(dialog, width=280, placeholder_text="gym, workout, exercised")
        keywords_entry.pack(padx=16, pady=4)

        def submit():
            name = name_entry.get().strip()
            if not name:
                return
            keywords = [k.strip() for k in keywords_entry.get().split(",") if k.strip()]
            db.add_habit(name, category_var.get(), keywords)
            dialog.destroy()
            self.refresh_habit_list()

        ctk.CTkButton(dialog, text="Create Habit", command=submit).pack(pady=16)
