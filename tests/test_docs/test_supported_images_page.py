"""The Supported games pages carry the table of the images each plugin opens, generated from the plugins' declarations."""
import importlib.util
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]


def _generator():
    spec = importlib.util.spec_from_file_location("supported_images_page", ROOT / "scripts" / "supported_images_page.py")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_both_pages_hold_the_current_block():
    generator = _generator()
    for lang, (path, _anchor) in generator.PAGES.items():
        current = path.read_text(encoding="utf-8")
        assert generator.updated_page(lang, current) == current, f"{path.name} ({lang}) is stale: run scripts/supported_images_page.py --write"


def test_a_page_without_markers_gets_the_block_before_the_platform_tables():
    generator = _generator()
    page = "# Title\n\n## Games by platform\n\nbody\n"
    result = generator.updated_page("en", page)
    assert result.index(generator.START) < result.index("## Games by platform")
    assert generator.updated_page("en", result) == result


def test_the_block_lists_each_declared_id_once_per_row():
    generator = _generator()
    block = generator.render("en")
    assert "| Zelda: The Wind Waker (GameCube BMG) | Disc ID | GZLE01 | USA |" in block
    assert block.count("| Pokemon FireRed") == 0 or block.count("SHA-1 of the ROM") >= 11
