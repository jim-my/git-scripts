#!/bin/bash

# test.sh: A simple test runner for git-scripts

set -euo pipefail

FAILURES=0

for script in git-*;
do
    if [ -f "$script" ] && [ -x "$script" ]; then
        echo "Testing $script..."
        if ."/$script" --help > /dev/null; then
            echo "  $script --help OK"
        else
            echo "  $script --help FAILED"
            FAILURES=$((FAILURES + 1))
        fi
    fi
done

if [ $FAILURES -gt 0 ]; then
    echo "$FAILURES tests failed."
    exit 1
else
    echo "All tests passed."
    exit 0
fi
