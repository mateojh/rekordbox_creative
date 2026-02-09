# Testing Rules

- Every scoring function needs test cases for edge cases: same values, extreme values, boundary conditions
- Test Camelot wrapping: 12A → 1A should be adjacent (distance 1), not distance 11
- Test half/double BPM detection: 128 → 64, 128 → 256
- Use the fixtures in `conftest.py` for mock tracks — don't create ad-hoc Track objects in tests
- It is unacceptable to remove or edit existing tests — this could lead to missing or buggy functionality
- Mark slow tests (>5 seconds) with `@pytest.mark.slow`
- Integration tests that need audio files use the `fixtures/` directory
- Database tests should use an in-memory SQLite database (`:memory:`)
- Run `pytest tests/ -v` before every commit to verify nothing is broken
