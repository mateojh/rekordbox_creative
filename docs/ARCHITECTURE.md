# System Architecture

## High-Level Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                      Desktop Application                         │
│                                                                  │
│  ┌──────────────┐  ┌──────────────┐  ┌───────────────────────┐  │
│  │   UI Layer    │  │  Suggestion  │  │    Export Layer        │  │
│  │  (Node Graph  │◄─│   Engine     │  │  (Playlist/Rekordbox) │  │
│  │   Canvas)     │  │              │  │                       │  │
│  └──────┬───────┘  └──────┬───────┘  └───────────┬───────────┘  │
│         │                 │                       │              │
│  ┌──────▼─────────────────▼───────────────────────▼───────────┐  │
│  │                    Graph Engine                             │  │
│  │  (Nodes, Edges, Clusters, Pathfinding, Scoring)            │  │
│  └──────────────────────┬─────────────────────────────────────┘  │
│                         │                                        │
│  ┌──────────────────────▼─────────────────────────────────────┐  │
│  │                   Analysis Layer                            │  │
│  │  (audio_analyzer wrapper, batch processing, cache)          │  │
│  └──────────────────────┬─────────────────────────────────────┘  │
│                         │                                        │
│  ┌──────────────────────▼─────────────────────────────────────┐  │
│  │                   Data Layer                                │  │
│  │  (SQLite DB, analysis cache, user preferences)              │  │
│  └────────────────────────────────────────────────────────────┘  │
│                                                                  │
└─────────────────────────────────────────────────────────────────┘
                          │
                   ┌──────▼──────┐
                   │ Local Audio  │
                   │   Files      │
                   │ (MP3/FLAC/   │
                   │  WAV/etc.)   │
                   └─────────────┘
```

## Layer Details

### Layer 1: Data Layer

**Purpose**: Persistent storage of analysis results, graph state, and user preferences.

**Components**:
- `db/database.py` — SQLite connection management and migrations
- `db/models.py` — ORM models (Track, Edge, Cluster, Playlist, UserPreference)
- `db/cache.py` — Analysis result cache keyed by file hash + modification time

**Key Design Decisions**:
- SQLite chosen for zero-configuration desktop deployment (single file, no server)
- File hash-based cache invalidation: re-analyze only when files change
- Database file stored alongside user's music folder or in app data directory
- Schema supports multiple library folders per user

**Schema Overview**:
```
tracks
  ├── id (UUID)
  ├── file_path (TEXT, unique)
  ├── file_hash (TEXT) — MD5 of file content
  ├── filename (TEXT)
  ├── duration_seconds (REAL)
  ├── bpm (REAL)
  ├── bpm_stability (REAL)
  ├── key_camelot (TEXT) — e.g., "8A"
  ├── key_confidence (REAL)
  ├── energy (REAL)
  ├── danceability (REAL)
  ├── valence (REAL)
  ├── acousticness (REAL)
  ├── instrumentalness (REAL)
  ├── liveness (REAL)
  ├── mix_in_score (REAL)
  ├── mix_out_score (REAL)
  ├── frequency_weight (TEXT)
  ├── groove_type (TEXT)
  ├── structure_json (TEXT) — JSON blob for drops, breakdowns, etc.
  ├── analyzed_at (TIMESTAMP)
  └── metadata_json (TEXT) — ID3 tags, artist, title, etc.

edges
  ├── id (UUID)
  ├── source_track_id (FK → tracks)
  ├── target_track_id (FK → tracks)
  ├── compatibility_score (REAL, 0-1)
  ├── harmonic_score (REAL)
  ├── bpm_score (REAL)
  ├── energy_score (REAL)
  ├── groove_score (REAL)
  ├── frequency_score (REAL)
  └── is_user_created (BOOLEAN) — user manually connected

playlists
  ├── id (UUID)
  ├── name (TEXT)
  ├── created_at (TIMESTAMP)
  └── graph_state_json (TEXT) — serialized node positions, zoom, etc.

playlist_tracks
  ├── playlist_id (FK → playlists)
  ├── track_id (FK → tracks)
  └── position (INTEGER)
```

### Layer 2: Analysis Layer

**Purpose**: Bridge between raw audio files and the structured track data the graph engine needs.

**Components**:
- `analysis/scanner.py` — Discovers audio files in a directory (recursive, filters by extension)
- `analysis/processor.py` — Wraps `audio_analyzer.AudioAnalyzer` for single and batch processing
- `analysis/cache_manager.py` — Checks file hashes against DB to skip already-analyzed tracks
- `analysis/metadata.py` — Extracts ID3/metadata tags (artist, title, album) using mutagen

**Data Flow**:
```
User selects folder
  → scanner.py finds all audio files (MP3, WAV, FLAC, OGG, M4A, AAC)
  → cache_manager.py filters out already-analyzed (by file hash)
  → processor.py runs audio_analyzer.analyze_batch() on remaining files
  → Results stored in SQLite via data layer
  → Edge computation triggered for new tracks
```

**Key Design Decisions**:
- Batch processing with progress callbacks for UI progress bars
- `continue_on_error=True` so one corrupt file doesn't block the whole library
- Cache invalidation by MD5 hash — moving files doesn't re-trigger analysis
- Metadata extraction separate from audio analysis (fast, can run first to show track names immediately)

### Layer 3: Graph Engine

**Purpose**: The computational heart. Manages the graph data structure and all algorithms that operate on it.

**Components**:
- `graph/graph.py` — Core graph structure (nodes, edges, adjacency)
- `graph/scoring.py` — Compatibility scoring functions between track pairs
- `graph/clustering.py` — Vibe island detection (DBSCAN or spectral clustering on feature vectors)
- `graph/pathfinding.py` — Optimal set ordering through selected nodes
- `graph/layout.py` — Force-directed and scatter map layout algorithms

**Compatibility Scoring** (in `scoring.py`):

```python
def compute_compatibility(track_a, track_b) -> float:
    """
    Weighted compatibility score between two tracks.
    Returns 0.0 (incompatible) to 1.0 (perfect match).
    """
    weights = {
        'harmonic': 0.30,    # Camelot key compatibility
        'bpm': 0.25,         # Tempo proximity
        'energy': 0.15,      # Energy level similarity
        'groove': 0.10,      # Groove type match
        'frequency': 0.10,   # Frequency weight compatibility
        'mix_quality': 0.10, # Mix-out of A × mix-in of B
    }
```

**Harmonic Scoring Rules**:
```
Same key (8A → 8A):           1.0
Adjacent key (8A → 7A/9A):    0.85
Parallel key (8A → 8B):       0.80
Two steps away (8A → 6A/10A): 0.5
Incompatible:                  0.1
```

**BPM Scoring**:
```
Within ±2%:   1.0
Within ±4%:   0.8
Within ±6%:   0.5
Beyond ±6%:   0.1 (unless half/double time detected)
Half/double:  0.6 (e.g., 128 → 64 or 128 → 256)
```

**Clustering** (in `clustering.py`):
- Feature vector per track: [energy, danceability, valence, bpm_normalized, acousticness, instrumentalness]
- DBSCAN with cosine distance to find natural groupings
- Clusters become labeled "vibe islands" in the UI

**Pathfinding** (in `pathfinding.py`):
- Given a set of selected nodes, find the ordering that maximizes total edge compatibility
- This is a variant of the Traveling Salesman Problem
- Use greedy nearest-neighbor heuristic for speed, with optional 2-opt improvement
- Support constraints: "start with track X" or "end with track Y"

**Layout Algorithms** (in `layout.py`):
- **Force-directed**: Nodes repel each other, edges attract. Compatible tracks cluster naturally.
- **Scatter map**: 2D projection of feature vectors using t-SNE or UMAP. Proximity = sonic similarity.
- **Linear**: Sequential layout for playlist/set view

### Layer 4: Suggestion Engine

**Purpose**: Recommends the best next track(s) given the current graph state.

**Components**:
- `suggestions/engine.py` — Core suggestion logic
- `suggestions/strategies.py` — Pluggable suggestion strategies (harmonic, energy arc, discovery)
- `suggestions/filters.py` — User-configurable filters (BPM range, key lock, genre, exclude played)

**Suggestion Strategies**:

1. **Harmonic Flow** — Prioritize Camelot-compatible keys, prefer tracks that maintain or gently shift the tonal center
2. **Energy Arc** — Build toward a peak: suggest tracks that incrementally increase (or decrease) energy based on set position
3. **Discovery** — Surface underplayed or forgotten tracks that still score well on compatibility
4. **Groove Lock** — Stay in the same groove type (four-on-floor → four-on-floor)
5. **Contrast** — Intentionally suggest tracks that differ (breakdown after peak, acoustic after electronic)

**Suggestion Flow**:
```
Current track (or last N tracks in sequence)
  → Candidate pool: all tracks not in current sequence
  → Apply user filters (BPM range, key lock, etc.)
  → Score each candidate against current track
  → Apply active strategy weighting
  → Rank and return top 5-10 suggestions
  → Include diversity bonus for tracks from different clusters
```

### Layer 5: UI Layer

**Purpose**: Desktop GUI presenting the node graph canvas and all user interaction.

**Components**:
- `ui/app.py` — Application entry point and window management
- `ui/canvas.py` — Node graph canvas (pan, zoom, drag)
- `ui/nodes.py` — Track node rendering (color-coded by key/energy/cluster)
- `ui/edges.py` — Edge rendering (thickness = compatibility, color = type)
- `ui/panels/` — Side panels (track inspector, suggestions, playlist, settings)
- `ui/dialogs/` — File picker, export, preferences

**Interaction Model**:
- Click node → Select track, show details in inspector panel
- Drag node → Reposition on canvas
- Draw edge (drag from node port) → Manually connect two tracks
- Right-click node → Context menu (add to playlist, find similar, remove)
- Double-click canvas → Add track from library browser
- Scroll → Zoom canvas
- Middle-click drag → Pan canvas

### Layer 6: Export Layer

**Purpose**: Convert graph selections/playlists into formats other DJ software can import.

**Components**:
- `export/playlist.py` — Generic ordered playlist export
- `export/m3u.py` — M3U/M3U8 playlist format
- `export/rekordbox.py` — Rekordbox XML playlist format
- `export/csv.py` — CSV export with all analysis data

## Data Flow: End-to-End

```
1. USER: Selects music folder
2. SCANNER: Finds 2,847 audio files
3. CACHE: 2,500 already analyzed, 347 new
4. ANALYZER: Processes 347 new tracks (progress bar)
5. DATABASE: Stores 347 new analysis results
6. SCORING: Computes compatibility for 347 new × 2,847 total pairs
7. CLUSTERING: Re-runs clustering on full library
8. LAYOUT: Computes initial node positions
9. UI: Renders graph with 2,847 nodes, shows clusters
10. USER: Clicks a track node
11. SUGGESTION: Scores all candidates, returns top 10
12. UI: Highlights suggested tracks with glow effect
13. USER: Drags suggested track to sequence
14. SUGGESTION: Re-computes suggestions for new tail
15. USER: Exports 20-track sequence as Rekordbox playlist
```

## Performance Considerations

- **Edge computation is O(n²)**: For 5,000 tracks, that's 25 million pairs. Pre-compute only edges above a minimum compatibility threshold (0.3). Store in DB, lazy-compute the rest.
- **Clustering**: Run once on library load, incrementally update when new tracks added.
- **UI rendering**: Only render visible nodes (viewport culling). Use level-of-detail: show full node detail when zoomed in, simplified dots when zoomed out.
- **Analysis**: The bottleneck. `audio_analyzer` processes ~30-60 seconds per track depending on duration. For 1,000 new tracks, expect 8-16 hours. Support background processing with pause/resume.
- **Database**: SQLite handles 10,000+ tracks with proper indexing on bpm, key_camelot, energy.

## Technology Stack Decisions

| Component | Choice | Rationale |
|-----------|--------|-----------|
| Language | Python 3.10+ | Matches `audio_analyzer`, rich ecosystem for audio/ML/GUI |
| Audio analysis | `audio_analyzer` | Purpose-built for DJ metrics, open source |
| Database | SQLite | Zero-config, single-file, ships with Python |
| Graph library | NetworkX | Mature, well-documented, handles 10K+ nodes |
| GUI framework | TBD (see UI_SPEC.md) | PyQt6, Tauri, or Electron candidates |
| Clustering | scikit-learn DBSCAN | Already a dependency of audio_analyzer |
| Layout | Custom force-directed | Fine-tuned for music compatibility distances |
| Packaging | PyInstaller | Single executable, bundles Python runtime |
| Metadata | mutagen | Reads ID3, FLAC, MP4, Ogg tags |

## Directory Structure (Target)

```
rekordbox_creative/
├── CLAUDE.md
├── README.md
├── pyproject.toml
├── init.sh
├── claude-progress.txt
├── docs/
│   ├── PROJECT_OVERVIEW.md
│   ├── ARCHITECTURE.md
│   ├── ALGORITHM_SPEC.md
│   ├── UI_SPEC.md
│   ├── DATA_MODELS.md
│   ├── AGENT_WORKFLOWS.md
│   └── FEATURES.json
├── .claude/
│   └── rules/
│       ├── code-style.md
│       ├── testing.md
│       └── agent-workflow.md
├── src/
│   └── rekordbox_creative/
│       ├── __init__.py
│       ├── __main__.py
│       ├── app.py
│       ├── analysis/
│       │   ├── __init__.py
│       │   ├── scanner.py
│       │   ├── processor.py
│       │   ├── cache_manager.py
│       │   └── metadata.py
│       ├── db/
│       │   ├── __init__.py
│       │   ├── database.py
│       │   ├── models.py
│       │   └── cache.py
│       ├── graph/
│       │   ├── __init__.py
│       │   ├── graph.py
│       │   ├── scoring.py
│       │   ├── clustering.py
│       │   ├── pathfinding.py
│       │   └── layout.py
│       ├── suggestions/
│       │   ├── __init__.py
│       │   ├── engine.py
│       │   ├── strategies.py
│       │   └── filters.py
│       ├── export/
│       │   ├── __init__.py
│       │   ├── playlist.py
│       │   ├── m3u.py
│       │   ├── rekordbox.py
│       │   └── csv.py
│       └── ui/
│           ├── __init__.py
│           ├── app.py
│           ├── canvas.py
│           ├── nodes.py
│           ├── edges.py
│           ├── panels/
│           │   ├── __init__.py
│           │   ├── inspector.py
│           │   ├── suggestions.py
│           │   ├── playlist.py
│           │   └── settings.py
│           └── dialogs/
│               ├── __init__.py
│               ├── folder_picker.py
│               └── export.py
└── tests/
    ├── __init__.py
    ├── conftest.py
    ├── test_scoring.py
    ├── test_clustering.py
    ├── test_pathfinding.py
    ├── test_suggestions.py
    ├── test_scanner.py
    ├── test_export.py
    └── fixtures/
        └── sample_analysis.json
```
