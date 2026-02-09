#!/bin/bash
# lint-on-save.sh — Runs ruff on edited Python files after Write/Edit
# Returns lint warnings as context for Claude

INPUT=$(cat)
FILE_PATH=$(echo "$INPUT" | jq -r '.tool_input.file_path // empty')

# Only lint Python files
if [[ "$FILE_PATH" != *.py ]]; then
    exit 0
fi

# Check if ruff is available
if ! command -v ruff &> /dev/null; then
    exit 0
fi

# Run ruff and capture output
LINT_OUTPUT=$(ruff check "$FILE_PATH" 2>&1)
EXIT_CODE=$?

if [ $EXIT_CODE -ne 0 ]; then
    echo "{\"additionalContext\": \"Lint warnings in $FILE_PATH:\\n$LINT_OUTPUT\"}"
else
    exit 0
fi
