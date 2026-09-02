from PyQt6 import QtCore, QtWidgets

from core.i18n import tr

ROLE_SHEET_IDX = QtCore.Qt.ItemDataRole.UserRole + 1
ROLE_FONT_NAME = QtCore.Qt.ItemDataRole.UserRole + 2
ROLE_ARCHIVE_NAME = QtCore.Qt.ItemDataRole.UserRole + 3
ROLE_SOURCE_TYPE = QtCore.Qt.ItemDataRole.UserRole + 4
ROLE_DISK_PATH = QtCore.Qt.ItemDataRole.UserRole + 5


class WindowTreeMixin:
    def scan_fonts_directories(self):
        """Scan active plugin fonts directory and custom fonts directory for archives and loose fonts."""
        # Preserve existing in-memory sources
        in_memory_sources = {k: v for k, v in self.font_sources.items() if v["type"] == "in_memory"}
        self.font_sources = in_memory_sources
        
        parent = self.parent()
        if not parent:
            return
            
        plugin_name = getattr(parent, 'active_game_plugin', None)
        custom_fonts_path = getattr(parent, 'fonts_dir_path', None)
        
        from pathlib import Path
        fonts_dirs = []
        if plugin_name:
            fonts_dirs.append(Path("plugins") / plugin_name / "fonts")
        if custom_fonts_path:
            custom_dir = Path(custom_fonts_path)
            if custom_dir.is_dir():
                fonts_dirs.append(custom_dir)
                
        from core.containers import ContainerManager
        
        for fonts_dir in fonts_dirs:
            if not fonts_dir.is_dir():
                continue
            for font_file in fonts_dir.iterdir():
                if not font_file.is_file():
                    continue
                suffix = font_file.suffix.lower()
                
                # Check for archives containing fonts
                if suffix in (".arc", ".rarc", ".u8"):
                    archive_name = font_file.name
                    if archive_name in self.font_sources:
                        continue
                    try:
                        archive_data = font_file.read_bytes()
                        if ContainerManager.is_supported(archive_data):
                            container = ContainerManager.open(archive_data)
                            if container:
                                files = {}
                                for inner_path in container.list_files():
                                    if Path(inner_path).suffix.lower() == ".bfn":
                                        try:
                                            files[Path(inner_path).name] = container.read_file(inner_path)
                                        except Exception:
                                            pass
                                if files:
                                    self.font_sources[archive_name] = {
                                        "type": "disk_archive",
                                        "path": str(font_file.resolve()),
                                        "files": files
                                    }
                    except Exception as e:
                        print(f"Error scanning archive {font_file}: {e}")
                        
                # Check for loose bfn files
                elif suffix == ".bfn":
                    font_name = font_file.name
                    if font_name in self.font_sources:
                        continue
                    try:
                        bfn_bytes = font_file.read_bytes()
                        self.font_sources[font_name] = {
                            "type": "disk_loose",
                            "path": str(font_file.resolve()),
                            "files": {font_name: bfn_bytes}
                        }
                    except Exception as e:
                        print(f"Error scanning loose font {font_file}: {e}")

    def rebuild_tree_widget(self, active_sheet_count=0, expanded_keys=None):
        """Populate the left tree widget with all found font sources, BFN files and sheets."""
        # Save expanded state of items to avoid collapsing on rebuild
        if expanded_keys is None:
            expanded_keys = set()
            iterator = QtWidgets.QTreeWidgetItemIterator(self.list_sheets)
            while iterator.value():
                item = iterator.value()
                if item.isExpanded():
                    archive = item.data(0, ROLE_ARCHIVE_NAME)
                    font = item.data(0, ROLE_FONT_NAME)
                    sheet = item.data(0, ROLE_SHEET_IDX)
                    # We identify nodes by:
                    # - (source_name, None) for top-level archive/source node
                    # - (source_name, bfn_name) for font file node
                    if sheet is None:
                        expanded_keys.add((archive, font))
                iterator += 1

        self.list_sheets.blockSignals(True)
        self.list_sheets.clear()
        
        from core.bfn_core import BfnCore
        
        for source_name, source_info in sorted(self.font_sources.items()):
            src_type = source_info["type"]
            disk_path = source_info["path"]
            files = source_info["files"]
            
            is_archive = src_type == "disk_archive" or (src_type == "in_memory" and len(files) > 1) or (self.archive_name and source_name == self.archive_name)
            
            if is_archive:
                archive_item = QtWidgets.QTreeWidgetItem(self.list_sheets, [source_name])
                archive_item.setData(0, ROLE_SOURCE_TYPE, src_type)
                archive_item.setData(0, ROLE_DISK_PATH, disk_path)
                archive_item.setData(0, ROLE_ARCHIVE_NAME, source_name)
                
                # Restore top-level expansion
                if not expanded_keys or (source_name, None) in expanded_keys:
                    archive_item.setExpanded(True)
                else:
                    archive_item.setExpanded(False)
                
                for bfn_name, bfn_bytes in sorted(files.items()):
                    file_item = QtWidgets.QTreeWidgetItem(archive_item, [bfn_name])
                    file_item.setData(0, ROLE_FONT_NAME, bfn_name)
                    file_item.setData(0, ROLE_ARCHIVE_NAME, source_name)
                    file_item.setData(0, ROLE_SOURCE_TYPE, src_type)
                    file_item.setData(0, ROLE_DISK_PATH, disk_path)
                    
                    sheet_count = 0
                    is_current = (bfn_name == self.current_bfn_name and (not self.archive_name or source_name == self.archive_name))
                    if is_current:
                        sheet_count = active_sheet_count
                    else:
                        try:
                            temp_bfn = BfnCore()
                            temp_bfn.load(bfn_bytes)
                            if temp_bfn.gly1:
                                gly = temp_bfn.gly1[0]
                                sheet_count = (gly["end_glyph"] - gly["start_glyph"]) // (gly["glyph_horizontal_count"] * gly["glyph_vertical_count"]) + 1
                        except Exception:
                            sheet_count = 1
                            
                    # Restore font expansion
                    if (not expanded_keys and is_current) or (source_name, bfn_name) in expanded_keys:
                        file_item.setExpanded(True)
                    else:
                        file_item.setExpanded(False)
                        
                    for s in range(sheet_count):
                        sheet_item = QtWidgets.QTreeWidgetItem(file_item, [f"Sheet {s}"])
                        sheet_item.setData(0, ROLE_SHEET_IDX, s)
                        sheet_item.setData(0, ROLE_FONT_NAME, bfn_name)
                        sheet_item.setData(0, ROLE_ARCHIVE_NAME, source_name)
                        sheet_item.setData(0, ROLE_SOURCE_TYPE, src_type)
                        sheet_item.setData(0, ROLE_DISK_PATH, disk_path)
            else:
                bfn_name = list(files.keys())[0]
                
                file_item = QtWidgets.QTreeWidgetItem(self.list_sheets, [bfn_name])
                file_item.setData(0, ROLE_FONT_NAME, bfn_name)
                file_item.setData(0, ROLE_SOURCE_TYPE, src_type)
                file_item.setData(0, ROLE_DISK_PATH, disk_path)
                
                sheet_count = 0
                is_current = (bfn_name == self.current_bfn_name and not self.archive_name)
                if is_current:
                    sheet_count = active_sheet_count
                else:
                    try:
                        temp_bfn = BfnCore()
                        temp_bfn.load(files[bfn_name])
                        if temp_bfn.gly1:
                            gly = temp_bfn.gly1[0]
                            sheet_count = (gly["end_glyph"] - gly["start_glyph"]) // (gly["glyph_horizontal_count"] * gly["glyph_vertical_count"]) + 1
                    except Exception:
                        sheet_count = 1
                
                # For loose files, the key is (None, bfn_name)
                if not expanded_keys or (None, bfn_name) in expanded_keys:
                    file_item.setExpanded(True)
                else:
                    file_item.setExpanded(False)
                    
                for s in range(sheet_count):
                    sheet_item = QtWidgets.QTreeWidgetItem(file_item, [f"Sheet {s}"])
                    sheet_item.setData(0, ROLE_SHEET_IDX, s)
                    sheet_item.setData(0, ROLE_FONT_NAME, bfn_name)
                    sheet_item.setData(0, ROLE_SOURCE_TYPE, src_type)
                    sheet_item.setData(0, ROLE_DISK_PATH, disk_path)
                    
        self.list_sheets.blockSignals(False)

    def set_current_sheet_row(self, sheet_idx):
        """Select a sheet item in the tree that matches the sheet_idx for the current font using role metadata."""
        iterator = QtWidgets.QTreeWidgetItemIterator(self.list_sheets)
        while iterator.value():
            item = iterator.value()
            role_sheet = item.data(0, ROLE_SHEET_IDX)
            role_font = item.data(0, ROLE_FONT_NAME)
            role_archive = item.data(0, ROLE_ARCHIVE_NAME)
            
            if role_sheet == sheet_idx and role_font == self.current_bfn_name:
                if not self.archive_name or role_archive == self.archive_name:
                    self.list_sheets.blockSignals(True)
                    self.list_sheets.setCurrentItem(item)
                    self.list_sheets.blockSignals(False)
                    self.select_sheet(sheet_idx)
                    break
            iterator += 1

    def select_sheet_tree(self, current, previous):
        """Handle tree item selection to change sheet or switch active font using role metadata."""
        if not current:
            return
            
        sheet_idx = current.data(0, ROLE_SHEET_IDX)
        bfn_name = current.data(0, ROLE_FONT_NAME)
        
        if sheet_idx is None:
            if bfn_name:
                if current.childCount() > 0:
                    self.list_sheets.setCurrentItem(current.child(0))
                    return
                sheet_idx = 0
            else:
                # Not a sheet item
                return
                
        archive_name = current.data(0, ROLE_ARCHIVE_NAME) or ""
        source_type = current.data(0, ROLE_SOURCE_TYPE)
        disk_path = current.data(0, ROLE_DISK_PATH) or ""
        
        is_different = (bfn_name != self.current_bfn_name or archive_name != self.archive_name)
        if is_different:
            self.switch_active_bfn_new(bfn_name, archive_name, source_type, disk_path, sheet_idx)
        else:
            self.select_sheet(sheet_idx)

    def switch_active_bfn_new(self, bfn_name, archive_name, source_type, disk_path, target_sheet_idx):
        """Switch active BFN font with proper save prompts and target file callbacks."""
        if self._dirty:
            reply = QtWidgets.QMessageBox.question(
                self,
                tr('Unsaved Changes'),
                tr("You have unsaved changes in '{0}'! Do you want to save them before switching?", self.current_bfn_name),
                QtWidgets.QMessageBox.StandardButton.Yes | QtWidgets.QMessageBox.StandardButton.No | QtWidgets.QMessageBox.StandardButton.Cancel
            )
            if reply == QtWidgets.QMessageBox.StandardButton.Yes:
                self.save_changes()
            elif reply == QtWidgets.QMessageBox.StandardButton.Cancel:
                self.set_current_sheet_row(self.current_sheet_index)
                return
                
        # Retrieve bytes from font_sources
        key = archive_name if archive_name else bfn_name
        source_info = self.font_sources.get(key)
        if not source_info:
            return
            
        bfn_bytes = source_info["files"].get(bfn_name)
        if not bfn_bytes:
            return
            
        # Set target callbacks based on source type
        self.archive_name = archive_name
        self.current_bfn_name = bfn_name
        
        if source_type == "in_memory":
            # Callback is provided by Picoripi
            # self.archive_save_callback is preserved
            self.archive_files = source_info["files"]
        elif source_type == "disk_archive":
            # Dynamic save callback for disk archives
            def dynamic_save_callback(filename: str, new_bytes: bytes):
                try:
                    from core.containers import ContainerManager
                    from pathlib import Path
                    archive_bytes = Path(disk_path).read_bytes()
                    container = ContainerManager.open(archive_bytes)
                    if container:
                        container.write_file(filename, new_bytes)
                        updated_archive = container.pack()
                        Path(disk_path).write_bytes(updated_archive)
                        # Update our local source files cache
                        source_info["files"][filename] = new_bytes
                        print(f"BFN Editor: Saved and packed '{filename}' to disk archive '{disk_path}'.")
                except Exception as ex:
                    QtWidgets.QMessageBox.critical(self, tr('BFN Editor'), tr('Failed to write back to disk archive:\n{0}', ex))
            self.archive_save_callback = dynamic_save_callback
            self.archive_files = source_info["files"]
        elif source_type == "disk_loose":
            # Dynamic save callback for loose files on disk
            def dynamic_save_callback(filename: str, new_bytes: bytes):
                try:
                    from pathlib import Path
                    Path(disk_path).write_bytes(new_bytes)
                    # Update local source cache
                    source_info["files"][filename] = new_bytes
                    print(f"BFN Editor: Saved loose font '{filename}' to '{disk_path}'.")
                except Exception as ex:
                    QtWidgets.QMessageBox.critical(self, tr('BFN Editor'), tr('Failed to save loose BFN to disk:\n{0}', ex))
            self.archive_save_callback = dynamic_save_callback
            self.archive_files = {}
            
        # Temporarily clear undo stack to avoid cross-font undoing
        self.undo_stack.clear()
        
        # Спробуємо завантажити оригінальний шрифт для порівняння
        self.original_font_metadata = None
        self.original_sheet_images = []
        
        parent = self.parent()
        if parent:
            orig_fonts_path = getattr(parent, 'orig_fonts_dir_path', None)
            if orig_fonts_path:
                from pathlib import Path
                orig_dir = Path(orig_fonts_path)
                if orig_dir.is_dir():
                    orig_bytes = None
                    if self.archive_name:
                        orig_archive_path = orig_dir / self.archive_name
                        if orig_archive_path.is_file():
                            try:
                                from core.containers import ContainerManager
                                archive_data = orig_archive_path.read_bytes()
                                if ContainerManager.is_supported(archive_data):
                                    container = ContainerManager.open(archive_data)
                                    if container:
                                        for inner_path in container.list_files():
                                            if Path(inner_path).name == bfn_name:
                                                orig_bytes = container.read_file(inner_path)
                                                break
                            except Exception as ex:
                                print(f"Error loading original font from archive: {ex}")
                    else:
                        orig_file_path = orig_dir / bfn_name
                        if orig_file_path.is_file():
                            try:
                                orig_bytes = orig_file_path.read_bytes()
                            except Exception as ex:
                                print(f"Error loading loose original font: {ex}")
                                
                    if orig_bytes:
                        try:
                            self.load_original_bfn_bytes(orig_bytes, bfn_name)
                            print(f"BFN Editor: Successfully loaded original comparison font '{bfn_name}'.")
                        except Exception as ex:
                            print(f"Failed to parse original font: {ex}")
        
        self.load_bfn_bytes(bfn_bytes, bfn_name)
        self.set_current_sheet_row(target_sheet_idx)
