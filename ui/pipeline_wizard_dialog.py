"""One window that puts the localization steps in order.

The tools all existed already; what was missing was the map. The order between
them is real -- markup before the speaker merge, a glossary before translating
text with it -- but it lived only in the roadmap, so the Tools menu read as a
pile of unrelated commands. This dialog states the order, shows how far each
step has got, says why the step exists, and hands off to the tool that does it.

Deliberately thin: it computes no pipeline logic of its own and runs nothing
itself. Every button triggers the same action the menu used to.
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from typing import Callable, Dict, List, Optional

from PyQt6.QtCore import QEvent, Qt
from PyQt6.QtWidgets import (
    QDialog,
    QDialogButtonBox,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QStackedWidget,
    QTreeWidget,
    QTreeWidgetItem,
    QTreeWidgetItemIterator,
    QVBoxLayout,
    QWidget,
)

from core.pipeline_status import (
    DONE,
    NOT_STARTED,
    PARTIAL,
    StepState,
    glossary_states,
    markup_state,
    overall,
    present,
    speaker_names_state,
    structural_seed_state,
    translation_state,
)
from core.speaker_alias_merge import find_markup_project, load_speaker_aliases
from utils.logging_utils import log_debug

_ICONS = {NOT_STARTED: "⚪", PARTIAL: "\U0001f7e1", DONE: "✅"}
_STEP_ROLE = Qt.ItemDataRole.UserRole


def _trigger(action_name: str) -> Callable:
    """Run whatever the menu action for this step already does."""
    def run(mw):
        action = getattr(mw, action_name, None)
        if action is not None:
            action.trigger()
    return run


def _embed_glossary_auto(mw, parent=None) -> QWidget:
    """The one user-facing glossary route, embedded in the pipeline."""
    from handlers.translation.glossary_pipeline_handler import GlossaryPipelineHandler

    handler = getattr(mw, "glossary_pipeline_handler", None)
    if handler is None:
        handler = GlossaryPipelineHandler(mw)
        mw.glossary_pipeline_handler = handler

    form = handler.make_dialog(
        parent=parent,
        on_build=lambda: handler.start_build(form.options()),
        target_step="auto",
    )
    form.setWindowFlags(Qt.WindowType.Widget)
    form.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, False)
    return form
def _embed_mempalace_builder(mw, parent=None) -> QWidget:
    """The Context Builder, hosted inside this window rather than beside it.

    It is a step-by-step build of its own, and two wizards in two windows is one
    wizard too many. A QDialog re-flagged as a plain Widget lays out inside a
    parent like any other widget, so this reuses the whole existing dialog
    without touching it.
    """
    from ui.mempalace_builder_dialog import MemePalaceBuilderDialog

    class _Embedded(MemePalaceBuilderDialog):
        """Hosted, so it has no window of its own to close.

        Its Close and 'Done — Close Builder' buttons would close nothing here,
        and the wizard already has one Close of its own. The same button becomes
        Stop while a job runs, though, and that has to stay reachable -- so it
        is hidden by state, not removed.
        """

        def close(self):
            self.save_builder_settings()
            return False

        def _set_ui_enabled(self, enabled):
            super()._set_ui_enabled(enabled)
            self.cancel_btn.setVisible(not enabled)  # visible only as Stop

        def _set_saved_dialogue_search_actions(self, complete):
            super()._set_saved_dialogue_search_actions(complete)
            self.story_context_done_btn.setVisible(False)

    builder = _Embedded(mw, parent=parent)
    builder.cancel_btn.setVisible(False)
    builder.story_context_done_btn.setVisible(False)
    builder.setWindowFlags(Qt.WindowType.Widget)
    # Standing alone it sizes itself as a window; embedded it must yield to the
    # host, and it must not self-destruct when the host hides it.
    builder.setAttribute(Qt.WidgetAttribute.WA_DeleteOnClose, False)
    builder.setMinimumSize(0, 0)
    return builder


@dataclass(frozen=True)
class Step:
    key: str
    title: str
    why: str
    button: str = ""
    run: Optional[Callable] = None
    # A capability name from the plugin's get_capabilities(). Empty means the
    # step works on extracted text alone and so applies to every game.
    requires: str = ""
    # Builds the step's own UI to show in place of the explanation, for a step
    # that is a workflow rather than a single command.
    embed: Optional[Callable] = None
    # The key of the step this one is part of. Describing and translating terms
    # are not stages beside collecting them, they are what you do to the
    # collection -- and a flat list said otherwise.
    parent: str = ""


def capabilities_of(mw) -> set:
    """What the active plugin says it can do. An absent answer means nothing."""
    getter = getattr(getattr(mw, "current_game_rules", None), "get_capabilities", None)
    if not callable(getter):
        return set()
    try:
        return set(getter() or ())
    except Exception:
        return set()


def steps_for(capabilities) -> List["Step"]:
    """The pipeline as it applies to this game.

    The wizard is the engine's, not any one plugin's. A game that only ever
    hands over extracted text still gets the whole glossary and translation
    path; the steps that need the game's own data appear only where a plugin
    declared it can supply it, rather than sitting there failing.
    """
    available = set(capabilities or ())
    return [step for step in STEPS if not step.requires or step.requires in available]


STEPS: List[Step] = [
    Step(
        "markup",
        "Mark up the script",
        "A walkthrough script is prose: names, stage directions and dialogue all "
        "look alike to a program. Marking it says which line is a speaker and "
        "which is speech.\n\n"
        "Everything downstream that needs to know who is talking reads this. "
        "Skip it and the next step has to guess from ALL-CAPS lines, which gets "
        "names wrong and misses most of them.",
        "Open Script Markup Studio",
        _trigger("script_markup_studio_action"),
    ),
    Step(
        "context",
        "Build the story context",
        "Weaves the marked-up script into a timeline: which scene a line belongs "
        "to, what happened before it, who was present.\n\n"
        "This is what lets a translation prompt say more than 'translate this "
        "sentence' -- the model gets the scene around the line.",
        embed=_embed_mempalace_builder,
    ),
    Step(
        "glossary",
        "Prepare and enrich the glossary",
        "This is the single glossary route. It first takes every reliable term "
        "available from game data and Script Markup, then sweeps the selected "
        "project blocks for missing terms, builds descriptions from the available "
        "context, and proposes translation variants.\n\n"
        "The pass runs without stopping for questions. Ambiguities remain visible "
        "as AI notes and review choices, but they never block text translation.",
        embed=_embed_glossary_auto,
    ),
    Step(
        "speakers",
        "Name the speakers",
        "The game data groups lines by voice but has no names for them, so they "
        "arrive as Voice 8, Voice 41. The script has the names but not the rows. "
        "This joins the two on the line text.\n\n"
        "Naming is then one decision per voice rather than one per line, and the "
        "names reach the Speaker field, the virtual folders, the translation "
        "prompt -- and the glossary, which seeds each character under the name "
        "decided here instead of the identifier the game's files use.",
        "Merge speakers from the script",
        _trigger("merge_speakers_action"),
        requires="speaker_attribution",
        parent="glossary",
    ),
    Step(
        "text",
        "Translate the text",
        "With the glossary confirmed and the speakers named, the text itself is "
        "translated block by block from the editor -- every line carrying its "
        "terms, its speaker and its scene into the prompt.\n\n"
        "There is no single button here on purpose: translating is done where "
        "you can read the result.",
    ),
]


class PipelineWizardDialog(QDialog):
    """Steps on the left, the selected step and its launcher on the right."""

    def __init__(self, main_window, parent=None):
        parent = parent if parent is not None else main_window
        if parent is not None and (
            not isinstance(parent, QWidget) or bool(getattr(parent, "_is_test_mode", False))
        ):
            parent = None
        super().__init__(parent)
        self.mw = main_window
        self.setWindowTitle("Localization Pipeline")
        # Roomy enough for the embedded Context Builder, which is a full
        # workflow rather than a paragraph and a button.
        self.resize(1220, 820)
        # Never modal: this window exists to open other windows, and a modal
        # wizard would lock the user out of the tool it just launched.
        self.setModal(False)
        self._states: Dict[str, StepState] = {}
        self._steps: List[Step] = steps_for(capabilities_of(main_window))
        self._codes_cache: Optional[tuple] = None  # (project_dir, codes)
        self._markup_path: str = ""

        layout = QVBoxLayout(self)
        self.headline = QLabel(self)
        layout.addWidget(self.headline)

        body = QHBoxLayout()
        # A tree, because the steps are not a flat sequence: describing terms,
        # naming speakers and translating them are all things you do to the
        # collection the step above produced.
        self.list = QTreeWidget(self)
        self.list.setMinimumWidth(320)
        self.list.setHeaderHidden(True)
        self.list.setWordWrap(True)
        self.list.setRootIsDecorated(False)
        self.list.setIndentation(18)
        body.addWidget(self.list, 1)

        # Most steps explain themselves and hand off with one button; a step that
        # is a workflow of its own shows that workflow here instead.
        self.stack = QStackedWidget(self)
        explain = QWidget(self.stack)
        right = QVBoxLayout(explain)
        right.setContentsMargins(0, 0, 0, 0)
        self.title = QLabel(explain)
        self.title.setStyleSheet("font-size: 15px; font-weight: bold;")
        self.state_label = QLabel(explain)
        self.why = QLabel(explain)
        self.why.setWordWrap(True)
        self.why.setAlignment(Qt.AlignmentFlag.AlignTop)
        self.run_button = QPushButton(explain)
        self.run_button.clicked.connect(self._run_current)
        right.addWidget(self.title)
        right.addWidget(self.state_label)
        right.addWidget(self.why, 1)
        right.addWidget(self.run_button)
        self.stack.addWidget(explain)
        self._explain_page = explain
        self._embedded: Dict[str, QWidget] = {}
        body.addWidget(self.stack, 2)
        layout.addLayout(body, 1)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Close | QDialogButtonBox.StandardButton.Retry,
            self,
        )
        buttons.button(QDialogButtonBox.StandardButton.Retry).setText("Refresh")
        buttons.button(QDialogButtonBox.StandardButton.Retry).clicked.connect(self.refresh)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        self.list.currentItemChanged.connect(self._on_current_changed)
        self.refresh()
        self.select_step(self._first_unfinished())

    # -- reading the project ------------------------------------------------

    def _probe(self) -> Dict[str, StepState]:
        """Ask the project where it stands. Never fatal: a step that cannot be
        measured reports 'not started' rather than taking the window down."""
        mw = self.mw
        project_dir = getattr(getattr(mw, "project_manager", None), "project_dir", None)
        composer = getattr(getattr(mw, "translation_handler", None), "prompt_composer", None)

        script_path = None
        client = None
        try:
            finder = getattr(composer, "_find_script_path", None)
            script_path = finder() if callable(finder) else None
            getter = getattr(composer, "_get_mempalace_client", None)
            client = getter() if callable(getter) else None
        except Exception as exc:
            log_debug(f"Pipeline wizard: reading the script context failed: {exc}")
        has_script = bool(script_path) and os.path.exists(str(script_path))

        entries = []
        try:
            manager = mw.translation_handler.glossary_handler.glossary_manager
            entries = list(manager.get_entries() or [])
        except Exception:
            pass
        glossary = glossary_states(entries)
        review_backlog = sum(
            1 for entry in entries if bool(getattr(entry, "is_unconfirmed", False))
        )
        glossary_state = StepState(
            NOT_STARTED if not entries else PARTIAL if review_backlog else DONE,
            (
                "automatic pass not run"
                if not entries
                else f"{len(entries)} terms; {review_backlog} awaiting review"
            ),
        )

        seeds = []
        try:
            rules = getattr(mw, "current_game_rules", None)
            getter = getattr(rules, "get_glossary_seed_entries", None)
            if callable(getter):
                seeds = getter() or []
        except Exception:
            seeds = []

        store = getattr(mw, "data_store", None)
        markup_project = find_markup_project(script_path, project_dir)
        self._markup_path = str(getattr(markup_project, "source_path", "") or "")
        return {
            "markup": markup_state(markup_project, has_script=has_script),
            "context": present(
                bool(getattr(client, "db_path", None)),
                "story context built",
                "no story context yet",
            ),
            "structural_seed": structural_seed_state(seeds, entries),
            "speakers": speaker_names_state(
                load_speaker_aliases(project_dir), self._speaker_codes(project_dir)
            ),
            "seed": glossary["seed"],
            "describe": glossary["describe"],
            "translate": glossary["translate"],
            "glossary": glossary_state,
            "text": translation_state(
                getattr(store, "data", None),
                getattr(store, "edited_file_data", None),
                getattr(store, "edited_data", None),
            ),
        }

    def _speaker_codes(self, project_dir) -> set:
        """Placeholder codes the plugin gives rows, computed once per project.

        This walks every row through the plugin, which is far too much to redo
        each time the window is activated -- and it cannot change while the
        project stays open: naming a code does not stop the plugin reporting it.
        """
        cached = self._codes_cache
        if cached is not None and cached[0] == project_dir:
            return cached[1]
        codes = set()
        try:
            from handlers.speaker_merge_handler import SpeakerMergeHandler

            codes = SpeakerMergeHandler(self.mw).placeholder_codes()
        except Exception as exc:
            log_debug(f"Pipeline wizard: counting speaker codes failed: {exc}")
        self._codes_cache = (project_dir, codes)
        return codes

    def refresh(self) -> None:
        """Re-read the project and redraw. Cheap enough to run on every return."""
        try:
            self._states = self._probe()
        except Exception as exc:
            log_debug(f"Pipeline wizard: probing failed: {exc}")
            self._states = {}

        # Recomputed here, not only at construction: loading another project can
        # bring a different plugin, and with it a different set of steps.
        self._steps = steps_for(capabilities_of(self.mw))

        current = self._current_key()
        self.list.blockSignals(True)
        self.list.clear()
        items: Dict[str, QTreeWidgetItem] = {}
        for step in self._steps:
            state = self._state_for(step)
            label = (
                f"{_ICONS.get(state.state, _ICONS[NOT_STARTED])}  {step.title}\n"
                f"      {state.detail}"
            )
            host = items.get(step.parent) if step.parent else None
            item = QTreeWidgetItem(host or self.list, [label])
            item.setData(0, _STEP_ROLE, step.key)
            items[step.key] = item
        self.list.expandAll()
        self.list.blockSignals(False)

        done = overall([self._state_for(step) for step in self._steps])
        self.headline.setText(f"Localization pipeline — {done.detail}")
        self.select_step(current or self._first_unfinished())

    def select_step(self, key: str) -> None:
        """Bring one step to the front, for a shortcut that names it."""
        item = self._item_for(key)
        if item is not None:
            self.list.setCurrentItem(item)

    def _item_for(self, key: str):
        walker = QTreeWidgetItemIterator(self.list)
        while walker.value():
            item = walker.value()
            if item.data(0, _STEP_ROLE) == key:
                return item
            walker += 1
        return None

    def _current_key(self) -> str:
        item = self.list.currentItem()
        return item.data(0, _STEP_ROLE) if item is not None else ""

    def _step_for(self, key: str) -> Optional[Step]:
        return next((step for step in self._steps if step.key == key), None)

    def _state_for(self, step: Step) -> StepState:
        return self._states.get(step.key, StepState(NOT_STARTED, "unknown"))

    def _first_unfinished(self) -> str:
        for step in self._steps:
            if self._state_for(step).state != DONE:
                return step.key
        return self._steps[0].key if self._steps else ""

    # -- signals ------------------------------------------------------------

    def changeEvent(self, event) -> None:
        """Re-read the project whenever the user comes back to this window.

        Non-modal means a step's tool runs alongside the wizard, so triggering
        it tells us nothing about the result. Coming back does.
        """
        super().changeEvent(event)
        if event.type() == QEvent.Type.ActivationChange and self.isActiveWindow():
            if hasattr(self, "list"):
                self.refresh()

    def _on_current_changed(self, current=None, _previous=None) -> None:
        key = current.data(0, _STEP_ROLE) if current is not None else self._current_key()
        step = self._step_for(key) if key else None
        if step is not None:
            self._show_step(step)

    def _show_step(self, step: Step) -> None:
        state = self._state_for(step)
        self.title.setText(step.title)
        self.state_label.setText(
            f"{_ICONS.get(state.state, _ICONS[NOT_STARTED])}  {state.detail}"
        )
        self.why.setText(step.why)
        self.run_button.setVisible(bool(step.run))
        self.run_button.setText(step.button or "")
        self.stack.setCurrentWidget(self._page_for(step))

    def _page_for(self, step: Step) -> QWidget:
        """The embedded tool for this step, built on first view.

        Lazily, and never fatally: a tool that cannot start on this project
        leaves the user with the explanation rather than an empty window.
        """
        if step.embed is None:
            return self._explain_page
        self._publish_markup_project()
        widget = self._embedded.get(step.key)
        if widget is None:
            try:
                widget = step.embed(self.mw, self.stack)
            except Exception as exc:
                log_debug(f"Pipeline wizard: embedding {step.key} failed: {exc}")
                return self._explain_page
            if not isinstance(widget, QWidget):
                log_debug(f"Pipeline wizard: {step.key} embedded no widget")
                return self._explain_page
            self._embedded[step.key] = widget
            self.stack.addWidget(widget)
        # Even freshly built: the earlier steps keep changing what it should
        # read, and marking the script up is a step of this same wizard.
        reload_hook = getattr(widget, "_load_active_markup_studio_project", None)
        if callable(reload_hook):
            try:
                reload_hook()
            except Exception as exc:
                log_debug(f"Pipeline wizard: refreshing {step.key} failed: {exc}")
        return widget

    def _publish_markup_project(self) -> None:
        """Hand the markup project the wizard found to whoever asks for it.

        Step one already located it on disk, so asking the user to browse for
        the same file in step two is busywork. The Context Builder looks for an
        active project on the main window, so telling it there is enough -- and
        the file field stays, for pointing it at a different project.
        """
        if not self._markup_path or not os.path.exists(self._markup_path):
            return
        current = getattr(self.mw, "script_markup_studio_project_path", "")
        if not isinstance(current, str) or not current or not os.path.exists(current):
            self.mw.script_markup_studio_project_path = self._markup_path

    def _run_current(self) -> None:
        step = self._step_for(self._current_key())
        if step is None or step.run is None:
            return
        try:
            step.run(self.mw)
        except Exception as exc:
            log_debug(f"Pipeline wizard: launching {step.key} failed: {exc}")
        self.refresh()
