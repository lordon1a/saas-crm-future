/**
 * Advanced Filter Component - HubSpot/Pipedrive Style
 * Modern, professional filtering system with multiple criteria support
 */

class AdvancedFilter {
    constructor(entityType, containerId) {
        this.entityType = entityType; // 'contact' or 'company'
        this.containerId = containerId;
        this.filterGroups = [];
        this.activeFilters = [];
        this.savedFilters = [];
        
        // Field definitions
        this.fields = this.getFieldDefinitions();
        
        // Operator definitions
        this.operators = {
            text: [
                { value: 'contains', label: 'içerir', needsValue: true },
                { value: 'not_contains', label: 'içermez', needsValue: true },
                { value: 'equals', label: 'eşittir', needsValue: true },
                { value: 'not_equals', label: 'eşit değildir', needsValue: true },
                { value: 'starts_with', label: 'ile başlar', needsValue: true },
                { value: 'ends_with', label: 'ile biter', needsValue: true },
                { value: 'is_null', label: 'boş', needsValue: false },
                { value: 'is_not_null', label: 'dolu', needsValue: false }
            ],
            number: [
                { value: 'equals', label: '=', needsValue: true },
                { value: 'not_equals', label: '≠', needsValue: true },
                { value: 'greater_than', label: '>', needsValue: true },
                { value: 'less_than', label: '<', needsValue: true },
                { value: 'greater_than_or_equal', label: '≥', needsValue: true },
                { value: 'less_than_or_equal', label: '≤', needsValue: true },
                { value: 'between', label: 'arasında', needsValue: true, isBetween: true },
                { value: 'is_null', label: 'boş', needsValue: false },
                { value: 'is_not_null', label: 'dolu', needsValue: false }
            ],
            date: [
                { value: 'equals', label: 'eşittir', needsValue: true },
                { value: 'greater_than', label: 'sonra', needsValue: true },
                { value: 'less_than', label: 'önce', needsValue: true },
                { value: 'between', label: 'arasında', needsValue: true, isBetween: true },
                { value: 'is_null', label: 'boş', needsValue: false },
                { value: 'is_not_null', label: 'dolu', needsValue: false }
            ],
            select: [
                { value: 'equals', label: 'eşittir', needsValue: true },
                { value: 'not_equals', label: 'eşit değildir', needsValue: true },
                { value: 'in', label: 'içinde', needsValue: true, isMulti: true },
                { value: 'not_in', label: 'içinde değil', needsValue: true, isMulti: true },
                { value: 'is_null', label: 'boş', needsValue: false },
                { value: 'is_not_null', label: 'dolu', needsValue: false }
            ],
            boolean: [
                { value: 'equals', label: 'eşittir', needsValue: true }
            ]
        };
    }
    
    getFieldDefinitions() {
        if (this.entityType === 'contact') {
            return [
                { id: 'first_name', label: 'Ad', type: 'text', icon: 'user' },
                { id: 'last_name', label: 'Soyad', type: 'text', icon: 'user' },
                { id: 'email', label: 'E-posta', type: 'text', icon: 'envelope' },
                { id: 'phone', label: 'Telefon', type: 'text', icon: 'phone' },
                { id: 'whatsapp_phone', label: 'WhatsApp', type: 'text', icon: 'whatsapp' },
                { id: 'job_title', label: 'Unvan', type: 'text', icon: 'briefcase' },
                { id: 'company_id', label: 'Şirket ID', type: 'number', icon: 'building' },
                { id: 'role', label: 'Rol', type: 'select', icon: 'user-tag', 
                  options: ['Decision Maker', 'Champion', 'Influencer', 'Blocker', 'User'] },
                { id: 'lead_score', label: 'Lead Score', type: 'number', icon: 'star' },
                { id: 'is_starred', label: 'Yıldızlı', type: 'boolean', icon: 'star' },
                { id: 'created_at', label: 'Oluşturulma Tarihi', type: 'date', icon: 'calendar' },
                { id: 'updated_at', label: 'Güncellenme Tarihi', type: 'date', icon: 'calendar' }
            ];
        } else {
            return [
                { id: 'name', label: 'Şirket Adı', type: 'text', icon: 'building' },
                { id: 'industry', label: 'Sektör', type: 'text', icon: 'industry' },
                { id: 'size', label: 'Büyüklük', type: 'select', icon: 'users',
                  options: ['1-10', '11-50', '51-200', '201-500', '500+'] },
                { id: 'website', label: 'Website', type: 'text', icon: 'globe' },
                { id: 'phone', label: 'Telefon', type: 'text', icon: 'phone' },
                { id: 'address', label: 'Adres', type: 'text', icon: 'map-marker' },
                { id: 'parent_company_id', label: 'Ana Şirket ID', type: 'number', icon: 'building' },
                { id: 'created_at', label: 'Oluşturulma Tarihi', type: 'date', icon: 'calendar' },
                { id: 'updated_at', label: 'Güncellenme Tarihi', type: 'date', icon: 'calendar' }
            ];
        }
    }
    
    init() {
        this.renderFilterButton();
        this.loadSavedFilters();
    }
    
    renderFilterButton() {
        const container = document.getElementById(this.containerId);
        if (!container) return;
        
        const buttonHtml = `
            <button id="advancedFilterBtn" onclick="advancedFilter.openFilterModal()" 
                    class="px-4 py-2 bg-white border border-gray-300 rounded-lg text-sm font-semibold text-gray-700 hover:bg-gray-50 hover:border-brand-400 hover:text-brand-700 transition-all duration-200 flex items-center gap-2 hover:shadow-md relative overflow-hidden group">
                <div class="absolute inset-0 bg-brand-100 opacity-0 group-hover:opacity-10 transition-opacity duration-300"></div>
                <i class="fas fa-filter text-sm relative z-10"></i>
                <span class="relative z-10">Filtreler</span>
                <span id="filterCountBadge" class="hidden ml-1 px-2 py-0.5 bg-brand-600 text-white text-xs font-bold rounded-full min-w-[20px] text-center animate-pulse-badge relative z-10">0</span>
                <i class="fas fa-chevron-down text-xs ml-1 transition-transform duration-200 group-hover:rotate-180 relative z-10" id="filterChevron"></i>
            </button>
        `;
        
        container.innerHTML = buttonHtml;
    }
    
    openFilterModal() {
        if (!document.getElementById('advancedFilterModal')) {
            this.createFilterModal();
        }
        
        if (this.filterGroups.length === 0) {
            this.addFilterGroup();
        }
        
        this.renderFilterModal();
        
        const modal = document.getElementById('advancedFilterModal');
        const panel = modal.querySelector('.bg-white');
        
        // Set initial hidden state
        modal.style.opacity = '0';
        if (panel) {
            panel.style.transform = 'scale(0.9) translateY(-20px)';
            panel.style.opacity = '0';
        }
        
        // Show modal
        modal.classList.remove('hidden');
        modal.classList.add('flex');
        
        // Add ESC key listener
        this.escKeyHandler = (e) => {
            if (e.key === 'Escape') {
                this.closeFilterModal();
            }
        };
        document.addEventListener('keydown', this.escKeyHandler);
        
        // Trigger smooth animation after a tiny delay
        setTimeout(() => {
            modal.style.transition = 'opacity 0.25s cubic-bezier(0.16, 1, 0.3, 1)';
            modal.style.opacity = '1';
            
            if (panel) {
                panel.style.transition = 'all 0.35s cubic-bezier(0.16, 1, 0.3, 1)';
                panel.style.transform = 'scale(1) translateY(0)';
                panel.style.opacity = '1';
            }
        }, 10);
    }
    
    createFilterModal() {
        const modalHtml = `
            <div id="advancedFilterModal" class="hidden fixed inset-0 bg-slate-900/40 backdrop-blur-sm z-50 items-center justify-center p-4" onclick="if(event.target === this) advancedFilter.closeFilterModal()">
                <div class="bg-white rounded-2xl shadow-2xl w-full max-w-5xl max-h-[90vh] overflow-hidden flex flex-col" onclick="event.stopPropagation()" style="will-change: transform, opacity;">
                    <div class="flex flex-col h-full">
                        <!-- Header -->
                        <div class="px-6 py-4 border-b border-gray-100 flex items-center justify-between flex-shrink-0 bg-gradient-to-r from-white to-gray-50">
                            <div class="flex items-center gap-3">
                                <div class="w-10 h-10 bg-gradient-to-br from-brand-600 to-purple-600 rounded-xl flex items-center justify-center shadow-lg">
                                    <i class="fas fa-filter text-white"></i>
                                </div>
                                <div>
                                    <h3 class="text-lg font-bold text-gray-900 flex items-center gap-2">
                                        Gelişmiş Filtreler
                                    </h3>
                                    <p class="text-xs text-gray-500 mt-0.5">Detaylı arama kriterleri ile filtreleyin</p>
                                </div>
                            </div>
                            <button onclick="advancedFilter.closeFilterModal()" 
                                    class="w-9 h-9 rounded-lg bg-white border border-gray-200 text-gray-400 hover:text-gray-700 hover:bg-gray-50 hover:border-gray-300 transition-all duration-200 flex items-center justify-center hover:rotate-90">
                                <i class="fas fa-times text-sm"></i>
                            </button>
                        </div>
                    </div>
                    
                    <!-- Quick Filters -->
                    <div class="px-6 py-3 border-b border-gray-100 flex items-center gap-2 overflow-x-auto flex-shrink-0 bg-gray-50/50">
                        <span class="text-xs font-semibold text-gray-600 whitespace-nowrap">Hızlı Filtreler:</span>
                        <div id="quickFiltersBar" class="flex items-center gap-2">
                            <!-- Quick filters will be rendered here -->
                        </div>
                    </div>
                    
                    <!-- Filter Groups -->
                    <div class="flex-1 overflow-y-auto p-6">
                        <div id="filterGroupsContainer" class="space-y-4">
                            <!-- Filter groups will be rendered here -->
                        </div>
                        
                        <button onclick="advancedFilter.addFilterGroup()" 
                                class="mt-4 px-4 py-2.5 border-2 border-dashed border-gray-300 text-gray-600 rounded-lg hover:border-brand-500 hover:text-brand-700 hover:bg-brand-50 transition-all duration-200 flex items-center gap-2 w-full justify-center hover:shadow-sm">
                            <i class="fas fa-plus text-sm"></i>
                            <span class="font-semibold">Yeni Filtre Grubu Ekle</span>
                        </button>
                    </div>
                    
                    <!-- Footer -->
                    <div class="px-6 py-4 border-t border-gray-100 flex items-center justify-between flex-shrink-0 bg-gray-50/30">
                        <div class="flex items-center gap-2">
                            <button onclick="advancedFilter.saveFilter()" 
                                    class="px-4 py-2.5 text-sm font-semibold text-gray-700 hover:bg-white border border-gray-200 hover:border-gray-300 rounded-lg transition-all duration-200 flex items-center gap-2 hover:shadow-sm">
                                <i class="fas fa-bookmark text-xs"></i>
                                <span>Kaydet</span>
                            </button>
                            <button onclick="advancedFilter.clearAllFilters()" 
                                    class="px-4 py-2.5 text-sm font-semibold text-red-600 hover:bg-red-50 border border-transparent hover:border-red-200 rounded-lg transition-all duration-200 hover:shadow-sm">
                                <i class="fas fa-eraser text-xs"></i>
                                <span>Temizle</span>
                            </button>
                        </div>
                        <div class="flex gap-3">
                            <button onclick="advancedFilter.closeFilterModal()" 
                                    class="px-6 py-2.5 bg-white border border-gray-300 text-gray-700 font-semibold rounded-lg hover:bg-gray-50 hover:border-gray-400 transition-all duration-200">
                                İptal
                            </button>
                            <button onclick="advancedFilter.applyFilters()" 
                                    class="px-6 py-2.5 bg-gradient-to-r from-brand-600 to-purple-600 text-white font-semibold rounded-lg hover:from-brand-700 hover:to-purple-700 transition-all duration-200 shadow-lg hover:shadow-xl flex items-center gap-2 hover:scale-105 active:scale-100">
                                <i class="fas fa-check text-sm"></i>
                                <span>Uygula</span>
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        `;
        
        document.body.insertAdjacentHTML('beforeend', modalHtml);
        this.renderQuickFilters();
    }
    
    renderQuickFilters() {
        const container = document.getElementById('quickFiltersBar');
        if (!container) return;
        
        const quickFilters = this.entityType === 'contact' ? [
            { id: 'high_score', label: 'Yüksek Skor', icon: 'star', color: 'purple' },
            { id: 'recent', label: 'Son Eklenenler', icon: 'clock', color: 'blue' },
            { id: 'no_company', label: 'Şirketsiz', icon: 'building', color: 'gray' },
            { id: 'starred', label: 'Yıldızlı', icon: 'star', color: 'yellow' }
        ] : [
            { id: 'recent', label: 'Son Eklenenler', icon: 'clock', color: 'blue' },
            { id: 'large', label: 'Büyük Şirketler', icon: 'building', color: 'green' },
            { id: 'no_parent', label: 'Ana Şirketsiz', icon: 'sitemap', color: 'gray' }
        ];
        
        container.innerHTML = quickFilters.map(qf => `
            <button onclick="advancedFilter.applyQuickFilter('${qf.id}')" 
                    class="px-3 py-1.5 bg-white border border-gray-200 rounded-lg text-xs font-semibold text-gray-700 hover:border-${qf.color}-500 hover:text-${qf.color}-600 hover:bg-${qf.color}-50 transition-all flex items-center gap-1.5 whitespace-nowrap">
                <i class="fas fa-${qf.icon}"></i>
                ${qf.label}
            </button>
        `).join('');
    }
    
    renderFilterModal() {
        const container = document.getElementById('filterGroupsContainer');
        if (!container) return;
        
        container.innerHTML = this.filterGroups.map((group, groupIndex) => 
            this.renderFilterGroup(group, groupIndex)
        ).join('');
    }
    
    renderFilterGroup(group, groupIndex) {
        const isFirst = groupIndex === 0;
        
        return `
            <div class="bg-white rounded-xl p-5 border border-gray-200 shadow-sm hover:shadow-md transition-all duration-300 hover:border-brand-200">
                ${!isFirst ? `
                    <div class="flex items-center justify-between mb-4">
                        <div class="flex items-center gap-2">
                            <span class="text-xs font-medium text-gray-500 uppercase tracking-wide">Mantık</span>
                            <select onchange="advancedFilter.updateGroupLogic(${groupIndex}, this.value)" 
                                    class="px-3 py-2 bg-gradient-to-b from-white to-gray-50 border border-gray-300 rounded-lg text-sm font-semibold text-gray-700 hover:border-brand-400 focus:border-brand-500 focus:ring-2 focus:ring-brand-200 transition-all duration-200">
                                <option value="AND" ${group.logic === 'AND' ? 'selected' : ''}>VE (AND)</option>
                                <option value="OR" ${group.logic === 'OR' ? 'selected' : ''}>VEYA (OR)</option>
                            </select>
                        </div>
                        <button onclick="advancedFilter.removeFilterGroup(${groupIndex})" 
                                class="px-3 py-2 text-red-600 hover:bg-red-50 rounded-lg transition-all duration-200 flex items-center gap-1.5 hover:scale-105 active:scale-95">
                            <i class="fas fa-trash text-sm"></i>
                            <span class="text-xs font-semibold">Grubu Sil</span>
                        </button>
                    </div>
                ` : ''}
                
                <div class="space-y-3">
                    ${group.conditions.map((condition, condIndex) => 
                        this.renderCondition(condition, groupIndex, condIndex)
                    ).join('')}
                </div>
                
                <button onclick="advancedFilter.addCondition(${groupIndex})" 
                        class="mt-4 px-4 py-2 text-sm font-semibold text-brand-600 hover:bg-brand-50 hover:text-brand-700 rounded-lg transition-all duration-200 flex items-center gap-2 border border-dashed border-brand-300 hover:border-brand-500 w-full justify-center hover:shadow-sm">
                    <i class="fas fa-plus text-xs"></i>
                    <span>Koşul Ekle</span>
                </button>
            </div>
        `;
    }
    
    renderCondition(condition, groupIndex, condIndex) {
        const field = this.fields.find(f => f.id === condition.field) || this.fields[0];
        const operators = this.operators[field.type] || this.operators.text;
        const selectedOperator = operators.find(op => op.value === condition.operator);
        
        return `
            <div class="flex items-start gap-3 bg-gradient-to-r from-gray-50 to-white p-4 rounded-lg border border-gray-200 hover:border-brand-300 transition-all duration-200 hover:shadow-sm group">
                <!-- Field Select -->
                <div class="flex-1">
                    <select onchange="advancedFilter.updateConditionField(${groupIndex}, ${condIndex}, this.value)" 
                            class="w-full px-3 py-2.5 bg-white border border-gray-300 rounded-lg text-sm font-medium text-gray-700 hover:border-brand-400 focus:border-brand-500 focus:ring-2 focus:ring-brand-200 transition-all duration-200 cursor-pointer">
                        ${this.fields.map(f => `
                            <option value="${f.id}" ${f.id === condition.field ? 'selected' : ''}>
                                ${f.label}
                            </option>
                        `).join('')}
                    </select>
                </div>
                
                <!-- Operator Select -->
                <div class="flex-1">
                    <select onchange="advancedFilter.updateConditionOperator(${groupIndex}, ${condIndex}, this.value)" 
                            class="w-full px-3 py-2.5 bg-white border border-gray-300 rounded-lg text-sm font-medium text-gray-700 hover:border-brand-400 focus:border-brand-500 focus:ring-2 focus:ring-brand-200 transition-all duration-200 cursor-pointer">
                        ${operators.map(op => `
                            <option value="${op.value}" ${op.value === condition.operator ? 'selected' : ''}>
                                ${op.label}
                            </option>
                        `).join('')}
                    </select>
                </div>
                
                <!-- Value Input -->
                <div class="flex-1">
                    ${this.renderValueInput(condition, groupIndex, condIndex, field, selectedOperator)}
                </div>
                
                <!-- Remove Button -->
                <button onclick="advancedFilter.removeCondition(${groupIndex}, ${condIndex})" 
                        class="p-2.5 text-red-600 hover:bg-red-50 rounded-lg transition-all duration-200 hover:scale-110 active:scale-95 opacity-0 group-hover:opacity-100">
                    <i class="fas fa-times text-sm"></i>
                </button>
            </div>
        `;
    }
    
    renderValueInput(condition, groupIndex, condIndex, field, operator) {
        if (!operator || !operator.needsValue) {
            return '<div class="text-xs text-gray-400 italic py-2">Değer gerekmiyor</div>';
        }
        
        const inputId = `filter_value_${groupIndex}_${condIndex}`;
        
        // Between operator
        if (operator.isBetween) {
            const values = Array.isArray(condition.value) ? condition.value : ['', ''];
            if (field.type === 'number') {
                return `
                    <div class="flex gap-1">
                        <input type="number" value="${values[0] || ''}" 
                               onchange="advancedFilter.updateConditionValue(${groupIndex}, ${condIndex}, [this.value, this.nextElementSibling.value])"
                               placeholder="Min" class="w-1/2 px-2 py-2 bg-gray-50 border border-gray-200 rounded-lg text-sm">
                        <input type="number" value="${values[1] || ''}"
                               onchange="advancedFilter.updateConditionValue(${groupIndex}, ${condIndex}, [this.previousElementSibling.value, this.value])"
                               placeholder="Max" class="w-1/2 px-2 py-2 bg-gray-50 border border-gray-200 rounded-lg text-sm">
                    </div>
                `;
            } else if (field.type === 'date') {
                return `
                    <div class="flex gap-1">
                        <input type="date" value="${values[0] || ''}"
                               onchange="advancedFilter.updateConditionValue(${groupIndex}, ${condIndex}, [this.value, this.nextElementSibling.value])"
                               class="w-1/2 px-2 py-2 bg-gray-50 border border-gray-200 rounded-lg text-sm">
                        <input type="date" value="${values[1] || ''}"
                               onchange="advancedFilter.updateConditionValue(${groupIndex}, ${condIndex}, [this.previousElementSibling.value, this.value])"
                               class="w-1/2 px-2 py-2 bg-gray-50 border border-gray-200 rounded-lg text-sm">
                    </div>
                `;
            }
        }
        
        // Multi-select for 'in' and 'not_in'
        if (operator.isMulti && field.type === 'select' && field.options) {
            const selectedValues = Array.isArray(condition.value) ? condition.value : [];
            return `
                <select id="${inputId}" multiple size="3"
                        onchange="advancedFilter.updateConditionValue(${groupIndex}, ${condIndex}, Array.from(this.selectedOptions).map(o => o.value))"
                        class="w-full px-2 py-1 bg-gray-50 border border-gray-200 rounded-lg text-sm">
                    ${field.options.map(opt => `
                        <option value="${opt}" ${selectedValues.includes(opt) ? 'selected' : ''}>${opt}</option>
                    `).join('')}
                </select>
            `;
        }
        
        // Regular inputs
        if (field.type === 'select' && field.options) {
            return `
                <select id="${inputId}" onchange="advancedFilter.updateConditionValue(${groupIndex}, ${condIndex}, this.value)"
                        class="w-full px-3 py-2 bg-gray-50 border border-gray-200 rounded-lg text-sm">
                    <option value="">Seçiniz...</option>
                    ${field.options.map(opt => `
                        <option value="${opt}" ${opt === condition.value ? 'selected' : ''}>${opt}</option>
                    `).join('')}
                </select>
            `;
        } else if (field.type === 'boolean') {
            return `
                <select id="${inputId}" onchange="advancedFilter.updateConditionValue(${groupIndex}, ${condIndex}, this.value === 'true')"
                        class="w-full px-3 py-2 bg-gray-50 border border-gray-200 rounded-lg text-sm">
                    <option value="true" ${condition.value === true ? 'selected' : ''}>Evet</option>
                    <option value="false" ${condition.value === false ? 'selected' : ''}>Hayır</option>
                </select>
            `;
        } else if (field.type === 'number') {
            return `
                <input type="number" id="${inputId}" value="${condition.value || ''}"
                       onchange="advancedFilter.updateConditionValue(${groupIndex}, ${condIndex}, parseFloat(this.value))"
                       placeholder="Değer" class="w-full px-3 py-2 bg-gray-50 border border-gray-200 rounded-lg text-sm">
            `;
        } else if (field.type === 'date') {
            return `
                <input type="date" id="${inputId}" value="${condition.value || ''}"
                       onchange="advancedFilter.updateConditionValue(${groupIndex}, ${condIndex}, this.value)"
                       class="w-full px-3 py-2 bg-gray-50 border border-gray-200 rounded-lg text-sm">
            `;
        } else {
            return `
                <input type="text" id="${inputId}" value="${condition.value || ''}"
                       onchange="advancedFilter.updateConditionValue(${groupIndex}, ${condIndex}, this.value)"
                       placeholder="Değer" class="w-full px-3 py-2 bg-gray-50 border border-gray-200 rounded-lg text-sm">
            `;
        }
    }
    
    // Filter manipulation methods
    addFilterGroup() {
        this.filterGroups.push({
            logic: 'AND',
            conditions: [
                { field: this.fields[0].id, operator: this.operators[this.fields[0].type][0].value, value: '' }
            ]
        });
        this.renderFilterModal();
    }
    
    removeFilterGroup(groupIndex) {
        this.filterGroups.splice(groupIndex, 1);
        if (this.filterGroups.length === 0) {
            this.addFilterGroup();
        }
        this.renderFilterModal();
    }
    
    updateGroupLogic(groupIndex, logic) {
        this.filterGroups[groupIndex].logic = logic;
    }
    
    addCondition(groupIndex) {
        this.filterGroups[groupIndex].conditions.push({
            field: this.fields[0].id,
            operator: this.operators[this.fields[0].type][0].value,
            value: ''
        });
        this.renderFilterModal();
    }
    
    removeCondition(groupIndex, condIndex) {
        this.filterGroups[groupIndex].conditions.splice(condIndex, 1);
        if (this.filterGroups[groupIndex].conditions.length === 0) {
            this.removeFilterGroup(groupIndex);
        } else {
            this.renderFilterModal();
        }
    }
    
    updateConditionField(groupIndex, condIndex, fieldId) {
        const field = this.fields.find(f => f.id === fieldId);
        this.filterGroups[groupIndex].conditions[condIndex].field = fieldId;
        this.filterGroups[groupIndex].conditions[condIndex].operator = this.operators[field.type][0].value;
        this.filterGroups[groupIndex].conditions[condIndex].value = '';
        this.renderFilterModal();
    }
    
    updateConditionOperator(groupIndex, condIndex, operator) {
        this.filterGroups[groupIndex].conditions[condIndex].operator = operator;
        this.renderFilterModal();
    }
    
    updateConditionValue(groupIndex, condIndex, value) {
        this.filterGroups[groupIndex].conditions[condIndex].value = value;
    }
    
    buildFilterQuery() {
        // Build filter groups with proper logic
        const validGroups = [];
        
        this.filterGroups.forEach(group => {
            const validConditions = [];
            
            group.conditions.forEach(condition => {
                const field = this.fields.find(f => f.id === condition.field);
                if (!field) return;
                
                const operator = this.operators[field.type]?.find(op => op.value === condition.operator);
                if (!operator) return;
                
                // Check if value is required and provided
                if (operator.needsValue) {
                    if (condition.value === '' || condition.value === null || condition.value === undefined) {
                        return; // Skip invalid conditions
                    }
                }
                
                validConditions.push({
                    field: condition.field,
                    operator: condition.operator,
                    value: condition.value
                });
            });
            
            if (validConditions.length > 0) {
                validGroups.push({
                    logic: group.logic || 'AND',
                    conditions: validConditions
                });
            }
        });
        
        if (validGroups.length === 0) {
            return null;
        }
        
        // If only one group, return simple filters array for backward compatibility
        if (validGroups.length === 1) {
            return { filters: validGroups[0].conditions };
        }
        
        // Multiple groups - return with group logic
        return {
            groups: validGroups,
            groupLogic: 'OR' // Groups are combined with OR by default
        };
    }
    
    async applyFilters() {
        const filterQuery = this.buildFilterQuery();
        
        if (!filterQuery) {
            showToast('Lütfen en az bir filtre kriteri ekleyin', 'warning');
            return;
        }
        
        this.activeFilters = filterQuery.filters;
        this.closeFilterModal();
        this.updateFilterBadge();
        this.renderActiveFilterChips();
        
        // Trigger reload with filters
        if (typeof window.loadWithFilters === 'function') {
            await window.loadWithFilters(filterQuery);
        } else if (this.entityType === 'contact' && typeof loadContacts === 'function') {
            window.activeContactFilters = filterQuery;
            await loadContacts();
        } else if (this.entityType === 'company' && typeof loadCompanies === 'function') {
            window.activeCompanyFilters = filterQuery;
            await loadCompanies();
        }
        
        showToast(`${this.activeFilters.length} filtre uygulandı`, 'success');
    }
    
    async applyQuickFilter(filterId) {
        try {
            const response = await fetch(`/api/v1/${this.entityType}s?quick_filter=${filterId}&page=1&per_page=50`);
            if (!response.ok) throw new Error('Quick filter failed');
            
            const data = await response.json();
            
            this.activeFilters = data.applied_filters?.filters || [];
            this.closeFilterModal();
            this.updateFilterBadge();
            this.renderActiveFilterChips();
            
            // Trigger reload
            if (this.entityType === 'contact' && typeof loadContacts === 'function') {
                window.activeContactFilters = data.applied_filters;
                await loadContacts();
            } else if (this.entityType === 'company' && typeof loadCompanies === 'function') {
                window.activeCompanyFilters = data.applied_filters;
                await loadCompanies();
            }
            
            showToast('Hızlı filtre uygulandı', 'success');
        } catch (error) {
            console.error('Quick filter error:', error);
            showToast('Filtre uygulanamadı', 'error');
        }
    }
    
    clearAllFilters() {
        this.filterGroups = [];
        this.activeFilters = [];
        this.addFilterGroup();
        this.renderFilterModal();
        this.updateFilterBadge();
        this.renderActiveFilterChips();
        
        // Clear global filters
        if (this.entityType === 'contact') {
            window.activeContactFilters = null;
            if (typeof loadContacts === 'function') loadContacts();
        } else {
            window.activeCompanyFilters = null;
            if (typeof loadCompanies === 'function') loadCompanies();
        }
    }
    
    updateFilterBadge() {
        const badge = document.getElementById('filterCountBadge');
        if (!badge) return;
        
        if (this.activeFilters.length > 0) {
            const wasHidden = badge.classList.contains('hidden');
            badge.textContent = this.activeFilters.length;
            badge.classList.remove('hidden');
            
            // Pulse animation when badge appears or count changes
            if (wasHidden || badge.dataset.lastCount !== String(this.activeFilters.length)) {
                badge.classList.add('animate-pulse-badge');
                setTimeout(() => badge.classList.remove('animate-pulse-badge'), 500);
            }
            badge.dataset.lastCount = this.activeFilters.length;
        } else {
            badge.classList.add('hidden');
        }
    }
    
    renderActiveFilterChips() {
        let container = document.getElementById('activeFilterChips');
        if (!container) {
            // Create container if it doesn't exist
            const toolbar = document.querySelector('.bg-white.border-b.border-slate-200.px-6.py-3');
            if (toolbar) {
                const chipsHtml = '<div id="activeFilterChips" class="hidden mt-3 flex items-center gap-2 flex-wrap"></div>';
                toolbar.insertAdjacentHTML('beforeend', chipsHtml);
                container = document.getElementById('activeFilterChips');
            }
        }
        
        if (!container) return;
        
        if (this.activeFilters.length === 0) {
            container.classList.add('hidden');
            return;
        }
        
        container.classList.remove('hidden');
        container.innerHTML = this.activeFilters.map((filter, index) => {
            const field = this.fields.find(f => f.id === filter.field);
            const operator = this.operators[field?.type || 'text'].find(op => op.value === filter.operator);
            
            return `
                <div class="filter-chip flex items-center gap-1.5 px-3 py-1.5 bg-brand-50 border border-brand-200 rounded-lg text-xs hover:shadow-md transition-all duration-200" style="animation-delay: ${index * 0.05}s">
                    <i class="fas fa-${field?.icon || 'filter'} text-brand-600 transition-transform duration-200"></i>
                    <span class="font-semibold text-brand-700">${field?.label || filter.field}</span>
                    <span class="text-brand-600">${operator?.label || filter.operator}</span>
                    ${filter.value ? `<span class="font-semibold text-brand-800">${Array.isArray(filter.value) ? filter.value.join(', ') : filter.value}</span>` : ''}
                    <button onclick="advancedFilter.removeActiveFilter(${index})" class="ml-1 text-brand-600 hover:text-brand-800 hover:scale-110 transition-all duration-200">
                        <i class="fas fa-times text-[10px]"></i>
                    </button>
                </div>
            `;
        }).join('');
    }
    
    removeActiveFilter(index) {
        this.activeFilters.splice(index, 1);
        this.updateFilterBadge();
        this.renderActiveFilterChips();
        
        if (this.activeFilters.length === 0) {
            this.clearAllFilters();
        } else {
            this.applyFilters();
        }
    }
    
    async saveFilter() {
        const name = prompt('Filtre adı:');
        if (!name) return;
        
        const filterQuery = this.buildFilterQuery();
        if (!filterQuery) {
            showToast('Kaydedilecek filtre yok', 'warning');
            return;
        }
        
        try {
            const response = await fetch('/api/v1/saved-filters', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    name: name,
                    entity_type: this.entityType,
                    filter_config: filterQuery,
                    is_shared: false
                })
            });
            
            if (response.ok) {
                const data = await response.json();
                showToast('Filtre başarıyla kaydedildi', 'success');
                await this.loadSavedFilters();
            } else {
                const errorData = await response.json();
                showToast(errorData.error || 'Filtre kaydedilemedi', 'error');
            }
        } catch (error) {
            console.error('Save filter error:', error);
            showToast('Filtre kaydedilemedi', 'error');
        }
    }
    
    async loadSavedFilters() {
        try {
            const response = await fetch(`/api/v1/saved-filters?entity_type=${this.entityType}`);
            if (response.ok) {
                const data = await response.json();
                // Combine user filters and shared filters
                this.savedFilters = [
                    ...(data.user_filters || []),
                    ...(data.shared_filters || [])
                ];
            }
        } catch (error) {
            console.log('Could not load saved filters:', error);
        }
    }
    
    closeFilterModal() {
        const modal = document.getElementById('advancedFilterModal');
        if (modal) {
            // Remove ESC key listener
            if (this.escKeyHandler) {
                document.removeEventListener('keydown', this.escKeyHandler);
                this.escKeyHandler = null;
            }
            
            const panel = modal.querySelector('.bg-white');
            
            // Smooth fade-out and scale animation with matching easing
            modal.style.transition = 'opacity 0.2s cubic-bezier(0.4, 0, 1, 1)';
            modal.style.opacity = '0';
            
            if (panel) {
                panel.style.transition = 'all 0.25s cubic-bezier(0.4, 0, 1, 1)';
                panel.style.transform = 'scale(0.92) translateY(-15px)';
                panel.style.opacity = '0';
            }
            
            setTimeout(() => {
                modal.classList.add('hidden');
                modal.classList.remove('flex');
                // Reset styles
                modal.style.opacity = '';
                modal.style.transition = '';
                if (panel) {
                    panel.style.transform = '';
                    panel.style.opacity = '';
                    panel.style.transition = '';
                }
            }, 250);
        }
    }
}

// Helper function for toast notifications
function showToast(message, type = 'info') {
    if (typeof window.showToast === 'function') {
        window.showToast(message, type);
    } else {
        console.log(`[${type.toUpperCase()}] ${message}`);
    }
}
