/**
 * Energy Flow — Shows energy trajectory through sequenced tracks.
 * Displays as a small sparkline chart in the bottom-left corner.
 */

class EnergyFlow {
    constructor(container) {
        this.container = container;
        this.canvas = document.createElement('canvas');
        this.canvas.width = 240;
        this.canvas.height = 60;
        this.canvas.style.width = '240px';
        this.canvas.style.height = '60px';
        this.container.appendChild(this.canvas);
        this.ctx = this.canvas.getContext('2d');
        this.sequence = [];  // [{label, energy, key}]
        this.container.style.display = 'none';
    }

    setSequence(tracks) {
        this.sequence = tracks || [];
        if (this.sequence.length < 2) {
            this.container.style.display = 'none';
            return;
        }
        this.container.style.display = 'block';
        this._render();
    }

    _render() {
        const ctx = this.ctx;
        const w = this.canvas.width;
        const h = this.canvas.height;
        const seq = this.sequence;

        ctx.clearRect(0, 0, w, h);

        // Background
        ctx.fillStyle = 'rgba(22, 27, 34, 0.8)';
        ctx.beginPath();
        ctx.roundRect(0, 0, w, h, 8);
        ctx.fill();

        if (seq.length < 2) return;

        const padX = 16;
        const padY = 12;
        const graphW = w - 2 * padX;
        const graphH = h - 2 * padY;

        // Draw grid lines
        ctx.strokeStyle = 'rgba(255, 255, 255, 0.04)';
        ctx.lineWidth = 0.5;
        for (let y = 0; y <= 1; y += 0.5) {
            const py = padY + graphH * (1 - y);
            ctx.beginPath();
            ctx.moveTo(padX, py);
            ctx.lineTo(padX + graphW, py);
            ctx.stroke();
        }

        // Compute points
        const points = seq.map((t, i) => ({
            x: padX + (i / (seq.length - 1)) * graphW,
            y: padY + graphH * (1 - (t.energy || 0)),
            energy: t.energy || 0,
        }));

        // Gradient fill under the line
        const gradient = ctx.createLinearGradient(0, padY, 0, padY + graphH);
        gradient.addColorStop(0, 'rgba(0, 212, 255, 0.15)');
        gradient.addColorStop(1, 'rgba(0, 212, 255, 0.0)');

        ctx.fillStyle = gradient;
        ctx.beginPath();
        ctx.moveTo(points[0].x, padY + graphH);
        for (const p of points) {
            ctx.lineTo(p.x, p.y);
        }
        ctx.lineTo(points[points.length - 1].x, padY + graphH);
        ctx.closePath();
        ctx.fill();

        // Draw line
        ctx.strokeStyle = '#00D4FF';
        ctx.lineWidth = 2;
        ctx.lineJoin = 'round';
        ctx.beginPath();
        ctx.moveTo(points[0].x, points[0].y);
        for (let i = 1; i < points.length; i++) {
            ctx.lineTo(points[i].x, points[i].y);
        }
        ctx.stroke();

        // Draw dots with energy-based color
        for (const p of points) {
            let dotColor;
            if (p.energy >= 0.8) dotColor = '#ef4444';
            else if (p.energy >= 0.6) dotColor = '#eab308';
            else if (p.energy >= 0.4) dotColor = '#22c55e';
            else dotColor = '#4488FF';

            ctx.fillStyle = dotColor;
            ctx.beginPath();
            ctx.arc(p.x, p.y, 3, 0, Math.PI * 2);
            ctx.fill();
        }

        // Label
        ctx.fillStyle = '#64748b';
        ctx.font = '8px Inter, sans-serif';
        ctx.fillText('ENERGY FLOW', padX, 9);
    }
}
