"""Review queue WP7: documentation claims that a machine can check against the archive and the code."""
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
ORIGINAL = ROOT / "docs" / "history" / "MEMPALACE_CONTEXT_MANIFESTO-2026-07.md"
CONTRACT = ROOT / "docs" / "MEMPALACE_CONTEXT_MANIFESTO.md"


def _original_stage_facts():
    """Per stage of the archived plan: (checked, unchecked) checklist items and whether the log says "завершено"."""
    text = ORIGINAL.read_text(encoding="utf-8")
    sections = re.split(r"^## Етап (\d+)\.", text, flags=re.M)
    facts = {}
    for number, body in zip(sections[1::2], sections[2::2]):
        body = re.split(r"^## \d+\.", body, flags=re.M)[0]          # stop at the next numbered chapter
        facts[int(number)] = [body.count("[x]"), body.count("[ ]")]
    finished = {int(n) for n in re.findall(r"^### [\d-]+ — Етап (\d+) завершено", text, flags=re.M)}
    return facts, finished


def _contract_statuses():
    rows = re.findall(r"^\|\s*(\d+)\s*\|[^|]*\|\s*([^|]+?)\s*\|", CONTRACT.read_text(encoding="utf-8"), flags=re.M)
    return {int(number): status for number, status in rows}


def test_the_stage_table_says_what_the_archived_plan_s_checklists_and_log_say():
    facts, finished = _original_stage_facts()
    statuses = _contract_statuses()

    assert finished == {1, 2}
    for stage in (0, 1, 2):
        assert facts[stage][1] == 0 and statuses[stage] == "done", stage
    assert facts[3][0] > 0 and facts[3][1] == 0 and 3 not in finished
    assert statuses[3] == "checklist complete, stage left open"
    assert facts[4][0] > 0 and facts[4][1] > 0
    assert statuses[4] == "partly"
    for stage in range(5, 11):
        assert facts[stage][0] == 0 and statuses[stage] == "not started", stage


def test_a_plugin_s_glossary_md_is_never_the_glossary(tmp_path):
    """plugins/plain_text/translation_prompts/glossary.md was deleted as unread. The glossary is looked up
    only in the project directory: zelda_ww still ships a glossary.md in its prompt folder and it is not used."""
    from handlers.translation.glossary_prompt_manager import GlossaryPromptManager

    assert (ROOT / "plugins" / "zelda_ww" / "translation_prompts" / "glossary.md").exists()

    class Projects:
        project_dir = None

    class Window:
        project_manager = Projects()

    manager = GlossaryPromptManager(Window(), None, None)
    for plugin in ("zelda_ww", "plain_text", "zelda_mc"):
        assert manager._resolve_glossary_path(plugin) is None                    # no project: no glossary
    Projects.project_dir = str(tmp_path)
    for plugin in ("zelda_ww", "plain_text", "zelda_mc"):
        assert manager._resolve_glossary_path(plugin) == tmp_path / "glossary.json"
