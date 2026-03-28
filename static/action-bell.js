// ActionBell - Daily action dashboard bell for prioritized tasks
// Displays high-value actions for sales representatives in topbar

class ActionBell {
    constructor() {
        this.bellIcon = null;
        this.badge = null;
        this.dropdown = null;
        this.actionCount = 0;
        this.refreshInterval = null;
    }

    /**
     * Initialize the action bell
     * Creates HTML, attaches listeners, loads actions
     */
    init() {
        this.createBellHTML();
        this.attachEventListeners();
        this.loadActions();
        this.startAutoRefresh();
    }

    /**
     * Create action bell HTML structure
     * Inserts bell icon with badge and dropdown into topbar
     */
    createBellHTML() {
        const topbar = document.querySelector('header');
        if (!topbar) {
            console.error('Topbar not found for action bell');
            return;
        }

        // Create bell container
        const bellContainer = document.createElement('div');
        bellContainer.id = 'action-bell-container';
        bellContainer.className = 'relative';
        bellContainer.innerHTML = `
            <button id="action-bell" class="w-9 h-9 rounded-full text-gray-500 hover:bg-gray-100 transition-all flex items-center justify-center relative" title="Bugün Ne Yapmalıyım?">
                <i class="fas fa-tasks text-sm"></i>
                <span id="action-badge" class="hidden absolute -top-1 -right-1 min-w-[18px] h-[18px] px-1 text-[10px] font-bold text-white bg-orange-500 rounded-full flex items-center justify-center shadow-sm">0</span>
            </button>
            
            <!-- Action Dropdown -->
            <div id="action-dropdown" class="hidden absolute right-0 mt-2 w-96 bg-white rounded-xl shadow-lg border border-slate-200 z-50">
                <!-- Header -->
                <div class="flex items-center justify-between p-4 border-b border-slate-100">
                    <h3 class="text-sm font-bold text-slate-700">Bugün Ne Yapmalıyım?</h3>
                    <div class="flex items-center gap-2">
                        <button id="refresh-actions-btn" class="text-xs text-brand-600 hover:text-brand-700 font-semibold" title="Yenile">
                            <i class="fas fa-sync-alt"></i>
                        </button>
                        <button onclick="window.location.href='/settings#dashboard'" class="text-xs text-slate-500 hover:text-slate-700 font-semibold" title="Dashboard Ayarları">
                            <i class="fas fa-cog"></i>
                        </button>
                    </div>
                </div>
                
                <!-- Action List -->
                <div id="action-list" class="max-h-96 overflow-y-auto">
                    <!-- Actions will be rendered here -->
                </div>
            </div>
        `;

        // Find the right container - look for the div with buttons in the header
        const buttonContainer = topbar.querySelector('.flex.items-center.gap-1\\.5, .flex.items-center.gap-2');
        const userMenuButton = topbar.querySelector('[data-topbar-menu-button]');
        
        if (buttonContainer && userMenuButton) {
            // Insert before user menu button
            buttonContainer.insertBefore(bellContainer, userMenuButton.parentElement);
        } else if (userMenuButton) {
            // Fallback: insert before user menu
            userMenuButton.parentElement.parentElement.insertBefore(bellContainer, userMenuButton.parentElement);
        } else {
            console.error('Could not find suitable location for action bell');
            return;
        }

        // Store references
        this.bellIcon = document.getElementById('action-bell');
        this.badge = document.getElementById('action-badge');
        this.dropdown = document.getElementById('action-dropdown');
    }

    /**
     * Attach event listeners to bell and dropdown
     */
    attachEventListeners() {
        if (!this.bellIcon || !this.dropdown) return;

        // Toggle dropdown on bell click
        this.bellIcon.addEventListener('click', (e) => {
            e.stopPropagation();
            this.toggleDropdown();
        });

        // Refresh button
        const refreshBtn = document.getElementById('refresh-actions-btn');
        if (refreshBtn) {
            refreshBtn.addEventListener('click', () => this.loadActions());
        }

        // Close dropdown when clicking outside
        document.addEventListener('click', (e) => {
            if (!this.dropdown.contains(e.target) && !this.bellIcon.contains(e.target)) {
                this.closeDropdown();
            }
        });
    }

    /**
     * Load actions from API
     */
    async loadActions() {
        try {
            const response = await fetch('/api/dashboard/actions');
            if (response.status === 401) {
                window.location.href = '/login';
                return;
            }

            if (!response.ok) {
                console.error('Failed to load actions');
                return;
            }

            const data = await response.json();
            this.actionCount = data.count || 0;
            this.updateBadge();
            this.renderActions(data.actions || []);

        } catch (error) {
            console.error('Error loading actions:', error);
        }
    }

    /**
     * Render actions in dropdown list
     * @param {Array} actions - Array of action objects
     */
    renderActions(actions) {
        const listContainer = document.getElementById('action-list');
        if (!listContainer) return;

        listContainer.innerHTML = '';

        if (actions.length === 0) {
            listContainer.innerHTML = `
                <div class="p-8 text-center">
                    <div class="w-12 h-12 bg-green-50 rounded-full flex items-center justify-center mx-auto mb-3">
                        <i class="fas fa-check-circle text-green-500 text-xl"></i>
                    </div>
                    <p class="text-sm font-semibold text-slate-700 mb-1">Harika iş!</p>
                    <p class="text-xs text-slate-500">Bugün için yapılacak aksiyon yok</p>
                </div>
            `;
            return;
        }

        actions.forEach(action => {
            const item = this.createActionItem(action);
            listContainer.appendChild(item);
        });
    }

    /**
     * Create action item HTML element
     * @param {Object} action - Action data
     * @returns {HTMLElement} Action item element
     */
    createActionItem(action) {
        const div = document.createElement('div');
        div.className = 'action-item p-3 border-b border-slate-100 hover:bg-slate-50 transition-colors';
        div.dataset.actionId = action.id;

        const borderColor = this.getPriorityBorderColor(action.priority);
        const priorityBadge = this.getPriorityBadge(action.priority);
        const icon = this.getActionIcon(action.action_type);
        const entityName = this.escapeHtml(action.entity_name);
        const recommendedAction = this.escapeHtml(action.recommended_action);

        div.innerHTML = `
            <div class="flex items-start gap-3 border-l-4 ${borderColor} pl-3">
                <div class="flex-shrink-0 w-8 h-8 rounded-full bg-slate-50 text-slate-600 flex items-center justify-center text-sm">
                    ${icon}
                </div>
                <div class="flex-1 min-w-0">
                    <div class="flex items-center gap-2 mb-1">
                        <p class="text-sm font-semibold text-slate-700">${entityName}</p>
                        ${priorityBadge}
                    </div>
                    <p class="text-xs text-slate-600 mb-2">${recommendedAction}</p>
                    ${this.renderContext(action.context)}
                    <div class="flex items-center gap-2 mt-2">
                        ${action.action_type === 'task_overdue' ? `
                            <button class="complete-action-btn text-xs px-2 py-1 bg-green-50 text-green-700 hover:bg-green-100 rounded font-medium transition-colors" data-action-id="${action.id}">
                                <i class="fas fa-check mr-1"></i>Tamamla
                            </button>
                        ` : ''}
                        <button class="dismiss-action-btn text-xs px-2 py-1 bg-slate-50 text-slate-600 hover:bg-slate-100 rounded font-medium transition-colors" data-action-id="${action.id}">
                            <i class="fas fa-times mr-1"></i>Kapat
                        </button>
                        <button class="view-action-btn text-xs px-2 py-1 text-brand-600 hover:text-brand-700 font-medium" data-action-id="${action.id}" data-entity-type="${action.entity_type}" data-entity-id="${action.entity_id}">
                            Görüntüle →
                        </button>
                    </div>
                </div>
            </div>
        `;

        // Attach button listeners
        const dismissBtn = div.querySelector('.dismiss-action-btn');
        if (dismissBtn) {
            dismissBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                this.dismissAction(action.id);
            });
        }

        const completeBtn = div.querySelector('.complete-action-btn');
        if (completeBtn) {
            completeBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                this.completeAction(action.id);
            });
        }

        const viewBtn = div.querySelector('.view-action-btn');
        if (viewBtn) {
            viewBtn.addEventListener('click', (e) => {
                e.stopPropagation();
                this.navigateToEntity(action.entity_type, action.entity_id);
            });
        }

        return div;
    }

    /**
     * Render context metadata
     * @param {Object} context - Context data
     * @returns {string} HTML string
     */
    renderContext(context) {
        if (!context) return '';

        const items = [];
        
        if (context.lead_score !== undefined) {
            items.push(`<span class="text-xs text-slate-500">Lead Score: <span class="font-semibold">${context.lead_score}</span></span>`);
        }
        
        if (context.days_since_activity !== undefined) {
            items.push(`<span class="text-xs text-slate-500">${context.days_since_activity} gün önce</span>`);
        }
        
        if (context.days_overdue !== undefined) {
            items.push(`<span class="text-xs text-red-600 font-semibold">${context.days_overdue} gün gecikmiş</span>`);
        }
        
        if (context.days_until_close !== undefined) {
            items.push(`<span class="text-xs text-orange-600 font-semibold">${context.days_until_close} gün içinde kapanıyor</span>`);
        }
        
        if (context.value !== undefined) {
            items.push(`<span class="text-xs text-slate-500">Değer: <span class="font-semibold">${this.formatCurrency(context.value)}</span></span>`);
        }

        if (items.length === 0) return '';

        return `<div class="flex flex-wrap gap-2 mt-1">${items.join('')}</div>`;
    }

    /**
     * Get priority border color class
     * @param {string} priority - Priority level
     * @returns {string} Tailwind class
     */
    getPriorityBorderColor(priority) {
        const colors = {
            'urgent': 'border-red-500',
            'high': 'border-orange-500',
            'medium': 'border-yellow-500'
        };
        return colors[priority] || 'border-slate-300';
    }

    /**
     * Get priority badge HTML
     * @param {string} priority - Priority level
     * @returns {string} Badge HTML
     */
    getPriorityBadge(priority) {
        const badges = {
            'urgent': '<span class="text-[10px] px-1.5 py-0.5 bg-red-100 text-red-700 rounded font-bold uppercase">Acil</span>',
            'high': '<span class="text-[10px] px-1.5 py-0.5 bg-orange-100 text-orange-700 rounded font-bold uppercase">Yüksek</span>',
            'medium': '<span class="text-[10px] px-1.5 py-0.5 bg-yellow-100 text-yellow-700 rounded font-bold uppercase">Orta</span>'
        };
        return badges[priority] || '';
    }

    /**
     * Get icon for action type
     * @param {string} type - Action type
     * @returns {string} Icon HTML
     */
    getActionIcon(type) {
        const icons = {
            'contact_followup': '<i class="fas fa-user"></i>',
            'deal_update': '<i class="fas fa-handshake"></i>',
            'task_overdue': '<i class="fas fa-clock"></i>'
        };
        return icons[type] || '<i class="fas fa-bell"></i>';
    }

    /**
     * Dismiss action
     * @param {string} actionId - Action ID
     */
    async dismissAction(actionId) {
        try {
            const response = await fetch(`/api/dashboard/actions/${actionId}/dismiss`, {
                method: 'POST'
            });

            if (response.ok) {
                // Remove from UI
                const item = document.querySelector(`[data-action-id="${actionId}"]`);
                if (item) {
                    item.style.opacity = '0';
                    setTimeout(() => {
                        item.remove();
                        this.actionCount = Math.max(0, this.actionCount - 1);
                        this.updateBadge();
                        
                        // Check if list is empty
                        const listContainer = document.getElementById('action-list');
                        if (listContainer && listContainer.children.length === 0) {
                            this.renderActions([]);
                        }
                    }, 300);
                }
                
                if (typeof showToast === 'function') {
                    showToast('Aksiyon kapatıldı', 'success');
                }
            }
        } catch (error) {
            console.error('Error dismissing action:', error);
            if (typeof showToast === 'function') {
                showToast('Hata oluştu', 'error');
            }
        }
    }

    /**
     * Complete action
     * @param {string} actionId - Action ID
     */
    async completeAction(actionId) {
        try {
            const response = await fetch(`/api/dashboard/actions/${actionId}/complete`, {
                method: 'POST'
            });

            if (response.ok) {
                // Remove from UI
                const item = document.querySelector(`[data-action-id="${actionId}"]`);
                if (item) {
                    item.style.opacity = '0';
                    setTimeout(() => {
                        item.remove();
                        this.actionCount = Math.max(0, this.actionCount - 1);
                        this.updateBadge();
                        
                        // Check if list is empty
                        const listContainer = document.getElementById('action-list');
                        if (listContainer && listContainer.children.length === 0) {
                            this.renderActions([]);
                        }
                    }, 300);
                }
                
                if (typeof showToast === 'function') {
                    showToast('Aksiyon tamamlandı', 'success');
                }
            }
        } catch (error) {
            console.error('Error completing action:', error);
            if (typeof showToast === 'function') {
                showToast('Hata oluştu', 'error');
            }
        }
    }

    /**
     * Navigate to entity detail page
     * @param {string} entityType - Entity type (contact, deal, task)
     * @param {number} entityId - Entity ID
     */
    navigateToEntity(entityType, entityId) {
        const routes = {
            'contact': `/contacts/${entityId}`,
            'deal': `/deals/${entityId}`,
            'task': `/tasks?task_id=${entityId}`
        };

        const url = routes[entityType];
        if (url) {
            window.location.href = url;
        }

        this.closeDropdown();
    }

    /**
     * Update badge count display
     */
    updateBadge() {
        if (!this.badge) return;

        if (this.actionCount > 0) {
            this.badge.textContent = this.actionCount > 99 ? '99+' : this.actionCount;
            this.badge.classList.remove('hidden');
        } else {
            this.badge.classList.add('hidden');
        }
    }

    /**
     * Toggle dropdown visibility
     */
    toggleDropdown() {
        if (!this.dropdown) return;

        const isHidden = this.dropdown.classList.contains('hidden');
        
        if (isHidden) {
            this.dropdown.classList.remove('hidden');
            // Reload actions when opening
            this.loadActions();
        } else {
            this.closeDropdown();
        }
    }

    /**
     * Close dropdown
     */
    closeDropdown() {
        if (this.dropdown) {
            this.dropdown.classList.add('hidden');
        }
    }

    /**
     * Start auto-refresh (every 5 minutes)
     */
    startAutoRefresh() {
        // Refresh every 5 minutes
        this.refreshInterval = setInterval(() => {
            this.loadActions();
        }, 5 * 60 * 1000);
    }

    /**
     * Stop auto-refresh
     */
    stopAutoRefresh() {
        if (this.refreshInterval) {
            clearInterval(this.refreshInterval);
            this.refreshInterval = null;
        }
    }

    /**
     * Format currency
     * @param {number} value - Currency value
     * @returns {string} Formatted currency
     */
    formatCurrency(value) {
        if (!value) return '₺0';
        return new Intl.NumberFormat('tr-TR', {
            style: 'currency',
            currency: 'TRY',
            minimumFractionDigits: 0,
            maximumFractionDigits: 0
        }).format(value);
    }

    /**
     * Escape HTML to prevent XSS
     * @param {string} str - String to escape
     * @returns {string} Escaped string
     */
    escapeHtml(str) {
        if (!str) return '';
        return String(str)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#039;');
    }
}

// Export for use in other modules
if (typeof module !== 'undefined' && module.exports) {
    module.exports = ActionBell;
}
