"""Integration tests for git-untracked-conflict."""

import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT_PATH = REPO_ROOT / "git-untracked-conflict"


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
    initial_branch = run(["git", "symbolic-ref", "--short", "HEAD"], cwd=repo).stdout.strip()

    (repo / "base.txt").write_text("base\n", encoding="utf-8")
    run(["git", "add", "base.txt"], cwd=repo)
    run(["git", "commit", "-qm", "base"], cwd=repo)

    run(["git", "checkout", "-qb", "feature"], cwd=repo)
    (repo / "same.txt").write_text("same content\n", encoding="utf-8")
    (repo / "different.txt").write_text("target content\n", encoding="utf-8")
    run(["git", "add", "same.txt", "different.txt"], cwd=repo)
    run(["git", "commit", "-qm", "add target files"], cwd=repo)

    run(["git", "checkout", "-q", initial_branch], cwd=repo)
    (repo / "same.txt").write_text("same content\n", encoding="utf-8")
    (repo / "different.txt").write_text("local different content\n", encoding="utf-8")

    return repo


def init_collision_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo_collision"
    repo.mkdir()

    run(["git", "init", "-q"], cwd=repo)
    run(["git", "config", "user.name", "Test User"], cwd=repo)
    run(["git", "config", "user.email", "test@example.com"], cwd=repo)
    initial_branch = run(["git", "symbolic-ref", "--short", "HEAD"], cwd=repo).stdout.strip()

    (repo / "base.txt").write_text("base\n", encoding="utf-8")
    run(["git", "add", "base.txt"], cwd=repo)
    run(["git", "commit", "-qm", "base"], cwd=repo)

    run(["git", "checkout", "-qb", "feature"], cwd=repo)
    (repo / "a").mkdir(exist_ok=True)
    (repo / "a" / "b.txt").write_text("target path a/b\n", encoding="utf-8")
    (repo / "a_b.txt").write_text("target path a_b\n", encoding="utf-8")
    run(["git", "add", "a/b.txt", "a_b.txt"], cwd=repo)
    run(["git", "commit", "-qm", "add collision-prone file names"], cwd=repo)

    run(["git", "checkout", "-q", initial_branch], cwd=repo)
    (repo / "a").mkdir(exist_ok=True)
    (repo / "a" / "b.txt").write_text("local path a/b\n", encoding="utf-8")
    (repo / "a_b.txt").write_text("local path a_b\n", encoding="utf-8")

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


def test_diff_mode_uses_correct_target_for_colliding_sanitized_names(tmp_path):
    repo = init_collision_repo(tmp_path)

    result = run([str(SCRIPT_PATH), "feature", "--diff"], cwd=repo)

    assert "Diff for: a/b.txt" in result.stdout
    assert "Diff for: a_b.txt" in result.stdout
    assert "target path a/b" in result.stdout
    assert "target path a_b" in result.stdout


def test_no_untracked_files(tmp_path):
    """When there are no untracked files, report clearly and exit 0."""
    repo = tmp_path / "repo"
    repo.mkdir()
    run(["git", "init", "-q"], cwd=repo)
    run(["git", "config", "user.name", "Test User"], cwd=repo)
    run(["git", "config", "user.email", "test@example.com"], cwd=repo)
    (repo / "base.txt").write_text("base\n", encoding="utf-8")
    run(["git", "add", "base.txt"], cwd=repo)
    run(["git", "commit", "-qm", "base"], cwd=repo)
    run(["git", "checkout", "-qb", "feature"], cwd=repo)
    run(["git", "checkout", "-q", "HEAD~0"], cwd=repo)  # detached, no untracked

    # No untracked files on the initial branch
    result = run([str(SCRIPT_PATH), "feature"], cwd=repo)

    assert result.returncode == 0
    assert "No untracked files would be overwritten" in result.stdout


def test_no_overlap_with_target_ref(tmp_path):
    """When untracked files don't appear in the target ref, report clearly and exit 0."""
    repo = init_repo(tmp_path)
    # Add an extra untracked file that doesn't exist in the feature branch
    (repo / "only_local.txt").write_text("local only\n", encoding="utf-8")

    # Remove the files that DO overlap so only the non-overlapping file remains
    (repo / "same.txt").unlink()
    (repo / "different.txt").unlink()

    result = run([str(SCRIPT_PATH), "feature"], cwd=repo)

    assert result.returncode == 0
    assert "No untracked files would be overwritten" in result.stdout


def test_help_flag_exits_zero_with_usage(tmp_path):
    """--help prints usage and exits 0."""
    repo = init_repo(tmp_path)
    result = run([str(SCRIPT_PATH), "--help"], cwd=repo, check=False)

    assert result.returncode == 0
    assert "Usage:" in result.stdout


def test_no_args_exits_nonzero_with_usage(tmp_path):
    """No arguments exits non-zero and prints usage."""
    repo = init_repo(tmp_path)
    result = run([str(SCRIPT_PATH)], cwd=repo, check=False)

    assert result.returncode != 0
    assert "Usage:" in result.stdout


def test_detects_overlap_when_invoked_from_subdirectory(tmp_path):
    """Running from a subdirectory correctly detects overlap (subdirectory bug)."""
    repo = init_repo(tmp_path)
    subdir = repo / "subdir"
    subdir.mkdir()

    result = run([str(SCRIPT_PATH), "feature"], cwd=subdir)

    assert "  - same.txt" in result.stdout
    assert "  - different.txt" in result.stdout


def test_detects_gitignored_untracked_files_that_would_be_overwritten(tmp_path):
    """Files that are gitignored locally but tracked in the target ref are detected."""
    repo = tmp_path / "repo"
    repo.mkdir()
    run(["git", "init", "-q"], cwd=repo)
    run(["git", "config", "user.name", "Test User"], cwd=repo)
    run(["git", "config", "user.email", "test@example.com"], cwd=repo)
    initial_branch = run(["git", "symbolic-ref", "--short", "HEAD"], cwd=repo).stdout.strip()

    # Base commit with .gitignore that ignores *.dxt
    (repo / ".gitignore").write_text("*.dxt\n", encoding="utf-8")
    (repo / "base.txt").write_text("base\n", encoding="utf-8")
    run(["git", "add", ".gitignore", "base.txt"], cwd=repo)
    run(["git", "commit", "-qm", "base"], cwd=repo)

    # Feature branch force-adds a .dxt file (tracked despite .gitignore)
    run(["git", "checkout", "-qb", "feature"], cwd=repo)
    (repo / "config.dxt").write_text("dxt content in target\n", encoding="utf-8")
    run(["git", "add", "-f", "config.dxt"], cwd=repo)
    run(["git", "commit", "-qm", "add dxt file"], cwd=repo)

    # Back on main: the .dxt file exists in the working tree but is gitignored/untracked
    run(["git", "checkout", "-q", initial_branch], cwd=repo)
    (repo / "config.dxt").write_text("local dxt content\n", encoding="utf-8")

    result = run([str(SCRIPT_PATH), "feature"], cwd=repo)

    assert "  - config.dxt" in result.stdout


def test_diff_labels_show_ref_not_tmpdir_path(tmp_path):
    """--diff output labels use 'local:<file>' and '<ref>:<file>', not tmpdir paths."""
    repo = init_repo(tmp_path)
    result = run([str(SCRIPT_PATH), "feature", "--diff"], cwd=repo)

    # Should NOT contain any /tmp or /var path fragments
    assert "/tmp" not in result.stdout
    assert "target.XXXXXX" not in result.stdout
    assert "local:different.txt" in result.stdout
    assert "feature:different.txt" in result.stdout
