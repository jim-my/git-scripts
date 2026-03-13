"""Integration tests for git-delete-local-merged."""

import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT_PATH = REPO_ROOT / "git-delete-local-merged"


def run(cmd, cwd, check=True, input_text=None):
    result = subprocess.run(
        cmd,
        cwd=cwd,
        capture_output=True,
        text=True,
        input=input_text,
    )
    if check and result.returncode != 0:
        raise AssertionError(
            f"Command failed ({result.returncode}): {' '.join(cmd)}\n"
            f"stdout:\n{result.stdout}\n"
            f"stderr:\n{result.stderr}"
        )
    return result


def branch_exists(repo: Path, branch: str) -> bool:
    result = run(
        ["git", "show-ref", "--verify", f"refs/heads/{branch}"],
        cwd=repo,
        check=False,
    )
    return result.returncode == 0


def init_repo_with_merged_branches(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    run(["git", "init", "-q"], cwd=repo)
    run(["git", "config", "user.name", "Test User"], cwd=repo)
    run(["git", "config", "user.email", "test@example.com"], cwd=repo)
    initial_branch = run(["git", "symbolic-ref", "--short", "HEAD"], cwd=repo).stdout.strip()

    (repo / "base.txt").write_text("base\n", encoding="utf-8")
    run(["git", "add", "base.txt"], cwd=repo)
    run(["git", "commit", "-qm", "base"], cwd=repo)

    # Branch that can be auto-deleted.
    run(["git", "checkout", "-qb", "merged_free"], cwd=repo)
    (repo / "free.txt").write_text("free\n", encoding="utf-8")
    run(["git", "add", "free.txt"], cwd=repo)
    run(["git", "commit", "-qm", "merged_free"], cwd=repo)
    run(["git", "checkout", "-q", initial_branch], cwd=repo)
    run(["git", "merge", "--no-ff", "-qm", "merge merged_free", "merged_free"], cwd=repo)

    # Branch that is merged, but checked out in another worktree.
    run(["git", "checkout", "-qb", "merged_in_use"], cwd=repo)
    (repo / "in-use.txt").write_text("in-use\n", encoding="utf-8")
    run(["git", "add", "in-use.txt"], cwd=repo)
    run(["git", "commit", "-qm", "merged_in_use"], cwd=repo)
    run(["git", "checkout", "-q", initial_branch], cwd=repo)
    run(["git", "merge", "--no-ff", "-qm", "merge merged_in_use", "merged_in_use"], cwd=repo)

    worktree_path = tmp_path / "other-worktree"
    run(["git", "worktree", "add", str(worktree_path), "merged_in_use"], cwd=repo)

    return repo, worktree_path


def test_defers_in_use_worktree_branches_to_second_confirmation(tmp_path):
    repo, _ = init_repo_with_merged_branches(tmp_path)

    result = run(
        [str(SCRIPT_PATH)],
        cwd=repo,
        input_text="y\nn\n",
    )

    assert result.returncode == 0
    assert "Merged branches that will be deleted now" in result.stdout
    assert "merged_free" in result.stdout
    assert "Merged branches currently checked out in other worktrees" in result.stdout
    assert "merged_in_use" in result.stdout
    assert "Skipped in-use merged branches." in result.stdout
    assert not branch_exists(repo, "merged_free")
    assert branch_exists(repo, "merged_in_use")
