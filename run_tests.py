import os
import subprocess
import sys
import glob

def run_tests():
    # Шлях до папки з тестами
    test_dir = "tests"
    python_exe = os.path.join("venv", "Scripts", "python.exe")
    if not os.path.exists(python_exe):
        python_exe = sys.executable  # Fallback to current python
    
    # Знаходимо всі файли тестів
    test_files = glob.glob(os.path.join(test_dir, "**", "test_*.py"), recursive=True)
    
    print(f"--- Starting Optimized Test Pipeline (Python Orchestrator) ---")
    print(f"Found {len(test_files)} test files.")
    
    failed_files = []
    
    for i, test_file in enumerate(test_files, 1):
        print(f"[{i}/{len(test_files)}] Running: {test_file}")
        
        # Запускаємо pytest в окремому процесі
        result = subprocess.run([python_exe, "-m", "pytest", "-v", test_file])
        
        if result.returncode != 0:
            print(f"FAILED: {test_file}")
            failed_files.append(test_file)
            
    print("\n--- Test Summary ---")
    print(f"Total: {len(test_files)}")
    print(f"Passed: {len(test_files) - len(failed_files)}")
    print(f"Failed: {len(failed_files)}")
    
    if failed_files:
        print("\nFailed files:")
        for f in failed_files:
            print(f"  {f}")
        sys.exit(1)
    else:
        print("\nAll tests passed successfully!")
        sys.exit(0)

if __name__ == "__main__":
    run_tests()
