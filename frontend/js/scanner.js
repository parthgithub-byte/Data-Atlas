/**
 * Scanner Module - Scan form, mode selection, and live progress tracking.
 */
const Scanner = {
    initialized: false,
    currentScanId: null,
    pollInterval: null,

    init() {
        this.prefillOwnedIdentity();
        this.reset();

        if (this.initialized) {
            return;
        }

        this.bindEvents();
        this.initialized = true;
    },

    bindEvents() {
        const form = document.getElementById('scan-form');
        if (form) {
            form.addEventListener('submit', (event) => {
                event.preventDefault();
                this.startScan();
            });
        }

        const modeInputs = document.querySelectorAll('input[name="scan-mode"]');
        modeInputs.forEach((input) => {
            input.addEventListener('change', () => {
                document.querySelectorAll('.mode-option').forEach((option) => option.classList.remove('mode-selected'));
                input.closest('.mode-option').classList.add('mode-selected');
            });
        });

        // Bind tag input events for usernames
        this.bindTagInput('scan-username-input', 'username-tag-wrapper', 'tag-chip');
        // Bind tag input events for phones
        this.bindTagInput('scan-phone-input', 'phone-tag-wrapper', 'tag-chip tag-chip-phone');
    },

    /**
     * Bind Enter and Backspace key events for a tag input field.
     */
    bindTagInput(inputId, wrapperId, chipClass) {
        const input = document.getElementById(inputId);
        const wrapper = document.getElementById(wrapperId);
        if (!input || !wrapper) return;

        input.addEventListener('keydown', (e) => {
            if (e.key === 'Enter') {
                e.preventDefault();
                const val = input.value.trim();
                if (val) {
                    this.addTag(wrapperId, val, chipClass);
                    input.value = '';
                }
            }
            if (e.key === 'Backspace' && input.value === '') {
                const chips = wrapper.querySelectorAll('.tag-chip');
                if (chips.length > 0) {
                    chips[chips.length - 1].remove();
                    this.updateTagCount(wrapperId);
                }
            }
        });

        // Clicking the wrapper focuses the input
        wrapper.addEventListener('click', () => {
            input.focus();
        });
    },

    /**
     * Add a chip tag to a tag-input-wrapper.
     */
    addTag(wrapperId, value, chipClass) {
        const wrapper = document.getElementById(wrapperId);
        const input = wrapper.querySelector('.tag-input-field');
        if (!wrapper || !input) return;

        // Prevent duplicates
        const existing = wrapper.querySelectorAll('.tag-chip');
        for (const chip of existing) {
            if (chip.dataset.value.toLowerCase() === value.toLowerCase()) return;
        }

        const chip = document.createElement('span');
        chip.className = chipClass;
        chip.dataset.value = value;
        chip.innerHTML = `${this.escapeHtml(value)}<button type="button" class="tag-remove" title="Remove">&times;</button>`;

        chip.querySelector('.tag-remove').addEventListener('click', (e) => {
            e.stopPropagation();
            chip.remove();
            this.updateTagCount(wrapperId);
        });

        wrapper.insertBefore(chip, input);
        this.updateTagCount(wrapperId);
    },

    /**
     * Update the tag count indicator in a wrapper.
     */
    updateTagCount(wrapperId) {
        const wrapper = document.getElementById(wrapperId);
        if (!wrapper) return;
        const count = wrapper.querySelectorAll('.tag-chip').length;

        let countEl = wrapper.querySelector('.tag-count');
        if (count > 0) {
            if (!countEl) {
                countEl = document.createElement('span');
                countEl.className = 'tag-count';
                wrapper.appendChild(countEl);
            }
            countEl.textContent = `${count} added`;
        } else if (countEl) {
            countEl.remove();
        }
    },

    /**
     * Get all tag values from a wrapper.
     */
    getTagValues(wrapperId) {
        const wrapper = document.getElementById(wrapperId);
        if (!wrapper) return [];
        return Array.from(wrapper.querySelectorAll('.tag-chip')).map(chip => chip.dataset.value);
    },

    /**
     * Clear all tags from a wrapper.
     */
    clearTags(wrapperId) {
        const wrapper = document.getElementById(wrapperId);
        if (!wrapper) return;
        wrapper.querySelectorAll('.tag-chip').forEach(chip => chip.remove());
        const countEl = wrapper.querySelector('.tag-count');
        if (countEl) countEl.remove();
        const input = wrapper.querySelector('.tag-input-field');
        if (input) input.value = '';
    },

    escapeHtml(str) {
        const div = document.createElement('div');
        div.textContent = str;
        return div.innerHTML;
    },

    isPlaceholderEmail(email) {
        return (email || '').trim().toLowerCase().endsWith('@digilocker.gov.in');
    },

    clearError() {
        const errorEl = document.getElementById('scan-error');
        if (errorEl) {
            errorEl.textContent = '';
        }
    },

    showError(message) {
        const errorEl = document.getElementById('scan-error');
        if (errorEl) {
            errorEl.textContent = message;
        }

        if (typeof Toast !== 'undefined') {
            Toast.show(message, 'error');
        } else {
            alert(message);
        }
    },

    prefillOwnedIdentity() {
        const user = API.getUser();
        const nameInput = document.getElementById('scan-name');
        const emailInput = document.getElementById('scan-email');
        const identityNotice = document.getElementById('scan-policy-identity');

        if (!nameInput || !emailInput) {
            return;
        }

        const trustedName = user?.full_name || '';
        const trustedEmail = user?.email || '';
        const hasUsableEmail = trustedEmail && !this.isPlaceholderEmail(trustedEmail);

        nameInput.value = trustedName;
        nameInput.readOnly = true;

        emailInput.value = hasUsableEmail ? trustedEmail : '';
        emailInput.readOnly = true;
        emailInput.placeholder = hasUsableEmail
            ? 'Locked to your account email'
            : 'No verified account email is available for scanning';

        if (identityNotice) {
            const identityBits = [trustedName || 'your signed-in account'];
            if (hasUsableEmail) {
                identityBits.push(trustedEmail);
            }
            identityNotice.textContent = `This scan is locked to ${identityBits.join(' | ')}. Optional username, phone, and address fields must also belong to you.`;
        }
    },

    async startScan() {
        this.clearError();

        const user = API.getUser();
        const name = document.getElementById('scan-name').value.trim();
        const email = document.getElementById('scan-email').value.trim();
        const usernames = this.getTagValues('username-tag-wrapper');
        const phones = this.getTagValues('phone-tag-wrapper');
        const address = (document.getElementById('scan-address')?.value || '').trim();
        const mode = document.querySelector('input[name="scan-mode"]:checked').value;
        const selfAttested = document.getElementById('scan-self-attested').checked;
        const trustedName = user?.full_name?.trim() || '';
        const trustedEmail = user?.email?.trim() || '';

        if (!trustedName) {
            this.showError('Your account is missing a profile name. Please update your account before scanning.');
            return;
        }

        if (name !== trustedName) {
            this.showError('The scan identity is locked to your signed-in profile. You cannot scan another person.');
            return;
        }

        if (email && trustedEmail && email.toLowerCase() !== trustedEmail.toLowerCase()) {
            this.showError('The scan email is locked to your signed-in account. You cannot scan another person.');
            return;
        }

        if (!selfAttested) {
            this.showError('Confirm the self-scan checkbox before starting. Scanning other people is blocked.');
            return;
        }

        const btn = document.getElementById('btn-start-scan');
        btn.disabled = true;
        btn.querySelector('span').textContent = 'Starting...';

        try {
            const scanData = {
                name: trustedName,
                self_attested: true,
            };

            if (trustedEmail && !this.isPlaceholderEmail(trustedEmail)) {
                scanData.email = trustedEmail;
            }
            if (usernames.length > 0) scanData.username = usernames.join(',');
            if (phones.length > 0) scanData.phone = phones.join(',');
            if (address) scanData.address = address;

            const data = mode === 'full'
                ? await API.startFullScan(scanData)
                : await API.startQuickScan(scanData);

            this.currentScanId = data.scan.id;
            this.showProgress();
            this.startPolling();
        } catch (error) {
            this.showError(error.error || 'Failed to start scan.');
        } finally {
            btn.disabled = false;
            btn.querySelector('span').textContent = 'Start Investigation';
        }
    },

    showProgress() {
        const card = document.getElementById('scan-progress-card');
        if (card) {
            card.style.display = 'block';
            card.scrollIntoView({ behavior: 'smooth', block: 'nearest' });
        }
    },

    startPolling() {
        if (this.pollInterval) clearInterval(this.pollInterval);

        this.pollInterval = setInterval(async () => {
            try {
                const data = await API.getScanStatus(this.currentScanId);
                this.updateProgress(data.scan);

                if (data.scan.status === 'completed' || data.scan.status === 'failed') {
                    clearInterval(this.pollInterval);
                    this.pollInterval = null;

                    if (data.scan.status === 'completed') {
                        setTimeout(() => {
                            window.location.hash = `#/results?id=${this.currentScanId}`;
                        }, 1500);
                    }
                }
            } catch (error) {
                console.error('Polling error:', error);
            }
        }, 1500);
    },

    updateProgress(scan) {
        const bar = document.getElementById('scan-progress-bar');
        if (bar) bar.style.width = `${scan.progress}%`;

        const text = document.getElementById('scan-progress-text');
        if (text) text.textContent = scan.current_stage || 'Processing...';

        const stages = document.querySelectorAll('.stage');
        const stageMap = {
            'Queued in background worker': 0,
            'Queued locally': 0,
            'Normalizing identity': 0,
            'Running discovery': 1,
            'Processing discovered profiles': 1,
            'Scoring and storing discoveries': 1,
            'Scraping discovered pages': 2,
            'Extracting entities': 3,
            'Extracting entities & metadata': 3,
            'Building identity graph': 4,
            'Generating risk report': 5,
            'Scan complete': 5,
        };

        const currentStageIndex = stageMap[scan.current_stage] ?? -1;
        stages.forEach((stage, index) => {
            stage.classList.remove('active', 'completed');
            if (index < currentStageIndex) {
                stage.classList.add('completed');
            } else if (index === currentStageIndex) {
                stage.classList.add('active');
            }
        });

        if (scan.status === 'completed') {
            stages.forEach((stage) => {
                stage.classList.remove('active');
                stage.classList.add('completed');
            });
        }

        if (scan.platforms_found > 0) {
            const liveResults = document.getElementById('scan-live-results');
            if (liveResults && !liveResults.querySelector(`[data-count="${scan.platforms_found}"]`)) {
                const item = document.createElement('div');
                item.className = 'live-result-item';
                item.dataset.count = scan.platforms_found;
                item.innerHTML = `
                    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M20 6L9 17l-5-5"/></svg>
                    <span>${scan.platforms_found} platform(s) discovered</span>
                `;
                liveResults.appendChild(item);
            }
        }
    },

    reset() {
        if (this.pollInterval) {
            clearInterval(this.pollInterval);
            this.pollInterval = null;
        }
        this.currentScanId = null;

        const card = document.getElementById('scan-progress-card');
        if (card) card.style.display = 'none';

        const bar = document.getElementById('scan-progress-bar');
        if (bar) bar.style.width = '0%';

        const text = document.getElementById('scan-progress-text');
        if (text) text.textContent = 'Waiting to start...';

        const liveResults = document.getElementById('scan-live-results');
        if (liveResults) liveResults.innerHTML = '';

        // Clear multi-tag inputs
        this.clearTags('username-tag-wrapper');
        this.clearTags('phone-tag-wrapper');

        // Clear address
        const addressInput = document.getElementById('scan-address');
        if (addressInput) addressInput.value = '';

        const selfAttested = document.getElementById('scan-self-attested');
        if (selfAttested) selfAttested.checked = false;

        this.clearError();
        this.prefillOwnedIdentity();

        document.querySelectorAll('.stage').forEach((stage) => stage.classList.remove('active', 'completed'));
    },
};
