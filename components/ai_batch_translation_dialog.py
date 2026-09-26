from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QHBoxLayout, QLabel, QPushButton,
    QFrame, QDialogButtonBox, QWidget, QScrollArea
)
from PyQt6.QtCore import Qt
from PyQt6.QtGui import QFont
from core.i18n import tr


class AIBatchTranslationDialog(QDialog):
    """Dialog providing choice and comprehensive explanation of AI batch translation pipelines."""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.mw = parent
        self.setWindowTitle(tr("AI Batch Translation"))
        self.setMinimumWidth(680)
        self.resize(720, 660)

        self._init_ui()

    def _init_ui(self):
        main_layout = QVBoxLayout(self)
        main_layout.setContentsMargins(18, 16, 18, 16)
        main_layout.setSpacing(12)

        # Header
        header_widget = QWidget(self)
        header_layout = QVBoxLayout(header_widget)
        header_layout.setContentsMargins(0, 0, 0, 0)
        header_layout.setSpacing(4)

        title_label = QLabel(tr("AI Batch Translation Pipeline"), header_widget)
        title_font = QFont()
        title_font.setPointSize(13)
        title_font.setBold(True)
        title_label.setFont(title_font)
        header_layout.addWidget(title_label)

        desc_label = QLabel(
            tr(
                "Choose the translation workflow for your project. A collaborative multi-agent consilium "
                "(Translator + Inline Arbiter/Editor) ensures glossary consistency, character voices, and narrative coherence."
            ),
            header_widget,
        )
        desc_label.setWordWrap(True)
        desc_label.setStyleSheet("color: #555555; font-size: 11px;")
        header_layout.addWidget(desc_label)

        main_layout.addWidget(header_widget)

        # Scrollable cards area
        scroll_area = QScrollArea(self)
        scroll_area.setWidgetResizable(True)
        scroll_area.setFrameShape(QFrame.Shape.NoFrame)

        cards_container = QWidget()
        cards_layout = QVBoxLayout(cards_container)
        cards_layout.setContentsMargins(0, 0, 0, 0)
        cards_layout.setSpacing(10)

        has_data = bool(
            self.mw
            and getattr(self.mw, "data_store", None)
            and getattr(self.mw.data_store, "data", None)
        )
        disabled_tip = tr("Open a project with text blocks to start batch translation.")

        # Card 1: Story First (Chronological)
        self.btn_story_first = QPushButton(tr("Translate Story First"), cards_container)
        self.btn_story_first.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_story_first.clicked.connect(self._run_story_first)
        card_story = self._create_option_card(
            title=tr("Phase 1: Story First (Chronological)"),
            description=tr(
                "Translates dialogue lines and cutscenes in true chronological order (guided by MemePalace timeline or story blocks). "
                "As dialogues are translated, key terminology, character voices, and lore decisions are automatically saved into the "
                "Narrative Ledger (canon memory) for downstream blocks."
            ),
            button=self.btn_story_first,
            badge_text=tr("Step 1"),
            badge_color="#2563eb",
            is_primary=False,
        )
        cards_layout.addWidget(card_story)

        # Card 2: Remaining Blocks (Semantic & System)
        self.btn_remaining_blocks = QPushButton(tr("Translate Remaining Blocks"), cards_container)
        self.btn_remaining_blocks.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_remaining_blocks.clicked.connect(self._run_remaining_blocks)
        card_rem = self._create_option_card(
            title=tr("Phase 2: Remaining Blocks (Semantic & System)"),
            description=tr(
                "Translates menus, UI interfaces, shops, item descriptions, and system messages. "
                "Automatically injects the narrative canon recorded during Phase 1, ensuring names and terms in menus and item descriptions "
                "match story dialogues 100%."
            ),
            button=self.btn_remaining_blocks,
            badge_text=tr("Step 2"),
            badge_color="#0891b2",
            is_primary=False,
        )
        cards_layout.addWidget(card_rem)

        # Card 3: Full Pipeline (Story -> Semantic) [Recommended]
        self.btn_full_pipeline = QPushButton(tr("Run Full Pipeline"), cards_container)
        self.btn_full_pipeline.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_full_pipeline.clicked.connect(self._run_full_pipeline)
        card_full = self._create_option_card(
            title=tr("Full Pipeline: Story ➔ Semantic"),
            description=tr(
                "Recommended for full project translation. Automatically runs Phase 1 (Story First) to establish the narrative canon, "
                "then seamlessly transitions into Phase 2 (Remaining Blocks) without requiring manual intervention."
            ),
            button=self.btn_full_pipeline,
            badge_text=tr("Recommended"),
            badge_color="#16a34a",
            is_primary=True,
        )
        cards_layout.addWidget(card_full)

        # Card 4: Chronological Linear (Legacy)
        self.btn_all_blocks = QPushButton(tr("Translate All Blocks"), cards_container)
        self.btn_all_blocks.setCursor(Qt.CursorShape.PointingHandCursor)
        self.btn_all_blocks.clicked.connect(self._run_all_blocks)
        card_all = self._create_option_card(
            title=tr("Translate All Blocks (Chronological Legacy)"),
            description=tr(
                "Translates all project blocks linearly in sequence without partitioning into story and system phases. "
                "Useful for smaller games or projects with a simple flat text structure."
            ),
            button=self.btn_all_blocks,
            badge_text=tr("Legacy"),
            badge_color="#64748b",
            is_primary=False,
        )
        cards_layout.addWidget(card_all)

        cards_layout.addStretch()
        scroll_area.setWidget(cards_container)
        main_layout.addWidget(scroll_area, 1)

        # Non-blocking rules notice
        notice_frame = QFrame(self)
        notice_frame.setStyleSheet(
            "QFrame { background-color: #f8fafc; border: 1px solid #e2e8f0; border-radius: 6px; padding: 6px; }"
        )
        notice_layout = QHBoxLayout(notice_frame)
        notice_layout.setContentsMargins(8, 6, 8, 6)
        notice_label = QLabel(
            tr(
                "<b>Note:</b> Non-blocking rules apply. Control tag modifications (e.g. [PLAYER] replaced with Link) "
                "and line width overflows will not halt translation. Any layout issues can be adjusted later using Auto-fix."
            ),
            notice_frame,
        )
        notice_label.setWordWrap(True)
        notice_label.setStyleSheet("color: #475569; font-size: 11px;")
        notice_layout.addWidget(notice_label)
        main_layout.addWidget(notice_frame)

        # Dialog Buttons
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Close, self)
        button_box.rejected.connect(self.reject)
        main_layout.addWidget(button_box)

        # Handle button enable state if no project loaded
        if not has_data:
            for btn in (self.btn_story_first, self.btn_remaining_blocks, self.btn_full_pipeline, self.btn_all_blocks):
                btn.setEnabled(False)
                btn.setToolTip(disabled_tip)

    def _create_option_card(
        self,
        title: str,
        description: str,
        button: QPushButton,
        badge_text: str,
        badge_color: str,
        is_primary: bool = False,
    ) -> QFrame:
        card = QFrame(self)
        border_color = "#3b82f6" if is_primary else "#e2e8f0"
        bg_color = "#f0fdf4" if is_primary else "#ffffff"
        card.setStyleSheet(
            f"QFrame {{ background-color: {bg_color}; border: 1px solid {border_color}; "
            f"border-radius: 8px; padding: 8px; }}"
        )

        card_layout = QVBoxLayout(card)
        card_layout.setContentsMargins(10, 8, 10, 8)
        card_layout.setSpacing(6)

        # Top row: Badge + Title + Action Button
        top_row = QHBoxLayout()
        top_row.setContentsMargins(0, 0, 0, 0)
        top_row.setSpacing(8)

        badge = QLabel(f" {badge_text} ", card)
        badge.setStyleSheet(
            f"background-color: {badge_color}; color: #ffffff; font-weight: bold; "
            f"font-size: 10px; border-radius: 4px; padding: 2px 4px;"
        )
        top_row.addWidget(badge)

        card_title = QLabel(title, card)
        title_font = QFont()
        title_font.setPointSize(11)
        title_font.setBold(True)
        card_title.setFont(title_font)
        card_title.setStyleSheet("border: none; background: transparent;")
        top_row.addWidget(card_title)
        top_row.addStretch()

        if is_primary:
            button.setStyleSheet(
                "QPushButton { background-color: #16a34a; color: white; font-weight: bold; "
                "padding: 6px 14px; border-radius: 5px; border: none; } "
                "QPushButton:hover { background-color: #15803d; } "
                "QPushButton:disabled { background-color: #94a3b8; }"
            )
        else:
            button.setStyleSheet(
                "QPushButton { padding: 5px 12px; border-radius: 5px; border: 1px solid #cbd5e1; "
                "background-color: #f8fafc; font-weight: 500; } "
                "QPushButton:hover { background-color: #e2e8f0; } "
                "QPushButton:disabled { color: #94a3b8; background-color: #f1f5f9; }"
            )
        button.setMinimumWidth(160)
        top_row.addWidget(button)
        card_layout.addLayout(top_row)

        # Description text
        desc = QLabel(description, card)
        desc.setWordWrap(True)
        desc.setStyleSheet("color: #475569; font-size: 11px; border: none; background: transparent;")
        card_layout.addWidget(desc)

        return card

    def _run_story_first(self):
        self.accept()
        translator = getattr(self.mw, "translation_handler", None)
        if translator and hasattr(translator, "translate_story_first"):
            translator.translate_story_first()

    def _run_remaining_blocks(self):
        self.accept()
        translator = getattr(self.mw, "translation_handler", None)
        if translator and hasattr(translator, "translate_remaining_blocks"):
            translator.translate_remaining_blocks()

    def _run_full_pipeline(self):
        self.accept()
        translator = getattr(self.mw, "translation_handler", None)
        if translator and hasattr(translator, "translate_all_blocks_pipeline"):
            translator.translate_all_blocks_pipeline()

    def _run_all_blocks(self):
        self.accept()
        translator = getattr(self.mw, "translation_handler", None)
        if translator and hasattr(translator, "translate_all_blocks_chronologically"):
            translator.translate_all_blocks_chronologically()
