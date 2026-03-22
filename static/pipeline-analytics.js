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
        const response = await fetch('/api/v1/deals/analytics' + (window.currentPipeline ? '?pipeline_id=' + window.currentPipeline.id : ''));
        if (!response.ok) throw new Error('Failed to fetch analytics');
        
        const result = await response.json();
        const data = await normalizeAnalyticsPayload(result);
        
        // Update KPI cards
        updateAnalyticsKPIs(data);
        
        // Render charts
        renderWinLossChart(data.win_loss_ratio);
        renderStageDistChart(data.funnel);
        
    } catch (error) {
        console.error('Error loading analytics:', error);
    }
}

async function normalizeAnalyticsPayload(result) {
    // Backward compatible: old format { success, data } and new direct format.
    if (result && typeof result === 'object' && result.success === true && result.data) {
        return result.data;
    }

    if (!result || typeof result !== 'object') {
        throw new Error('Unknown error');
    }
    if (result.error) {
        throw new Error(result.error);
    }

    // New backend payload:
    // { total_value, open_deals, weighted_forecast, by_category }
    const pipelineId = window.currentPipeline ? window.currentPipeline.id : null;
    const dealsUrl = '/api/v1/deals' + (pipelineId ? `?pipeline_id=${pipelineId}&per_page=100` : '?per_page=100');
    const [openRes, wonRes, lostRes] = await Promise.all([
        fetch(dealsUrl),
        fetch('/api/v1/deals' + (pipelineId ? `?pipeline_id=${pipelineId}&status=won&per_page=100` : '?status=won&per_page=100')),
        fetch('/api/v1/deals' + (pipelineId ? `?pipeline_id=${pipelineId}&status=lost&per_page=100` : '?status=lost&per_page=100')),
    ]);

    const openJson = openRes.ok ? await openRes.json() : { deals: [] };
    const wonJson = wonRes.ok ? await wonRes.json() : { deals: [] };
    const lostJson = lostRes.ok ? await lostRes.json() : { deals: [] };

    const openDeals = (openJson && (openJson.deals || openJson.data || [])) || [];
    const wonDeals = (wonJson && (wonJson.deals || wonJson.data || [])) || [];
    const lostDeals = (lostJson && (lostJson.deals || lostJson.data || [])) || [];

    const stageMap = new Map();
    openDeals.forEach((deal) => {
        const stageName = deal.stage && deal.stage.name ? deal.stage.name : 'Unknown';
        const prev = stageMap.get(stageName) || 0;
        stageMap.set(stageName, prev + 1);
    });
    const stageRows = Array.from(stageMap.entries()).map(([stage_name, deal_count]) => ({ stage_name, deal_count }));

    return {
        conversion_rate: {
            won_count: wonDeals.length,
            total_closed: wonDeals.length + lostDeals.length,
            rate: (wonDeals.length + lostDeals.length) > 0
                ? (wonDeals.length * 100 / (wonDeals.length + lostDeals.length))
                : 0
        },
        avg_sales_cycle_days: 0,
        funnel: {
            stages: stageRows
        },
        win_loss_ratio: {
            won: wonDeals.length,
            lost: lostDeals.length
        }
    };
}

// Update KPI cards
function updateAnalyticsKPIs(data) {
    // Win Rate
    const conversion = data.conversion_rate || {};
    const winRate = conversion.rate || 0;
    document.getElementById('analyticsWinRate').textContent = winRate.toFixed(1) + '%';
    document.getElementById('analyticsWonCount').textContent = conversion.won_count || 0;
    document.getElementById('analyticsTotalClosed').textContent = conversion.total_closed || 0;
    
    // Avg Sales Cycle
    document.getElementById('analyticsAvgCycle').textContent = (data.avg_sales_cycle_days || 0) + ' days';
    
    // Total Contacts (from funnel data)
    const stages = (data.funnel && data.funnel.stages) ? data.funnel.stages : [];
    const totalContacts = stages.reduce((sum, stage) => sum + (stage.deal_count || 0), 0);
    document.getElementById('analyticsTotalContacts').textContent = totalContacts;
}

// Render Win/Loss Chart
function renderWinLossChart(winLossData) {
    const ctx = document.getElementById('pipelineWinLossChart');
    
    if (winLossChart) {
        winLossChart.destroy();
    }
    
    const safeWinLoss = winLossData || {};
    const wonCount = safeWinLoss.won || 0;
    const lostCount = safeWinLoss.lost || 0;
    
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
