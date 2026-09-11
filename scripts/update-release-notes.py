"""Refresh the commit log JSON inside release-notes.html from git history."""

from __future__ import annotations

import json
import re
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
HTML_PATH = ROOT / "release-notes.html"
MARKER_START = "<!-- COMMITS_JSON_START -->"
MARKER_END = "<!-- COMMITS_JSON_END -->"


def git_commits() -> list[dict]:
    raw = subprocess.check_output(
        ["git", "log", "--pretty=format:%h\t%ad\t%s", "--date=short"],
        cwd=ROOT,
        text=True,
    )
    commits: list[dict] = []
    for line in raw.splitlines():
        short, date, subject = line.split("\t", 2)
        kind = "other"
        lower = subject.lower()
        for prefix, k in (
            ("feat:", "feat"),
            ("fix:", "fix"),
            ("ui:", "ui"),
            ("style:", "style"),
            ("docs:", "docs"),
            ("chore:", "chore"),
            ("ci:", "ci"),
            ("merge ", "merge"),
        ):
            if lower.startswith(prefix):
                kind = k
                break
        commits.append(
            {
                "hash": short,
                "date": date,
                "subject": subject,
                "kind": kind,
                "rebuild": "rebuild frontend dist" in lower,
            }
        )
    return commits


def main() -> None:
    html = HTML_PATH.read_text(encoding="utf-8")
    if MARKER_START not in html or MARKER_END not in html:
        raise SystemExit("release-notes.html is missing COMMITS_JSON markers")
    payload = json.dumps(git_commits(), indent=2)
    block = (
        f"{MARKER_START}\n"
        f'<script type="application/json" id="commits-json">\n{payload}\n</script>\n'
        f"{MARKER_END}"
    )
    updated = re.sub(
        re.escape(MARKER_START) + r".*?" + re.escape(MARKER_END),
        lambda _m: block,
        html,
        count=1,
        flags=re.S,
    )
    HTML_PATH.write_text(updated, encoding="utf-8", newline="\n")
    print(f"Updated {HTML_PATH} with {payload.count(chr(10)) and 'commits'}")


if __name__ == "__main__":
    main()
