/**
 * GraphEngine — wraps Sigma.js + Graphology for the Rekordbox Creative graph.
 *
 * Provides: loadGraph, updatePositions, highlightNodes, clearHighlights,
 * setNodeInSequence, clearSequenceBadges, fitAll, addEdge, setEdgeThreshold,
 * drawClusterHulls.
 */

class GraphEngine {
    constructor(container) {
        this.container = container;
        this.graph = new graphology.Graph({ type: 'undirected', multi: false });
        this.renderer = null;
        this.selectedNode = null;
        this.hoveredNode = null;
        this.highlightedNodes = null;  // Set of node IDs or null
        this.sequenceMap = {};         // nodeId -> position (0-indexed)
        this.edgeThreshold = 0.0;
        this.clusterHulls = [];        // [{id, trackIds, color}]
        this.nodeTags = {};            // nodeId -> [{name, color}]
        this.playingNodeId = null;     // ID of currently playing track
        this._pulsePhase = 0;         // For pulse animation
        this.tagFilterIds = new Set(); // Active tag filter node IDs

        this._initRenderer();
    }

    _initRenderer() {
        this.renderer = new Sigma(this.graph, this.container, {
            minCameraRatio: 0.02,
            maxCameraRatio: 15,
            labelFont: 'Inter, Segoe UI, Arial, sans-serif',
            labelSize: 12,
            labelWeight: '500',
            labelColor: { color: '#e0e0e0' },
            labelDensity: 0.07,
            labelRenderedSizeThreshold: 6,
            renderEdgeLabels: false,
            enableEdgeClickEvents: false,
            enableEdgeHoverEvents: false,
            defaultNodeType: 'circle',
            defaultEdgeType: 'line',
            stagePadding: 40,
            zIndex: true,
            nodeReducer: (node, data) => this._nodeReducer(node, data),
            edgeReducer: (edge, data) => this._edgeReducer(edge, data),
        });

        // Set up interactions
        setupInteractions(this);
    }

    // --- Reducers: dynamic visual styling per frame ---

    _nodeReducer(node, data) {
        const res = { ...data };

        // If this node has album art loaded, use dark background so the
        // Canvas overlay image renders cleanly on top.
        if (window.nodeImageOverlay && window.nodeImageOverlay.images[node]) {
            res.color = '#1a1a2e';
        }

        // Sequence badge: gold border for nodes in the set
        if (this.sequenceMap[node] !== undefined) {
            res.borderColor = '#FFD700';
            res.borderSize = 3;
        }

        // Selection highlight
        if (this.selectedNode === node) {
            res.borderColor = '#FFFFFF';
            res.borderSize = 3;
            res.zIndex = 10;
            res.highlighted = true;
        }

        // Hover neighborhood focus
        if (this.hoveredNode) {
            if (node === this.hoveredNode) {
                res.highlighted = true;
                res.zIndex = 10;
            } else if (this.graph.hasNode(this.hoveredNode) &&
                       this.graph.areNeighbors(node, this.hoveredNode)) {
                res.highlighted = true;
                res.zIndex = 5;
            } else {
                res.color = '#3a3a4a';
                res.label = '';
                res.zIndex = 0;
            }
        }

        // Suggestion highlighting
        if (this.highlightedNodes) {
            if (this.highlightedNodes.has(node)) {
                res.highlighted = true;
                res.zIndex = 8;
            } else if (!this.hoveredNode) {
                res.color = '#2a2a3a';
                res.label = '';
                res.zIndex = 0;
            }
        }

        // Sequence badge label
        if (this.sequenceMap[node] !== undefined) {
            const pos = this.sequenceMap[node] + 1;
            res.label = `[${pos}] ${data.label || ''}`;
        }

        // Tag ring — thin colored border for tagged nodes
        if (this.nodeTags[node] && this.nodeTags[node].length > 0) {
            const tagColor = this.nodeTags[node][0].color;
            if (!res.borderColor) {
                res.borderColor = tagColor;
                res.borderSize = 2;
            }
        }

        // Tag filter — dim non-matching nodes
        if (this.tagFilterIds.size > 0) {
            if (this.tagFilterIds.has(node)) {
                res.highlighted = true;
                res.zIndex = Math.max(res.zIndex || 0, 7);
            } else if (!this.hoveredNode && !this.highlightedNodes) {
                res.color = '#2a2a3a';
                res.label = '';
                res.zIndex = 0;
            }
        }

        // Playing node pulse animation
        if (this.playingNodeId === node) {
            const pulse = 1.0 + 0.15 * Math.sin(this._pulsePhase);
            res.size = (res.size || data.size || 8) * pulse;
            res.borderColor = '#00D4FF';
            res.borderSize = 3;
            res.zIndex = 15;
            res.highlighted = true;
        }

        return res;
    }

    _edgeReducer(edge, data) {
        const res = { ...data };
        const score = this.graph.getEdgeAttribute(edge, 'score') || 0;

        // --- Zoom-aware adaptive edge filtering ---
        const camera = this.renderer.getCamera();
        const ratio = camera.getState().ratio;

        // Base threshold from user setting, plus zoom-based increase:
        // When zoomed out (ratio > 1), progressively hide more edges.
        // When zoomed in (ratio < 0.5), show more edges.
        let adaptiveThreshold = this.edgeThreshold;
        if (ratio > 0.8) {
            // Zoomed out: raise threshold — fewer edges
            adaptiveThreshold += (ratio - 0.8) * 0.25;
        } else if (ratio < 0.3) {
            // Zoomed in: lower threshold — more edges
            adaptiveThreshold = Math.max(0.05, adaptiveThreshold - (0.3 - ratio) * 0.3);
        }

        // Threshold filtering with adaptive threshold
        if (score < adaptiveThreshold) {
            res.hidden = true;
            return res;
        }

        // When zoomed out, reduce edge visibility further
        if (ratio > 1.0 && !this.hoveredNode && !this.selectedNode) {
            const fade = Math.max(0.02, 0.12 / ratio);
            res.color = 'rgba(255,255,255,' + fade.toFixed(3) + ')';
            res.size = Math.max(0.3, (res.size || 1) * 0.7 / ratio);
        }

        // Hover: only show edges connected to hovered node
        if (this.hoveredNode) {
            const src = this.graph.source(edge);
            const tgt = this.graph.target(edge);
            if (src !== this.hoveredNode && tgt !== this.hoveredNode) {
                res.hidden = true;
            } else {
                res.color = scoreEdgeColor(score);
                res.size = scoreEdgeSize(score);
            }
        }

        // Selection: highlight connected edges
        if (this.selectedNode && !this.hoveredNode) {
            const src = this.graph.source(edge);
            const tgt = this.graph.target(edge);
            if (src === this.selectedNode || tgt === this.selectedNode) {
                res.color = scoreEdgeColor(score);
                res.size = scoreEdgeSize(score);
                res.zIndex = 5;
            }
        }

        // Suggestion highlighting
        if (this.highlightedNodes && !this.hoveredNode && !this.selectedNode) {
            const src = this.graph.source(edge);
            const tgt = this.graph.target(edge);
            if (!this.highlightedNodes.has(src) || !this.highlightedNodes.has(tgt)) {
                res.hidden = true;
            }
        }

        return res;
    }

    // --- Public API ---

    loadGraph(data) {
        this.graph.clear();
        this.selectedNode = null;
        this.hoveredNode = null;
        this.highlightedNodes = null;
        this.sequenceMap = {};
        this.clusterHulls = [];

        // Add nodes
        if (data.nodes) {
            for (const n of data.nodes) {
                this.graph.addNode(n.id, {
                    label: n.label || '',
                    x: n.x || 0,
                    y: n.y || 0,
                    size: n.size || 8,
                    color: n.color || '#888888',
                    bpm: n.bpm,
                    key: n.key,
                    energy: n.energy,
                    groove: n.groove,
                    frequency: n.frequency,
                    clusterId: n.clusterId,
                    title: n.title,
                    artist: n.artist,
                });
            }
        }

        // Add edges (use a counter to avoid duplicate keys)
        if (data.edges) {
            let edgeIdx = 0;
            for (const e of data.edges) {
                if (!this.graph.hasNode(e.source) || !this.graph.hasNode(e.target)) continue;
                // Skip if edge already exists (undirected)
                if (this.graph.hasEdge(e.source, e.target)) continue;
                try {
                    this.graph.addEdge(e.source, e.target, {
                        size: e.size || 1,
                        color: e.color || 'rgba(255,255,255,0.1)',
                        score: e.score || 0,
                        harmonic: e.harmonic,
                        bpm: e.bpm,
                        energy: e.energy,
                        groove: e.groove,
                        frequency: e.frequency,
                        mixQuality: e.mixQuality,
                        userCreated: e.userCreated || false,
                    });
                } catch (err) {
                    // Duplicate edge — skip
                }
                edgeIdx++;
            }
        }

        this.renderer.refresh();
        if (window.bridge) {
            window.bridge.log(
                'Graph loaded: ' + this.graph.order + ' nodes, ' + this.graph.size + ' edges'
            );
        }
    }

    updatePositions(positions) {
        // Animate nodes to new positions
        const duration = 500;
        const startTime = Date.now();
        const startPositions = {};

        for (const p of positions) {
            if (!this.graph.hasNode(p.id)) continue;
            startPositions[p.id] = {
                x: this.graph.getNodeAttribute(p.id, 'x'),
                y: this.graph.getNodeAttribute(p.id, 'y'),
                tx: p.x,
                ty: p.y,
            };
        }

        const animate = () => {
            const elapsed = Date.now() - startTime;
            const t = Math.min(1, elapsed / duration);
            const ease = t < 0.5 ? 2 * t * t : 1 - Math.pow(-2 * t + 2, 2) / 2;

            for (const [id, pos] of Object.entries(startPositions)) {
                if (!this.graph.hasNode(id)) continue;
                const nx = pos.x + (pos.tx - pos.x) * ease;
                const ny = pos.y + (pos.ty - pos.y) * ease;
                this.graph.setNodeAttribute(id, 'x', nx);
                this.graph.setNodeAttribute(id, 'y', ny);
            }

            if (t < 1) {
                requestAnimationFrame(animate);
            }
        };

        requestAnimationFrame(animate);
    }

    highlightNodes(nodeIds) {
        if (!nodeIds || nodeIds.length === 0) {
            this.highlightedNodes = null;
        } else {
            this.highlightedNodes = new Set(nodeIds);
        }
        this.renderer.refresh();
    }

    clearHighlights() {
        this.highlightedNodes = null;
        this.selectedNode = null;
        this.renderer.refresh();
    }

    setNodeInSequence(nodeId, position) {
        this.sequenceMap[nodeId] = position;
        this.renderer.refresh();
    }

    clearSequenceBadges() {
        this.sequenceMap = {};
        this.renderer.refresh();
    }

    fitAll() {
        const camera = this.renderer.getCamera();
        camera.animate({ x: 0.5, y: 0.5, ratio: 1 }, { duration: 300 });
    }

    addEdge(edgeData) {
        if (!this.graph.hasNode(edgeData.source) || !this.graph.hasNode(edgeData.target)) return;
        if (this.graph.hasEdge(edgeData.source, edgeData.target)) return;
        try {
            this.graph.addEdge(edgeData.source, edgeData.target, {
                size: edgeData.size || 1,
                color: edgeData.color || 'rgba(255,255,255,0.15)',
                score: edgeData.score || 0,
                userCreated: edgeData.userCreated || false,
            });
            this.renderer.refresh();
        } catch (err) {
            // Ignore duplicate
        }
    }

    setEdgeThreshold(threshold) {
        this.edgeThreshold = threshold;
        this.renderer.refresh();
    }

    setNodeTags(nodeId, tags) {
        this.nodeTags[nodeId] = tags || [];
        this.renderer.refresh();
    }

    setPlayingNode(nodeId) {
        this.playingNodeId = nodeId;
        // Start pulse animation loop
        if (!this._pulseInterval) {
            this._pulseInterval = setInterval(() => {
                this._pulsePhase += 0.15;
                if (this.playingNodeId) {
                    this.renderer.refresh();
                }
            }, 50);
        }
        this.renderer.refresh();
    }

    clearPlayingNode() {
        this.playingNodeId = null;
        if (this._pulseInterval) {
            clearInterval(this._pulseInterval);
            this._pulseInterval = null;
        }
        this._pulsePhase = 0;
        this.renderer.refresh();
    }

    setTagFilter(nodeIds) {
        if (!nodeIds || nodeIds.length === 0) {
            this.tagFilterIds = new Set();
        } else {
            this.tagFilterIds = new Set(nodeIds);
        }
        this.renderer.refresh();
    }

    clearTagFilter() {
        this.tagFilterIds = new Set();
        this.renderer.refresh();
    }

    drawClusterHulls(clusters) {
        // Store cluster data; rendered via nodeReducer as large background nodes
        this.clusterHulls = clusters || [];
        // Remove old hull nodes
        this.graph.forEachNode((node, attrs) => {
            if (attrs._isHull) {
                this.graph.dropNode(node);
            }
        });

        // Add transparent hull nodes behind each cluster
        for (const cluster of this.clusterHulls) {
            if (!cluster.trackIds || cluster.trackIds.length < 2) continue;
            let cx = 0, cy = 0, count = 0;
            for (const tid of cluster.trackIds) {
                if (this.graph.hasNode(tid)) {
                    cx += this.graph.getNodeAttribute(tid, 'x');
                    cy += this.graph.getNodeAttribute(tid, 'y');
                    count++;
                }
            }
            if (count < 2) continue;
            cx /= count;
            cy /= count;

            // Compute radius as max distance from centroid + padding
            let maxDist = 0;
            for (const tid of cluster.trackIds) {
                if (this.graph.hasNode(tid)) {
                    const dx = this.graph.getNodeAttribute(tid, 'x') - cx;
                    const dy = this.graph.getNodeAttribute(tid, 'y') - cy;
                    maxDist = Math.max(maxDist, Math.sqrt(dx * dx + dy * dy));
                }
            }

            const hullId = '_hull_' + cluster.id;
            if (!this.graph.hasNode(hullId)) {
                this.graph.addNode(hullId, {
                    x: cx,
                    y: cy,
                    size: maxDist * 0.3 + 20,
                    color: cluster.color + '25',  // 15% alpha
                    label: '',
                    zIndex: -10,
                    _isHull: true,
                });
            }
        }

        this.renderer.refresh();
    }
}

// --- Edge scoring visual helpers ---

function scoreEdgeColor(score) {
    if (score >= 0.8) return 'rgba(34, 197, 94, 0.6)';
    if (score >= 0.6) return 'rgba(234, 179, 8, 0.5)';
    if (score >= 0.4) return 'rgba(249, 115, 22, 0.4)';
    return 'rgba(239, 68, 68, 0.3)';
}

function scoreEdgeSize(score) {
    if (score >= 0.9) return 3.0;
    if (score >= 0.7) return 2.0;
    if (score >= 0.5) return 1.5;
    return 1.0;
}
