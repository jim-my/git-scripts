"""Regression tests for git-diff-123."""

import json
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent
SCRIPT_PATH = REPO_ROOT / "git-diff-123"


def run(cmd, cwd, check=True):
    result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if check and result.returncode != 0:
        raise AssertionError(
            f"Command failed ({result.returncode}): {' '.join(cmd)}\n"
            f"stdout:\n{result.stdout}\n"
            f"stderr:\n{result.stderr}"
        )
    return result


def init_conflicted_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()

    run(["git", "init", "-q"], cwd=repo)
    run(["git", "config", "user.name", "Test User"], cwd=repo)
    run(["git", "config", "user.email", "test@example.com"], cwd=repo)

    (repo / "f.txt").write_text("line1\nline2\n", encoding="utf-8")
    run(["git", "add", "f.txt"], cwd=repo)
    run(["git", "commit", "-qm", "base"], cwd=repo)

    run(["git", "checkout", "-qb", "feature"], cwd=repo)
    (repo / "f.txt").write_text("line1\nours\n", encoding="utf-8")
    run(["git", "commit", "-am", "ours"], cwd=repo)

    run(["git", "checkout", "-q", "main"], cwd=repo)
    (repo / "f.txt").write_text("line1\ntheirs\n", encoding="utf-8")
    run(["git", "commit", "-am", "theirs"], cwd=repo)

    merge_result = run(["git", "merge", "feature"], cwd=repo, check=False)
    assert merge_result.returncode != 0

    return repo


def test_remerge_applies_clean_resolution_from_edited_files(tmp_path):
    repo = init_conflicted_repo(tmp_path)

    extract = run([str(SCRIPT_PATH), "--extract", "--json", "f.txt"], cwd=repo)
    files = json.loads(extract.stdout)

    ours_path = Path(files["ours"])
    base_path = Path(files["base"])
    theirs_path = Path(files["theirs"])

    # User manually edits both sides to the same resolved content.
    resolved = "line1\nresolved\n"
    ours_path.write_text(resolved, encoding="utf-8")
    theirs_path.write_text(resolved, encoding="utf-8")

    remerge = run(
        [
            str(SCRIPT_PATH),
            "--remerge",
            "f.txt",
            str(ours_path),
            str(base_path),
            str(theirs_path),
        ],
        cwd=repo,
        check=False,
    )

    assert remerge.returncode == 0, remerge.stdout + remerge.stderr
    assert (repo / "f.txt").read_text(encoding="utf-8") == resolved

    staged = run(["git", "diff", "--cached", "--name-only"], cwd=repo)
    assert staged.stdout.strip() == "f.txt"


def test_remerge_keeps_file_unchanged_when_manual_edits_still_conflict(tmp_path):
    repo = init_conflicted_repo(tmp_path)

    extract = run([str(SCRIPT_PATH), "--extract", "--json", "f.txt"], cwd=repo)
    files = json.loads(extract.stdout)

    ours_path = Path(files["ours"])
    base_path = Path(files["base"])
    theirs_path = Path(files["theirs"])

    # Keep conflicting edits.
    ours_path.write_text("line1\nmanual ours\n", encoding="utf-8")
    theirs_path.write_text("line1\nmanual theirs\n", encoding="utf-8")

    before_content = (repo / "f.txt").read_text(encoding="utf-8")

    remerge = run(
        [
            str(SCRIPT_PATH),
            "--remerge",
            "f.txt",
            str(ours_path),
            str(base_path),
            str(theirs_path),
        ],
        cwd=repo,
        check=False,
    )

    assert remerge.returncode == 1
    assert "Re-merge still has conflicts" in remerge.stdout
    assert (repo / "f.txt").read_text(encoding="utf-8") == before_content
