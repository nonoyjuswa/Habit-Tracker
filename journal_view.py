import customtkinter as ctk
from datetime import datetime
import database as db
from date_utils import recent_days, today_str

VISIBLE_DAYS = 30


class JournalView(ctk.CTkFrame):
    def __init__(self, master, **kwargs):
        super().__init__(master, fg_color="transparent", **kwargs)
        self.selected_date = today_str()

        ctk.CTkLabel(self, text="Journal Timeline", font=("Segoe UI", 14, "bold")).pack(
            anchor="w", padx=4, pady=(4, 8)
        )

        self.timeline_frame = ctk.CTkScrollableFrame(
            self, orientation="horizontal", height=70, fg_color="#161b22"
        )
        self.timeline_frame.pack(fill="x", padx=4, pady=(0, 12))

        # --- Detail / entry panel below the timeline ---
        self.detail_panel = ctk.CTkFrame(self, fg_color="#161b22")
        self.detail_panel.pack(fill="both", expand=True, padx=4)

        self.detail_title = ctk.CTkLabel(self.detail_panel, text="", font=("Segoe UI", 13, "bold"))
        self.detail_title.pack(anchor="w", padx=16, pady=(16, 4))

        self.readonly_text = ctk.CTkTextbox(self.detail_panel, height=140, state="disabled")
        self.entry_text = ctk.CTkTextbox(self.detail_panel, height=140)
        self.register_btn = ctk.CTkButton(self.detail_panel, text="Register today's note", command=self._register_note)
        self.status_label = ctk.CTkLabel(self.detail_panel, text="", text_color="#8b949e")

        self.refresh()

    def refresh(self):
        for widget in self.timeline_frame.winfo_children():
            widget.destroy()

        days = recent_days(VISIBLE_DAYS)
        today = today_str()

        for day_str in days:
            note = db.get_note(day_str)
            is_today = day_str == today

            if is_today:
                fill = "#0d1117" if not note else "#238636"
                border = 2
            else:
                fill = "#238636" if note else "#21262d"
                border = 0

            dot = ctk.CTkButton(
                self.timeline_frame,
                text=day_str[-2:],  # just the day number, compact
                width=34, height=34, corner_radius=17,
                fg_color=fill,
                border_width=border,
                border_color="#22d3ee",
                hover_color="#30363d",
                font=("Segoe UI", 10),
                command=lambda d=day_str: self._select_day(d),
            )
            dot.pack(side="left", padx=3, pady=15)

        self._select_day(self.selected_date if self.selected_date in days else today)

    def _select_day(self, day_str):
        self.selected_date = day_str
        note = db.get_note(day_str)
        is_today = day_str == today_str()

        self.readonly_text.pack_forget()
        self.entry_text.pack_forget()
        self.register_btn.pack_forget()
        self.status_label.pack_forget()

        self.detail_title.configure(text=day_str + (" (Today)" if is_today else ""))

        if note:
            self.readonly_text.configure(state="normal")
            self.readonly_text.delete("1.0", "end")
            self.readonly_text.insert("1.0", f"[{note['time']}] {note['description']}")
            self.readonly_text.configure(state="disabled")
            self.readonly_text.pack(fill="both", expand=True, padx=16, pady=8)
            if is_today:
                self.status_label.configure(text="Today's note is locked in — nice.")
                self.status_label.pack(anchor="w", padx=16, pady=(0, 12))
        elif is_today:
            self.entry_text.delete("1.0", "end")
            self.entry_text.pack(fill="both", expand=True, padx=16, pady=8)
            self.register_btn.pack(anchor="e", padx=16, pady=(0, 16))
        else:
            self.readonly_text.configure(state="normal")
            self.readonly_text.delete("1.0", "end")
            self.readonly_text.insert("1.0", "(No note was recorded for this day.)")
            self.readonly_text.configure(state="disabled")
            self.readonly_text.pack(fill="both", expand=True, padx=16, pady=8)

    def _register_note(self):
        text = self.entry_text.get("1.0", "end").strip()
        if not text:
            return
        now_time = datetime.now().strftime("%H:%M")
        try:
            db.add_note(today_str(), now_time, text)
        except ValueError:
            pass  # already exists — shouldn't happen since UI hides the form once locked
        self.refresh()
