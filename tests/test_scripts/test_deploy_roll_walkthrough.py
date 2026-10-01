import importlib.util
from pathlib import Path

_spec = importlib.util.spec_from_file_location(
    "picoripi_deploy_script", Path(__file__).parents[2] / "scripts" / "deploy.py"
)
deploy = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(deploy)


def test_roll_walkthrough_archives_and_resets(tmp_path):
    src = tmp_path / "walkthrough.md"
    src.write_text("# Walkthrough\n\nreal content\n", encoding="utf-8")
    archive = tmp_path / "history"

    dst = deploy.roll_walkthrough("1.2.3", src=src, archive_dir=archive)

    assert dst == archive / "v1.2.3.md"
    assert "real content" in dst.read_text(encoding="utf-8")
    assert src.read_text(encoding="utf-8") == deploy.WALKTHROUGH_STUB
    # A second release without a new walkthrough must not overwrite the archive with the stub.
    assert deploy.roll_walkthrough("1.2.3", src=src, archive_dir=archive) is None
    assert "real content" in dst.read_text(encoding="utf-8")
