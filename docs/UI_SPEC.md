# UI/UX Specification

## Design Philosophy

- **Dark theme**: Matches DJ software conventions (Rekordbox, Serato, Ableton)
- **Canvas-centric**: The node graph is the main interaction surface, not a list
- **Information density**: Show enough data at a glance without overwhelming
- **Responsive**: Smooth panning, zooming, and node dragging at 60fps
- **Keyboard-friendly**: Power users should be able to navigate without a mouse

## Window Layout

```
┌──────────────────────────────────────────────────────────────────┐
│  Menu Bar: File | Edit | View | Analyze | Export | Settings      │
├────────────────────┬─────────────────────────────────────────────┤
│  Toolbar           │  Search: [_______________] [Layout ▼]      │
├────────────────────┴─────────────────────────────────────────────┤
│                    │                                   │         │
│                    │                                   │         │
│  Library Browser   │        Node Graph Canvas          │ Right   │
│  (collapsible)     │                                   │ Panel   │
│                    │        ┌───┐     ┌───┐           │ (tabs)  │
│  □ All Tracks      │        │ A ├─────┤ B │           │         │
│  □ Cluster: High   │        └─┬─┘     └───┘           │ [Insp.] │
│    Energy 128      │          │                        │ [Sugg.] │
│  □ Cluster: Chill  │        ┌─┴─┐                     │ [Set  ] │
│    Ambient         │        │ C │                      │ [Sett.] │
│                    │        └───┘                      │         │
│                    │                                   │         │
├────────────────────┴───────────────────────────────────┴─────────┤
│  Status Bar: 2,847 tracks | 15,432 edges | Cluster: 12 islands  │
└──────────────────────────────────────────────────────────────────┘
```

## Color System

### Key-Based Node Colors (Camelot Wheel)

Map the 12 Camelot numbers to a 12-hue color wheel:
```
1  → Red          (#FF4444)
2  → Red-Orange   (#FF6633)
3  → Orange       (#FF9922)
4  → Yellow       (#FFCC11)
5  → Yellow-Green (#99DD00)
6  → Green        (#44CC44)
7  → Teal         (#22BBAA)
8  → Cyan         (#22AADD)
9  → Blue         (#4488FF)
10 → Blue-Violet  (#6644FF)
11 → Violet       (#AA44FF)
12 → Magenta      (#FF44AA)

Minor (A): Saturated version
Major (B): Lighter/pastel version
```

This means nodes in compatible keys (adjacent on the wheel) are adjacent colors — visually obvious clustering.

### Energy → Node Size

```
Energy 0.0-0.3: Small node  (24px radius)
Energy 0.3-0.6: Medium node (32px radius)
Energy 0.6-0.8: Large node  (40px radius)
Energy 0.8-1.0: XL node     (48px radius)
```

### Edge Styling

```
Compatibility 0.3-0.5: Thin (1px), dim
Compatibility 0.5-0.7: Medium (2px), normal opacity
Compatibility 0.7-0.9: Thick (3px), bright
Compatibility 0.9-1.0: Extra thick (4px), glowing
User-created edge:     Dashed, highlighted color
```

### Theme Colors

```
Background:     #1A1A2E
Canvas BG:      #16213E
Node default:   Camelot color (see above)
Node selected:  White border glow
Node in set:    Gold border (#FFD700)
Edge default:   #FFFFFF20 (white, low opacity)
Edge active:    #FFFFFF80
Panel BG:       #0F0F23
Text primary:   #E0E0E0
Text secondary: #888888
Accent:         #00D4FF (cyan)
Warning:        #FF6B35
```

## Node Design

### Default State
```
     ┌─────────────────┐
     │  Track Name      │
     │  Artist          │
     │  ──────────────  │
     │  128 BPM  │ 8A   │
     └─────────────────┘
```

### Selected State
- White glow border
- Expanded to show:
```
     ╔═════════════════╗
     ║  Track Name      ║
     ║  Artist          ║
     ║  ──────────────  ║
     ║  128 BPM  │ 8A   ║
     ║  E: ████████░░   ║  (energy bar)
     ║  D: ██████░░░░   ║  (danceability bar)
     ║  🎵 4/4 │ Bass   ║  (groove, freq weight)
     ╚═════════════════╝
```

### Zoomed-Out State (LOD)
When many nodes visible, simplify to:
```
     ●  (colored dot, sized by energy)
```
Label appears on hover.

### In-Sequence State
- Gold border and sequence number badge:
```
     [3]┌─────────────────┐
        │  Track Name      │
        │  128 BPM  │ 8A   │
        └─────────────────┘
```

## Panels

### Library Browser (Left Panel, Collapsible)

- Tree view of tracks organized by:
  - All Tracks (flat list)
  - By Cluster (vibe islands)
  - By Key (Camelot groups)
  - By BPM Range
- Each entry shows: Track name, BPM, Key
- Click to select on canvas, double-click to add to sequence
- Sort by: Name, BPM, Key, Energy, Date Added

### Inspector Panel (Right Panel, Tab 1)

Shows when a track is selected:
```
┌─────────────────────────────┐
│ INSPECTOR                    │
├─────────────────────────────┤
│ "Track Title"                │
│ Artist Name                  │
│ Album Name                   │
│ Duration: 6:42               │
│                              │
│ ─── DJ Metrics ───           │
│ BPM:      128.0 (stable)     │
│ Key:      8A (conf: 0.85)    │
│ Mix-In:   ████████░░ 0.90    │
│ Mix-Out:  ████████░░ 0.85    │
│ Groove:   Four on Floor      │
│ Freq:     Bass Heavy         │
│                              │
│ ─── Audio Features ───       │
│ Energy:   ████████░░ 0.82    │
│ Dance:    ███████░░░ 0.75    │
│ Valence:  █████░░░░░ 0.58    │
│ Acoustic: ░░░░░░░░░░ 0.03   │
│ Instrum:  ██████░░░░ 0.65    │
│ Live:     █░░░░░░░░░ 0.12    │
│                              │
│ ─── Structure ───            │
│ Drops:    1:04, 3:12         │
│ Vocals:   0:32-1:04          │
│ Intro:    0:00-0:16          │
│ Outro:    5:20-6:42          │
│                              │
│ ─── Cluster ───              │
│ "High Energy 128 Four-on-    │
│  Floor Bass-Heavy"           │
└─────────────────────────────┘
```

### Suggestion Panel (Right Panel, Tab 2)

```
┌─────────────────────────────┐
│ SUGGESTIONS for "Track A"    │
├─────────────────────────────┤
│ Strategy: [Harmonic Flow ▼]  │
│ Filters: BPM [___-___]      │
│          Key Lock [□]        │
│          Groove Lock [□]     │
├─────────────────────────────┤
│ 1. Track B     0.92 ████████ │
│    128 BPM │ 8A │ E:0.80     │
│                              │
│ 2. Track C     0.87 ███████  │
│    127 BPM │ 9A │ E:0.78     │
│                              │
│ 3. Track D     0.81 ██████   │
│    130 BPM │ 8B │ E:0.85     │
│                              │
│ ... (up to 8 suggestions)    │
├─────────────────────────────┤
│ [Show Score Breakdown]       │
└─────────────────────────────┘
```

Score breakdown (expanded):
```
│  Track B breakdown:           │
│  Harmonic: 1.00 (8A → 8A)    │
│  BPM:      1.00 (128 → 128)  │
│  Energy:   0.80 (0.82 → 0.80)│
│  Groove:   1.00 (4/4 → 4/4)  │
│  Freq:     0.70 (bass → bal)  │
│  Mix:      0.88 (0.85 + 0.90)│
```

### Set Panel (Right Panel, Tab 3)

```
┌─────────────────────────────┐
│ CURRENT SET (8 tracks)       │
├─────────────────────────────┤
│ Total time: 48:35            │
│ Avg compatibility: 0.78      │
│                              │
│ [Optimize Order] [Clear All] │
├─────────────────────────────┤
│ ── Opener ──                 │
│ 1. Track A  128 BPM  8A     │
│    ↕ 0.92                    │
│ 2. Track B  128 BPM  8A     │
│    ↕ 0.87                    │
│ 3. Track C  127 BPM  9A     │
│                              │
│ ── Peak Time ──              │
│ 4. Track D  130 BPM  8B     │
│    ↕ 0.81                    │
│ 5. Track E  132 BPM  9B     │
│    ...                       │
├─────────────────────────────┤
│ [+ Add Segment]              │
│ [Export ▼]                   │
└─────────────────────────────┘
```

### Settings Panel (Right Panel, Tab 4)

```
┌─────────────────────────────┐
│ SETTINGS                     │
├─────────────────────────────┤
│ ─── Scoring Weights ───      │
│ Harmonic:   [====|=====] 0.30│
│ BPM:        [===|======] 0.25│
│ Energy:     [=|========] 0.15│
│ Groove:     [|=========] 0.10│
│ Frequency:  [|=========] 0.10│
│ Mix Quality:[|=========] 0.10│
│ [Reset to Defaults]          │
│                              │
│ ─── Display ───              │
│ Edge threshold:  [==|===] 0.3│
│ Node labels:     [On ▼]      │
│ Edge labels:     [Off ▼]     │
│ Color by:        [Key ▼]     │
│                              │
│ ─── Library ───              │
│ Music folder: /path/to/music │
│ [Change Folder]              │
│ [Re-analyze All]             │
│ [Clear Cache]                │
└─────────────────────────────┘
```

## Interactions

### Keyboard Shortcuts

| Shortcut | Action |
|----------|--------|
| Space | Play/preview selected track (if audio playback supported) |
| Delete/Backspace | Remove selected node from sequence |
| Cmd/Ctrl+A | Select all nodes |
| Cmd/Ctrl+F | Focus search bar |
| Cmd/Ctrl+E | Export current set |
| Cmd/Ctrl+S | Save graph state |
| Cmd/Ctrl+Z | Undo last action |
| 1/2/3/4 | Switch right panel tab |
| F | Fit all nodes in view |
| L | Cycle layout modes |
| +/- | Zoom in/out |
| Arrow keys | Pan canvas |
| Tab | Cycle through suggested tracks |
| Enter | Add highlighted suggestion to sequence |

### Mouse Interactions

| Action | Result |
|--------|--------|
| Click node | Select, show in inspector |
| Double-click node | Add to sequence |
| Right-click node | Context menu |
| Drag node | Reposition |
| Drag from node port | Create manual edge |
| Click edge | Show edge details |
| Scroll wheel | Zoom |
| Middle-click drag | Pan |
| Click canvas (empty) | Deselect all |
| Marquee select (Shift+drag) | Select multiple nodes |

## Animation and Feedback

- **Node selection**: 200ms border glow transition
- **Suggestion highlight**: Pulsing glow effect on suggested nodes (1s cycle)
- **Layout change**: 500ms animated transition between layout modes
- **Edge hover**: Edge thickens and shows compatibility score tooltip
- **Add to sequence**: Node briefly flashes gold
- **Drag feedback**: Ghost outline follows cursor, snap-to-grid optional

## First-Run Experience

1. Welcome screen with brief description
2. "Select Music Folder" button (prominent, centered)
3. Analysis begins with progress overlay
4. On completion, graph appears with force-directed layout
5. Tooltip hints: "Click a track to see suggestions" → "Double-click to add to your set"

## Responsive Behavior

- **Minimum window size**: 1024 × 768
- **Panels collapse**: Left and right panels can be collapsed for more canvas space
- **Panel resize**: Drag panel borders to resize
- **Full-screen canvas**: Double-click canvas area header to maximize

## GUI Framework Candidates

### Option A: PyQt6 / PySide6
- **Pros**: Mature, full-featured, native look, QGraphicsView ideal for node graphs, excellent performance
- **Cons**: GPL/LGPL licensing complexity, large bundle size (~50MB), Qt learning curve
- **Best for**: Maximum desktop performance, complex interactive canvas

### Option B: Dear PyGui
- **Pros**: GPU-accelerated, node editor built-in (imnodes), Python-native, game-like performance
- **Cons**: Less polished native look, smaller community, fewer widgets
- **Best for**: Node graph-heavy apps, performance-critical rendering

### Option C: CustomTkinter + Custom Canvas
- **Pros**: Lightweight, simple, modern look, easy packaging
- **Cons**: No built-in node graph, would need custom canvas implementation
- **Best for**: Simpler UIs, fast prototyping

### Recommendation: Dear PyGui or PyQt6
- Dear PyGui has a built-in node editor (via imnodes) which is a major accelerator for this project
- PyQt6's QGraphicsView is more flexible for custom node rendering and interaction
- Decision should be made early as it affects the entire UI layer
