# `git-resolve-conflict` test scenario map

This file explains what each repo-builder helper in `test_git_diff_123.py` simulates.

- `init_conflicted_repo`: classic 2-parent content conflict (`f.txt` differs on both branches).
- `init_modify_delete_conflict_repo`: one branch edits, the other deletes.
- `init_add_add_conflict_repo`: both branches add same path with different content.
- `init_repo_with_conflict_merge_commit`: merge conflict resolved and committed.
- `init_repo_with_add_add_conflict_merge_commit`: add/add conflict resolved and committed.
- `init_repo_with_clean_merge_commit`: clean merge commit, no manual conflict.
- `init_repo_with_add_delete_merge_commit`: merge with non-comparable add/delete paths.
- `init_repo_with_ongoing_merge_and_clean_file`: merge in progress with both conflicted and clean files.
- `init_repo_with_cherry_pick_conflict_and_clean_file`: cherry-pick in progress with conflicted and clean files.
- `init_repo_with_cherry_pick_conflict_and_unrelated_clean_history`: cherry-pick where older source history touched a clean file, but picked commit did not.
- `init_repo_with_octopus_merge_commit`: 3+ parent merge (octopus) to test unsupported/summary behavior.

How to read test flow:

1. helper builds a specific git graph/state
2. test runs `git-resolve-conflict` command(s)
3. assertions check file content, staging, and JSON/text output semantics
