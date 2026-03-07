"""Integration tests for git-untracked-overwritten."""

import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT_PATH = REPO_ROOT / "git-untracked-overwritten"


def run(cmd, cwd, check=True):
    result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if check and result.returncode != 0:
        raise AssertionError(
            f"Command failed ({result.returncode}): {' '.join(cmd)}\n"
            f"stdout:\n{result.stdout}\n"
            f"stderr:\n{result.stderr}"
        )
    return result


def init_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()

    run(["git", "init", "-q"], cwd=repo)
    run(["git", "config", "user.name", "Test User"], cwd=repo)
    run(["git", "config", "user.email", "test@example.com"], cwd=repo)

    (repo / "base.txt").write_text("base\n", encoding="utf-8")
    run(["git", "add", "base.txt"], cwd=repo)
    run(["git", "commit", "-qm", "base"], cwd=repo)

    run(["git", "checkout", "-qb", "feature"], cwd=repo)
    (repo / "same.txt").write_text("same content\n", encoding="utf-8")
    (repo / "different.txt").write_text("target content\n", encoding="utf-8")
    run(["git", "add", "same.txt", "different.txt"], cwd=repo)
    run(["git", "commit", "-qm", "add target files"], cwd=repo)

    run(["git", "checkout", "-q", "main"], cwd=repo)
    (repo / "same.txt").write_text("same content\n", encoding="utf-8")
    (repo / "different.txt").write_text("local different content\n", encoding="utf-8")

    return repo


def test_classifies_identical_vs_different(tmp_path):
    repo = init_repo(tmp_path)
    result = run([str(SCRIPT_PATH), "feature"], cwd=repo)

    assert "Identical (safe to delete):" in result.stdout
    assert "  - same.txt" in result.stdout
    assert "Different (review before merge):" in result.stdout
    assert "  - different.txt" in result.stdout


def test_diff_mode_shows_inline_diff_for_different_files(tmp_path):
    repo = init_repo(tmp_path)
    result = run([str(SCRIPT_PATH), "feature", "--diff"], cwd=repo)

    assert "Diff for: different.txt" in result.stdout
    assert "local different content" in result.stdout
    assert "target content" in result.stdout


def test_errors_for_unknown_ref(tmp_path):
    repo = init_repo(tmp_path)
    result = run([str(SCRIPT_PATH), "missing-ref"], cwd=repo, check=False)

    assert result.returncode == 1
    assert "Error: could not resolve ref 'missing-ref'" in result.stderr
