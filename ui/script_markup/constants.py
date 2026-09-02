"""Module-level constants for Script Markup Studio."""
from __future__ import annotations

from PyQt6.QtCore import Qt

from core.script_markup import LineKind, HierarchyType

# Background tint per classification, shared by the highlighter and the legend.
_KIND_COLORS = {
    LineKind.CHAPTER: "#fde7e9",        # red-ish
    LineKind.LOCATION: "#e7f0fb",       # blue-ish
    LineKind.ACTION: "#fff4ce",         # amber
    LineKind.SPEAKER: "#e6f7ea",        # green
    LineKind.GUTTER_SPEAKER: "#e6f7ea",
    LineKind.DIALOGUE_CONT: "#f1faf3",  # pale green
    LineKind.IGNORE: "#f3f3f3",         # grey
    LineKind.NARRATION: "#ffffff",      # plain
    LineKind.BLANK: "#ffffff",
}

_KIND_LABELS = [
    (LineKind.CHAPTER, "Chapter"),
    (LineKind.LOCATION, "Location"),
    (LineKind.ACTION, "Action"),
    (LineKind.SPEAKER, "Speaker / dialogue"),
    (LineKind.IGNORE, "Ignored / dropped"),
]

_KIND_TITLES = {
    LineKind.CHAPTER: "Chapter",
    LineKind.LOCATION: "Location",
    LineKind.ACTION: "Action",
    LineKind.SPEAKER: "Speaker",
    LineKind.GUTTER_SPEAKER: "Speaker",
    LineKind.DIALOGUE_CONT: "Dialogue",
    LineKind.IGNORE: "Ignored",
    LineKind.NARRATION: "Narration",
    LineKind.BLANK: "Blank",
}

_MENU_MARKS = [
    ("Chapter", LineKind.CHAPTER),
    ("Location", LineKind.LOCATION),
    ("Action", LineKind.ACTION),
    ("Speaker", LineKind.SPEAKER),
    ("Ignore", LineKind.IGNORE),
]

# Consecutive lines of one speaker form a "block". Adjacent blocks alternate
# between two tints (green / teal) so the eye reads each speaker's run as a unit;
# the speaker's header line gets the deeper "head" shade.
_BLOCK_HEAD = ("#a7dab4", "#9bd2da")
_BLOCK_BODY = ("#e6f7ea", "#ddf0f2")

_MAX_UNMARKED_HIGHLIGHT_LINES = 600
_UNMARKED_GROUP_THRESHOLD = 80
_MAX_UNMARKED_TREE_CHILDREN = 1200
_MAX_IGNORED_TREE_CHILDREN = 1200
_MAX_SEARCH_EXTRA_HIGHLIGHTS = 800
_OUTLINE_LINE_ROLE = Qt.ItemDataRole.UserRole
_OUTLINE_ENTRY_KEY_ROLE = Qt.ItemDataRole.UserRole + 1
_OUTLINE_MARK_KEY_ROLE = Qt.ItemDataRole.UserRole + 2
_HIERARCHY_TEMPLATE_FORMAT = "picoripi.script_markup_studio.hierarchy_template"
_STUDIO_SESSION_FORMAT = "picoripi.script_markup_studio.autosave_session"
_HISTORY_LIMIT = 200
_TEXT_CONTAINER_TYPES = {
    HierarchyType.STRUCTURE,
    HierarchyType.SPEAKER,
    HierarchyType.GLOSSARY,
    HierarchyType.ITEM,
    HierarchyType.TEXT,
    HierarchyType.IGNORE,
    HierarchyType.UNMARKED,
}
_ASSIGNED_SPEAKER_ORIGIN = "speaker_assignment"
_RAW_HIERARCHY_INDENT = 0
_RAW_HIERARCHY_GUTTER_WIDTH = 82
_RAW_HIERARCHY_MAX_VISUAL_DEPTH = 6
_CUSTOM_TYPE_COLORS = (
    "#e8f5e9",
    "#e3f2fd",
    "#fff8e1",
    "#f3e5f5",
    "#e0f7fa",
    "#fce4ec",
    "#f1f8e9",
    "#fff3e0",
)
_SAVE_EDIT_BUTTON_STYLE = """
    QPushButton {
        background: #107c41;
        color: #ffffff;
        border: 1px solid #0b5f31;
        border-radius: 4px;
        padding: 3px 10px;
        min-height: 24px;
        font-weight: 600;
    }
    QPushButton:hover {
        background: #138a49;
        border-color: #0a4f29;
    }
    QPushButton:pressed {
        background: #0b5f31;
    }
"""
_STOP_EDIT_BUTTON_STYLE = """
    QPushButton {
        background: #fde7e9;
        color: #7a1f2b;
        border: 1px solid #c83b4a;
        border-radius: 4px;
        padding: 3px 10px;
        min-height: 24px;
        font-weight: 600;
    }
    QPushButton:hover {
        background: #fff1f2;
        border-color: #a4262c;
    }
    QPushButton:pressed {
        background: #f8cdd2;
    }
"""


_HELP_HTML = """
<h2 style="margin-top:0;">Script Markup Studio</h2>
<p>Turns a raw walkthrough into the standardized script format
(<code>[Chapter:]</code> / <code>[Location:]</code> / <code>{Action:}</code> /
<code>SPEAKER: text</code>) that the MemePalace builders use to give the AI
translator rich context.</p>

<h3>How it works</h3>
<p>You work in a single view: the raw script, <b>colour-coded by what each line
becomes</b> &mdash; green for speech, amber for actions, blue for locations,
grey for lines that are dropped. There is no second pane to keep in sync; press
<b>Preview result…</b> any time to see the finished file, then <b>Export</b>.</p>

<h3>Three modes</h3>
<ul>
  <li><b>Hierarchy markup</b> (default) &mdash; manual depth-indexed tree marks.
      Each mark has a depth, type, label/text and type colour, then exports
      canonical Markdown.</li>
  <li><b>Picoripi rules</b> &mdash; uses the program's own walkthrough
      parser, the same rules it already uses to mark speakers and scenes. Best
      for already-structured scripts.</li>
  <li><b>Custom recipe</b> &mdash; tunable rules plus teach-by-example, for messy
      raw walkthroughs.</li>
</ul>

<h3>Workflow</h3>
<ol>
  <li>Use <b>Script &gt; Open script...</b> to load the raw walkthrough.</li>
  <li><i>(Hierarchy markup)</i> Mark selections, review the script tree, then use
      <b>Project</b>, <b>Template</b>, and <b>Auto-fill</b> when you need reusable
      marks or assisted fill-in.</li>
  <li><i>(Picoripi rules / Custom recipe)</i> Use <b>Start from cursor</b> and
      <b>End at cursor</b> to cut off the table of contents, cast list and legal
      front/back matter, so only the real story remains.</li>
  <li><i>(Custom recipe)</i> Tune with the checkboxes, or teach by example.</li>
  <li>Watch the colours and the Review queue; press <b>Preview result…</b> to
      check the finished file.</li>
  <li><b>Export</b> the standardized script.</li>
</ol>

<h3>Navigation and search</h3>
<ul>
  <li><b>Find</b>: type in the search box, press <b>Enter</b> for the next match,
      or <b>Shift+Enter</b> for the previous match. Use <b>Aa</b>, <b>Word</b>,
      and <b>.*</b> to refine matching.</li>
  <li><b>Minimap</b>: drag the right-side overview marker to move quickly through
      long raw scripts.</li>
  <li><b>Script tree</b>: double-click a node or review item to jump to its source
      line.</li>
</ul>

<h3>Keyboard shortcuts</h3>
<ul>
  <li><b>Ctrl+F</b> focuses Find. In the Find box, <b>Enter</b> jumps to the next
      match and <b>Shift+Enter</b> jumps to the previous match.</li>
  <li><b>Ctrl+M</b> marks the current selection with the chosen Type. While editing
      an existing hierarchy node, it saves the edit. In Picoripi rules or Custom
      recipe, it marks selected/current lines as Action.</li>
  <li><b>Ctrl+I</b> selects Ignore in Hierarchy markup; if raw text is selected, it
      marks that selection as ignored. In Picoripi rules or Custom recipe, it
      marks selected/current lines as Ignore.</li>
  <li><b>Ctrl+S</b> Structure, <b>Ctrl+P</b> Speaker, <b>Ctrl+T</b> Text, and
      <b>Ctrl+B</b> Breaker in Hierarchy markup. With raw text selected, the
      shortcut marks that selection; without selection, it only changes the Type
      picker.</li>
  <li><b>F2</b> renames the selected script tree node. Clicking an already
      selected tree node also opens rename; double-click still jumps to source.</li>
  <li><b>Ctrl+Z</b> undoes the last Studio change. <b>Ctrl+Y</b> redoes it.</li>
</ul>

<h3>Hierarchy Markdown</h3>
<ul>
  <li><b>Structure</b> depth 0/1/2 becomes <code>#</code>, <code>##</code>,
      <code>###</code> headings.</li>
  <li><b>Glossary</b> becomes a MemPalace source section. Its direct children
      become categories such as Characters, Items, Locations, or custom names.</li>
  <li><b>Speaker</b> and <b>Text</b> are marked separately, then render together:
      <code>**MIDNA**: dialogue</code>.</li>
  <li><b>Action</b> renders as a standalone square-bracket line:
      <code>[*Midna drops from a branch*]</code>.</li>
  <li><b>Context</b> marks dialogue conditions and choices in parentheses. It is
      nested under Speaker; the affected Text is nested under Context.</li>
  <li><b>Note</b> renders inline in parentheses, <b>Breaker</b> renders as
      <code>~~~~~~~~~~~~~~~~~~~~~~~~</code>, and <b>Narrator</b> renders as bold
      standalone text.</li>
  <li><b>AI mark missing</b> is a separate explicit action: it sends your
      approved hierarchy marks as examples and asks the configured AI provider
      to add missing nodes.</li>
  <li><b>Continue from marked examples</b> studies your approved marks and
      locally fills matching unmarked lines without AI. Use <b>Ctrl+Z</b> if
      the result needs to be rolled back.</li>
</ul>

<h3>&ldquo;Mark current line as&hellip;&rdquo; <span style="font-weight:normal;color:#777;">(Custom recipe)</span></h3>
<ul>
  <li><b>Speaker</b> &mdash; opens a small teacher. On one example line you mark
      the two parts <i>separately</i>: select the <b>name</b>, then the
      <b>spoken text</b>. Any separator works &mdash; <code>RUSL: Take this.</code>,
      <code>Rusl - Take this.</code>, <code>[Rusl] "Take this."</code>.</li>
  <li><b>Chapter / Location</b> &mdash; a header line with surrounding delimiters,
      e.g. <code>=== Act One ===</code>. A bare line without a delimiter is
      refused (it cannot be learned reliably).</li>
  <li><b>Ignore</b> &mdash; a recurring noise line (footer, credit, banner); every
      identical line is then dropped.</li>
</ul>

<h3>Manual marks from selection</h3>
<p>Select one or more source lines, right-click, then use <b>Mark selection as</b>
to set Chapter, Location, Action, Speaker or Ignore. Hover a coloured line to see
which state is marked there.</p>

<h3>Speaker formats detected automatically</h3>
<ul>
  <li><b>Inline:</b> <code>NAME: their dialogue</code></li>
  <li><b>Gutter (Format B):</b> the <code>NAME</code> alone on its line, dialogue
      on the lines below it (toggle <b>Gutter speakers</b>).</li>
</ul>
"""
