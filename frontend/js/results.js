/**
 * Results Module — Scan history, result cards, search/filter, export, and report modal.
 */
const Results = {
    currentScanId: null,
    allResults: [],

    async load() {
        try {
            const data = await API.getHistory();
            this.renderScanList(data.scans);
        } catch (error) {
            console.error('Failed to load results:', error);
        }
    },

    renderScanList(scans) {
        const list = document.getElementById('results-scan-list');
        if (!list) return;

        if (!scans || scans.length === 0) {
            list.innerHTML = '<p style="color:var(--text-tertiary);font-size:0.85rem;text-align:center;padding:20px;">No scans found</p>';
            return;
        }

        list.innerHTML = scans.map(s => `
            <div class="scan-list-item ${s.id === this.currentScanId ? 'active' : ''}"
                 onclick="Results.selectScan(${s.id})">
                <span class="scan-item-name">${s.target_name}</span>
                <div style="display:flex;align-items:center;gap:8px;margin-top:4px;">
                    <span class="badge badge-${s.mode}">${s.mode}</span>
                    <span class="badge badge-${s.status}">${s.status}</span>
                    <span class="scan-item-date">${this.formatDate(s.created_at)}</span>
                </div>
            </div>
        `).join('');
    },

    async selectScan(scanId) {
        this.currentScanId = scanId;

        // Update active state
        document.querySelectorAll('.scan-list-item').forEach(el => el.classList.remove('active'));
        event?.target?.closest?.('.scan-list-item')?.classList?.add('active');

        try {
            const data = await API.getScanResults(scanId);
            this.allResults = data.results || [];
            this.renderResults(data.scan, this.allResults);
        } catch (error) {
            console.error('Failed to load results:', error);
        }
    },

    renderResults(scan, results) {
        const emptyEl = document.getElementById('results-empty');
        const detailEl = document.getElementById('results-detail');

        if (emptyEl) emptyEl.style.display = 'none';
        if (detailEl) detailEl.style.display = 'block';

        // Risk summary
        this.renderRiskSummary(scan, results);

        // Results toolbar with search and export
        const toolbarEl = document.getElementById('results-toolbar');
        if (toolbarEl) {
            toolbarEl.innerHTML = `
                <div class="search-bar">
                    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2">
                        <circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3"/>
                    </svg>
                    <input type="text" id="results-search" placeholder="Filter results by platform, username..." oninput="Results.filterResults(this.value)">
                </div>
                <div class="btn-group">
                    <button class="btn btn-ghost btn-xs" onclick="Results.exportJSON()">
                        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
                        JSON
                    </button>
                    <button class="btn btn-ghost btn-xs" onclick="Results.exportCSV()">
                        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
                        CSV
                    </button>
                    <button class="btn btn-ghost btn-xs" onclick="Results.exportPDF()" style="color:var(--accent-red);">
                        <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"/><polyline points="14 2 14 8 20 8"/><line x1="16" y1="13" x2="8" y2="13"/><line x1="16" y1="17" x2="8" y2="17"/><polyline points="10 9 9 9 8 9"/></svg>
                        PDF Report
                    </button>
                    <span class="results-count" id="results-count">${results.length} results</span>
                </div>
            `;
        }

        // Results grid
        this.renderResultGrid(results);
    },

    filterResults(query) {
        const q = query.toLowerCase();
        const filtered = this.allResults.filter(r =>
            (r.platform || '').toLowerCase().includes(q) ||
            (r.username || '').toLowerCase().includes(q) ||
            (r.url || '').toLowerCase().includes(q) ||
            (r.category || '').toLowerCase().includes(q)
        );
        this.renderResultGrid(filtered);
        const countEl = document.getElementById('results-count');
        if (countEl) countEl.textContent = `${filtered.length} of ${this.allResults.length} results`;
    },

    renderResultGrid(results) {
        const grid = document.getElementById('results-grid');
        if (!grid) return;

        if (!results || results.length === 0) {
            grid.innerHTML = '<p style="color:var(--text-tertiary);text-align:center;padding:40px;">No results match your filter</p>';
            return;
        }

        grid.innerHTML = results.map((r, i) => {
            const score = r.match_score;
            const scorePct = score != null ? Math.round(score * 100) : null;
            const scoreColour = score == null ? '#6b7280'
                : score >= 0.70 ? '#16a34a'
                : score >= 0.40 ? '#ca8a04'
                : '#dc2626';

            // Activity status derived from last_seen_at
            let activityLabel = null, activityColour = '#6b7280';
            if (r.last_seen_at) {
                const ageDays = (Date.now() - new Date(r.last_seen_at).getTime()) / 86400000;
                if (ageDays <= 1)      { activityLabel = '● Active';   activityColour = '#16a34a'; }
                else if (ageDays <= 30) { activityLabel = '● Recent';   activityColour = '#2563eb'; }
                else                   { activityLabel = '○ Historical'; activityColour = '#6b7280'; }
            }

            const reasons = r.match_reasons || [];
            const reasonsHtml = reasons.length > 0 ? `
                <details style="margin-top:6px;">
                    <summary style="font-size:0.72rem;color:var(--text-tertiary);cursor:pointer;list-style:none;display:flex;align-items:center;gap:4px;">
                        <svg width="10" height="10" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="m9 18 6-6-6-6"/></svg>
                        ${reasons.length} match signal${reasons.length > 1 ? 's' : ''}
                    </summary>
                    <ul style="margin:4px 0 0 16px;padding:0;font-size:0.72rem;color:var(--text-secondary);list-style:disc;">
                        ${reasons.map(r => `<li>${r}</li>`).join('')}
                    </ul>
                </details>
            ` : '';

            return `
            <div class="result-card" style="animation-delay:${i * 0.03}s">
                <div class="result-card-header">
                    <span class="result-card-platform">${r.platform}</span>
                    <span class="badge badge-${r.risk_level || 'low'}">${r.risk_level || 'low'}</span>
                </div>
                ${r.username ? `<span class="result-card-username">@${r.username}</span>` : ''}
                ${r.display_name ? `<div style="font-size:0.82rem;color:var(--text-secondary);margin-bottom:4px;">${r.display_name}</div>` : ''}
                ${r.bio ? `<p style="font-size:0.78rem;color:var(--text-tertiary);margin-bottom:8px;line-height:1.4;">${r.bio.substring(0, 120)}${r.bio.length > 120 ? '...' : ''}</p>` : ''}
                <div class="result-card-meta">
                    ${scorePct != null ? `
                        <span class="result-meta-pill" style="background:${scoreColour}22;color:${scoreColour};border:1px solid ${scoreColour}44;font-weight:600;">
                            Match ${scorePct}%
                        </span>` : ''}
                    ${activityLabel ? `
                        <span class="result-meta-pill" style="color:${activityColour};font-size:0.70rem;">
                            ${activityLabel}
                        </span>` : ''}
                    ${r.last_seen_at ? `<span class="result-meta-pill">Seen ${this.formatDate(r.last_seen_at)}</span>` : ''}
                    ${r.evidence_available ? `<span class="result-meta-pill" style="color:#a855f7;" title="${r.evidence_filename || 'Evidence archived'}">Archived Evidence</span>` : ''}
                </div>
                ${reasonsHtml}
                <div class="result-card-entities">
                    ${(r.emails_found || []).map(e => `<span class="entity-tag entity-tag-email">${e}</span>`).join('')}
                    ${(r.phones_found || []).map(p => `<span class="entity-tag entity-tag-phone">${p}</span>`).join('')}
                </div>
                <a href="${r.url}" target="_blank" rel="noopener noreferrer" class="result-card-url">${r.url}</a>
            </div>
        `}).join('');
    },

    renderRiskSummary(scan, results) {
        const scoreEl = document.getElementById('risk-score-value');
        const circleEl = document.getElementById('risk-score-circle');
        const nameEl = document.getElementById('risk-target-name');
        const badgeEl = document.getElementById('risk-badge');
        const platformsEl = document.getElementById('result-platforms');
        const entitiesEl = document.getElementById('result-entities');
        const modeEl = document.getElementById('result-mode');

        if (scoreEl) scoreEl.textContent = scan.risk_score != null ? scan.risk_score : '—';
        if (nameEl) nameEl.textContent = scan.target_name;
        if (platformsEl) platformsEl.textContent = scan.platforms_found || results.length;
        if (entitiesEl) entitiesEl.textContent = scan.entities_found || 0;
        if (modeEl) modeEl.textContent = scan.mode === 'full' ? 'Full' : 'Quick';

        // Risk level badge
        const score = scan.risk_score || 0;
        let level = 'low', levelText = 'LOW RISK';
        if (score >= 8) { level = 'critical'; levelText = 'CRITICAL'; }
        else if (score >= 6) { level = 'high'; levelText = 'HIGH'; }
        else if (score >= 3) { level = 'medium'; levelText = 'MEDIUM'; }

        if (badgeEl) { badgeEl.className = `badge badge-${level} risk-badge`; badgeEl.textContent = levelText; }
        if (circleEl) { circleEl.className = `risk-score-circle ${level}`; }
    },

    async exportJSON() {
        if (!this.currentScanId) return;
        window.open(`${API.BASE_URL}/api/export/${this.currentScanId}/json`, '_blank');
        Toast.show('Downloading JSON export...', 'info');
    },

    async exportCSV() {
        if (!this.currentScanId) return;
        window.open(`${API.BASE_URL}/api/export/${this.currentScanId}/csv`, '_blank');
        Toast.show('Downloading CSV export...', 'info');
    },

    async exportPDF() {
        if (!this.currentScanId) return;
        Toast.show('Generating PDF report...', 'info');
        window.open(`${API.BASE_URL}/api/export/${this.currentScanId}/pdf`, '_blank');
    },

    async showReport() {
        if (!this.currentScanId) return;
        const modal = document.getElementById('report-modal');
        const body = document.getElementById('report-modal-body');
        if (!modal || !body) return;

        modal.style.display = 'flex';
        body.innerHTML = '<p style="text-align:center;color:var(--text-tertiary);padding:40px;">Loading report...</p>';

        try {
            const data = await API.getReport(this.currentScanId);
            this.renderReport(data.report);
        } catch (error) {
            body.innerHTML = '<p style="text-align:center;color:var(--accent-red);">Failed to load report</p>';
        }
    },

    renderReport(report) {
        const body = document.getElementById('report-modal-body');
        if (!body || !report) return;

        let html = `<div class="report-summary"><strong>Summary:</strong> ${report.summary || 'No summary available.'}</div>`;

        if (report.findings && report.findings.length > 0) {
            html += '<h3 style="margin-bottom:12px;">Findings</h3>';
            for (const finding of report.findings) {
                html += `
                    <div class="finding-card">
                        <div class="finding-header">
                            <span class="finding-title">${finding.title || 'Finding'}</span>
                            <span class="badge badge-${finding.severity || 'medium'}">${finding.severity || 'medium'}</span>
                        </div>
                        <p class="finding-desc">${finding.description || ''}</p>
                        ${finding.recommendation ? `<div class="finding-rec">💡 ${finding.recommendation}</div>` : ''}
                    </div>
                `;
            }
        }

        if (report.recommendations && report.recommendations.length > 0) {
            html += '<h3 style="margin:20px 0 12px;">Recommendations</h3>';
            html += '<div class="report-summary"><ul style="padding-left:18px;">';
            for (const rec of report.recommendations) {
                html += `<li style="margin-bottom:6px;">${rec}</li>`;
            }
            html += '</ul></div>';
        }

        body.innerHTML = html;
    },

    formatDate(isoStr) {
        if (!isoStr) return '';
        const d = new Date(isoStr);
        const now = new Date();
        const diff = now - d;
        if (diff < 60000) return 'Just now';
        if (diff < 3600000) return `${Math.floor(diff / 60000)}m ago`;
        if (diff < 86400000) return `${Math.floor(diff / 3600000)}h ago`;
        return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
    },
};
