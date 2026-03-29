/**
 * Catalog Module - In-app editor for the platform catalog JSON.
 */
const Catalog = {
    initialized: false,

    bindEvents() {
        if (this.initialized) return;
        this.initialized = true;

        const reloadBtn = document.getElementById('btn-catalog-reload');
        if (reloadBtn) {
            reloadBtn.addEventListener('click', () => this.load());
        }

        const formatBtn = document.getElementById('btn-catalog-format');
        if (formatBtn) {
            formatBtn.addEventListener('click', () => this.formatEditor());
        }

        const saveBtn = document.getElementById('btn-catalog-save');
        if (saveBtn) {
            saveBtn.addEventListener('click', () => this.save());
        }
    },

    async load() {
        this.bindEvents();
        this.setStatus('Loading platform catalog...', 'info');
        this.setBusy(true);

        try {
            const data = await API.getPlatformCatalog();
            const editor = document.getElementById('catalog-editor');
            if (editor) {
                editor.value = JSON.stringify(data.catalog, null, 2);
            }

            const canEdit = !!API.getUser()?.capabilities?.manage_catalog;
            this.renderSummary(data.summary, data.storage_label);
            this.setEditMode(canEdit);
            if (canEdit) {
                this.setStatus('Catalog loaded. Edit the JSON and save when ready.', 'info');
            }
        } catch (error) {
            this.setStatus(error.error || 'Failed to load platform catalog.', 'error');
            Toast.show('Failed to load platform catalog', 'error');
        } finally {
            this.setBusy(false);
        }
    },

    renderSummary(summary, storageLabel) {
        const totalEl = document.getElementById('catalog-total-platforms');
        const enumEl = document.getElementById('catalog-enumerated-platforms');
        const priorityEl = document.getElementById('catalog-priority-platforms');
        const pathEl = document.getElementById('catalog-file-path');
        const categoriesEl = document.getElementById('catalog-categories');

        if (totalEl) totalEl.textContent = summary?.total_platforms ?? 0;
        if (enumEl) enumEl.textContent = summary?.enumerated_platforms ?? 0;
        if (priorityEl) priorityEl.textContent = summary?.search_priority_platforms ?? 0;
        if (pathEl) pathEl.textContent = storageLabel || 'Server-managed';

        if (!categoriesEl) return;
        categoriesEl.innerHTML = '';

        const categories = summary?.categories || {};
        Object.entries(categories)
            .sort((a, b) => b[1] - a[1])
            .forEach(([name, count]) => {
                const chip = document.createElement('span');
                chip.className = 'catalog-chip';
                chip.textContent = `${name}: ${count}`;
                categoriesEl.appendChild(chip);
            });
    },

    formatEditor() {
        const editor = document.getElementById('catalog-editor');
        if (!editor) return;

        try {
            const parsed = JSON.parse(editor.value);
            editor.value = JSON.stringify(parsed, null, 2);
            this.setStatus('JSON formatted successfully.', 'success');
            Toast.show('Catalog JSON formatted', 'success');
        } catch (error) {
            this.setStatus(`Invalid JSON: ${error.message}`, 'error');
            Toast.show('Fix JSON before formatting', 'error');
        }
    },

    async save() {
        const editor = document.getElementById('catalog-editor');
        if (!editor) return;

        if (!API.getUser()?.capabilities?.manage_catalog) {
            this.setStatus('Only admin or analyst accounts can edit the live catalog.', 'error');
            Toast.show('Catalog editing is restricted', 'error');
            return;
        }

        let parsed;
        try {
            parsed = JSON.parse(editor.value);
        } catch (error) {
            this.setStatus(`Invalid JSON: ${error.message}`, 'error');
            Toast.show('Fix JSON before saving', 'error');
            return;
        }

        this.setBusy(true, 'Saving...');
        this.setStatus('Saving platform catalog...', 'info');

        try {
            const data = await API.savePlatformCatalog(parsed);
            editor.value = JSON.stringify(data.catalog, null, 2);
            this.renderSummary(data.summary, data.storage_label);
            this.setStatus('Catalog saved. New scans will use the updated platform list.', 'success');
            Toast.show('Platform catalog saved', 'success');
        } catch (error) {
            this.setStatus(error.error || 'Failed to save catalog.', 'error');
            Toast.show('Failed to save platform catalog', 'error');
        } finally {
            this.setBusy(false);
        }
    },

    setBusy(isBusy, busyLabel = 'Save Catalog') {
        const saveBtn = document.getElementById('btn-catalog-save');
        const reloadBtn = document.getElementById('btn-catalog-reload');
        const formatBtn = document.getElementById('btn-catalog-format');

        [saveBtn, reloadBtn, formatBtn].forEach((button) => {
            if (button) button.disabled = isBusy;
        });

        if (saveBtn) {
            saveBtn.querySelector('span').textContent = isBusy ? busyLabel : 'Save Catalog';
        }
    },

    setEditMode(canEdit) {
        const editor = document.getElementById('catalog-editor');
        const saveBtn = document.getElementById('btn-catalog-save');

        if (editor) editor.readOnly = !canEdit;
        if (saveBtn) saveBtn.style.display = canEdit ? '' : 'none';

        if (!canEdit) {
            this.setStatus('Read-only mode: only admin or analyst accounts can edit the live catalog.', 'info');
        }
    },

    setStatus(message, type = 'info') {
        const statusEl = document.getElementById('catalog-status');
        if (!statusEl) return;
        statusEl.className = `catalog-status ${type}`;
        statusEl.textContent = message;
    },
};
