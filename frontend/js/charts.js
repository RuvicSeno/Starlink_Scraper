/**
 * Chart.js configurations for the Starlink dashboard.
 * Creates and manages daily usage line chart and monthly comparison bar chart.
 */

const ChartManager = {
    dailyChart: null,
    monthlyChart: null,

    /** Shared dark-theme defaults for all charts */
    defaults() {
        Chart.defaults.color = '#94A3B8';
        Chart.defaults.borderColor = 'rgba(255,255,255,0.04)';
        Chart.defaults.font.family = "'Inter', sans-serif";
        Chart.defaults.font.size = 12;
        Chart.defaults.plugins.tooltip.backgroundColor = 'rgba(11,15,25,0.95)';
        Chart.defaults.plugins.tooltip.borderColor = 'rgba(255,255,255,0.1)';
        Chart.defaults.plugins.tooltip.borderWidth = 1;
        Chart.defaults.plugins.tooltip.cornerRadius = 8;
        Chart.defaults.plugins.tooltip.padding = 12;
        Chart.defaults.plugins.tooltip.titleFont = { weight: '600', size: 13 };
        Chart.defaults.plugins.tooltip.bodyFont = { size: 12 };
        Chart.defaults.plugins.legend.labels.usePointStyle = true;
        Chart.defaults.plugins.legend.labels.pointStyleWidth = 10;
        Chart.defaults.plugins.legend.labels.padding = 20;
    },

    /** Create the daily usage line chart */
    createDailyChart(canvasId, data) {
        const ctx = document.getElementById(canvasId);
        if (!ctx) return;
        if (this.dailyChart) this.dailyChart.destroy();

        const labels = data.map(d => {
            const dt = new Date(d.date);
            return dt.toLocaleDateString('en-US', { month: 'short', day: 'numeric' });
        });

        // Gradient fill
        const residentialGrad = ctx.getContext('2d').createLinearGradient(0, 0, 0, 300);
        residentialGrad.addColorStop(0, 'rgba(79,175,255,0.25)');
        residentialGrad.addColorStop(1, 'rgba(79,175,255,0.01)');

        this.dailyChart = new Chart(ctx, {
            type: 'line',
            data: {
                labels,
                datasets: [
                    {
                        label: 'Residential Data',
                        data: data.map(d => d.residential_gb ?? 0),
                        borderColor: '#4FAFFF',
                        backgroundColor: residentialGrad,
                        fill: true,
                        tension: 0.35,
                        borderWidth: 2,
                        pointRadius: 2,
                        pointHoverRadius: 6,
                        pointBackgroundColor: '#4FAFFF',
                        pointHoverBackgroundColor: '#fff',
                        pointHoverBorderColor: '#4FAFFF',
                        pointHoverBorderWidth: 2,
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                interaction: { mode: 'index', intersect: false },
                scales: {
                    x: {
                        grid: { display: false },
                        ticks: { maxTicksLimit: 15, maxRotation: 0 }
                    },
                    y: {
                        beginAtZero: true,
                        grid: { color: 'rgba(255,255,255,0.04)' },
                        ticks: {
                            callback: v => v.toFixed(1) + ' GB'
                        }
                    }
                },
                plugins: {
                    tooltip: {
                        callbacks: {
                            title: (items) => {
                                const idx = items[0].dataIndex;
                                return data[idx].date;
                            },
                            label: (item) => ` ${item.dataset.label}: ${item.raw.toFixed(3)} GB`
                        }
                    }
                }
            }
        });
    },

    /** Create the monthly comparison bar chart */
    createMonthlyChart(canvasId, data) {
        const ctx = document.getElementById(canvasId);
        if (!ctx) return;
        if (this.monthlyChart) this.monthlyChart.destroy();

        const labels = data.map(d => {
            const [y, m] = d.month.split('-');
            const dt = new Date(parseInt(y), parseInt(m) - 1);
            return dt.toLocaleDateString('en-US', { month: 'short', year: 'numeric' });
        });

        this.monthlyChart = new Chart(ctx, {
            type: 'bar',
            data: {
                labels,
                datasets: [
                    {
                        label: 'Residential Data',
                        data: data.map(d => d.residential_gb ?? 0),
                        backgroundColor: 'rgba(79,175,255,0.7)',
                        hoverBackgroundColor: 'rgba(79,175,255,0.9)',
                        borderRadius: 4,
                        borderSkipped: false,
                    }
                ]
            },
            options: {
                responsive: true,
                maintainAspectRatio: false,
                interaction: { mode: 'index', intersect: false },
                scales: {
                    x: {
                        grid: { display: false },
                    },
                    y: {
                        beginAtZero: true,
                        grid: { color: 'rgba(255,255,255,0.04)' },
                        ticks: { callback: v => v.toFixed(0) + ' GB' }
                    }
                },
                plugins: {
                    tooltip: {
                        callbacks: {
                            label: (item) => ` ${item.dataset.label}: ${item.raw.toFixed(2)} GB`
                        }
                    }
                }
            }
        });
    },

    /** Destroy all charts for cleanup */
    destroyAll() {
        if (this.dailyChart) { this.dailyChart.destroy(); this.dailyChart = null; }
        if (this.monthlyChart) { this.monthlyChart.destroy(); this.monthlyChart = null; }
    }
};
