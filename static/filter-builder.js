/**
 * FilterBuilder Component
 * Advanced filter builder with AND/OR logic and nested groups
 */

class FilterBuilder {
    constructor(entityType) {
        this.entityType = entityType; // 'contact' or 'company'
        this.groups = [];
        this.availableFields = this.getAvailableFields();
        this.operators = {
            text: ['equals', 'not_equals', 'contains', 'not_contains', 'starts_with', 'ends_with', 'is_null', 'is_not_null'],
            number: ['equals', 'not_equals', 'greater_than', 'less_than', 'between', 'is_null', 'is_not_null'],
            date: ['equals', 'greater_than', 'less_than', 'between', 'is_null', 'is_not_null'],
            boolean: ['equals'],
            select: ['equals', 'in', 'not_in', 'is_null', 'is_not_null']
        };
        this.editingFilterId = null;
    }
    
    getAvailableFields() {
        if (this.entityType === 'contact') {
            return [
                { name: 'first_name', label: 'First Name', type: 'text' },
                { name: 'last_name', label: 'Last Name', type: 'text' },
                { name: 'email', label: 'Email', type: 'text' },
                { name: 'phone', label: 'Phone', type: 'text' },
                { name: 'role', label: 'Role', type: 'select', options: ['Decision Maker', 'Champion', 'Influencer', 'User', 'Gatekeeper'] },
                { name: 'lead_score', label: 'Lead Score', type: 'number' },
                { name: 'is_starred', label: 'Starred', type: 'boolean' },
                { name: 'job_title', label: 'Job Title', type: 'text' },
                { name: 'created_at', label: 'Created Date', type: 'date' },
                { name: 'updated_at', label: 'Updated Date', type: 'date' }
            ];
        } else {
            return [
                { name: 'name', label: 'Company Name', type: 'text' },
                { name: 'industry', label: 'Industry', type: 'text' },
                { name: 'size', label: 'Size', type: 'select', options: ['1-10', '11-50', '51-200', '201-500', '500+'] },
                { name: 'website', label: 'Website', type: 'text' },
                { name: 'phone', label: 'Phone', type: 'text' },
                { name: 'created_at', label: 'Created Date', type: 'date' },
                { name: 'updated_at', label: 'Updated Date', type: 'date' }
            ];
        }
    }
    
    open(existingFilter = null) {
        if (existingFilter) {
            this.editingFilterId = existingFilter.id;
            const config = JSON.parse(existingFilter.filter_config);
            this.groups = config.groups || [];
        } else {
            this.editingFilterId = null;
            this.groups = [{ logic: 'AND', conditions: [{ field: '', operator: '', value: '' }] }];
        }
        
        this.render();
        this.showModal();
    }
    
    render() {
        const modalHtml = `
            <div id="filter-builder-modal" class="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50 hidden">
                <div class="bg-white rounded-lg shadow-xl max-w-4xl w-full max-h-[90vh] overflow-hidden">
                    <!-- Header -->
                    <div class="flex items-center justify-between p-6 border-b border-gray-200">
                        <h2 class="text-xl font-semibold text-gray-900">
                            ${this.editingFilterId ? 'Edit' : 'Create'} Advanced Filter
                        </h2>
                        <button onclick="filterBuilder.close()" class="text-gray-400 hover:text-gray-600">
                            <svg class="w-6 h-6" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                                <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path>
                            </svg>
                        </button>
                    </div>
                    
                    <!-- Body -->
                    <div class="p-6 overflow-y-auto max-h-[60vh]">
                        <div id="filter-groups-container">
                            ${this.renderGroups()}
                        </div>
                        
                        <button onclick="filterBuilder.addGroup()" 
                                class="mt-4 px-4 py-2 border border-blue-600 text-blue-600 rounded-md hover:bg-blue-50 text-sm font-medium">
                            + Add Group
                        </button>
                        
                        <!-- Group Logic -->
                        ${this.groups.length > 1 ? `
                            <div class="mt-6 p-4 bg-gray-50 rounded-md">
                                <label class="block text-sm font-medium text-gray-700 mb-2">
                                    Combine groups with:
                                </label>
                                <select id="group-logic-select" class="px-3 py-2 border border-gray-300 rounded-md text-sm">
                                    <option value="AND">AND (all groups must match)</option>
                                    <option value="OR">OR (any group can match)</option>
                                </select>
                            </div>
                        ` : ''}
                    </div>
                    
                    <!-- Footer -->
                    <div class="flex items-center justify-between p-6 border-t border-gray-200 bg-gray-50">
                        <button onclick="filterBuilder.testFilter()" 
                                class="px-4 py-2 border border-gray-300 rounded-md hover:bg-gray-50 text-sm font-medium">
                            Test Filter
                        </button>
                        <div class="flex gap-3">
                            <button onclick="filterBuilder.close()" 
                                    class="px-4 py-2 border border-gray-300 rounded-md hover:bg-gray-50 text-sm font-medium">
                                Cancel
                            </button>
                            <button onclick="filterBuilder.save()" 
                                    class="px-4 py-2 bg-blue-600 text-white rounded-md hover:bg-blue-700 text-sm font-medium">
                                ${this.editingFilterId ? 'Update' : 'Save'} Filter
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        `;
        
        // Remove existing modal if any
        const existingModal = document.getElementById('filter-builder-modal');
        if (existingModal) {
            existingModal.remove();
        }
        
        // Add new modal
        document.body.insertAdjacentHTML('beforeend', modalHtml);
    }
    
    renderGroups() {
        return this.groups.map((group, groupIndex) => `
            <div class="mb-6 p-4 border border-gray-300 rounded-lg bg-white" data-group-index="${groupIndex}">
                <div class="flex items-center justify-between mb-4">
                    <div class="flex items-center gap-3">
                        <span class="text-sm font-medium text-gray-700">Group ${groupIndex + 1}</span>
                        <select onchange="filterBuilder.updateGroupLogic(${groupIndex}, this.value)" 
                                class="px-2 py-1 border border-gray-300 rounded text-xs">
                            <option value="AND" ${group.logic === 'AND' ? 'selected' : ''}>AND</option>
                            <option value="OR" ${group.logic === 'OR' ? 'selected' : ''}>OR</option>
                        </select>
                    </div>
                    ${this.groups.length > 1 ? `
                        <button onclick="filterBuilder.removeGroup(${groupIndex})" 
                                class="text-red-600 hover:text-red-700 text-sm">
                            Remove Group
                        </button>
                    ` : ''}
                </div>
                
                <div class="space-y-3">
                    ${group.conditions.map((condition, conditionIndex) => 
                        this.renderCondition(groupIndex, conditionIndex, condition)
                    ).join('')}
                </div>
                
                <button onclick="filterBuilder.addCondition(${groupIndex})" 
                        class="mt-3 px-3 py-1.5 border border-gray-300 rounded-md hover:bg-gray-50 text-xs">
                    + Add Condition
                </button>
            </div>
        `).join('');
    }
    
    renderCondition(groupIndex, conditionIndex, condition) {
        const field = this.availableFields.find(f => f.name === condition.field);
        const fieldType = field ? field.type : 'text';
        const operators = this.operators[fieldType] || this.operators.text;
        
        return `
            <div class="flex items-start gap-2" data-condition-index="${conditionIndex}">
                <!-- Field Select -->
                <select onchange="filterBuilder.updateConditionField(${groupIndex}, ${conditionIndex}, this.value)" 
                        class="flex-1 px-3 py-2 border border-gray-300 rounded-md text-sm">
                    <option value="">Select field...</option>
                    ${this.availableFields.map(f => `
                        <option value="${f.name}" ${condition.field === f.name ? 'selected' : ''}>${f.label}</option>
                    `).join('')}
                </select>
                
                <!-- Operator Select -->
                <select onchange="filterBuilder.updateConditionOperator(${groupIndex}, ${conditionIndex}, this.value)" 
                        class="flex-1 px-3 py-2 border border-gray-300 rounded-md text-sm"
                        ${!condition.field ? 'disabled' : ''}>
                    <option value="">Select operator...</option>
                    ${operators.map(op => `
                        <option value="${op}" ${condition.operator === op ? 'selected' : ''}>
                            ${this.formatOperatorLabel(op)}
                        </option>
                    `).join('')}
                </select>
                
                <!-- Value Input -->
                <div class="flex-1">
                    ${this.renderValueInput(groupIndex, conditionIndex, condition, field)}
                </div>
                
                <!-- Remove Button -->
                ${this.groups[groupIndex].conditions.length > 1 ? `
                    <button onclick="filterBuilder.removeCondition(${groupIndex}, ${conditionIndex})" 
                            class="px-2 py-2 text-red-600 hover:text-red-700">
                        <svg class="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                            <path stroke-linecap="round" stroke-linejoin="round" stroke-width="2" d="M6 18L18 6M6 6l12 12"></path>
                        </svg>
                    </button>
                ` : '<div class="w-9"></div>'}
            </div>
        `;
    }
    
    renderValueInput(groupIndex, conditionIndex, condition, field) {
        if (!condition.operator || condition.operator === 'is_null' || condition.operator === 'is_not_null') {
            return '';
        }
        
        const inputId = `value-${groupIndex}-${conditionIndex}`;
        
        if (condition.operator === 'between') {
            if (field && field.type === 'number') {
                return `
                    <div class="flex gap-2">
                        <input type="number" id="${inputId}-min" value="${Array.isArray(condition.value) ? condition.value[0] : ''}" 
                               onchange="filterBuilder.updateConditionValue(${groupIndex}, ${conditionIndex}, [this.value, document.getElementById('${inputId}-max').value])"
                               placeholder="Min" class="flex-1 px-3 py-2 border border-gray-300 rounded-md text-sm">
                        <input type="number" id="${inputId}-max" value="${Array.isArray(condition.value) ? condition.value[1] : ''}"
                               onchange="filterBuilder.updateConditionValue(${groupIndex}, ${conditionIndex}, [document.getElementById('${inputId}-min').value, this.value])"
                               placeholder="Max" class="flex-1 px-3 py-2 border border-gray-300 rounded-md text-sm">
                    </div>
                `;
            } else if (field && field.type === 'date') {
                return `
                    <div class="flex gap-2">
                        <input type="date" id="${inputId}-min" value="${Array.isArray(condition.value) ? condition.value[0] : ''}"
                               onchange="filterBuilder.updateConditionValue(${groupIndex}, ${conditionIndex}, [this.value, document.getElementById('${inputId}-max').value])"
                               class="flex-1 px-3 py-2 border border-gray-300 rounded-md text-sm">
                        <input type="date" id="${inputId}-max" value="${Array.isArray(condition.value) ? condition.value[1] : ''}"
                               onchange="filterBuilder.updateConditionValue(${groupIndex}, ${conditionIndex}, [document.getElementById('${inputId}-min').value, this.value])"
                               class="flex-1 px-3 py-2 border border-gray-300 rounded-md text-sm">
                    </div>
                `;
            }
        } else if (condition.operator === 'in' || condition.operator === 'not_in') {
            if (field && field.type === 'select' && field.options) {
                const selectedValues = Array.isArray(condition.value) ? condition.value : [];
                return `
                    <select id="${inputId}" multiple size="3"
                            onchange="filterBuilder.updateConditionValue(${groupIndex}, ${conditionIndex}, Array.from(this.selectedOptions).map(o => o.value))"
                            class="w-full px-3 py-2 border border-gray-300 rounded-md text-sm">
                        ${field.options.map(opt => `
                            <option value="${opt}" ${selectedValues.includes(opt) ? 'selected' : ''}>${opt}</option>
                        `).join('')}
                    </select>
                `;
            } else {
                const valueStr = Array.isArray(condition.value) ? condition.value.join(', ') : condition.value;
                return `
                    <input type="text" id="${inputId}" value="${valueStr || ''}"
                           onchange="filterBuilder.updateConditionValue(${groupIndex}, ${conditionIndex}, this.value.split(',').map(v => v.trim()))"
                           placeholder="Comma-separated" class="w-full px-3 py-2 border border-gray-300 rounded-md text-sm">
                `;
            }
        } else {
            // Single value
            if (field && field.type === 'text') {
                return `
                    <input type="text" id="${inputId}" value="${condition.value || ''}"
                           onchange="filterBuilder.updateConditionValue(${groupIndex}, ${conditionIndex}, this.value)"
                           placeholder="Enter value" class="w-full px-3 py-2 border border-gray-300 rounded-md text-sm">
                `;
            } else if (field && field.type === 'number') {
                return `
                    <input type="number" id="${inputId}" value="${condition.value || ''}"
                           onchange="filterBuilder.updateConditionValue(${groupIndex}, ${conditionIndex}, this.value)"
                           placeholder="Enter number" class="w-full px-3 py-2 border border-gray-300 rounded-md text-sm">
                `;
            } else if (field && field.type === 'date') {
                return `
                    <input type="date" id="${inputId}" value="${condition.value || ''}"
                           onchange="filterBuilder.updateConditionValue(${groupIndex}, ${conditionIndex}, this.value)"
                           class="w-full px-3 py-2 border border-gray-300 rounded-md text-sm">
                `;
            } else if (field && field.type === 'boolean') {
                return `
                    <select id="${inputId}"
                            onchange="filterBuilder.updateConditionValue(${groupIndex}, ${conditionIndex}, this.value)"
                            class="w-full px-3 py-2 border border-gray-300 rounded-md text-sm">
                        <option value="true" ${condition.value === 'true' || condition.value === true ? 'selected' : ''}>Yes</option>
                        <option value="false" ${condition.value === 'false' || condition.value === false ? 'selected' : ''}>No</option>
                    </select>
                `;
            } else if (field && field.type === 'select' && field.options) {
                return `
                    <select id="${inputId}"
                            onchange="filterBuilder.updateConditionValue(${groupIndex}, ${conditionIndex}, this.value)"
                            class="w-full px-3 py-2 border border-gray-300 rounded-md text-sm">
                        <option value="">Select...</option>
                        ${field.options.map(opt => `
                            <option value="${opt}" ${condition.value === opt ? 'selected' : ''}>${opt}</option>
                        `).join('')}
                    </select>
                `;
            }
        }
        
        return '';
    }
    
    formatOperatorLabel(operator) {
        const labels = {
            'equals': 'Equals',
            'not_equals': 'Not Equals',
            'contains': 'Contains',
            'not_contains': 'Does Not Contain',
            'starts_with': 'Starts With',
            'ends_with': 'Ends With',
            'greater_than': 'Greater Than',
            'less_than': 'Less Than',
            'between': 'Between',
            'in': 'In',
            'not_in': 'Not In',
            'is_null': 'Is Empty',
            'is_not_null': 'Is Not Empty'
        };
        return labels[operator] || operator;
    }
    
    addGroup() {
        this.groups.push({ logic: 'AND', conditions: [{ field: '', operator: '', value: '' }] });
        this.refreshGroups();
    }
    
    removeGroup(groupIndex) {
        this.groups.splice(groupIndex, 1);
        this.refreshGroups();
    }
    
    updateGroupLogic(groupIndex, logic) {
        this.groups[groupIndex].logic = logic;
    }
    
    addCondition(groupIndex) {
        this.groups[groupIndex].conditions.push({ field: '', operator: '', value: '' });
        this.refreshGroups();
    }
    
    removeCondition(groupIndex, conditionIndex) {
        this.groups[groupIndex].conditions.splice(conditionIndex, 1);
        this.refreshGroups();
    }
    
    updateConditionField(groupIndex, conditionIndex, field) {
        this.groups[groupIndex].conditions[conditionIndex].field = field;
        this.groups[groupIndex].conditions[conditionIndex].operator = '';
        this.groups[groupIndex].conditions[conditionIndex].value = '';
        this.refreshGroups();
    }
    
    updateConditionOperator(groupIndex, conditionIndex, operator) {
        this.groups[groupIndex].conditions[conditionIndex].operator = operator;
        this.groups[groupIndex].conditions[conditionIndex].value = '';
        this.refreshGroups();
    }
    
    updateConditionValue(groupIndex, conditionIndex, value) {
        this.groups[groupIndex].conditions[conditionIndex].value = value;
    }
    
    refreshGroups() {
        const container = document.getElementById('filter-groups-container');
        if (container) {
            container.innerHTML = this.renderGroups();
        }
    }
    
    validate() {
        const errors = [];
        
        this.groups.forEach((group, groupIndex) => {
            group.conditions.forEach((condition, conditionIndex) => {
                if (!condition.field) {
                    errors.push(`Group ${groupIndex + 1}, Condition ${conditionIndex + 1}: Field is required`);
                }
                if (!condition.operator) {
                    errors.push(`Group ${groupIndex + 1}, Condition ${conditionIndex + 1}: Operator is required`);
                }
                if (condition.operator !== 'is_null' && condition.operator !== 'is_not_null') {
                    if (condition.value === '' || condition.value === null || condition.value === undefined) {
                        errors.push(`Group ${groupIndex + 1}, Condition ${conditionIndex + 1}: Value is required`);
                    }
                    if (condition.operator === 'between' && Array.isArray(condition.value)) {
                        if (!condition.value[0] || !condition.value[1]) {
                            errors.push(`Group ${groupIndex + 1}, Condition ${conditionIndex + 1}: Both min and max values required`);
                        }
                    }
                }
            });
        });
        
        return errors;
    }
    
    testFilter() {
        const errors = this.validate();
        if (errors.length > 0) {
            alert('Validation errors:\n' + errors.join('\n'));
            return;
        }
        
        const filterConfig = this.buildFilterConfig();
        
        // Show loading
        const testBtn = event.target;
        testBtn.disabled = true;
        testBtn.textContent = 'Testing...';
        
        // Test filter by calling API
        fetch(`/api/v1/${this.entityType}s?filters=${encodeURIComponent(JSON.stringify(filterConfig))}&page=1&per_page=10`)
            .then(response => response.json())
            .then(data => {
                const count = data.pagination ? data.pagination.total : 0;
                alert(`Filter test successful!\n\nFound ${count} matching ${this.entityType}s.`);
            })
            .catch(error => {
                console.error('Test filter error:', error);
                alert('Error testing filter. Please check your criteria.');
            })
            .finally(() => {
                testBtn.disabled = false;
                testBtn.textContent = 'Test Filter';
            });
    }
    
    buildFilterConfig() {
        const groupLogic = this.groups.length > 1 
            ? (document.getElementById('group-logic-select')?.value || 'OR')
            : 'AND';
        
        return {
            groups: this.groups.map(group => ({
                logic: group.logic,
                conditions: group.conditions.map(c => ({
                    field: c.field,
                    operator: c.operator,
                    value: c.value
                }))
            })),
            groupLogic
        };
    }
    
    save() {
        const errors = this.validate();
        if (errors.length > 0) {
            alert('Validation errors:\n' + errors.join('\n'));
            return;
        }
        
        const name = prompt('Enter a name for this filter:');
        if (!name) return;
        
        const description = prompt('Enter a description (optional):') || '';
        const isShared = confirm('Share this filter with your team?');
        
        const filterConfig = this.buildFilterConfig();
        
        const method = this.editingFilterId ? 'PATCH' : 'POST';
        const url = this.editingFilterId 
            ? `/api/v1/user-defined-filters/${this.editingFilterId}`
            : '/api/v1/user-defined-filters';
        
        fetch(url, {
            method,
            headers: {
                'Content-Type': 'application/json'
            },
            body: JSON.stringify({
                name,
                description,
                entity_type: this.entityType,
                filter_config: JSON.stringify(filterConfig),
                is_shared: isShared
            })
        })
        .then(response => response.json())
        .then(data => {
            alert(`Filter ${this.editingFilterId ? 'updated' : 'saved'} successfully!`);
            this.close();
            
            // Reload saved filters if filterPanel exists
            if (window.filterPanel) {
                window.filterPanel.loadSavedFilters();
            }
        })
        .catch(error => {
            console.error('Save filter error:', error);
            alert('Error saving filter. Please try again.');
        });
    }
    
    showModal() {
        const modal = document.getElementById('filter-builder-modal');
        if (modal) {
            modal.classList.remove('hidden');
        }
    }
    
    close() {
        const modal = document.getElementById('filter-builder-modal');
        if (modal) {
            modal.classList.add('hidden');
            setTimeout(() => modal.remove(), 300);
        }
        this.groups = [];
        this.editingFilterId = null;
    }
}

// Global instance
let filterBuilder = null;
