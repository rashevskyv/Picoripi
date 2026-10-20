"""The hint printed when Qt cannot be imported at start (utils/qt_import_hint.py): steps by platform."""
from utils.qt_import_hint import VC_REDIST_URL, hint_for

ERROR = ImportError("DLL load failed while importing QtCore: The specified procedure could not be found.")


def test_windows_hint_names_the_runtime_the_path_check_and_the_reinstall():
    text = hint_for(ERROR, platform="win32")
    assert "The specified procedure could not be found" in text
    assert VC_REDIST_URL in text
    assert "where Qt6Core.dll" in text
    assert "--force-reinstall PyQt6 PyQt6-Qt6 PyQt6-sip" in text
    assert [line[:2] for line in text.splitlines() if line[:2] in ("1.", "2.", "3.", "4.")] == ["1.", "2.", "3.", "4."]


def test_other_systems_get_only_the_platform_free_steps():
    text = hint_for(ERROR, platform="linux")
    assert VC_REDIST_URL not in text and "Qt6Core.dll" not in text
    assert "--force-reinstall" in text
    assert [line[:2] for line in text.splitlines() if line[:2] in ("1.", "2.", "3.")] == ["1.", "2."]
