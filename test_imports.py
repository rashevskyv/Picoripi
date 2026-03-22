import sys
print("starting", flush=True)

import core.data_store
print("core.data_store OK", flush=True)

import core.state_manager
print("core.state_manager OK", flush=True)

import ui.updaters.title_status_bar_updater
print("title_status_bar_updater OK", flush=True)

import ui.updaters.string_settings_updater
print("string_settings_updater OK", flush=True)

import ui.updaters.preview_updater
print("preview_updater OK", flush=True)
