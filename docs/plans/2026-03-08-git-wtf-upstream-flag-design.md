# Design: `--upstream / -u` flag for `git-wtf`

**Ticket:** #13
**Date:** 2026-03-08
**Status:** Approved

## Problem

`git-wtf` shows how a branch relates to its configured remote tracking branch, but provides no way to compare against a different upstream. Users often need to compare their branch against a different target (e.g., `origin/develop` instead of `origin/main`, or an arbitrary local branch).

## Solution

Add `--upstream <ref>` / `-u <ref>` flag to override the upstream branch used for comparison.

## Usage

```
git wtf --upstream origin/develop          # current branch vs origin/develop
git wtf my-feature --upstream main         # my-feature vs main
git wtf -u origin/release/1.0             # current branch vs remote release
```

## Design Details

### New flag
- `--upstream <ref>` / `-u <ref>`
- Accepts any valid branch ref resolvable in `all_branches` (local or remote)

### Behavior
- When `--upstream <ref>` is provided, the `remote_branch` field in the target branch's info is overridden with the specified upstream
- Applied to all target branches specified (or the current branch if no targets given)
- Integration/feature branch relations (`--relations` flag) continue to use original branch data, not the upstream override

### Error handling
- If the upstream ref is not found in `all_branches`, print a clear error and exit with code 1

## Changes

| Component | Change |
|-----------|--------|
| `parse_args()` | Parse `--upstream`/`-u <ref>`, store as `args['upstream']` |
| `main()` | Resolve upstream ref in `all_branches`; override `remote_branch` on each target |
| `USAGE` string | Document the new flag |
| `tests/test_git_wtf.py` | Add test cases for new flag behavior and error cases |

## Edge Cases

| Case | Behavior |
|------|----------|
| Upstream ref not found | Error message + exit 1 |
| Multiple targets + `--upstream` | Same upstream applied to all targets |
| `--upstream` + `--relations` | Relations still use original branch data |
| Upstream is same as target | Show as in-sync (0 commits ahead/behind) |
