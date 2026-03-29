/**
 * API Client - Fetch wrapper with cookie-based auth and CSRF protection.
 */
const API = {
    BASE_URL: window.location.origin,
    USER_STORAGE_KEY: 'dfas_user',

    getCookie(name) {
        const cookie = document.cookie
            .split('; ')
            .find((entry) => entry.startsWith(`${name}=`));
        return cookie ? decodeURIComponent(cookie.split('=').slice(1).join('=')) : '';
    },

    getCsrfToken() {
        return this.getCookie('csrf_access_token');
    },

    clearSession() {
        sessionStorage.removeItem(this.USER_STORAGE_KEY);
    },

    getUser() {
        const user = sessionStorage.getItem(this.USER_STORAGE_KEY);
        return user ? JSON.parse(user) : null;
    },

    setUser(user) {
        if (!user) {
            this.clearSession();
            return;
        }
        sessionStorage.setItem(this.USER_STORAGE_KEY, JSON.stringify(user));
    },

    isAuthenticated() {
        return !!this.getUser();
    },

    async request(endpoint, options = {}) {
        const url = `${this.BASE_URL}${endpoint}`;
        const method = (options.method || 'GET').toUpperCase();
        const headers = {
            ...options.headers,
        };

        if (!(options.body instanceof FormData) && !headers['Content-Type']) {
            headers['Content-Type'] = 'application/json';
        }

        if (!['GET', 'HEAD', 'OPTIONS'].includes(method)) {
            const csrfToken = this.getCsrfToken();
            if (csrfToken) {
                headers['X-CSRF-TOKEN'] = csrfToken;
            }
        }

        try {
            const response = await fetch(url, {
                ...options,
                headers,
                credentials: 'same-origin',
            });

            const contentType = response.headers.get('content-type') || '';
            const data = contentType.includes('application/json')
                ? await response.json()
                : await response.text();

            if (!response.ok) {
                const onPublicAuthPage = ['#/login', '#/register'].includes(window.location.hash || '#/login');
                if (
                    response.status === 401 &&
                    !endpoint.includes('/auth/login') &&
                    !endpoint.includes('/auth/register') &&
                    !onPublicAuthPage
                ) {
                    this.clearSession();
                    if (window.location.hash !== '#/login') {
                        window.location.hash = '#/login';
                    }
                }

                if (typeof data === 'string') {
                    throw { status: response.status, error: data || 'Request failed' };
                }

                throw { status: response.status, ...data };
            }

            return data;
        } catch (error) {
            if (error instanceof TypeError) {
                throw { status: 0, error: 'Network error. Is the server running?' };
            }
            throw error;
        }
    },

    async login(email, password) {
        const data = await this.request('/api/auth/login', {
            method: 'POST',
            body: JSON.stringify({ email, password }),
        });
        this.setUser(data.user);
        return data;
    },

    async register(fullName, email, password) {
        const data = await this.request('/api/auth/register', {
            method: 'POST',
            body: JSON.stringify({ full_name: fullName, email, password }),
        });
        this.setUser(data.user);
        return data;
    },

    async getMe() {
        return this.request('/api/auth/me');
    },

    async hydrateUser() {
        const data = await this.getMe();
        this.setUser(data.user);
        return data.user;
    },

    async logout() {
        try {
            return await this.request('/api/auth/logout', {
                method: 'POST',
            });
        } finally {
            this.clearSession();
        }
    },

    async getDigiLockerStatus() {
        return this.request('/api/auth/digilocker/status');
    },

    async initDigiLocker() {
        return this.request('/api/auth/digilocker/init');
    },

    async getGoogleStatus() {
        return this.request('/api/auth/google/status');
    },

    async initGoogle() {
        return this.request('/api/auth/google/init');
    },

    async startQuickScan(data) {
        return this.request('/api/scan/quick', {
            method: 'POST',
            body: JSON.stringify(data),
        });
    },

    async startFullScan(data) {
        return this.request('/api/scan/full', {
            method: 'POST',
            body: JSON.stringify(data),
        });
    },

    async getScanStatus(scanId) {
        return this.request(`/api/scan/${scanId}/status`);
    },

    async getScanResults(scanId) {
        return this.request(`/api/scan/${scanId}/results`);
    },

    async getHistory() {
        return this.request('/api/results/history');
    },

    async getGraph(scanId) {
        return this.request(`/api/results/${scanId}/graph`);
    },

    async getReport(scanId) {
        return this.request(`/api/results/${scanId}/report`);
    },

    async getDashboardStats() {
        return this.request('/api/dashboard/stats');
    },

    async getPlatformCatalog() {
        return this.request('/api/catalog/platforms');
    },

    async savePlatformCatalog(catalog) {
        return this.request('/api/catalog/platforms', {
            method: 'PUT',
            body: JSON.stringify({ catalog }),
        });
    },
};
