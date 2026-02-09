---
paths:
  - "src/rekordbox_creative/analysis/**"
  - "tests/test_scanner.py"
---

# Analysis Layer Rules

- Wrap `audio_analyzer.AudioAnalyzer` — do not reimplement analysis
- Use `AudioAnalyzer(use_cache=True)` for caching at the librosa level
- Our own cache layer uses file MD5 hash to skip re-analysis
- Supported formats: MP3, WAV, FLAC, OGG, M4A, AAC (from audio_analyzer)
- Always use `continue_on_error=True` for batch processing
- Provide progress callbacks: `progress_callback(filename, current, total)`
- Metadata extraction (mutagen) is separate from audio analysis — run it first
- Scanner discovers files recursively, filtering by extension
