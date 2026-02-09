# Implementation Roadmap

A phase-by-phase build plan for all 62 features from `FEATURES.json`. Each phase has dependencies satisfied by earlier phases. Agent assignments follow `.claude/agents/`.

For implementation details, see: `ALGORITHM_SPEC.md` (formulas), `DATA_MODELS.md` (models/schema), `ARCHITECTURE.md` (structure), `UI_SPEC.md` (design).

---

## Progress Tracker

| Phase | Name | Features | Status |
|-------|------|----------|--------|
| 0 | Project Skeleton | — | Complete |
| 1 | Data Models & Storage | 2 features | Complete (2/2) |
| 2 | Analysis Pipeline | 5 features | Complete (5/5) |
| 3 | Scoring Engine | 3 features | Complete (3/3) |
| 4 | Graph Engine Core | 5 features | Complete (5/5) |
| 5 | Suggestion Engine | 11 features | Complete (11/11) |
| 6 | Desktop UI Shell | 8 features | Not started |
| 7 | UI Interaction & Panels | 10 features | Not started |
| 8 | Set Building & Export | 9 features | Partial (4/9 — EXP done, SET not started) |
| 9 | Performance & Optimization | 3 features | Not started |
| 10 | Preferences & Polish | 2 features | Not started |
| 11 | Packaging & Distribution | 2 features | Not started |
| **Total** | | **62 features** | **32/62 passing** |

---

## Phase 0: Project Skeleton

**Agent**: `initializer` | **Duration**: 1 session

Create directory structure per `ARCHITECTURE.md`, `pyproject.toml`, placeholder files, `conftest.py` with mock fixtures, empty test files, venv, verify `pytest` and `ruff` pass, initial git commit.

**Exit criteria**: `bash init.sh` works, all modules importable, no features marked passing.

---

## Phase 1: Data Models & Storage

**Agent**: `backend` | **Duration**: 2 sessions | **Depends on**: Phase 0

### DB-001 — SQLite Storage
- **Files**: `db/database.py`, `db/models.py`, `tests/test_database.py`, `tests/test_models.py`
- **Blocks**: DB-002, SCAN-003, every feature that reads/writes data
- Implement all Pydantic models from `DATA_MODELS.md`, Database class with CRUD for tracks/edges, SQLite schema from `DATA_MODELS.md`

### DB-002 — Track Persistence
- **Files**: `db/cache.py`, `tests/test_database.py`
- **Depends on**: DB-001 | **Blocks**: SCAN-003, GRAPH-001
- CacheManager (is_cached, get_cached_track, invalidate_track), playlist persistence, file-based DB round-trip tests

---

## Phase 2: Analysis Pipeline

**Agent**: `backend` | **Duration**: 5 sessions | **Depends on**: Phase 1

| Feature | Files | Depends on | Blocks |
|---------|-------|------------|--------|
| SCAN-001 Folder Selection | `analysis/scanner.py`, `tests/test_scanner.py` | Phase 0 | SCAN-002, SCAN-005 |
| SCAN-002 Batch Analysis | `analysis/processor.py`, `tests/test_scanner.py` | SCAN-001 | SCAN-003, GRAPH-001 |
| SCAN-004 Metadata Extraction | `analysis/metadata.py`, `tests/test_scanner.py` | SCAN-001 | UI-008 |
| SCAN-005 Error Resilience | `analysis/processor.py`, `tests/test_scanner.py` | SCAN-002 | — |
| SCAN-003 Analysis Caching | `analysis/cache_manager.py`, `tests/test_scanner.py` | SCAN-002, DB-002 | PERF-002 |

Key classes: `AudioScanner` (recursive file discovery), `AudioProcessor` (wraps audio_analyzer, batch + progress callback), `MetadataExtractor` (mutagen), `AnalysisCacheManager` (MD5 hash filtering).

---

## Phase 3: Scoring Engine

**Agent**: `backend` | **Duration**: 3 sessions | **Depends on**: Phase 1 (models)

> **Critical**: Every formula must match `ALGORITHM_SPEC.md` exactly. See `.claude/rules/backend/scoring.md`.

| Feature | Depends on | Blocks |
|---------|------------|--------|
| GRAPH-003 Harmonic Scoring | Phase 1 | GRAPH-005 |
| GRAPH-004 BPM Scoring | Phase 1 | GRAPH-005 |
| GRAPH-005 Full Compatibility | GRAPH-003, GRAPH-004 | GRAPH-002, SUG-001, all edge/suggestion features |

**Files**: `graph/scoring.py`, `tests/test_scoring.py`

Implements: `harmonic_score`, `bpm_score`, `energy_score`, `groove_score`, `frequency_score`, `mix_quality_score`, `compute_compatibility`. All scoring rules, lookup tables, and confidence modifiers defined in `ALGORITHM_SPEC.md`.

---

## Phase 4: Graph Engine Core

**Agent**: `backend` | **Duration**: 5 sessions | **Depends on**: Phase 3

| Feature | Files | Depends on | Blocks |
|---------|-------|------------|--------|
| GRAPH-001 Node Creation | `graph/graph.py` | DB-002 | GRAPH-002 |
| GRAPH-002 Edge Computation | `graph/graph.py` | GRAPH-001, GRAPH-005 | GRAPH-006/007, SUG-001 |
| GRAPH-006 Clustering | `graph/clustering.py`, `tests/test_clustering.py` | GRAPH-001 | SUG-010, UI-016 |
| GRAPH-007 Force Layout | `graph/layout.py` | GRAPH-002 | UI-002, UI-015 |
| GRAPH-008 Scatter Layout | `graph/layout.py` | GRAPH-001 | UI-015 |
| GRAPH-009+010 Pathfinding | `graph/pathfinding.py`, `tests/test_pathfinding.py` | GRAPH-005 | SET-004 |

Key classes: `TrackGraph` (NetworkX DiGraph wrapper with add/remove/compute_edges), clustering via DBSCAN, layouts via spring_layout + t-SNE/UMAP, pathfinding via greedy + 2-opt.

---

## Phase 5: Suggestion Engine

**Agent**: `backend` | **Duration**: 8 sessions | **Depends on**: Phase 3, Phase 4 (clustering)

| Feature | Depends on | Key detail |
|---------|------------|------------|
| SUG-001 Basic Suggestions | GRAPH-005 | `SuggestionEngine.suggest()` pipeline, blocks all SUG-* |
| SUG-002 Sequence-Aware | SUG-001 | Context modifier: penalize repeat key/cluster/groove |
| SUG-003 Harmonic Flow | SUG-001 | Default strategy, modifier = 1.0 |
| SUG-004 Energy Arc | SUG-001 | Target energy by set position (build/peak/cooldown) |
| SUG-005 Discovery | SUG-001 | Boost by times_used (0→1.3x, <3→1.15x) |
| SUG-006 Groove Lock | SUG-001 | Same groove 1.2x, different 0.6x |
| SUG-007 Contrast | SUG-001 | Reward energy/frequency differences |
| SUG-008 BPM Range Filter | SUG-001 | Filter by bpm_min/bpm_max |
| SUG-009 Key Lock Filter | SUG-001, GRAPH-003 | Only harmonically compatible keys |
| SUG-010 Diversity Bonus | SUG-001, GRAPH-006 | Boost tracks from different clusters |
| SUG-011 Weight Customization | SUG-001 | Respect custom weights via normalized_weights() |

**Files**: `suggestions/engine.py`, `suggestions/strategies.py`, `suggestions/filters.py`, `tests/test_suggestions.py`

All strategy formulas defined in `ALGORITHM_SPEC.md`.

---

## Phase 6: Desktop UI Shell

**Agent**: `frontend` | **Duration**: 6 sessions | **Depends on**: Phase 4

> **Decision required before Phase 6**: Choose GUI framework (PyQt6 / Dear PyGui / CustomTkinter). See `UI_SPEC.md`.

| Feature | Depends on | Blocks |
|---------|------------|--------|
| UI-001 App Window | GUI decision | All UI features |
| UI-002 Canvas | UI-001, GRAPH-007 | UI-003/004/006/013/014/015/016 |
| UI-003 Node Display | UI-002 | UI-004 |
| UI-006 Edge Display | UI-002 | PREF-002 |
| UI-004 Node Selection | UI-003 | UI-005/007/008/009/012 |
| UI-005 Node Dragging | UI-004 | UI-007 |
| UI-018 Progress Bar | UI-001, SCAN-002 | PERF-003 |
| UI-013 Viewport Culling | UI-002 | PERF-001 |

**Files**: `ui/app.py`, `ui/canvas.py`, `ui/nodes.py`, `ui/edges.py`, `__main__.py`

Design spec in `UI_SPEC.md`: dark theme, Camelot color wheel, energy-based node sizing, edge thickness by compatibility.

---

## Phase 7: UI Interaction & Panels

**Agent**: `frontend` | **Duration**: 10 sessions | **Depends on**: Phase 6

| Feature | Depends on |
|---------|------------|
| UI-008 Inspector Panel | UI-004 |
| UI-009 Suggestion Panel | UI-004, SUG-001 |
| UI-010 Playlist Panel | UI-001 |
| UI-017 Suggestion Highlighting | UI-009 |
| UI-007 Manual Edge Creation | UI-005 |
| UI-011 Track Swap | UI-010, SUG-001 |
| UI-012 Context Menu | UI-004 |
| UI-014 Search & Filter | UI-002 |
| UI-015 Layout Switching | UI-002, GRAPH-007/008 |
| UI-016 Cluster Visualization | UI-002, GRAPH-006 |

**Files**: `ui/panels/` (inspector, suggestions, playlist, settings), `ui/dialogs/`

Panel layouts defined in `UI_SPEC.md`.

---

## Phase 8: Set Building & Export

**Agent**: `backend` (export) + `frontend` (UI) | **Duration**: 7 sessions | **Depends on**: Phase 5, Phase 7

| Feature | Agent | Depends on |
|---------|-------|------------|
| SET-001 Add to Sequence | frontend + backend | UI-010 |
| SET-002 Reorder Sequence | frontend | SET-001 |
| SET-003 Remove from Sequence | frontend | SET-001 |
| SET-004 Auto-Order | backend + frontend | SET-001, GRAPH-009/010 |
| SET-005 Set Segments | frontend | SET-001 |
| EXP-001 M3U Export | backend | SET-001 |
| EXP-002 Rekordbox XML Export | backend | SET-001 |
| EXP-003 CSV Export | backend | DB-001 |
| EXP-004 Save/Load Graph State | backend + frontend | UI-002, SET-001 |

**Files**: `export/m3u.py`, `export/rekordbox.py`, `export/csv.py`, `export/playlist.py`, `tests/test_export.py`

---

## Phase 9: Performance & Optimization

**Agent**: `backend` + `frontend` | **Duration**: 3 sessions | **Depends on**: Phase 8

| Feature | Depends on | Key detail |
|---------|------------|------------|
| PERF-001 Large Library | All core | SQLite indexing, BPM/key pre-filter, viewport culling, LOD. Target: 5000+ tracks in <3s |
| PERF-002 Incremental Edges | GRAPH-002, SCAN-003 | Compute only new_tracks x all_tracks |
| PERF-003 Background Analysis | SCAN-002, UI-018 | Background thread, thread-safe progress callback |

---

## Phase 10: Preferences & Polish

**Agent**: `backend` + `frontend` | **Duration**: 2 sessions | **Depends on**: Phase 8

| Feature | Depends on |
|---------|------------|
| PREF-001 Settings Persistence | DB-001, SUG-011 |
| PREF-002 Edge Threshold Setting | UI-006, PREF-001 |

---

## Phase 11: Packaging & Distribution

**Agent**: `backend` | **Duration**: 2 sessions | **Depends on**: All features

- **PKG-001** macOS: PyInstaller `.app` bundle
- **PKG-002** Windows: PyInstaller `.exe`

---

## Dependency Graph

```
Phase 0 (Skeleton)
  ├──► Phase 1 (DB)
  │      ├──► Phase 2 (Analysis) ──────────────────┐
  │      └──► Phase 3 (Scoring)                     │
  │              ├──► Phase 4 (Graph)                │
  │              │      └──► Phase 5 (Suggestions) ◄┘
  │              └──► Phase 6 (UI Shell)
  │                     └──► Phase 7 (UI Panels)
  │                            └──► Phase 8 (Set/Export)
  │                                   └──► Phase 9 (Perf)
  │                                          └──► Phase 10 (Prefs)
  │                                                 └──► Phase 11 (Packaging)
```

**Critical path**: Skeleton → DB-001 → DB-002 → GRAPH-003 → GRAPH-004 → GRAPH-005 → GRAPH-002 → SUG-001 → UI-001 → UI-002 → UI-004 → UI-009 → SET-001 → PERF-001 → PREF-001 → PKG-001

**Parallelization**: Phase 2 & 3 parallel (both need Phase 1), SUG-003-011 parallel (all need SUG-001 only), Phase 7 panels mostly independent, backend & frontend parallel once APIs defined.

---

## Milestones

| Milestone | Phases | Features | What works |
|-----------|--------|----------|------------|
| "It Calculates" | 0-3 | 10 | Models, DB, all 6 scoring functions |
| "It Graphs" | +4 | 18 | Nodes, edges, clusters, layouts, pathfinding |
| "It Suggests" | +2,5 | 30 | Analysis, caching, 5 strategies, filters |
| "It Renders" | +6,7 | 48 | Desktop GUI, canvas, panels, interactions |
| "It Ships" | +8-11 | 62 | Export, performance, preferences, executables |

---

## Session Planning Guide

| Session | Feature | Agent | Complexity |
|---------|---------|-------|------------|
| 1 | Phase 0: Skeleton | initializer | Medium |
| 2 | DB-001: SQLite Storage | backend | Medium |
| 3 | DB-002: Track Persistence | backend | Low |
| 4 | GRAPH-003: Harmonic Scoring | backend | Medium |
| 5 | GRAPH-004: BPM Scoring | backend | Medium |
| 6 | GRAPH-005: Full Compatibility | backend | High |
| 7 | SCAN-001: Folder Selection | backend | Low |
| 8 | SCAN-002: Batch Analysis | backend | Medium |
| 9 | SCAN-004: Metadata Extraction | backend | Low |
| 10 | SCAN-005: Error Resilience | backend | Low |
| 11 | SCAN-003: Analysis Caching | backend | Medium |
| 12 | GRAPH-001: Node Creation | backend | Low |
| 13 | GRAPH-002: Edge Computation | backend | High |
| 14 | GRAPH-006: Clustering | backend | Medium |
| 15 | GRAPH-007: Force Layout | backend | Medium |
| 16 | GRAPH-008: Scatter Layout | backend | Medium |
| 17 | GRAPH-009+010: Pathfinding | backend | Medium |
| 18 | SUG-001: Basic Suggestions | backend | High |
| 19 | SUG-002: Sequence-Aware | backend | Medium |
| 20 | SUG-003: Harmonic Flow | backend | Low |
| 21 | SUG-004: Energy Arc | backend | Medium |
| 22 | SUG-005: Discovery | backend | Low |
| 23 | SUG-006: Groove Lock | backend | Low |
| 24 | SUG-007: Contrast | backend | Low |
| 25 | SUG-008+009: Filters | backend | Low |
| 26 | SUG-010: Diversity Bonus | backend | Low |
| 27 | SUG-011: Weight Customization | backend | Low |
| 28 | **GUI Framework Decision** | research | — |
| 29-36 | UI Shell (001-005, 006, 013, 018) | frontend | Mixed |
| 37-46 | UI Panels & Interaction | frontend | Mixed |
| 47-51 | Set Building (SET-001-005) | frontend | Mixed |
| 52-55 | Export (EXP-001-004) | backend | Mixed |
| 56-58 | Performance (PERF-001-003) | both | High |
| 59-60 | Preferences (PREF-001-002) | both | Medium |
| 61-62 | Packaging (PKG-001-002) | backend | High |

---

## Risk Register

| Risk | Impact | Mitigation |
|------|--------|------------|
| `audio_analyzer` API mismatch | High | Research agent validates API before Phase 2 |
| GUI framework choice delays UI | High | Decide in session 28 with prototype spikes |
| Edge computation O(n^2) | Medium | Pre-filter BPM/key, threshold, incremental |
| PyInstaller bundling failures | Medium | Test packaging early (Phase 6) |
| DBSCAN parameter sensitivity | Low | Expose eps/min_samples as config |
| Cross-platform GUI differences | Medium | Choose framework with strong cross-platform support |

---

## Testing Strategy

| Type | Location | When |
|------|----------|------|
| Unit | `tests/test_*.py` | Every session |
| Model validation | `tests/test_models.py` | Phase 1+ |
| Scoring | `tests/test_scoring.py` | Phase 3+ |
| Integration | `tests/test_database.py` | Phase 1+ (`:memory:` SQLite) |
| Suggestions | `tests/test_suggestions.py` | Phase 5+ |
| Export | `tests/test_export.py` | Phase 8+ |
| Performance | `tests/test_performance.py` | Phase 9 (`@pytest.mark.slow`) |
| Full regression | `pytest tests/ -v` | Every session exit (stop hook) |
| Lint | `ruff check src/ tests/` | Every file save (lint hook) |
