class BaseUIUpdater:
    """Base u i updater implementation."""
    def __init__(self, main_window, data_processor):
        """Initialize a new instance."""
        self.mw = main_window
        self.data_processor = data_processor