/**
 * Library Book Usage Analysis System
 * Interactive Charts & UI Behaviors (Chart.js 4.x / 3.x compatible)
 */

document.addEventListener('DOMContentLoaded', function () {
    // -----------------------------------------------------------
    // Mobile Sidebar Toggle
    // -----------------------------------------------------------
    const sidebarToggler = document.getElementById('sidebarToggler');
    const sidebar = document.querySelector('.app-sidebar');
    if (sidebarToggler && sidebar) {
        sidebarToggler.addEventListener('click', function () {
            sidebar.classList.toggle('show');
        });
    }

    // -----------------------------------------------------------
    // Auto-dismiss Alerts after 5 seconds
    // -----------------------------------------------------------
    const alerts = document.querySelectorAll('.alert-dismissible');
    alerts.forEach(function (alert) {
        setTimeout(function () {
            try {
                const bsAlert = new bootstrap.Alert(alert);
                bsAlert.close();
            } catch (e) {}
        }, 5000);
    });

    // -----------------------------------------------------------
    // Initialize Dashboard Charts if on Dashboard
    // -----------------------------------------------------------
    if (document.getElementById('monthlyTrendsChart')) {
        initDashboardCharts();
    }

    // -----------------------------------------------------------
    // Client-side quick filter on data tables
    // -----------------------------------------------------------
    const clientSearchInputs = document.querySelectorAll('[data-table-filter]');
    clientSearchInputs.forEach(input => {
        const targetTableId = input.getAttribute('data-table-filter');
        const targetTable = document.getElementById(targetTableId);
        if (targetTable) {
            input.addEventListener('input', function () {
                const query = this.value.toLowerCase().trim();
                const rows = targetTable.querySelectorAll('tbody tr');
                rows.forEach(row => {
                    const text = row.innerText.toLowerCase();
                    row.style.display = text.includes(query) ? '' : 'none';
                });
            });
        }
    });

    // -----------------------------------------------------------
    // Issue Book Date auto-calculation helper
    // -----------------------------------------------------------
    const issueDateInput = document.getElementById('issue_date');
    const dueDateDisplay = document.getElementById('due_date_display');
    const periodDaysInput = document.getElementById('borrowing_period_days');

    if (issueDateInput && dueDateDisplay) {
        function updateDueDate() {
            const period = parseInt(periodDaysInput ? periodDaysInput.value : 14, 10) || 14;
            const issueVal = issueDateInput.value;
            if (issueVal) {
                const parts = issueVal.split('-');
                if (parts.length === 3) {
                    const issueDate = new Date(parseInt(parts[0]), parseInt(parts[1]) - 1, parseInt(parts[2]));
                    issueDate.setDate(issueDate.getDate() + period);
                    const yyyy = issueDate.getFullYear();
                    const mm = String(issueDate.getMonth() + 1).padStart(2, '0');
                    const dd = String(issueDate.getDate()).padStart(2, '0');
                    dueDateDisplay.value = `${yyyy}-${mm}-${dd}`;
                }
            }
        }
        issueDateInput.addEventListener('change', updateDueDate);
    }
});

/**
 * Initializes the 4 dashboard Chart.js charts by fetching API data.
 */
function initDashboardCharts() {
    fetch('/api/dashboard-charts')
        .then(response => response.json())
        .then(data => {
            renderMonthlyChart(data.monthly_trends);
            renderMostBorrowedChart(data.most_borrowed);
            renderCategoryChart(data.category_distribution);
            renderLoanStatusChart(data.loan_status);
        })
        .catch(err => {
            console.error('Failed to load dashboard charts data:', err);
        });
}

function renderMonthlyChart(trends) {
    const ctx = document.getElementById('monthlyTrendsChart');
    if (!ctx) return;

    new Chart(ctx, {
        type: 'line',
        data: {
            labels: trends.labels.length > 0 ? trends.labels : ['No Data'],
            datasets: [{
                label: 'Books Issued',
                data: trends.counts.length > 0 ? trends.counts : [0],
                borderColor: '#2563eb',
                backgroundColor: 'rgba(37, 99, 235, 0.1)',
                borderWidth: 2.8,
                fill: true,
                tension: 0.35,
                pointBackgroundColor: '#1d4ed8',
                pointBorderColor: '#ffffff',
                pointBorderWidth: 2,
                pointRadius: 5,
                pointHoverRadius: 7
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false },
                tooltip: {
                    backgroundColor: '#0f172a',
                    padding: 10,
                    cornerRadius: 8,
                    titleFont: { size: 12, weight: 'bold' },
                    bodyFont: { size: 12 }
                }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    ticks: { precision: 0, font: { size: 11 } },
                    grid: { color: '#f1f5f9' }
                },
                x: {
                    ticks: { font: { size: 11 } },
                    grid: { display: false }
                }
            }
        }
    });
}

function renderMostBorrowedChart(data) {
    const ctx = document.getElementById('mostBorrowedChart');
    if (!ctx) return;

    // Truncate labels for chart display
    const shortLabels = data.labels.map(l => l.length > 20 ? l.substring(0, 18) + '...' : l);

    new Chart(ctx, {
        type: 'bar',
        data: {
            labels: shortLabels.length > 0 ? shortLabels : ['No Data'],
            datasets: [{
                label: 'Borrow Count',
                data: data.counts.length > 0 ? data.counts : [0],
                backgroundColor: '#3b82f6',
                hoverBackgroundColor: '#1d4ed8',
                borderRadius: 6,
                barThickness: 24
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false },
                tooltip: {
                    backgroundColor: '#0f172a',
                    padding: 10,
                    cornerRadius: 8,
                    callbacks: {
                        title: function (context) {
                            const index = context[0].dataIndex;
                            return data.labels[index] || '';
                        }
                    }
                }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    ticks: { precision: 0, font: { size: 11 } },
                    grid: { color: '#f1f5f9' }
                },
                x: {
                    ticks: { font: { size: 10 }, maxRotation: 45, minRotation: 20 },
                    grid: { display: false }
                }
            }
        }
    });
}

function renderCategoryChart(data) {
    const ctx = document.getElementById('categoryPieChart');
    if (!ctx) return;

    const colors = [
        '#2563eb', '#06b6d4', '#10b981', '#f59e0b',
        '#6366f1', '#8b5cf6', '#ec4899', '#64748b'
    ];

    new Chart(ctx, {
        type: 'pie',
        data: {
            labels: data.labels.length > 0 ? data.labels : ['No Categories'],
            datasets: [{
                data: data.counts.length > 0 ? data.counts : [1],
                backgroundColor: colors.slice(0, Math.max(data.labels.length, 1)),
                borderColor: '#ffffff',
                borderWidth: 2
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'bottom',
                    labels: { boxWidth: 12, padding: 12, font: { size: 11 } }
                },
                tooltip: {
                    backgroundColor: '#0f172a',
                    padding: 10,
                    cornerRadius: 8
                }
            }
        }
    });
}

function renderLoanStatusChart(data) {
    const ctx = document.getElementById('loanStatusChart');
    if (!ctx) return;

    new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: data.labels,
            datasets: [{
                data: data.counts,
                backgroundColor: ['#10b981', '#3b82f6', '#ef4444'],
                borderColor: '#ffffff',
                borderWidth: 2,
                cutout: '68%'
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'bottom',
                    labels: { boxWidth: 12, padding: 12, font: { size: 11 } }
                },
                tooltip: {
                    backgroundColor: '#0f172a',
                    padding: 10,
                    cornerRadius: 8
                }
            }
        }
    });
}
