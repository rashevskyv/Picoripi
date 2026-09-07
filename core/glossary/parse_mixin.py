"""Markdown/JSON load, persist, and path helpers for GlossaryManager."""
from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional, Sequence

import re

from core.glossary.models import GlossaryEntry
from core.glossary.notes import _entry_to_dict, _fragments_from_raw, _variants_from_raw
from utils.logging_utils import log_debug


class ParseMixin:
    """Markdown/JSON load, persist, and path helpers."""

    def load_from_text(
        self,
        *,
        plugin_name: Optional[str],
        glossary_path: Optional[Path],
        raw_text: str,
    ) -> None:
        """Populate glossary from text buffer (either JSON or Markdown)."""
        self._plugin_name = plugin_name
        self._glossary_path = glossary_path
        sanitized_text = (raw_text or "").replace('\uFEFF', '')
        self._raw_text = sanitized_text
        
        # Check if text is JSON
        is_json = False
        if glossary_path and glossary_path.suffix.lower() == '.json':
            is_json = True
        elif not glossary_path and sanitized_text.strip().startswith(('[', '{')):
            is_json = True
            
        if is_json:
            try:
                import json
                data = json.loads(sanitized_text) if sanitized_text.strip() else []
                self._entries = []
                self._section_order = []
                sections_seen = set()
                for item in data:
                    entry = GlossaryEntry(
                        original=item.get("original", ""),
                        translation=item.get("translation", ""),
                        notes=item.get("notes", ""),
                        section=item.get("section"),
                        profiled=bool(item.get("profiled", False)),
                        status=str(item.get("status", "") or ""),
                        icon=str(item.get("icon", "") or ""),
                        fragments=_fragments_from_raw(item.get("fragments")),
                        translation_variants=_variants_from_raw(item.get("translation_variants")),
                        provisional=bool(item.get("provisional", False)),
                        suggested_name=str(item.get("suggested_name", "") or ""),
                        suggested_name_evidence=str(
                            item.get("suggested_name_evidence", "") or ""
                        ),
                    )
                    if entry.is_valid():
                        self._entries.append(entry)
                        sec = entry.section
                        if sec and sec not in sections_seen:
                            sections_seen.add(sec)
                            self._section_order.append(sec)
            except Exception as e:
                log_debug(f"GlossaryManager: Failed to parse JSON glossary: {e}")
                self._entries = []
        else:
            self._entries = self._parse_markdown(self._raw_text)
            
        self._build_pattern_cache()
        log_debug(
            f"GlossaryManager: loaded {len(self._entries)} entries for plugin "
            f"{plugin_name or '<global>'} from {str(glossary_path) if glossary_path else '<memory>'}"
        )

    def refresh_from_disk(self) -> None:
        """Update the from disk."""
        if self._glossary_path and self._glossary_path.exists():
            text = self._glossary_path.read_text(encoding='utf-8')
            self.load_from_text(
                plugin_name=self._plugin_name,
                glossary_path=self._glossary_path,
                raw_text=text,
            )
        else:
            # No glossary file - reset cache to empty
            self.load_from_text(
                plugin_name=self._plugin_name,
                glossary_path=self._glossary_path,
                raw_text="",
            )

    def get_raw_text(self) -> str:
        """Get the raw text."""
        return self._raw_text

    @property
    def glossary_path(self) -> Optional[Path]:
        """The file this glossary persists to, or None when memory-only.

        None means every write is dropped on the next reload, so callers that
        are about to produce a lot of entries should check it first.
        """
        return self._glossary_path

    def backup_file(self) -> Optional[Path]:
        """Copy the glossary file to ``<name>.bak``. Returns the backup path."""
        path = self._glossary_path
        if not path or not path.exists():
            return None
        backup = path.with_suffix(path.suffix + '.bak')
        try:
            backup.write_bytes(path.read_bytes())
            return backup
        except Exception as exc:
            log_debug(f"GlossaryManager: failed to back up {path.name}: {exc}")
            return None

    def save_to_disk(self) -> None:
        """Save to disk."""
        self._persist(write_only=True)

    def _parse_markdown(self, text: str) -> List[GlossaryEntry]:
        """Internal helper to parse markdown."""
        self._header_lines = []
        self._section_order = []
        if not text:
            return []

        entries: List[GlossaryEntry] = []
        current_section: Optional[str] = None
        seen_sections: set[str] = set()
        header_phase = True

        for raw_line in text.splitlines():
            stripped = raw_line.strip()

            if not stripped:
                if header_phase:
                    self._header_lines.append(raw_line)
                continue

            if stripped.startswith('## '):
                header_phase = False
                current_section = stripped[3:].strip()
                if current_section and current_section not in seen_sections:
                    seen_sections.add(current_section)
                    self._section_order.append(current_section)
                continue

            if header_phase and (stripped.startswith('#') or stripped.startswith('>')):
                self._header_lines.append(raw_line)
                continue

            if stripped.startswith('|'):
                header_phase = False
                if stripped.startswith('|-'):
                    continue
                parts = [part.strip() for part in stripped.strip('|').split('|')]
                if len(parts) < 3:
                    continue
                header_check = [p.lower() for p in parts[:3]]
                if header_check[0] in {'оригінал', 'original'} and header_check[1] in {'переклад', 'translation'}:
                    continue
                original, translation = parts[0], parts[1]
                notes = parts[2] if len(parts) >= 3 else ""
                # Replace <br> / <br/> with \n to restore newlines inside notes
                notes = re.sub(r'<br\s*/?>', '\n', notes, flags=re.IGNORECASE)
                notes = notes.replace(r'\|', '|')
                
                original = original.replace(r'\|', '|')
                translation = translation.replace(r'\|', '|')
                
                entry = GlossaryEntry(original=original, translation=translation, notes=notes, section=current_section)
                if entry.is_valid():
                    entries.append(entry)
                continue

            if '	' in raw_line:
                header_phase = False
                segments = raw_line.split('	')
                while len(segments) < 3:
                    segments.append('')
                original, translation, notes = [segment.strip() for segment in segments[:3]]
                notes = re.sub(r'<br\s*/?>', '\n', notes, flags=re.IGNORECASE)
                notes = notes.replace(r'\|', '|')
                
                original = original.replace(r'\|', '|')
                translation = translation.replace(r'\|', '|')
                
                entry = GlossaryEntry(original=original, translation=translation, notes=notes, section=current_section)
                if entry.is_valid():
                    entries.append(entry)

        return entries

    def _table_lines(self, entries: Sequence[GlossaryEntry]) -> List[str]:
        """Internal helper to table lines."""
        lines = ['| Original | Translation | Notes |', '|----------|-------------|-------|']
        for entry in entries:
            # Escape newlines as <br> and pipe characters as \| inside markdown table cells
            safe_notes = (entry.notes or "").replace('\n', '<br>')
            safe_notes = safe_notes.replace('|', r'\|')
            
            # Keep original and translation single-line and pipe-safe just in case
            safe_orig = (entry.original or "").replace('\n', ' ').replace('|', r'\|')
            safe_trans = (entry.translation or "").replace('\n', ' ').replace('|', r'\|')
            
            lines.append(f"| {safe_orig} | {safe_trans} | {safe_notes} |")
        return lines

    def _generate_markdown(self) -> str:
        """Internal helper to generate markdown."""
        lines: List[str] = []
        if self._header_lines:
            lines.extend(self._header_lines)
            if lines and lines[-1].strip():
                lines.append('')

        default_entries = [entry for entry in self._entries if not entry.section]
        if default_entries:
            lines.extend(self._table_lines(default_entries))
            lines.append('')

        section_to_entries: Dict[str, List[GlossaryEntry]] = {}
        for entry in self._entries:
            if entry.section:
                section_to_entries.setdefault(entry.section, []).append(entry)

        # Collect active sections preserving original order and appending new ones dynamically
        all_sections_present = {entry.section for entry in self._entries if entry.section}
        active_sections = []
        for s in self._section_order:
            if s in all_sections_present:
                active_sections.append(s)
        for s in sorted(all_sections_present):
            if s not in active_sections:
                active_sections.append(s)

        for section in active_sections:
            section_entries = section_to_entries.get(section, [])
            if not section_entries:
                continue
            if lines and lines[-1].strip():
                lines.append('')
            lines.append(f'## {section}')
            lines.append('')
            lines.extend(self._table_lines(section_entries))
            lines.append('')

        markdown_lines = [line.rstrip() for line in lines if line is not None]
        markdown = "\n".join(markdown_lines).strip("\n") + "\n"
        return markdown

    def _persist(self, write_only: bool = False) -> None:
        """Internal helper to persist."""
        if self._glossary_path:
            # Migration logic: if current path is .md, migrate it to .json!
            if self._glossary_path.suffix.lower() == '.md':
                json_path = self._glossary_path.with_suffix('.json')
                
                # Create .bak file for safety before deleting
                bak_path = self._glossary_path.with_suffix('.md.bak')
                try:
                    if self._glossary_path.exists():
                        if bak_path.exists():
                            bak_path.unlink()
                        self._glossary_path.rename(bak_path)
                        log_debug(f"GlossaryManager: Renamed legacy glossary {self._glossary_path.name} to backup {bak_path.name}")
                except Exception as e:
                    log_debug(f"GlossaryManager: Failed to rename legacy glossary to backup: {e}")
                
                self._glossary_path = json_path

            # Serialize entries to JSON
            import json
            data_to_save = [_entry_to_dict(entry) for entry in self._entries]
            
            try:
                raw_json = json.dumps(data_to_save, ensure_ascii=False, indent=2) + "\n"
                self._glossary_path.write_text(raw_json, encoding='utf-8')
                self._raw_text = raw_json
                log_debug(f"GlossaryManager: Persisted {len(self._entries)} entries to {self._glossary_path}")
            except Exception as e:
                log_debug(f"GlossaryManager: Failed to write JSON glossary: {e}")
                
            if not write_only:
                self._build_pattern_cache()
        else:
            # In-memory only (e.g. tests)
            # Make sure _raw_text is in sync (we generate Markdown for compatibility/tests that check get_raw_text)
            #
            # Markdown carries no status column and the parser drops rows with an
            # empty translation, so a seed-only entry does not survive a round
            # trip through this text. Anything running the build pipeline must
            # bind a real file first -- say so loudly instead of losing the work.
            if self._entries:
                log_debug(
                    f"GlossaryManager: {len(self._entries)} entries kept in memory only "
                    "(no glossary path bound); they will not survive a reload"
                )
            self._raw_text = self._generate_markdown()
            self._build_pattern_cache()
