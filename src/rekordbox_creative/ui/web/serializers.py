"""Serialize Track/Edge/Position data to JSON for the Sigma.js frontend."""

from __future__ import annotations

import json
from uuid import UUID

from rekordbox_creative.db.models import Edge, Track
from rekordbox_creative.graph.layout import NodePosition


# Camelot key number -> hex color (matches nodes.py)
CAMELOT_COLORS: dict[int, str] = {
    1: "#FF4444", 2: "#FF6633", 3: "#FF9922", 4: "#FFCC11",
    5: "#99DD00", 6: "#44CC44", 7: "#22BBAA", 8: "#22AADD",
    9: "#4488FF", 10: "#6644FF", 11: "#AA44FF", 12: "#FF44AA",
}


def _key_color(key: str) -> str:
    """Get hex color for a Camelot key string like '8A'."""
    try:
        num = int(key[:-1])
        mode = key[-1]
        base = CAMELOT_COLORS.get(num, "#888888")
        if mode == "B":
            # Lighten for major keys: blend toward white by ~40%
            r = int(base[1:3], 16)
            g = int(base[3:5], 16)
            b = int(base[5:7], 16)
            r = min(255, r + int((255 - r) * 0.4))
            g = min(255, g + int((255 - g) * 0.4))
            b = min(255, b + int((255 - b) * 0.4))
            return f"#{r:02x}{g:02x}{b:02x}"
        return base
    except (ValueError, IndexError):
        return "#888888"


def _node_size(energy: float) -> float:
    """Node size in Sigma units based on energy."""
    if energy < 0.3:
        return 5.0
    elif energy < 0.6:
        return 8.0
    elif energy < 0.8:
        return 11.0
    else:
        return 14.0


def _edge_size(score: float) -> float:
    """Edge thickness based on compatibility score."""
    if score < 0.5:
        return 0.5
    elif score < 0.7:
        return 1.0
    elif score < 0.9:
        return 1.5
    else:
        return 2.5


def _edge_color(score: float) -> str:
    """Edge color with alpha based on compatibility score."""
    if score < 0.5:
        return "rgba(255,255,255,0.08)"
    elif score < 0.7:
        return "rgba(255,255,255,0.15)"
    else:
        return "rgba(255,255,255,0.30)"


def serialize_node(track: Track, x: float = 0.0, y: float = 0.0) -> dict:
    """Serialize a Track to a Sigma.js-compatible node dict."""
    dj = track.dj_metrics
    ss = track.spotify_style
    title = track.metadata.title or track.filename
    artist = track.metadata.artist or ""
    label = f"{artist} - {title}" if artist else title
    if len(label) > 40:
        label = label[:38] + ".."

    return {
        "id": str(track.id),
        "label": label,
        "x": x,
        "y": y,
        "size": _node_size(ss.energy),
        "color": _key_color(dj.key),
        "bpm": round(dj.bpm, 1),
        "key": dj.key,
        "energy": round(ss.energy, 2),
        "groove": dj.groove_type,
        "frequency": dj.frequency_weight,
        "clusterId": track.cluster_id,
        "title": title,
        "artist": artist,
    }


def serialize_edge(edge: Edge) -> dict:
    """Serialize an Edge to a Sigma.js-compatible edge dict."""
    score = edge.compatibility_score
    return {
        "source": str(edge.source_id),
        "target": str(edge.target_id),
        "size": _edge_size(score),
        "color": _edge_color(score),
        "score": round(score, 3),
        "harmonic": round(edge.scores.harmonic, 2),
        "bpm": round(edge.scores.bpm, 2),
        "energy": round(edge.scores.energy, 2),
        "groove": round(edge.scores.groove, 2),
        "frequency": round(edge.scores.frequency, 2),
        "mixQuality": round(edge.scores.mix_quality, 2),
        "userCreated": edge.is_user_created,
    }


def serialize_graph(
    tracks: list[Track],
    edges: list[Edge],
    positions: list[NodePosition],
) -> str:
    """Build a full graph JSON string for Sigma.js loadGraph()."""
    pos_map: dict[UUID, tuple[float, float]] = {}
    for p in positions:
        pos_map[p.track_id] = (p.x, p.y)

    nodes = []
    for track in tracks:
        x, y = pos_map.get(track.id, (0.0, 0.0))
        nodes.append(serialize_node(track, x, y))

    edge_list = []
    track_ids = {t.id for t in tracks}
    for edge in edges:
        if edge.source_id in track_ids and edge.target_id in track_ids:
            edge_list.append(serialize_edge(edge))

    return json.dumps({"nodes": nodes, "edges": edge_list})


def serialize_positions(positions: list[NodePosition]) -> str:
    """Serialize positions for updatePositions()."""
    data = [
        {"id": str(p.track_id), "x": p.x, "y": p.y}
        for p in positions
    ]
    return json.dumps(data)


def serialize_clusters(
    clusters: dict[int, list[UUID]],
) -> str:
    """Serialize cluster data for drawClusterHulls()."""
    cluster_colors = [
        "#FF4444", "#44CC44", "#4488FF", "#FF9922",
        "#AA44FF", "#22BBAA", "#FFCC11", "#FF44AA",
    ]
    data = []
    for idx, (cid, track_ids) in enumerate(clusters.items()):
        if cid < 0:
            continue
        data.append({
            "id": cid,
            "trackIds": [str(tid) for tid in track_ids],
            "color": cluster_colors[idx % len(cluster_colors)],
        })
    return json.dumps(data)
