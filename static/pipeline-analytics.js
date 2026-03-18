// Pipeline Analytics Integration
let winLossChart = null;
let stageDistChart = null;
let analyticsVisible = false;

// Toggle analytics section
function toggleAnalytics() {
    const section = document.getElementById('analyticsSection');
    const toggleText = document.getElementById('analyticsToggleText');
    
    analyticsVisible = !analyticsVisible;
    
    if (analyticsVisible) {
        section.classList.remove('hidden');
        toggleText.textContent = 'Hide Analytics';
        loadPipelineAnalytics();
    } else {
        section.classList.add('hidden');
        toggleText.textContent = 'Show Analytics';
    }
}

// Load analytics data
async function loadPipelineAnalytics() {
    try {
        const response = await fetch('/api/v1/analytics/overview');
        if (!response.ok) throw new Error('Failed to fetch analytics');
        
        const result = await response.json();
        if (!result.success) throw new Error(result.error || 'Unknown error');
        
        const data = result.data;
        
        // Update KPI cards
        updateAnalyticsKPIs(data);
        
        // Render charts
        renderWinLossChart(data.win_loss_ratio);
        renderStageDistChart(data.funnel);
        
    } catch (error) {
        console.error('Error loading analytics:', error);
    }
}

// Update KPI cards
function updateAnalyticsKPIs(data) {
    // Win Rate
    const winRate = data.conversion_rate.rate || 0;
    document.getElementById('analyticsWinRate').textContent = winRate.toFixed(1) + '%';
    document.getElementById('analyticsWonCount').textContent = data.conversion_rate.won_count || 0;
    document.getElementById('analyticsTotalClosed').textContent = data.conversion_rate.total_closed || 0;
    
    // Avg Sales Cycle
    document.getElementById('analyticsAvgCycle').textContent = (data.avg_sales_cycle_days || 0) + ' days';
    
    // Total Contacts (from funnel data)
    const totalContacts = data.funnel.stages.reduce((sum, stage) => sum + stage.deal_count, 0);
    document.getElementById('analyticsTotalContacts').textContent = totalContacts;
}

// Render Win/Loss Chart
function renderWinLossChart(winLossData) {
    const ctx = document.getElementById('pipelineWinLossChart');
    
    if (winLossChart) {
        winLossChart.destroy();
    }
    
    const wonCount = winLossData.won || 0;
    const lostCount = winLossData.lost || 0;
    
    winLossChart = new Chart(ctx, {
        type: 'doughnut',
        data: {
            labels: ['Won', 'Lost'],
            datasets: [{
                data: [wonCount, lostCount],
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
                        padding: 15,
                        font: { size: 11 }
                    }
                },
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            const label = context.label || '';
                            const value = context.parsed || 0;
                            const total = wonCount + lostCount;
                            const percentage = total > 0 ? ((value / total) * 100).toFixed(1) : 0;
                            return label + ': ' + value + ' (' + percentage + '%)';
                        }
                    }
                }
            }
        }
    });
}

// Render Stage Distribution Chart
function renderStageDistChart(funnelData) {
    const ctx = document.getElementById('pipelineStageChart');
    
    if (stageDistChart) {
        stageDistChart.destroy();
    }
    
    const stages = funnelData.stages || [];
    const labels = stages.map(s => s.stage_name);
    const dealCounts = stages.map(s => s.deal_count);
    
    stageDistChart = new Chart(ctx, {
        type: 'bar',
        data: {
            labels: labels,
            datasets: [{
                label: 'Deals',
                data: dealCounts,
                backgroundColor: 'rgba(124, 58, 237, 0.8)',
                borderColor: 'rgb(124, 58, 237)',
                borderWidth: 2,
                borderRadius: 6
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false },
                tooltip: {
                    callbacks: {
                        label: function(context) {
                            return 'Deals: ' + context.parsed.y;
                        }
                    }
                }
            },
            scales: {
                y: {
                    beginAtZero: true,
                    ticks: {
                        stepSize: 1,
                        font: { size: 10 }
                    }
                },
                x: {
                    ticks: {
                        font: { size: 10 }
                    }
                }
            }
        }
    });
}

// Auto-load analytics if previously visible (localStorage)
document.addEventListener('DOMContentLoaded', () => {
    const wasVisible = localStorage.getItem('pipelineAnalyticsVisible') === 'true';
    if (wasVisible) {
        toggleAnalytics();
    }
});

// Save analytics visibility state
window.addEventListener('beforeunload', () => {
    localStorage.setItem('pipelineAnalyticsVisible', analyticsVisible);
});
