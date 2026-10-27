"""AGENTS.md rule 11: APP_VERSION changes only in a dedicated bump or release commit."""
import re
import subprocess
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[2]
# The last commit that bumped the version in a feature commit; the policy applies after it.
BASELINE = "8defc4ac"
VERSION_LINE = re.compile(r"^[+-]APP_VERSION\s*=", re.MULTILINE)


def _git(*args):
    return subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True, check=True).stdout


def test_version_changes_only_in_bump_commits():
    try:
        commits = _git("rev-list", f"{BASELINE}..HEAD", "--", "utils/constants.py").split()
    except (OSError, subprocess.CalledProcessError):
        pytest.skip("git history unavailable")
    offenders = []
    for sha in commits:
        subject = _git("show", "-s", "--format=%s", sha).strip()
        patch = _git("show", "--format=", "-U0", sha, "--", "utils/constants.py")
        if VERSION_LINE.search(patch) and not re.match(r"(Bump version|Release)\b", subject):
            offenders.append(f"{sha[:8]} {subject}")
    assert not offenders, "APP_VERSION changed outside a 'Bump version'/'Release' commit:\n" + "\n".join(offenders)
