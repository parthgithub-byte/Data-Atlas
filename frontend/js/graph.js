/**
 * Graph Module — Enhanced Cytoscape.js identity graph visualization.
 * Features: neighborhood highlight, toolbar, search, PNG export, stats panel.
 */
const Graph = {
    cy: null,
    currentScanId: null,
    highlightActive: false,

    async load(scanId) {
        if (!scanId) {
            // Show scan selector
            await this.showScanSelector();
            return;
        }

        this.currentScanId = scanId;
        try {
            const data = await API.getGraph(scanId);
            this.renderGraph(data.graph, data.scan);
        } catch (error) {
            console.error('Failed to load graph:', error);
            document.getElementById('cy').innerHTML = `
                <div style="display:flex;align-items:center;justify-content:center;height:100%;color:var(--text-tertiary);flex-direction:column;gap:12px;">
                    <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" opacity="0.4">
                        <circle cx="12" cy="12" r="10"/><path d="M12 8v4m0 4h.01"/>
                    </svg>
                    <p>Failed to load graph data</p>
                </div>`;
        }
    },

    async showScanSelector() {
        const container = document.getElementById('cy');
        try {
            const data = await API.getHistory();
            const scans = data.scans.filter(s => s.status === 'completed');

            if (scans.length === 0) {
                container.innerHTML = `
                    <div class="graph-scan-selector">
                        <svg width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1" opacity="0.3">
                            <circle cx="6" cy="6" r="3"/><circle cx="18" cy="18" r="3"/><circle cx="18" cy="6" r="3"/>
                            <line x1="8.5" y1="6" x2="15.5" y2="6"/><line x1="18" y1="8.5" x2="18" y2="15.5"/>
                        </svg>
                        <p>No completed scans found.<br>Run a scan first to see the identity graph.</p>
                        <a href="#/scan" class="btn btn-primary">Start New Scan</a>
                    </div>`;
                return;
            }

            let itemsHtml = scans.slice(0, 10).map(s => `
                <div class="scan-pick-item" onclick="Graph.load(${s.id})">
                    <div class="pick-name">${s.target_name}</div>
                    <div class="pick-meta">${s.mode.toUpperCase()} · ${s.platforms_found || 0} platforms · Risk: ${s.risk_score || '—'}</div>
                </div>
            `).join('');

            container.innerHTML = `
                <div class="graph-scan-selector">
                    <svg width="64" height="64" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1" opacity="0.3">
                        <circle cx="6" cy="6" r="3"/><circle cx="18" cy="18" r="3"/><circle cx="18" cy="6" r="3"/><circle cx="6" cy="18" r="3"/>
                        <line x1="8.5" y1="6" x2="15.5" y2="6"/><line x1="6" y1="8.5" x2="6" y2="15.5"/>
                        <line x1="18" y1="8.5" x2="18" y2="15.5"/><line x1="8.5" y1="18" x2="15.5" y2="18"/>
                    </svg>
                    <p>Select a scan to visualize its identity graph</p>
                    <div class="scan-picker">${itemsHtml}</div>
                </div>`;
        } catch (error) {
            container.innerHTML = `
                <div class="graph-scan-selector">
                    <p>Could not load scans. Please try again.</p>
                </div>`;
        }
    },

    renderGraph(graphData, scan) {
        if (!graphData || (!graphData.nodes.length && !graphData.edges.length)) {
            document.getElementById('cy').innerHTML = `
                <div style="display:flex;align-items:center;justify-content:center;height:100%;color:var(--text-tertiary);flex-direction:column;gap:12px;">
                    <svg width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="1.5" opacity="0.4">
                        <circle cx="12" cy="12" r="10"/>
                        <path d="M12 16v-4m0-4h.01"/>
                    </svg>
                    <p>No graph data available for this scan</p>
                </div>`;
            return;
        }

        const subtitle = document.getElementById('graph-subtitle');
        if (subtitle && scan) {
            subtitle.textContent = `Identity graph for "${scan.target_name}" — ${graphData.nodes.length} nodes, ${graphData.edges.length} edges`;
        }

        // Color & shape maps
        const colorMap = { name: '#8b5cf6', email: '#3b82f6', phone: '#ef4444', username: '#10b981', platform: '#f59e0b', url: '#6b7280' };
        const shapeMap = { name: 'diamond', email: 'round-rectangle', phone: 'triangle', username: 'ellipse', platform: 'hexagon', url: 'rectangle' };

        // Prepare Cytoscape elements
        const elements = [];

        for (const node of graphData.nodes) {
            const d = node.data || node;
            elements.push({
                data: {
                    id: d.id,
                    label: d.label || d.id,
                    type: d.type || 'unknown',
                    color: colorMap[d.type] || '#6b7280',
                    shape: shapeMap[d.type] || 'ellipse',
                    url: d.url || '',
                    username: d.username || '',
                    central: d.central || false,
                },
            });
        }

        for (const edge of graphData.edges) {
            const d = edge.data || edge;
            elements.push({
                data: {
                    source: d.source,
                    target: d.target,
                    relationship: d.relationship || 'related',
                    confidence: d.confidence || 0.5,
                },
            });
        }

        // Initialize Cytoscape
        if (this.cy) {
            this.cy.destroy();
        }

        // Clear container
        document.getElementById('cy').innerHTML = '';

        this.cy = cytoscape({
            container: document.getElementById('cy'),
            elements: elements,
            style: [
                {
                    selector: 'node',
                    style: {
                        'background-color': 'data(color)',
                        'label': 'data(label)',
                        'color': '#e2e8f0',
                        'text-valign': 'bottom',
                        'text-halign': 'center',
                        'font-size': '10px',
                        'font-family': 'Inter, sans-serif',
                        'font-weight': 500,
                        'text-margin-y': 6,
                        'width': 28,
                        'height': 28,
                        'shape': 'data(shape)',
                        'border-width': 2,
                        'border-color': 'data(color)',
                        'border-opacity': 0.5,
                        'text-max-width': '90px',
                        'text-wrap': 'ellipsis',
                        'overlay-opacity': 0,
                        'transition-property': 'border-width, border-opacity, width, height, opacity',
                        'transition-duration': '0.2s',
                    },
                },
                {
                    selector: 'node[?central]',
                    style: {
                        'width': 48,
                        'height': 48,
                        'font-size': '13px',
                        'font-weight': 700,
                        'border-width': 3,
                        'text-margin-y': 8,
                    },
                },
                {
                    selector: 'node:hover',
                    style: {
                        'border-width': 4,
                        'border-opacity': 1,
                        'width': 36,
                        'height': 36,
                    },
                },
                {
                    selector: 'node:selected',
                    style: {
                        'border-width': 4,
                        'border-opacity': 1,
                        'border-color': '#ffffff',
                    },
                },
                {
                    selector: 'node.dimmed',
                    style: {
                        'opacity': 0.15,
                    },
                },
                {
                    selector: 'node.highlighted',
                    style: {
                        'border-width': 4,
                        'border-opacity': 1,
                        'width': 36,
                        'height': 36,
                    },
                },
                {
                    selector: 'edge',
                    style: {
                        'width': function(ele) {
                            return Math.max(1, ele.data('confidence') * 3);
                        },
                        'line-color': 'rgba(100, 116, 180, 0.3)',
                        'target-arrow-color': 'rgba(100, 116, 180, 0.4)',
                        'target-arrow-shape': 'triangle',
                        'curve-style': 'bezier',
                        'arrow-scale': 0.8,
                        'font-size': '8px',
                        'color': 'rgba(100, 116, 180, 0.5)',
                        'text-rotation': 'autorotate',
                        'text-margin-y': -8,
                        'font-family': 'Inter, sans-serif',
                        'overlay-opacity': 0,
                        'transition-property': 'opacity, line-color',
                        'transition-duration': '0.2s',
                    },
                },
                {
                    selector: 'edge.dimmed',
                    style: {
                        'opacity': 0.08,
                    },
                },
                {
                    selector: 'edge.highlighted',
                    style: {
                        'line-color': 'rgba(59, 130, 246, 0.7)',
                        'target-arrow-color': 'rgba(59, 130, 246, 0.8)',
                        'width': 3,
                    },
                },
                {
                    selector: 'edge:hover',
                    style: {
                        'line-color': 'rgba(59, 130, 246, 0.6)',
                        'width': 3,
                    },
                },
            ],
            layout: {
                name: 'cose',
                animate: true,
                animationDuration: 800,
                randomize: true,
                nodeRepulsion: function() { return 6000; },
                idealEdgeLength: function() { return 80; },
                gravity: 0.3,
                numIter: 500,
                padding: 40,
            },
            minZoom: 0.2,
            maxZoom: 4,
            wheelSensitivity: 0.3,
        });

        // Tap node → show details + neighborhood highlight
        this.cy.on('tap', 'node', (evt) => {
            const node = evt.target;
            this.showNodeDetails(node);
            this.highlightNeighborhood(node);
        });

        this.cy.on('tap', (evt) => {
            if (evt.target === this.cy) {
                this.hideNodeDetails();
                this.clearHighlight();
            }
        });

        // Build toolbar and panels
        this.buildToolbar();
        this.buildStatsPanel(graphData);
        this.initControls();
    },

    highlightNeighborhood(node) {
        this.clearHighlight();
        this.highlightActive = true;

        const neighborhood = node.neighborhood().add(node);
        this.cy.elements().addClass('dimmed');
        neighborhood.removeClass('dimmed');
        neighborhood.nodes().addClass('highlighted');
        neighborhood.edges().addClass('highlighted');
    },

    clearHighlight() {
        if (!this.cy || !this.highlightActive) return;
        this.cy.elements().removeClass('dimmed highlighted');
        this.highlightActive = false;
    },

    showNodeDetails(nodeEl) {
        const data = nodeEl.data();
        const panel = document.getElementById('node-detail-panel');
        const label = document.getElementById('node-detail-label');
        const type = document.getElementById('node-detail-type');
        const meta = document.getElementById('node-detail-meta');

        if (!panel) return;

        label.textContent = data.label || data.id;
        type.textContent = data.type || 'Unknown';

        const colorMap = { name: '#8b5cf6', email: '#3b82f6', phone: '#ef4444', username: '#10b981', platform: '#f59e0b' };
        type.style.background = (colorMap[data.type] || '#6b7280') + '33';
        type.style.color = colorMap[data.type] || '#6b7280';

        let metaHtml = '';
        if (data.url) metaHtml += `<p><strong>URL:</strong> <a href="${data.url}" target="_blank" rel="noopener" style="word-break:break-all;">${data.url}</a></p>`;
        if (data.username) metaHtml += `<p><strong>Username:</strong> ${data.username}</p>`;
        metaHtml += `<p><strong>Node ID:</strong> <span style="font-family:var(--font-mono);font-size:0.75rem;">${data.id}</span></p>`;

        // Connected nodes
        const connectedNodes = nodeEl.neighborhood().nodes();
        if (connectedNodes.length > 0) {
            metaHtml += `<div class="node-detail-connections"><h4>Connected (${connectedNodes.length})</h4>`;
            connectedNodes.forEach(n => {
                const nData = n.data();
                const color = colorMap[nData.type] || '#6b7280';
                metaHtml += `<div class="connection-item"><span class="conn-dot" style="background:${color}"></span>${nData.label}</div>`;
            });
            metaHtml += `</div>`;
        }

        meta.innerHTML = metaHtml;
        panel.style.display = 'block';
    },

    hideNodeDetails() {
        const panel = document.getElementById('node-detail-panel');
        if (panel) panel.style.display = 'none';
    },

    buildToolbar() {
        // Remove existing toolbar
        const existing = document.querySelector('.graph-toolbar');
        if (existing) existing.remove();

        const toolbar = document.createElement('div');
        toolbar.className = 'graph-toolbar';
        toolbar.innerHTML = `
            <button onclick="Graph.zoomIn()" class="tooltip" data-tooltip="Zoom In" title="Zoom In">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3M8 11h6M11 8v6"/></svg>
            </button>
            <button onclick="Graph.zoomOut()" class="tooltip" data-tooltip="Zoom Out" title="Zoom Out">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"/><path d="m21 21-4.3-4.3M8 11h6"/></svg>
            </button>
            <button onclick="Graph.fitView()" class="tooltip" data-tooltip="Fit View" title="Fit View">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M15 3h6v6M9 21H3v-6M21 3l-7 7M3 21l7-7"/></svg>
            </button>
            <div class="toolbar-divider"></div>
            <button onclick="Graph.toggleLabels()" id="btn-toggle-labels" class="tooltip active" data-tooltip="Toggle Labels" title="Toggle Labels">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M4 7V4h16v3M9 20h6M12 4v16"/></svg>
            </button>
            <button onclick="Graph.toggleEdgeLabels()" id="btn-toggle-edge-labels" class="tooltip" data-tooltip="Edge Labels" title="Edge Labels">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M17 3v4M3 11h4m10 6v4M3 15h4"/><line x1="4" y1="6" x2="20" y2="18"/></svg>
            </button>
            <div class="toolbar-divider"></div>
            <button onclick="Graph.exportPNG()" class="tooltip" data-tooltip="Export PNG" title="Export PNG">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4"/><polyline points="7 10 12 15 17 10"/><line x1="12" y1="15" x2="12" y2="3"/></svg>
            </button>
            <button onclick="Graph.clearHighlight()" class="tooltip" data-tooltip="Clear Highlight" title="Clear Highlight">
                <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"/><path d="M15 9l-6 6M9 9l6 6"/></svg>
            </button>
        `;

        const container = document.querySelector('.graph-container');
        if (container) container.appendChild(toolbar);
    },

    buildStatsPanel(graphData) {
        const existing = document.querySelector('.graph-stats-panel');
        if (existing) existing.remove();

        const colorMap = { name: '#8b5cf6', email: '#3b82f6', phone: '#ef4444', username: '#10b981', platform: '#f59e0b', url: '#6b7280' };
        const typeCounts = {};
        for (const node of graphData.nodes) {
            const t = (node.data || node).type || 'unknown';
            typeCounts[t] = (typeCounts[t] || 0) + 1;
        }

        let rowsHtml = Object.entries(typeCounts).map(([type, count]) => `
            <div class="graph-stat-row">
                <span><span class="stat-dot" style="background:${colorMap[type] || '#6b7280'}"></span>${type}</span>
                <span>${count}</span>
            </div>
        `).join('');

        const panel = document.createElement('div');
        panel.className = 'graph-stats-panel glass-card';
        panel.innerHTML = `
            <h4>Graph Stats</h4>
            <div class="graph-stat-row"><span>Nodes</span><span>${graphData.nodes.length}</span></div>
            <div class="graph-stat-row"><span>Edges</span><span>${graphData.edges.length}</span></div>
            <div style="height:1px;background:var(--border-secondary);margin:8px 0;"></div>
            ${rowsHtml}
        `;

        const container = document.querySelector('.graph-container');
        if (container) container.appendChild(panel);
    },

    zoomIn() { if (this.cy) this.cy.zoom(this.cy.zoom() * 1.3); },
    zoomOut() { if (this.cy) this.cy.zoom(this.cy.zoom() / 1.3); },
    fitView() { if (this.cy) this.cy.fit(undefined, 40); },

    toggleLabels() {
        if (!this.cy) return;
        const btn = document.getElementById('btn-toggle-labels');
        const showing = btn?.classList.contains('active');
        if (showing) {
            this.cy.style().selector('node').style('label', '').update();
            btn?.classList.remove('active');
        } else {
            this.cy.style().selector('node').style('label', 'data(label)').update();
            btn?.classList.add('active');
        }
    },

    toggleEdgeLabels() {
        if (!this.cy) return;
        const btn = document.getElementById('btn-toggle-edge-labels');
        const showing = btn?.classList.contains('active');
        if (showing) {
            this.cy.style().selector('edge').style('label', '').update();
            btn?.classList.remove('active');
        } else {
            this.cy.style().selector('edge').style('label', 'data(relationship)').update();
            btn?.classList.add('active');
        }
    },

    exportPNG() {
        if (!this.cy) return;
        const png = this.cy.png({ scale: 2, bg: '#050816', full: true });
        const link = document.createElement('a');
        link.download = `dfas_graph_${this.currentScanId || 'export'}.png`;
        link.href = png;
        link.click();
        Toast.show('Graph exported as PNG', 'success');
    },

    initControls() {
        // Layout selector
        const layoutSelect = document.getElementById('graph-layout');
        if (layoutSelect) {
            layoutSelect.onchange = () => {
                const layoutName = layoutSelect.value;
                const layoutOptions = {
                    name: layoutName,
                    animate: true,
                    animationDuration: 800,
                    padding: 40,
                };

                if (layoutName === 'cose') {
                    layoutOptions.nodeRepulsion = function() { return 6000; };
                    layoutOptions.idealEdgeLength = function() { return 80; };
                    layoutOptions.gravity = 0.3;
                }

                this.cy.layout(layoutOptions).run();
            };
        }

        // Fit button
        const btnFit = document.getElementById('btn-graph-fit');
        if (btnFit) {
            btnFit.onclick = () => this.fitView();
        }

        // Close panel
        const panelClose = document.getElementById('panel-close');
        if (panelClose) {
            panelClose.onclick = () => {
                this.hideNodeDetails();
                this.clearHighlight();
            };
        }
    },
};

/**
 * Toast notification system
 */
const Toast = {
    show(message, type = 'info', duration = 3000) {
        let container = document.querySelector('.toast-container');
        if (!container) {
            container = document.createElement('div');
            container.className = 'toast-container';
            document.body.appendChild(container);
        }

        const toast = document.createElement('div');
        toast.className = `toast ${type}`;
        toast.textContent = message;
        container.appendChild(toast);

        setTimeout(() => {
            toast.style.animation = 'toastOut 0.3s ease forwards';
            setTimeout(() => toast.remove(), 300);
        }, duration);
    },
};
