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


def test_a_development_version_is_bumped_with_its_suffix():
    assert deploy.bump_version("0.3.149-dev") == "0.3.150-dev"
    assert deploy.bump_version("1.2.9") == "1.2.10"
    assert deploy.bump_version("nightly") == "nightly"


def test_a_release_entry_goes_between_unreleased_and_the_last_release(tmp_path, monkeypatch):
    changelog = tmp_path / "CHANGELOG.md"
    changelog.write_text("Intro.\n\n## [Unreleased]\n\n- pending\n\n## [1.2.3] - 2026-01-01\n\n- old\n", encoding="utf-8")
    monkeypatch.setattr(deploy, "CHANGELOG_PATH", changelog)

    deploy.update_changelog("1.2.4", ["a feature"], [], [])

    text = changelog.read_text(encoding="utf-8")
    assert text.index("## [Unreleased]") < text.index("## [1.2.4]") < text.index("### Added\n- a feature") < text.index("## [1.2.3]")
    assert text.startswith("Intro.\n")
