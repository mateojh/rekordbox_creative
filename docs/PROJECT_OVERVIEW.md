# Project Overview: Rekordbox Creative

## Vision

A standalone desktop application that transforms a DJ's local music library into an interactive, intelligent node graph. DJs drop a folder of audio files into the app, the system analyzes every track, and presents a visual canvas where songs exist as nodes connected by musical compatibility. The app suggests next tracks, reveals hidden connections between records, and helps DJs build sets that flow naturally.

## Problem Statement

DJs with large libraries (500-10,000+ tracks) face three problems:

1. **Discovery paralysis**: Too many tracks to remember what goes well together
2. **Set planning is manual**: Building coherent sets requires deep knowledge of every track's BPM, key, energy, and vibe
3. **Hidden connections**: Tracks that would mix beautifully together are never paired because the DJ doesn't think to try them

Existing tools (Rekordbox, Serato, Traktor) organize by metadata but don't visualize relationships or suggest creative transitions.

## Solution

A node-based graph interface where:

- Each track is a **node** displaying key metrics (BPM, key, energy, groove)
- **Edges** between nodes represent compatibility scores (harmonic, rhythmic, energy flow)
- A **suggestion engine** recommends the best next track based on the current graph state
- **Clusters** emerge naturally as "vibe islands" — groups of tracks that share sonic characteristics
- **Scatter map** plots the entire library spatially so proximity = compatibility
- Users can **lock sequences**, **swap tracks**, and **export playlists** to DJ software

## Target Users

- DJs with local music libraries (house, techno, electronic, but genre-agnostic)
- Primarily preparing sets before performances, not during live sets
- Comfortable with desktop applications
- Range from bedroom DJs to professional touring artists

## Non-Goals

- **Not a DJ player**: No decks, no live mixing, no waveform display
- **Not a streaming service**: Works exclusively with local files
- **Not web-based**: Desktop executable only — no browser, no server, no accounts
- **Not a DAW**: No audio editing, no effects, no recording

## Key Differentiators from Djoid.io

| Aspect | Djoid.io | Rekordbox Creative |
|--------|----------|-------------------|
| Platform | Web app (browser) | Desktop executable |
| Audio analysis | Server-side / proprietary | Local via `audio_analyzer` (open source) |
| Pricing | €99/year subscription | Free / open source |
| Data | Uploaded to cloud | Never leaves your machine |
| Integration | Rekordbox, Serato, Traktor export | Local folder input, playlist export |
| Node graph | Graph Playlist feature | Core interaction model |
| Scatter map | Available | Available (spatial layout) |

## Inspired Features from Djoid.io

### Graph Playlist (→ Node Graph)
Djoid's graph playlist visualizes track relationships through harmony, energy, and emotion. We adapt this as our core node graph canvas where every track is a draggable node and edges represent weighted compatibility.

### Scatter Map (→ Spatial View)
Djoid's scatter map plots the library spatially based on sonic characteristics. We implement this as a layout mode where proximity indicates compatibility, allowing DJs to discover "vibe islands."

### Chapter Builder (→ Set Segments)
Djoid structures sets into 3-20 track energy blocks. We support this through sequential node chains that users can group, label, and rearrange as set segments.

### Magic Sorting (→ Optimal Path)
Djoid's magic sorting auto-sequences tracks. We implement this as graph pathfinding — finding the optimal traversal through selected nodes that maximizes transition quality.

## Audio Analysis Foundation

All intelligence derives from the `audio_analyzer` library, which extracts:

### Spotify-Style Metrics (0.0–1.0 scale)
| Metric | Description | Use in Suggestions |
|--------|-------------|-------------------|
| Energy | Perceived intensity | Energy flow curves |
| Danceability | Dance suitability | Set vibe consistency |
| Acousticness | Acoustic confidence | Genre clustering |
| Instrumentalness | Vocal absence | Transition smoothness |
| Valence | Musical positiveness | Mood arcs |
| Liveness | Audience presence | Live vs studio clustering |

### DJ Metrics
| Metric | Description | Use in Suggestions |
|--------|-------------|-------------------|
| BPM | Tempo | Mix compatibility (±6%) |
| BPM Stability | Tempo variance | Mix reliability |
| Key (Camelot) | Musical key | Harmonic mixing rules |
| Key Confidence | Detection certainty | Suggestion weighting |
| Mix-In Score | Intro friendliness | Transition quality |
| Mix-Out Score | Outro friendliness | Transition quality |
| Frequency Weight | Bass/bright/mid/balanced | Sonic flow |
| Groove Type | Four-on-floor/breakbeat/etc. | Rhythmic compatibility |

### Structural Data
| Data | Description | Use in Suggestions |
|------|-------------|-------------------|
| Drop timestamps | Where energy peaks | Set climax planning |
| Breakdown ranges | Low-energy sections | Transition points |
| Vocal segments | Where vocals appear | Avoiding vocal clashes |
| Build sections | Energy ramps | Momentum planning |
| Intro/outro bounds | Entry/exit points | Mix point estimation |

## Success Criteria

1. User can point at a folder and see all tracks analyzed within minutes
2. Node graph accurately reflects musical relationships
3. Suggestions feel musically intelligent (not random)
4. Exported playlists translate directly to DJ software
5. App runs as a standalone executable without Python/Node.js installed
6. Performance handles 5,000+ track libraries without lag
