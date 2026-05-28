/**
 * API Client Module
 * Handles all communication with the FastAPI backend.
 */

const API = {
    BASE: '',

    /**
     * Generic fetch wrapper with error handling.
     */
    async request(endpoint, options = {}) {
        try {
            const response = await fetch(`${this.BASE}${endpoint}`, {
                headers: { 'Content-Type': 'application/json', ...options.headers },
                ...options
            });
            if (!response.ok) {
                throw new Error(`HTTP ${response.status}: ${response.statusText}`);
            }
            const contentType = response.headers.get('content-type');
            if (contentType && contentType.includes('application/json')) {
                return await response.json();
            }
            return response;
        } catch (err) {
            console.error(`API Error [${endpoint}]:`, err);
            throw err;
        }
    },

    // ── Data Endpoints ──

    async getDailyUsage(month = null) {
        const params = month ? `?month=${month}` : '';
        return this.request(`/api/usage/daily${params}`);
    },

    async getMonthlyUsage() {
        return this.request('/api/usage/monthly');
    },

    async getAllUsage() {
        return this.request('/api/usage/all');
    },

    async getSummary() {
        return this.request('/api/usage/summary');
    },

    async getAvailableMonths() {
        return this.request('/api/usage/months');
    },

    // ── Scraper Endpoints ──

    async startScraping() {
        return this.request('/api/scrape/start', { method: 'POST' });
    },

    async getScrapeStatus() {
        return this.request('/api/scrape/status');
    },

    async stopScraping() {
        return this.request('/api/scrape/stop', { method: 'POST' });
    },

    async getScrapeHistory() {
        return this.request('/api/scrape/history');
    },

    // ── Export ──

    getExportURL() {
        return `${this.BASE}/api/export/csv`;
    }
};
