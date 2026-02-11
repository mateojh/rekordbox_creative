/**
 * Camelot Wheel — Interactive SVG overlay showing the Camelot key system.
 * Highlights the selected track's key and compatible keys.
 */

class CamelotWheel {
    constructor(container) {
        this.container = container;
        this.currentKey = null;
        this._build();
        this.container.style.display = 'block';
    }

    _build() {
        const size = 140;
        const cx = size / 2;
        const cy = size / 2;
        const outerR = 60;
        const innerR = 38;
        const textR_outer = 50;
        const textR_inner = 28;

        let svg = `<svg width="${size}" height="${size}" viewBox="0 0 ${size} ${size}">`;

        // Background circle
        svg += `<circle cx="${cx}" cy="${cy}" r="${outerR + 4}" fill="rgba(22, 27, 34, 0.8)" stroke="rgba(255,255,255,0.06)" stroke-width="1"/>`;

        for (let i = 1; i <= 12; i++) {
            const angle = ((i - 1) * 30 - 90) * Math.PI / 180;
            const nextAngle = (i * 30 - 90) * Math.PI / 180;
            const midAngle = ((i - 0.5) * 30 - 90) * Math.PI / 180;
            const color = CAMELOT_COLORS[i] || '#888';
            const lightColor = lightenColor(color, 0.4);

            // Outer ring (B = Major)
            const ox = cx + textR_outer * Math.cos(midAngle);
            const oy = cy + textR_outer * Math.sin(midAngle);
            svg += `<circle class="cw-key" data-key="${i}B" cx="${ox}" cy="${oy}" r="9" fill="${lightColor}30" stroke="${lightColor}" stroke-width="1" style="cursor:pointer"/>`;
            svg += `<text x="${ox}" y="${oy}" text-anchor="middle" dominant-baseline="central" fill="${lightColor}" font-size="7" font-weight="600" pointer-events="none">${i}B</text>`;

            // Inner ring (A = Minor)
            const ix = cx + textR_inner * Math.cos(midAngle);
            const iy = cy + textR_inner * Math.sin(midAngle);
            svg += `<circle class="cw-key" data-key="${i}A" cx="${ix}" cy="${iy}" r="9" fill="${color}30" stroke="${color}" stroke-width="1" style="cursor:pointer"/>`;
            svg += `<text x="${ix}" y="${iy}" text-anchor="middle" dominant-baseline="central" fill="${color}" font-size="7" font-weight="600" pointer-events="none">${i}A</text>`;
        }

        svg += '</svg>';
        this.container.innerHTML = svg;
    }

    setKey(key) {
        this.currentKey = key;
        const circles = this.container.querySelectorAll('.cw-key');

        if (!key) {
            circles.forEach(c => {
                c.setAttribute('stroke-width', '1');
                c.setAttribute('r', '9');
            });
            return;
        }

        const num = parseInt(key.slice(0, -1), 10);
        const mode = key.slice(-1);
        const otherMode = mode === 'A' ? 'B' : 'A';
        const prev = num === 1 ? 12 : num - 1;
        const next = num === 12 ? 1 : num + 1;

        const compatible = new Set([
            key,
            `${prev}${mode}`, `${next}${mode}`,
            `${num}${otherMode}`,
        ]);

        circles.forEach(c => {
            const k = c.getAttribute('data-key');
            if (k === key) {
                c.setAttribute('stroke-width', '3');
                c.setAttribute('r', '11');
            } else if (compatible.has(k)) {
                c.setAttribute('stroke-width', '2');
                c.setAttribute('r', '10');
            } else {
                c.setAttribute('stroke-width', '0.5');
                c.setAttribute('r', '8');
                c.setAttribute('opacity', '0.4');
            }
        });

        // Reset opacity for compatible keys
        circles.forEach(c => {
            const k = c.getAttribute('data-key');
            if (k === key || compatible.has(k)) {
                c.setAttribute('opacity', '1');
            }
        });
    }

    clear() {
        this.setKey(null);
    }
}
