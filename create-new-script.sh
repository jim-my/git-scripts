#!/bin/bash

# create-new-script.sh: Helper to create new git scripts from template

set -euo pipefail

if [ $# -ne 1 ]; then
    echo "Usage: $0 <script-name>"
    echo "Example: $0 git-my-command"
    exit 1
fi

script_name="$1"

if [ -f "$script_name" ]; then
    echo "Error: $script_name already exists"
    exit 1
fi

echo "Creating new script: $script_name"

# Create the script using clean heredoc
cat > "$script_name" <<'TEMPLATE_EOF'
#!/bin/bash

# SCRIPT_NAME: Description of what this script does
#
# Add detailed description here

set -euo pipefail

usage() {
    cat <<'USAGE_EOF'
SCRIPT_NAME - Brief description

USAGE:
    SCRIPT_NAME [--help]

DESCRIPTION:
    Add detailed description here.

OPTIONS:
    --help    Show this help message

EXAMPLES:
    # Example usage
    SCRIPT_NAME

USAGE_EOF
}

if [[ $# -gt 0 && $1 == "--help" ]]; then usage; exit 0; fi
if ! git rev-parse --git-dir >/dev/null 2>&1; then echo "Error: Not in a git repository"; exit 1; fi

echo "SCRIPT_NAME: Add your implementation here"
TEMPLATE_EOF

# Replace placeholder with actual script name
sed -i '' "s/SCRIPT_NAME/$script_name/g" "$script_name"

chmod +x "$script_name"
echo "✓ Created $script_name"
echo "Edit the script and run 'just lint' to check it"
