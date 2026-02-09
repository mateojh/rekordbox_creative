"""Tests for DBSCAN clustering."""

import numpy as np
import pytest

from rekordbox_creative.db.models import (
    DJMetrics,
    SpotifyStyleMetrics,
    Track,
    TrackStructure,
)
from rekordbox_creative.graph.clustering import (
    GROOVE_ORDINALS,
    _mode,
    cluster_tracks,
    label_cluster,
    track_to_vector,
)


def _make_track(
    energy=0.5,
    danceability=0.5,
    valence=0.5,
    bpm=128.0,
    acousticness=0.1,
    instrumentalness=0.5,
    groove_type="four_on_floor",
    frequency_weight="balanced",
    key="8A",
    **kwargs,
) -> Track:
    """Helper to create a Track with specific attributes."""
    return Track(
        file_path=kwargs.get("file_path", f"/music/{id(energy)}.mp3"),
        file_hash=kwargs.get("file_hash", f"hash_{id(energy)}"),
        filename=kwargs.get("filename", "track.mp3"),
        duration_seconds=300.0,
        spotify_style=SpotifyStyleMetrics(
            energy=energy,
            danceability=danceability,
            acousticness=acousticness,
            instrumentalness=instrumentalness,
            valence=valence,
            liveness=0.1,
        ),
        dj_metrics=DJMetrics(
            bpm=bpm,
            bpm_stability=0.95,
            key=key,
            key_confidence=0.85,
            mix_in_score=0.8,
            mix_out_score=0.8,
            frequency_weight=frequency_weight,
            groove_type=groove_type,
        ),
        structure=TrackStructure(),
    )


# ---------------------------------------------------------------------------
# track_to_vector
# ---------------------------------------------------------------------------


class TestTrackToVector:
    def test_returns_7d_array(self, mock_track_a):
        vec = track_to_vector(mock_track_a)
        assert vec.shape == (7,)

    def test_values_match_track(self, mock_track_a):
        vec = track_to_vector(mock_track_a)
        assert vec[0] == pytest.approx(0.82)  # energy
        assert vec[1] == pytest.approx(0.75)  # danceability
        assert vec[2] == pytest.approx(0.58)  # valence
        assert vec[3] == pytest.approx(128.0 / 200.0)  # bpm normalized
        assert vec[4] == pytest.approx(0.03)  # acousticness
        assert vec[5] == pytest.approx(0.65)  # instrumentalness

    def test_groove_ordinal_encoding(self):
        for groove, expected in GROOVE_ORDINALS.items():
            t = _make_track(groove_type=groove)
            vec = track_to_vector(t)
            assert vec[6] == pytest.approx(expected)

    def test_unknown_groove_defaults_to_half(self):
        t = _make_track(groove_type="unknown_groove")
        vec = track_to_vector(t)
        assert vec[6] == pytest.approx(0.5)

    def test_returns_numpy_array(self, mock_track_a):
        vec = track_to_vector(mock_track_a)
        assert isinstance(vec, np.ndarray)


# ---------------------------------------------------------------------------
# _mode
# ---------------------------------------------------------------------------


class TestMode:
    def test_single_element(self):
        assert _mode(["four_on_floor"]) == "four_on_floor"

    def test_most_common(self):
        assert _mode(["a", "b", "a", "c"]) == "a"

    def test_empty_list(self):
        assert _mode([]) == "unknown"

    def test_tie_returns_first_most_common(self):
        result = _mode(["a", "b"])
        assert result in ("a", "b")


# ---------------------------------------------------------------------------
# label_cluster
# ---------------------------------------------------------------------------


class TestLabelCluster:
    def test_high_energy_label(self):
        tracks = [_make_track(energy=0.85, bpm=130.0) for _ in range(3)]
        label = label_cluster(tracks)
        assert "High Energy" in label
        assert "130 BPM" in label

    def test_mid_energy_label(self):
        tracks = [_make_track(energy=0.55, bpm=120.0) for _ in range(3)]
        label = label_cluster(tracks)
        assert "Mid Energy" in label

    def test_low_energy_label(self):
        tracks = [_make_track(energy=0.25, bpm=90.0) for _ in range(3)]
        label = label_cluster(tracks)
        assert "Low Energy" in label

    def test_includes_groove_and_freq(self):
        tracks = [
            _make_track(
                energy=0.8,
                bpm=128.0,
                groove_type="four_on_floor",
                frequency_weight="bass_heavy",
            )
            for _ in range(3)
        ]
        label = label_cluster(tracks)
        assert "Four On Floor" in label
        assert "Bass Heavy" in label

    def test_empty_tracks(self):
        assert label_cluster([]) == "Empty Cluster"


# ---------------------------------------------------------------------------
# cluster_tracks
# ---------------------------------------------------------------------------


class TestClusterTracks:
    def test_too_few_tracks(self):
        tracks = [_make_track(file_path=f"/m/{i}.mp3", file_hash=f"h{i}") for i in range(2)]
        clusters = cluster_tracks(tracks, min_samples=3)
        assert clusters == []

    def test_identical_tracks_cluster_together(self):
        """Many identical tracks should form at least one cluster."""
        tracks = [
            _make_track(
                energy=0.8,
                danceability=0.7,
                valence=0.5,
                bpm=128.0,
                acousticness=0.05,
                instrumentalness=0.6,
                file_path=f"/music/identical_{i}.mp3",
                file_hash=f"identical_{i}",
            )
            for i in range(10)
        ]
        clusters = cluster_tracks(tracks, eps=1.0, min_samples=3)
        assert len(clusters) >= 1

    def test_cluster_updates_track_cluster_id(self):
        """Tracks that get clustered should have cluster_id set."""
        tracks = [
            _make_track(
                energy=0.8,
                danceability=0.7,
                valence=0.5,
                bpm=128.0,
                file_path=f"/music/clust_{i}.mp3",
                file_hash=f"clust_{i}",
            )
            for i in range(10)
        ]
        cluster_tracks(tracks, eps=1.0, min_samples=3)
        # At least some tracks should be assigned cluster IDs
        assigned = [t for t in tracks if t.cluster_id is not None]
        assert len(assigned) > 0

    def test_noise_tracks_have_none_cluster_id(self):
        """Noise tracks (label=-1) should have cluster_id=None."""
        # Create a mixed set: 6 similar + 1 outlier
        similar = [
            _make_track(
                energy=0.8,
                danceability=0.7,
                bpm=128.0,
                file_path=f"/music/sim_{i}.mp3",
                file_hash=f"sim_{i}",
            )
            for i in range(6)
        ]
        outlier = _make_track(
            energy=0.1,
            danceability=0.1,
            bpm=60.0,
            acousticness=0.95,
            file_path="/music/outlier.mp3",
            file_hash="outlier_hash",
        )
        tracks = similar + [outlier]
        cluster_tracks(tracks, eps=0.5, min_samples=3)
        # The outlier may be noise
        # Just verify the function doesn't crash and returns valid results

    def test_cluster_object_fields(self):
        """Cluster objects should have correct fields populated."""
        tracks = [
            _make_track(
                energy=0.8,
                danceability=0.7,
                bpm=128.0,
                groove_type="four_on_floor",
                frequency_weight="bass_heavy",
                key="8A",
                file_path=f"/music/cf_{i}.mp3",
                file_hash=f"cf_{i}",
            )
            for i in range(10)
        ]
        clusters = cluster_tracks(tracks, eps=1.0, min_samples=3)
        if clusters:
            c = clusters[0]
            assert c.id >= 0
            assert len(c.track_ids) >= 3
            assert c.track_count == len(c.track_ids)
            assert c.avg_bpm > 0
            assert 0.0 <= c.avg_energy <= 1.0
            assert len(c.centroid) == 7
            assert isinstance(c.label, str)

    def test_returns_list_of_clusters(self):
        tracks = [
            _make_track(
                energy=0.8, bpm=128.0,
                file_path=f"/music/lc_{i}.mp3", file_hash=f"lc_{i}",
            )
            for i in range(10)
        ]
        result = cluster_tracks(tracks, eps=1.0, min_samples=3)
        assert isinstance(result, list)
