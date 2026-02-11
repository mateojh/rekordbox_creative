/**
 * Filter Bar — In-graph filter controls for quick filtering.
 * Shows key filter chips, BPM range, and cluster selector.
 */

class FilterBar {
    constructor(engine, container) {
        this.engine = engine;
        this.container = container;
        this.activeFilters = { keys: new Set(), bpmMin: 0, bpmMax: 999 };
        this._build();
        this.container.style.display = 'block';
    }

    _build() {
        this.container.innerHTML = `
            <div class="fb-group">
                <span class="fb-label">Key</span>
                <div class="fb-keys" id="fb-keys"></div>
            </div>
            <div class="fb-group">
                <span class="fb-label">BPM</span>
                <input type="number" id="fb-bpm-min" class="fb-input" placeholder="min" min="0" max="300">
                <span class="fb-dash">-</span>
                <input type="number" id="fb-bpm-max" class="fb-input" placeholder="max" min="0" max="300">
            </div>
            <div class="fb-group" id="fb-tag-group" style="display:none;">
                <span class="fb-label">Tags</span>
                <div class="fb-tags" id="fb-tags"></div>
            </div>
            <button class="fb-clear" id="fb-clear">Clear</button>
        `;

        // Add key filter chips
        const keysDiv = this.container.querySelector('#fb-keys');
        for (let i = 1; i <= 12; i++) {
            const color = CAMELOT_COLORS[i] || '#888';
            const chip = document.createElement('span');
            chip.className = 'fb-key-chip';
            chip.textContent = i;
            chip.style.borderColor = color;
            chip.style.color = color;
            chip.dataset.num = i;
            chip.addEventListener('click', () => this._toggleKey(i, chip, color));
            keysDiv.appendChild(chip);
        }

        // BPM inputs
        const bpmMin = this.container.querySelector('#fb-bpm-min');
        const bpmMax = this.container.querySelector('#fb-bpm-max');
        bpmMin.addEventListener('change', () => {
            this.activeFilters.bpmMin = parseFloat(bpmMin.value) || 0;
            this._apply();
        });
        bpmMax.addEventListener('change', () => {
            this.activeFilters.bpmMax = parseFloat(bpmMax.value) || 999;
            this._apply();
        });

        // Clear button
        this.container.querySelector('#fb-clear').addEventListener('click', () => {
            this.clear();
        });
    }

    _toggleKey(num, chip, color) {
        if (this.activeFilters.keys.has(num)) {
            this.activeFilters.keys.delete(num);
            chip.style.background = 'transparent';
        } else {
            this.activeFilters.keys.add(num);
            chip.style.background = color + '30';
        }
        this._apply();
    }

    _apply() {
        const engine = this.engine;
        const graph = engine.graph;
        const filters = this.activeFilters;
        const hasKeyFilter = filters.keys.size > 0;
        const hasBpmFilter = filters.bpmMin > 0 || filters.bpmMax < 999;

        if (!hasKeyFilter && !hasBpmFilter) {
            engine.highlightedNodes = null;
            engine.renderer.refresh();
            return;
        }

        const matching = new Set();
        graph.forEachNode((node, attrs) => {
            if (attrs._isHull) return;

            let pass = true;

            if (hasKeyFilter) {
                const keyStr = attrs.key || '';
                const keyNum = parseInt(keyStr.slice(0, -1), 10);
                if (!filters.keys.has(keyNum)) pass = false;
            }

            if (hasBpmFilter) {
                const bpm = attrs.bpm || 0;
                if (bpm < filters.bpmMin || bpm > filters.bpmMax) pass = false;
            }

            if (pass) matching.add(node);
        });

        engine.highlightedNodes = matching.size > 0 ? matching : null;
        engine.renderer.refresh();
    }

    setTags(tags) {
        // tags: [{id, name, color, trackIds: [nodeId, ...]}]
        this._tags = tags || [];
        const group = this.container.querySelector('#fb-tag-group');
        const tagsDiv = this.container.querySelector('#fb-tags');
        if (!tagsDiv) return;

        tagsDiv.innerHTML = '';
        if (tags.length === 0) {
            group.style.display = 'none';
            return;
        }
        group.style.display = 'flex';

        for (const tag of tags) {
            const chip = document.createElement('span');
            chip.className = 'fb-key-chip';
            chip.textContent = tag.name.slice(0, 8);
            chip.style.borderColor = tag.color;
            chip.style.color = tag.color;
            chip.style.fontSize = '9px';
            chip.dataset.tagId = tag.id;
            chip.addEventListener('click', () => this._toggleTag(tag, chip));
            tagsDiv.appendChild(chip);
        }
    }

    _toggleTag(tag, chip) {
        if (!this.activeFilters.tagIds) this.activeFilters.tagIds = new Set();
        if (this.activeFilters.tagIds.has(tag.id)) {
            this.activeFilters.tagIds.delete(tag.id);
            chip.style.background = 'transparent';
        } else {
            this.activeFilters.tagIds.add(tag.id);
            chip.style.background = tag.color + '30';
        }
        this._applyTagFilter();
    }

    _applyTagFilter() {
        if (!this.activeFilters.tagIds || this.activeFilters.tagIds.size === 0) {
            this.engine.clearTagFilter();
            return;
        }
        // Collect track IDs that have ALL selected tags
        const selectedTagIds = [...this.activeFilters.tagIds];
        const tagData = this._tags || [];
        let matchingNodes = null;
        for (const tagId of selectedTagIds) {
            const tag = tagData.find(t => t.id === tagId);
            if (!tag || !tag.trackIds) continue;
            const nodeSet = new Set(tag.trackIds);
            if (matchingNodes === null) {
                matchingNodes = nodeSet;
            } else {
                matchingNodes = new Set([...matchingNodes].filter(x => nodeSet.has(x)));
            }
        }
        this.engine.setTagFilter(matchingNodes ? [...matchingNodes] : []);
    }

    clear() {
        this.activeFilters = { keys: new Set(), bpmMin: 0, bpmMax: 999, tagIds: new Set() };
        // Reset UI
        this.container.querySelectorAll('.fb-key-chip').forEach(c => {
            c.style.background = 'transparent';
        });
        this.container.querySelector('#fb-bpm-min').value = '';
        this.container.querySelector('#fb-bpm-max').value = '';
        // Reset highlights
        this.engine.highlightedNodes = null;
        this.engine.clearTagFilter();
        this.engine.renderer.refresh();
    }
}
