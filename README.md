# Todo Widget

A clean to-do list widget that lives on your Windows desktop.

## Install (one file, no installer)

1. Download **[TodoWidget.exe](https://github.com/Ahmad-Nayfeh/TODOLIST-WINDOWS/releases/download/latest/TodoWidget.exe)**
   (Releases → latest).
2. Double-click it. That's it.

It turns on **Start with Windows** the first time it runs, so the widget appears on your
desktop after every restart. You can switch this off in the **⋯** menu.

> First run: Windows SmartScreen may say *"Windows protected your PC"* because the
> file is not code-signed. Click **More info → Run anyway**. On a managed company
> laptop, IT policy may block unsigned `.exe` files entirely.
>
> Tip: move `TodoWidget.exe` to a permanent folder (e.g. Documents) before running it,
> so it isn't deleted when you clean Downloads.

## Desktop modes (⋯ menu)

| Mode | Behaviour |
| --- | --- |
| **Pin to desktop** (default) | Stays on the desktop like a gadget. Stays visible after **Win + D** (Show desktop). Other programs can cover it. |
| **Always on top** | Floats above every window. |

## How to use

| Action | How |
| --- | --- |
| Add task | Type in the box, press **Enter** (or click **+**) |
| Mark done / undo | Click the round checkbox |
| Edit task | Double-click the text. **Enter** saves, **Esc** cancels |
| Star as important | Hover a task and click ☆ (starred tasks go to the top) |
| Delete task | Hover a task and click ✕ |
| More task actions | Right-click a task |
| Remove all completed | Click **Clear completed** |
| Collapse / expand | Arrow button in the header |
| Move / resize | Drag the header / drag the ◢ corner |
| Theme, accent color, opacity, lock position, start with Windows, exit | **⋯** menu (or right-click the header) |

Arabic and other right-to-left tasks are right-aligned automatically.
Everything is saved automatically to `%APPDATA%\TodoWidget\tasks.json`.

## Run from source

```
python todo_widget.py
```

Requires Python 3 with Tkinter (included in the standard Windows installer). No other packages.

## Build the .exe yourself

```
pip install pyinstaller
pyinstaller --onefile --windowed --name TodoWidget todo_widget.py
```

GitHub Actions runs a Windows smoke test, builds the `.exe`, checks that it starts, and publishes
it to the `latest` release on every push (see `.github/workflows/build.yml`).
