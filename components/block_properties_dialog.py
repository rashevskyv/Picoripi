# components/block_properties_dialog.py
import os
from pathlib import Path
from PyQt6.QtWidgets import (
    QDialog, QVBoxLayout, QFormLayout, QLineEdit, QGroupBox, QDialogButtonBox
)
from PyQt6.QtCore import Qt
from core.i18n import tr

class BlockPropertiesDialog(QDialog):
    """Dialog class for block properties."""
    def __init__(self, parent, block_idx: int):
        """Initialize a new instance."""
        super().__init__(parent)
        self.setWindowTitle(tr('Block Properties'))
        self.setMinimumWidth(550)
        self.resize(550, 480)
        
        pm = getattr(parent, "project_manager", None)
        ds = getattr(parent, "data_store", None)
        
        # Resolve block objects
        block_map = getattr(parent, 'block_to_project_file_map', {})
        proj_b_idx = block_map.get(block_idx, block_idx)
        block = None
        if pm and pm.project and proj_b_idx < len(pm.project.blocks):
            block = pm.project.blocks[proj_b_idx]
            
        display_name = ds.block_names.get(str(block_idx), f"Block {block_idx}") if ds else f"Block {block_idx}"
        
        # Base variables
        org_name = "N/A"
        extension = "N/A"
        is_archive = "No"
        container = "None (Regular File)"
        num_strings = "0"
        modified = "No"
        src_rel = "N/A"
        src_abs = "N/A"
        src_size = "File not found"
        trans_rel = "N/A"
        trans_abs = "N/A"
        trans_size = "File not found"
        
        if block:
            is_archive_bool = block.metadata.get('is_archive_member', False)
            is_archive = "Yes" if is_archive_bool else "No"
            
            if is_archive_bool:
                org_name = block.metadata.get('archive_file_name') or Path(block.source_file).name
                container = block.metadata.get('archive_rel_path') or "Unknown Archive"
            else:
                org_name = Path(block.source_file).name
                container = "None (Regular File)"
                
            extension = Path(org_name).suffix or "None"
            
            src_rel = block.source_file
            trans_rel = block.translation_file
            
            if pm:
                src_abs = pm.get_absolute_path(block.source_file, is_translation=False)
                trans_abs = pm.get_absolute_path(block.translation_file, is_translation=True)
                
                # Check source size
                if os.path.exists(src_abs):
                    try:
                        sz = os.path.getsize(src_abs)
                        src_size = f"{sz:,} bytes ({sz / 1024:.2f} KB)"
                    except Exception as e:
                        src_size = f"Error: {e}"
                        
                # Check translation size
                if os.path.exists(trans_abs):
                    try:
                        sz = os.path.getsize(trans_abs)
                        trans_size = f"{sz:,} bytes ({sz / 1024:.2f} KB)"
                    except Exception as e:
                        trans_size = f"Error: {e}"
                        
        if ds:
            # Number of strings
            if 0 <= block_idx < len(ds.data):
                num_strings = str(len(ds.data[block_idx]))
            # Unsaved changes
            if block_idx in ds.unsaved_block_indices:
                modified = "Yes (Unsaved Changes in Memory)"
            else:
                modified = "No"
                
        # Main Layout
        layout = QVBoxLayout(self)
        
        # 1. Group Box: General Info
        gen_group = QGroupBox(tr('General Info'), self)
        gen_layout = QFormLayout(gen_group)
        gen_layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        
        self.add_form_row(gen_layout, "Block Name:", display_name)
        self.add_form_row(gen_layout, "File Extension:", extension)
        self.add_form_row(gen_layout, "Internal Index:", f"Data Index: {block_idx} (Project Index: {proj_b_idx})")
        self.add_form_row(gen_layout, "Total Strings:", num_strings)
        self.add_form_row(gen_layout, "Modified State:", modified)
        layout.addWidget(gen_group)
        
        # 2. Group Box: Archive/Container Details
        archive_group = QGroupBox(tr('Archive / Container Details'), self)
        archive_layout = QFormLayout(archive_group)
        archive_layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        
        self.add_form_row(archive_layout, "Inside Container:", is_archive)
        self.add_form_row(archive_layout, "Container File:", container)
        self.add_form_row(archive_layout, "Original File Name:", org_name)
        layout.addWidget(archive_group)
        
        # 3. Group Box: Paths & Disk Info
        paths_group = QGroupBox(tr('Paths & Disk Info'), self)
        paths_layout = QFormLayout(paths_group)
        paths_layout.setLabelAlignment(Qt.AlignmentFlag.AlignRight)
        
        self.add_form_row(paths_layout, "Source Rel Path:", src_rel)
        self.add_form_row(paths_layout, "Source Abs Path:", src_abs)
        self.add_form_row(paths_layout, "Source File Size:", src_size)
        self.add_form_row(paths_layout, "Translation Rel:", trans_rel)
        self.add_form_row(paths_layout, "Translation Abs:", trans_abs)
        self.add_form_row(paths_layout, "Translation Size:", trans_size)
        layout.addWidget(paths_group)
        
        # Dialog buttons
        button_box = QDialogButtonBox(QDialogButtonBox.StandardButton.Ok, self)
        button_box.accepted.connect(self.accept)
        layout.addWidget(button_box)

    def add_form_row(self, layout: QFormLayout, label_text: str, value_text: str):
        """Add form row."""
        edit = QLineEdit(value_text, self)
        edit.setReadOnly(True)
        edit.setStyleSheet("QLineEdit { background: transparent; border: none; }")
        layout.addRow(label_text, edit)
