---
paths:
  - "src/rekordbox_creative/db/**"
  - "tests/test_database.py"
---

# Database Rules

- Use the SQLite schema from `docs/DATA_MODELS.md` exactly
- All database tests use in-memory SQLite (`:memory:`)
- Track IDs are UUIDs stored as TEXT
- File hash is MD5 of file content for cache invalidation
- Structure and metadata fields are JSON blobs (structure_json, metadata_json)
- Create indexes on bpm, key_camelot, energy, file_hash, cluster_id
- Edge table has UNIQUE(source_id, target_id) constraint
- Never expose raw SQL outside the `db/` module
