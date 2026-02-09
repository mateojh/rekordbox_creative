# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

Rekordbox Creative is a desktop application (executable, not web-based) that provides a node-based playlist suggestion algorithm for DJs. Users point the app at a local folder of audio files, the app analyzes them using audio feature extraction, and presents an interactive node graph where songs can be connected, swapped, and intelligently suggested based on musical compatibility.

Inspired by Djoid.io's graph playlist and scatter map concepts, but built as a standalone desktop app.

## Core Concepts

- **Node Graph**: Songs are nodes in a visual graph. Edges represent compatibility/transition quality between tracks. Users drag, connect, and rearrange nodes to build sets.
- **Audio Analysis**: Powered by the `audio_analyzer` library (github.com/samuelih/audio_analyzer) which extracts Spotify-style metrics (energy, danceability, valence, etc.), DJ metrics (BPM, key in Camelot notation, mix-in/out scores, groove type), and structural data (drops, breakdowns, vocal segments).
- **Smart Suggestions**: The algorithm recommends next tracks based on harmonic compatibility (Camelot wheel adjacency), BPM proximity, energy flow, and genre/vibe clustering.
- **Local-first**: All processing happens locally. No cloud services. Audio files never leave the user's machine.

## Architecture

The app has four major layers:

1. **Analysis Layer** — Wraps `audio_analyzer` to batch-process a user's music folder, cache results, and expose track metadata as structured data.
2. **Graph Engine** — Manages the node graph data structure: nodes (tracks), edges (compatibility scores), clusters (vibe islands), and pathfinding for set flow optimization.
3. **Suggestion Algorithm** — Scores candidate tracks against the current graph state using weighted compatibility across BPM, key, energy, frequency weight, groove type, and mix-in/out scores.
4. **UI Layer** — Desktop GUI rendering the interactive node graph, track inspector, suggestion panel, and playlist export.

## Audio Analysis Output Format

Each analyzed track produces this structure (from `audio_analyzer`):

```json
{
  "spotify_style": { "energy": 0.82, "danceability": 0.75, "acousticness": 0.03, "instrumentalness": 0.65, "valence": 0.58, "liveness": 0.12 },
  "dj_metrics": { "bpm": 128.0, "bpm_stability": 0.97, "key": "8A", "key_confidence": 0.85, "mix_in_score": 0.90, "mix_out_score": 0.85, "frequency_weight": "bass_heavy", "groove_type": "four_on_floor" },
  "structure": { "drops": [64.2, 192.5], "breakdowns": [[96.0, 128.0]], "vocal_segments": [[32.0, 64.0]], "build_sections": [[48.0, 64.0]], "intro_end": 16.0, "outro_start": 320.0 }
}
```

## Key Compatibility Rules (Camelot Wheel)

- **Same key**: Perfect match (e.g., 8A → 8A)
- **Adjacent keys**: +/- 1 on the wheel (e.g., 7A → 8A → 9A)
- **Parallel keys**: Same number, different letter (e.g., 8A ↔ 8B)
- BPM transitions should stay within ±6% for smooth mixing

## Tech Stack

- **Language**: Python 3.10+
- **Audio Analysis**: `audio_analyzer` (librosa, numpy, scipy, scikit-learn)
- **Desktop GUI**: TBD — candidates include PyQt6, Dear PyGui, or Tauri+Python
- **Graph Data**: NetworkX or custom graph structure
- **Database**: SQLite (zero-config, single-file, ships with Python)
- **Clustering**: scikit-learn DBSCAN (already a dependency of audio_analyzer)
- **Metadata**: mutagen (reads ID3, FLAC, MP4, Ogg tags)
- **Packaging**: PyInstaller or cx_Freeze for executable distribution

## Commands

```bash
# Session setup (run at the start of every session)
bash init.sh

# Run all tests
pytest tests/ -v

# Run a single test file
pytest tests/test_scoring.py -v

# Run a specific test
pytest tests/test_scoring.py::test_harmonic_same_key -v

# Run with coverage
pytest tests/ --cov=src/rekordbox_creative --cov-report=term-missing

# Lint
ruff check src/ tests/

# Lint and fix
ruff check src/ tests/ --fix

# Install in dev mode
pip install -e ".[dev]"
```

## Session Protocol

Every coding session must follow this sequence:

1. `bash init.sh` — Set up venv, install deps, run baseline tests
2. Read `claude-progress.txt` — Understand current state
3. Read `docs/FEATURES.json` — Find the next failing feature
4. Implement ONE feature — Write code + tests
5. `pytest tests/ -v` — Verify everything passes
6. `git commit` — Clean commit with descriptive message
7. Update `claude-progress.txt` — Log what was done

See @docs/AGENT_WORKFLOWS.md for full details on the two-agent development pattern (initializer + coding agent) based on [Anthropic's effective harnesses for long-running agents](https://www.anthropic.com/engineering/effective-harnesses-for-long-running-agents).

## Specialized Agents

Five agents are defined in `.claude/agents/` for team-based development:

| Agent | Model | Role | Owns |
|-------|-------|------|------|
| `backend` | inherit | Analysis, DB, graph, suggestions, export | `src/rekordbox_creative/{analysis,db,graph,suggestions,export}/` |
| `frontend` | inherit | Desktop GUI, canvas, panels, dialogs | `src/rekordbox_creative/ui/` |
| `qa` | haiku | Testing, validation, regression checks | `tests/` |
| `researcher` | haiku | Codebase exploration, bug investigation | Read-only |
| `initializer` | inherit | Project scaffolding (first run only) | Setup files |

### Agent Coordination Rules

- Each agent owns **non-overlapping files** to prevent merge conflicts
- Backend exposes APIs that frontend consumes — never the reverse
- QA validates after implementation — it reads but never writes source code
- Agents have persistent memory in `.claude/agent-memory/` for cross-session knowledge
- Use the shared task list for cross-agent coordination

## Hooks

Two hooks enforce quality gates (configured in `.claude/settings.json`):

- **Lint on save** (`PostToolUse` → `Write|Edit`): Runs `ruff check` on any Python file after write/edit. Lint warnings are returned as context. Script: `.claude/hooks/lint-on-save.sh`
- **Test on stop** (`Stop`): Before an agent can stop, verifies (1) all tests pass via `pytest tests/ -x --timeout=30` and (2) no uncommitted changes via `git status`. Blocks stop if either check fails. Script: `.claude/hooks/verify-tests-on-stop.sh`

## Path-Specific Rules

Rules in `.claude/rules/` are scoped by file path — they only load when working on matching files:

| Rule File | Scope | Key Constraints |
|-----------|-------|-----------------|
| `code-style.md` | Global | Python 3.10+ syntax, Pydantic v2, type hints, pathlib.Path, 100-char lines |
| `testing.md` | Global | Edge case testing, no removing tests, in-memory SQLite for DB tests |
| `agent-workflow.md` | Global | ONE feature per session, match spec formulas exactly |
| `backend/scoring.md` | `graph/scoring.py`, `test_scoring.py` | Exact algorithm spec formulas, Camelot wrapping, BPM half/double |
| `backend/database.md` | `db/**`, `test_database.py` | SQLite schema from DATA_MODELS.md, UUIDs as TEXT, JSON blobs |
| `backend/analysis.md` | `analysis/**`, `test_scanner.py` | Wrap audio_analyzer, MD5 cache, continue_on_error=True |
| `frontend/ui-guidelines.md` | `ui/**` | Dark theme colors, node size/energy, edge thickness/compat, viewport culling |

## Settings Configuration

Permissions and hooks are defined in `.claude/settings.json`:

- **Auto-allowed**: `pytest`, `ruff`, `pip`, `git status/log/diff`, `python -c`, `bash init.sh`, `Read`, `Glob`, `Grep`
- **Requires approval**: `Write`, `Edit`, `git commit/push`, `Bash` (other commands)

## Scoring Quick-Reference

| Component | Weight | Key Rule |
|-----------|--------|----------|
| Harmonic | 0.30 | Camelot wheel: same=1.0, adjacent=0.85, parallel=0.80, 2-step=0.5, other=0.1 |
| BPM | 0.25 | ±2%=1.0, ±4%=0.8, ±6%=0.5, half/double=0.6 |
| Energy | 0.15 | Smooth: ±0.10=1.0, ±0.20=0.8, ±0.35=0.5 |
| Groove | 0.10 | Same=1.0, lookup table for cross-type |
| Frequency | 0.10 | Same=1.0, balanced→any=0.7, extremes clash=0.3 |
| Mix Quality | 0.10 | (mix_out_A + mix_in_B) / 2.0 — directional |

## Documentation Index

- @docs/PROJECT_OVERVIEW.md — Vision, scope, target users, success criteria
- @docs/ARCHITECTURE.md — System layers, data flow, directory structure, tech decisions
- @docs/ALGORITHM_SPEC.md — Scoring formulas, suggestion engine, clustering, pathfinding
- @docs/UI_SPEC.md — Window layout, color system, panels, keyboard shortcuts
- @docs/DATA_MODELS.md — Pydantic models, SQLite schema, compatibility matrices
- @docs/FEATURES.json — 62 granular features with test steps (agent tracking)
- @docs/AGENT_WORKFLOWS.md — Two-agent system, prompts, testing strategy, implementation order
- @docs/IMPLEMENTATION_ROADMAP.md — Phase-by-phase build plan with dependencies and milestones

## Key File Locations

```
CLAUDE.md                          # This file — top-level project context
claude-progress.txt                # Session continuity log (agents update after each session)
init.sh                            # Session bootstrap script (venv, deps, baseline tests)
docs/FEATURES.json                 # 62 features, agents toggle "passes" field only
.claude/CLAUDE.md                  # Supplementary agent architecture instructions
.claude/agents/                    # Agent definitions (backend, frontend, qa, researcher, initializer)
.claude/rules/                     # Path-scoped rules (code-style, testing, scoring, db, analysis, ui)
.claude/hooks/                     # Quality gate scripts (lint-on-save, verify-tests-on-stop)
.claude/settings.json              # Permissions and hook configuration
src/rekordbox_creative/            # Main source code (analysis, db, graph, suggestions, export, ui)
tests/                             # Test suite (one file per module + conftest fixtures)
```
 