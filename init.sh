#!/bin/bash
# init.sh — Environment setup for coding agents
# Run at the start of every coding session
# See docs/AGENT_WORKFLOWS.md for full context

set -e

echo "=== Rekordbox Creative: Session Init ==="

# Ensure we're in the project root
if [ ! -f "CLAUDE.md" ]; then
    echo "ERROR: Not in project root. cd to the project directory first."
    exit 1
fi

# Create/activate virtual environment
if [ ! -d ".venv" ]; then
    echo "Creating virtual environment..."
    python3 -m venv .venv
fi

# Activate venv
source .venv/bin/activate
echo "Python: $(python --version) at $(which python)"

# Install dependencies
echo "Installing dependencies..."
pip install -e ".[dev]" --quiet 2>/dev/null || {
    echo "WARNING: pip install failed. pyproject.toml may not exist yet."
    echo "If this is the initializer agent's first run, this is expected."
}

# Verify audio_analyzer is available
python -c "from audio_analyzer import AudioAnalyzer; print('audio_analyzer: OK')" 2>/dev/null || {
    echo "WARNING: audio_analyzer not available. Install it first:"
    echo "  pip install git+https://github.com/samuelih/audio_analyzer.git"
}

# Show project state
echo ""
echo "=== Project State ==="
echo "Git status:"
git status --short 2>/dev/null || echo "Not a git repo"
echo ""
echo "Recent commits:"
git log --oneline -5 2>/dev/null || echo "No commits yet"

# Run baseline tests if tests exist
if [ -d "tests" ] && [ "$(find tests -name 'test_*.py' -type f 2>/dev/null | head -1)" ]; then
    echo ""
    echo "=== Running Baseline Tests ==="
    pytest tests/ -x --timeout=30 -q 2>/dev/null || {
        echo "WARNING: Some baseline tests failed. Check before implementing new features."
    }
else
    echo ""
    echo "No test files found yet. Skipping baseline tests."
fi

# Show feature progress
if [ -f "docs/FEATURES.json" ]; then
    echo ""
    echo "=== Feature Progress ==="
    total=$(python -c "import json; d=json.load(open('docs/FEATURES.json')); print(d['metadata']['total_features'])")
    passing=$(python -c "import json; d=json.load(open('docs/FEATURES.json')); print(sum(1 for f in d['features'] if f['passes']))")
    echo "Features: $passing / $total passing"

    # Show next failing feature
    next=$(python -c "
import json
d = json.load(open('docs/FEATURES.json'))
for f in d['features']:
    if not f['passes']:
        print(f'{f[\"id\"]}: {f[\"name\"]}')
        break
" 2>/dev/null || echo "Could not determine next feature")
    echo "Next feature: $next"
fi

echo ""
echo "=== Init complete. Ready to code. ==="
