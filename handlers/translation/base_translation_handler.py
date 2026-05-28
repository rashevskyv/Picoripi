class BaseTranslationHandler:
    def __init__(self, main_handler):
        self.main_handler = main_handler
        self.mw = main_handler.mw
        self.data_processor = main_handler.data_processor
        self.ui_updater = main_handler.ui_updater
