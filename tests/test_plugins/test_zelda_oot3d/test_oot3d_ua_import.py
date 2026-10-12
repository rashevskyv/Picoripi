"""tools/oot3d_ua_import.py on a synthetic workspace and a synthetic LayeredFS zip."""
import json
import zipfile
from pathlib import Path

from plugins.zelda_oot3d import sheet_import as si
from tools import oot3d_ua_import as tool
from .test_sheet_import import EU_ENGLISH, make_qm, make_sheet, sheet_row


def _workspace(tmp_path: Path, source_qm: bytes) -> Path:
    ws = tmp_path / "ws"
    (ws / "source" / "romfs" / "message" / "eu").mkdir(parents=True)
    (ws / "source" / "romfs" / "message" / "eu" / "eu.qm").write_bytes(source_qm)
    (ws / "source" / "romfs" / "scene").mkdir(parents=True)
    (ws / "source" / "romfs" / "scene" / "a.zar").write_bytes(b"original a")
    (ws / "source" / "romfs" / "scene" / "c.zar").write_bytes(b"original c")
    return ws


def test_import_writes_changed_romfs_files_and_skips_identical_ones(tmp_path):
    source = make_qm([(1, {EU_ENGLISH: b"Hello\x7f\x00"}), (2, {EU_ENGLISH: b"Bye\x7f\x00"})])
    sheet_values = make_sheet([sheet_row(1, "Hello⟦END⟧", "Привіт⟦END⟧"), sheet_row(2, "Bye⟦END⟧", "")])
    sheet_path = tmp_path / "sheet.json"
    sheet_path.write_text(json.dumps(sheet_values, ensure_ascii=False), encoding="utf-8")
    expected_qm = si.build_eu_qm(source, sheet_values).data
    ws = _workspace(tmp_path, source)
    package = tmp_path / "mod.zip"
    prefix = f"luma/titles/{tool.TITLE_ID}/romfs/"
    with zipfile.ZipFile(package, "w") as archive:
        archive.writestr(prefix + "message/eu/eu.qm", expected_qm)
        archive.writestr(prefix + "scene/a.zar", b"original a")            # identical to the original
        archive.writestr(prefix + "scene/c.zar", b"translated c")          # changed
        archive.writestr(f"luma/titles/{tool.TITLE_ID}/locale.txt", b"EUR EN\n")   # not romfs: ignored

    report = tool.run(ws, sheet_path, package, dry_run=False)

    assert report["package"]["eu_qm_equal"] is True
    assert report["written"] == ["message/eu/eu.qm", "scene/c.zar"]
    assert report["same_as_original"] == ["scene/a.zar"]
    assert report["fallback_ids"] == ["0x00000002"]
    translation = ws / "translation" / "romfs"
    assert (translation / "message" / "eu" / "eu.qm").read_bytes() == expected_qm
    assert (translation / "scene" / "c.zar").read_bytes() == b"translated c"
    assert not (translation / "scene" / "a.zar").exists()


def test_dry_run_writes_nothing(tmp_path):
    source = make_qm([(1, {EU_ENGLISH: b"Hello\x7f\x00"})])
    sheet_path = tmp_path / "sheet.json"
    sheet_path.write_text(json.dumps(make_sheet([sheet_row(1, "Hello⟦END⟧", "Привіт⟦END⟧")]), ensure_ascii=False),
                          encoding="utf-8")
    ws = _workspace(tmp_path, source)
    report = tool.run(ws, sheet_path, None, dry_run=True)
    assert report["written"] == ["message/eu/eu.qm"]
    assert not (ws / "translation").exists()
