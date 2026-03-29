/**
 * Auth Module - Login, register, DigiLocker, and secure session UI logic.
 */
const Auth = {
    authCheckPromise: null,

    init() {
        this.bindEvents();
    },

    bindEvents() {
        const loginForm = document.getElementById('login-form');
        if (loginForm) {
            loginForm.addEventListener('submit', (event) => {
                event.preventDefault();
                this.handleLogin();
            });
        }

        const registerForm = document.getElementById('register-form');
        if (registerForm) {
            registerForm.addEventListener('submit', (event) => {
                event.preventDefault();
                this.handleRegister();
            });
        }

        const showRegister = document.getElementById('show-register');
        if (showRegister) {
            showRegister.addEventListener('click', (event) => {
                event.preventDefault();
                document.getElementById('login-form').style.display = 'none';
                document.getElementById('register-form').style.display = 'block';
            });
        }

        const showLogin = document.getElementById('show-login');
        if (showLogin) {
            showLogin.addEventListener('click', (event) => {
                event.preventDefault();
                document.getElementById('register-form').style.display = 'none';
                document.getElementById('login-form').style.display = 'block';
            });
        }

        document.querySelectorAll('[data-oauth-provider]').forEach((button) => {
            button.addEventListener('click', () => {
                this.handleOAuth(button.dataset.oauthProvider);
            });
        });

        const btnLogout = document.getElementById('btn-logout');
        if (btnLogout) {
            btnLogout.addEventListener('click', () => this.logout());
        }
    },

    async handleLogin() {
        const email = document.getElementById('login-email').value.trim();
        const password = document.getElementById('login-password').value;
        const errorEl = document.getElementById('login-error');
        const btn = document.getElementById('btn-login');

        errorEl.textContent = '';
        btn.disabled = true;
        btn.querySelector('span').textContent = 'Signing in...';

        try {
            const data = await API.login(email, password);
            this.updateUserUI(data.user);
            window.location.hash = '#/dashboard';
        } catch (error) {
            errorEl.textContent = error.error || 'Login failed. Please try again.';
        } finally {
            btn.disabled = false;
            btn.querySelector('span').textContent = 'Sign In';
        }
    },

    async handleRegister() {
        const fullName = document.getElementById('register-name').value.trim();
        const email = document.getElementById('register-email').value.trim();
        const password = document.getElementById('register-password').value;
        const errorEl = document.getElementById('register-error');
        const btn = document.getElementById('btn-register');

        errorEl.textContent = '';
        btn.disabled = true;
        btn.querySelector('span').textContent = 'Creating account...';

        try {
            const data = await API.register(fullName, email, password);
            this.updateUserUI(data.user);
            window.location.hash = '#/dashboard';
        } catch (error) {
            errorEl.textContent = error.error || 'Registration failed. Please try again.';
        } finally {
            btn.disabled = false;
            btn.querySelector('span').textContent = 'Create Account';
        }
    },

    async handleOAuth(provider) {
        const providers = {
            google: {
                label: 'Google',
                status: () => API.getGoogleStatus(),
                init: () => API.initGoogle(),
                popupName: 'google-auth',
            },
            digilocker: {
                label: 'DigiLocker',
                status: () => API.getDigiLockerStatus(),
                init: () => API.initDigiLocker(),
                popupName: 'digilocker-auth',
            },
        };
        const selectedProvider = providers[provider];

        if (!selectedProvider) {
            return;
        }

        try {
            const status = await selectedProvider.status();
            if (!status.available) {
                alert(status.message || `${selectedProvider.label} integration is not configured.`);
                return;
            }

            const data = await selectedProvider.init();
            if (!data.auth_url) {
                return;
            }

            const popup = window.open(data.auth_url, selectedProvider.popupName, 'width=600,height=700');
            if (!popup) {
                alert('Popup blocked. Please allow popups and try again.');
                return;
            }

            const poll = window.setInterval(async () => {
                if (popup.closed) {
                    window.clearInterval(poll);
                    return;
                }

                try {
                    const user = await API.hydrateUser();
                    window.clearInterval(poll);
                    popup.close();
                    this.updateUserUI(user);
                    Toast.show(`Signed in with ${selectedProvider.label}`, 'success');
                    window.location.hash = '#/dashboard';
                } catch (error) {
                    // Wait until the OAuth flow completes and the browser receives auth cookies.
                }
            }, 1200);
        } catch (error) {
            alert(`Failed to initiate ${selectedProvider.label} authentication. ` + (error.error || error.message || ''));
        }
    },

    updateUserUI(user) {
        const nameEl = document.getElementById('user-name');
        const roleEl = document.getElementById('user-role');
        const avatarEl = document.getElementById('user-avatar');

        if (nameEl) nameEl.textContent = user?.full_name || 'User';
        if (roleEl) roleEl.textContent = user?.role || 'Secure Session';
        if (avatarEl) avatarEl.textContent = (user?.full_name || 'U').charAt(0).toUpperCase();
    },

    async logout() {
        try {
            await API.logout();
        } catch (error) {
            // Clear the browser session locally even if the server session already expired.
        }

        this.authCheckPromise = null;
        this.updateUserUI(null);
        window.location.hash = '#/login';
    },

    async checkAuth(forceRefresh = false) {
        const cachedUser = API.getUser();
        if (cachedUser && !forceRefresh) {
            this.updateUserUI(cachedUser);
            return true;
        }

        if (!this.authCheckPromise || forceRefresh) {
            this.authCheckPromise = API.hydrateUser()
                .then((user) => {
                    this.updateUserUI(user);
                    return true;
                })
                .catch(() => {
                    API.clearSession();
                    this.updateUserUI(null);
                    return false;
                })
                .finally(() => {
                    this.authCheckPromise = null;
                });
        }

        return this.authCheckPromise;
    },
};
