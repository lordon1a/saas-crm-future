/**
 * Modern Filter System for Contacts
 * HubSpot-style advanced filtering with AND/OR logic
 */

class FilterSystem {
    constructor() {
        this.filters = [];
        this.savedFilters = [];
        this.activeFilterId = null;
        this.operators = {
            text: [
                { value: 'contains', label: 'içerir' },
                { value: 'not_contains', label: 'içermez' },
                { value: 'equals', label: 'eşittir' },
                { value: 'not_equals', label: 'eşit değildir' },
                { value: 'starts_with', label: 'ile başlar' },
                { value: 'ends_with', label: 'ile biter' },
                { value: 'is_empty', label: 'boş' },
                { value: 'is_not_empty', label: 'dolu' }
            ],
            number: [
                { value: 'equals', label: 'eşittir' },
                { value: 'not_equals', label: 'eşit değildir' },
                { value: 'greater_than', label: 'büyüktür' },
                { value: 'less_than', label: 'küçüktür' },
                { value: 'greater_or_equal', label: 'büyük veya eşit' },
                { value: 'less_or_equal', label: 'küçük veya eşit' },
                { value: 'between', label: 'arasında' },
                { value: 'is_empty', label: 'boş' },
                { value: 'is_not_empty', label: 'dolu' }
            ],
            date: [
                { value: 'equals', label: 'eşittir' },
                { value: 'before', label: 'önce' },
                { value: 'after', label: 'sonra' },
                { value: 'between', label: 'arasında' },
                { value: 'last_7_days', label: 'son 7 gün' },
                { value: 'last_30_days', label: 'son 30 gün' },
                { value: 'this_month', label: 'bu ay' },
                { value: 'last_month', label: 'geçen ay' },
                { value: 'is_empty', label: 'boş' },
                { value: 'is_not_empty', label: 'dolu' }
            ],
            dropdown: [
                { value: 'equals', label: 'eşittir' },
                { value: 'not_equals', label: 'eşit değildir' },
                { value: 'in', label: 'içinde' },
                { value: 'not_in', label: 'içinde değil' },
                { value: 'is_empty', label: 'boş' },
                { value: 'is_not_empty', label: 'dolu' }
            ]
        };
        
        this.fields = [
            { id: 'first_name', label: 'Ad', type: 'text' },
            { id: 'last_name', label: 'Soyad', type: 'text' },
            { id: 'email', label: 'E-posta', type: 'text' },
            { id: 'phone', label: 'Telefon', type: 'text' },
            { id: 'whatsapp_phone', label: 'WhatsApp', type: 'text' },
            { id: 'company_id', label: 'Şirket', type: 'number' },
            { id: 'role', label: 'Rol', type: 'dropdown' },
            { id: 'job_title', label: 'Unvan', type: 'text' },
            { id: 'lead_score', label: 'Lead Score', type: 'number' },
            { id: 'is_starred', label: 'Yıldızlı', type: 'dropdown' },
            { id: 'created_at', label: 'Oluşturulma Tarihi', type: 'date' },
            { id: 'updated_at', label: 'Güncellenme Tarihi', type: 'date' }
        ];
    }

    init() {
        // Don't load saved filters on init to avoid 404
        // They will be loaded when user opens filter builder
        this.setupEventListeners();
        this.renderQuickFilters();
    }

    setupEventListeners() {
        // Filter button click
        document.getElementById('openFilterBuilder')?.addEventListener('click', () => {
            this.openFilterBuilder();
        });

        // Quick filter clicks
        document.querySelectorAll('.quick-filter-btn').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const filterId = e.currentTarget.dataset.filterId;
                this.applyQuickFilter(filterId);
            });
        });
    }

    openFilterBuilder() {
        const modal = document.getElementById('filterBuilderModal');
        if (!modal) {
            this.createFilterBuilderModal();
        }
        
        // Load saved filters when opening builder
        this.loadSavedFilters().then(() => {
            this.renderFilterBuilder();
        });
        
        const modalEl = document.getElementById('filterBuilderModal');
        const contentEl = document.getElementById('filterModalContent');
        
        modalEl.classList.remove('hidden');
        modalEl.classList.add('flex');
        
        // Trigger animation
        requestAnimationFrame(() => {
            contentEl.style.transform = 'scale(1)';
            contentEl.style.opacity = '1';
        });
    }

    createFilterBuilderModal() {
        const modalHTML = `
            <div id="filterBuilderModal" class="hidden fixed inset-0 bg-slate-900/40 backdrop-blur-sm z-50 items-center justify-center p-4 animate-fade-in">
                <div class="bg-white rounded-2xl shadow-2xl w-full max-w-4xl max-h-[90vh] overflow-hidden flex flex-col transform transition-all duration-300 ease-out scale-95 opacity-0" id="filterModalContent">
                    <!-- Header -->
                    <div class="px-6 py-4 border-b border-gray-100 flex items-center justify-between flex-shrink-0 bg-gradient-to-r from-white to-gray-50">
                        <div>
                            <h3 class="text-lg font-bold text-gray-900 flex items-center gap-2">
                                <i class="fas fa-filter text-brand-600"></i>
                                Gelişmiş Filtreler
                            </h3>
                            <p class="text-sm text-gray-500 mt-0.5">Kişileri detaylı kriterlere göre filtreleyin</p>
                        </div>
                        <button onclick="filterSystem.closeFilterBuilder()" class="w-9 h-9 rounded-lg bg-white border border-gray-200 text-gray-400 hover:text-gray-700 hover:bg-gray-50 hover:border-gray-300 transition-all duration-200 flex items-center justify-center hover:rotate-90">
                            <i class="fas fa-times text-sm"></i>
                        </button>
                    </div>

                    <!-- Saved Filters Tabs -->
                    <div class="px-6 py-3 border-b border-gray-100 flex items-center gap-2 overflow-x-auto flex-shrink-0 bg-gray-50/50">
                        <button onclick="filterSystem.newFilter()" class="px-3 py-2 text-xs font-semibold text-brand-600 hover:bg-brand-50 hover:text-brand-700 rounded-lg transition-all duration-200 flex items-center gap-1.5 border border-transparent hover:border-brand-200 hover:shadow-sm">
                            <i class="fas fa-plus text-xs"></i> 
                            <span>Yeni Filtre</span>
                        </button>
                        <div class="h-5 w-px bg-gray-300"></div>
                        <div id="savedFilterTabs" class="flex items-center gap-2">
                            <!-- Saved filters will be rendered here -->
                        </div>
                    </div>

                    <!-- Filter Builder Content -->
                    <div class="flex-1 overflow-y-auto p-6">
                        <div id="filterBuilderContent">
                            <!-- Filter groups will be rendered here -->
                        </div>
                    </div>

                    <!-- Footer -->
                    <div class="px-6 py-4 border-t border-gray-100 flex items-center justify-between flex-shrink-0 bg-gray-50/30">
                        <div class="flex items-center gap-2">
                            <button onclick="filterSystem.saveCurrentFilter()" class="px-4 py-2.5 text-sm font-semibold text-gray-700 hover:bg-white border border-gray-200 hover:border-gray-300 rounded-lg transition-all duration-200 flex items-center gap-2 hover:shadow-sm">
                                <i class="fas fa-bookmark text-xs"></i> 
                                <span>Kaydet</span>
                            </button>
                            <button onclick="filterSystem.clearAllFilters()" class="px-4 py-2.5 text-sm font-semibold text-red-600 hover:bg-red-50 border border-transparent hover:border-red-200 rounded-lg transition-all duration-200 hover:shadow-sm">
                                <i class="fas fa-eraser text-xs"></i>
                                <span>Temizle</span>
                            </button>
                        </div>
                        <div class="flex gap-3">
                            <button onclick="filterSystem.closeFilterBuilder()" class="px-6 py-2.5 bg-white border border-gray-300 text-gray-700 font-semibold rounded-lg hover:bg-gray-50 hover:border-gray-400 transition-all duration-200">
                                İptal
                            </button>
                            <button onclick="filterSystem.applyFilters()" class="px-6 py-2.5 bg-brand-600 text-white font-semibold rounded-lg hover:bg-brand-700 transition-all duration-200 shadow-lg hover:shadow-xl flex items-center gap-2 hover:scale-105 active:scale-100">
                                <i class="fas fa-check text-sm"></i>
                                <span id="filterApplyBtnText">Uygula</span>
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        `;
        
        document.body.insertAdjacentHTML('beforeend', modalHTML);
    }

    renderFilterBuilder() {
        const content = document.getElementById('filterBuilderContent');
        if (!content) return;

        if (this.filters.length === 0) {
            this.addFilterGroup();
        }

        let html = '<div class="space-y-4">';
        
        this.filters.forEach((filterGroup, groupIndex) => {
            html += this.renderFilterGroup(filterGroup, groupIndex);
        });

        html += '</div>';
        content.innerHTML = html;
        
        this.renderSavedFilterTabs();
    }

    renderFilterGroup(filterGroup, groupIndex) {
        const isFirst = groupIndex === 0;
        
        let html = `
            <div class="bg-white rounded-xl p-5 border border-gray-200 shadow-sm hover:shadow-md transition-all duration-300 animate-slide-in">
                ${!isFirst ? `
                    <div class="flex items-center justify-between mb-4 pb-3 border-b border-gray-100">
                        <div class="flex items-center gap-2">
                            <span class="text-xs font-medium text-gray-500 uppercase tracking-wide">Mantık</span>
                            <select onchange="filterSystem.updateGroupLogic(${groupIndex}, this.value)" class="px-3 py-2 bg-gradient-to-b from-white to-gray-50 border border-gray-300 rounded-lg text-sm font-semibold text-gray-700 hover:border-brand-400 focus:border-brand-500 focus:ring-2 focus:ring-brand-200 transition-all duration-200">
                                <option value="AND" ${filterGroup.logic === 'AND' ? 'selected' : ''}>VE (AND)</option>
                                <option value="OR" ${filterGroup.logic === 'OR' ? 'selected' : ''}>VEYA (OR)</option>
                            </select>
                        </div>
                        <button onclick="filterSystem.removeFilterGroup(${groupIndex})" class="text-red-600 hover:bg-red-50 p-2 rounded-lg transition-all duration-200 hover:scale-110 active:scale-95">
                            <i class="fas fa-trash text-sm"></i>
                        </button>
                    </div>
                ` : ''}
                
                <div class="space-y-3">
        `;

        filterGroup.conditions.forEach((condition, condIndex) => {
            html += this.renderCondition(condition, groupIndex, condIndex);
        });

        html += `
                </div>
                
                <button onclick="filterSystem.addCondition(${groupIndex})" class="mt-4 px-4 py-2 text-sm font-semibold text-brand-600 hover:bg-brand-50 hover:text-brand-700 rounded-lg transition-all duration-200 flex items-center gap-2 border border-dashed border-brand-300 hover:border-brand-500 w-full justify-center hover:shadow-sm">
                    <i class="fas fa-plus text-xs"></i> 
                    <span>Koşul Ekle</span>
                </button>
            </div>
        `;

        return html;
    }

    renderCondition(condition, groupIndex, condIndex) {
        const field = this.fields.find(f => f.id === condition.field) || this.fields[0];
        const operators = this.operators[field.type] || this.operators.text;
        
        return `
            <div class="flex items-center gap-3 bg-gradient-to-r from-gray-50 to-white p-4 rounded-lg border border-gray-200 hover:border-brand-300 transition-all duration-200 hover:shadow-sm group">
                <!-- Field Select -->
                <select onchange="filterSystem.updateConditionField(${groupIndex}, ${condIndex}, this.value)" 
                        class="flex-1 px-3 py-2.5 bg-white border border-gray-300 rounded-lg text-sm font-medium text-gray-700 hover:border-brand-400 focus:border-brand-500 focus:ring-2 focus:ring-brand-200 transition-all duration-200 cursor-pointer">
                    ${this.fields.map(f => `
                        <option value="${f.id}" ${f.id === condition.field ? 'selected' : ''}>${f.label}</option>
                    `).join('')}
                </select>

                <!-- Operator Select -->
                <select onchange="filterSystem.updateConditionOperator(${groupIndex}, ${condIndex}, this.value)"
                        class="flex-1 px-3 py-2.5 bg-white border border-gray-300 rounded-lg text-sm font-medium text-gray-700 hover:border-brand-400 focus:border-brand-500 focus:ring-2 focus:ring-brand-200 transition-all duration-200 cursor-pointer">
                    ${operators.map(op => `
                        <option value="${op.value}" ${op.value === condition.operator ? 'selected' : ''}>${op.label}</option>
                    `).join('')}
                </select>

                <!-- Value Input -->
                ${this.renderValueInput(condition, groupIndex, condIndex, field)}

                <!-- Remove Button -->
                <button onclick="filterSystem.removeCondition(${groupIndex}, ${condIndex})" 
                        class="p-2.5 text-red-600 hover:bg-red-50 rounded-lg transition-all duration-200 hover:scale-110 active:scale-95 opacity-0 group-hover:opacity-100">
                    <i class="fas fa-times text-sm"></i>
                </button>
            </div>
        `;
    }

    renderValueInput(condition, groupIndex, condIndex, field) {
        if (condition.operator === 'is_empty' || condition.operator === 'is_not_empty') {
            return '<div class="flex-1"></div>';
        }

        const inputId = `filter_value_${groupIndex}_${condIndex}`;
        
        if (field.type === 'dropdown') {
            // Get options based on field
            let options = [];
            if (field.id === 'role') {
                options = ['Decision Maker', 'Champion', 'Influencer', 'Blocker', 'User'];
            } else if (field.id === 'is_starred') {
                options = [
                    { value: 'true', label: 'Evet' },
                    { value: 'false', label: 'Hayır' }
                ];
            }
            
            return `
                <select id="${inputId}" onchange="filterSystem.updateConditionValue(${groupIndex}, ${condIndex}, this.value)"
                        class="flex-1 px-3 py-2.5 bg-white border border-gray-300 rounded-lg text-sm font-medium text-gray-700 hover:border-brand-400 focus:border-brand-500 focus:ring-2 focus:ring-brand-200 transition-all duration-200 cursor-pointer">
                    <option value="">Seçiniz</option>
                    ${field.id === 'is_starred' 
                        ? options.map(opt => `
                            <option value="${opt.value}" ${opt.value === condition.value ? 'selected' : ''}>${opt.label}</option>
                        `).join('')
                        : options.map(opt => `
                            <option value="${opt}" ${opt === condition.value ? 'selected' : ''}>${opt}</option>
                        `).join('')
                    }
                </select>
            `;
        } else if (field.type === 'number') {
            return `
                <input type="number" id="${inputId}" value="${condition.value || ''}"
                       onchange="filterSystem.updateConditionValue(${groupIndex}, ${condIndex}, this.value)"
                       placeholder="Değer girin"
                       class="flex-1 px-3 py-2.5 bg-white border border-gray-300 rounded-lg text-sm font-medium text-gray-700 hover:border-brand-400 focus:border-brand-500 focus:ring-2 focus:ring-brand-200 transition-all duration-200">
            `;
        } else if (field.type === 'date') {
            return `
                <input type="date" id="${inputId}" value="${condition.value || ''}"
                       onchange="filterSystem.updateConditionValue(${groupIndex}, ${condIndex}, this.value)"
                       class="flex-1 px-3 py-2.5 bg-white border border-gray-300 rounded-lg text-sm font-medium text-gray-700 hover:border-brand-400 focus:border-brand-500 focus:ring-2 focus:ring-brand-200 transition-all duration-200">
            `;
        } else {
            return `
                <input type="text" id="${inputId}" value="${condition.value || ''}"
                       onchange="filterSystem.updateConditionValue(${groupIndex}, ${condIndex}, this.value)"
                       placeholder="Değer girin"
                       class="flex-1 px-3 py-2.5 bg-white border border-gray-300 rounded-lg text-sm font-medium text-gray-700 hover:border-brand-400 focus:border-brand-500 focus:ring-2 focus:ring-brand-200 transition-all duration-200">
            `;
        }
    }

    // Filter manipulation methods
    newFilter() {
        this.filters = [];
        this.activeFilterId = null;
        this.addFilterGroup();
        this.renderFilterBuilder();
    }

    addFilterGroup() {
        this.filters.push({
            logic: 'AND',
            conditions: [
                { field: 'first_name', operator: 'contains', value: '' }
            ]
        });
        this.renderFilterBuilder();
    }

    addCondition(groupIndex) {
        this.filters[groupIndex].conditions.push({
            field: 'first_name',
            operator: 'contains',
            value: ''
        });
        this.renderFilterBuilder();
    }

    removeFilterGroup(groupIndex) {
        this.filters.splice(groupIndex, 1);
        if (this.filters.length === 0) {
            this.addFilterGroup();
        }
        this.renderFilterBuilder();
    }

    removeCondition(groupIndex, condIndex) {
        this.filters[groupIndex].conditions.splice(condIndex, 1);
        if (this.filters[groupIndex].conditions.length === 0) {
            this.removeFilterGroup(groupIndex);
        } else {
            this.renderFilterBuilder();
        }
    }

    updateGroupLogic(groupIndex, logic) {
        this.filters[groupIndex].logic = logic;
    }

    updateConditionField(groupIndex, condIndex, fieldId) {
        const field = this.fields.find(f => f.id === fieldId);
        this.filters[groupIndex].conditions[condIndex].field = fieldId;
        this.filters[groupIndex].conditions[condIndex].operator = this.operators[field.type][0].value;
        this.filters[groupIndex].conditions[condIndex].value = '';
        this.renderFilterBuilder();
    }

    updateConditionOperator(groupIndex, condIndex, operator) {
        this.filters[groupIndex].conditions[condIndex].operator = operator;
        this.renderFilterBuilder();
    }

    updateConditionValue(groupIndex, condIndex, value) {
        this.filters[groupIndex].conditions[condIndex].value = value;
    }

    // Apply filters
    async applyFilters() {
        const filterQuery = this.buildFilterQuery();
        
        // Close modal
        this.closeFilterBuilder();
        
        // Apply to contacts list
        await window.loadContactsWithFilters(filterQuery);
        
        // Update UI
        this.updateFilterBadge();
        this.renderActiveFilters();
    }

    buildFilterQuery() {
        // Convert filter structure to API query format
        // Backend expects: { filters: [ {field, operator, value}, ... ] }
        
        const allConditions = [];
        
        this.filters.forEach(group => {
            group.conditions.forEach(condition => {
                if (condition.value || condition.operator === 'is_empty' || condition.operator === 'is_not_empty') {
                    // Map frontend operators to backend operators
                    const operatorMap = {
                        'is_empty': 'is_null',
                        'is_not_empty': 'is_not_null',
                        'greater_or_equal': 'greater_than_or_equal',
                        'less_or_equal': 'less_than_or_equal',
                        'greater_than': 'greater_than',
                        'less_than': 'less_than',
                        'equals': 'equals',
                        'not_equals': 'not_equals',
                        'contains': 'contains',
                        'not_contains': 'not_contains',
                        'starts_with': 'starts_with',
                        'ends_with': 'ends_with',
                        'between': 'between',
                        'in': 'in',
                        'not_in': 'not_in'
                    };
                    
                    let backendOperator = operatorMap[condition.operator] || condition.operator;
                    
                    // Handle special cases
                    let value = condition.value;
                    
                    // Convert string boolean to actual boolean
                    if (value === 'true') value = true;
                    if (value === 'false') value = false;
                    
                    // Convert string numbers to actual numbers for numeric fields
                    const numericFields = ['lead_score', 'company_id', 'display_order'];
                    if (numericFields.includes(condition.field) && typeof value === 'string' && value !== '') {
                        value = parseFloat(value);
                    }
                    
                    allConditions.push({
                        field: condition.field,
                        operator: backendOperator,
                        value: value
                    });
                }
            });
        });

        return allConditions.length > 0 ? { filters: allConditions } : null;
    }

    renderActiveFilters() {
        const container = document.getElementById('activeFiltersDisplay');
        const list = document.getElementById('activeFiltersList');
        
        if (!container || !list) return;

        const activeConditions = this.filters.flatMap(group => 
            group.conditions.filter(c => c.value || c.operator === 'is_empty' || c.operator === 'is_not_empty')
        );

        if (activeConditions.length === 0) {
            container.classList.add('hidden');
            return;
        }

        container.classList.remove('hidden');
        
        list.innerHTML = activeConditions.map((condition, index) => {
            const field = this.fields.find(f => f.id === condition.field);
            const operator = this.operators[field?.type || 'text'].find(op => op.value === condition.operator);
            
            return `
                <div class="flex items-center gap-1.5 px-2.5 py-1 bg-brand-50 border border-brand-200 rounded-lg text-xs">
                    <span class="font-semibold text-brand-700">${field?.label || condition.field}</span>
                    <span class="text-brand-600">${operator?.label || condition.operator}</span>
                    ${condition.value ? `<span class="font-semibold text-brand-800">${condition.value}</span>` : ''}
                    <button onclick="filterSystem.removeActiveFilter(${index})" class="ml-1 text-brand-600 hover:text-brand-800">
                        <i class="fas fa-times text-[10px]"></i>
                    </button>
                </div>
            `;
        }).join('');
    }

    removeActiveFilter(index) {
        let currentIndex = 0;
        for (let groupIndex = 0; groupIndex < this.filters.length; groupIndex++) {
            const group = this.filters[groupIndex];
            for (let condIndex = 0; condIndex < group.conditions.length; condIndex++) {
                if (currentIndex === index) {
                    this.removeCondition(groupIndex, condIndex);
                    this.applyFilters();
                    return;
                }
                currentIndex++;
            }
        }
    }

    updateFilterBadge() {
        const badge = document.getElementById('activeFilterBadge');
        const count = this.filters.reduce((sum, group) => sum + group.conditions.length, 0);
        
        if (count > 0 && badge) {
            badge.textContent = count;
            badge.classList.remove('hidden');
        } else if (badge) {
            badge.classList.add('hidden');
        }
    }

    clearAllFilters() {
        this.filters = [];
        this.activeFilterId = null;
        this.addFilterGroup();
        this.renderFilterBuilder();
        this.updateFilterBadge();
        this.renderActiveFilters();
        
        // Clear global filter query
        window.activeFilterQuery = null;
    }

    closeFilterBuilder() {
        const modal = document.getElementById('filterBuilderModal');
        const contentEl = document.getElementById('filterModalContent');
        
        if (modal && contentEl) {
            // Animate out
            contentEl.style.transform = 'scale(0.95)';
            contentEl.style.opacity = '0';
            
            setTimeout(() => {
                modal.classList.add('hidden');
                modal.classList.remove('flex');
            }, 200);
        }
    }

    // Saved filters
    async saveCurrentFilter() {
        const name = prompt('Filtre adı:');
        if (!name) return;

        const filterData = {
            name: name,
            filters: this.filters,
            is_shared: false
        };

        try {
            const response = await fetch('/api/v1/contacts/filters', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(filterData)
            });

            if (response.ok) {
                const saved = await response.json();
                this.savedFilters.push(saved);
                this.renderSavedFilterTabs();
                this.renderQuickFilters();
                showToast('Filtre kaydedildi', 'success');
            }
        } catch (error) {
            console.error('Filter save error:', error);
            showToast('Filtre kaydedilemedi', 'error');
        }
    }

    async loadSavedFilters() {
        try {
            const response = await fetch('/api/v1/contacts/filters');
            if (response.ok) {
                this.savedFilters = await response.json();
                this.renderQuickFilters();
            } else if (response.status === 404) {
                // Endpoint doesn't exist yet, ignore
                console.log('Saved filters endpoint not available yet');
                this.savedFilters = [];
            }
        } catch (error) {
            console.log('Could not load saved filters:', error.message);
            this.savedFilters = [];
        }
    }

    renderSavedFilterTabs() {
        const container = document.getElementById('savedFilterTabs');
        if (!container) return;

        container.innerHTML = this.savedFilters.map(filter => `
            <button onclick="filterSystem.loadSavedFilter(${filter.id})" 
                    class="px-3 py-2 text-xs font-semibold rounded-lg transition-all duration-200 ${
                        this.activeFilterId === filter.id 
                            ? 'bg-brand-600 text-white shadow-md' 
                            : 'text-gray-600 hover:bg-white hover:text-gray-800 border border-gray-200 hover:border-gray-300 hover:shadow-sm'
                    }">
                <i class="fas fa-bookmark text-xs mr-1"></i>
                ${filter.name}
            </button>
        `).join('');
    }

    renderQuickFilters() {
        const container = document.getElementById('quickFiltersContainer');
        if (!container) return;

        const quickFilters = [
            { id: 'high_score', label: 'Yüksek Skor', icon: 'star', color: 'purple' },
            { id: 'recent', label: 'Son Eklenenler', icon: 'clock', color: 'blue' },
            { id: 'no_company', label: 'Şirketsiz', icon: 'building', color: 'gray' }
        ];

        container.innerHTML = quickFilters.map(filter => `
            <button onclick="filterSystem.applyQuickFilter('${filter.id}')" 
                    class="quick-filter-btn px-3 py-1.5 bg-white border border-gray-200 rounded-lg text-xs font-semibold text-gray-700 hover:border-${filter.color}-500 hover:text-${filter.color}-600 hover:bg-${filter.color}-50 transition-all flex items-center gap-1.5">
                <i class="fas fa-${filter.icon} text-xs"></i>
                ${filter.label}
            </button>
        `).join('');
    }

    async applyQuickFilter(filterId) {
        // Clear existing filters
        this.filters = [];
        
        // Define quick filter presets (backend format)
        const quickFilters = {
            'high_score': {
                filters: [
                    { field: 'lead_score', operator: 'greater_than_or_equal', value: 80 }
                ]
            },
            'recent': {
                filters: [
                    { field: 'created_at', operator: 'greater_than', value: new Date(Date.now() - 7 * 24 * 60 * 60 * 1000).toISOString().split('T')[0] }
                ]
            },
            'no_company': {
                filters: [
                    { field: 'company_id', operator: 'is_null', value: null }
                ]
            }
        };
        
        // Check if it's a saved filter
        if (filterId.startsWith('saved_')) {
            const savedFilterId = parseInt(filterId.replace('saved_', ''));
            await this.loadSavedFilter(savedFilterId);
            await this.applyFilters();
            return;
        }
        
        // Apply quick filter
        const filterConfig = quickFilters[filterId];
        if (filterConfig) {
            await window.loadContactsWithFilters(filterConfig);
            this.updateFilterBadge();
            
            // Show active filter chip
            const container = document.getElementById('activeFiltersDisplay');
            const list = document.getElementById('activeFiltersList');
            if (container && list) {
                container.classList.remove('hidden');
                const filterLabels = {
                    'high_score': 'Yüksek Skor (≥80)',
                    'recent': 'Son 7 Gün',
                    'no_company': 'Şirketsiz'
                };
                list.innerHTML = `
                    <div class="flex items-center gap-1.5 px-2.5 py-1 bg-brand-50 border border-brand-200 rounded-lg text-xs">
                        <span class="font-semibold text-brand-700">${filterLabels[filterId]}</span>
                        <button onclick="filterSystem.clearAllFilters(); loadContacts();" class="ml-1 text-brand-600 hover:text-brand-800">
                            <i class="fas fa-times text-[10px]"></i>
                        </button>
                    </div>
                `;
            }
        }
    }

    async loadSavedFilter(filterId) {
        const filter = this.savedFilters.find(f => f.id === filterId);
        if (filter) {
            this.filters = JSON.parse(JSON.stringify(filter.filters));
            this.activeFilterId = filterId;
            this.renderFilterBuilder();
        }
    }
}

// Initialize
const filterSystem = new FilterSystem();
window.filterSystem = filterSystem;
