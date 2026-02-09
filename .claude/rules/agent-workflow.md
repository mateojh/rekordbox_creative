# Agent Workflow Rules

- IMPORTANT: Implement exactly ONE feature per session. Do not try to build the entire app at once.
- Always start by reading `claude-progress.txt` and `git log --oneline -20`
- Always run `bash init.sh` at the start of every session
- Always read the feature description from `docs/FEATURES.json` before implementing
- Only change `"passes": false` to `"passes": true` in FEATURES.json when the feature genuinely works with passing tests
- Never mark a feature as passing without running the tests
- Commit after completing each feature with a descriptive message
- Update `claude-progress.txt` at the end of every session — this is critical for the next agent
- If stuck on a feature after 3 attempts, document the issue and move on
- When creating new files, follow the directory structure in `docs/ARCHITECTURE.md`
- When implementing scoring functions, match the exact formulas in `docs/ALGORITHM_SPEC.md`
- When implementing UI, match the layout and interactions in `docs/UI_SPEC.md`
- Use the data models defined in `docs/DATA_MODELS.md` — do not invent new schemas
