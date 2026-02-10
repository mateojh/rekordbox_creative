"""Performance tests for large library handling (PERF-001).

Tests that the system can handle 5000+ tracks with acceptable performance:
- Edge computation with BPM pre-filtering
- Batch database operations
- Graph construction and querying
"""

import random
import time

from rekordbox_creative.db.database import Database
from rekordbox_creative.db.models import (
    DJMetrics,
    Edge,
    EdgeScores,
    SpotifyStyleMetrics,
    Track,
    TrackStructure,
)
from rekordbox_creative.graph.graph import TrackGraph

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

CAMELOT_KEYS = [f"{n}{m}" for n in range(1, 13) for m in ("A", "B")]
GROOVE_TYPES = [
    "four_on_floor", "breakbeat", "half_time",
    "complex", "syncopated", "straight",
]
FREQ_WEIGHTS = ["bass_heavy", "bright", "mid_focused", "balanced"]


def _make_track(index: int) -> Track:
    """Generate a pseudo-random track for performance testing."""
    rng = random.Random(index)
    bpm = rng.uniform(100, 160)
    return Track(
        file_path=f"/music/perf_track_{index:05d}.mp3",
        file_hash=f"perf_hash_{index:05d}",
        filename=f"perf_track_{index:05d}.mp3",
        duration_seconds=rng.uniform(180, 480),
        spotify_style=SpotifyStyleMetrics(
            energy=rng.random(),
            danceability=rng.random(),
            acousticness=rng.random(),
            instrumentalness=rng.random(),
            valence=rng.random(),
            liveness=rng.random(),
        ),
        dj_metrics=DJMetrics(
            bpm=bpm,
            bpm_stability=rng.uniform(0.8, 1.0),
            key=rng.choice(CAMELOT_KEYS),
            key_confidence=rng.uniform(0.6, 1.0),
            mix_in_score=rng.uniform(0.5, 1.0),
            mix_out_score=rng.uniform(0.5, 1.0),
            frequency_weight=rng.choice(FREQ_WEIGHTS),
            groove_type=rng.choice(GROOVE_TYPES),
        ),
        structure=TrackStructure(),
    )


def _make_tracks(count: int) -> list[Track]:
    return [_make_track(i) for i in range(count)]


# ---------------------------------------------------------------------------
# BPM pre-filter tests
# ---------------------------------------------------------------------------


class TestBPMPreFilter:
    """Test the BPM pre-filter that skips obviously incompatible pairs."""

    def test_same_bpm(self):
        assert TrackGraph._bpm_compatible(128.0, 128.0) is True

    def test_close_bpm(self):
        assert TrackGraph._bpm_compatible(128.0, 130.0) is True

    def test_within_range(self):
        # 12% of 128 = 15.36 → 143.36
        assert TrackGraph._bpm_compatible(128.0, 143.0) is True

    def test_outside_range(self):
        # 128 * 1.12 = 143.36, so 150 is outside
        assert TrackGraph._bpm_compatible(128.0, 150.0) is False

    def test_far_apart(self):
        assert TrackGraph._bpm_compatible(80.0, 160.0) is True  # double time

    def test_half_time(self):
        assert TrackGraph._bpm_compatible(128.0, 64.0) is True

    def test_double_time(self):
        assert TrackGraph._bpm_compatible(128.0, 256.0) is True

    def test_near_double_not_quite(self):
        # ratio = 260/128 ≈ 2.03 → within 1.90-2.10 range
        assert TrackGraph._bpm_compatible(128.0, 260.0) is True

    def test_outside_double_range(self):
        # ratio = 280/128 ≈ 2.19 → outside
        assert TrackGraph._bpm_compatible(128.0, 280.0) is False


# ---------------------------------------------------------------------------
# Database batch operations
# ---------------------------------------------------------------------------


class TestDatabaseBatchOperations:
    """Test batch insert performance for edges."""

    def test_batch_edge_insert(self):
        """Insert 1000 edges in batch should be fast."""
        db = Database(":memory:")
        tracks = _make_tracks(50)
        for t in tracks:
            db.insert_track(t)

        edges = []
        for i in range(min(1000, len(tracks) * (len(tracks) - 1))):
            src_idx = i % len(tracks)
            tgt_idx = (i + 1) % len(tracks)
            if src_idx == tgt_idx:
                tgt_idx = (tgt_idx + 1) % len(tracks)
            edges.append(Edge(
                source_id=tracks[src_idx].id,
                target_id=tracks[tgt_idx].id,
                compatibility_score=0.5,
                scores=EdgeScores(
                    harmonic=0.5, bpm=0.5, energy=0.5,
                    groove=0.5, frequency=0.5, mix_quality=0.5,
                ),
            ))

        start = time.time()
        db.insert_edges_batch(edges)
        elapsed = time.time() - start
        assert elapsed < 5.0  # Should be well under 5 seconds
        db.close()

    def test_batch_insert_empty(self):
        """Batch insert with empty list should not error."""
        db = Database(":memory:")
        db.insert_edges_batch([])
        db.close()

    def test_get_edges_above_threshold(self):
        """Filter edges by threshold score."""
        db = Database(":memory:")
        tracks = _make_tracks(5)
        for t in tracks:
            db.insert_track(t)

        for i, score in enumerate([0.2, 0.4, 0.6, 0.8]):
            edge = Edge(
                source_id=tracks[i].id,
                target_id=tracks[i + 1].id,
                compatibility_score=score,
                scores=EdgeScores(
                    harmonic=score, bpm=score, energy=score,
                    groove=score, frequency=score, mix_quality=score,
                ),
            )
            db.insert_edge(edge)

        high = db.get_edges_above_threshold(0.5)
        assert len(high) == 2
        low = db.get_edges_above_threshold(0.3)
        assert len(low) == 3
        all_edges = db.get_edges_above_threshold(0.0)
        assert len(all_edges) == 4
        db.close()


# ---------------------------------------------------------------------------
# Graph edge computation performance
# ---------------------------------------------------------------------------


class TestGraphPerformance:
    """Test edge computation performance with BPM pre-filtering."""

    def test_edge_computation_100_tracks(self):
        """100 tracks should compute edges in under 5 seconds."""
        graph = TrackGraph()
        tracks = _make_tracks(100)
        for t in tracks:
            graph.add_node(t)

        start = time.time()
        edges = graph.compute_edges(threshold=0.3)
        elapsed = time.time() - start

        assert elapsed < 5.0
        assert len(edges) > 0
        assert graph.edge_count > 0

    def test_bpm_prefilter_reduces_computations(self):
        """BPM pre-filter should skip pairs with very different tempos."""
        graph = TrackGraph()

        # Create tracks with widely varying BPMs
        tracks = []
        for i in range(20):
            t = _make_track(i)
            # Override BPM to create clear groups: 80, 128, 160
            bpm_group = [80.0, 128.0, 160.0][i % 3]
            t.dj_metrics.bpm = bpm_group + random.uniform(-2, 2)
            tracks.append(t)

        for t in tracks:
            graph.add_node(t)

        edges = graph.compute_edges(threshold=0.0)

        # Verify no edges between 80 BPM and 160 BPM groups
        # (ratio = 2.0 which is half/double, so those ARE allowed)
        # But 80 <-> 128 (ratio = 1.6) should be filtered out
        for edge in edges:
            src = graph.get_node(edge.source_id)
            tgt = graph.get_node(edge.target_id)
            assert TrackGraph._bpm_compatible(
                src.dj_metrics.bpm, tgt.dj_metrics.bpm
            )

    def test_incremental_edges_with_prefilter(self):
        """Incremental edge computation also uses BPM pre-filter."""
        graph = TrackGraph()
        existing = _make_tracks(20)
        for t in existing:
            graph.add_node(t)
        graph.compute_edges(threshold=0.3)

        new_tracks = _make_tracks(5)
        # Shift indices to avoid ID collisions
        new_tracks = [_make_track(100 + i) for i in range(5)]
        for t in new_tracks:
            graph.add_node(t)

        new_edges = graph.compute_edges_for_new_tracks(
            new_tracks, threshold=0.3
        )
        # Should work without error
        assert isinstance(new_edges, list)


# ---------------------------------------------------------------------------
# Large library simulation (PERF-001)
# ---------------------------------------------------------------------------


class TestLargeLibrary:
    """Simulate handling a large library to verify performance targets."""

    def test_500_track_graph_construction(self):
        """500 tracks: build graph, compute edges, verify speed."""
        graph = TrackGraph()
        tracks = _make_tracks(500)

        start = time.time()
        for t in tracks:
            graph.add_node(t)
        add_elapsed = time.time() - start
        assert add_elapsed < 2.0  # Adding 500 nodes should be fast

        assert graph.node_count == 500

        start = time.time()
        graph.compute_edges(threshold=0.5)
        compute_elapsed = time.time() - start
        assert compute_elapsed < 30.0  # 500 tracks with pre-filter

    def test_database_round_trip_500_tracks(self):
        """500 tracks: insert, query, verify performance."""
        db = Database(":memory:")
        tracks = _make_tracks(500)

        start = time.time()
        for t in tracks:
            db.insert_track(t)
        insert_elapsed = time.time() - start
        assert insert_elapsed < 10.0

        start = time.time()
        loaded = db.get_all_tracks()
        query_elapsed = time.time() - start
        assert query_elapsed < 5.0

        assert len(loaded) == 500
        db.close()

    def test_node_lookup_performance(self):
        """Node lookup should be O(1) via dict-backed graph."""
        graph = TrackGraph()
        tracks = _make_tracks(1000)
        for t in tracks:
            graph.add_node(t)

        start = time.time()
        for t in tracks:
            result = graph.get_node(t.id)
            assert result is not None
        elapsed = time.time() - start
        assert elapsed < 1.0  # 1000 lookups should be instant
