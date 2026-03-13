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


def init_repo_with_merged_branches(tmp_path: Path, include_free_branch=True):
    repo = tmp_path / "repo"
    repo.mkdir()
    run(["git", "init", "-q"], cwd=repo)
    run(["git", "config", "user.name", "Test User"], cwd=repo)
    run(["git", "config", "user.email", "test@example.com"], cwd=repo)
    initial_branch = run(["git", "symbolic-ref", "--short", "HEAD"], cwd=repo).stdout.strip()

    (repo / "base.txt").write_text("base\n", encoding="utf-8")
    run(["git", "add", "base.txt"], cwd=repo)
    run(["git", "commit", "-qm", "base"], cwd=repo)

    if include_free_branch:
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


def test_deletes_in_use_branches_when_second_prompt_confirmed(tmp_path):
    repo, _ = init_repo_with_merged_branches(tmp_path)

    result = run(
        [str(SCRIPT_PATH)],
        cwd=repo,
        input_text="y\ny\n",
    )

    assert result.returncode == 0
    assert not branch_exists(repo, "merged_free")
    assert branch_exists(repo, "merged_in_use")
    assert "Failed to delete: 1 branches" in result.stdout


def test_uses_main_as_merge_target_not_current_head(tmp_path):
    repo = tmp_path / "repo_main_target"
    repo.mkdir()
    run(["git", "init", "-q"], cwd=repo)
    run(["git", "config", "user.name", "Test User"], cwd=repo)
    run(["git", "config", "user.email", "test@example.com"], cwd=repo)
    initial_branch = run(["git", "symbolic-ref", "--short", "HEAD"], cwd=repo).stdout.strip()

    (repo / "base.txt").write_text("base\n", encoding="utf-8")
    run(["git", "add", "base.txt"], cwd=repo)
    run(["git", "commit", "-qm", "base"], cwd=repo)

    run(["git", "checkout", "-qb", "work_branch"], cwd=repo)
    (repo / "work.txt").write_text("work\n", encoding="utf-8")
    run(["git", "add", "work.txt"], cwd=repo)
    run(["git", "commit", "-qm", "work branch commit"], cwd=repo)

    run(["git", "checkout", "-q", initial_branch], cwd=repo)
    run(["git", "checkout", "-qb", "merged_to_main"], cwd=repo)
    (repo / "main-merged.txt").write_text("main merged\n", encoding="utf-8")
    run(["git", "add", "main-merged.txt"], cwd=repo)
    run(["git", "commit", "-qm", "merged_to_main"], cwd=repo)
    run(["git", "checkout", "-q", initial_branch], cwd=repo)
    run(["git", "merge", "--no-ff", "-qm", "merge merged_to_main", "merged_to_main"], cwd=repo)

    run(["git", "checkout", "-q", "work_branch"], cwd=repo)

    result = run(
        [str(SCRIPT_PATH), "--dry-run"],
        cwd=repo,
    )

    assert result.returncode == 0
    assert "merged_to_main" in result.stdout


def test_first_prompt_abort_keeps_all_branches(tmp_path):
    repo, _ = init_repo_with_merged_branches(tmp_path)

    result = run(
        [str(SCRIPT_PATH)],
        cwd=repo,
        input_text="n\n",
    )

    assert result.returncode == 0
    assert "Aborted." in result.stdout
    assert branch_exists(repo, "merged_free")
    assert branch_exists(repo, "merged_in_use")


def test_dry_run_reports_buckets_and_deletes_nothing(tmp_path):
    repo, _ = init_repo_with_merged_branches(tmp_path)

    result = run(
        [str(SCRIPT_PATH), "--dry-run"],
        cwd=repo,
    )

    assert result.returncode == 0
    assert "Merged branches that would be auto-deleted" in result.stdout
    assert "Merged branches currently checked out in other worktrees" in result.stdout
    assert "merged_free" in result.stdout
    assert "merged_in_use" in result.stdout
    assert branch_exists(repo, "merged_free")
    assert branch_exists(repo, "merged_in_use")


def test_only_in_use_branch_shows_no_immediate_deletion_message(tmp_path):
    repo, _ = init_repo_with_merged_branches(tmp_path, include_free_branch=False)

    result = run(
        [str(SCRIPT_PATH)],
        cwd=repo,
        input_text="n\n",
    )

    assert result.returncode == 0
    assert "No merged branches are eligible for immediate deletion." in result.stdout
    assert "Merged branches currently checked out in other worktrees" in result.stdout
    assert branch_exists(repo, "merged_in_use")
