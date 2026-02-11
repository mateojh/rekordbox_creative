/**
 * User interaction handlers for the Sigma.js graph.
 * Click, hover, drag, context menu, tooltip.
 */

function setupInteractions(engine) {
    const renderer = engine.renderer;
    const graph = engine.graph;
    const tooltip = document.getElementById('tooltip');

    // --- Node hover: neighborhood focus + tooltip ---
    let hoveredNode = null;

    renderer.on('enterNode', ({ node }) => {
        hoveredNode = node;
        engine.hoveredNode = node;
        renderer.refresh();

        // Show tooltip
        if (tooltip && graph.hasNode(node)) {
            const attrs = graph.getNodeAttributes(node);
            tooltip.querySelector('.tt-title').textContent = attrs.title || attrs.label || '';
            tooltip.querySelector('.tt-artist').textContent = attrs.artist || '';

            const bpmEl = tooltip.querySelector('.tt-bpm');
            if (bpmEl) bpmEl.textContent = attrs.bpm ? attrs.bpm + ' BPM' : '';

            const keyEl = tooltip.querySelector('.tt-key');
            if (keyEl) {
                keyEl.textContent = attrs.key || '';
                keyEl.style.backgroundColor = (attrs.color || '#888') + '30';
                keyEl.style.color = attrs.color || '#888';
            }

            tooltip.style.display = 'block';
        }
    });

    renderer.on('leaveNode', () => {
        hoveredNode = null;
        engine.hoveredNode = null;
        renderer.refresh();
        if (tooltip) tooltip.style.display = 'none';
    });

    // Track mouse position for tooltip
    renderer.getMouseCaptor().on('mousemovebody', (e) => {
        if (tooltip && hoveredNode) {
            tooltip.style.left = (e.original.offsetX + 15) + 'px';
            tooltip.style.top = (e.original.offsetY + 15) + 'px';
        }

        // Handle drag
        if (isDragging && draggedNode) {
            const pos = renderer.viewportToGraph(e);
            graph.setNodeAttribute(draggedNode, 'x', pos.x);
            graph.setNodeAttribute(draggedNode, 'y', pos.y);
        }
    });

    // --- Node click: selection ---
    renderer.on('clickNode', ({ node, event }) => {
        engine.selectedNode = node;
        renderer.refresh();
        if (window.bridge) {
            window.bridge.on_node_click(node);
        }
    });

    // --- Node double-click: add to sequence ---
    renderer.on('doubleClickNode', ({ node }) => {
        if (window.bridge) {
            window.bridge.on_node_dblclick(node);
        }
    });

    // --- Node right-click: context menu ---
    renderer.on('rightClickNode', ({ node, event }) => {
        event.original.preventDefault();
        const screenX = event.original.screenX || event.original.clientX;
        const screenY = event.original.screenY || event.original.clientY;
        if (window.bridge) {
            window.bridge.on_node_context(node, screenX, screenY);
        }
    });

    // --- Stage click: deselect ---
    renderer.on('clickStage', () => {
        engine.selectedNode = null;
        engine.highlightedNodes = null;
        renderer.refresh();
        if (window.bridge) {
            window.bridge.on_canvas_click();
        }
    });

    // --- Node dragging ---
    let draggedNode = null;
    let isDragging = false;

    renderer.on('downNode', (e) => {
        isDragging = true;
        draggedNode = e.node;
        // Pin the bounding box so camera doesn't shift during drag
        if (!renderer.getCustomBBox()) {
            renderer.setCustomBBox(renderer.getBBox());
        }
    });

    const handleUp = () => {
        if (draggedNode) {
            // Optionally notify Python of new position
        }
        isDragging = false;
        draggedNode = null;
        renderer.setCustomBBox(null);
    };

    renderer.getMouseCaptor().on('mouseup', handleUp);

    // Disable default right-click context menu on the container
    renderer.getContainer().addEventListener('contextmenu', (e) => {
        e.preventDefault();
    });
}
