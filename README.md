# Git Utility Scripts Collection

> A comprehensive collection of 50+ Git utility scripts solving real workflow problems

[![Scripts](https://img.shields.io/badge/scripts-50+-blue.svg)](#scripts-index)
[![Languages](https://img.shields.io/badge/languages-Bash%20%7C%20Ruby%20%7C%20Python-brightgreen.svg)](#)
[![Quality](https://img.shields.io/badge/security-hardened-green.svg)](#security-features)

## 🚀 Quick Start

```bash
# Clone the repository
git clone https://github.com/jim-my/git-scripts.git
cd git-scripts

# Install all scripts
./install.sh

# Start using immediately
git check-dup                    # Find duplicate commits
git experiment start my-feature  # Safe experimentation
git wtf                          # Enhanced status
```

## 🌟 Featured Scripts

| Script | Purpose | Why Use It |
|--------|---------|------------|
| **git-check-dup** | Find duplicate commits between branches | Detects identical content with different hashes |
| **git-experiment** | Safe code experimentation sandbox | Isolated development with automatic cleanup |
| **git-search-in-each-commit** | Search through commit history | Fills gap in git's "contains pattern" search |
| **git-when-reached-branch** | Determine when commit reached branch | Comprehensive merge detection with confidence levels |
| **git-remove-redundant-commits** | Clean branch history automatically | Remove duplicates and rebase cleanly |
| **git-split-amended-commit** | Split accidentally merged commits | Fixes accidental `git commit --amend` mistakes |
| **git-wtf** | Enhanced repository status | Branch relationships and sync status |

## 📂 Categories

### 🔍 **Duplicate & History Management**
- **git-check-dup** - Find commits with identical content between branches
- **git-remove-redundant-commits** - Remove duplicate commits and rebase cleanly
- **git-remove-from-history** - Completely remove files/directories from history
- **git-search-in-each-commit** - Search for patterns across commit history
- **git-when-reached-branch** - Track when commits reached specific branches

### 🌿 **Branch Operations**
- **git-branch-current** - Get current branch name safely
- **git-branch-diff** - Visual diff of commit logs between branches
- **git-branch-new_and_track** - Create and track new branches
- **git-branch-not-merged** - List unmerged branches
- **git-branch-set_tracking** - Configure branch tracking
- **git-branch-show** - Show branch information
- **git-branch-tracking** - Display tracking relationships
- **git-delete-local-merged** - Delete local branches merged into current
- **git-promote** - Promote local branch to remote tracking

### 🔄 **Workflow Helpers**
- **git-amend** - Amend last commit with staged changes
- **git-experiment** - Safe experimentation with isolated branches
- **git-stage-all** - Stage all changes with confirmation
- **git-stash-smart** - Enhanced stash management with search
- **git-undo** - Undo last commit but keep changes staged
- **git-up** - Enhanced pull with change summary
- **git-reup** - Pull with rebase and change summary

### 📊 **Diff & Comparison Tools**
- **git-diff_with_prev** - Compare with previous version
- **git-diff-123** - Three-way diff visualization
- **git-diff-branch** - Compare branches with enhanced output
- **git-diff-changed_files** - Show only changed file names
- **git-diff-theirs_combined** - Show their changes in merge conflicts
- **git-diff-with-2nd-parent.rb** - Compare with second parent in merges
- **git-icdiff** - Side-by-side diffs with icdiff
- **git-show2** - Enhanced git show with better visualization
- **git-show-vim** - Show commits in vim

### 📈 **Log & Analysis**
- **git-incoming** - Show incoming changes from remote
- **git-log-merges** - Enhanced merge commit log
- **git-log-search_all_commits** - Search across all commits
- **git-ls-by-date** - List files by last commit date
- **git-merged-what-log** - Show what was merged
- **git-merged-what-show** - Display merge details
- **git-rank-contributers** - Rank contributors by diff size
- **git-show-merges** - Show merge relationships
- **git-status-date** - Status with date information
- **git-wtf** - Comprehensive repository status

### 🛠️ **Advanced Operations**
- **git-credit** - Credit authors on commits
- **git-extract-folder** - Extract folder to new repository
- **git-fetch-and-checkout** - Fetch and checkout in one command
- **git-find_file** - Find files across all branches
- **git-merge-test** - Test merge operations
- **git-move-after** - Move commits to new positions
- **git-move-before** - Reorder commits in history
- **git-split-amended-commit** - Split accidentally merged commits


## 🛡️ Security Features

All scripts implement security best practices:

- **Input validation** - All user inputs are validated and sanitized
- **Command injection protection** - No unsafe string interpolation
- **Error handling** - Comprehensive error checking with meaningful messages
- **Git repository validation** - Verify git repository before operations
- **Safe defaults** - Dry-run modes and confirmation prompts for destructive operations

## 📋 Installation Methods

### Method 1: Automatic Installation (Recommended)
```bash
git clone https://github.com/jim-my/git-scripts.git
cd git-scripts
./install.sh
```

### Method 2: Manual Installation
```bash
# Clone repository
git clone https://github.com/jim-my/git-scripts.git

# Add to PATH (add to your ~/.bashrc or ~/.zshrc)
export PATH="$HOME/git-scripts:$PATH"

# Or copy to local bin directory
cp git-scripts/git-* ~/.local/bin/
```

### Method 3: Selective Installation
```bash
# Install only specific scripts
cp git-scripts/git-check-dup ~/.local/bin/
cp git-scripts/git-experiment ~/.local/bin/
cp git-scripts/git-wtf ~/.local/bin/
```

## 💡 Usage Examples

### Duplicate Management Workflow
```bash
# Find duplicate commits between branches
git check-dup origin/main

# Remove duplicates and clean history
git remove-redundant-commits --apply
```

### Safe Experimentation
```bash
# Start experiment
git experiment start feature-xyz

# Work on changes...
git add . && git commit -m "experimental changes"

# Keep or discard
git experiment keep    # merge back to original branch
git experiment discard # delete experiment entirely
```

### Enhanced Status & Sync
```bash
# Comprehensive repository status
git wtf

# Enhanced pull with summary
git up                 # pull with merge
git reup              # pull with rebase
```

### Historical Analysis
```bash
# Search through commit history
git search-in-each-commit --keyword "TODO" --since "2024-01-01"

# Find when commit reached main branch
git when-reached-branch abc1234 main

# List files by last modification
git ls-by-date --sort
```

## 🔗 Script Dependencies

Some scripts work better together:

- **git-check-dup** + **git-remove-redundant-commits** - Complete duplicate management
- **git-experiment** + **git-stash-smart** - Enhanced experimental workflow
- **git-up/reup** + **git-wtf** - Comprehensive sync and status workflow

## 🧪 Requirements

- **Git** 2.0+ (most scripts work with older versions)
- **Bash** 4.0+ (for bash scripts)
- **Ruby** 2.0+ (for ruby scripts)
- **Python** 3.6+ (for python scripts)

### Optional Dependencies
- **vim** - For git-branch-diff, git-show-vim
- **icdiff** - For git-show2, git-icdiff (`pip install icdiff`)

## 🤝 Contributing

1. **Fork** the repository
2. **Create** a feature branch (`git checkout -b feature/amazing-script`)
3. **Follow** existing patterns:
   - Add proper error handling
   - Include comprehensive documentation
   - Use security best practices
   - Add usage examples
4. **Test** your script thoroughly
5. **Submit** a pull request

### Script Guidelines
- Use `set -euo pipefail` for bash scripts
- Validate all inputs
- Provide `--help` documentation
- Include usage examples in header
- Follow naming convention: `git-action-description`

## 📜 License

[MIT License](LICENSE) - Feel free to use and modify

## 🙏 Acknowledgments

- Inspired by [jwiegley/git-scripts](https://github.com/jwiegley/git-scripts)
- **git-when-reached-branch** based on [git-when-merged](https://github.com/mhagger/git-when-merged) by Michael Haggerty
- Built on top of Git's excellent foundation
- Community contributions and feedback

## 📞 Support

- **Issues**: Report bugs or request features via [GitHub Issues](https://github.com/jim-my/git-scripts/issues)
- **Discussions**: Share workflows and ask questions in [Discussions](https://github.com/jim-my/git-scripts/discussions)
- **Security**: Report security issues privately via email

---

## Scripts Index

<details>
<summary>Complete list of all 50 scripts (click to expand)</summary>

### A-D
- git-amend
- git-branch-current
- git-branch-diff
- git-branch-new_and_track
- git-branch-not-merged
- git-branch-set_tracking
- git-branch-show
- git-branch-tracking
- git-check-dup
- git-credit
- git-delete-local-merged
- git-diff_with_prev
- git-diff-123
- git-diff-branch
- git-diff-changed_files
- git-diff-theirs_combined
- git-diff-with-2nd-parent.rb

### E-M
- git-experiment
- git-extract-folder
- git-fetch-and-checkout.rb
- git-find_file
- git-icdiff
- git-incoming
- git-log-merges.rb
- git-log-search_all_commits
- git-ls-by-date.sh
- git-merge-test
- git-merged-what-log
- git-merged-what-show
- git-move-after
- git-move-before

### N-Z
- git-promote
- git-rank-contributers
- git-remove-from-history
- git-remove-redundant-commits
- git-reup
- git-search-in-each-commit
- git-show-merges
- git-show-vim
- git-show2
- git-split-amended-commit
- git-stage-all
- git-stash-smart
- git-status-date
- git-undo
- git-up
- git-when-reached-branch
- git-wtf

</details>

---

**⭐ Star this repository if you find it useful!**
