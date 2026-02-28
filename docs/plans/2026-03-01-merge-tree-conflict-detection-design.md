# Design: Replace `git merge-file` with `git merge-tree` for conflict detection

**Date:** 2026-03-01
**Issue:** #3 — git-diff-123: avoid unnecessary 3-way merge conflict
**Branch:** fix/merge-tree-conflict-detection

## Problem

`conflict_likely_for_merge_file` uses `git merge-file` (file-level 3-way merge) to predict
conflict likelihood for merge commits. This produces false conflicts when:
- Both sides made identical net changes relative to the merge base (file-level diff algorithm
  sees the patches differently even though the outcome is the same).
- Criss-cross history: the ad-hoc merge-base selection diverges from what `git merge` would
  actually use.
- `.gitattributes` merge drivers and rename tracking are not consulted.

`git merge-tree --write-tree` uses the same algorithm as `git merge`, so its conflict
predictions match what a real merge would produce.

## Scope

Replace `git merge-file` **only** in `conflict_likely_for_merge_file` (the audit/find path).
The `remerge_from_files` function (interactive resolution) is out of scope for this PR because
it operates on manually-edited temp files, not commits — a follow-up ticket covers that path.

## Architecture

### New helper: `merge_tree_conflicts_for_commit(parent1, parent2, base)`

```
git merge-tree --write-tree --merge-base=BASE --name-only PARENT1 PARENT2
```

- **Exit 0** (clean merge): returns empty `Set[]`
- **Exit 1** (conflicts): parses stdout — skips line 1 (merged tree SHA), collects filenames
  until the first blank line → returns `Set[conflicting_filenames]`
- **Exit 2+** (git internal error): returns `nil` (callers treat as non_comparable)

Output format (conflict case):
```
<tree-sha>       ← line 1, skip
f.txt            ← conflicting files, one per line
                 ← blank line separator
Auto-merging f.txt
CONFLICT (content): Merge conflict in f.txt
```

### Simplified `conflict_likely_for_merge_file(commit, file)`

Replaces the current ~60-line function that manually handles add/add, missing-in-*, and
file-level extraction. New flow:

1. Get parents → `non_comparable: not_a_merge_commit` if not a 2-parent merge
2. Get merge-base → `non_comparable: missing_merge_base` if empty
3. Call `merge_tree_conflicts_for_commit` → `non_comparable: merge_tree_error` if nil
4. Return `likely_conflict: merge_tree_conflict` if file in conflict set,
   else `likely_clean: merge_tree_clean`

All add/add, modify/delete, and missing-in-* cases are handled natively by `git merge-tree`.

### Caching for multi-file callers

`find_merges` and `find_merge_commit_files` call `conflict_likely_for_merge_file` once per
file in a commit. Without caching, this would invoke `git merge-tree` N times per commit.

Solution: extract the merge-tree call into a batch helper. The per-file callers in these
functions directly use `merge_tree_conflicts_for_commit` (called once per commit) and
perform the file lookup inline. `conflict_likely_for_merge_file` is the single-file entry
point used by `audit_merge` (which already calls it once).

## Error Handling

| Condition | Status | Reason |
|-----------|--------|--------|
| Not a merge commit | non_comparable | not_a_merge_commit |
| 3+ parent merge | non_comparable | unsupported_multi_parent_merge |
| No merge base found | non_comparable | missing_merge_base |
| `git merge-tree` exits with code 2+ | non_comparable | merge_tree_error |
| File in conflict set | likely_conflict | merge_tree_conflict |
| File not in conflict set | likely_clean | merge_tree_clean |

## Testing

### New fixtures / tests

1. **Identical net change** (`init_repo_with_identical_net_change_merge`):
   Both parents change the same line to the same content from base. With `git merge-file`
   this would have been a false-conflict; with `merge-tree` it must return `likely_clean`.

2. **Criss-cross merge** (`init_repo_with_criss_cross_merge`):
   Diamond history where naive `git merge-base` gives wrong result. `merge-tree` uses the
   correct virtual merge base → clean result.

### Existing test updates

Tests asserting `"reason": "merge_file_clean"` or `"reason": "merge_file_conflict"` update
to `"merge_tree_clean"` / `"merge_tree_conflict"`.

## Non-Goals

- `remerge_from_files` (interactive resolution) — separate ticket
- Custom merge strategy or `.gitattributes` driver changes
- Whitespace-handling knobs (future iteration)
