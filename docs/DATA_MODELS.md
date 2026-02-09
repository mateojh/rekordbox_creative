# Data Models Specification

## Overview

All data models are defined as Pydantic v2 models for validation and serialization. The database layer uses SQLite with these models mapped to tables.

## Core Models

### Track

The central entity. One per audio file.

```python
from pydantic import BaseModel, Field
from uuid import UUID, uuid4
from datetime import datetime
from typing import Optional

class SpotifyStyleMetrics(BaseModel):
    """Normalized 0.0-1.0 audio feature scores."""
    energy: float = Field(ge=0.0, le=1.0, description="Perceived intensity and activity")
    danceability: float = Field(ge=0.0, le=1.0, description="Suitability for dancing")
    acousticness: float = Field(ge=0.0, le=1.0, description="Confidence track is acoustic")
    instrumentalness: float = Field(ge=0.0, le=1.0, description="Confidence no vocals present")
    valence: float = Field(ge=0.0, le=1.0, description="Musical positiveness/happiness")
    liveness: float = Field(ge=0.0, le=1.0, description="Presence of audience")

class DJMetrics(BaseModel):
    """DJ-specific analysis results."""
    bpm: float = Field(gt=0, description="Beats per minute")
    bpm_stability: float = Field(ge=0.0, le=1.0, description="Tempo consistency")
    key: str = Field(pattern=r"^\d{1,2}[AB]$", description="Camelot notation (e.g. '8A')")
    key_confidence: float = Field(ge=0.0, le=1.0, description="Key detection confidence")
    mix_in_score: float = Field(ge=0.0, le=1.0, description="Intro mix-friendliness")
    mix_out_score: float = Field(ge=0.0, le=1.0, description="Outro mix-friendliness")
    frequency_weight: str = Field(description="bass_heavy | bright | mid_focused | balanced")
    groove_type: str = Field(description="four_on_floor | breakbeat | half_time | complex | syncopated | straight")

class TrackStructure(BaseModel):
    """Structural landmarks in the track (timestamps in seconds)."""
    drops: list[float] = Field(default_factory=list, description="Drop timestamps")
    breakdowns: list[list[float]] = Field(default_factory=list, description="[start, end] pairs")
    vocal_segments: list[list[float]] = Field(default_factory=list, description="[start, end] pairs")
    build_sections: list[list[float]] = Field(default_factory=list, description="[start, end] pairs")
    intro_end: Optional[float] = Field(None, description="Where intro ends")
    outro_start: Optional[float] = Field(None, description="Where outro begins")

class TrackMetadata(BaseModel):
    """ID3/file metadata."""
    artist: Optional[str] = None
    title: Optional[str] = None
    album: Optional[str] = None
    genre: Optional[str] = None
    year: Optional[int] = None
    track_number: Optional[int] = None
    comment: Optional[str] = None

class Track(BaseModel):
    """Complete track entity with all analysis data."""
    id: UUID = Field(default_factory=uuid4)
    file_path: str
    file_hash: str                          # MD5 of file content
    filename: str                           # Basename for display
    duration_seconds: float
    sample_rate: int = 22050

    # Analysis results
    spotify_style: SpotifyStyleMetrics
    dj_metrics: DJMetrics
    structure: TrackStructure

    # File metadata
    metadata: TrackMetadata = Field(default_factory=TrackMetadata)

    # Graph state (not persisted in analysis, set by graph engine)
    cluster_id: Optional[int] = None
    times_used: int = 0                     # How many times added to playlists
    analyzed_at: datetime = Field(default_factory=datetime.now)

    class Config:
        frozen = False  # Mutable for graph state updates
```

### Edge

Directional compatibility between two tracks.

```python
class EdgeScores(BaseModel):
    """Breakdown of compatibility components."""
    harmonic: float = Field(ge=0.0, le=1.0)
    bpm: float = Field(ge=0.0, le=1.0)
    energy: float = Field(ge=0.0, le=1.0)
    groove: float = Field(ge=0.0, le=1.0)
    frequency: float = Field(ge=0.0, le=1.0)
    mix_quality: float = Field(ge=0.0, le=1.0)

class Edge(BaseModel):
    """Weighted directional edge between two tracks."""
    id: UUID = Field(default_factory=uuid4)
    source_id: UUID                         # Track A (outgoing)
    target_id: UUID                         # Track B (incoming)
    compatibility_score: float = Field(ge=0.0, le=1.0)  # Weighted aggregate
    scores: EdgeScores                      # Component breakdown
    is_user_created: bool = False           # Manually drawn by user
```

### Cluster

A group of sonically similar tracks (vibe island).

```python
class Cluster(BaseModel):
    """A vibe island — group of sonically similar tracks."""
    id: int
    label: str                              # Auto-generated label
    track_ids: list[UUID]
    centroid: list[float]                   # Center of cluster in feature space

    # Aggregate stats for display
    avg_bpm: float
    avg_energy: float
    dominant_key: str
    dominant_groove: str
    dominant_frequency_weight: str
    track_count: int
```

### Playlist / Set

An ordered sequence of tracks.

```python
class SetSegment(BaseModel):
    """A named chapter/segment within a set."""
    name: str                               # e.g., "Opener", "Peak Time"
    start_position: int                     # Index in playlist
    end_position: int                       # Index in playlist (inclusive)

class Playlist(BaseModel):
    """An ordered set of tracks with metadata."""
    id: UUID = Field(default_factory=uuid4)
    name: str
    track_ids: list[UUID]                   # Ordered track IDs
    segments: list[SetSegment] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

    # Computed stats
    total_duration: float = 0.0             # Sum of track durations
    avg_compatibility: float = 0.0          # Average edge score between consecutive tracks
    total_compatibility: float = 0.0        # Sum of consecutive edge scores
```

### GraphState

Serializable snapshot of the entire UI state.

```python
class NodePosition(BaseModel):
    """Canvas position of a node."""
    track_id: UUID
    x: float
    y: float

class ViewportState(BaseModel):
    """Camera/viewport state."""
    center_x: float = 0.0
    center_y: float = 0.0
    zoom: float = 1.0

class GraphState(BaseModel):
    """Complete serializable graph state for save/load."""
    node_positions: list[NodePosition]
    viewport: ViewportState
    active_playlist_id: Optional[UUID] = None
    layout_mode: str = "force_directed"     # force_directed | scatter | linear
    color_mode: str = "key"                 # key | cluster | energy
    edge_threshold: float = 0.3
    selected_node_ids: list[UUID] = Field(default_factory=list)
```

### SuggestionConfig

User-configurable suggestion parameters.

```python
from enum import Enum

class SuggestionStrategy(str, Enum):
    HARMONIC_FLOW = "harmonic_flow"
    ENERGY_ARC = "energy_arc"
    DISCOVERY = "discovery"
    GROOVE_LOCK = "groove_lock"
    CONTRAST = "contrast"

class SuggestionConfig(BaseModel):
    """User-tunable suggestion behavior."""
    # Scoring weights (must sum to 1.0)
    harmonic_weight: float = 0.30
    bpm_weight: float = 0.25
    energy_weight: float = 0.15
    groove_weight: float = 0.10
    frequency_weight: float = 0.10
    mix_quality_weight: float = 0.10

    # Active strategy
    strategy: SuggestionStrategy = SuggestionStrategy.HARMONIC_FLOW

    # Filters
    bpm_min: Optional[float] = None
    bpm_max: Optional[float] = None
    key_lock: bool = False
    groove_lock: bool = False
    exclude_cluster_ids: list[int] = Field(default_factory=list)

    # Output
    num_suggestions: int = 8
    diversity_bonus: float = 0.1

    def normalized_weights(self) -> dict[str, float]:
        """Return weights normalized to sum to 1.0."""
        total = (self.harmonic_weight + self.bpm_weight + self.energy_weight +
                 self.groove_weight + self.frequency_weight + self.mix_quality_weight)
        return {
            'harmonic': self.harmonic_weight / total,
            'bpm': self.bpm_weight / total,
            'energy': self.energy_weight / total,
            'groove': self.groove_weight / total,
            'frequency': self.frequency_weight / total,
            'mix_quality': self.mix_quality_weight / total,
        }
```

### Suggestion Result

What the suggestion engine returns.

```python
class SuggestionResult(BaseModel):
    """A single track suggestion with scoring breakdown."""
    track_id: UUID
    final_score: float                      # After strategy modifiers
    base_compatibility: float               # Raw compatibility score
    strategy_modifier: float                # Strategy-specific boost/penalty
    context_modifier: float                 # Sequence context adjustment
    diversity_bonus: float                  # Cluster diversity boost
    score_breakdown: EdgeScores             # Component-level scores
```

## Camelot Wheel Reference Data

```python
CAMELOT_KEYS = {
    # Minor keys (A)
    "1A": "Ab minor",  "2A": "Eb minor",  "3A": "Bb minor",
    "4A": "F minor",   "5A": "C minor",   "6A": "G minor",
    "7A": "D minor",   "8A": "A minor",   "9A": "E minor",
    "10A": "B minor",  "11A": "F# minor", "12A": "Db minor",
    # Major keys (B)
    "1B": "B major",   "2B": "F# major",  "3B": "Db major",
    "4B": "Ab major",  "5B": "Eb major",  "6B": "Bb major",
    "7B": "F major",   "8B": "C major",   "9B": "G major",
    "10B": "D major",  "11B": "A major",  "12B": "E major",
}

# Compatible keys for each Camelot position
# Same key + adjacent (+/-1) + parallel (A↔B)
def compatible_keys(key: str) -> list[str]:
    num, mode = int(key[:-1]), key[-1]
    prev_num = 12 if num == 1 else num - 1
    next_num = 1 if num == 12 else num + 1
    other_mode = "B" if mode == "A" else "A"
    return [
        key,                           # Same
        f"{prev_num}{mode}",          # -1 same mode
        f"{next_num}{mode}",          # +1 same mode
        f"{num}{other_mode}",         # Parallel
    ]
```

## Groove Type Compatibility Matrix

```python
GROOVE_COMPATIBILITY: dict[tuple[str, str], float] = {
    # Same type = perfect match
    ("four_on_floor", "four_on_floor"): 1.0,
    ("breakbeat", "breakbeat"):         1.0,
    ("half_time", "half_time"):         1.0,
    ("complex", "complex"):             1.0,
    ("syncopated", "syncopated"):       1.0,
    ("straight", "straight"):           1.0,

    # Good matches
    ("four_on_floor", "straight"):      0.7,
    ("breakbeat", "syncopated"):        0.7,
    ("breakbeat", "complex"):           0.6,

    # Moderate matches
    ("four_on_floor", "half_time"):     0.5,
    ("straight", "half_time"):          0.5,
    ("syncopated", "complex"):          0.5,

    # Poor matches
    ("four_on_floor", "breakbeat"):     0.3,
    ("four_on_floor", "syncopated"):    0.3,
    ("half_time", "breakbeat"):         0.3,
    ("straight", "syncopated"):         0.3,

    # Bad matches
    ("four_on_floor", "complex"):       0.2,
    ("half_time", "complex"):           0.2,
    ("half_time", "syncopated"):        0.2,
    ("straight", "complex"):            0.2,
    ("straight", "breakbeat"):          0.3,
}
```

## Frequency Weight Compatibility Matrix

```python
FREQUENCY_COMPATIBILITY: dict[tuple[str, str], float] = {
    # Same = perfect
    ("bass_heavy", "bass_heavy"):       1.0,
    ("bright", "bright"):               1.0,
    ("mid_focused", "mid_focused"):     1.0,
    ("balanced", "balanced"):           1.0,

    # Balanced transitions well to anything
    ("balanced", "bass_heavy"):         0.7,
    ("balanced", "bright"):             0.7,
    ("balanced", "mid_focused"):        0.7,

    # Mid transitions moderately
    ("mid_focused", "bass_heavy"):      0.5,
    ("mid_focused", "bright"):          0.5,

    # Extremes clash
    ("bass_heavy", "bright"):           0.3,
}
```

## SQLite Schema

```sql
CREATE TABLE IF NOT EXISTS tracks (
    id TEXT PRIMARY KEY,
    file_path TEXT UNIQUE NOT NULL,
    file_hash TEXT NOT NULL,
    filename TEXT NOT NULL,
    duration_seconds REAL NOT NULL,
    sample_rate INTEGER DEFAULT 22050,

    -- Spotify-style (0-1)
    energy REAL, danceability REAL, acousticness REAL,
    instrumentalness REAL, valence REAL, liveness REAL,

    -- DJ metrics
    bpm REAL, bpm_stability REAL,
    key_camelot TEXT, key_confidence REAL,
    mix_in_score REAL, mix_out_score REAL,
    frequency_weight TEXT, groove_type TEXT,

    -- Structural (JSON)
    structure_json TEXT,

    -- Metadata (JSON)
    metadata_json TEXT,

    -- Graph state
    cluster_id INTEGER,
    times_used INTEGER DEFAULT 0,
    analyzed_at TEXT NOT NULL
);

CREATE INDEX idx_tracks_bpm ON tracks(bpm);
CREATE INDEX idx_tracks_key ON tracks(key_camelot);
CREATE INDEX idx_tracks_energy ON tracks(energy);
CREATE INDEX idx_tracks_file_hash ON tracks(file_hash);
CREATE INDEX idx_tracks_cluster ON tracks(cluster_id);

CREATE TABLE IF NOT EXISTS edges (
    id TEXT PRIMARY KEY,
    source_id TEXT NOT NULL REFERENCES tracks(id),
    target_id TEXT NOT NULL REFERENCES tracks(id),
    compatibility_score REAL NOT NULL,
    harmonic_score REAL, bpm_score REAL, energy_score REAL,
    groove_score REAL, frequency_score REAL, mix_quality_score REAL,
    is_user_created INTEGER DEFAULT 0,
    UNIQUE(source_id, target_id)
);

CREATE INDEX idx_edges_source ON edges(source_id);
CREATE INDEX idx_edges_target ON edges(target_id);
CREATE INDEX idx_edges_score ON edges(compatibility_score);

CREATE TABLE IF NOT EXISTS playlists (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    graph_state_json TEXT
);

CREATE TABLE IF NOT EXISTS playlist_tracks (
    playlist_id TEXT NOT NULL REFERENCES playlists(id),
    track_id TEXT NOT NULL REFERENCES tracks(id),
    position INTEGER NOT NULL,
    PRIMARY KEY(playlist_id, track_id)
);

CREATE TABLE IF NOT EXISTS preferences (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL
);
```
