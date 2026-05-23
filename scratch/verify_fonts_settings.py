import sys
import shutil
import json
from pathlib import Path
from PyQt5.QtWidgets import QApplication
from main import MainWindow
from core.project_manager import ProjectManager

def main():
    app = QApplication(sys.argv)
    
    # Create a temporary project directory
    temp_proj_dir = Path("d:/git/dev/Picoripi/scratch/test_verify_project")
    if temp_proj_dir.exists():
        shutil.rmtree(temp_proj_dir)
    temp_proj_dir.mkdir(parents=True, exist_ok=True)
    
    print("Initializing MainWindow...")
    mw = MainWindow()
    
    print("Creating new project...")
    pm = ProjectManager()
    success = pm.create_new_project(
        project_dir=temp_proj_dir,
        name="FontsVerifyProject",
        plugin_name="zelda_mc",
        source_path="d:/git/dev/Picoripi/scratch/test_verify_project",
        is_directory_mode=True
    )
    assert success is True
    mw.project_manager = pm
    
    # Set the font directory paths
    print("Configuring font directory paths...")
    mw.fonts_dir_path = "C:/temp/translated_fonts"
    mw.orig_fonts_dir_path = "C:/temp/original_fonts"
    
    print("Saving settings to project...")
    assert pm.save_settings_to_project(mw) is True
    
    # Read the .uiproj file on disk directly
    uiproj_path = temp_proj_dir / "project.uiproj"
    assert uiproj_path.exists()
    
    with open(uiproj_path, 'r', encoding='utf-8') as f:
        metadata = json.load(f)
        
    print("\nVerifying direct content in .uiproj:")
    project_settings = metadata.get("metadata", {}).get("settings", {})
    print("fonts_dir_path in file:", project_settings.get("fonts_dir_path"))
    print("orig_fonts_dir_path in file:", project_settings.get("orig_fonts_dir_path"))
    
    assert project_settings.get("fonts_dir_path") == "C:/temp/translated_fonts"
    assert project_settings.get("orig_fonts_dir_path") == "C:/temp/original_fonts"
    
    # Simulate project reload
    print("\nSimulating project reload...")
    mw_new = MainWindow()
    pm_new = ProjectManager()
    assert pm_new.load(uiproj_path) is True
    mw_new.project_manager = pm_new
    
    # Ensure they are set to empty first on new window
    mw_new.fonts_dir_path = ""
    mw_new.orig_fonts_dir_path = ""
    
    print("Restoring settings from project...")
    assert pm_new.load_settings_from_project(mw_new) is True
    
    print("Loaded fonts_dir_path:", mw_new.fonts_dir_path)
    print("Loaded orig_fonts_dir_path:", mw_new.orig_fonts_dir_path)
    
    assert mw_new.fonts_dir_path == "C:/temp/translated_fonts"
    assert mw_new.orig_fonts_dir_path == "C:/temp/original_fonts"
    
    # Cleanup
    print("\nCleaning up temporary project...")
    shutil.rmtree(temp_proj_dir)
    
    print("\nVERIFICATION SUCCESSFUL! Fonts directory paths are successfully saved in .uiproj and reloaded!")
    sys.exit(0)

if __name__ == "__main__":
    main()
