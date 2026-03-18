/**
 * Pipeline Enhancements - Visual Rotting, Dynamic Forecast, Auto-Tasks
 * Features:
 * 1. Red Alert (Visual Rotting) - Cards turn red when stale
 * 2. Dynamic Forecast Widget - Real-time weighted forecast updates
 * 3. Auto-Task Creation - Automatic reminders for stale deals
 */

// Override renderDealCard to include rotting indicators
window.renderDealCardEnhanced = function(deal) {
    const closeDate = deal.expected_close_date ? 
        new Date(deal.expected_close_date).toLocaleDateString('en-US', {month: 'short', day: 'numeric'}) : 
        'No date';
    
    const isRotting = deal.is_rotting || false;
    const daysInStage = deal.days_in_stage || 0;
    const rottingClass = isRotting ? 'deal-card-rotting' : '';
    
    return `
        <div class="deal-card ${rottingClass} bg-white border border-slate-200 rounded-lg p-3 cursor-move hover:shadow-md hover:border-brand-300 transition-all group" 
             draggable="true" 
             data-deal-id="${deal.id}" 
             data-stage-id="${deal.stage.id}">
            ${isRotting ? `
            <div class="deal-rotting-badge flex items-center gap-1.5 mb-2 px-2 py-1 bg-red-50 border border-red-200 rounded text-xs font-bold text-red-600">
                <i class="fas fa-exclamation-triangle"></i>
                <span>${daysInStage} days - Follow up needed!</span>
            </div>
            ` : ''}
            <div class="flex items-start justify-between mb-2" onclick="showDealDetails(${deal.id})">
                <h4 class="text-sm font-semibold text-slate-800 group-hover:text-brand-600 transition-colors line-clamp-2">${deal.name}</h4>
            </div>
            <div class="flex items-center gap-1.5 mb-2" onclick="showDealDetails(${deal.id})">
                <i class="fas fa-building text-xs text-slate-400"></i>
                <p class="text-xs text-slate-500">${deal.company ? deal.company.name : 'No company'}</p>
            </div>
            <div class="flex items-center justify-between pt-2 border-t border-slate-100" onclick="showDealDetails(${deal.id})">
                <span class="text-sm font-bold text-emerald-600">${deal.value.toLocaleString('en-US')}</span>
                <span class="text-xs text-slate-400 flex items-center gap-1">
                    <i class="far fa-calendar"></i>
                    ${closeDate}
                </span>
            </div>
        </div>
    `;
};

// Dynamic forecast update on drag
window.updateForecastOnDrag = function() {
    if (!window.currentPipeline || !window.deals) return;
    
    let totalForecast = 0;
    let totalValue = 0;
    let openDeals = 0;
    
    window.deals.forEach(deal => {
        if (deal.status === 'open') {
            openDeals++;
            totalValue += parseFloat(deal.value);
            
            // Calculate weighted value
            if (deal.stage && deal.stage.probability) {
                totalForecast += parseFloat(deal.value) * (deal.stage.probability / 100);
            }
        }
    });
    
    // Update UI
    document.getElementById('forecastValue').textContent = 
        `$${Math.round(totalForecast).toLocaleString('en-US')}`;
    document.getElementById('openDealsCount').textContent = openDeals;
    document.getElementById('dealCount').textContent = `${openDeals} Deal${openDeals !== 1 ? 's' : ''}`;
    document.getElementById('totalValue').textContent = 
        `$${Math.round(totalValue).toLocaleString('en-US')}`;
};

// Auto-task creation for rotting deals
window.createAutoTasksForRottingDeals = async function() {
    try {
        const response = await fetch('/api/v1/deals/auto-tasks', {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json'
            }
        });
        
        if (!response.ok) {
            throw new Error('Failed to create auto-tasks');
        }
        
        const data = await response.json();
        
        if (data.tasks_created > 0) {
            showToast(`✓ Created ${data.tasks_created} reminder task${data.tasks_created !== 1 ? 's' : ''}`, 'success');
        } else {
            showToast('No rotting deals found', 'info');
        }
        
        return data;
    } catch (error) {
        console.error('Error creating auto-tasks:', error);
        showToast('✗ Failed to create auto-tasks', 'error');
        return null;
    }
};

// Check for rotting deals periodically
window.checkRottingDeals = async function() {
    try {
        const response = await fetch(`/api/v1/deals/rotting?pipeline_id=${window.currentPipeline?.id || ''}`);
        const data = await response.json();
        
        if (data.rotting_deals && data.rotting_deals.length > 0) {
            console.log(`Found ${data.rotting_deals.length} rotting deals`);
            
            // Show notification badge
            const badge = document.getElementById('rottingDealsBadge');
            if (badge) {
                badge.textContent = data.rotting_deals.length;
                badge.classList.remove('hidden');
            }
        }
        
        return data.rotting_deals || [];
    } catch (error) {
        console.error('Error checking rotting deals:', error);
        return [];
    }
};

// Initialize enhancements
document.addEventListener('DOMContentLoaded', function() {
    // Check for rotting deals every 5 minutes
    setInterval(checkRottingDeals, 5 * 60 * 1000);
    
    // Initial check
    setTimeout(checkRottingDeals, 2000);
});
