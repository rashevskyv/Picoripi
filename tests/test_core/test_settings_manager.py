from unittest.mock import MagicMock
from core.settings_manager import SettingsManager


class _FakeGlobalSettings:
    """Records the global settings calls into a shared log."""

    def __init__(self, log):
        self._log = log

    def load(self, settings):
        self._log.append(("global.load", settings))

    def save(self, settings):
        self._log.append(("global.save", settings))


class _FakePluginSettings:
    """Records the plugin settings calls into a shared log."""

    def __init__(self, log):
        self._log = log

    def load(self, settings):
        self._log.append(("plugin.load", settings))

    def save(self):
        self._log.append(("plugin.save",))

    def save_block_names(self):
        self._log.append(("plugin.save_block_names",))


class _FakeFontMapLoader:
    """Records the font map calls into a shared log."""

    def __init__(self, log):
        self._log = log

    def load_all_font_maps(self):
        self._log.append(("fonts.load_all_font_maps",))

    def update_icon_sequences_cache(self):
        self._log.append(("fonts.update_icon_sequences_cache",))

    def refresh_icon_highlighting(self):
        self._log.append(("fonts.refresh_icon_highlighting",))


class _FakeRecentProjectsManager:
    """Records the recent projects calls into a shared log."""

    def __init__(self, log):
        self._log = log

    def clear_recent_projects(self):
        self._log.append(("recent.clear_recent_projects",))


def _patch_collaborators(mocker):
    mocker.patch('core.settings_manager.GlobalSettings')
    mocker.patch('core.settings_manager.PluginSettings')
    mocker.patch('core.settings_manager.FontMapLoader')
    mocker.patch('core.settings_manager.RecentProjectsManager')
    mocker.patch('core.settings_manager.SessionStateManager')


def _manager_with_fakes(mocker, main_window=None):
    """Build a SettingsManager whose collaborators are recording fakes sharing one log."""
    _patch_collaborators(mocker)
    sm = SettingsManager(main_window if main_window is not None else MagicMock())
    log = []
    sm.global_settings = _FakeGlobalSettings(log)
    sm.plugin_settings = _FakePluginSettings(log)
    sm.font_map_loader = _FakeFontMapLoader(log)
    sm.recent_projects_manager = _FakeRecentProjectsManager(log)
    return sm, log

def test_SettingsManager_init(mocker):
    # Mocking external classes initialized in __init__
    mocker.patch('core.settings_manager.GlobalSettings')
    mocker.patch('core.settings_manager.PluginSettings')
    mocker.patch('core.settings_manager.FontMapLoader')
    mocker.patch('core.settings_manager.RecentProjectsManager')
    mocker.patch('core.settings_manager.SessionStateManager')

    mw = MagicMock()

    mw.data_store = mw
    sm = SettingsManager(mw)

    from utils.constants import SETTINGS_FILE_PATH
    assert sm.mw == mw
    assert sm.settings_file_path == SETTINGS_FILE_PATH
    assert sm._settings == {}

def test_SettingsManager_get(mocker):
    mocker.patch('core.settings_manager.GlobalSettings')
    mocker.patch('core.settings_manager.PluginSettings')
    mocker.patch('core.settings_manager.FontMapLoader')
    mocker.patch('core.settings_manager.RecentProjectsManager')
    mocker.patch('core.settings_manager.SessionStateManager')

    sm = SettingsManager(MagicMock())
    sm._settings = {"test_key": "test_value"}

    assert sm.get("test_key") == "test_value"
    assert sm.get("non_existent", "default") == "default"

def test_SettingsManager_set(mocker):
    mocker.patch('core.settings_manager.GlobalSettings')
    mocker.patch('core.settings_manager.PluginSettings')
    mocker.patch('core.settings_manager.FontMapLoader')
    mocker.patch('core.settings_manager.RecentProjectsManager')
    mocker.patch('core.settings_manager.SessionStateManager')

    mw = MagicMock()

    mw.data_store = mw
    # Ensure mw.some_attr is a plain attribute, not a property
    mw.some_attr = "old"

    sm = SettingsManager(mw)
    sm.set("some_attr", "new")

    assert sm._settings["some_attr"] == "new"
    assert mw.some_attr == "new"


def test_SettingsManager_load_settings(mocker):
    # Mock logging functions to avoid real calls
    mocker.patch('utils.logging_utils.set_enabled_log_categories')
    mocker.patch('utils.logging_utils.update_logger_handlers')

    mw = MagicMock()
    mw.data_store = mw
    mw.restore_unsaved_on_startup = False
    mw.last_opened_path = ""
    sm, log = _manager_with_fakes(mocker, mw)
    sm._settings = {"theme": "dark"}

    sm.load_settings()

    assert log == [
        ("global.load", {"theme": "dark"}),
        ("plugin.load", {"theme": "dark"}),
        ("fonts.load_all_font_maps",),
    ]

def test_SettingsManager_save_settings(mocker):
    sm, log = _manager_with_fakes(mocker)
    sm._settings = {"theme": "dark"}

    sm.save_settings()
    assert log == [("global.save", {"theme": "dark"}), ("plugin.save",)]

    log.clear()
    sm.save_settings(save_project_settings=False)
    assert log == [("global.save", {"theme": "dark"})]


def test_SettingsManager_load_unsaved_session(mocker):
    mocker.patch('core.settings_manager.GlobalSettings')
    mocker.patch('core.settings_manager.PluginSettings')
    mocker.patch('core.settings_manager.FontMapLoader')
    mocker.patch('core.settings_manager.RecentProjectsManager')
    mocker.patch('core.settings_manager.SessionStateManager')

    mw = MagicMock()

    mw.data_store = mw
    mw.restore_unsaved_on_startup = True
    sm = SettingsManager(mw)

    # Mock json.load and open to return dummy data
    mocker.patch("builtins.open", mocker.mock_open(read_data='{"restore_unsaved_on_startup": true, "unsaved_session_data": {"(0, 0)": "test"}}'))
    mocker.patch("core.settings_manager.Path.exists", return_value=True)

    sm.load_unsaved_session()
    assert mw.data_store.edited_data == {(0, 0): "test"}

def test_SettingsManager_load_all_font_maps(mocker):
    sm, log = _manager_with_fakes(mocker)
    sm.load_all_font_maps()
    assert log == [("fonts.load_all_font_maps",)]

def test_SettingsManager_add_recent_project(mocker):
    mocker.patch('core.settings_manager.GlobalSettings')
    mocker.patch('core.settings_manager.PluginSettings')
    mocker.patch('core.settings_manager.FontMapLoader')
    mocker.patch('core.settings_manager.RecentProjectsManager')
    mocker.patch('core.settings_manager.SessionStateManager')

    sm = SettingsManager(MagicMock())
    sm.recent_projects_manager.add_recent_project = MagicMock()
    sm.add_recent_project("path/to/proj")
    sm.recent_projects_manager.add_recent_project.assert_called_once_with("path/to/proj", 10)

def test_SettingsManager_remove_recent_project(mocker):
    mocker.patch('core.settings_manager.GlobalSettings')
    mocker.patch('core.settings_manager.PluginSettings')
    mocker.patch('core.settings_manager.FontMapLoader')
    mocker.patch('core.settings_manager.RecentProjectsManager')
    mocker.patch('core.settings_manager.SessionStateManager')

    sm = SettingsManager(MagicMock())
    sm.recent_projects_manager.remove_recent_project = MagicMock()
    sm.remove_recent_project("path/to/proj")
    sm.recent_projects_manager.remove_recent_project.assert_called_once_with("path/to/proj")

def test_SettingsManager_clear_recent_projects(mocker):
    sm, log = _manager_with_fakes(mocker)
    sm.clear_recent_projects()
    assert log == [("recent.clear_recent_projects",)]

def test_SettingsManager_save_block_names(mocker):
    sm, log = _manager_with_fakes(mocker)
    sm.save_block_names()
    assert log == [("plugin.save_block_names",)]

def test_SettingsManagerupdate_icon_sequences_cache(mocker):
    sm, log = _manager_with_fakes(mocker)
    sm._update_icon_sequences_cache()
    assert log == [("fonts.update_icon_sequences_cache",)]

def test_SettingsManagerrefresh_icon_highlighting(mocker):
    sm, log = _manager_with_fakes(mocker)
    sm._refresh_icon_highlighting()
    assert log == [("fonts.refresh_icon_highlighting",)]
