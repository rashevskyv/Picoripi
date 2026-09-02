# Picoripi UI translation

Fills `locales/<code>.json` from English keys in `locales/en.json` (which are the `tr("...")` literals in the app).

## What to run

1. Start Gemini Web2API so `http://127.0.0.1:8081/v1/models` answers.
2. Double-click `run.bat` (or run it from a terminal).
3. In the window, leave **Ukrainian (uk)** checked. Leave other languages off unless you are doing a deploy pass.
4. Click **Translate selected**. Restart Picoripi and pick **Українська** in **Language**.

`run.bat` with extra arguments skips the window and calls `translate.py` directly, e.g. `run.bat --langs uk`.

Russian is not a target. After Ukrainian exists, later languages receive it as extra context in the prompt.
