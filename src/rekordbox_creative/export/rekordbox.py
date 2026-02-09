"""Rekordbox XML playlist format export.

Generates XML compatible with Rekordbox's import format.
"""

from __future__ import annotations

import xml.etree.ElementTree as ET
from pathlib import Path
from urllib.parse import quote

from rekordbox_creative.db.models import Track


def _track_to_xml_element(track: Track, track_id: int) -> ET.Element:
    """Create a <TRACK> element for a single track."""
    el = ET.SubElement(ET.Element("root"), "TRACK")
    el.set("TrackID", str(track_id))
    el.set("Name", track.metadata.title or track.filename)
    el.set("Artist", track.metadata.artist or "")
    el.set("Album", track.metadata.album or "")
    el.set("Genre", track.metadata.genre or "")
    el.set("Kind", "MP3 File")
    el.set("TotalTime", str(int(track.duration_seconds)))
    el.set("AverageBpm", f"{track.dj_metrics.bpm:.2f}")
    el.set("Tonality", track.dj_metrics.key)

    # Rekordbox expects file:// URIs
    file_path = track.file_path.replace("\\", "/")
    if not file_path.startswith("/"):
        file_path = "/" + file_path
    el.set("Location", "file://localhost" + quote(file_path))

    return el


def export_rekordbox_xml(
    tracks: list[Track],
    output_path: Path | str,
    *,
    playlist_name: str = "Rekordbox Creative Set",
) -> Path:
    """Write a Rekordbox-compatible XML playlist file.

    Args:
        tracks: Ordered list of tracks to include.
        output_path: File path to write (will be created/overwritten).
        playlist_name: Name of the playlist in Rekordbox.

    Returns:
        The output path as a Path object.
    """
    output_path = Path(output_path)

    # Root DJ_PLAYLISTS element
    root = ET.Element("DJ_PLAYLISTS", Version="1.0.0")

    # PRODUCT element
    product = ET.SubElement(root, "PRODUCT")
    product.set("Name", "rekordbox_creative")
    product.set("Version", "1.0.0")
    product.set("Company", "")

    # COLLECTION
    collection = ET.SubElement(root, "COLLECTION", Entries=str(len(tracks)))

    track_id_map: dict[int, int] = {}
    for idx, track in enumerate(tracks, start=1):
        track_el = _track_to_xml_element(track, idx)
        collection.append(track_el)
        track_id_map[idx] = idx

    # PLAYLISTS
    playlists = ET.SubElement(root, "PLAYLISTS")
    playlist_node = ET.SubElement(
        playlists, "NODE", Type="1", Name="ROOT", Count="1"
    )
    playlist_folder = ET.SubElement(
        playlist_node,
        "NODE",
        Name=playlist_name,
        Type="1",
        KeyType="0",
        Entries=str(len(tracks)),
    )
    for idx in range(1, len(tracks) + 1):
        ET.SubElement(playlist_folder, "TRACK", Key=str(idx))

    # Write XML
    tree = ET.ElementTree(root)
    ET.indent(tree, space="  ")
    tree.write(str(output_path), encoding="utf-8", xml_declaration=True)
    return output_path
