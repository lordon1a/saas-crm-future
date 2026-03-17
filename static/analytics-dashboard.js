// Analytics Dashboard JavaScript
// Handles data fetching and chart rendering

let pipelineChart = null;
let winLossChart = null;

// Initialize dashboard on page load
document.addEventListener('DOMContentLoaded', () => {
    loadDashboardData();
});

// Load all dashboard data
async function loadDashboardData() {
    try {
        showLoading();
        
        const response = await fetch('/api/analytics/dashboard');
        
        if (!response.ok) {
            throw new Error('Failed to fetch dashboard data');
        }
        
        const data = await response.json();
        
        // Update KPIs
        updateKPIs(data.kpis);
        
        // Render charts
        renderPipelineChart(data.pipeline_distribution);
        renderWinLossChart(data.win_loss_ratio);
        
        // Update task stats
        updateTaskStats(data.task_completion, data.kpis);
        
        hideLoading();
        
    } catch (error) {
        console.error('Error loading dashboard:', error);
        showError('Failed to load dashboard data');
        hideLoading();
    }
}

// Update KPI cards
function updateKPIs(kpis) {
    document.getElementById('kpiTotalRevenue').textContent = formatCurrency(kpis.total_revenue);
    document.getElementById('kpiOpenOpportunities').textContent = kpis.open_opportunities;
    document.getElementById('kpiTotalContacts').textContent = kpis.total_contacts;
    document.getElementById('kpiActiveTasks').textContent = kpis.active_tasks;
}

// Render pipeline distribution bar chart
function renderPipelineChart(data) {
    const ctx = document.getElementById('pipelineChart');
    
    // Destroy existing chart if any
    if (pipelineChart) {
        pipelineChart.destroy();
    }
    
    const stages = data.stages || [];
    const labels = stages.map(s => s.stage_name);
    const values = stages.map(s => s.total_value);
    
    pipelineChart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [{
                label: 'Deal Value ($)',
                data: values,
                backgroundColor: [
                    'rgba(59, 130, 246, 0.8)',
                    'rgba(16, 185, 129, 0.8)',
                    'rgba(245, 158, 11, 0.8)',
                    'rgba(239, 68, 68, 0.8)',
                    'rgba(139, 92, 246, 0.8)'
                ],
                borderColor: [
                    'rgb(59, 130, 246)',
                    'rgb(16, 185, 129)',
                    'rgb(245, 158, 11)',
                    'rgb(239, 68, 68)',
                    'rgb(139, 92, 246)'
                ],
                borderWidth: 2,
                borderRadius: 8
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    display: false
                },
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            return 'Value: $' + context.parsed.y.toLocaleString();
                        }
                    }
                }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    ticks: {
                        callback: function(value) {
                            return '$' + value.toLocaleString();
                        }
                    }
                }
            }
        }
    });
}

// Render win/loss doughnut chart
function renderWinLossChart(data) {
    const ctx = document.getElementById('winLossChart');
    
    // Destroy existing chart if any
    if (winLossChart) {
        winLossChart.destroy();
    }
    
    // Update win rate text
    document.getElementById('winRateText').textContent = data.win_rate + '% Win Rate';
    
    winLossChart = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: ['Won', 'Lost'],
            datasets: [{
                data: [data.won_count, data.lost_count],
                backgroundColor: [
                    'rgba(16, 185, 129, 0.8)',
                    'rgba(239, 68, 68, 0.8)'
                ],
                borderColor: [
                    'rgb(16, 185, 129)',
                    'rgb(239, 68, 68)'
                ],
                borderWidth: 2
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: {
                    position: 'bottom',
                    labels: {
                        padding: 20,
                        font: {
                            size: 14
                        }
                    }
                },
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            const label = context.label || '';
                            const value = context.parsed || 0;
                            const total = context.dataset.data.reduce((a, b) => a + b, 0);
                            const percentage = total > 0 ? ((value / total) * 100).toFixed(1) : 0;
                            return label + ': ' + value + ' (' + percentage + '%)';
                        }
                    }
                }
            }
        }
    });
}

// Update task completion stats
function updateTaskStats(taskData, kpis) {
    document.getElementById('totalTasks').textContent = taskData.total_tasks;
    document.getElementById('completedTasks').textContent = taskData.completed_tasks;
    document.getElementById('overdueTasks').textContent = taskData.overdue_tasks;
    document.getElementById('completedThisMonth').textContent = kpis.completed_tasks_this_month;
    document.getElementById('completionRateText').textContent = taskData.completion_rate + '% Complete';
}

// Refresh dashboard
function refreshDashboard() {
    loadDashboardData();
}

// Show loading state
function showLoading() {
    document.getElementById('loadingState').classList.remove('hidden');
    document.getElementById('dashboardContent').classList.add('hidden');
}

// Hide loading state
function hideLoading() {
    document.getElementById('loadingState').classList.add('hidden');
    document.getElementById('dashboardContent').classList.remove('hidden');
}

// Show error message
function showError(message) {
    const loadingState = document.getElementById('loadingState');
    loadingState.innerHTML = `
        <div class="text-center">
            <i class="fas fa-exclamation-circle text-4xl text-red-600 mb-4"></i>
            <p class="text-gray-600">${message}</p>
            <button onclick="refreshDashboard()" class="mt-4 px-4 py-2 bg-purple-600 text-white rounded-lg hover:bg-purple-700">
                Try Again
            </button>
        </div>
    `;
}

// Format currency
function formatCurrency(value) {
    return '$' + value.toLocaleString('en-US', {
        minimumFractionDigits: 0,
        maximumFractionDigits: 0
    });
}
