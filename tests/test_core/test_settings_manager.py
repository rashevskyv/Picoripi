import pytest
from unittest.mock import MagicMock
from core.settings_manager import SettingsManager

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
    
    assert sm.mw == mw
    assert sm.settings_file_path == "settings.json"
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
    mocker.patch('core.settings_manager.GlobalSettings')
    mocker.patch('core.settings_manager.PluginSettings')
    mocker.patch('core.settings_manager.FontMapLoader')
    mocker.patch('core.settings_manager.RecentProjectsManager')
    mocker.patch('core.settings_manager.SessionStateManager')
    
    # Mock logging functions to avoid real calls
    mocker.patch('utils.logging_utils.set_enabled_log_categories')
    mocker.patch('utils.logging_utils.update_logger_handlers')

    mw = MagicMock()

    mw.data_store = mw
    mw.restore_unsaved_on_startup = False
    sm = SettingsManager(mw)
    
    # Mock specific managers to check calls
    sm.global_settings.load = MagicMock()
    sm.plugin_settings.load = MagicMock()
    sm.font_map_loader.load_all_font_maps = MagicMock()
    
    sm.load_settings()
    
    sm.global_settings.load.assert_called_once()
    sm.plugin_settings.load.assert_called_once()
    sm.font_map_loader.load_all_font_maps.assert_called_once()

def test_SettingsManager_save_settings(mocker):
    mocker.patch('core.settings_manager.GlobalSettings')
    mocker.patch('core.settings_manager.PluginSettings')
    mocker.patch('core.settings_manager.FontMapLoader')
    mocker.patch('core.settings_manager.RecentProjectsManager')
    mocker.patch('core.settings_manager.SessionStateManager')
    
    sm = SettingsManager(MagicMock())
    sm.global_settings.save = MagicMock()
    sm.plugin_settings.save = MagicMock()
    
    sm.save_settings()
    
    sm.global_settings.save.assert_called_once()
    sm.plugin_settings.save.assert_called_once()


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
    mocker.patch('core.settings_manager.GlobalSettings')
    mocker.patch('core.settings_manager.PluginSettings')
    mocker.patch('core.settings_manager.FontMapLoader')
    mocker.patch('core.settings_manager.RecentProjectsManager')
    mocker.patch('core.settings_manager.SessionStateManager')
    
    sm = SettingsManager(MagicMock())
    sm.font_map_loader.load_all_font_maps = MagicMock()
    sm.load_all_font_maps()
    sm.font_map_loader.load_all_font_maps.assert_called_once()

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
    mocker.patch('core.settings_manager.GlobalSettings')
    mocker.patch('core.settings_manager.PluginSettings')
    mocker.patch('core.settings_manager.FontMapLoader')
    mocker.patch('core.settings_manager.RecentProjectsManager')
    mocker.patch('core.settings_manager.SessionStateManager')
    
    sm = SettingsManager(MagicMock())
    sm.recent_projects_manager.clear_recent_projects = MagicMock()
    sm.clear_recent_projects()
    sm.recent_projects_manager.clear_recent_projects.assert_called_once()

def test_SettingsManager_save_block_names(mocker):
    mocker.patch('core.settings_manager.GlobalSettings')
    mocker.patch('core.settings_manager.PluginSettings')
    mocker.patch('core.settings_manager.FontMapLoader')
    mocker.patch('core.settings_manager.RecentProjectsManager')
    mocker.patch('core.settings_manager.SessionStateManager')
    
    sm = SettingsManager(MagicMock())
    sm.plugin_settings.save_block_names = MagicMock()
    sm.save_block_names()
    sm.plugin_settings.save_block_names.assert_called_once()

def test_SettingsManagerupdate_icon_sequences_cache(mocker):
    mocker.patch('core.settings_manager.GlobalSettings')
    mocker.patch('core.settings_manager.PluginSettings')
    mocker.patch('core.settings_manager.FontMapLoader')
    mocker.patch('core.settings_manager.RecentProjectsManager')
    mocker.patch('core.settings_manager.SessionStateManager')
    
    sm = SettingsManager(MagicMock())
    sm.font_map_loader.update_icon_sequences_cache = MagicMock()
    sm._update_icon_sequences_cache()
    sm.font_map_loader.update_icon_sequences_cache.assert_called_once()

def test_SettingsManagerrefresh_icon_highlighting(mocker):
    mocker.patch('core.settings_manager.GlobalSettings')
    mocker.patch('core.settings_manager.PluginSettings')
    mocker.patch('core.settings_manager.FontMapLoader')
    mocker.patch('core.settings_manager.RecentProjectsManager')
    mocker.patch('core.settings_manager.SessionStateManager')
    
    sm = SettingsManager(MagicMock())
    sm.font_map_loader.refresh_icon_highlighting = MagicMock()
    sm._refresh_icon_highlighting()
    sm.font_map_loader.refresh_icon_highlighting.assert_called_once()


