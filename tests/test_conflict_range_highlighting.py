"""Tests for conflict-range highlighting (Phase 1).

Tests --tool-conflict-ranges mode of git-resolve-conflict, which computes
conflict line ranges by finding overlapping ours/theirs changes relative to
base — without running a full merge.
"""

import json
import subprocess
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT_PATH = REPO_ROOT / "git-resolve-conflict"


def conflict_ranges(ours_text, base_text, theirs_text, tmp_path):
    """Write temp files, run --tool-conflict-ranges, return (data, returncode)."""
    ours = tmp_path / "ours"
    base = tmp_path / "base"
    theirs = tmp_path / "theirs"
    ours.write_text(ours_text)
    base.write_text(base_text)
    theirs.write_text(theirs_text)

    result = subprocess.run(
        [str(SCRIPT_PATH), "--tool-conflict-ranges", str(ours), str(base), str(theirs)],
        capture_output=True,
        text=True,
    )
    return json.loads(result.stdout), result.returncode


def test_both_sides_change_same_line(tmp_path):
    """Both ours and theirs changed line 2 → one conflict range at ours line 2."""
    base = "line1\nshared\nline3\n"
    ours = "line1\nours_edit\nline3\n"
    theirs = "line1\ntheirs_edit\nline3\n"

    data, rc = conflict_ranges(ours, base, theirs, tmp_path)

    assert rc == 0
    assert data["status"] == "ok"
    assert len(data["ranges"]) == 1
    assert data["ranges"][0]["ours_start"] == 2
    assert data["ranges"][0]["ours_end"] == 2


def test_non_overlapping_changes_produce_no_ranges(tmp_path):
    """Ours changed line 2, theirs changed line 4 → different base regions, no conflict."""
    base = "a\nb\nc\nd\ne\n"
    ours = "a\nours\nc\nd\ne\n"
    theirs = "a\nb\nc\ntheirs\ne\n"

    data, rc = conflict_ranges(ours, base, theirs, tmp_path)

    assert rc == 0
    assert data["ranges"] == []


def test_identical_files_produce_no_ranges(tmp_path):
    """ours == base == theirs → no changes anywhere, no ranges."""
    content = "alpha\nbeta\ngamma\n"

    data, rc = conflict_ranges(content, content, content, tmp_path)

    assert rc == 0
    assert data["ranges"] == []


def test_multiple_independent_conflict_regions(tmp_path):
    """Two separate conflict regions are both reported."""
    base = "a\nb\nc\nd\ne\nf\ng\nh\n"
    ours = "a\nours1\nc\nd\ne\nours2\ng\nh\n"    # changed lines 2 and 6
    theirs = "a\ntheirs1\nc\nd\ne\ntheirs2\ng\nh\n"  # changed lines 2 and 6

    data, rc = conflict_ranges(ours, base, theirs, tmp_path)

    assert rc == 0
    assert len(data["ranges"]) == 2
    starts = [r["ours_start"] for r in data["ranges"]]
    assert 2 in starts
    assert 6 in starts


def test_only_ours_changed_produces_no_range(tmp_path):
    """Ours changed, theirs unchanged → no conflict (clean auto-merge)."""
    base = "line1\nline2\nline3\n"
    ours = "line1\nours_only\nline3\n"
    theirs = base  # no change

    data, rc = conflict_ranges(ours, base, theirs, tmp_path)

    assert rc == 0
    assert data["ranges"] == []


def test_both_insert_at_same_base_position(tmp_path):
    """Both sides insert after the same base line → conflict range."""
    base = "line1\nline2\nline3\n"
    ours = "line1\ninserted_by_ours\nline2\nline3\n"    # insert before line2
    theirs = "line1\ninserted_by_theirs\nline2\nline3\n"  # insert before line2

    data, rc = conflict_ranges(ours, base, theirs, tmp_path)

    assert rc == 0
    assert len(data["ranges"]) >= 1


def test_missing_argument_exits_nonzero(tmp_path):
    """Calling --tool-conflict-ranges with wrong arg count exits non-zero."""
    result = subprocess.run(
        [str(SCRIPT_PATH), "--tool-conflict-ranges", "only_one_arg"],
        capture_output=True,
        text=True,
    )
    assert result.returncode != 0


def test_nonexistent_file_returns_json_error(tmp_path):
    """Missing input file → JSON error, not silent empty ranges."""
    result = subprocess.run(
        [str(SCRIPT_PATH), "--tool-conflict-ranges",
         "/nonexistent/ours", "/nonexistent/base", "/nonexistent/theirs"],
        capture_output=True,
        text=True,
    )
    data = json.loads(result.stdout)
    assert result.returncode != 0
    assert data["status"] == "error"
    assert "message" in data


def test_deletion_at_top_of_file_produces_valid_line_numbers(tmp_path):
    """Ours deletes first line, theirs edits it → ours_start must be >= 1 (no lnum:0 in quickfix)."""
    base = "first_line\nline2\nline3\n"
    ours = "line2\nline3\n"          # deleted first line
    theirs = "edited_first\nline2\nline3\n"  # edited first line

    data, rc = conflict_ranges(ours, base, theirs, tmp_path)

    assert rc == 0
    assert data["status"] == "ok"
    # May or may not detect a conflict range, but any reported range must have valid line numbers
    for r in data["ranges"]:
        assert r["ours_start"] >= 1, f"ours_start={r['ours_start']} is invalid (< 1)"
        assert r["ours_end"] >= 1, f"ours_end={r['ours_end']} is invalid (< 1)"
