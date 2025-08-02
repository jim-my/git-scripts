#!/bin/bash
set -euo pipefail

# =============================================================================
# Git Scripts Installation Script
# =============================================================================
#
# This script installs all Git utility scripts to make them available as
# git subcommands. Supports multiple installation methods and platforms.
#
# Usage: ./install.sh [options]
# =============================================================================

# Colors for output
GREEN='\033[0;32m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
RED='\033[0;31m'
BOLD='\033[1m'
NC='\033[0m' # No Color

# Default configuration
INSTALL_METHOD="auto"
INSTALL_DIR=""
FORCE=false
VERBOSE=false
DRY_RUN=false

# Script information
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SCRIPT_COUNT=$(find "$SCRIPT_DIR" -name "git-*" -type f -perm +111 | wc -l | tr -d ' ')

usage() {
    cat << 'EOF'
Git Scripts Installation Script

USAGE:
    ./install.sh [options]

OPTIONS:
    --method <method>     Installation method (auto|copy|symlink|path)
    --dir <directory>     Installation directory (default: auto-detect)
    --force              Overwrite existing scripts
    --verbose            Show detailed output
    --dry-run            Show what would be done without executing
    --help               Show this help message

INSTALLATION METHODS:
    auto       Automatically choose best method (default)
    copy       Copy scripts to bin directory
    symlink    Create symbolic links to scripts
    path       Add scripts directory to PATH

EXAMPLES:
    ./install.sh                           # Auto installation
    ./install.sh --method copy             # Copy to ~/.local/bin
    ./install.sh --dir /usr/local/bin      # Install to system directory
    ./install.sh --dry-run --verbose       # Preview installation
    ./install.sh --force                   # Overwrite existing files

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

# Detect best installation directory
detect_install_dir() {
    local candidates=(
        "$HOME/.local/bin"
        "$HOME/bin"
        "/usr/local/bin"
    )
    
    for dir in "${candidates[@]}"; do
        if [[ -d "$dir" ]] && [[ -w "$dir" ]]; then
            echo "$dir"
            return 0
        fi
    done
    
    # Create ~/.local/bin if it doesn't exist
    mkdir -p "$HOME/.local/bin"
    echo "$HOME/.local/bin"
}

# Check if directory is in PATH
is_in_path() {
    local dir="$1"
    [[ ":$PATH:" == *":$dir:"* ]]
}

# Detect best installation method
detect_install_method() {
    local install_dir="$1"
    
    # If install dir is writable and in PATH, prefer copy
    if [[ -w "$install_dir" ]] && is_in_path "$install_dir"; then
        echo "copy"
    # If we can create symlinks, prefer that
    elif command -v ln >/dev/null 2>&1; then
        echo "symlink"
    # Otherwise use PATH method
    else
        echo "path"
    fi
}

# Find all git scripts
find_git_scripts() {
    find "$SCRIPT_DIR" -name "git-*" -type f -perm +111 | sort
}

# Install using copy method
install_copy() {
    local install_dir="$1"
    local scripts=()
    while IFS= read -r script; do
        scripts+=("$script")
    done < <(find_git_scripts)
    
    log_info "ALWAYS" "Installing ${#scripts[@]} scripts to $install_dir using copy method"
    
    if [[ "$DRY_RUN" == true ]]; then
        log_info "ALWAYS" "DRY RUN: Would copy the following scripts:"
        for script in "${scripts[@]}"; do
            echo "  $(basename "$script") -> $install_dir/$(basename "$script")"
        done
        return 0
    fi
    
    # Create install directory if needed
    if [[ ! -d "$install_dir" ]]; then
        mkdir -p "$install_dir"
        log_info "Created directory: $install_dir"
    fi
    
    local copied=0
    local skipped=0
    
    for script in "${scripts[@]}"; do
        local script_name
        script_name="$(basename "$script")"
        local target="$install_dir/$script_name"
        
        if [[ -f "$target" ]] && [[ "$FORCE" == false ]]; then
            log_warning "Skipping $script_name (already exists, use --force to overwrite)"
            ((skipped++))
            continue
        fi
        
        if cp "$script" "$target"; then
            chmod +x "$target"
            log_info "Copied: $script_name"
            ((copied++))
        else
            log_error "Failed to copy: $script_name"
        fi
    done
    
    log_success "Copied $copied scripts, skipped $skipped"
}

# Install using symlink method
install_symlink() {
    local install_dir="$1"
    local scripts=()
    while IFS= read -r script; do
        scripts+=("$script")
    done < <(find_git_scripts)
    
    log_info "ALWAYS" "Installing ${#scripts[@]} scripts to $install_dir using symlink method"
    
    if [[ "$DRY_RUN" == true ]]; then
        log_info "ALWAYS" "DRY RUN: Would create the following symlinks:"
        for script in "${scripts[@]}"; do
            echo "  $install_dir/$(basename "$script") -> $script"
        done
        return 0
    fi
    
    # Create install directory if needed
    if [[ ! -d "$install_dir" ]]; then
        mkdir -p "$install_dir"
        log_info "Created directory: $install_dir"
    fi
    
    local linked=0
    local skipped=0
    
    for script in "${scripts[@]}"; do
        local script_name
        script_name="$(basename "$script")"
        local target="$install_dir/$script_name"
        
        if [[ -e "$target" ]] && [[ "$FORCE" == false ]]; then
            log_warning "Skipping $script_name (already exists, use --force to overwrite)"
            ((skipped++))
            continue
        fi
        
        # Remove existing file/link if force is enabled
        if [[ -e "$target" ]] && [[ "$FORCE" == true ]]; then
            rm -f "$target"
        fi
        
        if ln -sf "$script" "$target"; then
            log_info "Linked: $script_name"
            ((linked++))
        else
            log_error "Failed to link: $script_name"
        fi
    done
    
    log_success "Linked $linked scripts, skipped $skipped"
}

# Install using PATH method
install_path() {
    log_info "ALWAYS" "Installing scripts using PATH method"
    
    local shell_rc
    case "$SHELL" in
        */zsh)
            shell_rc="$HOME/.zshrc"
            ;;
        */bash)
            shell_rc="$HOME/.bashrc"
            ;;
        *)
            shell_rc="$HOME/.profile"
            ;;
    esac
    
    local path_line="export PATH=\"$SCRIPT_DIR:\$PATH\""
    
    if [[ "$DRY_RUN" == true ]]; then
        log_info "ALWAYS" "DRY RUN: Would add the following line to $shell_rc:"
        echo "  $path_line"
        return 0
    fi
    
    # Check if already in PATH
    if is_in_path "$SCRIPT_DIR"; then
        log_success "Scripts directory already in PATH"
        return 0
    fi
    
    # Check if line already exists in rc file
    if [[ -f "$shell_rc" ]] && grep -Fq "$SCRIPT_DIR" "$shell_rc"; then
        log_success "PATH entry already exists in $shell_rc"
        return 0
    fi
    
    # Add to shell rc file
    echo "" >> "$shell_rc"
    echo "# Git Scripts Collection" >> "$shell_rc"
    echo "$path_line" >> "$shell_rc"
    
    log_success "Added to $shell_rc"
    log_info "ALWAYS" "Restart your shell or run: source $shell_rc"
}

# Verify installation
verify_installation() {
    log_info "ALWAYS" "Verifying installation..."
    
    local test_scripts=("git-check-dup" "git-experiment" "git-wtf")
    local found=0
    
    for script in "${test_scripts[@]}"; do
        if command -v "$script" >/dev/null 2>&1; then
            log_info "✓ $script found in PATH"
            ((found++))
        else
            log_warning "✗ $script not found in PATH"
        fi
    done
    
    if [[ "$found" -eq "${#test_scripts[@]}" ]]; then
        log_success "Installation verified successfully!"
        return 0
    else
        log_warning "Partial installation detected. You may need to restart your shell."
        return 1
    fi
}

# Check requirements
check_requirements() {
    log_info "Checking requirements..."
    
    # Check Git
    if ! command -v git >/dev/null 2>&1; then
        log_error "Git is required but not installed"
        exit 1
    fi
    
    local git_version
    git_version=$(git --version | cut -d' ' -f3)
    log_info "Git version: $git_version"
    
    # Check script directory
    if [[ ! -d "$SCRIPT_DIR" ]]; then
        log_error "Scripts directory not found: $SCRIPT_DIR"
        exit 1
    fi
    
    # Check for scripts
    local script_count
    script_count=$(find_git_scripts | wc -l | tr -d ' ')
    if [[ "$script_count" -eq 0 ]]; then
        log_error "No git scripts found in $SCRIPT_DIR"
        exit 1
    fi
    
    log_info "Found $script_count git scripts"
}

# Parse command line arguments
parse_arguments() {
    while [[ $# -gt 0 ]]; do
        case "$1" in
            --method)
                shift
                INSTALL_METHOD="$1"
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
    
    # Validate install method
    case "$INSTALL_METHOD" in
        auto|copy|symlink|path)
            ;;
        *)
            log_error "Invalid install method: $INSTALL_METHOD"
            usage
            ;;
    esac
}

# Main installation function
main() {
    echo -e "${BOLD}Git Scripts Collection Installer${NC}"
    echo "Installing $SCRIPT_COUNT git utility scripts"
    echo
    
    parse_arguments "$@"
    check_requirements
    
    # Auto-detect installation directory if not specified
    if [[ -z "$INSTALL_DIR" ]]; then
        INSTALL_DIR=$(detect_install_dir)
        log_info "Auto-detected install directory: $INSTALL_DIR"
    fi
    
    # Auto-detect installation method if needed
    if [[ "$INSTALL_METHOD" == "auto" ]]; then
        INSTALL_METHOD=$(detect_install_method "$INSTALL_DIR")
        log_info "Auto-detected install method: $INSTALL_METHOD"
    fi
    
    # Perform installation
    case "$INSTALL_METHOD" in
        copy)
            install_copy "$INSTALL_DIR"
            ;;
        symlink)
            install_symlink "$INSTALL_DIR"
            ;;
        path)
            install_path
            ;;
    esac
    
    echo
    
    # Verify installation (skip for dry-run and path method)
    if [[ "$DRY_RUN" == false ]] && [[ "$INSTALL_METHOD" != "path" ]]; then
        verify_installation
    fi
    
    # Show next steps
    echo
    log_success "Installation complete!"
    echo
    echo -e "${CYAN}Next steps:${NC}"
    echo "1. Test installation: git check-dup --help"
    echo "2. Explore scripts: git experiment start test-feature"
    echo "3. Read documentation: cat README.md"
    
    if [[ "$INSTALL_METHOD" == "path" ]]; then
        echo "4. Restart your shell or run: source ~/.$(basename "$SHELL")rc"
    fi
    
    if ! is_in_path "$INSTALL_DIR" && [[ "$INSTALL_METHOD" != "path" ]]; then
        echo
        log_warning "Install directory is not in PATH: $INSTALL_DIR"
        echo "Add to your shell rc file:"
        echo "  export PATH=\"$INSTALL_DIR:\$PATH\""
    fi
}

# Run main function
main "$@"