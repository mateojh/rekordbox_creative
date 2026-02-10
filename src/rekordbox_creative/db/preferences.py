"""Settings persistence via the preferences table.

Stores and retrieves user-configurable settings (scoring weights,
strategy, filters, edge threshold) as JSON in the preferences table.
"""

from __future__ import annotations

import json
import logging

from rekordbox_creative.db.database import Database
from rekordbox_creative.db.models import SuggestionConfig

logger = logging.getLogger(__name__)

# Keys used in the preferences table
_KEY_SUGGESTION_CONFIG = "suggestion_config"
_KEY_EDGE_THRESHOLD = "edge_threshold"
_KEY_LAST_FOLDER = "last_folder"
_KEY_LAYOUT_MODE = "layout_mode"
_KEY_COLOR_MODE = "color_mode"


class PreferencesManager:
    """Read/write user preferences backed by the Database preferences table."""

    def __init__(self, database: Database) -> None:
        self.db = database

    # ------------------------------------------------------------------
    # SuggestionConfig (PREF-001)
    # ------------------------------------------------------------------

    def save_suggestion_config(self, config: SuggestionConfig) -> None:
        """Persist the full SuggestionConfig as JSON."""
        self.db.set_preference(_KEY_SUGGESTION_CONFIG, config.model_dump_json())

    def load_suggestion_config(self) -> SuggestionConfig:
        """Load SuggestionConfig from DB, or return defaults."""
        raw = self.db.get_preference(_KEY_SUGGESTION_CONFIG)
        if raw is None:
            return SuggestionConfig()
        return SuggestionConfig.model_validate_json(raw)

    # ------------------------------------------------------------------
    # Edge threshold (PREF-002)
    # ------------------------------------------------------------------

    def save_edge_threshold(self, threshold: float) -> None:
        """Persist the edge display threshold."""
        self.db.set_preference(_KEY_EDGE_THRESHOLD, json.dumps(threshold))

    def load_edge_threshold(self) -> float:
        """Load edge threshold from DB, or return default 0.3."""
        raw = self.db.get_preference(_KEY_EDGE_THRESHOLD)
        if raw is None:
            return 0.3
        return float(json.loads(raw))

    # ------------------------------------------------------------------
    # General string preferences
    # ------------------------------------------------------------------

    def save_last_folder(self, path: str) -> None:
        """Remember the last music folder the user selected."""
        self.db.set_preference(_KEY_LAST_FOLDER, path)

    def load_last_folder(self) -> str | None:
        """Return the last music folder, or None."""
        return self.db.get_preference(_KEY_LAST_FOLDER)

    def save_layout_mode(self, mode: str) -> None:
        """Persist the layout mode (force_directed, scatter, linear)."""
        self.db.set_preference(_KEY_LAYOUT_MODE, mode)

    def load_layout_mode(self) -> str:
        """Load layout mode from DB, or return default."""
        return self.db.get_preference(_KEY_LAYOUT_MODE) or "force_directed"

    def save_color_mode(self, mode: str) -> None:
        """Persist the color mode (key, cluster, energy)."""
        self.db.set_preference(_KEY_COLOR_MODE, mode)

    def load_color_mode(self) -> str:
        """Load color mode from DB, or return default."""
        return self.db.get_preference(_KEY_COLOR_MODE) or "key"
