#!/bin/bash
# verify-tests-on-stop.sh — Checks if tests pass before agent stops
# Prevents agents from stopping with broken tests

INPUT=$(cat)

# Check if stop hook is already active (prevent infinite loops)
STOP_HOOK_ACTIVE=$(echo "$INPUT" | jq -r '.stop_hook_active // false')
if [ "$STOP_HOOK_ACTIVE" = "true" ]; then
    exit 0
fi

# Check if tests directory exists and has test files
if [ ! -d "tests" ]; then
    exit 0
fi

TEST_FILES=$(find tests -name 'test_*.py' -type f 2>/dev/null | head -1)
if [ -z "$TEST_FILES" ]; then
    exit 0
fi

# Check if venv is available
if [ -d ".venv" ]; then
    source .venv/bin/activate 2>/dev/null
fi

# Run tests
TEST_OUTPUT=$(pytest tests/ -x --timeout=30 -q 2>&1)
EXIT_CODE=$?

if [ $EXIT_CODE -ne 0 ]; then
    echo "Tests are failing. Fix them before stopping:" >&2
    echo "$TEST_OUTPUT" >&2
    exit 2
fi

# Check for uncommitted changes
GIT_STATUS=$(git status --short 2>/dev/null)
if [ -n "$GIT_STATUS" ]; then
    echo "There are uncommitted changes. Commit your work before stopping:" >&2
    echo "$GIT_STATUS" >&2
    exit 2
fi

exit 0
