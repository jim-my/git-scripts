# Git Duplicate Management Tools

Two powerful Git tools for managing duplicate commits in your repository workflow.

## 🔍 git-check-dup

**Find duplicate commits between branches**

Detects commits with identical **content** (same patch-id) between your current branch and a remote branch. Essential for identifying commits that were cherry-picked, rebased, or applied multiple times with different hashes.

### ⚠️ What Are "Duplicate" Commits?

**DUPLICATE = Same code changes, different commit hashes**

- ✅ **Commits that make identical changes** to the code (same additions, deletions, modifications)
- ✅ **Different commit hashes** due to different timestamps, authors, or commit context
- ✅ **Created by**: Cherry-picking, rebasing, manual re-application of changes

**NOT DUPLICATES:**
- ❌ Commits with identical messages but different code changes
- ❌ Commits that modify the same files but make different changes  
- ❌ Commits with similar but not identical content

**Example:**
```
Commit A (local):  abc1234 "Add user validation" - adds 3 lines to user.py
Commit B (remote): def5678 "Add user validation" - adds the SAME 3 lines to user.py
→ These are DUPLICATES (same content, different hashes)

Commit C: ghi9012 "Add user validation" - adds 5 different lines to user.py  
→ This is NOT a duplicate (same message, different content)
```

### Quick Start
```bash
git-check-dup                    # Check against origin/main
git-check-dup upstream/develop   # Check against specific branch
git-check-dup --quiet | wc -l   # Count duplicates (pipe-friendly)
```

### Output Example
```
Local                                    Remote(origin/main)              Patch_id
134ba637a252ebf49b5e511dcf9ab4434f80928f faaf9ca934f27792a912cc3db7fadadaa0b7c8ad 2edbefbe2ef9cef17745ac7fa6e2c5d101a9376b
    134ba637: 2025-08-01 docs: add wb_screenshot_select and wb_click_at visual selection tools
    faaf9ca9: 2025-08-01 docs: add wb_screenshot_select and wb_click_at visual selection tools
```

### Use Cases
- **Before rebasing**: Check if your commits already exist upstream
- **After cherry-picking**: Verify which commits were successfully applied
- **Code review**: Identify redundant commits in pull requests
- **Branch cleanup**: Find commits that can be safely dropped

---

## 🧹 git-remove-duplicates-and-rebase

**Automatically clean branch history and rebase**

Removes duplicate commits and cleanly rebases your branch onto a target branch. Solves the common problem of redundant commits from development workflows with cherry-picking, rebasing, and merging.

### Quick Start
```bash
git-remove-duplicates-and-rebase                    # Dry-run (safe preview)
git-remove-duplicates-and-rebase --apply            # Actually clean and rebase
git-remove-duplicates-and-rebase --onto upstream/main --apply
```

### Workflow
1. **Preview**: Run without `--apply` to see what will happen
2. **Review**: Check the duplicate detection and rebase plan
3. **Execute**: Run with `--apply` to perform the cleanup
4. **Resolve**: Handle any rebase conflicts manually if needed

### Safety Features
- ✅ **Dry-run by default** - Always preview before applying
- ✅ **Automatic backups** - Creates timestamped backup branch
- ✅ **Conflict detection** - Stops on rebase conflicts for manual resolution
- ✅ **Clear reporting** - Shows exactly what duplicates will be removed

### Use Cases
- **Clean feature branches** before merging
- **Remove redundant commits** after cherry-picking
- **Prepare clean PRs** with linear history
- **Fix messy branches** with duplicate commits from rebasing mishaps

---

## 🔧 How They Work Together

These tools use **patch-id** comparison to detect content duplicates regardless of commit hash differences:

### Technical Details: What is patch-id?

**Patch-id** is Git's way of creating a content fingerprint for commits:

- **Same patch-id** = Identical code changes (same lines added/removed/modified)
- **Different patch-id** = Different code changes (even if commit messages are identical)
- **Ignores**: Commit hash, timestamp, author, commit message
- **Focuses on**: Actual code differences (the "diff" or "patch")

```bash
# Two commits with same content will have same patch-id
git show abc1234 | git patch-id --stable
# Output: f1d2d2f924e986ac86fdf7b36c94bcdf32beec15 abc1234

git show def5678 | git patch-id --stable  
# Output: f1d2d2f924e986ac86fdf7b36c94bcdf32beec15 def5678
#         ^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^ Same patch-id = duplicate content
```

1. **git-check-dup** identifies which commits are duplicates
2. **git-remove-duplicates-and-rebase** uses git-check-dup internally and automatically removes them during rebase

### Example Workflow
```bash
# 1. Check what duplicates exist
git-check-dup origin/main

# 2. Preview the cleanup (dry-run)
git-remove-duplicates-and-rebase --onto origin/main

# 3. Actually perform the cleanup
git-remove-duplicates-and-rebase --onto origin/main --apply
```

---

## 📋 Common Scenarios

### Scenario 1: Messy Feature Branch
```bash
# You have a feature branch with duplicate commits from rebasing
git checkout feature/my-feature
git-remove-duplicates-and-rebase --apply
```

### Scenario 2: Check Before Push
```bash
# Before pushing, check if any commits already exist upstream
git-check-dup origin/main
# If duplicates found, clean them up
git-remove-duplicates-and-rebase --apply
```

### Scenario 3: Clean PR Preparation
```bash
# Prepare a clean branch for pull request
git-remove-duplicates-and-rebase --onto origin/main --apply
git push --force-with-lease origin feature/my-feature
```

### Scenario 4: Post-Cherry-Pick Cleanup
```bash
# After cherry-picking commits, remove any duplicates
git-check-dup upstream/develop
git-remove-duplicates-and-rebase --onto upstream/develop --apply
```

---

## 🛡️ Safety & Recovery

Both tools prioritize safety:

- **git-check-dup**: Read-only operation, never modifies your repository
- **git-remove-duplicates-and-rebase**: Creates backup branches automatically

### If Something Goes Wrong
```bash
# List all backup branches
git branch | grep "$(git rev-parse --abbrev-ref HEAD)_"

# Restore from backup (replace TIMESTAMP with actual timestamp)
git reset --hard feature/my-feature_TIMESTAMP
```

---

## 🚀 Installation

These tools are part of the dotfiles git utilities. Ensure they're in your PATH:

```bash
# Check if installed
which git-check-dup git-remove-duplicates-and-rebase

# They should be in ~/.dotfiles/bin/git/ and accessible as git subcommands
```

Both tools integrate seamlessly with Git's subcommand system and can be called as `git check-dup` or `git remove-duplicates-and-rebase` as well.