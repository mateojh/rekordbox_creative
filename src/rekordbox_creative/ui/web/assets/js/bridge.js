/**
 * JS-side QWebChannel bridge setup.
 * Connects to the Python GraphBridge object and initializes the graph engine.
 */

(function () {
    'use strict';

    // Wait for QWebChannel transport to be available
    function initBridge() {
        if (typeof QWebChannel === 'undefined') {
            console.error('QWebChannel not available');
            // Still init the engine without bridge (for standalone testing)
            initEngine(null);
            return;
        }

        new QWebChannel(qt.webChannelTransport, function (channel) {
            window.bridge = channel.objects.bridge;
            console.log('QWebChannel bridge connected');
            initEngine(window.bridge);
        });
    }

    function initEngine(bridge) {
        const container = document.getElementById('sigma-container');
        if (!container) {
            console.error('sigma-container not found');
            return;
        }

        // Create the global graph engine
        window.graphEngine = new GraphEngine(container);

        // Notify Python that JS is ready
        if (bridge) {
            bridge.on_js_ready();
        }
    }

    // Start when DOM is ready
    if (document.readyState === 'loading') {
        document.addEventListener('DOMContentLoaded', initBridge);
    } else {
        initBridge();
    }
})();
