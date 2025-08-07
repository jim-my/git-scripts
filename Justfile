# Justfile for git-scripts development

# Default recipe to display help
default:
    @just --list

# Run all pre-commit hooks
pre-commit:
    @echo "Running pre-commit hooks..."
    pre-commit run --all-files

# Run shellcheck on all scripts
lint:
    @echo "Running shellcheck on all git scripts..."
    shellcheck --severity=warning git-* || true

# Run shellcheck and try to auto-fix issues where possible
fix:
    @echo "Running shellcheck with suggestions..."
    @for script in git-*; do \
        echo "Checking $$script..."; \
        shellcheck --format=diff $$script | patch -p1 || true; \
    done

# Run tests
test:
    @echo "Running tests..."
    @if [ -f test.sh ]; then \
        ./test.sh; \
    else \
        echo "No test.sh found. Create tests for your scripts!"; \
    fi

# Install scripts using the Makefile
install:
    @echo "Installing scripts..."
    make install

# Uninstall scripts using the Makefile
uninstall:
    @echo "Uninstalling scripts..."
    make uninstall

# Clean up temporary files
clean:
    @echo "Cleaning up..."
    make clean
    @rm -f .pre-commit-config.yaml.bak

# Check all scripts for common issues
check:
    @echo "Running comprehensive checks..."
    @echo "1. Checking executability..."
    @for script in git-*; do \
        if [ ! -x "$$script" ]; then \
            echo "Warning: $$script is not executable"; \
        fi; \
    done
    @echo "2. Checking shebangs..."
    @for script in git-*; do \
        if ! head -1 "$$script" | grep -q '^#!/'; then \
            echo "Warning: $$script missing shebang"; \
        fi; \
    done
    @echo "3. Running shellcheck..."
    @just lint
    @echo "Check complete."

# Format and validate the repository
format:
    @echo "Formatting repository..."
    @just pre-commit
    @echo "Repository formatted."

# Setup development environment
setup:
    @echo "Setting up development environment..."
    @if ! command -v pre-commit >/dev/null 2>&1; then \
        echo "Installing pre-commit..."; \
        pip install pre-commit; \
    fi
    @pre-commit install
    @echo "Development environment ready!"

# Show help for a specific script
help script="":
    @if [ -n "{{script}}" ]; then \
        if [ -f "./{{script}}" ]; then \
            ./{{script}} --help; \
        else \
            echo "Script {{script}} not found"; \
            echo "Available scripts:"; \
            ls git-* | head -10; \
        fi; \
    else \
        echo "Usage: just help <script-name>"; \
        echo "Example: just help git-redo"; \
        echo ""; \
        echo "Available scripts:"; \
        ls git-* | head -10; \
        if [ $(ls git-* | wc -l) -gt 10 ]; then \
            echo "... and $(( $(ls git-* | wc -l) - 10 )) more"; \
        fi; \
    fi

# Run a quick development cycle (format, lint, test)
dev:
    @echo "Running development cycle..."
    @just format
    @just lint
    @just test
    @echo "Development cycle complete!"

# Show git status and recent commits (useful for script development)
status:
    @echo "Repository status:"
    @git status --short
    @echo ""
    @echo "Recent commits:"
    @git log --oneline -5

# Create a new git script from template
new-script name="":
    @./create-new-script.sh "{{name}}"
