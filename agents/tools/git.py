"""Tools for parsing and extracting structured data from unified diffs."""

from __future__ import annotations

import re
from dataclasses import dataclass, field, asdict

from langchain.tools import tool


@dataclass
class Hunk:
    old_start: int
    old_count: int
    new_start: int
    new_count: int
    header: str
    added_lines: list[str] = field(default_factory=list)
    removed_lines: list[str] = field(default_factory=list)
    context_lines: list[str] = field(default_factory=list)


@dataclass
class FileDiff:
    path: str
    change_type: str  # "added", "modified", "deleted", "renamed"
    old_path: str | None = None
    hunks: list[Hunk] = field(default_factory=list)

    @property
    def added_line_count(self) -> int:
        return sum(len(h.added_lines) for h in self.hunks)

    @property
    def removed_line_count(self) -> int:
        return sum(len(h.removed_lines) for h in self.hunks)


_DIFF_HEADER = re.compile(r"^diff --git a/(.*) b/(.*)$")
_HUNK_HEADER = re.compile(
    r"^@@ -(\d+)(?:,(\d+))? \+(\d+)(?:,(\d+))? @@(.*)$"
)


def _parse_diff_to_file_diffs(diff: str) -> list[FileDiff]:
    """Parse a unified diff string into a list of FileDiff objects."""
    file_diffs: list[FileDiff] = []
    current: FileDiff | None = None
    current_hunk: Hunk | None = None

    for line in diff.splitlines():
        header_match = _DIFF_HEADER.match(line)
        if header_match:
            old_path, new_path = header_match.group(1), header_match.group(2)
            if new_path == "/dev/null":
                change_type = "deleted"
                path = old_path
            elif old_path == "/dev/null":
                change_type = "added"
                path = new_path
            elif old_path != new_path:
                change_type = "renamed"
                path = new_path
            else:
                change_type = "modified"
                path = new_path
            current = FileDiff(
                path=path,
                change_type=change_type,
                old_path=old_path if old_path != new_path else None,
            )
            current_hunk = None
            file_diffs.append(current)
            continue

        hunk_match = _HUNK_HEADER.match(line)
        if hunk_match and current is not None:
            current_hunk = Hunk(
                old_start=int(hunk_match.group(1)),
                old_count=int(hunk_match.group(2) or 1),
                new_start=int(hunk_match.group(3)),
                new_count=int(hunk_match.group(4) or 1),
                header=hunk_match.group(5).strip(),
            )
            current.hunks.append(current_hunk)
            continue

        if current_hunk is not None:
            if line.startswith("+"):
                current_hunk.added_lines.append(line[1:])
            elif line.startswith("-"):
                current_hunk.removed_lines.append(line[1:])
            elif line.startswith(" "):
                current_hunk.context_lines.append(line[1:])

    return file_diffs


@tool
def parse_diff(diff: str) -> list[dict]:
    """Parse a unified diff into structured file changes.

    Returns a list of file change objects, each containing the file path,
    change type (added/modified/deleted/renamed), and hunks with added lines,
    removed lines, and context lines with their line numbers.
    """
    return [asdict(fd) for fd in _parse_diff_to_file_diffs(diff)]


@tool
def list_changed_files(diff: str) -> list[dict]:
    """List all files changed in a diff with their change type and line counts.

    Returns a list of objects with path, change_type (added/modified/deleted/renamed),
    lines_added, and lines_removed.
    """
    return [
        {
            "path": fd.path,
            "change_type": fd.change_type,
            "old_path": fd.old_path,
            "lines_added": fd.added_line_count,
            "lines_removed": fd.removed_line_count,
        }
        for fd in _parse_diff_to_file_diffs(diff)
    ]


@tool
def get_file_diff(diff: str, file_path: str) -> str:
    """Extract the raw diff for a single file from a multi-file diff.

    Pass the full diff and a file path. Returns the unified diff section
    for that file only, or an empty string if the file is not found.
    """
    lines = diff.splitlines()
    capturing = False
    result: list[str] = []

    for line in lines:
        header_match = _DIFF_HEADER.match(line)
        if header_match:
            if capturing:
                break
            old_path, new_path = header_match.group(1), header_match.group(2)
            if file_path in (old_path, new_path):
                capturing = True
        if capturing:
            result.append(line)

    return "\n".join(result)
