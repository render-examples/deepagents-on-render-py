"""Tests for agents/tools/git.py — diff parsing and extraction tools."""

from agents.tools.git import (
    _parse_diff_to_file_diffs,
    parse_diff,
    list_changed_files,
    get_file_diff,
)


class TestParseDiffInternal:
    """Tests for the internal _parse_diff_to_file_diffs parser."""

    def test_single_file_modified(self, simple_diff):
        result = _parse_diff_to_file_diffs(simple_diff)
        assert len(result) == 1
        fd = result[0]
        assert fd.path == "src/utils.py"
        assert fd.change_type == "modified"
        assert fd.old_path is None

    def test_single_file_hunks(self, simple_diff):
        fd = _parse_diff_to_file_diffs(simple_diff)[0]
        assert len(fd.hunks) == 1
        hunk = fd.hunks[0]
        assert hunk.old_start == 10
        assert hunk.new_start == 10
        assert len(hunk.removed_lines) == 1
        assert len(hunk.added_lines) == 3

    def test_multi_file(self, multi_file_diff):
        result = _parse_diff_to_file_diffs(multi_file_diff)
        assert len(result) == 3
        paths = [fd.path for fd in result]
        assert paths == ["src/utils.py", "src/auth.py", "README.md"]

    def test_multi_file_change_types(self, multi_file_diff):
        result = _parse_diff_to_file_diffs(multi_file_diff)
        for fd in result:
            assert fd.change_type == "modified"

    def test_new_file(self, new_file_diff):
        result = _parse_diff_to_file_diffs(new_file_diff)
        assert len(result) == 1
        assert result[0].change_type == "added"
        assert result[0].path == "src/new_module.py"

    def test_deleted_file(self, deleted_file_diff):
        result = _parse_diff_to_file_diffs(deleted_file_diff)
        assert len(result) == 1
        assert result[0].change_type == "deleted"
        assert result[0].path == "src/old_module.py"

    def test_renamed_file(self, renamed_file_diff):
        result = _parse_diff_to_file_diffs(renamed_file_diff)
        assert len(result) == 1
        fd = result[0]
        assert fd.change_type == "renamed"
        assert fd.path == "src/new_name.py"
        assert fd.old_path == "src/old_name.py"

    def test_line_counts(self, multi_file_diff):
        result = _parse_diff_to_file_diffs(multi_file_diff)
        utils = result[0]
        assert utils.added_line_count == 1
        assert utils.removed_line_count == 0
        auth = result[1]
        assert auth.added_line_count == 4
        assert auth.removed_line_count == 0

    def test_empty_diff(self):
        result = _parse_diff_to_file_diffs("")
        assert result == []


class TestParseDiffTool:
    """Tests for the parse_diff LangChain tool."""

    def test_returns_list_of_dicts(self, simple_diff):
        result = parse_diff.invoke({"diff": simple_diff})
        assert isinstance(result, list)
        assert len(result) == 1
        assert isinstance(result[0], dict)

    def test_dict_structure(self, simple_diff):
        result = parse_diff.invoke({"diff": simple_diff})[0]
        assert result["path"] == "src/utils.py"
        assert result["change_type"] == "modified"
        assert "hunks" in result
        assert len(result["hunks"]) == 1

    def test_hunk_dict_structure(self, simple_diff):
        hunk = parse_diff.invoke({"diff": simple_diff})[0]["hunks"][0]
        assert hunk["old_start"] == 10
        assert hunk["new_start"] == 10
        assert isinstance(hunk["added_lines"], list)
        assert isinstance(hunk["removed_lines"], list)
        assert isinstance(hunk["context_lines"], list)


class TestListChangedFiles:
    def test_single_file(self, simple_diff):
        result = list_changed_files.invoke({"diff": simple_diff})
        assert len(result) == 1
        assert result[0]["path"] == "src/utils.py"
        assert result[0]["change_type"] == "modified"

    def test_multi_file(self, multi_file_diff):
        result = list_changed_files.invoke({"diff": multi_file_diff})
        assert len(result) == 3
        paths = [f["path"] for f in result]
        assert "src/utils.py" in paths
        assert "src/auth.py" in paths
        assert "README.md" in paths

    def test_line_counts(self, simple_diff):
        result = list_changed_files.invoke({"diff": simple_diff})[0]
        assert result["lines_added"] == 3
        assert result["lines_removed"] == 1

    def test_new_file_type(self, new_file_diff):
        result = list_changed_files.invoke({"diff": new_file_diff})
        assert result[0]["change_type"] == "added"

    def test_deleted_file_type(self, deleted_file_diff):
        result = list_changed_files.invoke({"diff": deleted_file_diff})
        assert result[0]["change_type"] == "deleted"

    def test_renamed_file_includes_old_path(self, renamed_file_diff):
        result = list_changed_files.invoke({"diff": renamed_file_diff})[0]
        assert result["old_path"] == "src/old_name.py"
        assert result["path"] == "src/new_name.py"

    def test_empty_diff(self):
        result = list_changed_files.invoke({"diff": ""})
        assert result == []


class TestGetFileDiff:
    def test_extracts_single_file(self, multi_file_diff):
        result = get_file_diff.invoke({
            "diff": multi_file_diff,
            "file_path": "src/auth.py",
        })
        assert "src/auth.py" in result
        assert "def logout" in result
        assert "src/utils.py" not in result
        assert "README.md" not in result

    def test_extracts_first_file(self, multi_file_diff):
        result = get_file_diff.invoke({
            "diff": multi_file_diff,
            "file_path": "src/utils.py",
        })
        assert "import json" in result
        assert "def logout" not in result

    def test_extracts_last_file(self, multi_file_diff):
        result = get_file_diff.invoke({
            "diff": multi_file_diff,
            "file_path": "README.md",
        })
        assert "Updated docs" in result
        assert "src/auth.py" not in result

    def test_not_found(self, multi_file_diff):
        result = get_file_diff.invoke({
            "diff": multi_file_diff,
            "file_path": "nonexistent.py",
        })
        assert result == ""

    def test_result_is_valid_diff(self, multi_file_diff):
        result = get_file_diff.invoke({
            "diff": multi_file_diff,
            "file_path": "src/auth.py",
        })
        assert result.startswith("diff --git")
        assert "@@" in result
