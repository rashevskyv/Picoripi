"""Add the Picoripi projects found under a folder to the Project Manager of a chosen data folder.

Same rules as the manager's "Import projects from a folder": every ``picoripi/project.uiproj`` below
``--root`` is found, one folder per series is created, and projects already listed are left as they are.
Dry run by default. With ``--apply`` the data folder gets a self-ignoring ``.gitignore`` (a ``*`` line, so Git
skips it) and the registry is backed up (a copy) before it is written. The dry run reports both and writes nothing.

    python scripts/import_projects_to_data_folder.py --root "<folder with the projects>" --data-dir "<your data folder>"
    python scripts/import_projects_to_data_folder.py --root ... --data-dir ... --apply
"""
from __future__ import annotations

import argparse
import os
import shutil
import sys
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def _parse(argv):
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--root", required=True, help="folder to search for picoripi/project.uiproj files")
    parser.add_argument("--data-dir", required=True, help="the data folder Picoripi uses (the one you chose)")
    parser.add_argument("--apply", action="store_true", help="write the registry (default: dry run)")
    return parser.parse_args(argv)


def main(argv=None) -> int:
    args = _parse(sys.argv[1:] if argv is None else argv)
    data_dir = Path(args.data_dir).expanduser().resolve()
    root = Path(args.root).expanduser().resolve()
    if not root.is_dir():
        print(f"ERROR: --root is not a folder: {root}")
        return 2
    # Point the app at the same folder before any Picoripi module reads it.
    os.environ["PICORIPI_HOME"] = str(data_dir)
    sys.path.insert(0, str(ROOT))

    from core.project_library import discovery, registry
    from utils.data_folder_git import (
        GIT_IGNORED, GIT_NOT_IGNORED, GIT_NO_REPO, data_folder_git_state, ensure_self_ignore, has_self_ignore,
    )

    found = discovery.find_projects(root)
    # A dry run must not write: an unreadable registry is read as empty here, not moved aside.
    registered = {os.path.abspath(p["path"]) for p in registry.read(data_dir, set_aside=args.apply)["projects"]}
    git_state = data_folder_git_state(data_dir).state
    git_text = {
        GIT_NO_REPO: "not inside a Git repository",
        GIT_IGNORED: "inside a Git repository that ignores it",
        GIT_NOT_IGNORED: "inside a Git repository, NOT ignored",
    }.get(git_state, "Git could not tell")
    if has_self_ignore(data_dir):
        ignore_text = "present"
    else:
        ignore_text = "missing, written below" if args.apply else "missing, --apply writes it"

    print(f"Data folder : {data_dir}")
    print(f"Search root : {root}")
    print(f"Git         : {git_text}")
    print(f".gitignore  : {ignore_text} (ignores the data folder itself)")
    print(f"Found       : {len(found)} project files")
    print()
    print(f"{'series':24} {'platform':10} {'name':30} {'state':16} project file")
    to_add = []
    for item in found:
        state = "ok"
        if item.get("error"):
            state = "unreadable"
        elif os.path.abspath(item["project_file"]) in registered:
            state = "already listed"
        elif item.get("duplicate"):
            state = "duplicate id"
        else:
            to_add.append(item)
        print(f"{item.get('series', '')[:24]:24} {item.get('platform', '')[:10]:10} "
              f"{(item.get('name') or '')[:30]:30} {state:16} {item['project_file']}")
    print()
    print(f"Would add   : {len(to_add)} (skipped: {len(found) - len(to_add)})")

    if not args.apply:
        print("Dry run: nothing written. Run again with --apply to add them.")
        return 0

    data_dir.mkdir(parents=True, exist_ok=True)
    # First, so the folder is ignored by Git before any file lands in it.
    if ensure_self_ignore(data_dir):
        print(f"Gitignore   : written {data_dir / '.gitignore'}")
    reg_file = registry.registry_path(data_dir)
    if reg_file.exists():
        stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        backup = data_dir / "backups" / f"project_manager_{stamp}.json"
        backup.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(reg_file, backup)   # a copy: the original stays and is then updated
        print(f"Backup      : {backup}")

    def operation(reg, items):
        folder_ids = {}
        for folder in reg.document["folders"]:
            folder_ids.setdefault(folder["name"].casefold(), folder["id"])
        for item in items:
            series = item.get("series") or ""
            folder_id = None
            if series:
                folder_id = folder_ids.get(series.casefold())
                if folder_id is None:
                    folder_id = reg.create_folder(series)
                    folder_ids[series.casefold()] = folder_id
            reg.add(item["project_file"], project_id=item.get("project_id", ""),
                    platform=item.get("platform", ""), folder_id=folder_id)

    document = registry.mutate(data_dir, operation, to_add)
    print(f"Written     : {reg_file} ({len(document['projects'])} projects listed)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
