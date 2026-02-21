"""Regression tests for git-diff-123."""

import json
import os
import pty
import select
import subprocess
import time
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


def init_conflicted_repo(tmp_path: Path, file_path: str = "f.txt") -> Path:
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
    assert "Choose a diff to view for 'f.txt'" in decoded, decoded
    assert "4. Retry without editing" in decoded, decoded
    assert "4. Re-merge now" not in decoded, decoded


def init_repo_with_conflict_merge_commit(tmp_path: Path) -> Path:
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


def init_repo_with_clean_merge_commit(tmp_path: Path) -> Path:
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


def test_commit_without_hash_defaults_to_head(tmp_path):
    repo = init_repo_with_clean_merge_commit(tmp_path)

    result = run(
        [str(SCRIPT_PATH), "--commit", "f.txt", "--json"],
        cwd=repo,
        check=False,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    assert payload["status"] == "ok"
