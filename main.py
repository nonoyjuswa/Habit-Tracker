import customtkinter as ctk
import database as db
from journal_view import JournalView
from habits_view import HabitsView

ctk.set_appearance_mode("dark")
ctk.set_default_color_theme("green")


class App(ctk.CTk):
    def __init__(self):
        super().__init__()
        self.title("Habit Journal")
        self.geometry("980x680")
        self.configure(fg_color="#0d1117")

        db.init_db()

        header = ctk.CTkLabel(
            self, text="📓 Habit Journal", font=("Segoe UI", 20, "bold")
        )
        header.pack(anchor="w", padx=20, pady=(16, 4))

        self.tabs = ctk.CTkTabview(self, fg_color="#0d1117")
        self.tabs.pack(fill="both", expand=True, padx=16, pady=(0, 16))
        self.tabs.add("Journal")
        self.tabs.add("Habits")

        JournalView(self.tabs.tab("Journal")).pack(fill="both", expand=True, padx=8, pady=8)
        HabitsView(self.tabs.tab("Habits")).pack(fill="both", expand=True, padx=8, pady=8)


if __name__ == "__main__":
    app = App()
    app.mainloop()
