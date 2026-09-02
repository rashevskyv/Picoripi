from PyQt6 import QtWidgets

from core.i18n import tr

_FILL_PRESETS = [
    ("Latin  A – Z",                       "la",    "A",      "Z",      "ABCDEFGHIJKLMNOPQRSTUVWXYZ"),
    ("Latin  a – z",                       "la_l",  "a",      "z",      "abcdefghijklmnopqrstuvwxyz"),
    ("Ukrainian  А – Я (uppercase)",       "uk_u",  "\u0410", "\u042F", "АБВГҐДЕЄЖЗИІЇЙКЛМНОПРСТУФХЦЧШЩЬЮЯ"),
    ("Ukrainian  а – я (lowercase)",       "uk_l",  "\u0430", "\u044F", "абвгґдеєжзиіїйклмнопрстуфхцчшщьюя"),
    ("Russian  А – Я (uppercase with Ё)",  "ru_u",  "\u0410", "\u042F", "АБВГДЕЁЖЗИЙКЛМНОПРСТУФХЦЧШЩЪЫЬЭЮЯ"),
    ("Russian  а – я (lowercase with ё)",  "ru_l",  "\u0430", "\u044F", "абвгдеёжзийклмнопрстуфхцчшщъыьэюя"),
    ("Belarusian  А – Я (uppercase)",      "be_u",  "\u0410", "\u042F", "АБВГДЕЁЖЗІЙКЛМНОПРСТУЎФХЦЧШЫЬЭЮЯ"),
    ("Belarusian  а – я (lowercase)",      "be_l",  "\u0430", "\u044F", "абвгдеёжзійклмнопрстуўфхцчшыьэюя"),
    ("Greek  Α – Ω (uppercase)",           "el",    "\u0391", "\u03A9", "ΑΒΓΔΕΖΗΘΙΚΛΜΝΞΟΠΡΣΤΥΦΧΨΩ"),
    ("Greek  α – ω (lowercase)",           "el_l",  "\u03B1", "\u03C9", "αβγδεζηθικλμνξοπρστυφχψω"),
    ("Arabic  \u0621 – \u064A",            "ar",    "\u0621", "\u064A", None),
    ("Hiragana  \u3041 – \u3096",          "ja",    "\u3041", "\u3096", None),
    ("Katakana  \u30A1 – \u30F6",          "ja_k",  "\u30A1", "\u30F6", None),
    ("Hangul syllables (first 32)",        "ko",    "\uAC00", "\uAC1F", None),
    ("Custom (edit below)",                "custom", "",      "",       None),
]

# Map from spellchecker lang code to preset lang_key
_LANG_TO_PRESET = {
    "uk": "uk_u",
    "ru": "ru_u",
    "be": "be_u",
    "bg": "ru_u",
    "sr": "ru_u",
    "mk": "ru_u",
    "el": "el",
    "ar": "ar",
    "ja": "ja",
    "ko": "ko",
}


class FillRangeDialog(QtWidgets.QDialog):
    def __init__(self, parent=None, lang=""):
        super().__init__(parent)
        self.setWindowTitle(tr("Fill From To"))
        self.setModal(True)
        self.resize(380, 260)

        # Determine default preset key from spellchecker language
        base_lang = lang.split("_")[0].split("-")[0].lower() if lang else ""
        default_preset_key = _LANG_TO_PRESET.get(base_lang, "la")

        layout = QtWidgets.QVBoxLayout(self)
        layout.setSpacing(8)

        # --- Alphabet / Language selector ---
        lang_row = QtWidgets.QHBoxLayout()
        lang_row.addWidget(QtWidgets.QLabel(tr("Alphabet:")))
        self.lang_combo = QtWidgets.QComboBox()
        for item in _FILL_PRESETS:
            label, key = item[0], item[1]
            self.lang_combo.addItem(tr(label), key)
        # Select default
        for i, item in enumerate(_FILL_PRESETS):
            key = item[1]
            if key == default_preset_key:
                self.lang_combo.setCurrentIndex(i)
                break
        lang_row.addWidget(self.lang_combo, 1)
        layout.addLayout(lang_row)

        # --- Start / End and Sequence fields ---
        form = QtWidgets.QFormLayout()
        self.input_start = QtWidgets.QLineEdit()
        self.input_start.setPlaceholderText(tr("e.g. A or U+0410 or 0410"))
        self.input_end = QtWidgets.QLineEdit()
        self.input_end.setPlaceholderText(tr("e.g. Z or U+042F or 042F"))
        self.input_sequence = QtWidgets.QLineEdit()
        self.input_sequence.setPlaceholderText(tr("Sequence of characters to fill sequentially"))
        
        form.addRow(tr("Start Character / Code:"), self.input_start)
        form.addRow(tr("End Character / Code:"), self.input_end)
        form.addRow(tr("Sequence Preview / Edit:"), self.input_sequence)
        layout.addLayout(form)

        help_lbl = QtWidgets.QLabel(
            tr(
                "Choose a preset, enter a range, or edit the sequence directly.\n"
                "The table will be filled sequentially starting from the selected row."
            )
        )
        help_lbl.setStyleSheet("color: #88888b; font-size: 11px;")
        layout.addWidget(help_lbl)

        buttons = QtWidgets.QDialogButtonBox(
            QtWidgets.QDialogButtonBox.StandardButton.Ok | QtWidgets.QDialogButtonBox.StandardButton.Cancel,
            self
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        layout.addWidget(buttons)

        # Fill fields from current preset, then connect signal
        self._apply_preset(self.lang_combo.currentIndex())
        self.lang_combo.currentIndexChanged.connect(self._apply_preset)

        # If user edits manually — switch combobox to "Custom" and update sequence
        self.input_start.textEdited.connect(self._on_start_end_edited)
        self.input_end.textEdited.connect(self._on_start_end_edited)
        self.input_sequence.textEdited.connect(self._on_manual_edit)

    # ------------------------------------------------------------------
    def _apply_preset(self, index):
        item = _FILL_PRESETS[index]
        label, key, start_ch, end_ch, explicit_seq = item
        if key == "custom":
            return  # keep whatever user typed
            
        self.input_start.blockSignals(True)
        self.input_end.blockSignals(True)
        self.input_sequence.blockSignals(True)
        
        self.input_start.setText(start_ch)
        self.input_end.setText(end_ch)
        
        if explicit_seq:
            self.input_sequence.setText(explicit_seq)
        else:
            # Generate from start and end
            if start_ch and end_ch:
                try:
                    s_code = ord(start_ch)
                    e_code = ord(end_ch)
                    if s_code <= e_code:
                        seq = "".join(chr(c) for c in range(s_code, e_code + 1))
                        self.input_sequence.setText(seq)
                    else:
                        self.input_sequence.setText("")
                except Exception:
                    self.input_sequence.setText("")
            else:
                self.input_sequence.setText("")
                
        self.input_start.blockSignals(False)
        self.input_end.blockSignals(False)
        self.input_sequence.blockSignals(False)

    def _on_manual_edit(self):
        # Switch combobox to "Custom" silently so auto-apply doesn't override
        custom_idx = next(
            (i for i, item in enumerate(_FILL_PRESETS) if item[1] == "custom"),
            -1
        )
        if custom_idx >= 0 and self.lang_combo.currentIndex() != custom_idx:
            self.lang_combo.blockSignals(True)
            self.lang_combo.setCurrentIndex(custom_idx)
            self.lang_combo.blockSignals(False)

    def _on_start_end_edited(self):
        self._on_manual_edit()
        self._update_sequence_from_start_end()

    def _update_sequence_from_start_end(self):
        start_val, end_val = self.get_range()
        if start_val is not None and end_val is not None:
            if start_val <= end_val:
                try:
                    seq = "".join(chr(c) for c in range(start_val, end_val + 1))
                    self.input_sequence.blockSignals(True)
                    self.input_sequence.setText(seq)
                    self.input_sequence.blockSignals(False)
                except Exception:
                    pass

    # ------------------------------------------------------------------
    def get_sequence_codes(self):
        txt = self.input_sequence.text()
        return [ord(c) for c in txt]

    def get_range(self):
        start_txt = self.input_start.text().strip()
        end_txt = self.input_end.text().strip()
        
        def parse_val(txt):
            if not txt:
                return None
            if txt.upper().startswith("U+") or txt.upper().startswith("0X"):
                clean = txt.replace("U+", "").replace("u+", "").replace("0x", "").replace("0X", "")
                try:
                    return int(clean, 16)
                except ValueError:
                    pass
            if len(txt) > 1 and all(c in "0123456789ABCDEFabcdef" for c in txt):
                try:
                    return int(txt, 16)
                except ValueError:
                    pass
            if len(txt) == 1:
                return ord(txt[0])
            try:
                return int(txt)
            except ValueError:
                pass
            return None

        start_val = parse_val(start_txt)
        end_val = parse_val(end_txt)
        return start_val, end_val

