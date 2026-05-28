/**
 * Main Application Module
 * Orchestrates dashboard initialization, data loading, scraping controls,
 * and UI state management.
 */

const App = {
    statusPollInterval: null,
    currentMonth: null,

    /** Initialize the dashboard */
    async init() {
        ChartManager.defaults();
        this.bindControls();
        await this.loadDashboard();
    },

    /** Bind button and control event listeners */
    bindControls() {
        // Scraping controls
        const startBtn = document.getElementById('btn-start-scrape');
        const stopBtn = document.getElementById('btn-stop-scrape');
        const refreshBtn = document.getElementById('btn-refresh');
        const exportBtn = document.getElementById('btn-export');
        const monthSelect = document.getElementById('month-select');

        if (startBtn) startBtn.addEventListener('click', () => this.startScraping());
        if (stopBtn) stopBtn.addEventListener('click', () => this.stopScraping());
        if (refreshBtn) refreshBtn.addEventListener('click', () => this.loadDashboard());
        if (exportBtn) exportBtn.addEventListener('click', () => this.exportCSV());
        if (monthSelect) monthSelect.addEventListener('change', (e) => this.onMonthChange(e.target.value));

        // Table sort headers
        document.querySelectorAll('.data-table th[data-col]').forEach(th => {
            th.addEventListener('click', () => DataTable.handleSort(th.dataset.col));
        });
    },

    /** Load all dashboard data */
    async loadDashboard() {
        this.showLoading(true);
        try {
            const [summaryRes, monthlyRes, allRes, monthsRes] = await Promise.all([
                API.getSummary(),
                API.getMonthlyUsage(),
                API.getAllUsage(),
                API.getAvailableMonths()
            ]);

            // Populate overview cards
            if (summaryRes.status === 'ok') {
                const monthlyData = (monthlyRes.status === 'ok' && Array.isArray(monthlyRes.data))
                    ? monthlyRes.data
                    : [];
                this.updateOverviewCards(summaryRes.data, monthlyData);
            }

            // Populate month selector
            if (monthsRes.status === 'ok') {
                this.populateMonthSelector(monthsRes.data, summaryRes?.available_months);
            }

            // Render charts
            if (monthlyRes.status === 'ok' && monthlyRes.data.length > 0) {
                ChartManager.createMonthlyChart('monthly-chart', monthlyRes.data);
            }

            // Daily chart — use latest month or all data
            if (allRes.status === 'ok' && allRes.data.length > 0) {
                const latestMonth = summaryRes?.data?.latest_month;
                const dailyData = latestMonth
                    ? allRes.data.filter(d => d.month === latestMonth)
                    : allRes.data.slice(-31);
                ChartManager.createDailyChart('daily-chart', dailyData);
                this.currentMonth = latestMonth;

                // Update month select to match
                const sel = document.getElementById('month-select');
                if (sel && latestMonth) sel.value = latestMonth;
            }

            // Render table
            if (allRes.status === 'ok') {
                DataTable.init(allRes.data);
            }

            // Update scrape status
            await this.updateScrapeStatus();

        } catch (err) {
            console.error('Failed to load dashboard:', err);
            this.showToast('Failed to load dashboard data.', 'error');
        } finally {
            this.showLoading(false);
        }
    },

    /** Update the four overview statistic cards */
    updateOverviewCards(summary, monthlyData = []) {
        if (!summary) return;

        const monthlyResidentialTotal = monthlyData.reduce(
            (acc, row) => acc + Number(row.residential_gb ?? 0),
            0
        );
        const summaryResidential = Number(summary.total_residential_gb ?? 0);
        const finalResidentialTotal = monthlyResidentialTotal > 0 ? monthlyResidentialTotal : summaryResidential;
        console.log('[usage-debug] monthly residential values:', monthlyData.map(r => ({
            month: r.month,
            residential_gb: r.residential_gb
        })));
        console.log('[usage-debug] total residential aggregation:', {
            monthlyResidentialTotal,
            summaryResidential,
            finalResidentialTotal
        });

        this.setCardValue('card-residential', finalResidentialTotal, 'GB');
        this.setCardValue('card-peak', summary.peak_residential_gb, 'GB');

        // Update detail text
        const residentialDetail = document.getElementById('card-residential-detail');
        const peakDetail = document.getElementById('card-peak-detail');

        if (residentialDetail) residentialDetail.textContent = `Across ${summary.total_days} days`;
        if (peakDetail) peakDetail.textContent = summary.peak_day
            ? `Peak day: ${new Date(summary.peak_day).toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })}`
            : 'No data yet';
    },

    /** Set a card's numeric value with animation */
    setCardValue(cardId, value, unit) {
        const el = document.getElementById(cardId);
        if (!el) return;
        const num = value ? parseFloat(value).toFixed(2) : '0.00';
        el.innerHTML = `${num}<span class="card-unit">${unit}</span>`;
    },

    /** Populate the month filter dropdown */
    populateMonthSelector(months) {
        const sel = document.getElementById('month-select');
        if (!sel) return;
        sel.innerHTML = '<option value="">All Months</option>';
        if (months && months.length > 0) {
            // Show newest first in dropdown
            [...months].reverse().forEach(m => {
                const [y, mo] = m.split('-');
                const dt = new Date(parseInt(y), parseInt(mo) - 1);
                const label = dt.toLocaleDateString('en-US', { month: 'long', year: 'numeric' });
                sel.innerHTML += `<option value="${m}">${label}</option>`;
            });
        }
    },

    /** Handle month selection change */
    async onMonthChange(month) {
        this.currentMonth = month || null;
        try {
            const res = month
                ? await API.getDailyUsage(month)
                : await API.getAllUsage();

            if (res.status === 'ok' && res.data.length > 0) {
                ChartManager.createDailyChart('daily-chart', res.data);
                DataTable.init(res.data);
            }
        } catch (err) {
            this.showToast('Failed to load month data.', 'error');
        }
    },

    /** Start a scraping job */
    async startScraping() {
        try {
            const btn = document.getElementById('btn-start-scrape');
            if (btn) { btn.disabled = true; btn.innerHTML = '<span class="spinner"></span> Starting...'; }

            const res = await API.startScraping();
            if (res.status === 'ok') {
                this.showToast(res.message, 'info');
                this.startStatusPolling();
            } else {
                this.showToast(res.message || 'Failed to start scraping.', 'error');
                if (btn) { btn.disabled = false; btn.innerHTML = '🛰️ Start Scraping'; }
            }
        } catch (err) {
            this.showToast('Failed to start scraping: ' + err.message, 'error');
            const btn = document.getElementById('btn-start-scrape');
            if (btn) { btn.disabled = false; btn.innerHTML = '🛰️ Start Scraping'; }
        }
    },

    /** Stop a running scraping job */
    async stopScraping() {
        try {
            const res = await API.stopScraping();
            this.showToast(res.message || 'Stop requested.', 'warning');
        } catch (err) {
            this.showToast('Failed to stop scraping.', 'error');
        }
    },

    /** Poll scrape status every 2 seconds while running */
    startStatusPolling() {
        this.stopStatusPolling();
        this.statusPollInterval = setInterval(() => this.updateScrapeStatus(), 2000);
    },

    stopStatusPolling() {
        if (this.statusPollInterval) {
            clearInterval(this.statusPollInterval);
            this.statusPollInterval = null;
        }
    },

    /** Fetch and display current scrape status */
    async updateScrapeStatus() {
        try {
            const res = await API.getScrapeStatus();
            if (res.status !== 'ok') return;

            const s = res.data;
            const badge = document.getElementById('status-badge');
            const statusText = document.getElementById('status-text');
            const progress = document.getElementById('scrape-progress');
            const startBtn = document.getElementById('btn-start-scrape');
            const stopBtn = document.getElementById('btn-stop-scrape');

            if (badge) badge.dataset.status = s.status;
            if (statusText) statusText.textContent = this.capitalise(s.status);
            if (progress) progress.textContent = s.progress || '';

            const isRunning = s.status === 'running';
            if (startBtn) {
                startBtn.disabled = isRunning;
                startBtn.innerHTML = isRunning ? '<span class="spinner"></span> Scraping...' : '🛰️ Start Scraping';
            }
            if (stopBtn) stopBtn.style.display = isRunning ? 'inline-flex' : 'none';

            // Stop polling when finished
            if (!isRunning && this.statusPollInterval) {
                this.stopStatusPolling();
                if (s.status === 'completed') {
                    this.showToast(`Scraping complete! ${s.records_saved} records saved.`, 'success');
                    await this.loadDashboard();
                } else if (s.status === 'error') {
                    this.showToast(`Scraping error: ${s.error || 'Unknown error'}`, 'error');
                } else if (s.status === 'auth_required') {
                    this.showToast('Login required. Re-run scraping to open the login window.', 'warning');
                }
            }
        } catch (err) {
            // Silently ignore status poll errors
        }
    },

    /** Trigger CSV download */
    exportCSV() {
        const url = API.getExportURL();
        const a = document.createElement('a');
        a.href = url;
        a.download = 'starlink_usage_data.csv';
        document.body.appendChild(a);
        a.click();
        document.body.removeChild(a);
        this.showToast('CSV download started.', 'success');
    },

    /** Show/hide loading skeletons */
    showLoading(show) {
        document.querySelectorAll('.skeleton-wrap').forEach(el => {
            el.style.display = show ? 'block' : 'none';
        });
        document.querySelectorAll('.data-content').forEach(el => {
            el.style.display = show ? 'none' : 'block';
        });
    },

    /** Display a toast notification */
    showToast(message, type = 'info') {
        const container = document.getElementById('toast-container');
        if (!container) return;

        const toast = document.createElement('div');
        toast.className = `toast ${type}`;
        toast.innerHTML = `<span>${message}</span>`;
        container.appendChild(toast);

        setTimeout(() => {
            toast.classList.add('toast-out');
            setTimeout(() => toast.remove(), 300);
        }, 4000);
    },

    capitalise(str) {
        if (!str) return '';
        return str.charAt(0).toUpperCase() + str.slice(1);
    }
};

// ── Boot ──
document.addEventListener('DOMContentLoaded', () => App.init());
