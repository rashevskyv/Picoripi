import os
import shutil
import subprocess
import sys
from pathlib import Path
import re

def git_commit(message):
    print(f"🔒 Committing changes: '{message}'...")
    try:
        subprocess.run(["git", "add", "."], check=True)
        subprocess.run(["git", "commit", "-m", message], check=True)
        print("✅ Commit successful.")
    except subprocess.CalledProcessError:
        print("⚠️ Git commit failed (maybe nothing to commit?). Continuing...")

def delete_files(files):
    print("🗑️ Deleting duplicate/flattened files...")
    for file_path in files:
        p = Path(file_path)
        if p.exists():
            try:
                p.unlink()
                print(f"   Deleted: {p}")
            except Exception as e:
                print(f"   ❌ Error deleting {p}: {e}")

def move_files(file_map):
    print("🚚 Moving files...")
    for src, dest in file_map.items():
        src_path = Path(src)
        dest_path = Path(dest)
        
        if src_path.exists():
            dest_path.parent.mkdir(parents=True, exist_ok=True)
            try:
                shutil.move(str(src_path), str(dest_path))
                print(f"   Moved: {src} -> {dest}")
            except Exception as e:
                print(f"   ❌ Error moving {src}: {e}")

def fix_imports(replacements):
    print("🔧 Updating imports in all .py files...")
    # Get all python files
    py_files = list(Path(".").rglob("*.py"))
    
    # Exclude the cleanup script itself
    py_files = [f for f in py_files if f.name != "cleanup_project.py" and "venv" not in str(f)]

    for file_path in py_files:
        try:
            with open(file_path, 'r', encoding='utf-8') as f:
                content = f.read()
            
            original_content = content
            
            for old, new in replacements.items():
                # Replace imports
                content = content.replace(f"from {old}", f"from {new}")
                content = content.replace(f"import {old}", f"import {new}")
                # Specific case for components renaming
                content = content.replace(f"components.{old}", f"components.{new}")

            if content != original_content:
                with open(file_path, 'w', encoding='utf-8') as f:
                    f.write(content)
                print(f"   Updated imports in: {file_path}")
                
        except Exception as e:
            print(f"   ❌ Error processing {file_path}: {e}")

def main():
    # 1. Commit current state
    git_commit("chore: pre-cleanup backup state")

    # 2. Files to delete (Duplicates/Flattened versions found in root)
    files_to_delete = [
        # Flattened plugin files
        "plugins_plain_text_config.py",
        "plugins_plain_text_rules.py",
        "plugins_pokemon_fr_config.json",
        "plugins_pokemon_fr_config.py",
        "plugins_pokemon_fr_font_map.json",
        "plugins_pokemon_fr_problem_analyzer.py",
        "plugins_pokemon_fr_rules.py",
        "plugins_pokemon_fr_tag_manager.py",
        "plugins_pokemon_fr_text_fixer.py",
        "plugins_zelda_mc_config.json",
        "plugins_zelda_mc_config.py",
        "plugins_zelda_mc_font_map.json",
        "plugins_zelda_mc_problem_analyzer.py",
        "plugins_zelda_mc_rules.py",
        "plugins_zelda_mc_tag_logic.py",
        "plugins_zelda_mc_tag_manager.py",
        "plugins_zelda_mc_text_fixer.py",
        "plugins_zelda_mc_translation_prompts_glossary.md",
        "plugins_zelda_mc_translation_prompts_prompts.json",
        "plugins_zelda_ww_config.json",
        "plugins_zelda_ww_config.py",
        "plugins_zelda_ww_font_map.json",
        "plugins_zelda_ww_problem_analyzer.py",
        "plugins_zelda_ww_rules.py",
        "plugins_zelda_ww_tag_logic.py",
        "plugins_zelda_ww_tag_manager.py",
        "plugins_zelda_ww_text_fixer.py",
        "plugins_zelda_ww_translation_prompts_glossary.md",
        "plugins_zelda_ww_translation_prompts_prompts.json",
        
        # Flattened/Duplicate handlers and utils in root
        "translation_handler.py",
        "translation_translation_handler.py",
        "translation_ui_handler.py",
        "translation_variations_dialog.py",
        "translation_prompts_glossary.md",
        "translation_prompts_prompts.json",
        
        # Duplicate Core/Utils in root (originals are in core/ or utils/)
        "config.py",
        "constants.py", 
        "logging_utils.py",
        "settings_manager.py",
        "data_manager.py",
        "data_state_processor.py",
        "spellchecker_manager.py",
        "tag_utils.py",
        "project_manager.py",
        "utils.py",
        "base_handler.py",
        "base_game_rules.py",
        "base_translation_handler.py",
        "base_ui_updater.py",
        "base_import_rules.py",
        
        # Duplicate folders that shouldn't be in root if they exist elsewhere
        "translation/translation_handler.py", # If removing the whole folder is too risky, remove file
    ]
    
    delete_files(files_to_delete)

    # 3. Rename Components to snake_case
    # Map: Current Path -> New Path
    renames = {
        "components/custom_list_widget.py": "components/custom_list_widget.py",
        "components/CustomListItemDelegate.py": "components/custom_list_item_delegate.py",
        "components/LineNumberedTextEdit.py": "components/line_numbered_text_edit.py",
        "components/line_number_area.py": "components/line_number_area.py",
        "components/TextHighlightManager.py": "components/text_highlight_manager.py",
        "components/editor_constants.py": "components/editor_constants.py",
        "components/LNET_highlight_interface.py": "components/lnet_highlight_interface.py",
        "components/LNET_line_number_area_paint_logic.py": "components/lnet_line_number_area_paint_logic.py",
        "components/editor_mouse_handlers.py": "components/editor_mouse_handlers.py",
        "components/LNET_paint_event_logic.py": "components/lnet_paint_event_logic.py",
        "components/editor_paint_handlers.py": "components/editor_paint_handlers.py",
        "components/LNET_paint_helpers.py": "components/lnet_paint_helpers.py",
    }
    move_files(renames)

    # 4. Organize Main Window components
    # Move main_window_*.py to ui/main_window/
    mw_moves = {
        "main_window_actions.py": "ui/main_window/main_window_actions.py",
        "main_window_block_handler.py": "ui/main_window/main_window_block_handler.py",
        "main_window_event_handler.py": "ui/main_window/main_window_event_handler.py",
        "main_window_helper.py": "ui/main_window/main_window_helper.py",
        "main_window_plugin_handler.py": "ui/main_window/main_window_plugin_handler.py",
        "main_window_ui_handler.py": "ui/main_window/main_window_ui_handler.py",
    }
    move_files(mw_moves)
    
    # Create __init__.py for the new package
    Path("ui/main_window/__init__.py").touch()

    # 5. Fix Imports
    # This dictionary maps "OldString" -> "NewString" for import statements
    import_replacements = {
        # Components renames
        "components.custom_list_widget": "components.custom_list_widget",
        "components.custom_list_item_delegate": "components.custom_list_item_delegate",
        "components.editor.line_numbered_text_edit": "components.line_numbered_text_edit",
        "components.line_number_area": "components.line_number_area",
        "components.editor.text_highlight_manager": "components.text_highlight_manager",
        "components.editor_constants": "components.editor_constants",
        "components.editor.highlight_interface": "components.lnet_highlight_interface",
        "components.editor.line_number_area_paint_logic": "components.lnet_line_number_area_paint_logic",
        "components.editor_mouse_handlers": "components.editor_mouse_handlers",
        "components.editor.paint_event_logic": "components.lnet_paint_event_logic",
        "components.editor_paint_handlers": "components.editor_paint_handlers",
        "components.editor.paint_helpers": "components.lnet_paint_helpers",
        
        # Main Window moves
        "main_window_actions": "ui.main_window.main_window_actions",
        "main_window_block_handler": "ui.main_window.main_window_block_handler",
        "main_window_event_handler": "ui.main_window.main_window_event_handler",
        "main_window_helper": "ui.main_window.main_window_helper",
        "main_window_plugin_handler": "ui.main_window.main_window_plugin_handler",
        "main_window_ui_handler": "ui.main_window.main_window_ui_handler",
        
        # Fixing Root Duplicates imports to point to correct locations
        "utils ": "utils.utils ", # sometimes import utils is used
        "logging_utils": "utils.logging_utils",
        "constants": "utils.constants",
        "syntax_highlighter": "utils.syntax_highlighter",
        "settings_manager": "core.settings_manager",
        "data_manager": "core.data_manager",
        "data_state_processor": "core.data_state_processor",
        "project_manager": "core.project_manager",
        "spellchecker_manager": "core.spellchecker_manager",
        "tag_utils": "core.tag_utils",
    }
    
    fix_imports(import_replacements)

    # 6. Final Commit
    git_commit("refactor: project cleanup and restructuring (phase 1)")
    
    print("\n✨ Cleanup finished! Please check if 'main.py' runs correctly.")
    print("NOTE: I kept file sizes as is for now. The 500-line limit will be addressed in the next refactoring phase.")

if __name__ == "__main__":
    main()