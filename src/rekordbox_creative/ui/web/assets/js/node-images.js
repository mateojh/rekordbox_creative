/**
 * NodeImageOverlay — Renders circular album artwork on a Canvas 2D overlay
 * positioned over the Sigma.js WebGL canvas.
 *
 * Usage:
 *   window.nodeImageOverlay = new NodeImageOverlay(window.graphEngine);
 *   window.nodeImageOverlay.loadImages({ nodeId: "data:image/jpeg;base64,..." });
 */

class NodeImageOverlay {
    constructor(graphEngine) {
        this.graphEngine = graphEngine;
        this.renderer = graphEngine.renderer;
        this.images = {};    // nodeId -> HTMLImageElement (loaded)
        this.pending = {};   // nodeId -> dataURI (loading)
        this.canvas = null;
        this.ctx = null;
        this._enabled = true;
        this._minNodeSize = 4;  // Don't draw art for nodes smaller than this

        this._init();
    }

    _init() {
        // Create overlay canvas matching the Sigma container.
        // Sigma's internal layers: edges(1), nodes(2), labels(3), hovers(4), mouse(5).
        // We insert between nodes and labels so art shows on nodes but
        // labels/tooltips render on top.
        const container = this.renderer.getContainer();
        this.canvas = document.createElement('canvas');
        this.canvas.id = 'art-overlay';
        this.canvas.style.cssText =
            'position:absolute;top:0;left:0;width:100%;height:100%;' +
            'pointer-events:none;z-index:3;';
        container.appendChild(this.canvas);
        this.ctx = this.canvas.getContext('2d');

        // Match size to container
        this._resize();
        this._resizeObserver = new ResizeObserver(() => this._resize());
        this._resizeObserver.observe(container);

        // Redraw on each Sigma render
        this.renderer.on('afterRender', () => this._draw());

        if (window.bridge) {
            window.bridge.log('NodeImageOverlay initialized');
        }
    }

    _resize() {
        const container = this.renderer.getContainer();
        const rect = container.getBoundingClientRect();
        const dpr = window.devicePixelRatio || 1;
        this.canvas.width = rect.width * dpr;
        this.canvas.height = rect.height * dpr;
        this.canvas.style.width = rect.width + 'px';
        this.canvas.style.height = rect.height + 'px';
    }

    /**
     * Load artwork images from a map of nodeId -> data URI.
     */
    loadImages(nodeImageMap) {
        if (!nodeImageMap) return;

        const entries = Object.entries(nodeImageMap);
        let loaded = 0;
        let errors = 0;

        if (window.bridge) {
            window.bridge.log('NodeImageOverlay: loading ' + entries.length + ' images');
        }

        for (const [nodeId, dataUri] of entries) {
            if (this.images[nodeId]) continue;  // Already loaded

            const img = new Image();
            img.onload = () => {
                this.images[nodeId] = img;
                delete this.pending[nodeId];
                loaded++;
                // Refresh periodically, not on every single image
                if (loaded % 20 === 0 || loaded === entries.length - errors) {
                    this.renderer.refresh();
                    if (window.bridge) {
                        window.bridge.log('Art loaded: ' + loaded + '/' + entries.length);
                    }
                }
            };
            img.onerror = () => {
                delete this.pending[nodeId];
                errors++;
            };
            this.pending[nodeId] = dataUri;
            img.src = dataUri;
        }
    }

    /**
     * Main draw loop — called after each Sigma render.
     */
    _draw() {
        const ctx = this.ctx;
        const dpr = window.devicePixelRatio || 1;
        ctx.clearRect(0, 0, this.canvas.width, this.canvas.height);

        if (!this._enabled) return;

        const imageCount = Object.keys(this.images).length;
        if (imageCount === 0) return;

        // Get camera state for zoom-based decisions
        const camera = this.renderer.getCamera();
        const cameraState = camera.getState();
        const ratio = cameraState.ratio;

        // When very zoomed out, skip album art entirely
        if (ratio > 4) return;

        // Fade art opacity as we zoom out
        const artOpacity = ratio > 1.5
            ? Math.max(0, 1 - (ratio - 1.5) / 2.5)
            : 1.0;
        if (artOpacity <= 0) return;

        const graph = this.graphEngine.graph;

        // Compute the pixel-size scale factor for node sizes.
        // Sigma's shader renders node diameter as:
        //   size * correctionRatio * 2, where correctionRatio =
        //   pixelRatio * viewportWidth / (2 * max(width, height)) / cameraRatio
        // In CSS pixel space (what we draw in), we divide by pixelRatio:
        const w = this.canvas.width / dpr;
        const h = this.canvas.height / dpr;
        const maxDim = Math.max(w, h);
        const sizeScale = w / (2 * maxDim * ratio);

        ctx.globalAlpha = artOpacity;

        let drawnCount = 0;

        graph.forEachNode((nodeId, attrs) => {
            if (attrs._isHull) return;

            const img = this.images[nodeId];
            if (!img) return;

            const displayData = this.renderer.getNodeDisplayData(nodeId);
            if (!displayData || displayData.hidden) return;

            // Use raw graph coordinates (attrs.x/y) with graphToViewport().
            // displayData.x/y are in Sigma's normalized "framed graph" space —
            // feeding those into graphToViewport() double-normalizes and
            // collapses all artwork into one spot.
            const viewPos = this.renderer.graphToViewport({
                x: attrs.x,
                y: attrs.y
            });
            const vx = viewPos.x;
            const vy = viewPos.y;

            // Compute rendered pixel radius matching Sigma's WebGL output
            const r = displayData.size * sizeScale;

            // Skip nodes that are too small to show art
            if (r < this._minNodeSize) return;

            // Skip nodes outside viewport (with margin)
            if (vx < -r || vx > w + r || vy < -r || vy > h + r) return;

            // Dim nodes that are dimmed by nodeReducer
            if (displayData.color === '#3a3a4a' || displayData.color === '#2a2a3a') {
                ctx.globalAlpha = 0.15 * artOpacity;
            } else {
                ctx.globalAlpha = artOpacity;
            }

            // Draw circular clipped album art
            ctx.save();
            ctx.beginPath();
            ctx.arc(vx * dpr, vy * dpr, r * dpr, 0, Math.PI * 2);
            ctx.closePath();
            ctx.clip();
            ctx.drawImage(
                img,
                (vx - r) * dpr, (vy - r) * dpr,
                r * 2 * dpr, r * 2 * dpr
            );
            ctx.restore();

            // Draw border ring
            ctx.beginPath();
            ctx.arc(vx * dpr, vy * dpr, r * dpr, 0, Math.PI * 2);

            if (displayData.borderColor) {
                ctx.strokeStyle = displayData.borderColor;
                ctx.lineWidth = (displayData.borderSize || 2) * dpr;
            } else {
                ctx.strokeStyle = 'rgba(255,255,255,0.2)';
                ctx.lineWidth = 1 * dpr;
            }
            ctx.stroke();

            drawnCount++;
        });

        ctx.globalAlpha = 1.0;
    }

    /**
     * Toggle album art display on/off.
     */
    setEnabled(enabled) {
        this._enabled = enabled;
        this.renderer.refresh();
    }

    /**
     * Clear all loaded images.
     */
    clear() {
        this.images = {};
        this.pending = {};
        this.renderer.refresh();
    }
}
