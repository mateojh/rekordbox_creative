"""Tests for PREF-001 (Settings Persistence) and PREF-002 (Edge Threshold)."""

import pytest

from rekordbox_creative.db.database import Database
from rekordbox_creative.db.models import SuggestionConfig, SuggestionStrategy
from rekordbox_creative.db.preferences import PreferencesManager


@pytest.fixture
def prefs():
    """PreferencesManager with in-memory DB."""
    db = Database(":memory:")
    mgr = PreferencesManager(db)
    yield mgr
    db.close()


@pytest.fixture
def prefs_file(tmp_path):
    """PreferencesManager with file-based DB for persistence tests."""
    db_path = tmp_path / "prefs.db"
    db = Database(db_path)
    mgr = PreferencesManager(db)
    yield mgr, db_path
    db.close()


# ===========================================================================
# PREF-001 — SuggestionConfig persistence
# ===========================================================================


class TestSuggestionConfigPersistence:
    def test_load_defaults_when_empty(self, prefs):
        config = prefs.load_suggestion_config()
        assert config.harmonic_weight == 0.30
        assert config.bpm_weight == 0.25
        assert config.strategy == SuggestionStrategy.HARMONIC_FLOW
        assert config.num_suggestions == 8

    def test_save_and_load_custom_weights(self, prefs):
        config = SuggestionConfig(harmonic_weight=0.50, bpm_weight=0.10)
        prefs.save_suggestion_config(config)
        loaded = prefs.load_suggestion_config()
        assert loaded.harmonic_weight == 0.50
        assert loaded.bpm_weight == 0.10

    def test_save_and_load_strategy(self, prefs):
        config = SuggestionConfig(strategy=SuggestionStrategy.ENERGY_ARC)
        prefs.save_suggestion_config(config)
        loaded = prefs.load_suggestion_config()
        assert loaded.strategy == SuggestionStrategy.ENERGY_ARC

    def test_save_and_load_filters(self, prefs):
        config = SuggestionConfig(
            bpm_min=125.0, bpm_max=135.0,
            key_lock=True, groove_lock=True,
            exclude_cluster_ids=[1, 2],
        )
        prefs.save_suggestion_config(config)
        loaded = prefs.load_suggestion_config()
        assert loaded.bpm_min == 125.0
        assert loaded.bpm_max == 135.0
        assert loaded.key_lock is True
        assert loaded.groove_lock is True
        assert loaded.exclude_cluster_ids == [1, 2]

    def test_overwrite_config(self, prefs):
        config1 = SuggestionConfig(harmonic_weight=0.50)
        prefs.save_suggestion_config(config1)
        config2 = SuggestionConfig(harmonic_weight=0.20)
        prefs.save_suggestion_config(config2)
        loaded = prefs.load_suggestion_config()
        assert loaded.harmonic_weight == 0.20

    def test_normalized_weights_preserved(self, prefs):
        config = SuggestionConfig(
            harmonic_weight=0.40, bpm_weight=0.30, energy_weight=0.10,
            groove_weight=0.05, frequency_weight=0.10, mix_quality_weight=0.05,
        )
        prefs.save_suggestion_config(config)
        loaded = prefs.load_suggestion_config()
        weights = loaded.normalized_weights()
        total = sum(weights.values())
        assert abs(total - 1.0) < 1e-9

    def test_config_survives_reopen(self, prefs_file, tmp_path):
        mgr, db_path = prefs_file
        config = SuggestionConfig(
            strategy=SuggestionStrategy.DISCOVERY,
            harmonic_weight=0.40,
            diversity_bonus=0.2,
        )
        mgr.save_suggestion_config(config)
        mgr.db.close()

        # Reopen with fresh connection
        db2 = Database(db_path)
        mgr2 = PreferencesManager(db2)
        loaded = mgr2.load_suggestion_config()
        db2.close()

        assert loaded.strategy == SuggestionStrategy.DISCOVERY
        assert loaded.harmonic_weight == 0.40
        assert loaded.diversity_bonus == 0.2


# ===========================================================================
# PREF-002 — Edge threshold persistence
# ===========================================================================


class TestEdgeThresholdPersistence:
    def test_default_threshold(self, prefs):
        assert prefs.load_edge_threshold() == 0.3

    def test_save_and_load_threshold(self, prefs):
        prefs.save_edge_threshold(0.5)
        assert prefs.load_edge_threshold() == 0.5

    def test_threshold_overwrite(self, prefs):
        prefs.save_edge_threshold(0.5)
        prefs.save_edge_threshold(0.1)
        assert prefs.load_edge_threshold() == 0.1

    def test_threshold_survives_reopen(self, prefs_file, tmp_path):
        mgr, db_path = prefs_file
        mgr.save_edge_threshold(0.7)
        mgr.db.close()

        db2 = Database(db_path)
        mgr2 = PreferencesManager(db2)
        assert mgr2.load_edge_threshold() == 0.7
        db2.close()


# ===========================================================================
# Other preferences
# ===========================================================================


class TestOtherPreferences:
    def test_last_folder_default_none(self, prefs):
        assert prefs.load_last_folder() is None

    def test_save_and_load_last_folder(self, prefs):
        prefs.save_last_folder("/home/user/music")
        assert prefs.load_last_folder() == "/home/user/music"

    def test_layout_mode_default(self, prefs):
        assert prefs.load_layout_mode() == "force_directed"

    def test_save_and_load_layout_mode(self, prefs):
        prefs.save_layout_mode("scatter")
        assert prefs.load_layout_mode() == "scatter"

    def test_color_mode_default(self, prefs):
        assert prefs.load_color_mode() == "key"

    def test_save_and_load_color_mode(self, prefs):
        prefs.save_color_mode("energy")
        assert prefs.load_color_mode() == "energy"
