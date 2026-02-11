/**
 * Minimap — Small overview canvas in the bottom-right corner.
 * Shows all nodes as colored dots and a viewport rectangle.
 * Click to navigate.
 */

class Minimap {
    constructor(engine, container) {
        this.engine = engine;
        this.container = container;
        this.canvas = document.createElement('canvas');
        this.canvas.width = container.clientWidth * 2;   // 2x for retina
        this.canvas.height = container.clientHeight * 2;
        this.canvas.style.width = '100%';
        this.canvas.style.height = '100%';
        this.container.appendChild(this.canvas);
        this.ctx = this.canvas.getContext('2d');

        // Show the minimap
        this.container.style.display = 'block';

        // Click to navigate
        this.container.addEventListener('click', (e) => this._onClick(e));

        // Re-render on camera change
        this.engine.renderer.getCamera().on('updated', () => this.render());

        // Initial render
        this.render();
    }

    render() {
        const ctx = this.ctx;
        const w = this.canvas.width;
        const h = this.canvas.height;
        const graph = this.engine.graph;

        ctx.clearRect(0, 0, w, h);

        // Background
        ctx.fillStyle = 'rgba(22, 27, 34, 0.75)';
        ctx.fillRect(0, 0, w, h);

        if (graph.order === 0) return;

        // Compute bounding box of all nodes
        let minX = Infinity, maxX = -Infinity;
        let minY = Infinity, maxY = -Infinity;

        graph.forEachNode((node, attrs) => {
            if (attrs._isHull) return;
            minX = Math.min(minX, attrs.x);
            maxX = Math.max(maxX, attrs.x);
            minY = Math.min(minY, attrs.y);
            maxY = Math.max(maxY, attrs.y);
        });

        if (!isFinite(minX)) return;

        const padding = 10;
        const rangeX = (maxX - minX) || 1;
        const rangeY = (maxY - minY) || 1;
        const scaleX = (w - 2 * padding) / rangeX;
        const scaleY = (h - 2 * padding) / rangeY;
        const scale = Math.min(scaleX, scaleY);

        const offsetX = padding + ((w - 2 * padding) - rangeX * scale) / 2;
        const offsetY = padding + ((h - 2 * padding) - rangeY * scale) / 2;

        const toMiniX = (x) => offsetX + (x - minX) * scale;
        const toMiniY = (y) => offsetY + (y - minY) * scale;

        // Draw edges (very thin)
        ctx.strokeStyle = 'rgba(255, 255, 255, 0.05)';
        ctx.lineWidth = 0.5;
        graph.forEachEdge((edge, attrs) => {
            if (attrs.hidden) return;
            const src = graph.source(edge);
            const tgt = graph.target(edge);
            const sa = graph.getNodeAttributes(src);
            const ta = graph.getNodeAttributes(tgt);
            if (sa._isHull || ta._isHull) return;
            ctx.beginPath();
            ctx.moveTo(toMiniX(sa.x), toMiniY(sa.y));
            ctx.lineTo(toMiniX(ta.x), toMiniY(ta.y));
            ctx.stroke();
        });

        // Draw nodes as dots
        graph.forEachNode((node, attrs) => {
            if (attrs._isHull) return;
            const mx = toMiniX(attrs.x);
            const my = toMiniY(attrs.y);
            ctx.fillStyle = attrs.color || '#888888';
            ctx.beginPath();
            ctx.arc(mx, my, 2, 0, Math.PI * 2);
            ctx.fill();
        });

        // Draw viewport rectangle
        const camera = this.engine.renderer.getCamera();
        const state = camera.getState();
        // Sigma camera state: x, y in [0,1] range, ratio
        // We need to map this to our minimap coordinate space
        // The camera's x,y represents the center of the viewport in normalized graph space
        // ratio is the zoom level (higher = more zoomed out)

        // Get the viewport bounds in graph coordinates
        const dims = this.engine.renderer.getDimensions();
        const graphExtent = this.engine.renderer.getGraphDimensions();

        // Simple approach: use sigma's viewportToGraph for corners
        try {
            const topLeft = this.engine.renderer.viewportToGraph({x: 0, y: 0});
            const bottomRight = this.engine.renderer.viewportToGraph({
                x: dims.width, y: dims.height
            });

            const vx1 = toMiniX(topLeft.x);
            const vy1 = toMiniY(topLeft.y);
            const vx2 = toMiniX(bottomRight.x);
            const vy2 = toMiniY(bottomRight.y);

            ctx.strokeStyle = 'rgba(0, 212, 255, 0.6)';
            ctx.lineWidth = 1.5;
            ctx.strokeRect(
                Math.min(vx1, vx2),
                Math.min(vy1, vy2),
                Math.abs(vx2 - vx1),
                Math.abs(vy2 - vy1)
            );
        } catch (e) {
            // viewportToGraph may fail if renderer not ready
        }

        // Store mapping for click handler
        this._mapState = { minX, maxX, minY, maxY, scale, offsetX, offsetY };
    }

    _onClick(e) {
        if (!this._mapState) return;

        const rect = this.container.getBoundingClientRect();
        const mx = (e.clientX - rect.left) * 2;  // 2x for retina
        const my = (e.clientY - rect.top) * 2;
        const { minX, scale, offsetX, minY, offsetY } = this._mapState;

        const graphX = (mx - offsetX) / scale + minX;
        const graphY = (my - offsetY) / scale + minY;

        // Find the closest graph coordinates in normalized camera space
        // and animate there
        try {
            const pos = this.engine.renderer.graphToViewport({x: graphX, y: graphY});
            const dims = this.engine.renderer.getDimensions();
            // Convert to normalized camera coordinates
            const nx = pos.x / dims.width;
            const ny = pos.y / dims.height;
            const camera = this.engine.renderer.getCamera();
            const state = camera.getState();
            camera.animate(
                { x: nx, y: ny, ratio: state.ratio },
                { duration: 200 }
            );
        } catch (e) {
            // Ignore navigation errors
        }
    }
}
