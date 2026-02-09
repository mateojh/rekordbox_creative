# Agent Workflows & Long-Running Agent Harness

## Architecture: Two-Agent System

Based on [Anthropic's effective harnesses for long-running agents](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents), this project uses a two-agent pattern:

1. **Initializer Agent** — Runs once at the start to set up the environment, create scaffolding, and make the first commit
2. **Coding Agent** — Runs in subsequent sessions, picks up one feature at a time, implements it, tests it, and commits

### Why Two Agents?

Without structure, agents tend to:
- Try to one-shot the entire app (too ambitious, context overflow)
- Declare the project complete prematurely
- Leave broken state for the next session
- Waste tokens re-discovering project state

The two-agent system solves this by:
- Separating environment setup from feature implementation
- Forcing one-feature-at-a-time incremental progress
- Using structured artifacts (progress file, feature list, git history) for cross-session continuity
- Requiring testing before marking features as done

## Initializer Agent

### When to Run
Run once at the start of the project, or after a major restructure.

### What It Does

1. **Creates the project skeleton** — Directory structure, `pyproject.toml`, `__init__.py` files
2. **Sets up the feature list** — `docs/FEATURES.json` with all features marked as `"passes": false`
3. **Creates `init.sh`** — Script that coding agents run at the start of every session
4. **Creates `claude-progress.txt`** — Session log that agents update after each session
5. **Makes the initial git commit** — Clean baseline to diff against
6. **Installs dependencies** — Creates virtual environment and installs `audio_analyzer` and dev deps

### Initializer Prompt Template

```
You are the initializer agent for the Rekordbox Creative project. Your job is
to set up the development environment, NOT to implement features.

Read all files in docs/ to understand the project.

Do the following:
1. Create the directory structure defined in docs/ARCHITECTURE.md
2. Create pyproject.toml with all dependencies
3. Create __init__.py and placeholder files for each module
4. Create init.sh (see docs/AGENT_WORKFLOWS.md for template)
5. Create claude-progress.txt with initial state
6. Set up the virtual environment and install dependencies
7. Run pytest to verify the skeleton works (empty tests pass)
8. Make an initial git commit: "chore: initialize project skeleton"

Do NOT implement any features. Only create scaffolding.
Do NOT modify docs/FEATURES.json — features start as failing.
```

## Coding Agent

### Session Startup Sequence

Every coding agent session begins with:

```
1. Run `pwd` to confirm working directory
2. Read `claude-progress.txt` for last session's state
3. Read `git log --oneline -20` for recent commits
4. Read `docs/FEATURES.json` to find next failing feature
5. Run `bash init.sh` to set up the environment
6. Run a quick smoke test: `pytest tests/ -x --timeout=10`
7. Pick ONE feature to implement this session
```

### Implementation Loop

```
For the chosen feature:
  1. Read the feature's description and steps from FEATURES.json
  2. Read relevant source files to understand current state
  3. Implement the feature
  4. Write tests for the feature
  5. Run the tests: `pytest tests/test_<module>.py -v`
  6. If tests fail, fix and re-run (up to 3 attempts)
  7. If tests pass, update FEATURES.json: set "passes": true
  8. Git commit with descriptive message
  9. Update claude-progress.txt with what was done
```

### Session Exit Checklist

Before ending a session, the coding agent must:

```
1. All tests pass: `pytest tests/ -v`
2. No uncommitted changes: `git status` shows clean
3. claude-progress.txt is updated with:
   - What was accomplished
   - What was attempted but not finished
   - Any blockers or issues discovered
   - Suggested next feature to work on
4. FEATURES.json reflects actual state (only mark passes:true if truly working)
```

### Coding Agent Prompt Template

```
You are a coding agent for the Rekordbox Creative project. Your job is to
implement exactly ONE feature per session.

STARTUP:
1. Run `pwd` to confirm you're in the project root
2. Read claude-progress.txt
3. Read git log --oneline -20
4. Read docs/FEATURES.json and find the next failing feature
5. Run bash init.sh
6. Run pytest tests/ -x --timeout=30

IMPLEMENT:
1. Pick the next failing feature (by ID order, or as suggested in progress file)
2. Read the feature description carefully
3. Implement it, write tests, verify it works
4. Run ALL tests to ensure nothing is broken

RULES:
- Implement exactly ONE feature per session
- Write tests for everything you implement
- Never remove or weaken existing tests
- Commit your work with a descriptive message
- Update claude-progress.txt before ending

If you get stuck on a feature after 3 attempts, document the issue in
claude-progress.txt and move to the next feature. Do not spend the entire
session on one blocker.
```

## `init.sh` Template

```bash
#!/bin/bash
# init.sh — Environment setup for coding agents
# Run at the start of every session

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
source .venv/bin/activate

# Install dependencies
echo "Installing dependencies..."
pip install -e ".[dev]" --quiet

# Verify audio_analyzer is available
python -c "from audio_analyzer import AudioAnalyzer; print('audio_analyzer: OK')"

# Run baseline tests
echo "Running baseline tests..."
pytest tests/ -x --timeout=30 -q

echo "=== Init complete. Ready to code. ==="
```

## `claude-progress.txt` Format

```
# Rekordbox Creative — Agent Progress Log
# Updated after each coding session

## Current State
- Last session: 2025-01-15
- Features passing: 5/62
- Last feature implemented: GRAPH-003 (Harmonic Scoring)
- Current blocker: None

## Session Log

### Session 5 — 2025-01-15
- Implemented: GRAPH-003 (Harmonic Scoring)
- Tests added: test_scoring.py::test_harmonic_same_key, test_harmonic_adjacent, test_harmonic_parallel, test_harmonic_wrapping
- Commit: abc1234 "feat: implement Camelot wheel harmonic scoring"
- Notes: Wrapping logic (12A → 1A) needed special handling
- Next suggested: GRAPH-004 (BPM Scoring)

### Session 4 — 2025-01-14
- Implemented: GRAPH-002 (Edge Computation)
- Tests added: test_scoring.py::test_edge_creation, test_edge_threshold
- Commit: def5678 "feat: edge computation with threshold filtering"
- Notes: Performance is fine for <1000 tracks. May need optimization later for 5000+
- Next suggested: GRAPH-003 (Harmonic Scoring)

...
```

## Feature Implementation Order

Recommended order to maximize incremental testability:

### Phase 1: Foundation (Features 1-10)
```
SCAN-001  Folder Selection
SCAN-002  Batch Analysis
SCAN-003  Analysis Caching
SCAN-004  Metadata Extraction
SCAN-005  Error Resilience
DB-001    SQLite Storage
DB-002    Track Persistence
GRAPH-001 Node Creation
GRAPH-002 Edge Computation
GRAPH-003 Harmonic Scoring
```

### Phase 2: Scoring & Graph (Features 11-20)
```
GRAPH-004 BPM Scoring
GRAPH-005 Full Compatibility Score
GRAPH-006 Clustering (Vibe Islands)
GRAPH-007 Force-Directed Layout
GRAPH-008 Scatter Map Layout
GRAPH-009 Greedy Pathfinding
GRAPH-010 2-Opt Improvement
SUG-001   Basic Suggestions
SUG-002   Sequence-Aware Suggestions
SUG-003   Harmonic Flow Strategy
```

### Phase 3: Advanced Suggestions (Features 21-30)
```
SUG-004   Energy Arc Strategy
SUG-005   Discovery Strategy
SUG-006   Groove Lock Strategy
SUG-007   Contrast Strategy
SUG-008   BPM Range Filter
SUG-009   Key Lock Filter
SUG-010   Diversity Bonus
SUG-011   Weight Customization
```

### Phase 4: Desktop UI (Features 31-50)
```
UI-001    App Window
UI-002    Node Graph Canvas
UI-003    Node Display
UI-004    Node Selection
UI-005    Node Dragging
UI-006    Edge Display
UI-007    Manual Edge Creation
UI-008    Track Inspector Panel
UI-009    Suggestion Panel
UI-010    Playlist Panel
UI-011    Track Swap
UI-012    Right-Click Context Menu
UI-013    Viewport Culling
UI-014    Search and Filter
UI-015    Layout Mode Switching
UI-016    Cluster Visualization
UI-017    Suggestion Highlighting
UI-018    Progress Bar During Analysis
```

### Phase 5: Set Building & Export (Features 51-58)
```
SET-001   Add to Sequence
SET-002   Reorder Sequence
SET-003   Remove from Sequence
SET-004   Auto-Order Sequence
SET-005   Set Segments / Chapters
EXP-001   M3U Export
EXP-002   Rekordbox XML Export
EXP-003   CSV Export
EXP-004   Save/Load Graph State
```

### Phase 6: Performance & Packaging (Features 59-62)
```
PERF-001  Large Library Handling
PERF-002  Incremental Edge Computation
PERF-003  Background Analysis
PKG-001   Standalone Executable (macOS)
PKG-002   Standalone Executable (Windows)
PREF-001  Settings Persistence
PREF-002  Edge Threshold Setting
```

## Agent Team Coordination (Multi-Agent)

For parallel development, use Claude Code agent teams. Recommended team structure:

### Team Structure

```
Lead Agent (Coordinator)
├── Backend Agent — analysis layer, database, graph engine, suggestions
├── Frontend Agent — UI layer, canvas, panels, interactions
└── QA Agent — testing, integration validation, performance checks
```

### CLAUDE.md for Team Context

Each agent needs the full project context. The CLAUDE.md file should be checked in so all agents inherit it. Additionally:

- **Backend Agent**: Point to `docs/ARCHITECTURE.md`, `docs/ALGORITHM_SPEC.md`, `docs/DATA_MODELS.md`
- **Frontend Agent**: Point to `docs/UI_SPEC.md`, `docs/DATA_MODELS.md`
- **QA Agent**: Point to `docs/FEATURES.json`, all test files

### Task Assignment Rules

- Each agent owns a non-overlapping set of files
- Backend: `src/rekordbox_creative/analysis/`, `db/`, `graph/`, `suggestions/`
- Frontend: `src/rekordbox_creative/ui/`
- QA: `tests/`
- Avoid two agents editing the same file (causes merge conflicts)
- Use the shared task list for coordination

### Agent Communication Patterns

- Backend → Frontend: "TrackStore API is ready at `db.get_track(id)`, returns `Track` model"
- Frontend → Backend: "Need a method `suggestions.get_top_n(track_id, config) -> list[SuggestionResult]`"
- QA → Both: "Feature GRAPH-003 test is failing: harmonic_score('12A', '1A') returns 0.1 instead of 0.85"

## Testing Strategy

### Unit Tests
Each scoring function, each model, each database operation gets its own test.

```
tests/
├── test_scoring.py          # Harmonic, BPM, energy, groove, frequency, mix quality
├── test_clustering.py       # DBSCAN clustering, label generation
├── test_pathfinding.py      # Greedy, 2-opt, constraints
├── test_suggestions.py      # Suggestion engine, strategies, filters
├── test_scanner.py          # File discovery, format filtering
├── test_export.py           # M3U, Rekordbox XML, CSV output
├── test_database.py         # CRUD operations, caching
├── test_models.py           # Pydantic model validation
└── conftest.py              # Shared fixtures (mock tracks, mock analysis results)
```

### Fixtures

```python
# conftest.py
@pytest.fixture
def mock_track_a():
    """A 128 BPM, 8A, high-energy four-on-floor track."""
    return Track(
        file_path="/music/track_a.mp3",
        file_hash="abc123",
        filename="track_a.mp3",
        duration_seconds=360.0,
        spotify_style=SpotifyStyleMetrics(
            energy=0.82, danceability=0.75, acousticness=0.03,
            instrumentalness=0.65, valence=0.58, liveness=0.12
        ),
        dj_metrics=DJMetrics(
            bpm=128.0, bpm_stability=0.97, key="8A", key_confidence=0.85,
            mix_in_score=0.90, mix_out_score=0.85,
            frequency_weight="bass_heavy", groove_type="four_on_floor"
        ),
        structure=TrackStructure(drops=[64.2, 192.5])
    )

@pytest.fixture
def mock_track_b():
    """A 127 BPM, 9A, medium-energy four-on-floor track — compatible with A."""
    return Track(
        file_path="/music/track_b.mp3",
        file_hash="def456",
        filename="track_b.mp3",
        duration_seconds=340.0,
        spotify_style=SpotifyStyleMetrics(
            energy=0.70, danceability=0.72, acousticness=0.05,
            instrumentalness=0.80, valence=0.50, liveness=0.08
        ),
        dj_metrics=DJMetrics(
            bpm=127.0, bpm_stability=0.95, key="9A", key_confidence=0.90,
            mix_in_score=0.85, mix_out_score=0.80,
            frequency_weight="balanced", groove_type="four_on_floor"
        ),
        structure=TrackStructure(drops=[60.0, 180.0])
    )
```

### Test Commands

```bash
# Run all tests
pytest tests/ -v

# Run a single test file
pytest tests/test_scoring.py -v

# Run a specific test
pytest tests/test_scoring.py::test_harmonic_same_key -v

# Run with coverage
pytest tests/ --cov=src/rekordbox_creative --cov-report=term-missing

# Run fast (skip slow integration tests)
pytest tests/ -v -m "not slow"
```
