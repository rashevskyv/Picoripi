"""Command line for the ``check_fit`` tool: ``python -m mcp_server.check_fit <project.uiproj> <items.json>``.

``items.json`` holds ``[{"block": 0, "string": 12, "text": "..."}]``; the result is printed as JSON (UTF-8).
``--failed`` prints only the strings that do not fit or have problems.
"""
import json
import sys

from utils import app_mode

app_mode.headless = True

from mcp_server import tools  # noqa: E402


def main(argv) -> int:
    failed_only = "--failed" in argv
    args = [arg for arg in argv if arg != "--failed"]
    if len(args) != 2:
        print(__doc__, file=sys.stderr)
        return 2
    with open(args[1], encoding="utf-8") as handle:
        items = json.load(handle)
    result = tools.check_fit(args[0], items)
    if failed_only:
        result["items"] = [item for item in result["items"] if not item["ok"]]
    sys.stdout.reconfigure(encoding="utf-8")
    print(json.dumps(result, ensure_ascii=False, indent=1))
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
