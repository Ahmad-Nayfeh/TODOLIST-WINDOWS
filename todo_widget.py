"""Todo Widget - a small always-on-top to-do list for the desktop.

Tasks are saved automatically to:
    Windows: %APPDATA%\\TodoWidget\\tasks.json
    Other:   ~/.todo_widget/tasks.json
"""

import json
import os
import sys
import tkinter as tk

APP_NAME = "TodoWidget"

# Colors
BG = "#1e1f26"
HEADER_BG = "#2a2c36"
CARD_BG = "#2f3240"
CARD_HOVER = "#383b4c"
TEXT = "#e8e8ee"
MUTED = "#8a8da0"
ACCENT = "#5b8def"
DANGER = "#e5534b"
FONT = "Segoe UI" if sys.platform == "win32" else "Helvetica"


def data_dir():
    if sys.platform == "win32":
        base = os.environ.get("APPDATA") or os.path.expanduser("~")
        path = os.path.join(base, APP_NAME)
    else:
        path = os.path.join(os.path.expanduser("~"), ".todo_widget")
    os.makedirs(path, exist_ok=True)
    return path


DATA_FILE = os.path.join(data_dir(), "tasks.json")


def load_state():
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            state = json.load(f)
        if isinstance(state, dict) and isinstance(state.get("tasks"), list):
            return state
    except (OSError, ValueError):
        pass
    return {"tasks": [], "geometry": "300x420+80+80", "on_top": True}


def save_state(state):
    tmp = DATA_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)
    os.replace(tmp, DATA_FILE)


class TodoWidget:
    def __init__(self, root):
        self.root = root
        self.state = load_state()
        self._drag = None
        self._resize = None

        root.title("Todo Widget")
        root.configure(bg=BG)
        root.overrideredirect(True)  # frameless, widget-like
        root.geometry(self.state.get("geometry", "300x420+80+80"))
        root.minsize(220, 200)
        root.attributes("-topmost", self.state.get("on_top", True))
        try:
            root.attributes("-alpha", 0.96)
        except tk.TclError:
            pass

        self._build_header()
        self._build_input()
        self._build_list()
        self._build_footer()
        self.render()

        root.bind("<Escape>", lambda e: self.root.focus_set())
        root.protocol("WM_DELETE_WINDOW", self.quit)
        self.entry.focus_set()

    # ---------- UI building ----------
    def _build_header(self):
        h = tk.Frame(self.root, bg=HEADER_BG, height=32)
        h.pack(fill="x")
        h.pack_propagate(False)

        title = tk.Label(h, text="✔  To-Do", bg=HEADER_BG, fg=TEXT,
                         font=(FONT, 10, "bold"))
        title.pack(side="left", padx=10)

        close = self._icon_button(h, "✕", self.quit, hover=DANGER)
        close.pack(side="right", padx=(0, 4))
        mini = self._icon_button(h, "—", self.minimize)
        mini.pack(side="right")
        self.pin_btn = self._icon_button(h, "📌", self.toggle_on_top)
        self.pin_btn.pack(side="right")
        self._update_pin()

        for w in (h, title):
            w.bind("<ButtonPress-1>", self._start_drag)
            w.bind("<B1-Motion>", self._on_drag)
            w.bind("<ButtonRelease-1>", lambda e: self._save_geometry())

    def _build_input(self):
        f = tk.Frame(self.root, bg=BG)
        f.pack(fill="x", padx=10, pady=(10, 6))
        self.entry = tk.Entry(f, bg=CARD_BG, fg=TEXT, insertbackground=TEXT,
                              relief="flat", font=(FONT, 10),
                              highlightthickness=1, highlightcolor=ACCENT,
                              highlightbackground=CARD_BG)
        self.entry.pack(side="left", fill="x", expand=True, ipady=5)
        self.entry.bind("<Return>", lambda e: self.add_task())
        self._placeholder = "Add a task and press Enter…"
        self._show_placeholder()
        self.entry.bind("<FocusIn>", lambda e: self._hide_placeholder())
        self.entry.bind("<FocusOut>", lambda e: self._show_placeholder())

        add = tk.Label(f, text="+", bg=ACCENT, fg="white", width=3,
                       font=(FONT, 12, "bold"), cursor="hand2")
        add.pack(side="left", padx=(6, 0), fill="y")
        add.bind("<Button-1>", lambda e: self.add_task())

    def _build_list(self):
        wrap = tk.Frame(self.root, bg=BG)
        wrap.pack(fill="both", expand=True, padx=(10, 2))
        self.canvas = tk.Canvas(wrap, bg=BG, highlightthickness=0, bd=0)
        sb = tk.Scrollbar(wrap, orient="vertical", command=self.canvas.yview)
        self.canvas.configure(yscrollcommand=sb.set)
        sb.pack(side="right", fill="y")
        self.canvas.pack(side="left", fill="both", expand=True)

        self.list_frame = tk.Frame(self.canvas, bg=BG)
        self._win = self.canvas.create_window((0, 0), window=self.list_frame,
                                              anchor="nw")
        self.list_frame.bind("<Configure>", lambda e: self.canvas.configure(
            scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfigure(
            self._win, width=e.width))
        self.root.bind_all("<MouseWheel>", self._on_wheel)          # Windows
        self.root.bind_all("<Button-4>", lambda e: self.canvas.yview_scroll(-1, "units"))
        self.root.bind_all("<Button-5>", lambda e: self.canvas.yview_scroll(1, "units"))

    def _build_footer(self):
        f = tk.Frame(self.root, bg=BG)
        f.pack(fill="x", padx=10, pady=(4, 6))
        self.count_lbl = tk.Label(f, text="", bg=BG, fg=MUTED, font=(FONT, 8))
        self.count_lbl.pack(side="left")
        clear = tk.Label(f, text="Clear done", bg=BG, fg=MUTED,
                         font=(FONT, 8, "underline"), cursor="hand2")
        clear.pack(side="right", padx=(0, 14))
        clear.bind("<Button-1>", lambda e: self.clear_done())

        grip = tk.Label(f, text="◢", bg=BG, fg=MUTED, cursor="size_nw_se" if sys.platform == "win32"
                        else "bottom_right_corner",
                        font=(FONT, 9))
        grip.place(relx=1.0, rely=1.0, anchor="se")
        grip.bind("<ButtonPress-1>", self._start_resize)
        grip.bind("<B1-Motion>", self._on_resize)
        grip.bind("<ButtonRelease-1>", lambda e: self._save_geometry())

    def _icon_button(self, parent, text, cmd, hover=CARD_HOVER):
        b = tk.Label(parent, text=text, bg=HEADER_BG, fg=TEXT, width=3,
                     font=(FONT, 9), cursor="hand2")
        b.bind("<Button-1>", lambda e: cmd())
        b.bind("<Enter>", lambda e: b.configure(bg=hover))
        b.bind("<Leave>", lambda e: b.configure(bg=HEADER_BG))
        return b

    # ---------- placeholder ----------
    def _show_placeholder(self):
        if not self.entry.get():
            self.entry.insert(0, self._placeholder)
            self.entry.configure(fg=MUTED)

    def _hide_placeholder(self):
        if self.entry.get() == self._placeholder and self.entry.cget("fg") == MUTED:
            self.entry.delete(0, "end")
            self.entry.configure(fg=TEXT)

    # ---------- rendering ----------
    def render(self):
        for child in self.list_frame.winfo_children():
            child.destroy()
        tasks = self.state["tasks"]
        if not tasks:
            tk.Label(self.list_frame, text="Nothing to do 🎉", bg=BG, fg=MUTED,
                     font=(FONT, 10)).pack(pady=30)
        # Open tasks first, then done tasks
        order = [i for i, t in enumerate(tasks) if not t["done"]] + \
                [i for i, t in enumerate(tasks) if t["done"]]
        for i in order:
            self._task_row(i, tasks[i])
        done = sum(t["done"] for t in tasks)
        self.count_lbl.configure(text=f"{len(tasks) - done} left · {done} done")

    def _task_row(self, index, task):
        row = tk.Frame(self.list_frame, bg=CARD_BG)
        row.pack(fill="x", pady=3, padx=(0, 6))

        box = tk.Label(row, text="☑" if task["done"] else "☐", bg=CARD_BG,
                       fg=ACCENT if task["done"] else TEXT,
                       font=(FONT, 12), cursor="hand2")
        box.pack(side="left", padx=(8, 4), pady=4)

        font = (FONT, 10, "overstrike") if task["done"] else (FONT, 10)
        lbl = tk.Label(row, text=task["text"], bg=CARD_BG,
                       fg=MUTED if task["done"] else TEXT, font=font,
                       anchor="w", justify="left", wraplength=180)
        lbl.pack(side="left", fill="x", expand=True, pady=4)

        delete = tk.Label(row, text="✕", bg=CARD_BG, fg=MUTED,
                          font=(FONT, 9), cursor="hand2")
        delete.pack(side="right", padx=8)

        widgets = (row, box, lbl, delete)

        def hover(color):
            for w in widgets:
                w.configure(bg=color)

        for w in widgets:
            w.bind("<Enter>", lambda e: hover(CARD_HOVER))
            w.bind("<Leave>", lambda e: hover(CARD_BG))
        for w in (box, lbl):
            w.bind("<Button-1>", lambda e, i=index: self.toggle(i))
        lbl.bind("<Double-Button-1>", lambda e, i=index, r=row, l=lbl:
                 self.edit(i, r, l))
        delete.bind("<Button-1>", lambda e, i=index: self.delete(i))
        delete.bind("<Enter>", lambda e: (hover(CARD_HOVER),
                                          delete.configure(fg=DANGER)))
        delete.bind("<Leave>", lambda e: (hover(CARD_BG),
                                          delete.configure(fg=MUTED)))
        row.bind("<Configure>", lambda e, l=lbl: l.configure(
            wraplength=max(80, e.width - 70)))

    # ---------- actions ----------
    def add_task(self):
        self._hide_placeholder()
        text = self.entry.get().strip()
        if not text:
            return
        self.state["tasks"].insert(0, {"text": text, "done": False})
        self.entry.delete(0, "end")
        self.persist()
        self.render()
        self.canvas.update_idletasks()
        self.canvas.yview_moveto(0)

    def toggle(self, i):
        self.state["tasks"][i]["done"] = not self.state["tasks"][i]["done"]
        self.persist()
        self.render()

    def delete(self, i):
        del self.state["tasks"][i]
        self.persist()
        self.render()

    def edit(self, i, row, lbl):
        lbl.pack_forget()
        e = tk.Entry(row, bg=CARD_HOVER, fg=TEXT, insertbackground=TEXT,
                     relief="flat", font=(FONT, 10))
        e.insert(0, self.state["tasks"][i]["text"])
        e.pack(side="left", fill="x", expand=True, pady=4)
        e.focus_set()
        e.select_range(0, "end")

        done = []

        def commit(_=None):
            if done:  # Return and FocusOut can both fire
                return
            done.append(True)
            text = e.get().strip()
            if text:
                self.state["tasks"][i]["text"] = text
                self.persist()
            self.render()

        e.bind("<Return>", commit)
        e.bind("<FocusOut>", commit)
        e.bind("<Escape>", lambda _: (done.append(True), self.render()))

    def clear_done(self):
        self.state["tasks"] = [t for t in self.state["tasks"] if not t["done"]]
        self.persist()
        self.render()

    def toggle_on_top(self):
        self.state["on_top"] = not self.state.get("on_top", True)
        self.root.attributes("-topmost", self.state["on_top"])
        self._update_pin()
        self.persist()

    def _update_pin(self):
        self.pin_btn.configure(fg=TEXT if self.state.get("on_top", True)
                               else MUTED)

    def minimize(self):
        # Frameless windows can't be iconified directly; briefly restore
        # the frame so the window goes to the taskbar.
        self.root.overrideredirect(False)
        self.root.iconify()
        self.root.bind("<Map>", self._on_restore)

    def _on_restore(self, _=None):
        if self.root.state() == "normal":
            self.root.unbind("<Map>")
            self.root.overrideredirect(True)
            self.root.attributes("-topmost", self.state.get("on_top", True))

    def quit(self):
        self._save_geometry()
        self.root.destroy()

    def persist(self):
        try:
            save_state(self.state)
        except OSError:
            pass

    # ---------- move / resize ----------
    def _start_drag(self, e):
        self._drag = (e.x_root - self.root.winfo_x(),
                      e.y_root - self.root.winfo_y())

    def _on_drag(self, e):
        if self._drag:
            dx, dy = self._drag
            self.root.geometry(f"+{e.x_root - dx}+{e.y_root - dy}")

    def _start_resize(self, e):
        self._resize = (e.x_root, e.y_root,
                        self.root.winfo_width(), self.root.winfo_height())

    def _on_resize(self, e):
        if self._resize:
            x0, y0, w0, h0 = self._resize
            w = max(220, w0 + e.x_root - x0)
            h = max(200, h0 + e.y_root - y0)
            self.root.geometry(f"{w}x{h}")

    def _save_geometry(self):
        self.state["geometry"] = self.root.geometry()
        self.persist()

    def _on_wheel(self, e):
        self.canvas.yview_scroll(int(-e.delta / 120), "units")


def main():
    if sys.platform == "win32":
        try:  # crisp text on high-DPI screens
            import ctypes
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            pass
    root = tk.Tk()
    TodoWidget(root)
    root.mainloop()


if __name__ == "__main__":
    main()
