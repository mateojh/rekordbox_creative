---
paths:
  - "src/rekordbox_creative/graph/scoring.py"
  - "tests/test_scoring.py"
---

# Scoring Implementation Rules

- Match the exact formulas in `docs/ALGORITHM_SPEC.md` — no approximations
- Camelot wheel distance uses `min(abs(a - b), 12 - abs(a - b))` for wrapping
- BPM half/double check: ratio between 1.95 and 2.05 returns 0.6
- Key confidence modifier: multiply harmonic score by `min(conf_a, conf_b)` when either < 0.7
- BPM stability modifier: reduce BPM score by 20% when either track has stability < 0.8
- Groove and frequency scores use lookup tables — check both `(a,b)` and `(b,a)` for symmetric pairs
- Mix quality is directional: uses `mix_out` of source and `mix_in` of target
