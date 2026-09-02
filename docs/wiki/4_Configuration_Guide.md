# Configuration Files & Database Guide

This guide details the structure, properties, and values of Picoripi's configuration files and its local database schema.

---

## 1. Environment Variables (`.env`)

The `.env` file is stored in the project's root folder and contains private API keys for external services:

```ini
# OpenAI API Settings
OPENAI_API_KEY=sk-...

# Google Gemini API Settings
GEMINI_API_KEY=AIzaSy...

# DeepL Translation Settings (Optional)
DEEPL_API_KEY=...

# MemePalace API Endpoint (Defaults to localhost server)
MEMPALACE_SERVER_URL=http://127.0.0.1:8000
```

---

## 2. Global Settings (`settings.json`)

The application's state and preferences are stored in the root directory under `settings.json`. Below is an overview of the key configuration sections:

*   **`theme`**: Set to `"dark"`, `"light"`, or `"system"`.
*   **`font_family`**: The default UI display typeface (e.g. `"Segoe UI"`, `"Inter"`).
*   **`font_size`**: The global interface font scale (8px to 24px).
*   **`tooltip_font_size`**: Font scale for glossary descriptions (6px to 32px).
*   **`spellchecker_enabled`**: Boolean flag to toggle live hunspell checks.
*   **`spellchecker_language`**: ISO language code (e.g., `"uk_UA"`, `"en_US"`).
*   **`live_bfn_preview`**: Live simulator flag for custom Nintendo fonts.
*   **`ai_provider`**: Active LLM client. Value must be one of: `"openai"`, `"gemini"`, `"ollama"`, `"perplexity"`. For Gemini Web2API use `"openai"` (OpenAI Compatible) with a local endpoint.
*   **`ai_presets`**: Dictionary storing named configurations for API connections:
    ```json
    "ai_presets": {
      "Gemini Web2API": {
        "provider": "openai",
        "model": "gemini-3.7-flash",
        "endpoint_url": "http://127.0.0.1:8081/v1",
        "api_key": "local",
        "timeout": 180,
        "temperature": 0.0
      },
      "LocalOllama": {
        "provider": "ollama",
        "model": "llama3",
        "endpoint_url": "http://localhost:11434",
        "temperature": 0.5
      }
    }
    ```

Gemini Web2API setup (WebTOP, accounts, Parallel Requests): [5. Gemini Web2API](5_Gemini_Web2API.md).

---

## 3. Tag Aliases & Proportional Font Maps

These files exist inside each game plugin folder (under `plugins/<plugin_name>/`) or custom fonts directories.

### 3.1 `font_map.json` (Proportional Width Rules)
Used by the text analysis engine to calculate the exact horizontal layout spacing of strings.
```json
{
  "widths": {
    "32": 4,
    "46": 2,
    "65": 8
  },
  "aliases": {
    "{PLAYER}": {
      "alias": "Link",
      "width": 24
    }
  },
  "default_width": 6
}
```
*   `widths`: A map of character decimal code points (keys must be strings of integers) to their pixel widths. E.g. `"32"` maps the space character (` `) to 4 pixels, `"65"` maps `A` to 8 pixels.
*   `aliases`: Maps arbitrary gameplay control codes to dummy replacement words (aliases) and pixel widths.
*   `default_width`: The fallback width (in pixels) applied to characters not listed in the widths map.

### 3.2 `aliases.json` (Custom Tag Replacements)
Maintains custom aliases created by the user inside the editor:
```json
{
  "{item_key}": "Key Item",
  "{playerName}": "Link"
}
```

---

## 4. SQLite Database Schema (`mempalace_local.db`)

Picoripi stores visual context information, relationship mapping, and chronological transcripts locally in an SQLite database. The file is created automatically inside the active project's directory.

```
+-------------------------------------------------------------+
|                        Database Schema                      |
+-------------------------------------------------------------+
|  [wings]                                                    |
|  - id (INTEGER PRIMARY KEY)                                 |
|  - name (TEXT UNIQUE)                                       |
|  - description (TEXT)                                       |
|      ^                                                      |
|      | (1-to-many cascade)                                  |
|  [rooms]                                                    |
|  - id (INTEGER PRIMARY KEY)                                 |
|  - wing_id (INTEGER FOREIGN KEY)                            |
|  - name (TEXT)                                              |
|  - description (TEXT)                                       |
|      ^                                                      |
|      | (1-to-many cascade)                                  |
|  [drawers]                                                  |
|  - id (INTEGER PRIMARY KEY)                                 |
|  - room_id (INTEGER FOREIGN KEY)                            |
|  - name (TEXT)                                              |
|  - content (TEXT)                                           |
|  - metadata (TEXT JSON string)                              |
+-------------------------------------------------------------+
```

### 4.1 Table Definitions & Relationships

1.  **`wings`**: Represents projects (e.g. Zelda, Pokemon).
    *   `id`: Primary key.
    *   `name`: Unique string identifier (typically the project name).
    *   `description`: Overview text.

2.  **`rooms`**: Represents physical rooms or narration segments.
    *   `id`: Primary key.
    *   `wing_id`: Foreign key linked to `wings.id`.
    *   `name`: Room identifier (e.g. `Forest_Temple_Entrance`).
    *   `description`: Descriptive overview of the room scene.

3.  **`drawers`**: Contains actual dialogue scripts, transcript segments, or AI-generated visual scene cues.
    *   `id`: Primary key.
    *   `room_id`: Foreign key linked to `rooms.id`.
    *   `name`: Drawer identifier (e.g., `visual_scene_context` or `youtube_transcript`).
    *   `content`: Flat text strings containing scene transcriptions.
    *   `metadata`: JSON-formatted string storing properties such as `speaker_map` and `timestamps`.

4.  **`knowledge_graph`**: Captures relationships between characters and items.
    *   `id`: Primary key.
    *   `wing_id`: Foreign key linked to `wings.id`.
    *   `source_entity`: Name of the source (e.g., `Link`).
    *   `target_entity`: Name of the target (e.g., `Zelda`).
    *   `relation`: Relationship type (e.g., `protects`).
    *   `valid_from`: Time coordinates where the relation holds true.

5.  **`script_chapters`**: Manages timeline sections extracted from narrative scripts.
    *   `id`: Primary key.
    *   `wing_id`: Foreign key.
    *   `num`: Section index (e.g., `Act 1, Chapter 2`).
    *   `title`: The chapter title.
    *   `start_line` / `end_line`: Dialogue line range boundaries.
    *   `ai_summary`: The summary generated by the AI.
    *   `content`: Dialogue content.

6.  **`script_mappings`**: Connects flat translation IDs (like BMG labels) to script timeline lines.
    *   `id`: Primary key.
    *   `wing_id` / `chapter_id`: Reference keys.
    *   `bmg_id`: Unique BMG string ID.
    *   `script_line`: Line index in the narrative script.
    *   `bmg_text`: Source text.
