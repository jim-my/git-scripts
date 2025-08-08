#!/usr/bin/env bash
# Git aliases for simple operations that don't warrant full scripts

# Show files changed between commits (replaces git-diff-changed_files script)
alias git-diff-changed-files='git diff --name-only'

# Usage:
# git-diff-changed-files SHA1 [SHA2]  # Show changed files between commits
# source this file or add to your shell profile
