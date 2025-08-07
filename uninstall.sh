#!/bin/bash
set -euo pipefail

# =============================================================================
# Git Scripts Uninstallation Script
# =============================================================================
#
# This script removes all Git utility scripts that were installed by install.sh.
# Supports multiple removal methods and provides safe cleanup options.
#
# Usage: ./uninstall.sh [options]
# =============================================================================

# Colors for output
GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BOLD='\033[1m'
NC='\033[0m' # No Color

# Default configuration
UNINSTALL_METHOD="auto"
INSTALL_DIR=""
FORCE=false
VERBOSE=false
DRY_RUN=false
KEEP_CONFIGS=true

# Script information
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

usage() {
    cat << 'EOF'
Git Scripts Uninstallation Script

USAGE:
    ./uninstall.sh [options]

OPTIONS:
    --method <method>     Uninstall method (auto|search|manual)
    --dir <directory>     Directory to remove scripts from
    --force              Remove files without confirmation
    --verbose            Show detailed output
    --dry-run            Show what would be done without executing
    --remove-configs     Also remove PATH entries from shell config files
    --help               Show this help message

UNINSTALL METHODS:
    auto       Automatically find and remove scripts (default)
    search     Search common directories for installed scripts
    manual     Remove from specified directory only

EXAMPLES:
    ./uninstall.sh                           # Auto uninstall
    ./uninstall.sh --dir ~/.local/bin        # Remove from specific directory
    ./uninstall.sh --dry-run --verbose       # Preview removal
    ./uninstall.sh --remove-configs          # Also clean PATH entries

EOF
    exit 1
}

log_info() {
    if [[ "$VERBOSE" == true ]] || [[ "$1" == "ALWAYS" ]]; then
        if [[ "$1" == "ALWAYS" ]]; then
            shift
        fi
        echo -e "${CYAN}[INFO]${NC} $*"
    fi
}

log_success() {
    echo -e "${GREEN}[✓]${NC} $*"
}

log_warning() {
    echo -e "${YELLOW}[⚠]${NC} $*"
}

log_error() {
    echo -e "${RED}[✗]${NC} $*" >&2
}

# Find all git scripts in current directory
find_git_scripts() {
    find "$SCRIPT_DIR" -name "git-*" -type f -perm +111 | sort
}

# Get script names without path
get_script_names() {
    local scripts=()
    while IFS= read -r script; do
        scripts+=($(basename "$script"))
    done < <(find_git_scripts)
    printf '%s\n' "${scripts[@]}"
}

# Find common installation directories
find_install_directories() {
    local candidates=(
        "$HOME/.local/bin"
        "$HOME/bin"
        "/usr/local/bin"
    )

    local found_dirs=()
    for dir in "${candidates[@]}"; do
        if [[ -d "$dir" ]]; then
            found_dirs+=("$dir")
        fi
    done

    printf '%s\n' "${found_dirs[@]}"
}

# Check if script exists in directory
script_exists_in_dir() {
    local script_name="$1"
    local dir="$2"
    [[ -f "$dir/$script_name" ]]
}

# Remove scripts from directory
remove_scripts_from_dir() {
    local install_dir="$1"
    local script_names=()
    while IFS= read -r name; do
        script_names+=("$name")
    done < <(get_script_names)

    log_info "ALWAYS" "Removing scripts from $install_dir"

    local found=0
    local removed=0
    local failed=0

    for script_name in "${script_names[@]}"; do
        local script_path="$install_dir/$script_name"

        if [[ -f "$script_path" ]]; then
            ((found++))

            if [[ "$DRY_RUN" == true ]]; then
                echo "  Would remove: $script_path"
                continue
            fi

            if rm -f "$script_path" 2>/dev/null; then
                log_info "Removed: $script_name"
                ((removed++))
            else
                log_error "Failed to remove: $script_name"
                ((failed++))
            fi
        fi
    done

    if [[ "$DRY_RUN" == true ]]; then
        log_info "ALWAYS" "DRY RUN: Would remove $found scripts from $install_dir"
    else
        log_success "Removed $removed scripts, failed $failed"
    fi

    return $found
}

# Auto uninstall - search common directories
auto_uninstall() {
    log_info "ALWAYS" "Searching for installed scripts..."

    local total_found=0

    while IFS= read -r dir; do
        if remove_scripts_from_dir "$dir"; then
            ((total_found += $?))
        fi
    done < <(find_install_directories)

    if [[ "$total_found" -eq 0 ]]; then
        log_warning "No installed scripts found in common directories"
        log_info "ALWAYS" "Try: ./uninstall.sh --method search --verbose"
    fi
}

# Search method - look more thoroughly
search_uninstall() {
    log_info "ALWAYS" "Searching PATH for installed scripts..."

    local script_names=()
    while IFS= read -r name; do
        script_names+=("$name")
    done < <(get_script_names)

    local found_scripts=()

    for script_name in "${script_names[@]}"; do
        local script_path
        if script_path=$(command -v "$script_name" 2>/dev/null); then
            found_scripts+=("$script_path")
            log_info "Found: $script_path"
        fi
    done

    if [[ "${#found_scripts[@]}" -eq 0 ]]; then
        log_warning "No scripts found in PATH"
        return 0
    fi

    if [[ "$DRY_RUN" == true ]]; then
        log_info "ALWAYS" "DRY RUN: Would remove ${#found_scripts[@]} scripts:"
        printf '  %s\n' "${found_scripts[@]}"
        return 0
    fi

    # Confirm removal
    if [[ "$FORCE" == false ]]; then
        echo
        log_warning "Found ${#found_scripts[@]} installed scripts:"
        printf '  %s\n' "${found_scripts[@]}"
        echo
        read -p "Remove all these scripts? (y/N): " confirm
        if [[ "$confirm" != "y" && "$confirm" != "Y" ]]; then
            echo "Cancelled"
            return 0
        fi
    fi

    local removed=0
    local failed=0

    for script_path in "${found_scripts[@]}"; do
        if rm -f "$script_path" 2>/dev/null; then
            log_info "Removed: $script_path"
            ((removed++))
        else
            log_error "Failed to remove: $script_path"
            ((failed++))
        fi
    done

    log_success "Removed $removed scripts, failed $failed"
}

# Manual uninstall from specific directory
manual_uninstall() {
    local install_dir="$1"

    if [[ ! -d "$install_dir" ]]; then
        log_error "Directory does not exist: $install_dir"
        return 1
    fi

    remove_scripts_from_dir "$install_dir"
}

# Remove PATH entries from shell config files
remove_path_entries() {
    if [[ "$KEEP_CONFIGS" == true ]]; then
        log_info "Skipping PATH cleanup (use --remove-configs to clean)"
        return 0
    fi

    log_info "ALWAYS" "Cleaning PATH entries from shell config files..."

    local shell_configs=(
        "$HOME/.bashrc"
        "$HOME/.zshrc"
        "$HOME/.profile"
    )

    local cleaned=0

    for config in "${shell_configs[@]}"; do
        if [[ ! -f "$config" ]]; then
            continue
        fi

        # Look for lines containing our script directory
        if grep -q "$SCRIPT_DIR" "$config" 2>/dev/null; then
            if [[ "$DRY_RUN" == true ]]; then
                log_info "Would clean PATH entries from: $config"
                grep "$SCRIPT_DIR" "$config" | sed 's/^/  /'
                continue
            fi

            # Create backup
            cp "$config" "$config.backup.$(date +%Y%m%d_%H%M%S)"

            # Remove lines containing our script directory
            if grep -v "$SCRIPT_DIR" "$config" > "$config.tmp" && mv "$config.tmp" "$config"; then
                log_info "Cleaned PATH entries from: $config"
                ((cleaned++))
            else
                log_error "Failed to clean: $config"
                # Restore backup
                mv "$config.backup."* "$config" 2>/dev/null || true
            fi
        fi
    done

    if [[ "$DRY_RUN" == false ]] && [[ "$cleaned" -gt 0 ]]; then
        log_success "Cleaned $cleaned config files"
        log_info "ALWAYS" "Restart your shell to apply changes"
    fi
}

# Verify uninstallation
verify_uninstall() {
    log_info "ALWAYS" "Verifying uninstallation..."

    local test_scripts=("git-check-dup" "git-experiment" "git-wtf")
    local still_found=0

    for script in "${test_scripts[@]}"; do
        if command -v "$script" >/dev/null 2>&1; then
            log_warning "✗ $script still found in PATH"
            ((still_found++))
        else
            log_info "✓ $script not found"
        fi
    done

    if [[ "$still_found" -eq 0 ]]; then
        log_success "Uninstallation verified - no scripts found in PATH"
        return 0
    else
        log_warning "$still_found scripts still found in PATH"
        log_info "ALWAYS" "Try: ./uninstall.sh --method search --verbose"
        return 1
    fi
}

# Parse command line arguments
parse_arguments() {
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --method)
                shift
                UNINSTALL_METHOD="$1"
                ;;
            --dir)
                shift
                INSTALL_DIR="$1"
                ;;
            --force)
                FORCE=true
                ;;
            --verbose)
                VERBOSE=true
                ;;
            --dry-run)
                DRY_RUN=true
                VERBOSE=true
                ;;
            --remove-configs)
                KEEP_CONFIGS=false
                ;;
            --help|-h)
                usage
                ;;
            *)
                log_error "Unknown option: $1"
                usage
                ;;
        esac
        shift
    done

    # Validate uninstall method
    case "$UNINSTALL_METHOD" in
        auto|search|manual)
            ;;
        *)
            log_error "Invalid uninstall method: $UNINSTALL_METHOD"
            usage
            ;;
    esac

    # Manual method requires directory
    if [[ "$UNINSTALL_METHOD" == "manual" ]] && [[ -z "$INSTALL_DIR" ]]; then
        log_error "Manual method requires --dir option"
        usage
    fi
}

# Main uninstallation function
main() {
    echo -e "${BOLD}Git Scripts Collection Uninstaller${NC}"
    echo

    parse_arguments "$@"

    # Check if script directory exists
    if [[ ! -d "$SCRIPT_DIR" ]]; then
        log_error "Scripts directory not found: $SCRIPT_DIR"
        exit 1
    fi

    # Perform uninstallation
    case "$UNINSTALL_METHOD" in
        auto)
            auto_uninstall
            ;;
        search)
            search_uninstall
            ;;
        manual)
            manual_uninstall "$INSTALL_DIR"
            ;;
    esac

    # Clean PATH entries if requested
    remove_path_entries

    echo

    # Verify uninstallation (skip for dry-run)
    if [[ "$DRY_RUN" == false ]]; then
        verify_uninstall
    fi

    # Show completion message
    echo
    if [[ "$DRY_RUN" == true ]]; then
        log_success "Dry-run complete - no changes made"
    else
        log_success "Uninstallation complete!"
    fi

    echo
    echo -e "${CYAN}If scripts are still accessible:${NC}"
    echo "1. Check for additional installation directories"
    echo "2. Run: ./uninstall.sh --method search --verbose"
    echo "3. Manually remove PATH entries from shell config files"
    echo "4. Restart your shell"
}

# Run main function
main "$@"
