import subprocess
import sys
import os
import pytest

def test_ruff_check():
    """
    Runs Ruff check on the codebase to ensure no syntax errors or undefined names are present.
    """
    cmd = [sys.executable, "-m", "ruff", "check"]
    
    # Run the command in the project root
    result = subprocess.run(cmd, capture_output=True, text=True)
    
    assert result.returncode == 0, f"Ruff check failed with exit code {result.returncode}.\nOutput:\n{result.stdout}\nErrors:\n{result.stderr}"

