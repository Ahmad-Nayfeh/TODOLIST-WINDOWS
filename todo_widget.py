"""Todo Widget - a small to-do list that lives on the Windows desktop.

Tasks and settings are saved automatically to:
    Windows: %APPDATA%\\TodoWidget\\tasks.json
    Other:   ~/.todo_widget/tasks.json
"""

import json
import os
import sys
import tkinter as tk
from datetime import datetime

APP_NAME = "TodoWidget"
WINDOW_TITLE = "Todo Widget"
IS_WIN = sys.platform == "win32"

if IS_WIN:
    import ctypes
    from ctypes import wintypes

THEMES = {
    "dark": {
        "bg": "#16171d", "surface": "#20222b", "hover": "#2a2d38",
        "border": "#2e313d", "text": "#eceef4", "muted": "#8b8fa3",
        "subtle": "#5d6173", "danger": "#ef5b5b", "star": "#f5b942",
    },
    "light": {
        "bg": "#f6f7fb", "surface": "#ffffff", "hover": "#eef0f6",
        "border": "#dfe2ea", "text": "#1d2030", "muted": "#6b7085",
        "subtle": "#a3a8b8", "danger": "#e5484d", "star": "#e8a317",
    },
}
ACCENTS = {
    "Blue": "#5b8def", "Purple": "#9b6dff", "Teal": "#2fb8a4",
    "Pink": "#ec5f9a", "Orange": "#f08c3a", "Green": "#4caf6e",
}

FONT = "Segoe UI" if IS_WIN else "Helvetica"
# Segoe MDL2 Assets ships with Windows 10/11; plain symbols elsewhere.
ICON_FONT = "Segoe MDL2 Assets" if IS_WIN else FONT
ICONS = {
    "more": "" if IS_WIN else "⋯",
    "up": "" if IS_WIN else "▴",
    "down": "" if IS_WIN else "▾",
    "add": "" if IS_WIN else "+",
    "close": "" if IS_WIN else "✕",
    "star": "" if IS_WIN else "☆",
    "star_on": "" if IS_WIN else "★",
    "lock": "" if IS_WIN else "🔒",
}

DEFAULT_STATE = {
    "tasks": [],
    "geometry": None,
    "mode": "desktop",        # "desktop" or "top"
    "theme": "dark",
    "accent": "Blue",
    "alpha": 0.97,
    "locked": False,
    "collapsed": False,
    "autostart_initialized": False,
}


# ---------------------------------------------------------------- storage
def data_dir():
    if IS_WIN:
        base = os.environ.get("APPDATA") or os.path.expanduser("~")
        path = os.path.join(base, APP_NAME)
    else:
        path = os.path.join(os.path.expanduser("~"), ".todo_widget")
    os.makedirs(path, exist_ok=True)
    return path


DATA_FILE = os.path.join(data_dir(), "tasks.json")


def load_state():
    state = dict(DEFAULT_STATE)
    try:
        with open(DATA_FILE, "r", encoding="utf-8") as f:
            saved = json.load(f)
        if isinstance(saved, dict) and isinstance(saved.get("tasks"), list):
            state.update(saved)
    except (OSError, ValueError):
        pass
    state.pop("on_top", None)  # setting from version 1
    for t in state["tasks"]:
        t.setdefault("done", False)
        t.setdefault("star", False)
    if state["theme"] not in THEMES:
        state["theme"] = "dark"
    if state["accent"] not in ACCENTS:
        state["accent"] = "Blue"
    return state


def save_state(state):
    tmp = DATA_FILE + ".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(state, f, ensure_ascii=False, indent=2)
    os.replace(tmp, DATA_FILE)


def is_rtl(text):
    return any("֐" <= c <= "ࣿ" or "יִ" <= c <= "ﻼ"
               for c in text)


# ---------------------------------------------------------------- Windows
class WinDesktop:
    """Windows-only helpers: desktop pinning, autostart, single instance."""

    GWLP_HWNDPARENT = -8
    HWND_TOP, HWND_BOTTOM, HWND_TOPMOST, HWND_NOTOPMOST = 0, 1, -1, -2
    SWP_NOSIZE, SWP_NOMOVE, SWP_NOACTIVATE = 0x1, 0x2, 0x10
    RUN_KEY = r"Software\Microsoft\Windows\CurrentVersion\Run"
    DESKTOP_CLASSES = ("Progman", "WorkerW")

    def __init__(self):
        u = ctypes.WinDLL("user32", use_last_error=True)
        self.u = u
        u.GetParent.argtypes = [wintypes.HWND]
        u.GetParent.restype = wintypes.HWND
        u.FindWindowW.argtypes = [wintypes.LPCWSTR, wintypes.LPCWSTR]
        u.FindWindowW.restype = wintypes.HWND
        u.GetForegroundWindow.restype = wintypes.HWND
        u.GetClassNameW.argtypes = [wintypes.HWND, wintypes.LPWSTR, ctypes.c_int]
        u.GetWindowThreadProcessId.argtypes = [wintypes.HWND,
                                               ctypes.POINTER(wintypes.DWORD)]
        u.SetWindowPos.argtypes = [wintypes.HWND, wintypes.HWND, ctypes.c_int,
                                   ctypes.c_int, ctypes.c_int, ctypes.c_int,
                                   ctypes.c_uint]
        u.GetWindowLongW.argtypes = [wintypes.HWND, ctypes.c_int]
        u.GetWindowLongW.restype = ctypes.c_long
        u.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
        u.SetForegroundWindow.argtypes = [wintypes.HWND]
        if ctypes.sizeof(ctypes.c_void_p) == 8:
            self._set_long = u.SetWindowLongPtrW
        else:
            self._set_long = u.SetWindowLongW
        self._set_long.argtypes = [wintypes.HWND, ctypes.c_int, ctypes.c_void_p]
        self._set_long.restype = ctypes.c_void_p
        self.pid = os.getpid()

    # --- z-order -----------------------------------------------------
    def progman(self):
        return self.u.FindWindowW("Progman", None)

    def set_owner(self, hwnd, owner):
        # Windows owned by the desktop are not hidden by "Show desktop".
        self._set_long(hwnd, self.GWLP_HWNDPARENT, owner or 0)

    def _pos(self, hwnd, after):
        flags = self.SWP_NOMOVE | self.SWP_NOSIZE | self.SWP_NOACTIVATE
        self.u.SetWindowPos(hwnd, after, 0, 0, 0, 0, flags)

    def set_topmost(self, hwnd, on):
        self._pos(hwnd, self.HWND_TOPMOST if on else self.HWND_NOTOPMOST)

    def is_topmost(self, hwnd):
        return bool(self.u.GetWindowLongW(hwnd, -20) & 0x8)  # WS_EX_TOPMOST

    def place_behind(self, hwnd, other):
        self._pos(hwnd, self.HWND_NOTOPMOST)
        self._pos(hwnd, other)

    def foreground(self):
        """Return (hwnd, is_desktop, is_own_process) for the active window."""
        fg = self.u.GetForegroundWindow()
        if not fg:
            return None, False, False
        buf = ctypes.create_unicode_buffer(64)
        self.u.GetClassNameW(fg, buf, 64)
        pid = wintypes.DWORD()
        self.u.GetWindowThreadProcessId(fg, ctypes.byref(pid))
        return fg, buf.value in self.DESKTOP_CLASSES, pid.value == self.pid

    @staticmethod
    def round_corners(hwnd):
        try:  # Windows 11 only; silently ignored elsewhere
            pref = ctypes.c_int(2)  # DWMWCP_ROUND
            ctypes.windll.dwmapi.DwmSetWindowAttribute(
                wintypes.HWND(hwnd), 33, ctypes.byref(pref), 4)
        except Exception:
            pass

    # --- autostart ---------------------------------------------------
    @staticmethod
    def exe_path():
        return sys.executable if getattr(sys, "frozen", False) else None

    def autostart_enabled(self):
        import winreg
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, self.RUN_KEY) as k:
                winreg.QueryValueEx(k, APP_NAME)
            return True
        except OSError:
            return False

    def set_autostart(self, enable):
        import winreg
        exe = self.exe_path()
        try:
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, self.RUN_KEY, 0,
                                winreg.KEY_SET_VALUE) as k:
                if enable and exe:
                    winreg.SetValueEx(k, APP_NAME, 0, winreg.REG_SZ,
                                      f'"{exe}"')
                elif not enable:
                    winreg.DeleteValue(k, APP_NAME)
            return True
        except OSError:
            return False

    # --- single instance ---------------------------------------------
    def already_running(self):
        k32 = ctypes.WinDLL("kernel32", use_last_error=True)
        k32.CreateMutexW.restype = wintypes.HANDLE
        self._mutex = k32.CreateMutexW(None, False, "Local\\TodoWidgetMutex")
        return ctypes.get_last_error() == 183  # ERROR_ALREADY_EXISTS

    def show_existing(self):
        hwnd = self.u.FindWindowW(None, WINDOW_TITLE)
        if hwnd:
            self.u.ShowWindow(hwnd, 9)  # SW_RESTORE
            self.u.SetForegroundWindow(hwnd)


# ---------------------------------------------------------------- widget
class RoundCheck(tk.Canvas):
    """A round checkbox drawn on a canvas."""

    def __init__(self, parent, size, done, colors, accent, command):
        super().__init__(parent, width=size, height=size, bg=colors["surface"],
                         highlightthickness=0, bd=0, cursor="hand2")
        self.size, self.done, self.c, self.accent = size, done, colors, accent
        self.hovered = False
        self.bind("<Button-1>", lambda e: command())
        self.draw()

    def set_bg(self, color):
        self.configure(bg=color)

    def draw(self):
        self.delete("all")
        s, p = self.size, 2
        if self.done:
            self.create_oval(p, p, s - p, s - p, fill=self.accent,
                             outline=self.accent)
            w = max(2, s // 9)
            self.create_line(s * .30, s * .52, s * .45, s * .67, s * .72, s * .36,
                             fill="white", width=w, capstyle="round",
                             joinstyle="round")
        else:
            color = self.accent if self.hovered else self.c["subtle"]
            self.create_oval(p, p, s - p, s - p, outline=color, width=2)

    def hover(self, on):
        self.hovered = on
        self.draw()


class TodoWidget:
    def __init__(self, root, win=None):
        self.root = root
        self.win = win
        self.state = load_state()
        self.s = root.winfo_fpixels("1i") / 96.0  # DPI scale
        self._drag = None
        self._resize = None
        self._hwnd = None
        self._owner = None
        self._raised = False

        root.title(WINDOW_TITLE)
        root.overrideredirect(True)
        geo = self.state.get("geometry") or "{}x{}+{}+{}".format(
            self.px(310), self.px(440),
            root.winfo_screenwidth() - self.px(350), self.px(60))
        root.geometry(geo)
        root.minsize(self.px(240), self.px(52))
        self.apply_alpha()

        self.build_ui()
        root.protocol("WM_DELETE_WINDOW", self.quit)
        root.update_idletasks()

        if self.win:
            self._hwnd = self.win.u.GetParent(root.winfo_id())
            self.win.round_corners(self._hwnd)
            self._first_run_autostart()
        self.apply_mode()
        self._tick_clock()

    def px(self, v):
        return int(round(v * self.s))

    @property
    def c(self):
        return THEMES[self.state["theme"]]

    @property
    def accent(self):
        return ACCENTS[self.state["accent"]]

    # ---------------------------------------------------------------- UI
    def build_ui(self):
        for child in self.root.winfo_children():
            child.destroy()
        c = self.c
        self.root.configure(bg=c["border"])
        self.shell = tk.Frame(self.root, bg=c["bg"])
        self.shell.pack(fill="both", expand=True, padx=1, pady=1)
        self._build_header()
        self.body = tk.Frame(self.shell, bg=c["bg"])
        self._build_progress()
        self._build_input()
        self._build_list()
        self._build_footer()
        self._build_menu()
        if not self.state["collapsed"]:
            self.body.pack(fill="both", expand=True)
        self._update_date()
        self.render()

    def _build_header(self):
        c = self.c
        h = tk.Frame(self.shell, bg=c["bg"])
        h.pack(fill="x", padx=self.px(14), pady=(self.px(12), self.px(6)))
        self.header = h

        left = tk.Frame(h, bg=c["bg"])
        left.pack(side="left", fill="x", expand=True)
        self.title_lbl = tk.Label(left, text="My Tasks", bg=c["bg"],
                                  fg=c["text"], font=(FONT, 15, "bold"))
        self.title_lbl.pack(anchor="w")
        self.date_lbl = tk.Label(left, text="", bg=c["bg"], fg=self.accent,
                                 font=(FONT, 9, "bold"))
        self.date_lbl.pack(anchor="w")

        self.more_btn = self._icon_btn(h, ICONS["more"], self.show_menu)
        self.more_btn.pack(side="right", anchor="n")
        self.collapse_btn = self._icon_btn(
            h, ICONS["down"] if self.state["collapsed"] else ICONS["up"],
            self.toggle_collapse)
        self.collapse_btn.pack(side="right", anchor="n")
        if self.state["locked"]:
            tk.Label(h, text=ICONS["lock"], bg=c["bg"], fg=c["subtle"],
                     font=(ICON_FONT, 8)).pack(side="right", anchor="n",
                                               pady=self.px(6))

        for w in (h, left, self.title_lbl, self.date_lbl):
            w.bind("<ButtonPress-1>", self._start_drag)
            w.bind("<B1-Motion>", self._on_drag)
            w.bind("<ButtonRelease-1>", lambda e: self._save_geometry())
            w.bind("<Button-3>", lambda e: self.show_menu(e))

    def _build_progress(self):
        c = self.c
        f = tk.Frame(self.body, bg=c["bg"])
        f.pack(fill="x", padx=self.px(14), pady=(0, self.px(10)))
        self.progress = tk.Canvas(f, height=self.px(6), bg=c["bg"],
                                  highlightthickness=0, bd=0)
        self.progress.pack(fill="x", side="left", expand=True,
                           pady=self.px(5))
        self.progress_lbl = tk.Label(f, text="", bg=c["bg"], fg=c["muted"],
                                     font=(FONT, 8))
        self.progress_lbl.pack(side="right", padx=(self.px(8), 0))
        self.progress.bind("<Configure>", lambda e: self._draw_progress())

    def _build_input(self):
        c = self.c
        box = tk.Frame(self.body, bg=c["surface"],
                       highlightthickness=1, highlightbackground=c["border"],
                       highlightcolor=self.accent)
        box.pack(fill="x", padx=self.px(14), pady=(0, self.px(10)))
        self.entry_box = box
        self.entry = tk.Entry(box, bg=c["surface"], fg=c["text"],
                              insertbackground=c["text"], relief="flat",
                              font=(FONT, 10), bd=0, highlightthickness=0)
        self.entry.pack(side="left", fill="x", expand=True,
                        padx=(self.px(10), 0), ipady=self.px(7))
        self.entry.bind("<Return>", lambda e: self.add_task())
        self.entry.bind("<KeyRelease>", self._entry_direction)
        self._placeholder = "Add a task…"
        self._show_placeholder()
        self.entry.bind("<FocusIn>", self._entry_focus_in)
        self.entry.bind("<FocusOut>", self._entry_focus_out)

        add = tk.Label(box, text=ICONS["add"], bg=self.accent, fg="white",
                       font=(ICON_FONT, 10, "bold"), cursor="hand2",
                       width=3)
        add.pack(side="right", fill="y", padx=self.px(4), pady=self.px(4))
        add.bind("<Button-1>", lambda e: self.add_task())

    def _build_list(self):
        c = self.c
        wrap = tk.Frame(self.body, bg=c["bg"])
        wrap.pack(fill="both", expand=True, padx=(self.px(14), self.px(6)))
        self.canvas = tk.Canvas(wrap, bg=c["bg"], highlightthickness=0, bd=0)
        self.canvas.pack(side="left", fill="both", expand=True)
        self.list_frame = tk.Frame(self.canvas, bg=c["bg"])
        self._win = self.canvas.create_window((0, 0), window=self.list_frame,
                                              anchor="nw")
        self.list_frame.bind("<Configure>", lambda e: self.canvas.configure(
            scrollregion=self.canvas.bbox("all")))
        self.canvas.bind("<Configure>", lambda e: self.canvas.itemconfigure(
            self._win, width=e.width - self.px(8)))
        self.root.bind_all("<MouseWheel>", self._on_wheel)
        self.root.bind_all("<Button-4>", lambda e: self._scroll(-1))
        self.root.bind_all("<Button-5>", lambda e: self._scroll(1))

    def _build_footer(self):
        c = self.c
        f = tk.Frame(self.body, bg=c["bg"])
        f.pack(fill="x", padx=self.px(14), pady=(self.px(4), self.px(8)))
        self.count_lbl = tk.Label(f, text="", bg=c["bg"], fg=c["muted"],
                                  font=(FONT, 8))
        self.count_lbl.pack(side="left")
        self.clear_lbl = tk.Label(f, text="Clear completed", bg=c["bg"],
                                  fg=c["muted"], font=(FONT, 8),
                                  cursor="hand2")
        self.clear_lbl.pack(side="right", padx=(0, self.px(12)))
        self.clear_lbl.bind("<Button-1>", lambda e: self.clear_done())
        self.clear_lbl.bind("<Enter>", lambda e: self.clear_lbl.configure(
            fg=c["danger"]))
        self.clear_lbl.bind("<Leave>", lambda e: self.clear_lbl.configure(
            fg=c["muted"]))

        if not self.state["locked"]:
            grip = tk.Label(f, text="◢", bg=c["bg"], fg=c["subtle"],
                            font=(FONT, 8),
                            cursor="size_nw_se" if IS_WIN
                            else "bottom_right_corner")
            grip.place(relx=1.0, rely=1.0, anchor="se", x=self.px(6))
            grip.bind("<ButtonPress-1>", self._start_resize)
            grip.bind("<B1-Motion>", self._on_resize)
            grip.bind("<ButtonRelease-1>", lambda e: self._save_geometry())

    def _icon_btn(self, parent, text, cmd):
        c = self.c
        b = tk.Label(parent, text=text, bg=c["bg"], fg=c["muted"],
                     font=(ICON_FONT, 10), cursor="hand2", width=3,
                     pady=self.px(3))
        b.bind("<Button-1>", lambda e: cmd(e) if cmd == self.show_menu
               else cmd())
        b.bind("<Enter>", lambda e: b.configure(bg=c["hover"], fg=c["text"]))
        b.bind("<Leave>", lambda e: b.configure(bg=c["bg"], fg=c["muted"]))
        return b

    def _build_menu(self):
        c = self.c
        opts = dict(tearoff=0, bg=c["surface"], fg=c["text"],
                    activebackground=self.accent, activeforeground="white",
                    font=(FONT, 9), bd=0)
        m = tk.Menu(self.root, **opts)
        self.mode_var = tk.StringVar(value=self.state["mode"])
        m.add_radiobutton(label="Pin to desktop", value="desktop",
                          variable=self.mode_var, command=self.set_mode)
        m.add_radiobutton(label="Always on top", value="top",
                          variable=self.mode_var, command=self.set_mode)
        m.add_separator()

        theme = tk.Menu(m, **opts)
        self.theme_var = tk.StringVar(value=self.state["theme"])
        for name in THEMES:
            theme.add_radiobutton(label=name.title(), value=name,
                                  variable=self.theme_var,
                                  command=self.set_theme)
        m.add_cascade(label="Theme", menu=theme)

        accent = tk.Menu(m, **opts)
        self.accent_var = tk.StringVar(value=self.state["accent"])
        for name in ACCENTS:
            accent.add_radiobutton(label=name, value=name,
                                   variable=self.accent_var,
                                   command=self.set_accent)
        m.add_cascade(label="Accent color", menu=accent)

        alpha = tk.Menu(m, **opts)
        self.alpha_var = tk.DoubleVar(value=self.state["alpha"])
        for pct in (100, 95, 90, 85, 80, 70):
            alpha.add_radiobutton(label=f"{pct}%", value=pct / 100,
                                  variable=self.alpha_var,
                                  command=self.set_alpha)
        m.add_cascade(label="Opacity", menu=alpha)
        m.add_separator()

        self.lock_var = tk.BooleanVar(value=self.state["locked"])
        m.add_checkbutton(label="Lock position", variable=self.lock_var,
                          command=self.toggle_lock)
        if self.win and self.win.exe_path():
            self.auto_var = tk.BooleanVar(value=self.win.autostart_enabled())
            m.add_checkbutton(label="Start with Windows",
                              variable=self.auto_var,
                              command=self.toggle_autostart)
        m.add_separator()
        m.add_command(label="Exit", command=self.quit)
        self.menu = m

    def show_menu(self, e=None):
        x = e.x_root if e else self.root.winfo_rootx()
        y = e.y_root if e else self.root.winfo_rooty()
        try:
            self.menu.tk_popup(x, y)
        finally:
            self.menu.grab_release()

    # ---------------------------------------------------------------- entry
    def _show_placeholder(self):
        if not self.entry.get():
            self.entry.insert(0, self._placeholder)
            self.entry.configure(fg=self.c["subtle"], justify="left")

    def _hide_placeholder(self):
        if (self.entry.get() == self._placeholder
                and self.entry.cget("fg") == self.c["subtle"]):
            self.entry.delete(0, "end")
            self.entry.configure(fg=self.c["text"])

    def _entry_focus_in(self, _):
        self._hide_placeholder()
        self.entry_box.configure(highlightbackground=self.accent)

    def _entry_focus_out(self, _):
        self._show_placeholder()
        self.entry_box.configure(highlightbackground=self.c["border"])

    def _entry_direction(self, _):
        self.entry.configure(
            justify="right" if is_rtl(self.entry.get()) else "left")

    # ---------------------------------------------------------------- render
    def render(self):
        c = self.c
        for child in self.list_frame.winfo_children():
            child.destroy()
        tasks = self.state["tasks"]
        if not tasks:
            tk.Label(self.list_frame, text="✨", bg=c["bg"], fg=c["muted"],
                     font=(FONT, 20)).pack(pady=(self.px(30), 0))
            tk.Label(self.list_frame, text="All clear. Add your first task!",
                     bg=c["bg"], fg=c["muted"], font=(FONT, 9)).pack()
        order = sorted(range(len(tasks)), key=lambda i: (
            tasks[i]["done"], not tasks[i]["star"]))
        for i in order:
            self._task_row(i, tasks[i])
        done = sum(1 for t in tasks if t["done"])
        left = len(tasks) - done
        self.count_lbl.configure(
            text=f"{left} task{'s' if left != 1 else ''} left")
        self.progress_lbl.configure(text=f"{done}/{len(tasks)}")
        self._draw_progress()

    def _draw_progress(self):
        p = self.progress
        p.delete("all")
        w, h = p.winfo_width(), p.winfo_height()
        if w <= 1:
            return
        tasks = self.state["tasks"]
        ratio = (sum(1 for t in tasks if t["done"]) / len(tasks)) if tasks else 0
        r = h / 2
        self._pill(p, 0, 0, w, h, r, self.c["hover"])
        if ratio > 0:
            self._pill(p, 0, 0, max(h, w * ratio), h, r, self.accent)

    @staticmethod
    def _pill(cv, x0, y0, x1, y1, r, color):
        cv.create_oval(x0, y0, x0 + 2 * r, y1, fill=color, outline=color)
        cv.create_oval(x1 - 2 * r, y0, x1, y1, fill=color, outline=color)
        cv.create_rectangle(x0 + r, y0, x1 - r, y1, fill=color, outline=color)

    def _task_row(self, index, task):
        c = self.c
        row = tk.Frame(self.list_frame, bg=c["surface"])
        row.pack(fill="x", pady=(0, self.px(6)))
        inner = tk.Frame(row, bg=c["surface"])
        inner.pack(fill="x", padx=self.px(10), pady=self.px(8))

        check = RoundCheck(inner, self.px(20), task["done"], c, self.accent,
                           lambda i=index: self.toggle(i))
        check.pack(side="left", anchor="n", pady=(self.px(1), 0))

        delete = tk.Label(inner, text=ICONS["close"], bg=c["surface"],
                          fg=c["surface"], font=(ICON_FONT, 8),
                          cursor="hand2")
        delete.pack(side="right", anchor="n", padx=(self.px(4), 0),
                    pady=(self.px(3), 0))
        star = tk.Label(inner,
                        text=ICONS["star_on"] if task["star"] else ICONS["star"],
                        bg=c["surface"],
                        fg=c["star"] if task["star"] else c["surface"],
                        font=(ICON_FONT, 9), cursor="hand2")
        star.pack(side="right", anchor="n", pady=(self.px(2), 0))

        rtl = is_rtl(task["text"])
        font = (FONT, 10, "overstrike") if task["done"] else (FONT, 10)
        lbl = tk.Label(inner, text=task["text"], bg=c["surface"],
                       fg=c["subtle"] if task["done"] else c["text"],
                       font=font, anchor="e" if rtl else "w",
                       justify="right" if rtl else "left")
        lbl.pack(side="left", fill="x", expand=True, padx=(self.px(10), 0))

        frames = (row, inner, lbl, delete, star)

        def hover(on):
            bg = c["hover"] if on else c["surface"]
            for w in frames:
                w.configure(bg=bg)
            check.set_bg(bg)
            check.hover(on)
            delete.configure(fg=c["muted"] if on else bg)
            if not task["star"]:
                star.configure(fg=c["muted"] if on else bg)

        for w in frames + (check,):
            w.bind("<Enter>", lambda e: hover(True), add="+")
            w.bind("<Leave>", lambda e: hover(False), add="+")
            w.bind("<Button-3>", lambda e, i=index, r=row, l=lbl:
                   self._row_menu(e, i, r, l))
        lbl.bind("<Double-Button-1>", lambda e, i=index, r=inner, l=lbl:
                 self.edit(i, r, l))
        delete.bind("<Button-1>", lambda e, i=index: self.delete(i))
        delete.bind("<Enter>", lambda e: delete.configure(fg=c["danger"]),
                    add="+")
        star.bind("<Button-1>", lambda e, i=index: self.toggle_star(i))
        inner.bind("<Configure>", lambda e, l=lbl: l.configure(
            wraplength=max(self.px(60), e.width - self.px(80))))

    def _row_menu(self, e, i, row, lbl):
        c = self.c
        m = tk.Menu(self.root, tearoff=0, bg=c["surface"], fg=c["text"],
                    activebackground=self.accent, activeforeground="white",
                    font=(FONT, 9), bd=0)
        t = self.state["tasks"][i]
        m.add_command(label="Mark as not done" if t["done"] else "Mark as done",
                      command=lambda: self.toggle(i))
        m.add_command(label="Remove star" if t["star"] else "Star (important)",
                      command=lambda: self.toggle_star(i))
        m.add_command(label="Edit",
                      command=lambda: self.edit(i, lbl.master, lbl))
        m.add_separator()
        m.add_command(label="Delete", command=lambda: self.delete(i))
        try:
            m.tk_popup(e.x_root, e.y_root)
        finally:
            m.grab_release()

    # ---------------------------------------------------------------- actions
    def add_task(self):
        self._hide_placeholder()
        text = self.entry.get().strip()
        if not text:
            return
        self.state["tasks"].insert(0, {"text": text, "done": False,
                                       "star": False})
        self.entry.delete(0, "end")
        self.entry.configure(justify="left")
        self.persist()
        self.render()
        self.canvas.update_idletasks()
        self.canvas.yview_moveto(0)

    def toggle(self, i):
        self.state["tasks"][i]["done"] = not self.state["tasks"][i]["done"]
        self.persist()
        self.render()

    def toggle_star(self, i):
        self.state["tasks"][i]["star"] = not self.state["tasks"][i]["star"]
        self.persist()
        self.render()

    def delete(self, i):
        del self.state["tasks"][i]
        self.persist()
        self.render()

    def edit(self, i, parent, lbl):
        c = self.c
        lbl.pack_forget()
        e = tk.Entry(parent, bg=c["bg"], fg=c["text"], insertbackground=c["text"],
                     relief="flat", font=(FONT, 10), highlightthickness=1,
                     highlightcolor=self.accent,
                     highlightbackground=self.accent)
        e.insert(0, self.state["tasks"][i]["text"])
        e.pack(side="left", fill="x", expand=True, padx=(self.px(10), 0))
        e.focus_set()
        e.select_range(0, "end")
        finished = []

        def commit(_=None):
            if finished:  # Return and FocusOut can both fire
                return
            finished.append(True)
            text = e.get().strip()
            if text:
                self.state["tasks"][i]["text"] = text
                self.persist()
            self.render()

        e.bind("<Return>", commit)
        e.bind("<FocusOut>", commit)
        e.bind("<Escape>", lambda _: (finished.append(True), self.render()))

    def clear_done(self):
        self.state["tasks"] = [t for t in self.state["tasks"] if not t["done"]]
        self.persist()
        self.render()

    def toggle_collapse(self):
        self.state["collapsed"] = not self.state["collapsed"]
        w = self.root.winfo_width()
        if self.state["collapsed"]:
            self.state["expanded_height"] = self.root.winfo_height()
            self.body.pack_forget()
            self.root.update_idletasks()
            h = self.header.winfo_reqheight() + self.px(20)
        else:
            self.body.pack(fill="both", expand=True)
            h = self.state.get("expanded_height") or self.px(440)
        self.collapse_btn.configure(
            text=ICONS["down"] if self.state["collapsed"] else ICONS["up"])
        self.root.geometry(f"{w}x{h}")
        self._save_geometry()

    # ---------------------------------------------------------------- settings
    def set_mode(self):
        self.state["mode"] = self.mode_var.get()
        self.persist()
        self.apply_mode()

    def set_theme(self):
        self.state["theme"] = self.theme_var.get()
        self.persist()
        self.build_ui()

    def set_accent(self):
        self.state["accent"] = self.accent_var.get()
        self.persist()
        self.build_ui()

    def set_alpha(self):
        self.state["alpha"] = self.alpha_var.get()
        self.persist()
        self.apply_alpha()

    def apply_alpha(self):
        try:
            self.root.attributes("-alpha", self.state["alpha"])
        except tk.TclError:
            pass

    def toggle_lock(self):
        self.state["locked"] = self.lock_var.get()
        self.persist()
        self.build_ui()

    def toggle_autostart(self):
        self.win.set_autostart(self.auto_var.get())
        self.auto_var.set(self.win.autostart_enabled())

    def _first_run_autostart(self):
        """Turn on 'Start with Windows' once; keep the saved path current."""
        if not self.win.exe_path():
            return
        if not self.state["autostart_initialized"]:
            self.win.set_autostart(True)
            self.state["autostart_initialized"] = True
            self.persist()
        elif self.win.autostart_enabled():
            self.win.set_autostart(True)  # exe may have been moved

    # ---------------------------------------------------------------- z-order
    def apply_mode(self):
        top = self.state["mode"] == "top"
        self.root.attributes("-topmost", top)
        if not self.win:
            return
        if top:
            self.win.set_owner(self._hwnd, None)
            self._owner = None
            self.win.set_topmost(self._hwnd, True)
        else:
            self.win.set_topmost(self._hwnd, False)
            self._raised = False
            self._desktop_watch()

    def _desktop_watch(self):
        """Keep the widget on the desktop: visible when the desktop is
        shown (including after Win+D), behind other apps otherwise."""
        if not self.win or self.state["mode"] != "desktop":
            return
        try:
            progman = self.win.progman()
            if progman and progman != self._owner:  # explorer restarted
                self.win.set_owner(self._hwnd, progman)
                self._owner = progman
            fg, is_desktop, own = self.win.foreground()
            if is_desktop and not self._raised:
                self.win.set_topmost(self._hwnd, True)
                self._raised = True
            elif (fg and not is_desktop and not own and self._raised
                  and not self.win.is_topmost(fg)):  # skip taskbar, Alt+Tab
                self.win.place_behind(self._hwnd, fg)
                self._raised = False
        except Exception:
            pass
        self.root.after(400, self._desktop_watch)

    # ---------------------------------------------------------------- misc
    def _update_date(self):
        now = datetime.now()
        self.date_lbl.configure(text=f"{now:%A}, {now.day} {now:%B}".upper())

    def _tick_clock(self):
        self._update_date()
        self.root.after(30_000, self._tick_clock)

    def quit(self):
        self._save_geometry()
        self.root.destroy()

    def persist(self):
        try:
            save_state(self.state)
        except OSError:
            pass

    def _start_drag(self, e):
        if self.state["locked"]:
            self._drag = None
            return
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
            w = max(self.px(240), w0 + e.x_root - x0)
            h = max(self.px(200), h0 + e.y_root - y0)
            self.root.geometry(f"{w}x{h}")

    def _save_geometry(self):
        self.state["geometry"] = self.root.geometry()
        self.persist()

    def _scroll(self, units):
        if self.canvas.yview() != (0.0, 1.0):
            self.canvas.yview_scroll(units, "units")

    def _on_wheel(self, e):
        self._scroll(int(-e.delta / 120))


def main():
    win = None
    if IS_WIN:
        try:  # crisp text on high-DPI screens
            ctypes.windll.shcore.SetProcessDpiAwareness(1)
        except Exception:
            pass
        win = WinDesktop()
        if win.already_running():
            win.show_existing()
            return
    root = tk.Tk()
    TodoWidget(root, win)
    root.mainloop()


if __name__ == "__main__":
    main()
