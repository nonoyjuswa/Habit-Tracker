import customtkinter as ctk


class KeywordChip(ctk.CTkFrame):
    """One keyword pill. Hovering anywhere over it reveals a small edit (✏)
    and remove (✕) button; moving the mouse fully off the chip hides them
    again. Uses a short delayed recheck so moving onto the icons themselves
    doesn't cause them to vanish before you can click them."""

    def __init__(self, master, keyword: str, on_edit, on_remove, **kwargs):
        super().__init__(master, fg_color="#21262d", corner_radius=12, **kwargs)
        self.keyword = keyword
        self.on_edit = on_edit
        self.on_remove = on_remove

        self.label = ctk.CTkLabel(
            self, text=keyword, text_color="#c9d1d9", font=("Segoe UI", 11)
        )
        self.label.pack(side="left", padx=(10, 4), pady=4)

        self.icon_frame = ctk.CTkFrame(self, fg_color="transparent")
        self.edit_btn = ctk.CTkButton(
            self.icon_frame, text="✏", width=20, height=20, corner_radius=10,
            fg_color="#30363d", hover_color="#388bfd", font=("Segoe UI", 9),
            command=lambda: self.on_edit(self.keyword),
        )
        self.edit_btn.pack(side="left", padx=(0, 3))
        self.remove_btn = ctk.CTkButton(
            self.icon_frame, text="✕", width=20, height=20, corner_radius=10,
            fg_color="#30363d", hover_color="#f85149", font=("Segoe UI", 9),
            command=lambda: self.on_remove(self.keyword),
        )
        self.remove_btn.pack(side="left", padx=(0, 6))
        # icon_frame intentionally not packed yet — hidden until hovered

        for widget in (self, self.label, self.icon_frame, self.edit_btn, self.remove_btn):
            widget.bind("<Enter>", self._on_enter)
            widget.bind("<Leave>", self._on_leave)

    def _on_enter(self, event=None):
        if not self.icon_frame.winfo_ismapped():
            self.icon_frame.pack(side="left")

    def _on_leave(self, event=None):
        # Don't hide immediately — the mouse might just be crossing from
        # the label onto the icon buttons, which are separate widgets.
        self.after(80, self._hide_if_truly_left)

    def _hide_if_truly_left(self):
        try:
            x, y = self.winfo_pointerxy()
            widget_under_pointer = self.winfo_containing(x, y)
        except Exception:
            widget_under_pointer = None

        w = widget_under_pointer
        while w is not None:
            if w == self:
                return  # pointer is still somewhere inside this chip
            w = getattr(w, "master", None)

        if self.icon_frame.winfo_ismapped():
            self.icon_frame.pack_forget()