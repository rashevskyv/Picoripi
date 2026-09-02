"""Small window to pick which UI catalogs to fill, then run translate.py.

Default: Ukrainian only. Other languages are for a later deploy pass.
"""
from __future__ import annotations

import json
import subprocess
import sys
import tkinter as tk
from pathlib import Path
from tkinter import messagebox, ttk

ROOT = Path(__file__).resolve().parent
LANGS = json.loads((ROOT / "languages.json").read_text(encoding="utf-8"))
LANGS.pop("ru", None)
DEFAULT_ON = {"uk"}
PY = ROOT / ".venv" / "Scripts" / "python.exe"
if not PY.exists():
    PY = Path(sys.executable)


def main():
    win = tk.Tk()
    win.title("Picoripi UI translation")
    win.geometry("420x460")
    win.minsize(380, 400)

    ttk.Label(
        win,
        text="Choose languages to translate from English (locales/en.json).",
        wraplength=390,
    ).pack(anchor="w", padx=12, pady=(12, 4))
    ttk.Label(
        win,
        text="Ukrainian is selected by default. Turn on more languages only when you are ready to deploy.",
        wraplength=390,
    ).pack(anchor="w", padx=12, pady=(0, 8))

    vars_by_code = {}
    box = ttk.Frame(win)
    box.pack(fill="both", expand=True, padx=12)
    for code, name in LANGS.items():
        var = tk.BooleanVar(value=code in DEFAULT_ON)
        vars_by_code[code] = var
        ttk.Checkbutton(box, text=f"{name}  ({code})", variable=var).pack(anchor="w")

    force_var = tk.BooleanVar(value=False)
    ttk.Checkbutton(
        win,
        text="Re-translate keys that already have a value",
        variable=force_var,
    ).pack(anchor="w", padx=12, pady=(8, 4))

    status = tk.StringVar(value="")
    ttk.Label(win, textvariable=status, wraplength=390).pack(anchor="w", padx=12)

    def run_translate():
        codes = [c for c, var in vars_by_code.items() if var.get()]
        if not codes:
            messagebox.showwarning("Picoripi UI translation", "Select at least one language.")
            return
        cmd = [str(PY), str(ROOT / "translate.py"), "--langs", ",".join(codes)]
        if force_var.get():
            cmd.append("--force")
        status.set("Running: " + " ".join(cmd[1:]))
        win.update_idletasks()
        try:
            proc = subprocess.run(cmd, cwd=str(ROOT))
        except OSError as exc:
            messagebox.showerror("Picoripi UI translation", str(exc))
            return
        if proc.returncode == 0:
            status.set("Finished. Catalogs are in locales/.")
            messagebox.showinfo(
                "Picoripi UI translation",
                "Done. Restart Picoripi to load the new catalog.\n\n"
                + ", ".join(codes),
            )
        else:
            status.set(f"Failed with exit code {proc.returncode}. See the console.")
            messagebox.showerror("Picoripi UI translation", f"translate.py exited {proc.returncode}")

    btns = ttk.Frame(win)
    btns.pack(fill="x", padx=12, pady=12)
    ttk.Button(btns, text="Translate selected", command=run_translate).pack(side="left")
    ttk.Button(btns, text="Close", command=win.destroy).pack(side="right")

    win.mainloop()


if __name__ == "__main__":
    main()
