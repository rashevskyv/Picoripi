import json
from dataclasses import replace

import pytest

from core.script_markup import (
    HIERARCHY_FORMAT_VERSION,
    HIERARCHY_PROJECT_FORMAT,
    HierarchyProjectError,
    HierarchyImportStatus,
    HierarchyType,
    default_type_definitions,
    load_hierarchy_project,
    parse_hierarchy_project,
    hierarchy_import_status,
)


def _payload():
    definitions = default_type_definitions()
    return {
        "format": HIERARCHY_PROJECT_FORMAT,
        "version": HIERARCHY_FORMAT_VERSION,
        "source_path": "C:/scripts/raw.txt",
        "raw_text": "Act I\nChapter One\nScene One\nMIDNA\nHello.\nTerm\n",
        "type_definitions": [
            {
                "type_id": item.type_id,
                "label": item.label,
                "description": item.description,
                "color": item.color,
            }
            for item in definitions.values()
        ],
        "hierarchy_marks": [
            {"start_line": 0, "end_line": 5, "depth": 0, "type_id": HierarchyType.STRUCTURE, "order": 1, "origin": "manual", "approved": True},
            {"start_line": 1, "end_line": 5, "depth": 1, "type_id": HierarchyType.STRUCTURE, "order": 2, "origin": "manual", "approved": True},
            {"start_line": 2, "end_line": 5, "depth": 2, "type_id": HierarchyType.STRUCTURE, "order": 3, "origin": "manual", "approved": True},
            {"start_line": 3, "end_line": 3, "depth": 3, "type_id": HierarchyType.SPEAKER, "order": 4, "origin": "manual", "approved": True},
            {"start_line": 4, "end_line": 4, "depth": 4, "type_id": HierarchyType.TEXT, "order": 5, "origin": "manual", "approved": True},
            {"start_line": 5, "end_line": 5, "depth": 3, "type_id": HierarchyType.GLOSSARY, "order": 6, "origin": "ai", "approved": False},
        ],
    }


def test_parse_hierarchy_project_is_deterministic_and_separates_unapproved_marks():
    first = parse_hierarchy_project(_payload())
    second = parse_hierarchy_project(_payload())

    assert first == second
    assert first.node_counts() == {
        "act": 1,
        "chapter": 1,
        "scene": 1,
        "structure": 0,
        "speaker": 1,
        "dialogue": 1,
        "glossary": 0,
        "item": 0,
        "item_description": 0,
    }
    assert len(first.unapproved_marks) == 1


@pytest.mark.parametrize(
    ("field", "value", "message"),
    [
        ("format", "other.format", "Unsupported format"),
        ("version", HIERARCHY_FORMAT_VERSION + 1, "Unsupported hierarchy project version"),
        ("raw_text", None, "raw_text must be a string"),
        ("type_definitions", {}, "type_definitions must be an array"),
        ("hierarchy_marks", {}, "hierarchy_marks must be an array"),
    ],
)
def test_parse_hierarchy_project_rejects_invalid_contract(field, value, message):
    payload = _payload()
    payload[field] = value

    with pytest.raises(HierarchyProjectError, match=message):
        parse_hierarchy_project(payload)


def test_parse_hierarchy_project_rejects_mark_outside_raw_text():
    payload = _payload()
    payload["hierarchy_marks"][0]["end_line"] = 99

    with pytest.raises(HierarchyProjectError, match="outside raw_text"):
        parse_hierarchy_project(payload)


def test_load_hierarchy_project_hashes_exact_source_file(tmp_path):
    path = tmp_path / "script_markup_project.json"
    path.write_text(json.dumps(_payload(), ensure_ascii=False), encoding="utf-8")

    project = load_hierarchy_project(path)

    assert project.source_path == str(path.resolve())
    assert len(project.source_hash) == 64


def test_load_hierarchy_project_rejects_corrupted_json(tmp_path):
    path = tmp_path / "script_markup_project.json"
    path.write_text("{broken", encoding="utf-8")

    with pytest.raises(HierarchyProjectError, match="Invalid UTF-8 JSON"):
        load_hierarchy_project(path)


def test_hierarchy_import_status_compares_path_hash_and_version():
    project = replace(
        parse_hierarchy_project(_payload()),
        source_path="C:/project/script_markup_project.json",
        source_hash="current-hash",
    )

    assert hierarchy_import_status(project) == HierarchyImportStatus.NOT_IMPORTED
    assert hierarchy_import_status(
        project,
        imported_path=project.source_path,
        imported_hash=project.source_hash,
        imported_version=project.version,
    ) == HierarchyImportStatus.UP_TO_DATE
    assert hierarchy_import_status(
        project,
        imported_path=project.source_path,
        imported_hash="old-hash",
        imported_version=project.version,
    ) == HierarchyImportStatus.SOURCE_CHANGED
    assert hierarchy_import_status(
        project,
        imported_path="C:/project/another.json",
        imported_hash=project.source_hash,
        imported_version=project.version,
    ) == HierarchyImportStatus.NOT_IMPORTED
