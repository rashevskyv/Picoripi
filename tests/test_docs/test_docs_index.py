"""docs/INDEX.md is generated from the header of each document and stays in step with them (WP7 7.1)."""
from tools import docs_index


def test_the_repository_s_headers_and_index_are_up_to_date():
    assert docs_index.check() == []


def test_every_document_under_docs_has_a_header_except_the_generated_ones():
    for path in docs_index.documents():
        fields, _body = docs_index.split_header(docs_index.read(path))
        assert fields.get("status") in docs_index.STATUSES, path
        assert fields.get("updated") and fields.get("owns") and fields.get("tokens"), path
    assert docs_index.NO_HEADER == {"docs/INDEX.md", "docs/PLUGIN_CONTRACT.md"}


def test_a_ukrainian_page_has_the_same_status_and_owner_as_its_english_twin():
    for path in docs_index.documents():
        if not path.startswith("docs/wiki/uk/"):
            continue
        twin, _ = docs_index.split_header(docs_index.read("docs/wiki/" + path[len("docs/wiki/uk/"):]))
        fields, _ = docs_index.split_header(docs_index.read(path))
        assert (fields["status"], fields["owns"]) == (twin["status"], twin["owns"]), path


def test_header_round_trip_keeps_the_body_and_the_field_order():
    text = "---\nstatus: current\nupdated: 2026-10-02\nowns: core/x\ntokens: 0.1k\npurpose: A thing\n---\n# Title\n\nBody: with a colon\n"

    fields, body = docs_index.split_header(text)

    assert fields == {"status": "current", "updated": "2026-10-02", "owns": "core/x", "tokens": "0.1k", "purpose": "A thing"}
    assert body == "# Title\n\nBody: with a colon\n"
    assert docs_index.join_header(fields, body) == text


def test_a_document_without_a_header_is_all_body():
    assert docs_index.split_header("# Title\n---\nnot a header\n---\n") == ({}, "# Title\n---\nnot a header\n---\n")


def test_cyrillic_text_costs_more_tokens_than_latin_text_of_the_same_length():
    assert docs_index.estimate_tokens("а" * 2300) == 1000
    assert docs_index.estimate_tokens("a" * 3800) == 1000
    assert docs_index.format_tokens(1249) == "1.2k" and docs_index.format_tokens(20) == "0.1k"
    assert docs_index.parse_tokens("3.9k") == 3900


def test_a_stale_token_count_is_reported_only_when_it_is_far_off(tmp_path, monkeypatch):
    monkeypatch.setattr(docs_index, "ROOT", tmp_path)
    (tmp_path / "docs").mkdir()
    header = "---\nstatus: current\nupdated: 2026-10-02\nowns: x\ntokens: 1.0k\npurpose: p\n---\n"
    (tmp_path / "docs" / "near.md").write_text(header + "a" * 4300, encoding="utf-8")     # ~1.1k: within tolerance
    (tmp_path / "docs" / "far.md").write_text(header + "a" * 9000, encoding="utf-8")      # ~2.4k

    assert docs_index.problems("docs/near.md") == []
    assert docs_index.problems("docs/far.md") == ["docs/far.md: header says 1.0k, the text is about 2.4k"]


def test_missing_fields_and_unknown_statuses_are_reported(tmp_path, monkeypatch):
    monkeypatch.setattr(docs_index, "ROOT", tmp_path)
    (tmp_path / "docs").mkdir()
    (tmp_path / "docs" / "bare.md").write_text("# no header\n", encoding="utf-8")
    (tmp_path / "docs" / "odd.md").write_text("---\nstatus: maybe\nupdated: 2026-10-02\ntokens: 0.1k\n---\nx\n", encoding="utf-8")

    assert docs_index.problems("docs/bare.md") == ["docs/bare.md: no header"]
    assert docs_index.problems("docs/odd.md") == [
        "docs/odd.md: header has no 'owns'",
        "docs/odd.md: header has no 'purpose'",
        "docs/odd.md: status 'maybe' is not one of current, design, archive, merge, delete",
    ]


def test_write_refreshes_the_counts_and_the_index(tmp_path, monkeypatch):
    monkeypatch.setattr(docs_index, "ROOT", tmp_path)
    monkeypatch.setattr(docs_index, "EXTRA", ())
    (tmp_path / "docs" / "wiki" / "uk").mkdir(parents=True)
    header = "---\nstatus: current\nupdated: 2026-10-02\nowns: ui/\ntokens: 0.1k\n{purpose}---\n"
    (tmp_path / "docs" / "wiki" / "1_Guide.md").write_text(header.format(purpose="purpose: The guide\n") + "a" * 7600, encoding="utf-8")
    (tmp_path / "docs" / "wiki" / "uk" / "1_Guide.md").write_text(header.format(purpose="") + "а" * 4600, encoding="utf-8")

    assert docs_index.main(["--check"]) == 1
    assert docs_index.main(["--write"]) == 0

    index = (tmp_path / "docs" / "INDEX.md").read_text(encoding="utf-8")
    assert "| `docs/wiki/1_Guide.md` (+uk) | The guide | 2.0k | current | ui/ |" in index
    assert "uk/1_Guide" not in index                      # a translation is not a second row
    assert "tokens: 2.0k" in (tmp_path / "docs" / "wiki" / "uk" / "1_Guide.md").read_text(encoding="utf-8")
    assert docs_index.main(["--check"]) == 0
