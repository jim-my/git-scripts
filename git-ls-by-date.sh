#!/usr/bin/env bash
set -euo pipefail

# =============================================================================
# git-ls-by-date - List files ordered by last commit date
# =============================================================================
#
# PURPOSE:
#   List all files in the repository with their last commit date, sorted by date.
#   Useful for finding recently modified files or identifying stale files.
#
# USAGE:
#   git-ls-by-date [--help] [--sort] [commit]
#
# EXAMPLES:
#   git-ls-by-date                    # List files with dates from HEAD
#   git-ls-by-date --sort             # Sort by date (oldest first)
#   git-ls-by-date main               # List files from main branch
#
# =============================================================================

# Usage function
usage() {
    cat << 'EOF'
Usage: git-ls-by-date [--help] [--sort] [commit]

List all files with their last commit date.

Arguments:
  commit    Git commit/branch to examine (default: HEAD)

Options:
  --sort    Sort output by date (oldest first)
  --help    Show this help message

Examples:
  git-ls-by-date                    # List files with dates from HEAD
  git-ls-by-date --sort             # Sort by date (oldest first)  
  git-ls-by-date main               # List files from main branch

Output format: YYYY-MM-DD filename
EOF
    exit 1
}

# Error handling function
error_exit() {
    local message="$1"
    local exit_code="${2:-1}"
    echo "Error: $message" >&2
    exit "$exit_code"
}

# Check if we're in a git repository
check_git_repo() {
    if ! git rev-parse --git-dir >/dev/null 2>&1; then
        error_exit "Not in a git repository"
    fi
}

# Parse arguments
parse_arguments() {
    COMMIT="HEAD"
    SORT_OUTPUT=false
    
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --help|-h)
                usage
                ;;
            --sort|-s)
                SORT_OUTPUT=true
                ;;
            -*)
                error_exit "Unknown option: $1. Use --help for usage information."
                ;;
            *)
                COMMIT="$1"
                ;;
        esac
        shift
    done
}

# Validate commit exists
validate_commit() {
    local commit="$1"
    if ! git rev-parse --verify "$commit" >/dev/null 2>&1; then
        error_exit "Commit '$commit' not found"
    fi
}

# Main function
main() {
    parse_arguments "$@"
    check_git_repo
    validate_commit "$COMMIT"
    
    echo "Listing files from commit: $COMMIT"
    echo
    
    # Create temporary file for output
    local temp_file
    temp_file=$(mktemp)
    trap "rm -f '$temp_file'" EXIT
    
    # Process each file safely using process substitution
    while IFS= read -r filename; do
        if [[ -n "$filename" ]]; then
            # Get last commit date for this file
            local commit_date
            if commit_date=$(git log -1 --format="%ad" --date=short -- "$filename" 2>/dev/null); then
                printf "%s %s\n" "$commit_date" "$filename" >> "$temp_file"
            else
                printf "????-??-?? %s\n" "$filename" >> "$temp_file"
            fi
        fi
    done < <(git ls-tree -r --name-only "$COMMIT" 2>/dev/null)
    
    # Output results (sorted or unsorted)
    if [[ "$SORT_OUTPUT" == true ]]; then
        sort "$temp_file"
    else
        cat "$temp_file"
    fi
}

# Run main function with all arguments
main "$@"
