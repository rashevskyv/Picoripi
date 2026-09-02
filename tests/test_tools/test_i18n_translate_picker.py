import importlib.util
from pathlib import Path


def _load_picker():
    path = Path(__file__).resolve().parents[2] / "tools" / "i18n-translate" / "picker.py"
    spec = importlib.util.spec_from_file_location("picoripi_i18n_picker", path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_default_selection_is_ukrainian_only():
    mod = _load_picker()
    assert mod.DEFAULT_ON == {"uk"}
    assert "ru" not in mod.LANGS
