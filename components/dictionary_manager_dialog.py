import requests
from pathlib import Path
from typing import List
from PyQt5.QtWidgets import (
    QDialog, QVBoxLayout, QListWidget, QListWidgetItem, QPushButton,
    QDialogButtonBox, QLabel, QProgressBar, QApplication, QLineEdit,
    QHBoxLayout
)
from PyQt5.QtCore import Qt, QThread, pyqtSignal
from utils.logging_utils import log_debug, log_error
import pycountry

DICTIONARY_API_URL = "https://api.github.com/repos/wooorm/dictionaries/contents/dictionaries"
DICTIONARY_DOWNLOAD_URL_TEMPLATE = "https://raw.githubusercontent.com/wooorm/dictionaries/main/dictionaries/{lang_code}/index.{ext}"
LOCAL_DICT_PATH = "resources/spellchecker"

class DownloadThread(QThread):
    progress = pyqtSignal(str, int)
    finished = pyqtSignal(str, bool, str)

    def __init__(self, downloads: List[tuple[str, str]]):
        super().__init__()
        self.downloads = downloads

    def run(self):
        for url, save_path in self.downloads:
            save_path_obj = Path(save_path)
            file_name = save_path_obj.name
            try:
                self.progress.emit(f"Downloading {file_name}...", 0)
                response = requests.get(url, stream=True)
                response.raise_for_status()
                total_size = int(response.headers.get('content-length', 0))
                
                save_path_obj.parent.mkdir(parents=True, exist_ok=True)
                
                downloaded_size = 0
                with open(save_path_obj, 'wb') as f:
                    for chunk in response.iter_content(chunk_size=8192):
                        if not chunk: continue
                        f.write(chunk)
                        downloaded_size += len(chunk)
                        if total_size > 0:
                            progress = int((downloaded_size / total_size) * 100)
                            self.progress.emit(f"Downloading {file_name}...", progress)
                
                self.progress.emit(f"Downloaded {file_name}", 100)
            except Exception as e:
                log_error(f"Failed to download dictionary from {url}: {e}", exc_info=True)
                self.finished.emit(url, False, str(e))
                return
        self.finished.emit("", True, "All files downloaded successfully.")


class DictionaryManagerDialog(QDialog):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Dictionary Manager")
        self.setMinimumSize(450, 400)
        self.spellchecker_manager = getattr(parent, 'mw', parent).spellchecker_manager
        
        self.remote_languages = []
        self.local_languages = []
        self.lang_code_map = {}
        
        main_layout = QVBoxLayout(self)
        
        filter_layout = QHBoxLayout()
        filter_layout.addWidget(QLabel("Filter:"))
        self.filter_edit = QLineEdit(self)
        self.filter_edit.setPlaceholderText("e.g., Ukrainian or uk")
        filter_layout.addWidget(self.filter_edit)
        main_layout.addLayout(filter_layout)

        main_layout.addWidget(QLabel("Available Dictionaries:"))
        self.dict_list = QListWidget(self)
        main_layout.addWidget(self.dict_list)
        
        self.download_button = QPushButton("Download Selected", self)
        self.download_button.setEnabled(False)
        main_layout.addWidget(self.download_button)

        self.progress_bar = QProgressBar(self)
        self.progress_bar.setVisible(False)
        main_layout.addWidget(self.progress_bar)

        self.status_label = QLabel("", self)
        main_layout.addWidget(self.status_label)
        
        button_box = QDialogButtonBox(QDialogButtonBox.Close)
        button_box.rejected.connect(self.reject)
        main_layout.addWidget(button_box)

        self.dict_list.itemSelectionChanged.connect(self.update_button_state)
        self.download_button.clicked.connect(self.download_selected)
        self.filter_edit.textChanged.connect(self.refresh_list)
        
        self.load_dictionaries()

    def _get_lang_name(self, code):
        try:
            lang_code_part = code.split('_')[0]
            lang = pycountry.languages.get(alpha_2=lang_code_part)
            return lang.name if lang else code
        except Exception:
            return code

    def load_dictionaries(self):
        self.status_label.setText("Fetching remote dictionary list...")
        QApplication.processEvents()
        try:
            response = requests.get(DICTIONARY_API_URL, timeout=10)
            response.raise_for_status()
            data = response.json()
            self.remote_languages = sorted([item['name'] for item in data if item['type'] == 'dir'])
            
            self.lang_code_map = {code: self._get_lang_name(code) for code in self.remote_languages}
            
            self.status_label.setText("Ready.")
        except Exception as e:
            error_message = f"Error fetching list: {e}"
            self.status_label.setText(error_message)
            log_error(f"Could not fetch dictionary list: {e}", exc_info=True)
        
        self.refresh_list()

    def refresh_list(self):
        self.dict_list.clear()
        self.local_languages = self.spellchecker_manager.scan_local_dictionaries() if self.spellchecker_manager else {}
        filter_text = self.filter_edit.text().lower()
        
        for lang_code in self.remote_languages:
            lang_name = self.lang_code_map.get(lang_code, lang_code)
            
            if filter_text and not (filter_text in lang_code.lower() or filter_text in lang_name.lower()):
                continue

            is_downloaded = lang_code in self.local_languages
            status = "[Downloaded]" if is_downloaded else "[Available]"
            display_text = f"{lang_name} ({lang_code}) {status}"
            item = QListWidgetItem(display_text)
            item.setData(Qt.UserRole, lang_code)
            item.setFlags(item.flags() & ~Qt.ItemIsSelectable if is_downloaded else item.flags() | Qt.ItemIsSelectable)
            self.dict_list.addItem(item)
            
    def update_button_state(self):
        self.download_button.setEnabled(len(self.dict_list.selectedItems()) > 0)

    def download_selected(self):
        selected_items = self.dict_list.selectedItems()
        if not selected_items:
            return

        lang_code = selected_items[0].data(Qt.UserRole)
        
        local_dict_path_obj = Path(LOCAL_DICT_PATH)
        downloads = [
            (DICTIONARY_DOWNLOAD_URL_TEMPLATE.format(lang_code=lang_code, ext='dic'), (local_dict_path_obj / f"{lang_code}.dic").as_posix()),
            (DICTIONARY_DOWNLOAD_URL_TEMPLATE.format(lang_code=lang_code, ext='aff'), (local_dict_path_obj / f"{lang_code}.aff").as_posix())
        ]
        
        self.download_button.setEnabled(False)
        self.progress_bar.setVisible(True)
        self.progress_bar.setValue(0)
        self.status_label.setText(f"Starting download for {lang_code}...")

        self.download_thread = DownloadThread(downloads)
        self.download_thread.progress.connect(self.on_download_progress)
        self.download_thread.finished.connect(self.on_download_finished)
        self.download_thread.start()
        
    def on_download_progress(self, message, value):
        self.status_label.setText(message)
        self.progress_bar.setValue(value)

    def on_download_finished(self, url, success, message):
        self.progress_bar.setVisible(False)
        self.status_label.setText(message)
        if success:
            self.refresh_list()
            if self.spellchecker_manager:
                self.spellchecker_manager.reload_dictionary(self.spellchecker_manager.language)
        self.update_button_state()
