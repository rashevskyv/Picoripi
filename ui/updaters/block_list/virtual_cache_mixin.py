"""Virtual folder cache restore/persist and story row helpers."""
from __future__ import annotations

import re
from core.mempalace.story_timeline import (
    StoryVirtualProjection,
    story_virtual_projection_from_dict,
    story_virtual_projection_to_dict,
)
from core.story_context_overrides import iter_story_context_overrides
from core.manual_story_structures import apply_manual_story_structures
from core.mempalace.dialogue_mapping import canonicalize_dialogue_text

class VirtualCacheMixin:
    """Virtual folder cache restore/persist and story row helpers."""

    @staticmethod
    def _rows_from_cache(groups) -> dict[str, list[tuple[int, int]]]:
        if not isinstance(groups, dict):
            return {}
        return {
            str(name): [tuple(row) for row in rows if isinstance(row, (list, tuple)) and len(row) == 2]
            for name, rows in groups.items()
        }

    def _restore_persisted_virtual_cache(self, wing_name: str) -> bool:
        cache = getattr(self.mw.data_store, "virtual_block_cache", {})
        if (
            not isinstance(cache, dict)
            or cache.get("version") != 1
            or cache.get("wing_name") != wing_name
            or cache.get("data_shape") != self._data_shape_signature()
        ):
            return False
        projection = story_virtual_projection_from_dict(cache.get("story_projection"))
        if not isinstance(projection, StoryVirtualProjection):
            return False
        project = getattr(getattr(self.mw, "project_manager", None), "project", None)
        projection = apply_manual_story_structures(projection, project)
        self._story_projection_cache = projection
        self._chapters_cache = list(projection.roots)
        self._chapter_mappings_cache = None
        self._chapters_cache_wing_name = wing_name
        self._reference_item_groups_cache = self._rows_from_cache(cache.get("item_mappings"))
        window_groups = self._rows_from_cache(cache.get("window_groups"))
        self._window_kind_groups_cache = {
            name: set(rows) for name, rows in window_groups.items()
        }
        self._chapters_load_error = None
        self._is_loading_chapters = False
        return True

    def _persist_virtual_cache(self, wing_name: str, item_mappings) -> None:
        projection = self._story_projection_cache
        if not isinstance(projection, StoryVirtualProjection):
            return
        window_groups = self._window_kind_groups()
        cache = {
            "version": 1,
            "wing_name": wing_name,
            "data_shape": self._data_shape_signature(),
            "story_projection": story_virtual_projection_to_dict(projection),
            "item_mappings": {
                name: [list(row) for row in rows]
                for name, rows in item_mappings.items()
            },
            "window_groups": {
                name: [list(row) for row in sorted(rows)]
                for name, rows in window_groups.items()
            },
        }
        if cache == getattr(self.mw.data_store, "virtual_block_cache", {}):
            return
        self.mw.data_store.virtual_block_cache = cache
        scheduler = getattr(self.data_processor, "schedule_autosave", None)
        if callable(scheduler):
            scheduler()

    def _resolve_story_mapping(self, mapping):
        """Resolve a normalized story relation to one physical project string."""
        try:
            block_idx = int(mapping.game_block_id)
            string_idx = int(mapping.string_index)
            data = getattr(self.mw.data_store, "data", [])
            if 0 <= block_idx < len(data) and 0 <= string_idx < len(data[block_idx]):
                return block_idx, string_idx
        except (TypeError, ValueError, IndexError):
            pass
        handler = getattr(self.mw, "list_selection_handler", None)
        if handler is not None:
            return handler.resolve_bmg_id_to_indices(mapping.game_string_id)
        return None

    def _story_mapping_indices(self, mappings) -> list[tuple[int, int]]:
        resolved = []
        seen = set()
        for mapping in mappings:
            indices = self._resolve_story_mapping(mapping)
            if indices is not None and indices not in seen:
                seen.add(indices)
                resolved.append(indices)
        return resolved

    @staticmethod
    def _item_match_text(value: str) -> str:
        canonical = canonicalize_dialogue_text(str(value or ""))
        return " ".join(re.findall(r"[\w']+", canonical.casefold()))

    def _reference_item_mappings(self, client, document_id):
        """Derive conservative exact/contained links for the non-dialogue item catalogue."""
        item_mappings = {}
        reverse = {}
        if client is None or document_id is None:
            return item_mappings, reverse
        references = client.get_reference_items(document_id)
        prepared = []
        for reference in references:
            name = self._item_match_text(reference.name)
            description = self._item_match_text(reference.description)
            combined = " ".join(part for part in (name, description) if part)
            prepared.append((reference.name, tuple(x for x in (name, description, combined) if x)))
        for block_idx, block in enumerate(getattr(self.mw.data_store, "data", [])):
            for string_idx, raw in enumerate(block):
                game = self._item_match_text(raw)
                if len(game) < 3:
                    continue
                matches = []
                for item_name, variants in prepared:
                    if any(game == variant or (len(game) >= 10 and f" {game} " in f" {variant} ") for variant in variants):
                        matches.append(item_name)
                if len(set(matches)) == 1:
                    name = matches[0]
                    item_mappings.setdefault(name, []).append((block_idx, string_idx))
                    reverse[(block_idx, string_idx)] = name
        return item_mappings, reverse

    def _apply_manual_item_overrides(self, item_mappings):
        """Overlay explicit Item/None assignments without mutating the cached scan."""
        combined = {name: list(rows) for name, rows in item_mappings.items()}
        for (block_idx, string_idx), assignment in self._story_context_overrides().items():
            if "item" not in assignment:
                continue
            row = (block_idx, string_idx)
            for rows in combined.values():
                if row in rows:
                    rows.remove(row)
            item_name = str(assignment.get("item") or "None").strip()
            if item_name.casefold() != "none":
                combined.setdefault(item_name, []).append(row)
        return {name: rows for name, rows in combined.items() if rows}

    def _story_context_overrides(self) -> dict[tuple[int, int], dict]:
        """Read manual structure overrides once for one tree rebuild."""
        if self._story_context_overrides_cache is None:
            result = {
                (block_idx, string_idx): assignment
                for block_idx, string_idx, assignment in iter_story_context_overrides(self.mw)
            }
            if not self._cache_story_overrides:
                return result
            self._story_context_overrides_cache = result
        return self._story_context_overrides_cache

    def _story_structure_overrides(self) -> dict[tuple[int, int], dict]:
        """Return the structure-only subset without filtering it for every Story node."""
        if self._story_structure_overrides_cache is None:
            result = {
                row: assignment
                for row, assignment in self._story_context_overrides().items()
                if "structure_id" in assignment
            }
            if not self._cache_story_overrides:
                return result
            self._story_structure_overrides_cache = result
        return self._story_structure_overrides_cache

    def _story_override_index(self):
        """Index manual Story rows by target so each tree node is O(its own rows)."""
        if self._story_override_index_cache is None:
            overrides = self._story_structure_overrides()
            by_structure = {}
            for row, assignment in overrides.items():
                structure_id = assignment.get("structure_id")
                if structure_id not in (None, "story:none"):
                    by_structure.setdefault(structure_id, []).append(row)
            result = (set(overrides), by_structure)
            if not self._cache_story_overrides:
                return result
            self._story_override_index_cache = result
        return self._story_override_index_cache

    def _all_game_rows(self) -> set[tuple[int, int]]:
        """Non-blank source rows. Padding stays in physical blocks, not virtual folders."""
        return {
            (block_idx, string_idx)
            for block_idx, block in enumerate(getattr(self.mw.data_store, "data", []))
            for string_idx in range(len(block))
            if not self._is_blank_row(block_idx, string_idx)
        }

    def _is_blank_row(self, block_idx: int, string_idx: int) -> bool:
        data = getattr(getattr(self.mw, "data_store", None), "data", None)
        if not isinstance(data, list) or not (0 <= block_idx < len(data)):
            return False
        block = data[block_idx]
        if not isinstance(block, (list, tuple)) or not (0 <= string_idx < len(block)):
            return False
        return not str(block[string_idx] or "").strip()

    def _virtual_scope(self, allowed_rows=None) -> set[tuple[int, int]]:
        """Rows a virtual folder may hold: ``allowed_rows`` or all game rows, minus blanks."""
        scope = set(allowed_rows) if allowed_rows is not None else self._all_game_rows()
        return {row for row in scope if not self._is_blank_row(*row)}

    def _story_linked_rows(self, projection: StoryVirtualProjection) -> set[tuple[int, int]]:
        linked = set()

        def visit(folder):
            linked.update(self._story_mapping_indices(folder.mappings))
            for child in folder.children:
                visit(child)

        for root in projection.roots:
            visit(root)
        overrides = self._story_structure_overrides()
        linked.difference_update(overrides)
        for (block_idx, string_idx), assignment in overrides.items():
            if assignment.get("structure_id") not in (None, "story:none"):
                linked.add((block_idx, string_idx))
        return linked
