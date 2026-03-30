/**
 * Workflow Builder JavaScript
 * Handles workflow list management and integration with ReactFlow canvas.
 * Most builder functionality has been moved to WorkflowCanvas.
 */

const WorkflowBuilder = {
    // Current state
    currentWorkflow: null,
    isEditing: false,
    
    // DOM Elements
    elements: {},
    
    /**
     * Initialize the workflow builder
     */
    init() {
        this.cacheElements();
        this.bindEvents();
        this.loadWorkflows();
    },
    
    /**
     * Cache DOM elements for performance
     */
    cacheElements() {
        this.elements = {
            workflowList: document.getElementById('workflowList'),
            statsPanel: document.getElementById('statsPanel'),
        };
    },
    
    /**
     * Bind event listeners
     */
    bindEvents() {
        // No more form-based event bindings - canvas handles the workflow editing
    },
    
    /**
     * Load workflows list from API
     */
    async loadWorkflows() {
        try {
            const response = await fetch('/api/v1/workflows', {
                headers: getCsrfHeaders()
            });
            const data = await response.json();
            
            if (data.workflows) {
                this.renderWorkflowList(data.workflows);
            }
            
            // Update stats
            this.updateStats(data);
        } catch (error) {
            console.error('Error loading workflows:', error);
            showToast('Otomasyonlar yüklenirken hata oluştu', 'error');
        }
    },
    
    /**
     * Render workflow list
     */
    renderWorkflowList(workflows) {
        if (!this.elements.workflowList) return;
        
        this.elements.workflowList.innerHTML = '';
        
        if (workflows.length === 0) {
            this.elements.workflowList.innerHTML = `
                <div class="text-center py-8 text-slate-500">
                    <i class="fas fa-robot text-4xl mb-3 text-slate-300"></i>
                    <p>Henüz otomasyon kuralı yok</p>
                    <p class="text-sm mt-1">Yukarıdaki formu kullanarak yeni kural oluşturabilirsiniz</p>
                </div>
            `;
            return;
        }
        
        workflows.forEach(workflow => {
            const item = this.createWorkflowListItem(workflow);
            this.elements.workflowList.appendChild(item);
        });
    },
    
    /**
     * Create a workflow list item element
     */
    createWorkflowListItem(workflow) {
        const div = document.createElement('div');
        div.className = 'bg-white rounded-xl border border-slate-200 p-4 hover:border-brand-500 transition-colors cursor-pointer relative group';
        div.dataset.workflowId = workflow.id;
        
        const triggerIcon = this.getTriggerIcon(workflow.trigger_type);
        const isActive = workflow.is_active;
        
        div.innerHTML = `
            <div class="flex items-start justify-between">
                <div class="flex items-center gap-3">
                    <div class="w-10 h-10 rounded-xl ${isActive ? 'bg-brand-100 text-brand-600' : 'bg-slate-100 text-slate-400'} flex items-center justify-center">
                        <i class="${triggerIcon}"></i>
                    </div>
                    <div>
                        <h4 class="font-semibold text-slate-800">${workflow.name}</h4>
                        <p class="text-xs text-slate-500">${this.getTriggerName(workflow.trigger_type)}</p>
                    </div>
                </div>
                <div class="flex items-center gap-2">
                    <button type="button" onclick="event.stopPropagation(); WorkflowBuilder.deleteWorkflow(${workflow.id})" 
                        class="w-8 h-8 rounded-lg bg-red-100 text-red-600 hover:bg-red-200 flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity" 
                        title="Sil">
                        <i class="fas fa-trash text-xs"></i>
                    </button>
                    <label class="relative inline-flex items-center cursor-pointer">
                        <input type="checkbox" class="sr-only peer" ${isActive ? 'checked' : ''} onchange="WorkflowBuilder.toggleWorkflow(${workflow.id}, this.checked)">
                        <div class="w-11 h-6 bg-slate-200 peer-focus:outline-none peer-focus:ring-4 peer-focus:ring-brand-300 rounded-full peer peer-checked:after:translate-x-full rtl:peer-checked:after:-translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:start-[2px] after:bg-white after:border-slate-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-brand-600"></div>
                    </label>
                </div>
            </div>
            <div class="mt-3 flex items-center justify-between text-xs text-slate-400">
                <span><i class="fas fa-play mr-1"></i>${workflow.run_count || 0} çalıştırma</span>
                <span>${workflow.last_run_at ? this.formatDate(workflow.last_run_at) : 'Hiç çalışmadı'}</span>
            </div>
        `;
        
        div.addEventListener('click', (e) => {
            if (!e.target.closest('label') && !e.target.closest('button')) {
                this.editWorkflow(workflow);
            }
        });
        
        return div;
    },
    
    /**
     * Delete a workflow
     */
    async deleteWorkflow(workflowId) {
        if (!confirm('Bu workflow\'u silmek istediğinizden emin misiniz?')) {
            return;
        }
        
        try {
            const response = await fetch(`/api/v1/workflows/${workflowId}`, {
                method: 'DELETE',
                headers: getCsrfHeaders()
            });
            
            if (response.ok) {
                showToast('Workflow silindi', 'success');
                this.loadWorkflows();
            } else {
                const error = await response.json();
                showToast(error.error || 'Silme başarısız', 'error');
            }
        } catch (error) {
            console.error('Error deleting workflow:', error);
            showToast('Workflow silinemedi', 'error');
        }
    },
    
    /**
     * Toggle workflow active status
     */
    async toggleWorkflow(id, isActive) {
        try {
            const response = await fetch(`/api/v1/workflows/${id}/toggle`, {
                method: 'PATCH',
                headers: getCsrfHeaders()
            });
            
            if (response.ok) {
                showToast(`Otomasyon ${isActive ? 'aktif' : 'pasif'} hale getirildi`, 'success');
                this.loadWorkflows();
            }
        } catch (error) {
            console.error('Error toggling workflow:', error);
            showToast('Durum değiştirilemedi', 'error');
        }
    },
    
    /**
     * Edit an existing workflow - loads it on the canvas
     */
    async editWorkflow(workflow) {
        try {
            const response = await fetch(`/api/v1/workflows/${workflow.id}`, {
                headers: getCsrfHeaders()
            });
            const data = await response.json();
            
            this.currentWorkflow = data;
            this.isEditing = true;
            
            // Load workflow on the canvas instead of populating form
            if (window.WorkflowCanvas) {
                WorkflowCanvas.loadWorkflow(data);
            }
            
        } catch (error) {
            console.error('Error loading workflow:', error);
            showToast('Otomasyon yüklenemedi', 'error');
        }
    },
    
    /**
     * Show new workflow on canvas
     */
    showNewWorkflow() {
        this.isEditing = false;
        this.currentWorkflow = null;
        
        if (window.WorkflowCanvas) {
            WorkflowCanvas.showNewWorkflow();
        }
    },
    
    /**
     * Filter workflows by search term
     */
    filterWorkflows(searchTerm) {
        const items = document.querySelectorAll('#workflowList > div');
        const term = searchTerm.toLowerCase();
        
        items.forEach(item => {
            const name = item.querySelector('h4')?.textContent?.toLowerCase() || '';
            const desc = item.querySelector('.text-slate-500')?.textContent?.toLowerCase() || '';
            
            if (name.includes(term) || desc.includes(term)) {
                item.classList.remove('hidden');
            } else {
                item.classList.add('hidden');
            }
        });
    },
    
    /**
     * Update stats panel
     */
    updateStats(data) {
        // Update total count
        const activeCount = data.workflows?.filter(w => w.is_active).length || 0;
        const countEl = document.getElementById('activeCount');
        if (countEl) {
            countEl.textContent = `${activeCount} Aktif Kural`;
        }
    },
    
    /**
     * Get trigger icon
     */
    getTriggerIcon(triggerType) {
        const icons = {
            'deal_stage_changed': 'fas fa-exchange-alt',
            'deal_created': 'fas fa-plus-circle',
            'deal_won': 'fas fa-trophy',
            'deal_lost': 'fas fa-times-circle',
            'contact_created': 'fas fa-user-plus',
            'contact_no_activity': 'fas fa-clock',
            'task_completed': 'fas fa-check-circle',
        };
        return icons[triggerType] || 'fas fa-bolt';
    },
    
    /**
     * Get trigger display name
     */
    getTriggerName(triggerType) {
        const names = {
            'deal_stage_changed': 'Aşama değişti',
            'deal_created': 'Yeni anlaşma',
            'deal_won': 'Anlaşma kazanıldı',
            'deal_lost': 'Anlaşma kaybedildi',
            'contact_created': 'Yeni kişi',
            'contact_no_activity': 'Kişi hareketsiz',
            'deal_no_activity': 'Anlaşma hareketsiz',
            'task_completed': 'Görev tamamlandı',
        };
        return names[triggerType] || triggerType;
    },
    
    /**
     * Format date
     */
    formatDate(dateStr) {
        if (!dateStr) return '';
        const date = new Date(dateStr);
        return date.toLocaleDateString('tr-TR', { day: 'numeric', month: 'short' });
    }
};

// Initialize when DOM is ready
document.addEventListener('DOMContentLoaded', () => {
    if (document.getElementById('workflowList')) {
        WorkflowBuilder.init();
        
        // Initialize WorkflowCanvas after WorkflowBuilder is ready
        if (window.WorkflowCanvas) {
            WorkflowCanvas.init();
        }
    }
});
