"""Integration tests for git-find_file."""

import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent
SCRIPT_PATH = REPO_ROOT / "git-find_file"


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

    (repo / "present.txt").write_text("v1\n", encoding="utf-8")
    run(["git", "add", "present.txt"], cwd=repo)
    run(["git", "commit", "-qm", "add present"], cwd=repo)

    run(["git", "checkout", "-qb", "feature"], cwd=repo)
    (repo / "present.txt").write_text("feature\n", encoding="utf-8")
    run(["git", "commit", "-am", "feature change"], cwd=repo)

    run(["git", "checkout", "-q", "main"], cwd=repo)
    (repo / "deleted.txt").write_text("to be deleted\n", encoding="utf-8")
    run(["git", "add", "deleted.txt"], cwd=repo)
    run(["git", "commit", "-qm", "add deleted file"], cwd=repo)
    run(["git", "rm", "-q", "deleted.txt"], cwd=repo)
    run(["git", "commit", "-qm", "delete file"], cwd=repo)

    return repo


def test_find_file_current_tree_mode(tmp_path):
    repo = init_repo(tmp_path)
    result = run([str(SCRIPT_PATH), "present\\.txt", "--local"], cwd=repo)
    assert "main:present.txt" in result.stdout
    assert "feature:present.txt" in result.stdout


def test_find_file_deleted_mode(tmp_path):
    repo = init_repo(tmp_path)
    result = run([str(SCRIPT_PATH), "deleted\\.txt", "--local", "--deleted"], cwd=repo)
    assert "main:" in result.stdout
    assert ":deleted.txt" in result.stdout


def test_find_file_history_mode(tmp_path):
    repo = init_repo(tmp_path)
    result = run([str(SCRIPT_PATH), "present\\.txt", "--local", "--history"], cwd=repo)
    assert "main:" in result.stdout
    assert "feature:" in result.stdout
    assert ":present.txt" in result.stdout
