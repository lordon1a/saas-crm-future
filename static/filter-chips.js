/**
 * FilterChips Component - Modern CRM Filter System
 * Displays active filters as modern chips/badges with color coding
 * 
 * Requirements: 4.1, 4.2, 4.3, 4.4, 4.5, 4.6, 4.7
 */

class FilterChips {
    constructor(containerId) {
        this.containerId = containerId;
        this.container = null;
        this.onRemoveCallback = null;
        
        // Field type to color mapping
        this.colorMap = {
            text: 'bg-blue-100 text-blue-800 border-blue-300 hover:bg-blue-200',
            number: 'bg-green-100 text-green-800 border-green-300 hover:bg-green-200',
            date: 'bg-purple-100 text-purple-800 border-purple-300 hover:bg-purple-200',
            boolean: 'bg-orange-100 text-orange-800 border-orange-300 hover:bg-orange-200',
            select: 'bg-blue-100 text-blue-800 border-blue-300 hover:bg-blue-200'
        };
        
        // Operator labels in Turkish
        this.operatorLabels = {
            'equals': 'Eşittir',
            'not_equals': 'Eşit Değildir',
            'contains': 'İçerir',
            'not_contains': 'İçermez',
            'starts_with': 'İle Başlar',
            'ends_with': 'İle Biter',
            'greater_than': 'Büyüktür',
            'greater_than_or_equal': 'Büyük Eşittir',
            'less_than': 'Küçüktür',
            'less_than_or_equal': 'Küçük Eşittir',
            'between': 'Arasında',
            'in': 'İçinde',
            'not_in': 'İçinde Değil',
            'is_null': 'Boş',
            'is_not_null': 'Boş Değil'
        };
        
        this.init();
    }
    
    /**
     * Initialize component
     */
    init() {
        this.container = document.getElementById(this.containerId);
        if (!this.container) {
            console.error(`FilterChips: Container with id "${this.containerId}" not found`);
        }
    }
    
    /**
     * Render filter chips
     * @param {Object} activeFilters - Object with field names as keys and {operator, value} as values
     * @param {Array} availableFields - Array of field definitions with name, label, type
     */
    render(activeFilters, availableFields = []) {
        if (!this.container) {
            console.error('FilterChips: Container not initialized');
            return;
        }
        
        const filterKeys = Object.keys(activeFilters || {});
        
        // If no active filters, show empty state
        if (filterKeys.length === 0) {
            this.container.innerHTML = '<span class="text-sm text-gray-500">Aktif filtre yok</span>';
            return;
        }
        
        // Build chips HTML
        const chipsHtml = filterKeys.map(field => {
            const filter = activeFilters[field];
            const fieldObj = availableFields.find(f => f.name === field);
            const fieldLabel = fieldObj ? fieldObj.label : field;
            const fieldType = fieldObj ? fieldObj.type : 'text';
            
            return this.createChipHtml(field, fieldLabel, fieldType, filter.operator, filter.value);
        }).join('');
        
        // Render with fade-in animation
        this.container.innerHTML = chipsHtml;
        
        // Trigger fade-in animation
        setTimeout(() => {
            this.container.querySelectorAll('.filter-chip').forEach(chip => {
                chip.classList.add('opacity-100');
            });
        }, 10);
        
        // Attach event handlers
        this.attachRemoveHandlers();
    }
    
    /**
     * Create HTML for a single chip
     * @param {string} field - Field name
     * @param {string} fieldLabel - Human-readable field label
     * @param {string} fieldType - Field type (text, number, date, boolean, select)
     * @param {string} operator - Filter operator
     * @param {*} value - Filter value
     * @returns {string} HTML string
     */
    createChipHtml(field, fieldLabel, fieldType, operator, value) {
        const chipColor = this.getChipColor(fieldType);
        const chipLabel = this.formatChipLabel(fieldLabel, operator, value);
        const tooltipText = this.formatTooltip(fieldLabel, operator, value);
        
        return `
            <div class="filter-chip inline-flex items-center gap-2 px-3 py-1.5 ${chipColor} rounded-lg text-sm border transition-all duration-200 opacity-0 shadow-sm"
                 data-field="${field}"
                 title="${tooltipText}">
                <span class="font-medium">${fieldLabel}</span>
                <span class="text-xs opacity-75">${this.formatOperatorLabel(operator)}</span>
                ${this.formatValueDisplay(value)}
                <button class="filter-chip-remove ml-1 hover:scale-110 transition-transform focus:outline-none focus:ring-2 focus:ring-offset-1 focus:ring-current rounded" 
                        data-field="${field}"
                        aria-label="Filtreyi kaldır: ${fieldLabel}">
                    <svg class="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                        <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path>
                    </svg>
                </button>
            </div>
        `;
    }
    
    /**
     * Get chip color based on field type
     * @param {string} fieldType - Field type (text, number, date, boolean, select)
     * @returns {string} Tailwind CSS classes for color
     */
    getChipColor(fieldType) {
        return this.colorMap[fieldType] || this.colorMap.text;
    }
    
    /**
     * Format chip label (field + operator + value)
     * @param {string} fieldLabel - Human-readable field label
     * @param {string} operator - Filter operator
     * @param {*} value - Filter value
     * @returns {string} Formatted label
     */
    formatChipLabel(fieldLabel, operator, value) {
        const operatorLabel = this.formatOperatorLabel(operator);
        const valueLabel = this.formatValueLabel(value, operator);
        
        return `${fieldLabel} ${operatorLabel}${valueLabel}`;
    }
    
    /**
     * Format operator label for display
     * @param {string} operator - Filter operator
     * @returns {string} Human-readable operator label
     */
    formatOperatorLabel(operator) {
        return this.operatorLabels[operator] || operator;
    }
    
    /**
     * Format value label for display in chip
     * @param {*} value - Filter value
     * @param {string} operator - Filter operator
     * @returns {string} Formatted value label
     */
    formatValueLabel(value, operator) {
        // Null operators don't need value display
        if (operator === 'is_null' || operator === 'is_not_null') {
            return '';
        }
        
        // Array values (between, in, not_in)
        if (Array.isArray(value)) {
            if (operator === 'between') {
                return `: ${value[0]} - ${value[1]}`;
            }
            // For 'in' and 'not_in', show count if more than 2 items
            if (value.length > 2) {
                return `: ${value.length} değer`;
            }
            return `: ${value.join(', ')}`;
        }
        
        // Boolean values
        if (typeof value === 'boolean') {
            return `: ${value ? 'Evet' : 'Hayır'}`;
        }
        
        // String/number values - truncate if too long
        const valueStr = String(value);
        if (valueStr.length > 20) {
            return `: ${valueStr.substring(0, 20)}...`;
        }
        
        return `: ${valueStr}`;
    }
    
    /**
     * Format value display HTML for chip
     * @param {*} value - Filter value
     * @returns {string} HTML string for value display
     */
    formatValueDisplay(value) {
        // Don't show value element for null operators
        if (value === null || value === undefined) {
            return '';
        }
        
        let displayValue = '';
        
        if (Array.isArray(value)) {
            if (value.length > 2) {
                displayValue = `${value.length} değer`;
            } else {
                displayValue = value.join(', ');
            }
        } else if (typeof value === 'boolean') {
            displayValue = value ? 'Evet' : 'Hayır';
        } else {
            displayValue = String(value);
            if (displayValue.length > 20) {
                displayValue = displayValue.substring(0, 20) + '...';
            }
        }
        
        return displayValue ? `<span class="text-xs font-normal">${displayValue}</span>` : '';
    }
    
    /**
     * Format tooltip text with full filter details
     * @param {string} fieldLabel - Human-readable field label
     * @param {string} operator - Filter operator
     * @param {*} value - Filter value
     * @returns {string} Tooltip text
     */
    formatTooltip(fieldLabel, operator, value) {
        const operatorLabel = this.formatOperatorLabel(operator);
        
        if (operator === 'is_null' || operator === 'is_not_null') {
            return `${fieldLabel} ${operatorLabel}`;
        }
        
        let valueText = '';
        if (Array.isArray(value)) {
            if (operator === 'between') {
                valueText = `${value[0]} ile ${value[1]} arasında`;
            } else {
                valueText = value.join(', ');
            }
        } else if (typeof value === 'boolean') {
            valueText = value ? 'Evet' : 'Hayır';
        } else {
            valueText = String(value);
        }
        
        return `${fieldLabel} ${operatorLabel}: ${valueText}`;
    }
    
    /**
     * Attach remove button event handlers
     */
    attachRemoveHandlers() {
        if (!this.container) return;
        
        const removeButtons = this.container.querySelectorAll('.filter-chip-remove');
        removeButtons.forEach(button => {
            button.addEventListener('click', (e) => {
                e.preventDefault();
                e.stopPropagation();
                
                const field = button.dataset.field;
                const chip = button.closest('.filter-chip');
                
                // Fade-out animation
                if (chip) {
                    chip.classList.add('opacity-0', 'scale-95');
                    
                    // Wait for animation to complete before removing
                    setTimeout(() => {
                        if (this.onRemoveCallback) {
                            this.onRemoveCallback(field);
                        }
                    }, 200);
                } else {
                    // No animation, remove immediately
                    if (this.onRemoveCallback) {
                        this.onRemoveCallback(field);
                    }
                }
            });
        });
    }
    
    /**
     * Set callback function for when a chip is removed
     * @param {Function} callback - Function to call with field name when chip is removed
     */
    onRemove(callback) {
        this.onRemoveCallback = callback;
    }
    
    /**
     * Clear all chips
     */
    clear() {
        if (!this.container) return;
        
        // Fade out all chips
        const chips = this.container.querySelectorAll('.filter-chip');
        chips.forEach(chip => {
            chip.classList.add('opacity-0', 'scale-95');
        });
        
        // Clear after animation
        setTimeout(() => {
            this.container.innerHTML = '<span class="text-sm text-gray-500">Aktif filtre yok</span>';
        }, 200);
    }
}
