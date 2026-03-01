# Merge-Tree Conflict Detection Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Replace `git merge-file` with `git merge-tree --write-tree` in `conflict_likely_for_merge_file` so that conflict predictions match what `git merge` actually does, eliminating false conflicts from identical net changes and criss-cross histories.

**Architecture:** Add `merge_tree_conflicts_for_commit(parent1, parent2)` helper that runs `git merge-tree --write-tree --name-only` once and returns a `Set` of conflicting filenames. A module-level constant cache (`MERGE_TREE_CACHE`) ensures it's called at most once per unique (parent1, parent2) pair across the whole process. `conflict_likely_for_merge_file` becomes a thin wrapper around this helper.

> **Implementation note:** The helper signature and cache key were simplified from `(parent1, parent2, base)` to `(parent1, parent2)` during implementation. Passing `--merge-base=BASE` to `git merge-tree` bypasses its recursive virtual merge-base construction for criss-cross histories — the primary advantage of merge-tree over merge-file. Omitting the flag lets git compute the correct merge base automatically.

**Tech Stack:** Ruby (existing script), `git merge-tree --write-tree` (Git ≥ 2.38, confirmed available at 2.53.0), Ruby `Set` stdlib.

---

### Task 1: Add `merge_tree_conflicts_for_commit` helper (TDD)

**Files:**
- Modify: `git-resolve-conflict` (add `require 'set'` at top, add helper after `get_merge_base`)
- Test: `test_git_diff_123.py`

**Context:** `git merge-tree --write-tree --merge-base=BASE --name-only PARENT1 PARENT2` stdout format on conflict (exit 1):
```
<tree-sha>        ← line 1, always present
f.txt             ← conflicting filenames, one per line, until blank line
                  ← blank line
Auto-merging f.txt
CONFLICT (content): Merge conflict in f.txt
```
On clean (exit 0): single line with tree SHA, no filenames.

**Step 1: Write the failing test**

Add this test to `test_git_diff_123.py` after the existing import block. It exercises the helper indirectly through `--find --commit`:

```python
def init_repo_with_identical_net_change_merge(tmp_path: Path) -> Path:
    """Merge where both parents changed the same line to the same value.
    git merge-file sees this as a potential conflict depending on patch context,
    but git merge-tree handles it correctly as clean."""
    repo = tmp_path / "repo_identical_net_change"
    repo.mkdir()

    run(["git", "init", "-q"], cwd=repo)
    run(["git", "branch", "-m", "main"], cwd=repo)
    run(["git", "config", "user.name", "Test User"], cwd=repo)
    run(["git", "config", "user.email", "test@example.com"], cwd=repo)

    (repo / "f.txt").write_text("base\n", encoding="utf-8")
    run(["git", "add", "f.txt"], cwd=repo)
    run(["git", "commit", "-qm", "base"], cwd=repo)
    base_sha = run(["git", "rev-parse", "HEAD"], cwd=repo).stdout.strip()

    run(["git", "checkout", "-qb", "feature"], cwd=repo)
    (repo / "f.txt").write_text("resolved\n", encoding="utf-8")
    run(["git", "add", "f.txt"], cwd=repo)
    run(["git", "commit", "-qm", "feature: resolve"], cwd=repo)

    run(["git", "checkout", "-q", "main"], cwd=repo)
    (repo / "f.txt").write_text("resolved\n", encoding="utf-8")
    run(["git", "add", "f.txt"], cwd=repo)
    run(["git", "commit", "-qm", "main: resolve"], cwd=repo)

    # Merge: both sides made the same change. Git merge handles this cleanly.
    run(["git", "merge", "--no-ff", "-qm", "merge identical changes", "feature"],
        cwd=repo, check=True)
    return repo


def test_merge_tree_detects_identical_net_change_as_clean(tmp_path):
    repo = init_repo_with_identical_net_change_merge(tmp_path)
    head = run(["git", "rev-parse", "HEAD"], cwd=repo).stdout.strip()

    result = run([str(SCRIPT_PATH), "--find", "--commit", head, "--json"], cwd=repo, check=False)
    assert result.returncode == 0, result.stderr
    payload = json.loads(result.stdout)
    files = {entry["file"]: entry for entry in payload["files"]}
    assert "f.txt" in files
    assert files["f.txt"]["conflict_likely"] is False
    assert files["f.txt"]["reason"] == "merge_tree_clean"
```

**Step 2: Run test to verify it fails**

```bash
cd /Users/jimmyyan/work/02-git-scripts
pytest test_git_diff_123.py::test_merge_tree_detects_identical_net_change_as_clean -v
```

Expected: FAIL (reason will be `merge_file_clean` not `merge_tree_clean`, or the repo fixture fails to build).

**Step 3: Add `require 'set'` and the helper to `git-resolve-conflict`**

At the top of the file, add `require 'set'` after the existing requires:
```ruby
require 'set'
```

After `get_merge_base` (currently line 135), add:

```ruby
# Module-level cache: keyed by "parent1:parent2:base" → Set of conflicting filenames (or nil on error).
MERGE_TREE_CACHE = {}

# Runs `git merge-tree --write-tree --name-only` once per unique (parent1, parent2, base) triple.
# Returns:
#   Set[]            — clean merge (no conflicts)
#   Set["a.txt", …] — conflict, with the listed files having conflict markers
#   nil              — git internal error (exit 2+), treat as non_comparable
def merge_tree_conflicts_for_commit(parent1, parent2, base)
  cache_key = "#{parent1}:#{parent2}:#{base}"
  return MERGE_TREE_CACHE[cache_key] if MERGE_TREE_CACHE.key?(cache_key)

  out, _err, status = Open3.capture3(
    "git", "merge-tree", "--write-tree", "--merge-base=#{base}", "--name-only",
    parent1, parent2
  )

  result = case status.exitstatus
           when 0
             Set.new
           when 1
             # stdout: line 1 = tree SHA, lines 2..blank = conflicting filenames
             lines = out.lines.map(&:chomp)
             filenames = lines.drop(1).take_while { |l| !l.empty? }
             Set.new(filenames)
           else
             nil
           end

  MERGE_TREE_CACHE[cache_key] = result
  result
end
```

**Step 4: Run test again**

```bash
pytest test_git_diff_123.py::test_merge_tree_detects_identical_net_change_as_clean -v
```

Expected: FAIL still — `conflict_likely_for_merge_file` still uses `git merge-file`. That's correct; we haven't wired it up yet.

**Step 5: Commit the helper alone**

```bash
just pre-commit
git add git-resolve-conflict test_git_diff_123.py
git commit -m "feat(resolve-conflict): add merge_tree_conflicts_for_commit helper with cache"
```

---

### Task 2: Replace `conflict_likely_for_merge_file` body with merge-tree lookup

**Files:**
- Modify: `git-resolve-conflict` (lines ~566–626)

**Context:** Current function (~60 lines) manually handles add/add same-content, missing-in-*, and runs `git merge-file`. All of these are handled natively by `git merge-tree`. The new version keeps the 2-parent guard and merge-base guard; everything else is replaced.

**Step 1: Replace the function body**

Replace the content of `conflict_likely_for_merge_file` (keep the signature):

```ruby
def conflict_likely_for_merge_file(commit, file)
  parents = get_merge_commit_parents(commit)
  return { "conflict_likely" => nil, "status" => "non_comparable", "reason" => "not_a_merge_commit" } unless parents
  if parents.length != 2
    return { "conflict_likely" => nil, "status" => "non_comparable", "reason" => "unsupported_multi_parent_merge" }
  end

  parent1, parent2 = parents
  base = get_merge_base(parent1, parent2)
  if base.empty?
    return { "conflict_likely" => nil, "status" => "non_comparable", "reason" => "missing_merge_base" }
  end

  conflict_set = merge_tree_conflicts_for_commit(parent1, parent2, base)
  if conflict_set.nil?
    return { "conflict_likely" => nil, "status" => "non_comparable", "reason" => "merge_tree_error" }
  end

  if conflict_set.include?(file)
    { "conflict_likely" => true, "status" => "likely_conflict", "reason" => "merge_tree_conflict" }
  else
    { "conflict_likely" => false, "status" => "likely_clean", "reason" => "merge_tree_clean" }
  end
end
```

**Step 2: Run the new test**

```bash
pytest test_git_diff_123.py::test_merge_tree_detects_identical_net_change_as_clean -v
```

Expected: PASS.

**Step 3: Run full test suite to see what breaks**

```bash
pytest test_git_diff_123.py -v 2>&1 | grep -E "PASSED|FAILED|ERROR"
```

Expected failures (reason strings changed):
- `test_find_commit_json_handles_multi_hunk_merge_file_conflicts` — expects `"merge_file_conflict"`
- `test_commit_summary_json_includes_non_comparable_reason` — expects `missing_in_*` reason
- `test_audit_merge_allows_missing_side_file_for_review` — expects `"missing_in_theirs_base"` reason

**Step 4: Update `audit_merge` to remove the `missing_in_*` special-case guard**

In `audit_merge`, find the block that reads:
```ruby
if analysis["conflict_likely"].nil? && !(analysis["reason"] || "").start_with?("missing_in_")
```

Replace with:
```ruby
if analysis["conflict_likely"].nil?
```

(The `missing_in_*` exception was needed when those cases were non_comparable; now they're properly resolved by merge-tree.)

**Step 5: Commit the implementation**

```bash
just pre-commit
git add git-resolve-conflict
git commit -m "feat(resolve-conflict): replace git merge-file with git merge-tree in conflict_likely_for_merge_file

Fixes issue #3. git merge-tree uses the same algorithm as git merge, eliminating
false conflicts from identical net changes and criss-cross histories. The
merge_tree_conflicts_for_commit helper is called at most once per (p1, p2, base)
triple via MERGE_TREE_CACHE, so multi-file commits pay only one subprocess per commit.

add/add same-content, modify/delete, and missing-in-* cases that were previously
non_comparable are now correctly classified as merge_tree_clean or merge_tree_conflict."
```

---

### Task 3: Update existing tests for renamed reason strings

**Files:**
- Modify: `test_git_diff_123.py`

**Context:** Three tests assert on the old reason strings or the now-gone `non_comparable` behavior for add/delete files.

**Step 1: Fix `test_find_commit_json_handles_multi_hunk_merge_file_conflicts`**

Line ~747: change:
```python
assert files["f.txt"]["reason"] == "merge_file_conflict"
```
to:
```python
assert files["f.txt"]["reason"] == "merge_tree_conflict"
```

**Step 2: Fix `test_commit_summary_json_includes_non_comparable_reason`**

This test uses `init_repo_with_add_delete_merge_commit`. With `git merge-tree`, both `only-main.txt` (added by main, not by feature) and `only-feature.txt` (added by feature, not by main) are cleanly resolved — they're now `merge_tree_clean`, not `non_comparable`. Update the test to reflect correct behavior:

```python
def test_commit_summary_json_reports_add_delete_files_as_clean(tmp_path):
    repo = init_repo_with_add_delete_merge_commit(tmp_path)
    head = run(["git", "rev-parse", "HEAD"], cwd=repo).stdout.strip()

    result = run([str(SCRIPT_PATH), "--commit", head, "--json"], cwd=repo, check=False)
    assert result.returncode == 0, result.stdout + result.stderr
    payload = json.loads(result.stdout)
    assert payload["status"] == "ok"
    # Files that were only added by one side are cleanly resolved by git merge-tree
    reasons = {entry.get("reason") for entry in payload["files"]}
    assert reasons == {"merge_tree_clean"}
```

(Rename the test function from `test_commit_summary_json_includes_non_comparable_reason` to `test_commit_summary_json_reports_add_delete_files_as_clean`.)

**Step 3: Fix `test_audit_merge_allows_missing_side_file_for_review`**

Lines ~841-842: change:
```python
assert payload["conflict_likely"] is False
assert payload["reason"] == "missing_in_theirs_base"
```
to:
```python
assert payload["conflict_likely"] is False
assert payload["reason"] == "merge_tree_clean"
```

(`conflict_likely is False` stays — merge-tree still correctly identifies this as clean.)

**Step 4: Run full test suite**

```bash
pytest test_git_diff_123.py -v
```

Expected: all 42 tests pass (41 previous + 1 new).

**Step 5: Commit**

```bash
just pre-commit
git add test_git_diff_123.py
git commit -m "test(resolve-conflict): update reason assertions for merge-tree rename

merge_file_clean/conflict → merge_tree_clean/conflict.
Add/delete files are now merge_tree_clean (not non_comparable)."
```

---

### Task 4: Final verification and PR

**Step 1: Run full test suite one more time**

```bash
pytest test_git_diff_123.py -q
```

Expected: all tests pass, 0 failures.

**Step 2: Smoke-test the CLI on a real conflicted merge commit**

```bash
# In any git repo with a merge commit SHA handy:
git log --merges --oneline -5
git-resolve-conflict --find --commit <SHA> --json | python3 -m json.tool
```

Expected: JSON with `merge_tree_clean` or `merge_tree_conflict` reasons, no errors.

**Step 3: Push and open PR**

```bash
git push -u origin fix/merge-tree-conflict-detection
gh pr create \
  --title "fix: replace git merge-file with git merge-tree for conflict detection" \
  --body "Closes #3

## Summary
- Adds \`merge_tree_conflicts_for_commit\` helper using \`git merge-tree --write-tree --name-only\`
- Replaces \`git merge-file\` in \`conflict_likely_for_merge_file\` with commit-level \`merge-tree\`
- Adds per-(p1,p2,base) cache so multi-file commits pay only 1 subprocess
- Adds regression test for identical-net-change false conflict
- Updates reason strings: \`merge_file_*\` → \`merge_tree_*\`
- Add/delete-only files (previously \`non_comparable\`) now correctly reported as \`merge_tree_clean\`

## Test plan
- [ ] \`pytest test_git_diff_123.py -q\` — all tests pass
- [ ] \`git-resolve-conflict --find --commit <SHA>\` on a real merge commit — no errors"
```
