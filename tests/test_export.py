"""Tests for export functionality."""

import csv
import xml.etree.ElementTree as ET

import pytest

from rekordbox_creative.db.models import (
    DJMetrics,
    GraphState,
    NodePosition,
    SpotifyStyleMetrics,
    Track,
    TrackMetadata,
    TrackStructure,
    ViewportState,
)
from rekordbox_creative.export.csv import CSV_COLUMNS, export_csv
from rekordbox_creative.export.m3u import export_m3u
from rekordbox_creative.export.playlist import format_duration, resolve_tracks
from rekordbox_creative.export.rekordbox import export_rekordbox_xml


def _make_track(
    bpm=128.0,
    key="8A",
    energy=0.8,
    file_path="/music/track.mp3",
    artist=None,
    title=None,
    **kw,
) -> Track:
    return Track(
        file_path=file_path,
        file_hash=kw.get("file_hash", f"hash_{file_path}"),
        filename=kw.get("filename", file_path.split("/")[-1]),
        duration_seconds=kw.get("duration_seconds", 360.0),
        spotify_style=SpotifyStyleMetrics(
            energy=energy, danceability=0.7, acousticness=0.05,
            instrumentalness=0.6, valence=0.5, liveness=0.1,
        ),
        dj_metrics=DJMetrics(
            bpm=bpm, bpm_stability=0.95, key=key, key_confidence=0.85,
            mix_in_score=0.85, mix_out_score=0.80,
            frequency_weight="balanced", groove_type="four_on_floor",
        ),
        structure=TrackStructure(),
        metadata=TrackMetadata(artist=artist, title=title),
    )


@pytest.fixture
def sample_tracks():
    return [
        _make_track(bpm=128.0, key="8A", energy=0.8, file_path="/music/song1.mp3",
                     file_hash="h1", artist="DJ Alpha", title="Track One",
                     duration_seconds=360.0),
        _make_track(bpm=130.0, key="9A", energy=0.85, file_path="/music/song2.mp3",
                     file_hash="h2", artist="DJ Beta", title="Track Two",
                     duration_seconds=300.0),
        _make_track(bpm=125.0, key="7A", energy=0.7, file_path="/music/song3.mp3",
                     file_hash="h3", artist=None, title=None,
                     duration_seconds=420.0),
    ]


# ===========================================================================
# playlist.py helpers
# ===========================================================================


class TestFormatDuration:
    def test_seconds_only(self):
        assert format_duration(45.0) == "0:45"

    def test_minutes(self):
        assert format_duration(180.0) == "3:00"

    def test_minutes_and_seconds(self):
        assert format_duration(195.5) == "3:15"

    def test_hours(self):
        assert format_duration(3661.0) == "1:01:01"

    def test_zero(self):
        assert format_duration(0.0) == "0:00"


class TestResolveTracks:
    def test_resolves_in_order(self, sample_tracks):
        ids = [sample_tracks[2].id, sample_tracks[0].id]
        result = resolve_tracks(ids, sample_tracks)
        assert len(result) == 2
        assert result[0].id == sample_tracks[2].id
        assert result[1].id == sample_tracks[0].id

    def test_skips_missing_ids(self, sample_tracks):
        from uuid import uuid4

        ids = [sample_tracks[0].id, uuid4()]
        result = resolve_tracks(ids, sample_tracks)
        assert len(result) == 1

    def test_empty_ids(self, sample_tracks):
        assert resolve_tracks([], sample_tracks) == []


# ===========================================================================
# M3U export
# ===========================================================================


class TestM3UExport:
    def test_creates_file(self, sample_tracks, tmp_path):
        out = tmp_path / "playlist.m3u"
        result = export_m3u(sample_tracks, out)
        assert result.exists()

    def test_header(self, sample_tracks, tmp_path):
        out = tmp_path / "playlist.m3u"
        export_m3u(sample_tracks, out)
        content = out.read_text(encoding="utf-8")
        assert content.startswith("#EXTM3U")

    def test_custom_name(self, sample_tracks, tmp_path):
        out = tmp_path / "playlist.m3u"
        export_m3u(sample_tracks, out, playlist_name="My DJ Set")
        content = out.read_text(encoding="utf-8")
        assert "# My DJ Set" in content

    def test_track_entries(self, sample_tracks, tmp_path):
        out = tmp_path / "playlist.m3u"
        export_m3u(sample_tracks, out)
        content = out.read_text(encoding="utf-8")
        lines = content.strip().split("\n")
        # Header line + comment + 3 * (EXTINF + path) = 2 + 6 = 8
        assert len(lines) == 8

    def test_extinf_format(self, sample_tracks, tmp_path):
        out = tmp_path / "playlist.m3u"
        export_m3u(sample_tracks, out)
        content = out.read_text(encoding="utf-8")
        assert "#EXTINF:360,DJ Alpha - Track One" in content

    def test_missing_metadata_uses_filename(self, sample_tracks, tmp_path):
        out = tmp_path / "playlist.m3u"
        export_m3u(sample_tracks, out)
        content = out.read_text(encoding="utf-8")
        # Track 3 has no artist/title
        assert "Unknown Artist - song3.mp3" in content

    def test_file_paths_present(self, sample_tracks, tmp_path):
        out = tmp_path / "playlist.m3u"
        export_m3u(sample_tracks, out)
        content = out.read_text(encoding="utf-8")
        for track in sample_tracks:
            assert track.file_path in content

    def test_empty_tracklist(self, tmp_path):
        out = tmp_path / "empty.m3u"
        export_m3u([], out)
        content = out.read_text(encoding="utf-8")
        assert "#EXTM3U" in content

    def test_returns_path(self, sample_tracks, tmp_path):
        out = tmp_path / "playlist.m3u"
        result = export_m3u(sample_tracks, out)
        assert result == out

    def test_accepts_string_path(self, sample_tracks, tmp_path):
        out = str(tmp_path / "playlist.m3u")
        result = export_m3u(sample_tracks, out)
        assert result.exists()


# ===========================================================================
# Rekordbox XML export
# ===========================================================================


class TestRekordboxXMLExport:
    def test_creates_file(self, sample_tracks, tmp_path):
        out = tmp_path / "rekordbox.xml"
        result = export_rekordbox_xml(sample_tracks, out)
        assert result.exists()

    def test_xml_valid(self, sample_tracks, tmp_path):
        out = tmp_path / "rekordbox.xml"
        export_rekordbox_xml(sample_tracks, out)
        tree = ET.parse(out)
        root = tree.getroot()
        assert root.tag == "DJ_PLAYLISTS"

    def test_collection_count(self, sample_tracks, tmp_path):
        out = tmp_path / "rekordbox.xml"
        export_rekordbox_xml(sample_tracks, out)
        tree = ET.parse(out)
        root = tree.getroot()
        collection = root.find("COLLECTION")
        assert collection is not None
        assert collection.get("Entries") == "3"

    def test_track_elements(self, sample_tracks, tmp_path):
        out = tmp_path / "rekordbox.xml"
        export_rekordbox_xml(sample_tracks, out)
        tree = ET.parse(out)
        root = tree.getroot()
        collection = root.find("COLLECTION")
        tracks = collection.findall("TRACK")
        assert len(tracks) == 3

    def test_track_attributes(self, sample_tracks, tmp_path):
        out = tmp_path / "rekordbox.xml"
        export_rekordbox_xml(sample_tracks, out)
        tree = ET.parse(out)
        root = tree.getroot()
        collection = root.find("COLLECTION")
        first_track = collection.findall("TRACK")[0]
        assert first_track.get("Name") == "Track One"
        assert first_track.get("Artist") == "DJ Alpha"
        assert first_track.get("AverageBpm") == "128.00"
        assert first_track.get("Tonality") == "8A"

    def test_playlist_node(self, sample_tracks, tmp_path):
        out = tmp_path / "rekordbox.xml"
        export_rekordbox_xml(sample_tracks, out, playlist_name="Test Set")
        tree = ET.parse(out)
        root = tree.getroot()
        playlists = root.find("PLAYLISTS")
        assert playlists is not None

    def test_empty_tracklist(self, tmp_path):
        out = tmp_path / "empty.xml"
        export_rekordbox_xml([], out)
        tree = ET.parse(out)
        root = tree.getroot()
        collection = root.find("COLLECTION")
        assert collection.get("Entries") == "0"

    def test_location_format(self, sample_tracks, tmp_path):
        out = tmp_path / "rekordbox.xml"
        export_rekordbox_xml(sample_tracks, out)
        tree = ET.parse(out)
        root = tree.getroot()
        collection = root.find("COLLECTION")
        first_track = collection.findall("TRACK")[0]
        location = first_track.get("Location")
        assert location.startswith("file://localhost/")

    def test_accepts_string_path(self, sample_tracks, tmp_path):
        out = str(tmp_path / "rekordbox.xml")
        result = export_rekordbox_xml(sample_tracks, out)
        assert result.exists()


# ===========================================================================
# CSV export
# ===========================================================================


class TestCSVExport:
    def test_creates_file(self, sample_tracks, tmp_path):
        out = tmp_path / "library.csv"
        result = export_csv(sample_tracks, out)
        assert result.exists()

    def test_header_row(self, sample_tracks, tmp_path):
        out = tmp_path / "library.csv"
        export_csv(sample_tracks, out)
        with out.open(encoding="utf-8") as f:
            reader = csv.reader(f)
            header = next(reader)
            assert header == CSV_COLUMNS

    def test_row_count(self, sample_tracks, tmp_path):
        out = tmp_path / "library.csv"
        export_csv(sample_tracks, out)
        with out.open(encoding="utf-8") as f:
            reader = csv.reader(f)
            rows = list(reader)
            assert len(rows) == 4  # header + 3 tracks

    def test_data_integrity(self, sample_tracks, tmp_path):
        out = tmp_path / "library.csv"
        export_csv(sample_tracks, out)
        with out.open(encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            assert rows[0]["bpm"] == "128.0"
            assert rows[0]["key"] == "8A"
            assert rows[0]["energy"] == "0.8"
            assert rows[0]["artist"] == "DJ Alpha"
            assert rows[0]["title"] == "Track One"

    def test_all_columns_present(self, sample_tracks, tmp_path):
        out = tmp_path / "library.csv"
        export_csv(sample_tracks, out)
        with out.open(encoding="utf-8") as f:
            reader = csv.DictReader(f)
            for row in reader:
                for col in CSV_COLUMNS:
                    assert col in row

    def test_empty_tracklist(self, tmp_path):
        out = tmp_path / "empty.csv"
        export_csv([], out)
        with out.open(encoding="utf-8") as f:
            reader = csv.reader(f)
            rows = list(reader)
            assert len(rows) == 1  # header only

    def test_missing_metadata(self, sample_tracks, tmp_path):
        out = tmp_path / "library.csv"
        export_csv(sample_tracks, out)
        with out.open(encoding="utf-8") as f:
            reader = csv.DictReader(f)
            rows = list(reader)
            # Track 3 has no artist/title
            assert rows[2]["artist"] == ""
            assert rows[2]["title"] == ""

    def test_accepts_string_path(self, sample_tracks, tmp_path):
        out = str(tmp_path / "library.csv")
        result = export_csv(sample_tracks, out)
        assert result.exists()


# ===========================================================================
# Save/Load Graph State (EXP-004)
# ===========================================================================


class TestGraphStateSaveLoad:
    def test_graph_state_round_trip(self, sample_tracks, tmp_path):
        """GraphState can be serialized to JSON and loaded back."""
        positions = [
            NodePosition(track_id=t.id, x=i * 100.0, y=i * 50.0)
            for i, t in enumerate(sample_tracks)
        ]
        state = GraphState(
            node_positions=positions,
            viewport=ViewportState(center_x=100.0, center_y=200.0, zoom=1.5),
            layout_mode="scatter",
            color_mode="cluster",
            edge_threshold=0.5,
        )

        out = tmp_path / "graph_state.json"
        out.write_text(state.model_dump_json(indent=2), encoding="utf-8")

        loaded = GraphState.model_validate_json(out.read_text(encoding="utf-8"))
        assert len(loaded.node_positions) == 3
        assert loaded.viewport.zoom == 1.5
        assert loaded.layout_mode == "scatter"
        assert loaded.edge_threshold == 0.5

    def test_graph_state_with_selected_nodes(self, sample_tracks, tmp_path):
        state = GraphState(
            node_positions=[
                NodePosition(track_id=sample_tracks[0].id, x=0.0, y=0.0)
            ],
            viewport=ViewportState(),
            selected_node_ids=[sample_tracks[0].id],
        )
        json_str = state.model_dump_json()
        loaded = GraphState.model_validate_json(json_str)
        assert len(loaded.selected_node_ids) == 1

    def test_graph_state_defaults(self):
        state = GraphState(
            node_positions=[],
            viewport=ViewportState(),
        )
        assert state.layout_mode == "force_directed"
        assert state.color_mode == "key"
        assert state.edge_threshold == 0.3
