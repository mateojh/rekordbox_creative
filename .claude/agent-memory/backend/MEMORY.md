# Backend Agent Memory

## Completed Features
- **DB-001** (SQLite Storage): Database class with full CRUD, 5 tables, 8 indexes
- **DB-002** (Track Persistence): CacheManager wrapping Database for hash-based lookups

## Key Implementation Patterns

### Database Serialization
- Track model flattened to SQLite: nested `spotify_style.energy` -> `energy` column
- `dj_metrics.key` -> `key_camelot` column (note the rename)
- `structure` and `metadata` stored as JSON blobs via `model_dump_json()`
- UUIDs stored as TEXT via `str(uuid)`
- Booleans stored as INTEGER (0/1)
- Datetimes stored as ISO format TEXT strings

### Database Connection Setup
- `PRAGMA journal_mode=WAL` for better concurrent read performance
- `PRAGMA foreign_keys=ON` to enforce FK constraints
- `row_factory = sqlite3.Row` for dict-style column access
- `executescript()` for multi-statement DDL (CREATE TABLE/INDEX)
- Single `commit()` after each operation for simplicity

### Test Patterns
- In-memory `:memory:` for most tests (fast, isolated)
- `tmp_path` fixture for file-based persistence tests
- `mock_track_a` and `mock_track_b` from conftest.py for standard test data
- Helper functions `_make_track()` and `_make_edge()` for custom test data
- Test classes organized by entity: TestTrackCRUD, TestEdgeCRUD, etc.

## File Inventory
- `/src/rekordbox_creative/db/database.py` - Database class (538 lines)
- `/src/rekordbox_creative/db/cache.py` - CacheManager class (32 lines)
- `/src/rekordbox_creative/db/models.py` - Pydantic models (pre-existing)
- `/tests/test_database.py` - 57 database tests
- `/tests/test_models.py` - 44 model validation tests

## Gotchas
- Ruff autofix removed unused imports (Path, DJMetrics etc. in test files)
- `SuggestionConfig.normalized_weights()` will divide-by-zero if all weights are 0
- Edge UNIQUE(source_id, target_id) allows reverse edges A->B and B->A
