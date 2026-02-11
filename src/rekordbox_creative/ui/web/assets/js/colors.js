/**
 * Camelot color system — matches Python nodes.py color mapping.
 * Minor (A) = saturated, Major (B) = lightened 40%.
 */
const CAMELOT_COLORS = {
    1:  '#FF4444', 2:  '#FF6633', 3:  '#FF9922', 4:  '#FFCC11',
    5:  '#99DD00', 6:  '#44CC44', 7:  '#22BBAA', 8:  '#22AADD',
    9:  '#4488FF', 10: '#6644FF', 11: '#AA44FF', 12: '#FF44AA',
};

/**
 * Get the hex color for a Camelot key string like '8A'.
 */
function getKeyColor(key) {
    if (!key || key.length < 2) return '#888888';
    const num = parseInt(key.slice(0, -1), 10);
    const mode = key.slice(-1);
    const base = CAMELOT_COLORS[num] || '#888888';
    if (mode === 'B') {
        return lightenColor(base, 0.4);
    }
    return base;
}

/**
 * Lighten a hex color by blending toward white.
 */
function lightenColor(hex, amount) {
    const r = parseInt(hex.slice(1, 3), 16);
    const g = parseInt(hex.slice(3, 5), 16);
    const b = parseInt(hex.slice(5, 7), 16);
    const nr = Math.min(255, Math.round(r + (255 - r) * amount));
    const ng = Math.min(255, Math.round(g + (255 - g) * amount));
    const nb = Math.min(255, Math.round(b + (255 - b) * amount));
    return '#' + [nr, ng, nb].map(c => c.toString(16).padStart(2, '0')).join('');
}

/**
 * Darken a hex color.
 */
function darkenColor(hex, amount) {
    const r = parseInt(hex.slice(1, 3), 16);
    const g = parseInt(hex.slice(3, 5), 16);
    const b = parseInt(hex.slice(5, 7), 16);
    const nr = Math.max(0, Math.round(r * (1 - amount)));
    const ng = Math.max(0, Math.round(g * (1 - amount)));
    const nb = Math.max(0, Math.round(b * (1 - amount)));
    return '#' + [nr, ng, nb].map(c => c.toString(16).padStart(2, '0')).join('');
}

/**
 * Score -> color gradient (red->amber->green).
 */
function scoreColor(score) {
    if (score >= 0.8) return '#22c55e';
    if (score >= 0.6) return '#eab308';
    if (score >= 0.4) return '#f97316';
    return '#ef4444';
}

/**
 * Cluster ID -> color (8 cycling colors at 25% alpha for hulls).
 */
const CLUSTER_COLORS = [
    '#FF4444', '#44CC44', '#4488FF', '#FF9922',
    '#AA44FF', '#22BBAA', '#FFCC11', '#FF44AA',
];

function getClusterColor(idx) {
    return CLUSTER_COLORS[idx % CLUSTER_COLORS.length];
}
