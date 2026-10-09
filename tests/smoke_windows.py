"""Smoke test for the Windows-only code paths (run in CI on windows-latest)."""
import os
import sys
import tempfile

os.environ["APPDATA"] = tempfile.mkdtemp()
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import tkinter as tk  # noqa: E402
import todo_widget as tw  # noqa: E402

win = tw.WinDesktop()
assert not win.already_running(), "mutex should be free in a clean CI run"

root = tk.Tk()
app = tw.TodoWidget(root, win)
root.update()
assert app._hwnd, "could not get the window handle"
print("hwnd:", app._hwnd, "progman:", win.progman())

app._desktop_watch()                 # desktop mode: owner + z-order logic
print("foreground:", win.foreground())
print("owner set to progman:", app._owner == win.progman())
fg = win.foreground()[0]
if fg:
    print("fg topmost:", win.is_topmost(fg))
app.mode_var.set("top"); app.set_mode(); root.update()
assert win.is_topmost(app._hwnd), "always-on-top mode did not apply"
app.mode_var.set("desktop"); app.set_mode(); root.update()
# Desktop mode is raised only while the desktop itself is the active window.
assert win.is_topmost(app._hwnd) == app._raised, "desktop z-order mismatch"
print("autostart enabled (not frozen, expected False):", win.autostart_enabled())

app.entry.event_generate("<FocusIn>")
app.entry.delete(0, "end"); app.entry.insert(0, "CI task"); app.add_task()
app.theme_var.set("light"); app.set_theme(); root.update()
app.quit()
print("WINDOWS SMOKE TEST PASSED")
