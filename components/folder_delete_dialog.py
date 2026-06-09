from PyQt6.QtWidgets import QDialog, QVBoxLayout, QLabel, QHBoxLayout, QPushButton, QStyle
from PyQt6.QtCore import Qt

class FolderDeleteDialog(QDialog):
    def __init__(self, folder_name: str, parent=None):
        super().__init__(parent)
        self.setWindowTitle("Delete Folder")
        self.setModal(True)
        # 0: Cancel, 1: Delete Only Folder (keep contents), 2: Delete Folder + Contents
        self.result_action = 0 
        
        self._setup_ui(folder_name)
        
    def _setup_ui(self, folder_name: str):
        layout = QVBoxLayout(self)
        
        # Warning icon and text
        header_layout = QHBoxLayout()
        icon_label = QLabel()
        icon = self.style().standardIcon(QStyle.StandardPixmap.SP_MessageBoxQuestion)
        icon_label.setPixmap(icon.pixmap(32, 32))
        header_layout.addWidget(icon_label)
        
        text_label = QLabel(
            f"You are about to delete the folder <b>{folder_name}</b>.<br><br>"
            "What would you like to do with the files and subfolders inside it?"
        )
        text_label.setWordWrap(True)
        header_layout.addWidget(text_label, stretch=1)
        layout.addLayout(header_layout)
        
        layout.addSpacing(10)
        
        # Buttons
        btn_layout = QVBoxLayout()
        
        self.btn_keep = QPushButton("Delete Folder, but Keep Contents")
        self.btn_keep.setToolTip("Removes the folder and moves its contents up one level.")
        self.btn_keep.clicked.connect(self._on_keep_clicked)
        btn_layout.addWidget(self.btn_keep)
        
        self.btn_delete_all = QPushButton("Delete Folder AND its Contents")
        self.btn_delete_all.setToolTip("Permanently removes this folder and everything inside it from the project.")
        self.btn_delete_all.setStyleSheet("color: #d32f2f;") # Red text to indicate destruction
        self.btn_delete_all.clicked.connect(self._on_delete_all_clicked)
        btn_layout.addWidget(self.btn_delete_all)
        
        layout.addLayout(btn_layout)
        
        layout.addSpacing(10)
        
        self.btn_cancel = QPushButton("Cancel")
        self.btn_cancel.clicked.connect(self.reject)
        layout.addWidget(self.btn_cancel, alignment=Qt.AlignmentFlag.AlignCenter)
        
        self.resize(350, 200)

    def _on_keep_clicked(self):
        self.result_action = 1
        self.accept()
        
    def _on_delete_all_clicked(self):
        self.result_action = 2
        self.accept()
