"""Measure prompt composition sizes for single and batch translation.

Runs AIPromptComposer against a fake main window (no MemPalace DB, no plugin
flow data, 12 glossary entries, a 40-string block). Sizes are chars; tokens
estimated at ~4 chars/token for English and ~2.5 chars/token for Cyrillic.
"""
import os, sys, json, re
os.environ.setdefault("QT_QPA_PLATFORM", "offscreen")
sys.path.insert(0, "/home/claude/pico")

from PyQt6.QtWidgets import QApplication
app = QApplication.instance() or QApplication([])

from core.glossary_manager import GlossaryManager
from handlers.translation.prompt_composer import AIPromptComposer

# ---------- fake world ----------
BLOCK = [
    "Hey, [PLAYER]! Are you heading to\nOrdon Village again?",
    "Link, the goats got loose!\nHelp me round them up!",
    "Rusl asked me to bring the sword\nto Hyrule Castle.",
    "Ilia will be waiting at Ordon Spring.\nDon't be late.",
    "Yes",
    "No",
    "You got a {0}!\nIt's a wooden sword.",
    "The Midna shadow follows you\nwherever you go.",
    "Zelda is the princess of Hyrule.",
    "Welcome to the shop!\nWhat would you like?",
] * 4  # 40 strings
BLOCK = [f"{t}" for t in BLOCK]

GLOSSARY_MD = """
| Original | Translation | Notes |
|---|---|---|
| Link | Лінк | Головний герой, хлопець 17 років, мовчазний |
| Ordon Village | Село Ордон | Рідне село Лінка |
| Rusl | Русл | Мечник, старший, звертається до Лінка неформально |
| Hyrule Castle | Замок Гайрул | Столиця |
| Ilia | Ілія | Подруга Лінка, донька старости, звертається неформально |
| Ordon Spring | Джерело Ордон | Святе джерело біля села |
| Midna | Мідна | Принцеса сутінків, саркастична |
| Zelda | Зельда | Принцеса Гайрулу, формальна мова |
| Hyrule | Гайрул | Королівство |
| goat | коза | Тварина |
| wooden sword | дерев'яний меч | Предмет |
| Ganondorf | Ґанондорф | Головний злодій |
"""

gm = GlossaryManager()
gm.load_from_text(plugin_name="zelda", glossary_path=None, raw_text=GLOSSARY_MD)

class Rules:
    def get_display_name(self): return "Zelda TP"
    def get_text_representation_for_editor(self, t): return t
    def get_translation_context_for_string(self, b, s):
        return {"window_type": "TalkBox"} if s % 5 else {"window_type": "Choice", "content_role": "Choice"}
    def get_ai_flow_context_for_string(self, b, s):
        return f"conversation Ordon_{s//5}: line {s%5+1}/5; after player picks 'Yes'"
    def get_ai_flow_overview(self, b, idxs):
        return "Conversation Ordon_0 (owner: Rusl)\n  1. greeting\n  2. request\n  3. choice Yes/No\n  4. reply\n" * max(1, len(idxs)//5)
    def get_addressee_for_string(self, b, s, speaker=None): return "Link"

class DS:
    data = [BLOCK]
    reference_languages_data = {"German": {(0, i): "Deutsche Referenz Zeile " + str(i) for i in range(40)},
                                "French": {(0, i): "Référence française " + str(i) for i in range(40)}}
    reference_data = {}
    block_names = {}
    physical_block_idx = 0
    current_string_idx = 0

class MW:
    target_language = "Ukrainian"
    current_game_rules = Rules()
    active_game_rules = Rules()
    data_store = DS()
    default_tag_mappings = {"[PLAYER]": "{Player}", "[Color:Red]": "{C:1}", "[/Color]": "{C:0}"}
    string_metadata = {}
    line_width_warning_threshold_pixels = 280
    game_dialog_max_width_pixels = 300
    lines_per_page = 3
    project_manager = None
    translation_handler = None
    block_to_project_file_map = {}

class DP:
    def get_current_string_text(self, b, s):
        return (("Переклад рядка %d" % s) if s % 3 == 0 else "", False)

class MainHandler:
    mw = MW()
    data_processor = DP()
    ui_updater = None
    _glossary_manager = gm

mh = MainHandler()
composer = AIPromptComposer(mh)
composer.story_context.get_mempalace_client = lambda: None  # no DB
composer.story_context.fetch_story_context = lambda *a, **k: None

SYSTEM = json.load(open("/home/claude/pico/translation_prompts/prompts.json"))["translation"]["system_prompt"]

def tok(s):
    cyr = len(re.findall(r"[Ѐ-ӿ]", s))
    return int(cyr / 2.5 + (len(s) - cyr) / 4)

def report(name, system, user):
    print(f"\n=== {name} ===")
    print(f"system: {len(system)} chars ~{tok(system)} tok | user: {len(user)} chars ~{tok(user)} tok | total ~{tok(system)+tok(user)} tok")
    # split user sections
    for sec in user.split("\n\n"):
        head = sec.split("\n", 1)[0][:60]
        print(f"   [{len(sec):5d} ch ~{tok(sec):4d} tok] {head}")

# ---------- single ----------
sys_s, usr_s = composer.compose_messages(SYSTEM, BLOCK[1], block_idx=0, string_idx=1,
                                         expected_lines=2, mode_description="current row")
report("SINGLE translate_single (row 1)", sys_s, usr_s)
open("/home/claude/audit/scratch/single_user.txt", "w").write(usr_s)
open("/home/claude/audit/scratch/single_system.txt", "w").write(sys_s)

# ---------- batch chunk of 12 out of 40 ----------
items = [{"id": i, "text": BLOCK[i]} for i in range(40)]
chunk = items[0:12]
sys_b, usr_b, pmap = composer.compose_batch_request(SYSTEM, chunk, items, block_idx=0,
                                                    mode_description="block 1")
report("BATCH chunk 12/40 (no ledger)", sys_b, usr_b)
open("/home/claude/audit/scratch/batch_user.txt", "w").write(usr_b)
open("/home/claude/audit/scratch/batch_system.txt", "w").write(sys_b)

payload = json.loads(usr_b.split("JSON DATA TO PROCESS:\n", 1)[1])
print("\nJSON payload keys & sizes:")
for k, v in payload.items():
    s = json.dumps(v, ensure_ascii=False, indent=2)
    print(f"   {k:28s} {len(s):6d} ch ~{tok(s):5d} tok")
one = json.dumps(payload["strings_to_translate"][0], ensure_ascii=False, indent=2)
print(f"   per-item example ({len(one)} ch ~{tok(one)} tok):\n{one}")
print("   glossary entries injected:", payload["glossary"].count("\n") - 1,
      "| entries actually in chunk text:",
      len(gm.get_relevant_terms(" ".join(i['text'] for i in chunk))))

# whole block of 40 as 4 chunks: total tokens
total = 0
for k in range(0, 40, 12):
    s, u, _ = composer.compose_batch_request(SYSTEM, items[k:k+12], items, block_idx=0, mode_description="block 1")
    total += tok(s) + tok(u)
print(f"\n4 chunks x (system+user) ~{total} tok input for 40 strings (~{tok(' '.join(BLOCK))} tok of source text) => overhead x{total/ max(1,tok(' '.join(BLOCK))):.1f}")

# retry variant
s, u, _ = composer.compose_batch_request(SYSTEM, chunk, items, block_idx=0, mode_description="block 1",
                                         is_retry=True, retry_reason="Line count mismatch in chunk 1")
print(f"retry user prompt: {len(u)} ch ~{tok(u)} tok")

# duplicated sentence check
dup = "All text chunks you receive in a single request are part of a larger"
print("duplicate cohesion sentence occurrences in batch system prompt:", sys_b.count(dup))
print("CONTEXT PRIORITY occurrences in single system:", sys_s.count("Preserve source meaning"), "| in batch:", sys_b.count("preserve source meaning"))
