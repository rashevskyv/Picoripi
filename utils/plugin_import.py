"""One lock for every import of a game plugin.

The main window forgets a plugin's modules and imports them again when a project loads. A Project Manager worker
that counts or reads a project imports the same plugin. Both take this lock, so one never sees the modules half
dropped by the other. Hold it only for the import and the construction of ``GameRules``, never for a long parse.
"""
import threading

PLUGIN_IMPORT_LOCK = threading.RLock()
