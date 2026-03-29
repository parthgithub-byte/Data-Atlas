/**
 * Dashboard Module — Stats cards, recent scans table.
 */
const Dashboard = {
    async load() {
        try {
            const data = await API.getDashboardStats();
            this.renderStats(data.stats);
            this.renderTrends(data.timeline);
            this.renderRecentScans(data.recent_scans);
        } catch (error) {
            console.warn('Dashboard load error (may be first load):', error);
            // Don't rethrow — show zeros gracefully
            this.renderStats({
                total_scans: 0,
                total_profiles_found: 0,
                avg_risk_score: 0,
                total_entities_found: 0,
            });
            this.renderRecentScans([]);
        }
    },

    renderStats(stats) {
        this.animateCounter('stat-total-scans', stats.total_scans || 0);
        this.animateCounter('stat-profiles-found', stats.total_profiles_found || 0);
        this.animateCounter('stat-avg-risk', stats.avg_risk_score || 0, true);
        this.animateCounter('stat-entities', stats.total_entities_found || 0);
    },

    renderTrends(timeline) {
        if (!timeline || timeline.length === 0) return;
        
        this.renderSparkline('trend-scans-chart', timeline, 'scans', 'var(--accent-blue)', 'var(--accent-blue-glow)');
        this.renderSparkline('trend-risk-chart', timeline, 'avg_risk', 'var(--accent-amber)', 'var(--accent-amber-glow)', 10);
    },

    renderSparkline(containerId, data, key, color, glowColor, maxOverride = null) {
        const container = document.getElementById(containerId);
        if (!container) return;
        
        // Use ResizeObserver for responsive charts if available, otherwise just use calculated width
        const width = container.clientWidth || 400;
        const height = container.clientHeight || 140;
        
        let maxVal = maxOverride;
        if (maxVal === null) {
            maxVal = Math.max(...data.map(d => d[key]), 1); // at least 1
            // Pad max value a bit for better visuals
            maxVal = maxVal * 1.2;
        }
        
        const padding = { top: 15, right: 15, bottom: 25, left: 15 };
        const innerWidth = width - padding.left - padding.right;
        const innerHeight = height - padding.top - padding.bottom;
        
        const stepX = innerWidth / (Math.max(data.length - 1, 1));
        
        let pathData = '';
        let areaData = '';
        let pointsHtml = '';
        
        data.forEach((d, i) => {
            const val = d[key];
            const x = padding.left + i * stepX;
            // Floor at 0 for y calculation
            const safeVal = Math.max(0, val);
            const y = padding.top + innerHeight - (safeVal / maxVal) * innerHeight;
            
            if (i === 0) {
                pathData += `M ${x},${y} `;
                areaData += `M ${x},${padding.top + innerHeight} L ${x},${y} `;
            } else {
                pathData += `L ${x},${y} `;
                areaData += `L ${x},${y} `;
            }
            
            // Tooltips
            const displayVal = key === 'avg_risk' ? val.toFixed(1) : val;
            const dateStr = this.formatDate(d.date).replace(' ago', '').replace('Just now', 'Today');
            // Simplified approach for the tooltip
            const pointTitle = `${displayVal} on ${dateStr}`;
            
            pointsHtml += `<circle cx="${x}" cy="${y}" r="4" fill="var(--bg-secondary)" stroke="${color}" stroke-width="2" class="tooltip" data-tooltip="${pointTitle}" title="${pointTitle}" style="cursor: pointer; transition: r 0.2s;"></circle>`;
        });
        
        areaData += `L ${width - padding.right},${padding.top + innerHeight} Z`;
        
        const firstDate = this.formatDate(data[0].date).replace(' ago', '');
        const midDate = this.formatDate(data[Math.floor(data.length/2)].date).replace(' ago', '');
        const lastDate = 'Today';
        
        const svgHtml = `
            <svg width="100%" height="100%" viewBox="0 0 ${width} ${height}" style="overflow: visible; position: absolute; inset: 0;">
                <defs>
                    <linearGradient id="grad-${containerId}" x1="0" y1="0" x2="0" y2="1">
                        <stop offset="0%" stop-color="${color}" stop-opacity="0.2" />
                        <stop offset="100%" stop-color="${color}" stop-opacity="0" />
                    </linearGradient>
                </defs>
                <path d="${areaData}" fill="url(#grad-${containerId})" />
                <path d="${pathData}" fill="none" stroke="${color}" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round" />
                ${pointsHtml}
                
                <text x="${padding.left}" y="${height-2}" fill="var(--text-tertiary)" font-size="10" text-anchor="start">${firstDate}</text>
                <text x="${width/2}" y="${height-2}" fill="var(--text-tertiary)" font-size="10" text-anchor="middle">${midDate}</text>
                <text x="${width - padding.right}" y="${height-2}" fill="var(--text-tertiary)" font-size="10" text-anchor="end">${lastDate}</text>
            </svg>
        `;
        
        container.innerHTML = svgHtml;
    },

    animateCounter(elementId, targetValue, isFloat = false) {
        const el = document.getElementById(elementId);
        if (!el) return;

        const duration = 1200;
        const startTime = performance.now();
        const startValue = 0;

        function update(currentTime) {
            const elapsed = currentTime - startTime;
            const progress = Math.min(elapsed / duration, 1);

            // Ease out cubic
            const eased = 1 - Math.pow(1 - progress, 3);
            const current = startValue + (targetValue - startValue) * eased;

            el.textContent = isFloat ? current.toFixed(1) : Math.round(current);

            if (progress < 1) {
                requestAnimationFrame(update);
            }
        }

        requestAnimationFrame(update);
    },

    renderRecentScans(scans) {
        const tbody = document.getElementById('recent-scans-body');
        if (!tbody) return;

        if (!scans || scans.length === 0) {
            tbody.innerHTML = '<tr class="empty-row"><td colspan="7">No scans yet. Start your first investigation!</td></tr>';
            return;
        }

        tbody.innerHTML = scans.map(scan => `
            <tr>
                <td><strong style="color: var(--text-primary)">${this.escapeHtml(scan.target_name)}</strong></td>
                <td><span class="badge badge-${scan.mode}">${scan.mode}</span></td>
                <td><span class="badge badge-${scan.status}">${scan.status}</span></td>
                <td>${scan.risk_score !== null ? `<span style="color: ${this.getRiskColor(scan.risk_score)}">${scan.risk_score}/10</span>` : '—'}</td>
                <td>${scan.platforms_found || 0}</td>
                <td>${this.formatDate(scan.created_at)}</td>
                <td>
                    ${scan.status === 'completed' ? `
                        <a href="#/results?id=${scan.id}" class="btn btn-sm btn-secondary">View</a>
                    ` : scan.status === 'running' ? `
                        <span class="badge badge-running">In Progress</span>
                    ` : '—'}
                </td>
            </tr>
        `).join('');
    },

    getRiskColor(score) {
        if (score >= 8) return 'var(--risk-critical)';
        if (score >= 6) return 'var(--risk-high)';
        if (score >= 3) return 'var(--risk-medium)';
        return 'var(--risk-low)';
    },

    formatDate(dateStr) {
        if (!dateStr) return '—';
        const date = new Date(dateStr);
        const now = new Date();
        const diffMs = now - date;
        const diffMins = Math.floor(diffMs / 60000);
        const diffHours = Math.floor(diffMs / 3600000);
        const diffDays = Math.floor(diffMs / 86400000);

        if (diffMins < 1) return 'Just now';
        if (diffMins < 60) return `${diffMins}m ago`;
        if (diffHours < 24) return `${diffHours}h ago`;
        if (diffDays < 7) return `${diffDays}d ago`;
        return date.toLocaleDateString();
    },

    escapeHtml(str) {
        const div = document.createElement('div');
        div.textContent = str;
        return div.innerHTML;
    },
};
