# Node-Based Playlist Suggestion Algorithm Specification

## Overview

The suggestion algorithm operates on a weighted graph where tracks are nodes and edges represent musical compatibility. It answers the question: **"Given the current state of the DJ's set, what should come next?"**

## Graph Structure

### Nodes

Each node contains the full analysis output from `audio_analyzer`:

```
Node {
    track_id: UUID
    file_path: string

    # Core DJ metrics
    bpm: float              # 60-200
    bpm_stability: float    # 0-1
    key: string             # Camelot notation ("8A", "12B", etc.)
    key_confidence: float   # 0-1

    # Scoring inputs
    energy: float           # 0-1
    danceability: float     # 0-1
    valence: float          # 0-1
    instrumentalness: float # 0-1
    mix_in_score: float     # 0-1
    mix_out_score: float    # 0-1
    frequency_weight: enum  # bass_heavy | bright | mid_focused | balanced
    groove_type: enum       # four_on_floor | breakbeat | half_time | complex | syncopated | straight

    # Structural
    drops: float[]
    vocal_segments: [float, float][]
    intro_end: float
    outro_start: float

    # Graph state
    position: (x, y)       # Canvas position
    cluster_id: int?        # Assigned vibe island
    is_in_sequence: bool    # Currently part of the active set
    sequence_position: int? # Position in set (0-indexed)
}
```

### Edges

Edges are directional (A → B may score differently than B → A because mix-out of A combines with mix-in of B):

```
Edge {
    source_id: UUID
    target_id: UUID

    # Component scores (each 0-1)
    harmonic_score: float
    bpm_score: float
    energy_score: float
    groove_score: float
    frequency_score: float
    mix_quality_score: float

    # Aggregate
    compatibility_score: float  # Weighted sum

    # Metadata
    is_user_created: bool       # Manually connected by user
}
```

## Compatibility Scoring Algorithm

### 1. Harmonic Score (weight: 0.30)

Uses the Camelot Wheel to determine key compatibility.

**Camelot Wheel Reference**:
```
Inner ring (minor):  1A  2A  3A  4A  5A  6A  7A  8A  9A  10A  11A  12A
Outer ring (major):  1B  2B  3B  4B  5B  6B  7B  8B  9B  10B  11B  12B
```

**Scoring**:
```python
def harmonic_score(key_a: str, key_b: str) -> float:
    num_a, mode_a = parse_camelot(key_a)  # "8A" → (8, "A")
    num_b, mode_b = parse_camelot(key_b)

    # Same key
    if key_a == key_b:
        return 1.0

    # Parallel key (same number, different mode: 8A ↔ 8B)
    if num_a == num_b and mode_a != mode_b:
        return 0.8

    # Adjacent key (±1 on wheel, same mode: 7A ↔ 8A ↔ 9A)
    if mode_a == mode_b and camelot_distance(num_a, num_b) == 1:
        return 0.85

    # Two steps away
    if mode_a == mode_b and camelot_distance(num_a, num_b) == 2:
        return 0.5

    # Diagonal (adjacent number + mode switch)
    if mode_a != mode_b and camelot_distance(num_a, num_b) == 1:
        return 0.4

    # Everything else
    return 0.1

def camelot_distance(a: int, b: int) -> int:
    """Distance on circular Camelot wheel (1-12, wrapping)."""
    return min(abs(a - b), 12 - abs(a - b))
```

**Key Confidence Modifier**: Multiply harmonic_score by `min(key_conf_a, key_conf_b)` when confidence < 0.7 to reduce weight of uncertain key detections.

### 2. BPM Score (weight: 0.25)

```python
def bpm_score(bpm_a: float, bpm_b: float) -> float:
    ratio = max(bpm_a, bpm_b) / min(bpm_a, bpm_b)
    pct_diff = abs(ratio - 1.0)

    # Check half/double time
    half_double_ratio = max(bpm_a, bpm_b) / min(bpm_a, bpm_b)
    if 1.95 <= half_double_ratio <= 2.05:
        return 0.6  # Halftime/doubletime transition viable

    if pct_diff <= 0.02:    # Within 2%
        return 1.0
    elif pct_diff <= 0.04:  # Within 4%
        return 0.8
    elif pct_diff <= 0.06:  # Within 6% (DJ pitch range)
        return 0.5
    elif pct_diff <= 0.10:  # Within 10%
        return 0.2
    else:
        return 0.05
```

**BPM Stability Modifier**: If either track has `bpm_stability < 0.8`, reduce the BPM score by 20% — unstable BPM makes beatmatching unreliable.

### 3. Energy Score (weight: 0.15)

Measures energy compatibility. Supports two modes:

```python
def energy_score(energy_a: float, energy_b: float, mode: str = "smooth") -> float:
    diff = abs(energy_a - energy_b)

    if mode == "smooth":
        # Prefer gradual transitions (±0.15 energy)
        if diff <= 0.10:
            return 1.0
        elif diff <= 0.20:
            return 0.8
        elif diff <= 0.35:
            return 0.5
        else:
            return 0.2

    elif mode == "arc":
        # In arc mode, score based on desired direction
        # Handled by the strategy layer, not here
        return 1.0 - diff
```

### 4. Groove Score (weight: 0.10)

```python
GROOVE_COMPAT = {
    ("four_on_floor", "four_on_floor"): 1.0,
    ("four_on_floor", "straight"):      0.7,
    ("breakbeat", "breakbeat"):         1.0,
    ("breakbeat", "syncopated"):        0.7,
    ("half_time", "half_time"):         1.0,
    ("half_time", "four_on_floor"):     0.5,
    # ... symmetric pairs
}

def groove_score(groove_a: str, groove_b: str) -> float:
    pair = (groove_a, groove_b)
    return GROOVE_COMPAT.get(pair, GROOVE_COMPAT.get((groove_b, groove_a), 0.3))
```

### 5. Frequency Weight Score (weight: 0.10)

```python
FREQ_COMPAT = {
    ("bass_heavy", "bass_heavy"):    1.0,
    ("bass_heavy", "balanced"):      0.7,
    ("bass_heavy", "bright"):        0.3,  # Jarring transition
    ("bright", "bright"):            1.0,
    ("balanced", "balanced"):        1.0,
    ("mid_focused", "mid_focused"):  1.0,
    ("balanced", "bright"):          0.7,
    ("balanced", "mid_focused"):     0.7,
    # ... symmetric pairs
}

def frequency_score(freq_a: str, freq_b: str) -> float:
    pair = (freq_a, freq_b)
    return FREQ_COMPAT.get(pair, FREQ_COMPAT.get((freq_b, freq_a), 0.5))
```

### 6. Mix Quality Score (weight: 0.10)

Directional — depends on the mix-out quality of track A and mix-in quality of track B:

```python
def mix_quality_score(mix_out_a: float, mix_in_b: float) -> float:
    """Average of outgoing track's mix-out friendliness and
    incoming track's mix-in friendliness."""
    return (mix_out_a + mix_in_b) / 2.0
```

### Aggregate Compatibility

```python
def compute_compatibility(track_a, track_b) -> float:
    scores = {
        'harmonic':    harmonic_score(track_a.key, track_b.key),
        'bpm':         bpm_score(track_a.bpm, track_b.bpm),
        'energy':      energy_score(track_a.energy, track_b.energy),
        'groove':      groove_score(track_a.groove_type, track_b.groove_type),
        'frequency':   frequency_score(track_a.frequency_weight, track_b.frequency_weight),
        'mix_quality': mix_quality_score(track_a.mix_out_score, track_b.mix_in_score),
    }

    weights = {
        'harmonic': 0.30, 'bpm': 0.25, 'energy': 0.15,
        'groove': 0.10, 'frequency': 0.10, 'mix_quality': 0.10
    }

    return sum(scores[k] * weights[k] for k in weights)
```

## Suggestion Engine

### Input Context

The engine receives:
1. **Current track** — The track the user just selected or the tail of their sequence
2. **Sequence history** — All tracks already in the set (ordered)
3. **Active strategy** — Which suggestion approach to use
4. **User filters** — BPM range, key lock, genre filter, etc.

### Suggestion Pipeline

```
Step 1: Build candidate pool
  → All tracks NOT in current sequence
  → Remove tracks filtered by user settings

Step 2: Apply user filters
  → BPM range filter (e.g., 125-132 only)
  → Key lock filter (only harmonically compatible keys)
  → Groove type filter
  → Cluster/genre filter

Step 3: Score each candidate
  → Compute compatibility with current track
  → Apply active strategy modifier
  → Apply sequence context modifier (avoid repeating patterns)

Step 4: Diversity bonus
  → Boost tracks from different clusters than last 3 played
  → Boost tracks with different frequency weight than last played
  → Boost underplayed/less-selected tracks (discovery bonus)

Step 5: Rank and return
  → Sort by final score descending
  → Return top N suggestions (default: 8)
  → Include score breakdown for transparency
```

### Strategy Modifiers

**Harmonic Flow** (default):
```python
# Standard behavior, no modification to base scores
modifier = 1.0
```

**Energy Arc**:
```python
# target_energy based on position in set
set_progress = sequence_position / estimated_set_length  # 0.0 to 1.0

if set_progress < 0.3:
    target_energy = 0.5 + (set_progress * 0.5)   # Build up: 0.5 → 0.65
elif set_progress < 0.7:
    target_energy = 0.7 + (set_progress * 0.3)   # Peak: 0.7 → 0.91
else:
    target_energy = 0.9 - ((set_progress - 0.7) * 1.5)  # Cool down: 0.9 → 0.45

energy_fit = 1.0 - abs(candidate.energy - target_energy)
modifier = 0.5 + (0.5 * energy_fit)  # Scale to 0.5-1.0
```

**Discovery**:
```python
# Boost tracks never or rarely added to playlists
if candidate.times_used == 0:
    modifier = 1.3  # 30% boost for never-used tracks
elif candidate.times_used < 3:
    modifier = 1.15  # 15% boost for rarely-used
else:
    modifier = 1.0
```

**Groove Lock**:
```python
if candidate.groove_type == current_track.groove_type:
    modifier = 1.2
else:
    modifier = 0.6  # Penalize groove changes
```

**Contrast**:
```python
energy_diff = abs(candidate.energy - current_track.energy)
if energy_diff > 0.3:
    modifier = 1.2  # Reward energy contrast
freq_diff = candidate.frequency_weight != current_track.frequency_weight
if freq_diff:
    modifier *= 1.1  # Reward frequency variety
```

### Sequence Context Modifiers

Prevent repetitive suggestions by analyzing the recent history:

```python
def sequence_context_modifier(candidate, last_n_tracks: list) -> float:
    modifier = 1.0

    # Penalize same key as last 2 tracks (variety)
    recent_keys = [t.key for t in last_n_tracks[-2:]]
    if candidate.key in recent_keys:
        modifier *= 0.8

    # Penalize same cluster as last 3 tracks
    recent_clusters = [t.cluster_id for t in last_n_tracks[-3:]]
    if candidate.cluster_id in recent_clusters:
        modifier *= 0.85

    # Penalize same groove as last 4 tracks (even in groove lock mode, nudge variety)
    recent_grooves = [t.groove_type for t in last_n_tracks[-4:]]
    if all(g == candidate.groove_type for g in recent_grooves):
        modifier *= 0.9

    return modifier
```

## Clustering Algorithm (Vibe Islands)

### Feature Vector Construction

Each track is represented as a 7-dimensional vector:

```python
def track_to_vector(track) -> np.ndarray:
    return np.array([
        track.energy,
        track.danceability,
        track.valence,
        track.bpm / 200.0,          # Normalize to 0-1 range
        track.acousticness,
        track.instrumentalness,
        groove_to_numeric(track.groove_type),  # Ordinal encoding
    ])
```

### Clustering Process

```python
from sklearn.cluster import DBSCAN
from sklearn.preprocessing import StandardScaler

vectors = np.array([track_to_vector(t) for t in all_tracks])
scaled = StandardScaler().fit_transform(vectors)

clustering = DBSCAN(
    eps=0.5,              # Neighborhood radius
    min_samples=3,        # Minimum cluster size
    metric='cosine'       # Cosine distance for feature comparison
)

labels = clustering.fit_predict(scaled)
# labels[i] = cluster_id for track i, -1 = noise/unclustered
```

### Cluster Labeling

Auto-generate cluster labels from dominant characteristics:
```python
def label_cluster(tracks_in_cluster) -> str:
    avg_energy = mean(t.energy for t in tracks_in_cluster)
    avg_bpm = mean(t.bpm for t in tracks_in_cluster)
    dominant_groove = mode(t.groove_type for t in tracks_in_cluster)
    dominant_freq = mode(t.frequency_weight for t in tracks_in_cluster)

    # Example output: "High Energy 128 BPM Four-on-Floor Bass-Heavy"
    energy_label = "High Energy" if avg_energy > 0.7 else "Mid Energy" if avg_energy > 0.4 else "Low Energy"
    return f"{energy_label} {int(avg_bpm)} BPM {dominant_groove.replace('_', ' ').title()} {dominant_freq.replace('_', ' ').title()}"
```

## Pathfinding: Optimal Set Ordering

Given N selected tracks, find the ordering that maximizes total transition quality.

### Greedy Nearest-Neighbor

```python
def greedy_order(tracks: list, start: Track = None) -> list:
    """O(n²) greedy approach — fast, good enough for most sets."""
    remaining = set(tracks)
    current = start or max(remaining, key=lambda t: t.energy)  # Start with highest energy if no preference
    ordered = [current]
    remaining.remove(current)

    while remaining:
        best = max(remaining, key=lambda t: compute_compatibility(current, t))
        ordered.append(best)
        remaining.remove(best)
        current = best

    return ordered
```

### 2-Opt Improvement

```python
def two_opt_improve(ordered: list, max_iterations: int = 1000) -> list:
    """Improve greedy solution by swapping pairs."""
    improved = True
    iteration = 0

    while improved and iteration < max_iterations:
        improved = False
        for i in range(1, len(ordered) - 1):
            for j in range(i + 1, len(ordered)):
                # Try reversing the segment between i and j
                new_order = ordered[:i] + ordered[i:j+1][::-1] + ordered[j+1:]
                if total_compatibility(new_order) > total_compatibility(ordered):
                    ordered = new_order
                    improved = True
        iteration += 1

    return ordered
```

## Edge Precomputation Strategy

Computing all pairs is O(n²). For 5,000 tracks = 25 million edges. Strategy:

1. **Filter by BPM**: Only compute edges where BPM is within ±10% (halves the space)
2. **Filter by key**: Only compute edges for harmonically compatible keys (reduces by ~70%)
3. **Threshold**: Only store edges with compatibility > 0.3
4. **Lazy computation**: Compute edges for newly added tracks against existing library incrementally
5. **Background processing**: Edge computation runs in a background thread after initial analysis completes

Expected edge count after filtering: ~2-5% of all possible pairs, manageable in SQLite.

## User-Adjustable Parameters

Users can tune the suggestion behavior:

```python
class SuggestionConfig:
    # Weight overrides (must sum to 1.0, rebalanced automatically)
    harmonic_weight: float = 0.30
    bpm_weight: float = 0.25
    energy_weight: float = 0.15
    groove_weight: float = 0.10
    frequency_weight: float = 0.10
    mix_quality_weight: float = 0.10

    # Filters
    bpm_range: tuple[float, float] | None = None  # e.g., (125, 132)
    key_lock: bool = False  # Only suggest harmonically compatible
    groove_lock: bool = False  # Only same groove type
    exclude_clusters: list[int] = []

    # Strategy
    active_strategy: str = "harmonic_flow"

    # Results
    num_suggestions: int = 8
    diversity_bonus: float = 0.1  # Cluster diversity boost
```
