"""Pydantic v2 data models — all data structures from DATA_MODELS.md."""

from datetime import datetime
from enum import Enum
from uuid import UUID, uuid4

from pydantic import BaseModel, Field

# ---------------------------------------------------------------------------
# Track sub-models
# ---------------------------------------------------------------------------

class SpotifyStyleMetrics(BaseModel):
    """Normalized 0.0-1.0 audio feature scores."""

    energy: float = Field(ge=0.0, le=1.0, description="Perceived intensity and activity")
    danceability: float = Field(ge=0.0, le=1.0, description="Suitability for dancing")
    acousticness: float = Field(ge=0.0, le=1.0, description="Confidence track is acoustic")
    instrumentalness: float = Field(
        ge=0.0, le=1.0, description="Confidence no vocals present"
    )
    valence: float = Field(ge=0.0, le=1.0, description="Musical positiveness/happiness")
    liveness: float = Field(ge=0.0, le=1.0, description="Presence of audience")


class DJMetrics(BaseModel):
    """DJ-specific analysis results."""

    bpm: float = Field(gt=0, description="Beats per minute")
    bpm_stability: float = Field(ge=0.0, le=1.0, description="Tempo consistency")
    key: str = Field(pattern=r"^\d{1,2}[AB]$", description="Camelot notation (e.g. '8A')")
    key_confidence: float = Field(ge=0.0, le=1.0, description="Key detection confidence")
    mix_in_score: float = Field(ge=0.0, le=1.0, description="Intro mix-friendliness")
    mix_out_score: float = Field(ge=0.0, le=1.0, description="Outro mix-friendliness")
    frequency_weight: str = Field(
        description="bass_heavy | bright | mid_focused | balanced"
    )
    groove_type: str = Field(
        description=(
            "four_on_floor | breakbeat | half_time | complex | syncopated | straight"
        )
    )


class TrackStructure(BaseModel):
    """Structural landmarks in the track (timestamps in seconds)."""

    drops: list[float] = Field(default_factory=list, description="Drop timestamps")
    breakdowns: list[list[float]] = Field(
        default_factory=list, description="[start, end] pairs"
    )
    vocal_segments: list[list[float]] = Field(
        default_factory=list, description="[start, end] pairs"
    )
    build_sections: list[list[float]] = Field(
        default_factory=list, description="[start, end] pairs"
    )
    intro_end: float | None = Field(None, description="Where intro ends")
    outro_start: float | None = Field(None, description="Where outro begins")


class TrackMetadata(BaseModel):
    """ID3/file metadata."""

    artist: str | None = None
    title: str | None = None
    album: str | None = None
    genre: str | None = None
    year: int | None = None
    track_number: int | None = None
    comment: str | None = None


# ---------------------------------------------------------------------------
# Track (central entity)
# ---------------------------------------------------------------------------

class Track(BaseModel):
    """Complete track entity with all analysis data."""

    id: UUID = Field(default_factory=uuid4)
    file_path: str
    file_hash: str
    filename: str
    duration_seconds: float
    sample_rate: int = 22050

    spotify_style: SpotifyStyleMetrics
    dj_metrics: DJMetrics
    structure: TrackStructure

    metadata: TrackMetadata = Field(default_factory=TrackMetadata)

    cluster_id: int | None = None
    times_used: int = 0
    analyzed_at: datetime = Field(default_factory=datetime.now)

    model_config = {"frozen": False}


# ---------------------------------------------------------------------------
# Edge
# ---------------------------------------------------------------------------

class EdgeScores(BaseModel):
    """Breakdown of compatibility components."""

    harmonic: float = Field(ge=0.0, le=1.0)
    bpm: float = Field(ge=0.0, le=1.0)
    energy: float = Field(ge=0.0, le=1.0)
    groove: float = Field(ge=0.0, le=1.0)
    frequency: float = Field(ge=0.0, le=1.0)
    mix_quality: float = Field(ge=0.0, le=1.0)


class Edge(BaseModel):
    """Weighted directional edge between two tracks."""

    id: UUID = Field(default_factory=uuid4)
    source_id: UUID
    target_id: UUID
    compatibility_score: float = Field(ge=0.0, le=1.0)
    scores: EdgeScores
    is_user_created: bool = False


# ---------------------------------------------------------------------------
# Cluster
# ---------------------------------------------------------------------------

class Cluster(BaseModel):
    """A vibe island — group of sonically similar tracks."""

    id: int
    label: str
    track_ids: list[UUID]
    centroid: list[float]

    avg_bpm: float
    avg_energy: float
    dominant_key: str
    dominant_groove: str
    dominant_frequency_weight: str
    track_count: int


# ---------------------------------------------------------------------------
# Playlist / Set
# ---------------------------------------------------------------------------

class SetSegment(BaseModel):
    """A named chapter/segment within a set."""

    name: str
    start_position: int
    end_position: int


class Playlist(BaseModel):
    """An ordered set of tracks with metadata."""

    id: UUID = Field(default_factory=uuid4)
    name: str
    track_ids: list[UUID]
    segments: list[SetSegment] = Field(default_factory=list)
    created_at: datetime = Field(default_factory=datetime.now)
    updated_at: datetime = Field(default_factory=datetime.now)

    total_duration: float = 0.0
    avg_compatibility: float = 0.0
    total_compatibility: float = 0.0


# ---------------------------------------------------------------------------
# Graph state (save/load)
# ---------------------------------------------------------------------------

class NodePosition(BaseModel):
    """Canvas position of a node."""

    track_id: UUID
    x: float
    y: float


class ViewportState(BaseModel):
    """Camera/viewport state."""

    center_x: float = 0.0
    center_y: float = 0.0
    zoom: float = 1.0


class GraphState(BaseModel):
    """Complete serializable graph state for save/load."""

    node_positions: list[NodePosition]
    viewport: ViewportState
    active_playlist_id: UUID | None = None
    layout_mode: str = "force_directed"
    color_mode: str = "key"
    edge_threshold: float = 0.3
    selected_node_ids: list[UUID] = Field(default_factory=list)


# ---------------------------------------------------------------------------
# Suggestion
# ---------------------------------------------------------------------------

class SuggestionStrategy(str, Enum):
    HARMONIC_FLOW = "harmonic_flow"
    ENERGY_ARC = "energy_arc"
    DISCOVERY = "discovery"
    GROOVE_LOCK = "groove_lock"
    CONTRAST = "contrast"


class SuggestionConfig(BaseModel):
    """User-tunable suggestion behavior."""

    harmonic_weight: float = 0.30
    bpm_weight: float = 0.25
    energy_weight: float = 0.15
    groove_weight: float = 0.10
    frequency_weight: float = 0.10
    mix_quality_weight: float = 0.10

    strategy: SuggestionStrategy = SuggestionStrategy.HARMONIC_FLOW

    bpm_min: float | None = None
    bpm_max: float | None = None
    key_lock: bool = False
    groove_lock: bool = False
    exclude_cluster_ids: list[int] = Field(default_factory=list)

    num_suggestions: int = 8
    diversity_bonus: float = 0.1

    def normalized_weights(self) -> dict[str, float]:
        """Return weights normalized to sum to 1.0."""
        total = (
            self.harmonic_weight
            + self.bpm_weight
            + self.energy_weight
            + self.groove_weight
            + self.frequency_weight
            + self.mix_quality_weight
        )
        return {
            "harmonic": self.harmonic_weight / total,
            "bpm": self.bpm_weight / total,
            "energy": self.energy_weight / total,
            "groove": self.groove_weight / total,
            "frequency": self.frequency_weight / total,
            "mix_quality": self.mix_quality_weight / total,
        }


class SuggestionResult(BaseModel):
    """A single track suggestion with scoring breakdown."""

    track_id: UUID
    final_score: float
    base_compatibility: float
    strategy_modifier: float
    context_modifier: float
    diversity_bonus: float
    score_breakdown: EdgeScores
