# Picoripi API Reference (Automatically Extracted)

This document list all classes, public methods, and top-level functions inside the key components of the Picoripi project.

## Component: `core`

### File: [data_store.py](../../core/data_store.py)

#### Class: `Class AppDataStore`

*Centralized store for application data. Decouples data state from MainWindow UI.*


##### Methods

- **`clear(self)`**
  *Description*: Reset all data to default state.

- **`mark_dirty(self, block_idx)`**
  *Description*: Mark a block as having unsaved changes.

- **`mark_clean(self, block_idx)`**
  *Description*: Mark a block or the entire store as clean.



---

### File: [markdown_script_parser.py](../../core/markdown_script_parser.py)

#### Functions

- **`parse_markdown_script(file_path)`**
  *Description*: Parse a standardized Markdown game script file into structured data. Extracts global synopsis, characters cast with attributes, terms,  and chronological chapters with locations, actions, and dialogues.

---

### File: [script_segmenter.py](../../core/script_segmenter.py)

#### Functions

- **`clean_chapter_title(raw_title)`**
  *Description*: Clean up spaced-out letters in chapter titles. e.g. 'S u b s e r v i e n t  T w i l i g h t' -> 'Subservient Twilight'

- **`segment_script_file(script_path)`**
  *Description*: Segment the text script into structured chapters.

---

### File: [base_container.py](../../core/containers/base_container.py)

#### Class: `Class BaseArchiveContainer(ABC)`

*Abstract interface for reading and writing game archive files in-memory.  Implementations must support: - Detecting supported archive formats via can_handle() - Listing all file paths within the archive - Reading individual file contents - Writing (patching) individual file contents in-memory - Packing the (potentially modified) archive back to bytes*


##### Methods

- **`can_handle(cls, data)`**
  *Description*: Return True if this container implementation can parse the given raw bytes.  Args:     data: Raw bytes of the archive file (may be compressed).  Returns:     True if this implementation can handle the format.

- **`__init__(self, data)`**
  *Description*: Initialize and parse the archive from raw bytes.  Args:     data: Raw bytes of the archive file.

- **`list_files(self)`**
  *Description*: Return a list of all file paths within the archive, using forward-slash separators. Does not include directory entries or special entries (., ..).  Returns:     List of unix-style relative paths, e.g. ["Bmgres/bootUp.bmg", "Bmgres/getItem.bmg"]

- **`read_file(self, path)`**
  *Description*: Read the contents of a file from the archive.  If the file was previously modified via write_file(), returns the modified version.  Args:     path: Unix-style path as returned by list_files().  Returns:     Raw bytes of the file.  Raises:     KeyError: If the path does not exist in the archive.

- **`write_file(self, path, data)`**
  *Description*: Stage updated contents for a file in the archive (in-memory only).  The change is not persisted until pack() is called.  Args:     path: Unix-style path as returned by list_files().     data: New raw bytes to store for this file.  Raises:     KeyError: If the path does not exist in the archive.

- **`pack(self)`**
  *Description*: Assemble and return the complete archive as bytes, incorporating any changes made via write_file().  If the original archive was compressed (e.g. Yaz0), the output will also be in the same compressed format.  Returns:     Complete archive bytes ready to be written to disk.

- **`has_pending_changes(self)`**
  *Description*: Return True if any files have been staged for writing.



---

### File: [container_manager.py](../../core/containers/container_manager.py)

#### Class: `Class ContainerManager`

*Factory that selects the appropriate archive container implementation based on the magic bytes of the given raw data.*


##### Methods

- **`open(data)`**
  *Description*: Detect the archive format and return an initialised container instance.  Args:     data: Raw bytes of the archive file (may be Yaz0-compressed).  Returns:     An initialised BaseArchiveContainer subclass, or None if the format     is not recognised.

- **`is_supported(data)`**
  *Description*: Return True if the raw bytes represent a recognised archive format.  Args:     data: Raw bytes of the archive file.  Returns:     True if ContainerManager.open() would succeed.



---

## Component: `handlers`

## Component: `ui`

### File: [ui_setup.py](../../ui/ui_setup.py)

#### Functions

- **`setup_main_window_ui(main_window)`**
  *Description*: Sets up the main window UI by delegating to specialized builders. This replaces the monolithic 470-line setup function.

---

### File: [ui_utils.py](../../ui/ui_utils.py)

#### Functions

- **`prettify_standard_context_menu(menu, style)`**
  *Description*: Finds standard actions like Undo, Redo, Cut, Copy, Paste, etc.  in a QMenu and assigns them standard icons from QStyle if they are missing.

---

## Component: `components`

## Component: `plugins`

### File: [config_factory.py](../../plugins/common/config_factory.py)

#### Functions

- **`generate_base_config(prefix, overrides, custom_problems)`**
  *Description*: Generate unified base problem configuration definitions for a plugin prefix.

---

## Component: `utils`
