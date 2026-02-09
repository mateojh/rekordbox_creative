"""Tests for Pydantic data models."""

import math
from uuid import uuid4

import pytest
from pydantic import ValidationError

from rekordbox_creative.db.models import (
    DJMetrics,
    Edge,
    EdgeScores,
    Playlist,
    SpotifyStyleMetrics,
    SuggestionConfig,
    SuggestionStrategy,
    Track,
    TrackMetadata,
    TrackStructure,
)

# ---------------------------------------------------------------------------
# SpotifyStyleMetrics
# ---------------------------------------------------------------------------


class TestSpotifyStyleMetrics:
    def test_valid_metrics(self):
        m = SpotifyStyleMetrics(
            energy=0.5, danceability=0.6, acousticness=0.1,
            instrumentalness=0.7, valence=0.4, liveness=0.2,
        )
        assert m.energy == 0.5
        assert m.danceability == 0.6

    def test_boundary_zero(self):
        m = SpotifyStyleMetrics(
            energy=0.0, danceability=0.0, acousticness=0.0,
            instrumentalness=0.0, valence=0.0, liveness=0.0,
        )
        assert m.energy == 0.0

    def test_boundary_one(self):
        m = SpotifyStyleMetrics(
            energy=1.0, danceability=1.0, acousticness=1.0,
            instrumentalness=1.0, valence=1.0, liveness=1.0,
        )
        assert m.energy == 1.0

    def test_energy_above_1_fails(self):
        with pytest.raises(ValidationError):
            SpotifyStyleMetrics(
                energy=1.1, danceability=0.5, acousticness=0.5,
                instrumentalness=0.5, valence=0.5, liveness=0.5,
            )

    def test_energy_below_0_fails(self):
        with pytest.raises(ValidationError):
            SpotifyStyleMetrics(
                energy=-0.1, danceability=0.5, acousticness=0.5,
                instrumentalness=0.5, valence=0.5, liveness=0.5,
            )

    def test_danceability_above_1_fails(self):
        with pytest.raises(ValidationError):
            SpotifyStyleMetrics(
                energy=0.5, danceability=1.5, acousticness=0.5,
                instrumentalness=0.5, valence=0.5, liveness=0.5,
            )

    def test_missing_field_fails(self):
        with pytest.raises(ValidationError):
            SpotifyStyleMetrics(
                energy=0.5, danceability=0.5,
                # missing remaining fields
            )


# ---------------------------------------------------------------------------
# DJMetrics
# ---------------------------------------------------------------------------


class TestDJMetrics:
    def test_valid_dj_metrics(self):
        m = DJMetrics(
            bpm=128.0, bpm_stability=0.97, key="8A",
            key_confidence=0.85, mix_in_score=0.9, mix_out_score=0.85,
            frequency_weight="bass_heavy", groove_type="four_on_floor",
        )
        assert m.bpm == 128.0
        assert m.key == "8A"

    def test_bpm_zero_fails(self):
        with pytest.raises(ValidationError):
            DJMetrics(
                bpm=0.0, bpm_stability=0.97, key="8A",
                key_confidence=0.85, mix_in_score=0.9, mix_out_score=0.85,
                frequency_weight="bass_heavy", groove_type="four_on_floor",
            )

    def test_bpm_negative_fails(self):
        with pytest.raises(ValidationError):
            DJMetrics(
                bpm=-10.0, bpm_stability=0.97, key="8A",
                key_confidence=0.85, mix_in_score=0.9, mix_out_score=0.85,
                frequency_weight="bass_heavy", groove_type="four_on_floor",
            )

    def test_key_pattern_valid_single_digit(self):
        m = DJMetrics(
            bpm=128.0, bpm_stability=0.97, key="1B",
            key_confidence=0.85, mix_in_score=0.9, mix_out_score=0.85,
            frequency_weight="balanced", groove_type="breakbeat",
        )
        assert m.key == "1B"

    def test_key_pattern_valid_double_digit(self):
        m = DJMetrics(
            bpm=128.0, bpm_stability=0.97, key="12A",
            key_confidence=0.85, mix_in_score=0.9, mix_out_score=0.85,
            frequency_weight="balanced", groove_type="breakbeat",
        )
        assert m.key == "12A"

    def test_key_pattern_invalid_letters(self):
        with pytest.raises(ValidationError):
            DJMetrics(
                bpm=128.0, bpm_stability=0.97, key="XY",
                key_confidence=0.85, mix_in_score=0.9, mix_out_score=0.85,
                frequency_weight="balanced", groove_type="breakbeat",
            )

    def test_key_pattern_invalid_no_mode(self):
        with pytest.raises(ValidationError):
            DJMetrics(
                bpm=128.0, bpm_stability=0.97, key="8",
                key_confidence=0.85, mix_in_score=0.9, mix_out_score=0.85,
                frequency_weight="balanced", groove_type="breakbeat",
            )

    def test_key_pattern_invalid_c_mode(self):
        with pytest.raises(ValidationError):
            DJMetrics(
                bpm=128.0, bpm_stability=0.97, key="8C",
                key_confidence=0.85, mix_in_score=0.9, mix_out_score=0.85,
                frequency_weight="balanced", groove_type="breakbeat",
            )

    def test_key_confidence_out_of_range(self):
        with pytest.raises(ValidationError):
            DJMetrics(
                bpm=128.0, bpm_stability=0.97, key="8A",
                key_confidence=1.5, mix_in_score=0.9, mix_out_score=0.85,
                frequency_weight="bass_heavy", groove_type="four_on_floor",
            )

    def test_mix_score_out_of_range(self):
        with pytest.raises(ValidationError):
            DJMetrics(
                bpm=128.0, bpm_stability=0.97, key="8A",
                key_confidence=0.85, mix_in_score=-0.1, mix_out_score=0.85,
                frequency_weight="bass_heavy", groove_type="four_on_floor",
            )


# ---------------------------------------------------------------------------
# TrackStructure
# ---------------------------------------------------------------------------


class TestTrackStructure:
    def test_defaults(self):
        s = TrackStructure()
        assert s.drops == []
        assert s.breakdowns == []
        assert s.vocal_segments == []
        assert s.build_sections == []
        assert s.intro_end is None
        assert s.outro_start is None

    def test_with_values(self):
        s = TrackStructure(
            drops=[64.2, 192.5],
            breakdowns=[[96.0, 128.0]],
            vocal_segments=[[32.0, 64.0]],
            intro_end=16.0,
            outro_start=320.0,
        )
        assert s.drops == [64.2, 192.5]
        assert s.breakdowns == [[96.0, 128.0]]
        assert s.intro_end == 16.0


# ---------------------------------------------------------------------------
# TrackMetadata
# ---------------------------------------------------------------------------


class TestTrackMetadata:
    def test_defaults_all_none(self):
        m = TrackMetadata()
        assert m.artist is None
        assert m.title is None
        assert m.album is None
        assert m.genre is None
        assert m.year is None

    def test_with_values(self):
        m = TrackMetadata(
            artist="DJ Test", title="Track One", album="Album",
            genre="House", year=2024,
        )
        assert m.artist == "DJ Test"
        assert m.year == 2024


# ---------------------------------------------------------------------------
# Track
# ---------------------------------------------------------------------------


class TestTrack:
    def test_create_track(self, mock_track_a):
        assert mock_track_a.filename == "track_a.mp3"
        assert mock_track_a.dj_metrics.bpm == 128.0
        assert mock_track_a.dj_metrics.key == "8A"
        assert mock_track_a.spotify_style.energy == 0.82
        assert mock_track_a.structure.drops == [64.2, 192.5]

    def test_track_has_uuid(self, mock_track_a):
        assert mock_track_a.id is not None

    def test_track_default_cluster_id_none(self, mock_track_a):
        assert mock_track_a.cluster_id is None

    def test_track_default_times_used_zero(self, mock_track_a):
        assert mock_track_a.times_used == 0

    def test_track_mutable(self, mock_track_a):
        """Track model is mutable (frozen=False)."""
        mock_track_a.cluster_id = 5
        assert mock_track_a.cluster_id == 5
        mock_track_a.times_used = 10
        assert mock_track_a.times_used == 10

    def test_track_round_trip_serialization(self, mock_track_a):
        """Track -> dict -> Track produces identical data."""
        data = mock_track_a.model_dump()
        restored = Track(**data)

        assert restored.id == mock_track_a.id
        assert restored.file_path == mock_track_a.file_path
        assert restored.file_hash == mock_track_a.file_hash
        assert restored.filename == mock_track_a.filename
        assert restored.duration_seconds == mock_track_a.duration_seconds
        assert restored.spotify_style.energy == mock_track_a.spotify_style.energy
        assert restored.dj_metrics.bpm == mock_track_a.dj_metrics.bpm
        assert restored.dj_metrics.key == mock_track_a.dj_metrics.key
        assert restored.structure.drops == mock_track_a.structure.drops
        assert restored.metadata.artist == mock_track_a.metadata.artist

    def test_track_json_round_trip(self, mock_track_a):
        """Track -> JSON -> Track round-trip."""
        json_str = mock_track_a.model_dump_json()
        restored = Track.model_validate_json(json_str)
        assert restored.id == mock_track_a.id
        assert restored.dj_metrics.bpm == mock_track_a.dj_metrics.bpm


# ---------------------------------------------------------------------------
# Edge & EdgeScores
# ---------------------------------------------------------------------------


class TestEdgeScores:
    def test_valid_scores(self):
        s = EdgeScores(
            harmonic=0.85, bpm=0.9, energy=0.7,
            groove=1.0, frequency=0.5, mix_quality=0.88,
        )
        assert s.harmonic == 0.85

    def test_score_above_1_fails(self):
        with pytest.raises(ValidationError):
            EdgeScores(
                harmonic=1.1, bpm=0.9, energy=0.7,
                groove=1.0, frequency=0.5, mix_quality=0.88,
            )

    def test_score_below_0_fails(self):
        with pytest.raises(ValidationError):
            EdgeScores(
                harmonic=-0.1, bpm=0.9, energy=0.7,
                groove=1.0, frequency=0.5, mix_quality=0.88,
            )

    def test_boundary_values(self):
        s = EdgeScores(
            harmonic=0.0, bpm=0.0, energy=0.0,
            groove=0.0, frequency=0.0, mix_quality=0.0,
        )
        assert s.harmonic == 0.0
        s2 = EdgeScores(
            harmonic=1.0, bpm=1.0, energy=1.0,
            groove=1.0, frequency=1.0, mix_quality=1.0,
        )
        assert s2.mix_quality == 1.0


class TestEdge:
    def test_create_edge(self):
        src = uuid4()
        tgt = uuid4()
        e = Edge(
            source_id=src, target_id=tgt,
            compatibility_score=0.85,
            scores=EdgeScores(
                harmonic=0.85, bpm=0.9, energy=0.8,
                groove=1.0, frequency=0.7, mix_quality=0.88,
            ),
        )
        assert e.source_id == src
        assert e.target_id == tgt
        assert e.compatibility_score == 0.85
        assert e.is_user_created is False

    def test_edge_user_created(self):
        e = Edge(
            source_id=uuid4(), target_id=uuid4(),
            compatibility_score=0.5,
            scores=EdgeScores(
                harmonic=0.5, bpm=0.5, energy=0.5,
                groove=0.5, frequency=0.5, mix_quality=0.5,
            ),
            is_user_created=True,
        )
        assert e.is_user_created is True

    def test_edge_has_uuid(self):
        e = Edge(
            source_id=uuid4(), target_id=uuid4(),
            compatibility_score=0.5,
            scores=EdgeScores(
                harmonic=0.5, bpm=0.5, energy=0.5,
                groove=0.5, frequency=0.5, mix_quality=0.5,
            ),
        )
        assert e.id is not None

    def test_compatibility_above_1_fails(self):
        with pytest.raises(ValidationError):
            Edge(
                source_id=uuid4(), target_id=uuid4(),
                compatibility_score=1.5,
                scores=EdgeScores(
                    harmonic=0.5, bpm=0.5, energy=0.5,
                    groove=0.5, frequency=0.5, mix_quality=0.5,
                ),
            )


# ---------------------------------------------------------------------------
# SuggestionConfig
# ---------------------------------------------------------------------------


class TestSuggestionConfig:
    def test_default_weights(self):
        cfg = SuggestionConfig()
        assert cfg.harmonic_weight == 0.30
        assert cfg.bpm_weight == 0.25
        assert cfg.energy_weight == 0.15
        assert cfg.groove_weight == 0.10
        assert cfg.frequency_weight == 0.10
        assert cfg.mix_quality_weight == 0.10

    def test_normalized_weights_sum_to_one(self):
        cfg = SuggestionConfig()
        w = cfg.normalized_weights()
        assert math.isclose(sum(w.values()), 1.0, rel_tol=1e-9)

    def test_custom_weights_normalize(self):
        cfg = SuggestionConfig(
            harmonic_weight=0.50, bpm_weight=0.50,
            energy_weight=0.0, groove_weight=0.0,
            frequency_weight=0.0, mix_quality_weight=0.0,
        )
        w = cfg.normalized_weights()
        assert math.isclose(sum(w.values()), 1.0, rel_tol=1e-9)
        assert math.isclose(w["harmonic"], 0.5, rel_tol=1e-9)
        assert math.isclose(w["bpm"], 0.5, rel_tol=1e-9)

    def test_unequal_weights_normalize(self):
        cfg = SuggestionConfig(
            harmonic_weight=1.0, bpm_weight=1.0,
            energy_weight=1.0, groove_weight=1.0,
            frequency_weight=1.0, mix_quality_weight=1.0,
        )
        w = cfg.normalized_weights()
        assert math.isclose(sum(w.values()), 1.0, rel_tol=1e-9)
        # All equal, each should be 1/6
        for v in w.values():
            assert math.isclose(v, 1.0 / 6.0, rel_tol=1e-9)

    def test_default_strategy(self):
        cfg = SuggestionConfig()
        assert cfg.strategy == SuggestionStrategy.HARMONIC_FLOW

    def test_default_filters(self):
        cfg = SuggestionConfig()
        assert cfg.bpm_min is None
        assert cfg.bpm_max is None
        assert cfg.key_lock is False
        assert cfg.groove_lock is False
        assert cfg.exclude_cluster_ids == []

    def test_num_suggestions_default(self):
        cfg = SuggestionConfig()
        assert cfg.num_suggestions == 8
        assert cfg.diversity_bonus == 0.1


# ---------------------------------------------------------------------------
# Playlist
# ---------------------------------------------------------------------------


class TestPlaylist:
    def test_create_playlist(self):
        t1, t2 = uuid4(), uuid4()
        pl = Playlist(name="My Set", track_ids=[t1, t2])
        assert pl.name == "My Set"
        assert len(pl.track_ids) == 2
        assert pl.id is not None

    def test_playlist_defaults(self):
        pl = Playlist(name="Empty", track_ids=[])
        assert pl.segments == []
        assert pl.total_duration == 0.0
        assert pl.avg_compatibility == 0.0
