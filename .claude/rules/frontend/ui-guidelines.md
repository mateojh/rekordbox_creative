---
paths:
  - "src/rekordbox_creative/ui/**"
---

# UI Implementation Rules

- Follow `docs/UI_SPEC.md` for all layout, color, and interaction decisions
- Dark theme: background #1A1A2E, canvas #16213E, panels #0F0F23
- Node colors follow the 12-hue Camelot color wheel (see UI_SPEC.md)
- Node size scales with energy: 24px (low) to 48px (high)
- Edge thickness scales with compatibility: 1px (0.3-0.5) to 4px (0.9-1.0)
- Minimum window size: 1024x768
- Implement viewport culling — only render visible nodes
- Level-of-detail: full node at zoom-in, colored dot at zoom-out
- All keyboard shortcuts from UI_SPEC.md must be implemented
- Never call `db/` directly — use graph engine or suggestion engine APIs
