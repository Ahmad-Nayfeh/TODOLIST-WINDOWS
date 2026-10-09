# Todo Widget

A small, always-on-top to-do list widget for Windows laptops.

## Install (one file, no installer)

1. Go to **Releases → latest** on this repo and download **`TodoWidget.exe`**.
2. Double-click it. That's it.

> First run: Windows SmartScreen may say *"Windows protected your PC"* because the
> file is not code-signed. Click **More info → Run anyway**. On a managed company
> laptop, IT policy may block unsigned `.exe` files entirely.

**Start with Windows (optional):** press `Win + R`, type `shell:startup`, press Enter,
and put a shortcut to `TodoWidget.exe` in that folder.

## How to use

| Action | How |
| --- | --- |
| Add task | Type in the box, press **Enter** (or click **+**) |
| Mark done / undo | Click the task or its checkbox |
| Edit task | Double-click the text, press **Enter** to save, **Esc** to cancel |
| Delete task | Click **✕** on the task |
| Remove all done tasks | Click **Clear done** |
| Move widget | Drag the top bar |
| Resize | Drag the **◢** corner |
| Always on top on/off | Click **📌** |
| Minimize / Close | **—** / **✕** in the top bar |

Tasks, position, and size are saved automatically to `%APPDATA%\TodoWidget\tasks.json`.

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

The result is `dist\TodoWidget.exe`. GitHub Actions does this automatically on every push
(see `.github/workflows/build.yml`).
