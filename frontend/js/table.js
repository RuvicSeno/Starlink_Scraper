/**
 * Data Table Module
 * Renders a searchable, sortable, paginated table of usage records.
 */

const DataTable = {
    data: [],
    filtered: [],
    sortCol: 'date',
    sortAsc: false,
    page: 1,
    perPage: 25,
    searchTerm: '',

    /** Initialize the table with data */
    init(records) {
        this.data = records || [];
        this.filtered = [...this.data];
        this.page = 1;
        this.sort(this.sortCol, this.sortAsc);
        this.render();
        this.bindEvents();
    },

    /** Bind search input and other events */
    bindEvents() {
        const input = document.getElementById('table-search');
        if (input) {
            input.addEventListener('input', (e) => {
                this.searchTerm = e.target.value.toLowerCase().trim();
                this.applyFilter();
            });
        }
    },

    /** Apply search filter */
    applyFilter() {
        if (!this.searchTerm) {
            this.filtered = [...this.data];
        } else {
            this.filtered = this.data.filter(r =>
                r.date.includes(this.searchTerm) ||
                r.month.includes(this.searchTerm) ||
                String(r.residential_gb).includes(this.searchTerm)
            );
        }
        this.page = 1;
        this.sort(this.sortCol, this.sortAsc);
        this.render();
    },

    /** Sort data by column */
    sort(col, asc) {
        this.sortCol = col;
        this.sortAsc = asc;
        this.filtered.sort((a, b) => {
            let va = a[col], vb = b[col];
            if (typeof va === 'string') {
                return asc ? va.localeCompare(vb) : vb.localeCompare(va);
            }
            return asc ? va - vb : vb - va;
        });
    },

    /** Render the table */
    render() {
        const tbody = document.getElementById('table-body');
        const meta = document.getElementById('table-meta');
        if (!tbody) return;

        // Calculate pagination
        const total = this.filtered.length;
        const totalPages = Math.max(1, Math.ceil(total / this.perPage));
        if (this.page > totalPages) this.page = totalPages;
        const start = (this.page - 1) * this.perPage;
        const end = Math.min(start + this.perPage, total);
        const pageData = this.filtered.slice(start, end);

        // Render rows
        if (pageData.length === 0) {
            tbody.innerHTML = `
                <tr><td colspan="3" class="empty-state" style="padding:40px">
                    <div class="empty-state-icon">📊</div>
                    <div class="empty-state-title">No data available</div>
                    <div class="empty-state-text">Start scraping to populate the table.</div>
                </td></tr>`;
        } else {
            tbody.innerHTML = pageData.map(r => `
                <tr>
                    <td>${this.formatDate(r.date)}</td>
                    <td class="val-download">${(r.residential_gb ?? 0).toFixed(3)}</td>
                    <td>${r.month}</td>
                </tr>
            `).join('');
        }

        // Update meta info
        if (meta) {
            meta.textContent = total > 0
                ? `Showing ${start + 1}–${end} of ${total} records`
                : 'No records';
        }

        // Render pagination
        this.renderPagination(totalPages);
        this.updateSortIndicators();
    },

    /** Render pagination buttons */
    renderPagination(totalPages) {
        const container = document.getElementById('pagination-controls');
        if (!container) return;

        let html = '';
        html += `<button class="pagination-btn" data-page="prev" ${this.page <= 1 ? 'disabled' : ''}>‹</button>`;

        const maxVisible = 5;
        let startPage = Math.max(1, this.page - Math.floor(maxVisible / 2));
        let endPage = Math.min(totalPages, startPage + maxVisible - 1);
        if (endPage - startPage < maxVisible - 1) {
            startPage = Math.max(1, endPage - maxVisible + 1);
        }

        if (startPage > 1) {
            html += `<button class="pagination-btn" data-page="1">1</button>`;
            if (startPage > 2) html += `<span style="color:var(--text-muted);padding:0 4px">…</span>`;
        }

        for (let i = startPage; i <= endPage; i++) {
            html += `<button class="pagination-btn${i === this.page ? ' active' : ''}" data-page="${i}">${i}</button>`;
        }

        if (endPage < totalPages) {
            if (endPage < totalPages - 1) html += `<span style="color:var(--text-muted);padding:0 4px">…</span>`;
            html += `<button class="pagination-btn" data-page="${totalPages}">${totalPages}</button>`;
        }

        html += `<button class="pagination-btn" data-page="next" ${this.page >= totalPages ? 'disabled' : ''}>›</button>`;
        container.innerHTML = html;

        // Bind pagination clicks
        container.querySelectorAll('.pagination-btn').forEach(btn => {
            btn.addEventListener('click', () => {
                const p = btn.dataset.page;
                if (p === 'prev') this.page = Math.max(1, this.page - 1);
                else if (p === 'next') this.page++;
                else this.page = parseInt(p);
                this.render();
            });
        });
    },

    /** Update column header sort indicators */
    updateSortIndicators() {
        document.querySelectorAll('.data-table th[data-col]').forEach(th => {
            const col = th.dataset.col;
            const icon = th.querySelector('.sort-icon');
            th.classList.toggle('sorted', col === this.sortCol);
            if (icon) {
                icon.textContent = col === this.sortCol ? (this.sortAsc ? '▲' : '▼') : '▲';
            }
        });
    },

    /** Handle column header click for sorting */
    handleSort(col) {
        if (this.sortCol === col) {
            this.sortAsc = !this.sortAsc;
        } else {
            this.sortCol = col;
            this.sortAsc = col === 'date'; // Default ascending for date
        }
        this.sort(this.sortCol, this.sortAsc);
        this.page = 1;
        this.render();
    },

    /** Format date string for display */
    formatDate(dateStr) {
        const dt = new Date(dateStr);
        return dt.toLocaleDateString('en-US', {
            year: 'numeric', month: 'short', day: 'numeric'
        });
    }
};
