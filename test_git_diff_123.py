"""Regression tests for git-resolve-conflict."""

import json
import os
import pty
import select
import subprocess
import time
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parent
SCRIPT_PATH = REPO_ROOT / "git-resolve-conflict"
LEGACY_SHIM_PATH = REPO_ROOT / "git-diff-123"


def run(cmd, cwd, check=True):
    result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if check and result.returncode != 0:
        raise AssertionError(
            f"Command failed ({result.returncode}): {' '.join(cmd)}\n"
            f"stdout:\n{result.stdout}\n"
            f"stderr:\n{result.stderr}"
        )
    return result


def init_conflicted_repo(tmp_path: Path, file_path: str = "f.txt") -> Path:
    """Two-parent merge conflict on one file (classic content conflict)."""
    repo = tmp_path / "repo"
    repo.mkdir()

    run(["git", "init", "-q"], cwd=repo)
    run(["git", "config", "user.name", "Test User"], cwd=repo)
    run(["git", "config", "user.email", "test@example.com"], cwd=repo)

    target = repo / file_path
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text("line1\nline2\n", encoding="utf-8")
    run(["git", "add", file_path], cwd=repo)
    run(["git", "commit", "-qm", "base"], cwd=repo)

    run(["git", "checkout", "-qb", "feature"], cwd=repo)
    target.write_text("line1\nours\n", encoding="utf-8")
    run(["git", "commit", "-am", "ours"], cwd=repo)

    run(["git", "checkout", "-q", "main"], cwd=repo)
    target.write_text("line1\ntheirs\n", encoding="utf-8")
    run(["git", "commit", "-am", "theirs"], cwd=repo)

    merge_result = run(["git", "merge", "feature"], cwd=repo, check=False)
    assert merge_result.returncode != 0

    return repo


def init_multi_hunk_conflicted_repo(tmp_path: Path, file_path: str = "f.txt") -> Path:
    """Merge conflict with at least two independent conflict hunks."""
    repo = tmp_path / "repo_multi_hunk_conflict"
    repo.mkdir()

    run(["git", "init", "-q"], cwd=repo)
    run(["git", "branch", "-m", "main"], cwd=repo)
    run(["git", "config", "user.name", "Test User"], cwd=repo)
    run(["git", "config", "user.email", "test@example.com"], cwd=repo)

    target = repo / file_path
    target.write_text("A\nkeep1\nB\nkeep2\nC\n", encoding="utf-8")
    run(["git", "add", file_path], cwd=repo)
    run(["git", "commit", "-qm", "base"], cwd=repo)

    run(["git", "checkout", "-qb", "feature"], cwd=repo)
    target.write_text("A\nours1\nB\nours2\nC\n", encoding="utf-8")
    run(["git", "add", file_path], cwd=repo)
    run(["git", "commit", "-qm", "feature edits"], cwd=repo)

    run(["git", "checkout", "-q", "main"], cwd=repo)
    target.write_text("A\ntheirs1\nB\ntheirs2\nC\n", encoding="utf-8")
    run(["git", "add", file_path], cwd=repo)
    run(["git", "commit", "-qm", "main edits"], cwd=repo)

    merge_result = run(["git", "merge", "feature"], cwd=repo, check=False)
    assert merge_result.returncode != 0
    return repo


def init_modify_delete_conflict_repo(tmp_path: Path, file_path: str = "f.txt") -> Path:
    """Merge conflict where one side modifies and the other deletes the same file."""
    repo = tmp_path / "repo_modify_delete_conflict"
    repo.mkdir()

    run(["git", "init", "-q"], cwd=repo)
    run(["git", "config", "user.name", "Test User"], cwd=repo)
    run(["git", "config", "user.email", "test@example.com"], cwd=repo)

    target = repo / file_path
    target.write_text("line1\nline2\n", encoding="utf-8")
    run(["git", "add", file_path], cwd=repo)
    run(["git", "commit", "-qm", "base"], cwd=repo)

    run(["git", "checkout", "-qb", "feature"], cwd=repo)
    target.write_text("line1\nfeature update\n", encoding="utf-8")
    run(["git", "commit", "-am", "feature modifies"], cwd=repo)

    run(["git", "checkout", "-q", "main"], cwd=repo)
    run(["git", "rm", "-q", file_path], cwd=repo)
    run(["git", "commit", "-qm", "main deletes"], cwd=repo)

    merge_result = run(["git", "merge", "feature"], cwd=repo, check=False)
    assert merge_result.returncode != 0

    return repo


def init_add_add_conflict_repo(tmp_path: Path, file_path: str = "f.txt") -> Path:
    """Merge conflict where both branches add the same path with different content."""
    repo = tmp_path / "repo_add_add_conflict"
    repo.mkdir()

    run(["git", "init", "-q"], cwd=repo)
    run(["git", "config", "user.name", "Test User"], cwd=repo)
    run(["git", "config", "user.email", "test@example.com"], cwd=repo)

    (repo / "base.txt").write_text("base\n", encoding="utf-8")
    run(["git", "add", "base.txt"], cwd=repo)
    run(["git", "commit", "-qm", "base"], cwd=repo)

    run(["git", "checkout", "-qb", "feature"], cwd=repo)
    (repo / file_path).write_text("feature content\n", encoding="utf-8")
    run(["git", "add", file_path], cwd=repo)
    run(["git", "commit", "-qm", "feature adds file"], cwd=repo)

    run(["git", "checkout", "-q", "main"], cwd=repo)
    (repo / file_path).write_text("main content\n", encoding="utf-8")
    run(["git", "add", file_path], cwd=repo)
    run(["git", "commit", "-qm", "main adds file"], cwd=repo)

    merge_result = run(["git", "merge", "feature"], cwd=repo, check=False)
    assert merge_result.returncode != 0

    return repo


def test_remerge_applies_clean_resolution_from_edited_files(tmp_path):
    repo = init_conflicted_repo(tmp_path)

    extract = run([str(SCRIPT_PATH), "--tool-extract", "f.txt"], cwd=repo)
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
            "--tool-remerge",
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

    extract = run([str(SCRIPT_PATH), "--tool-extract", "f.txt"], cwd=repo)
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
            "--tool-remerge",
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


def test_extract_handles_conflicted_file_paths_with_spaces(tmp_path):
    file_path = "dir with spaces/f name.txt"
    repo = init_conflicted_repo(tmp_path, file_path=file_path)

    extract = run([str(SCRIPT_PATH), "--tool-extract", file_path], cwd=repo, check=False)
    assert extract.returncode == 0, extract.stdout + extract.stderr

    files = json.loads(extract.stdout)
    expected_ours = run(["git", "show", f":2:{file_path}"], cwd=repo).stdout
    expected_base = run(["git", "show", f":1:{file_path}"], cwd=repo).stdout
    expected_theirs = run(["git", "show", f":3:{file_path}"], cwd=repo).stdout

    assert Path(files["ours"]).read_text(encoding="utf-8") == expected_ours
    assert Path(files["base"]).read_text(encoding="utf-8") == expected_base
    assert Path(files["theirs"]).read_text(encoding="utf-8") == expected_theirs


def test_extract_handles_modify_delete_conflict_with_missing_ours_stage(tmp_path):
    repo = init_modify_delete_conflict_repo(tmp_path)

    extract = run([str(SCRIPT_PATH), "--tool-extract", "f.txt"], cwd=repo, check=False)
    assert extract.returncode == 0, extract.stdout + extract.stderr

    files = json.loads(extract.stdout)
    assert Path(files["ours"]).read_text(encoding="utf-8") == ""
    assert Path(files["base"]).read_text(encoding="utf-8") == run(
        ["git", "show", ":1:f.txt"], cwd=repo
    ).stdout
    assert Path(files["theirs"]).read_text(encoding="utf-8") == run(
        ["git", "show", ":3:f.txt"], cwd=repo
    ).stdout


def test_extract_handles_add_add_conflict_with_missing_base_stage(tmp_path):
    repo = init_add_add_conflict_repo(tmp_path)

    extract = run([str(SCRIPT_PATH), "--tool-extract", "f.txt"], cwd=repo, check=False)
    assert extract.returncode == 0, extract.stdout + extract.stderr

    files = json.loads(extract.stdout)
    assert Path(files["base"]).read_text(encoding="utf-8") == ""
    assert Path(files["ours"]).read_text(encoding="utf-8") == run(
        ["git", "show", ":2:f.txt"], cwd=repo
    ).stdout
    assert Path(files["theirs"]).read_text(encoding="utf-8") == run(
        ["git", "show", ":3:f.txt"], cwd=repo
    ).stdout


def test_remerge_json_reports_still_conflicted_status(tmp_path):
    repo = init_conflicted_repo(tmp_path)

    extract = run([str(SCRIPT_PATH), "--tool-extract", "f.txt"], cwd=repo)
    files = json.loads(extract.stdout)

    ours_path = Path(files["ours"])
    base_path = Path(files["base"])
    theirs_path = Path(files["theirs"])

    ours_path.write_text("line1\nmanual ours\n", encoding="utf-8")
    theirs_path.write_text("line1\nmanual theirs\n", encoding="utf-8")

    remerge = run(
        [
            str(SCRIPT_PATH),
            "--tool-remerge",
            "f.txt",
            str(ours_path),
            str(base_path),
            str(theirs_path),
        ],
        cwd=repo,
        check=False,
    )
    assert remerge.returncode == 1

    payload = json.loads(remerge.stdout)
    assert payload["status"] == "still_conflicted"


def test_remerge_json_reports_still_conflicted_for_multi_hunk_conflicts(tmp_path):
    repo = init_multi_hunk_conflicted_repo(tmp_path)

    extract = run([str(SCRIPT_PATH), "--tool-extract", "f.txt"], cwd=repo)
    files = json.loads(extract.stdout)

    Path(files["ours"]).write_text("A\nmanual ours1\nB\nmanual ours2\nC\n", encoding="utf-8")
    Path(files["theirs"]).write_text(
        "A\nmanual theirs1\nB\nmanual theirs2\nC\n", encoding="utf-8"
    )

    remerge = run(
        [
            str(SCRIPT_PATH),
            "--tool-remerge",
            "f.txt",
            files["ours"],
            files["base"],
            files["theirs"],
        ],
        cwd=repo,
        check=False,
    )
    assert remerge.returncode == 1
    payload = json.loads(remerge.stdout)
    assert payload["status"] == "still_conflicted"


def test_default_file_mode_uses_guided_prompt_in_tty_session(tmp_path):
    repo = init_conflicted_repo(tmp_path)
    run(["git", "config", "core.editor", "true"], cwd=repo)

    master_fd, slave_fd = pty.openpty()
    proc = subprocess.Popen(
        [str(SCRIPT_PATH), "f.txt"],
        cwd=repo,
        stdin=slave_fd,
        stdout=slave_fd,
        stderr=slave_fd,
        close_fds=True,
    )
    os.close(slave_fd)

    output = b""
    deadline = time.time() + 8
    saw_prompt = False
    while time.time() < deadline:
        rlist, _, _ = select.select([master_fd], [], [], 0.2)
        if rlist:
            chunk = os.read(master_fd, 4096)
            if not chunk:
                break
            output += chunk
            if b"Choose a diff to view for 'f.txt'" in output:
                saw_prompt = True
                os.write(master_fd, b"q\n")
                break
        if proc.poll() is not None:
            break

    if saw_prompt:
        # Drain remaining output so process can exit cleanly.
        end_deadline = time.time() + 3
        while time.time() < end_deadline and proc.poll() is None:
            rlist, _, _ = select.select([master_fd], [], [], 0.2)
            if rlist:
                chunk = os.read(master_fd, 4096)
                if not chunk:
                    break
                output += chunk
    proc.wait(timeout=5)
    os.close(master_fd)

    decoded = output.decode("utf-8", errors="replace")
    assert "Conflict summary for 'f.txt':" in decoded, decoded
    assert "Choose a diff to view for 'f.txt'" in decoded, decoded
    assert "4. Retry without editing" in decoded, decoded
    assert "4. Re-merge now" not in decoded, decoded


def init_repo_with_conflict_merge_commit(tmp_path: Path) -> Path:
    """Completed merge commit that required manual conflict resolution."""
    repo = tmp_path / "repo_conflict_merge"
    repo.mkdir()

    run(["git", "init", "-q"], cwd=repo)
    run(["git", "config", "user.name", "Test User"], cwd=repo)
    run(["git", "config", "user.email", "test@example.com"], cwd=repo)

    (repo / "f.txt").write_text("line1\nline2\n", encoding="utf-8")
    run(["git", "add", "f.txt"], cwd=repo)
    run(["git", "commit", "-qm", "base"], cwd=repo)

    run(["git", "checkout", "-qb", "feature"], cwd=repo)
    (repo / "f.txt").write_text("line1\nours\n", encoding="utf-8")
    run(["git", "commit", "-am", "feature change"], cwd=repo)

    run(["git", "checkout", "-q", "main"], cwd=repo)
    (repo / "f.txt").write_text("line1\ntheirs\n", encoding="utf-8")
    run(["git", "commit", "-am", "main change"], cwd=repo)

    merge = run(["git", "merge", "feature"], cwd=repo, check=False)
    assert merge.returncode != 0
    (repo / "f.txt").write_text("line1\nresolved\n", encoding="utf-8")
    run(["git", "add", "f.txt"], cwd=repo)
    run(["git", "commit", "-qm", "manual merge resolution"], cwd=repo)

    return repo


def init_repo_with_add_add_conflict_merge_commit(tmp_path: Path) -> Path:
    """Completed merge commit from an add/add conflict with manual resolution."""
    repo = tmp_path / "repo_add_add_conflict_merge"
    repo.mkdir()

    run(["git", "init", "-q"], cwd=repo)
    run(["git", "branch", "-m", "main"], cwd=repo)
    run(["git", "config", "user.name", "Test User"], cwd=repo)
    run(["git", "config", "user.email", "test@example.com"], cwd=repo)

    (repo / "root.txt").write_text("base\n", encoding="utf-8")
    run(["git", "add", "root.txt"], cwd=repo)
    run(["git", "commit", "-qm", "base"], cwd=repo)

    run(["git", "checkout", "-qb", "feature"], cwd=repo)
    (repo / "f.txt").write_text("feature version\n", encoding="utf-8")
    run(["git", "add", "f.txt"], cwd=repo)
    run(["git", "commit", "-qm", "feature adds"], cwd=repo)

    run(["git", "checkout", "-q", "main"], cwd=repo)
    (repo / "f.txt").write_text("main version\n", encoding="utf-8")
    run(["git", "add", "f.txt"], cwd=repo)
    run(["git", "commit", "-qm", "main adds"], cwd=repo)

    merge = run(["git", "merge", "feature"], cwd=repo, check=False)
    assert merge.returncode != 0
    (repo / "f.txt").write_text("resolved\n", encoding="utf-8")
    run(["git", "add", "f.txt"], cwd=repo)
    run(["git", "commit", "-qm", "resolve add/add"], cwd=repo)
    return repo


def init_repo_with_clean_merge_commit(tmp_path: Path) -> Path:
    """Completed merge commit that is cleanly auto-mergeable."""
    repo = tmp_path / "repo_clean_merge"
    repo.mkdir()

    run(["git", "init", "-q"], cwd=repo)
    run(["git", "config", "user.name", "Test User"], cwd=repo)
    run(["git", "config", "user.email", "test@example.com"], cwd=repo)

    (repo / "f.txt").write_text("a\nb\n", encoding="utf-8")
    run(["git", "add", "f.txt"], cwd=repo)
    run(["git", "commit", "-qm", "base"], cwd=repo)

    run(["git", "checkout", "-qb", "feature"], cwd=repo)
    (repo / "f.txt").write_text("a\nb\nfeature_line\n", encoding="utf-8")
    run(["git", "commit", "-am", "feature append"], cwd=repo)

    run(["git", "checkout", "-q", "main"], cwd=repo)
    (repo / "f.txt").write_text("main_prefix\na\nb\n", encoding="utf-8")
    run(["git", "commit", "-am", "main prepend"], cwd=repo)

    run(["git", "merge", "--no-ff", "-qm", "clean merge", "feature"], cwd=repo)
    return repo


def init_repo_with_add_delete_merge_commit(tmp_path: Path) -> Path:
    """Completed merge commit with non-comparable add/delete file paths."""
    repo = tmp_path / "repo_add_delete_merge"
    repo.mkdir()

    run(["git", "init", "-q"], cwd=repo)
    run(["git", "config", "user.name", "Test User"], cwd=repo)
    run(["git", "config", "user.email", "test@example.com"], cwd=repo)

    (repo / "root.txt").write_text("base\n", encoding="utf-8")
    run(["git", "add", "root.txt"], cwd=repo)
    run(["git", "commit", "-qm", "base"], cwd=repo)

    run(["git", "checkout", "-qb", "feature"], cwd=repo)
    (repo / "only-feature.txt").write_text("feature only\n", encoding="utf-8")
    run(["git", "add", "only-feature.txt"], cwd=repo)
    run(["git", "commit", "-qm", "add feature-only file"], cwd=repo)

    run(["git", "checkout", "-q", "main"], cwd=repo)
    (repo / "only-main.txt").write_text("main only\n", encoding="utf-8")
    run(["git", "add", "only-main.txt"], cwd=repo)
    run(["git", "commit", "-qm", "add main-only file"], cwd=repo)

    run(["git", "merge", "--no-ff", "-qm", "merge feature add/delete", "feature"], cwd=repo)
    return repo


def init_repo_with_ongoing_merge_and_clean_file(tmp_path: Path) -> Path:
    """In-progress merge with one conflicted file and one clean file."""
    repo = tmp_path / "repo_ongoing_merge_clean_file"
    repo.mkdir()

    run(["git", "init", "-q"], cwd=repo)
    run(["git", "branch", "-m", "main"], cwd=repo)
    run(["git", "config", "user.name", "Test User"], cwd=repo)
    run(["git", "config", "user.email", "test@example.com"], cwd=repo)

    (repo / "clean.txt").write_text("line1\nline2\n", encoding="utf-8")
    (repo / "conflict.txt").write_text("base\n", encoding="utf-8")
    run(["git", "add", "clean.txt", "conflict.txt"], cwd=repo)
    run(["git", "commit", "-qm", "base"], cwd=repo)

    run(["git", "checkout", "-qb", "feature"], cwd=repo)
    (repo / "clean.txt").write_text("line1\nline2\nfeature_tail\n", encoding="utf-8")
    (repo / "conflict.txt").write_text("feature_version\n", encoding="utf-8")
    run(["git", "add", "clean.txt", "conflict.txt"], cwd=repo)
    run(["git", "commit", "-qm", "feature changes"], cwd=repo)

    run(["git", "checkout", "-q", "main"], cwd=repo)
    (repo / "clean.txt").write_text("main_head\nline1\nline2\n", encoding="utf-8")
    (repo / "conflict.txt").write_text("main_version\n", encoding="utf-8")
    run(["git", "add", "clean.txt", "conflict.txt"], cwd=repo)
    run(["git", "commit", "-qm", "main changes"], cwd=repo)

    merge = run(["git", "merge", "feature"], cwd=repo, check=False)
    assert merge.returncode != 0

    return repo


def init_repo_with_cherry_pick_conflict_and_clean_file(tmp_path: Path) -> Path:
    """In-progress cherry-pick with one conflicted file and one clean file."""
    repo = tmp_path / "repo_cherry_pick_clean_file"
    repo.mkdir()

    run(["git", "init", "-q"], cwd=repo)
    run(["git", "branch", "-m", "main"], cwd=repo)
    run(["git", "config", "user.name", "Test User"], cwd=repo)
    run(["git", "config", "user.email", "test@example.com"], cwd=repo)

    (repo / "clean.txt").write_text("line1\nline2\n", encoding="utf-8")
    (repo / "conflict.txt").write_text("base\n", encoding="utf-8")
    run(["git", "add", "clean.txt", "conflict.txt"], cwd=repo)
    run(["git", "commit", "-qm", "base"], cwd=repo)

    run(["git", "checkout", "-qb", "feature"], cwd=repo)
    (repo / "clean.txt").write_text("line1\nline2\nfeature_tail\n", encoding="utf-8")
    (repo / "conflict.txt").write_text("feature_version\n", encoding="utf-8")
    run(["git", "add", "clean.txt", "conflict.txt"], cwd=repo)
    run(["git", "commit", "-qm", "feature changes"], cwd=repo)
    feature_commit = run(["git", "rev-parse", "HEAD"], cwd=repo).stdout.strip()

    run(["git", "checkout", "-q", "main"], cwd=repo)
    (repo / "conflict.txt").write_text("main_version\n", encoding="utf-8")
    run(["git", "add", "conflict.txt"], cwd=repo)
    run(["git", "commit", "-qm", "main conflict change"], cwd=repo)

    cp = run(["git", "cherry-pick", feature_commit], cwd=repo, check=False)
    assert cp.returncode != 0
    return repo


def init_repo_with_cherry_pick_conflict_and_unrelated_clean_history(tmp_path: Path) -> Path:
    """Cherry-pick conflict where earlier source-branch commits changed a clean file."""
    repo = tmp_path / "repo_cherry_pick_unrelated_clean"
    repo.mkdir()

    run(["git", "init", "-q"], cwd=repo)
    run(["git", "branch", "-m", "main"], cwd=repo)
    run(["git", "config", "user.name", "Test User"], cwd=repo)
    run(["git", "config", "user.email", "test@example.com"], cwd=repo)

    (repo / "clean.txt").write_text("base_clean\n", encoding="utf-8")
    (repo / "conflict.txt").write_text("base_conflict\n", encoding="utf-8")
    run(["git", "add", "clean.txt", "conflict.txt"], cwd=repo)
    run(["git", "commit", "-qm", "base"], cwd=repo)

    run(["git", "checkout", "-qb", "feature"], cwd=repo)
    (repo / "clean.txt").write_text("feature_clean\n", encoding="utf-8")
    run(["git", "add", "clean.txt"], cwd=repo)
    run(["git", "commit", "-qm", "feature clean change"], cwd=repo)

    (repo / "conflict.txt").write_text("feature_conflict\n", encoding="utf-8")
    run(["git", "add", "conflict.txt"], cwd=repo)
    run(["git", "commit", "-qm", "feature conflict change"], cwd=repo)
    picked_commit = run(["git", "rev-parse", "HEAD"], cwd=repo).stdout.strip()

    run(["git", "checkout", "-q", "main"], cwd=repo)
    (repo / "conflict.txt").write_text("main_conflict\n", encoding="utf-8")
    run(["git", "add", "conflict.txt"], cwd=repo)
    run(["git", "commit", "-qm", "main conflict change"], cwd=repo)

    cp = run(["git", "cherry-pick", picked_commit], cwd=repo, check=False)
    assert cp.returncode != 0
    return repo


def init_repo_with_one_sided_clean_change_merge(tmp_path: Path) -> Path:
    """Completed merge where main changed f.txt but feature didn't.
    f.txt appears in git diff-tree -m (differs from feature parent) and resolves cleanly.
    Used to verify merge_tree_clean reason is returned for non-conflicting file analysis."""
    repo = tmp_path / "repo_one_sided_clean"
    repo.mkdir()

    run(["git", "init", "-q"], cwd=repo)
    run(["git", "branch", "-m", "main"], cwd=repo)
    run(["git", "config", "user.name", "Test User"], cwd=repo)
    run(["git", "config", "user.email", "test@example.com"], cwd=repo)

    (repo / "f.txt").write_text("base\n", encoding="utf-8")
    run(["git", "add", "f.txt"], cwd=repo)
    run(["git", "commit", "-qm", "base"], cwd=repo)

    run(["git", "checkout", "-qb", "feature"], cwd=repo)
    (repo / "other.txt").write_text("feature-only\n", encoding="utf-8")
    run(["git", "add", "other.txt"], cwd=repo)
    run(["git", "commit", "-qm", "feature adds other.txt"], cwd=repo)

    run(["git", "checkout", "-q", "main"], cwd=repo)
    (repo / "f.txt").write_text("changed\n", encoding="utf-8")
    run(["git", "add", "f.txt"], cwd=repo)
    run(["git", "commit", "-qm", "main changes f.txt"], cwd=repo)

    run(["git", "merge", "--no-ff", "-qm", "merge feature into main", "feature"],
        cwd=repo, check=True)
    return repo


def init_repo_with_revert_conflict_and_clean_file(tmp_path: Path) -> Path:
    """In-progress revert where one file reverts cleanly while another conflicts."""
    repo = tmp_path / "repo_revert_clean_file"
    repo.mkdir()

    run(["git", "init", "-q"], cwd=repo)
    run(["git", "branch", "-m", "main"], cwd=repo)
    run(["git", "config", "user.name", "Test User"], cwd=repo)
    run(["git", "config", "user.email", "test@example.com"], cwd=repo)

    (repo / "clean.txt").write_text("base_clean\n", encoding="utf-8")
    (repo / "conflict.txt").write_text("base_conflict\n", encoding="utf-8")
    run(["git", "add", "clean.txt", "conflict.txt"], cwd=repo)
    run(["git", "commit", "-qm", "base"], cwd=repo)

    (repo / "clean.txt").write_text("changed_clean\n", encoding="utf-8")
    (repo / "conflict.txt").write_text("changed_conflict\n", encoding="utf-8")
    run(["git", "add", "clean.txt", "conflict.txt"], cwd=repo)
    run(["git", "commit", "-qm", "target"], cwd=repo)
    revert_commit = run(["git", "rev-parse", "HEAD"], cwd=repo).stdout.strip()

    (repo / "conflict.txt").write_text("later_conflict\n", encoding="utf-8")
    run(["git", "add", "conflict.txt"], cwd=repo)
    run(["git", "commit", "-qm", "later conflict change"], cwd=repo)

    revert_result = run(["git", "revert", revert_commit], cwd=repo, check=False)
    assert revert_result.returncode != 0
    return repo


def test_audit_merge_json_reports_conflict_likely_true(tmp_path):
    repo = init_repo_with_conflict_merge_commit(tmp_path)
    commit = run(["git", "rev-parse", "HEAD"], cwd=repo).stdout.strip()

    result = run(
        [str(SCRIPT_PATH), "--commit", commit, "f.txt", "--json"],
        cwd=repo,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    assert payload["status"] == "ok"
    assert payload["conflict_likely"] is True
    assert Path(payload["resolved"]).exists()
    assert Path(payload["original_ours"]).exists()
    assert Path(payload["original_theirs"]).exists()
    assert Path(payload["original_base"]).exists()


def test_audit_merge_json_reports_conflict_likely_false(tmp_path):
    repo = init_repo_with_clean_merge_commit(tmp_path)
    commit = run(["git", "rev-parse", "HEAD"], cwd=repo).stdout.strip()

    result = run(
        [str(SCRIPT_PATH), "--commit", commit, "f.txt", "--json"],
        cwd=repo,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    assert payload["status"] == "ok"
    assert payload["conflict_likely"] is False


def test_audit_merge_json_handles_add_add_conflict_case(tmp_path):
    repo = init_repo_with_add_add_conflict_merge_commit(tmp_path)
    commit = run(["git", "rev-parse", "HEAD"], cwd=repo).stdout.strip()

    result = run(
        [str(SCRIPT_PATH), "--commit", commit, "f.txt", "--json"],
        cwd=repo,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    assert payload["status"] == "ok"
    assert payload["conflict_likely"] is True
    assert Path(payload["original_base"]).exists()
    assert Path(payload["original_base"]).read_text(encoding="utf-8") == ""


def test_commit_alias_runs_merge_audit(tmp_path):
    repo = init_repo_with_clean_merge_commit(tmp_path)
    commit = run(["git", "rev-parse", "HEAD"], cwd=repo).stdout.strip()

    result = run(
        [str(SCRIPT_PATH), "--commit", commit, "f.txt", "--json"],
        cwd=repo,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    assert payload["status"] == "ok"


def test_commit_requires_explicit_sha(tmp_path):
    repo = init_repo_with_clean_merge_commit(tmp_path)

    result = run(
        [str(SCRIPT_PATH), "--commit", "f.txt", "--json"],
        cwd=repo,
        check=False,
    )

    assert result.returncode == 1
    assert "not a merge commit" in (result.stdout + result.stderr).lower()


def test_legacy_git_diff_123_shim_forwards_to_new_command(tmp_path):
    repo = init_repo_with_clean_merge_commit(tmp_path)
    head = run(["git", "rev-parse", "HEAD"], cwd=repo).stdout.strip()
    result = run([str(LEGACY_SHIM_PATH), "--commit", head, "--json"], cwd=repo, check=False)
    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    assert payload["status"] == "ok"


def test_find_json_lists_likely_conflicted_merges(tmp_path):
    repo = init_repo_with_conflict_merge_commit(tmp_path)
    head = run(["git", "rev-parse", "HEAD"], cwd=repo).stdout.strip()

    result = run([str(SCRIPT_PATH), "--find", "--json"], cwd=repo, check=False)
    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    assert payload["status"] == "ok"
    matches = [m for m in payload["merges"] if m["commit"] == head]
    assert matches, payload
    assert matches[0]["conflict_likely"] is True


def test_find_commit_json_lists_file_conflict_likelihood(tmp_path):
    repo = init_repo_with_conflict_merge_commit(tmp_path)
    head = run(["git", "rev-parse", "HEAD"], cwd=repo).stdout.strip()

    result = run([str(SCRIPT_PATH), "--find", "--commit", head, "--json"], cwd=repo, check=False)
    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    assert payload["status"] == "ok"
    assert payload["commit"] == head
    files = {entry["file"]: entry for entry in payload["files"]}
    assert "f.txt" in files
    assert files["f.txt"]["conflict_likely"] is True


def test_find_commit_json_handles_multi_hunk_merge_file_conflicts(tmp_path):
    repo = init_multi_hunk_conflicted_repo(tmp_path)
    (repo / "f.txt").write_text("A\nresolved1\nB\nresolved2\nC\n", encoding="utf-8")
    run(["git", "add", "f.txt"], cwd=repo)
    run(["git", "commit", "-qm", "manual merge resolution"], cwd=repo)
    head = run(["git", "rev-parse", "HEAD"], cwd=repo).stdout.strip()

    result = run([str(SCRIPT_PATH), "--find", "--commit", head, "--json"], cwd=repo, check=False)
    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    files = {entry["file"]: entry for entry in payload["files"]}
    assert files["f.txt"]["conflict_likely"] is True
    assert files["f.txt"]["reason"] == "merge_tree_conflict"


def test_find_supports_git_log_filter_passthrough(tmp_path):
    repo = init_repo_with_conflict_merge_commit(tmp_path)
    head = run(["git", "rev-parse", "HEAD"], cwd=repo).stdout.strip()

    result = run(
        [str(SCRIPT_PATH), "--find", "--json", "--", "--grep=manual merge resolution"],
        cwd=repo,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    commits = [m["commit"] for m in payload["merges"]]
    assert commits == [head]


def test_find_accepts_file_before_find_flag(tmp_path):
    repo = init_repo_with_conflict_merge_commit(tmp_path)
    result = run(
        [str(SCRIPT_PATH), "f.txt", "--find", "--json", "--", "--grep=manual merge resolution"],
        cwd=repo,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    assert payload["status"] == "ok"
    assert len(payload["merges"]) == 1


def test_commit_with_only_sha_runs_merge_summary_mode(tmp_path):
    repo = init_repo_with_conflict_merge_commit(tmp_path)
    head = run(["git", "rev-parse", "HEAD"], cwd=repo).stdout.strip()

    result = run([str(SCRIPT_PATH), "--commit", head, "--json"], cwd=repo, check=False)
    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    assert payload["status"] == "ok"
    assert payload["commit"] == head
    assert isinstance(payload["files"], list)


def test_default_mode_missing_file_has_clear_not_found_error(tmp_path):
    repo = init_repo_with_clean_merge_commit(tmp_path)

    result = run([str(SCRIPT_PATH), "does-not-exist.txt"], cwd=repo, check=False)
    assert result.returncode == 1
    assert "not found" in result.stdout.lower() or "not found" in result.stderr.lower()


def test_find_does_not_leak_git_show_fatal_errors(tmp_path):
    repo = init_repo_with_add_delete_merge_commit(tmp_path)
    result = run([str(SCRIPT_PATH), "--find"], cwd=repo, check=False)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "fatal: path" not in result.stderr.lower()
    assert "likely_clean" in result.stdout


def test_find_json_does_not_leak_git_errors_to_stderr_outside_repo(tmp_path):
    workdir = tmp_path / "outside_repo"
    workdir.mkdir()
    result = run([str(SCRIPT_PATH), "--find", "--json"], cwd=workdir, check=False)
    assert result.returncode == 1
    payload = json.loads(result.stdout)
    assert payload["status"] == "error"
    assert result.stderr.strip() == ""


def test_commit_summary_json_reports_add_delete_files_as_clean(tmp_path):
    repo = init_repo_with_add_delete_merge_commit(tmp_path)
    head = run(["git", "rev-parse", "HEAD"], cwd=repo).stdout.strip()

    result = run([str(SCRIPT_PATH), "--commit", head, "--json"], cwd=repo, check=False)
    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    assert payload["status"] == "ok"
    # Files added by only one side (add/delete) are cleanly resolved by git merge-tree
    reasons = {entry.get("reason") for entry in payload["files"]}
    assert reasons == {"merge_tree_clean"}


def test_audit_merge_allows_missing_side_file_for_review(tmp_path):
    repo = init_repo_with_add_delete_merge_commit(tmp_path)
    head = run(["git", "rev-parse", "HEAD"], cwd=repo).stdout.strip()

    result = run(
        [str(SCRIPT_PATH), "--commit", head, "only-main.txt", "--json"],
        cwd=repo,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    assert payload["status"] == "ok"
    assert payload["conflict_likely"] is False
    assert payload["reason"] == "merge_tree_clean"
    assert Path(payload["resolved"]).exists()
    assert Path(payload["original_ours"]).read_text(encoding="utf-8") == "main only\n"
    assert Path(payload["original_base"]).read_text(encoding="utf-8") == ""
    assert Path(payload["original_theirs"]).read_text(encoding="utf-8") == ""


def test_commit_summary_text_groups_statuses_prettily(tmp_path):
    repo = init_repo_with_add_delete_merge_commit(tmp_path)
    head = run(["git", "rev-parse", "HEAD"], cwd=repo).stdout.strip()

    result = run([str(SCRIPT_PATH), "--commit", head], cwd=repo, check=False)
    assert result.returncode == 0, result.stdout + result.stderr
    text = result.stdout
    assert "likely_clean:" in text
    assert "  - " in text or "  + " in text or "  ~ " in text


def test_find_text_marks_clean_for_add_delete_merge(tmp_path):
    repo = init_repo_with_add_delete_merge_commit(tmp_path)
    result = run([str(SCRIPT_PATH), "--find"], cwd=repo, check=False)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "likely_clean" in result.stdout


def test_color_always_adds_ansi_sequences_in_text_mode(tmp_path):
    repo = init_repo_with_add_delete_merge_commit(tmp_path)
    head = run(["git", "rev-parse", "HEAD"], cwd=repo).stdout.strip()
    result = run([str(SCRIPT_PATH), "--color=always", "--commit", head], cwd=repo, check=False)
    assert result.returncode == 0, result.stdout + result.stderr
    assert "\x1b[" in result.stdout


def test_no_color_overrides_color_always(tmp_path):
    repo = init_repo_with_add_delete_merge_commit(tmp_path)
    head = run(["git", "rev-parse", "HEAD"], cwd=repo).stdout.strip()
    result = run(
        [str(SCRIPT_PATH), "--color=always", "--no-color", "--commit", head],
        cwd=repo,
        check=False,
    )
    assert result.returncode == 0, result.stdout + result.stderr
    assert "\x1b[" not in result.stdout


def init_repo_with_octopus_merge_commit(tmp_path: Path) -> Path:
    """Completed octopus merge (3+ parents) for multi-parent handling tests."""
    repo = tmp_path / "repo_octopus_merge"
    repo.mkdir()

    run(["git", "init", "-q"], cwd=repo)
    run(["git", "branch", "-m", "main"], cwd=repo)
    run(["git", "config", "user.name", "Test User"], cwd=repo)
    run(["git", "config", "user.email", "test@example.com"], cwd=repo)

    (repo / "base.txt").write_text("base\n", encoding="utf-8")
    run(["git", "add", "base.txt"], cwd=repo)
    run(["git", "commit", "-qm", "base"], cwd=repo)

    run(["git", "checkout", "-qb", "b1"], cwd=repo)
    (repo / "f1.txt").write_text("b1\n", encoding="utf-8")
    run(["git", "add", "f1.txt"], cwd=repo)
    run(["git", "commit", "-qm", "b1"], cwd=repo)

    run(["git", "checkout", "-q", "main"], cwd=repo)
    run(["git", "checkout", "-qb", "b2"], cwd=repo)
    (repo / "f2.txt").write_text("b2\n", encoding="utf-8")
    run(["git", "add", "f2.txt"], cwd=repo)
    run(["git", "commit", "-qm", "b2"], cwd=repo)

    run(["git", "checkout", "-q", "main"], cwd=repo)
    run(["git", "checkout", "-qb", "b3"], cwd=repo)
    (repo / "f3.txt").write_text("b3\n", encoding="utf-8")
    run(["git", "add", "f3.txt"], cwd=repo)
    run(["git", "commit", "-qm", "b3"], cwd=repo)

    run(["git", "checkout", "-q", "main"], cwd=repo)
    run(["git", "merge", "--no-ff", "-qm", "octopus merge", "b1", "b2", "b3"], cwd=repo)
    return repo


def test_find_commit_json_marks_octopus_merges_non_comparable(tmp_path):
    repo = init_repo_with_octopus_merge_commit(tmp_path)
    head = run(["git", "rev-parse", "HEAD"], cwd=repo).stdout.strip()

    result = run([str(SCRIPT_PATH), "--find", "--commit", head, "--json"], cwd=repo, check=False)
    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    assert payload["status"] == "ok"
    assert payload["files"], payload
    assert all(entry["status"] == "non_comparable" for entry in payload["files"])
    assert all(
        entry["reason"] == "unsupported_multi_parent_merge"
        for entry in payload["files"]
    )


def test_commit_file_audit_rejects_octopus_merge(tmp_path):
    repo = init_repo_with_octopus_merge_commit(tmp_path)
    head = run(["git", "rev-parse", "HEAD"], cwd=repo).stdout.strip()

    result = run([str(SCRIPT_PATH), "--commit", head, "f1.txt", "--json"], cwd=repo, check=False)
    assert result.returncode == 1
    payload = json.loads(result.stdout)
    assert payload["status"] == "error"
    assert "only supports 2-parent merge commits" in payload["message"].lower()


def test_find_missing_commit_value_exits_non_zero(tmp_path):
    repo = init_repo_with_clean_merge_commit(tmp_path)
    result = run([str(SCRIPT_PATH), "--find", "--commit"], cwd=repo, check=False)
    assert result.returncode == 1
    assert "USAGE:" in result.stdout


def test_tool_extract_missing_file_arg_exits_non_zero(tmp_path):
    repo = init_repo_with_clean_merge_commit(tmp_path)
    result = run([str(SCRIPT_PATH), "--tool-extract"], cwd=repo, check=False)
    assert result.returncode == 1
    assert "USAGE:" in result.stdout


def test_non_interactive_default_mode_exits_non_zero_when_not_resolved(tmp_path):
    repo = init_conflicted_repo(tmp_path)
    result = run([str(SCRIPT_PATH), "f.txt"], cwd=repo, check=False)
    assert result.returncode == 1
    assert "Aborted without applying resolution." in result.stdout


def test_default_mode_allows_clean_file_during_active_merge(tmp_path):
    repo = init_repo_with_ongoing_merge_and_clean_file(tmp_path)
    result = run([str(SCRIPT_PATH), "clean.txt"], cwd=repo, check=False)
    assert result.returncode == 1
    assert "not in a merge conflict state" not in result.stdout
    assert "Starting guided 3-way merge resolution..." in result.stdout


def test_default_mode_allows_clean_file_during_active_cherry_pick(tmp_path):
    repo = init_repo_with_cherry_pick_conflict_and_clean_file(tmp_path)
    result = run([str(SCRIPT_PATH), "clean.txt"], cwd=repo, check=False)
    assert result.returncode == 1
    assert "not in a merge conflict state" not in result.stdout
    assert "Starting guided 3-way merge resolution..." in result.stdout


def test_cherry_pick_clean_file_extract_ignores_unrelated_earlier_branch_changes(tmp_path):
    repo = init_repo_with_cherry_pick_conflict_and_unrelated_clean_history(tmp_path)
    before_clean = (repo / "clean.txt").read_text(encoding="utf-8")

    extract = run([str(SCRIPT_PATH), "--tool-extract", "clean.txt"], cwd=repo)
    files = json.loads(extract.stdout)
    assert Path(files["base"]).read_text(encoding="utf-8") == "feature_clean\n"

    remerge = run(
        [
            str(SCRIPT_PATH),
            "--tool-remerge",
            "clean.txt",
            files["ours"],
            files["base"],
            files["theirs"],
        ],
        cwd=repo,
        check=False,
    )
    assert remerge.returncode == 0, remerge.stdout + remerge.stderr
    assert (repo / "clean.txt").read_text(encoding="utf-8") == before_clean
    staged = run(["git", "diff", "--cached", "--name-only"], cwd=repo).stdout.splitlines()
    assert "clean.txt" not in staged


def test_revert_clean_file_extract_models_reverse_patch_direction(tmp_path):
    repo = init_repo_with_revert_conflict_and_clean_file(tmp_path)

    extract = run([str(SCRIPT_PATH), "--tool-extract", "clean.txt"], cwd=repo)
    files = json.loads(extract.stdout)

    assert Path(files["ours"]).read_text(encoding="utf-8") == "changed_clean\n"
    assert Path(files["base"]).read_text(encoding="utf-8") == "changed_clean\n"
    assert Path(files["theirs"]).read_text(encoding="utf-8") == "base_clean\n"


def test_merge_tree_returns_clean_reason_for_non_conflicting_file(tmp_path):
    repo = init_repo_with_one_sided_clean_change_merge(tmp_path)
    head = run(["git", "rev-parse", "HEAD"], cwd=repo).stdout.strip()

    result = run([str(SCRIPT_PATH), "--find", "--commit", head, "--json"], cwd=repo, check=False)
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    files = {entry["file"]: entry for entry in payload["files"]}
    assert "f.txt" in files
    assert files["f.txt"]["conflict_likely"] is False
    assert files["f.txt"]["reason"] == "merge_tree_clean"


def test_default_mode_can_target_file_named_help(tmp_path):
    repo = tmp_path / "repo_help_filename"
    repo.mkdir()

    run(["git", "init", "-q"], cwd=repo)
    run(["git", "branch", "-m", "main"], cwd=repo)
    run(["git", "config", "user.name", "Test User"], cwd=repo)
    run(["git", "config", "user.email", "test@example.com"], cwd=repo)

    file_path = "--help"
    (repo / file_path).write_text("base\n", encoding="utf-8")
    run(["git", "add", "--", file_path], cwd=repo)
    run(["git", "commit", "-qm", "base"], cwd=repo)

    run(["git", "checkout", "-qb", "feature"], cwd=repo)
    (repo / file_path).write_text("feature\n", encoding="utf-8")
    run(["git", "add", "--", file_path], cwd=repo)
    run(["git", "commit", "-qm", "feature"], cwd=repo)

    run(["git", "checkout", "-q", "main"], cwd=repo)
    (repo / file_path).write_text("main\n", encoding="utf-8")
    run(["git", "add", "--", file_path], cwd=repo)
    run(["git", "commit", "-qm", "main"], cwd=repo)

    merge_result = run(["git", "merge", "feature"], cwd=repo, check=False)
    assert merge_result.returncode != 0

    result = run([str(SCRIPT_PATH), "--", file_path], cwd=repo, check=False)
    assert result.returncode == 1
    assert "Starting guided 3-way merge resolution..." in result.stdout
    assert "USAGE:" not in result.stdout


def test_default_mode_can_target_file_named_json_flag(tmp_path):
    repo = tmp_path / "repo_json_filename"
    repo.mkdir()

    run(["git", "init", "-q"], cwd=repo)
    run(["git", "branch", "-m", "main"], cwd=repo)
    run(["git", "config", "user.name", "Test User"], cwd=repo)
    run(["git", "config", "user.email", "test@example.com"], cwd=repo)

    file_path = "--json"
    (repo / file_path).write_text("base\n", encoding="utf-8")
    run(["git", "add", "--", file_path], cwd=repo)
    run(["git", "commit", "-qm", "base"], cwd=repo)

    run(["git", "checkout", "-qb", "feature"], cwd=repo)
    (repo / file_path).write_text("feature\n", encoding="utf-8")
    run(["git", "add", "--", file_path], cwd=repo)
    run(["git", "commit", "-qm", "feature"], cwd=repo)

    run(["git", "checkout", "-q", "main"], cwd=repo)
    (repo / file_path).write_text("main\n", encoding="utf-8")
    run(["git", "add", "--", file_path], cwd=repo)
    run(["git", "commit", "-qm", "main"], cwd=repo)

    merge_result = run(["git", "merge", "feature"], cwd=repo, check=False)
    assert merge_result.returncode != 0

    result = run([str(SCRIPT_PATH), "--", file_path], cwd=repo, check=False)
    assert result.returncode == 1
    assert "Starting guided 3-way merge resolution..." in result.stdout
    assert "USAGE:" not in result.stdout


def test_default_mode_can_target_file_named_dry_run_flag(tmp_path):
    repo = tmp_path / "repo_dry_run_filename"
    repo.mkdir()

    run(["git", "init", "-q"], cwd=repo)
    run(["git", "branch", "-m", "main"], cwd=repo)
    run(["git", "config", "user.name", "Test User"], cwd=repo)
    run(["git", "config", "user.email", "test@example.com"], cwd=repo)

    file_path = "--dry-run"
    (repo / file_path).write_text("base\n", encoding="utf-8")
    run(["git", "add", "--", file_path], cwd=repo)
    run(["git", "commit", "-qm", "base"], cwd=repo)

    run(["git", "checkout", "-qb", "feature"], cwd=repo)
    (repo / file_path).write_text("feature\n", encoding="utf-8")
    run(["git", "add", "--", file_path], cwd=repo)
    run(["git", "commit", "-qm", "feature"], cwd=repo)

    run(["git", "checkout", "-q", "main"], cwd=repo)
    (repo / file_path).write_text("main\n", encoding="utf-8")
    run(["git", "add", "--", file_path], cwd=repo)
    run(["git", "commit", "-qm", "main"], cwd=repo)

    merge_result = run(["git", "merge", "feature"], cwd=repo, check=False)
    assert merge_result.returncode != 0

    result = run([str(SCRIPT_PATH), "--", file_path], cwd=repo, check=False)
    assert result.returncode == 1
    assert "Starting guided 3-way merge resolution..." in result.stdout
    assert "USAGE:" not in result.stdout
