// Team Member Selector Component
// Reusable dropdown component for assigning team members to CRM entities

class TeamMemberSelector {
    constructor(containerId, options = {}) {
        this.containerId = containerId;
        this.container = document.getElementById(containerId);
        this.options = {
            includeUnassigned: options.includeUnassigned !== false, // default true
            selectedValue: options.selectedValue || null,
            placeholder: options.placeholder || 'Atama yapın',
            disabled: options.disabled || false,
            onChange: options.onChange || null
        };
        this.members = [];
        this.selectElement = null;
    }

    // Initialize the selector
    async init() {
        await this.loadMembers();
        this.render();
    }

    // Load team members from API
    async loadMembers() {
        try {
            const response = await fetch('/api/assignments/members');
            if (!response.ok) throw new Error('Failed to load members');
            
            const data = await response.json();
            this.members = data.members || [];
        } catch (error) {
            console.error('Error loading team members:', error);
            this.members = [];
        }
    }

    // Render the dropdown
    render() {
        if (!this.container) {
            console.error(`Container #${this.containerId} not found`);
            return;
        }

        // Create select element
        this.selectElement = document.createElement('select');
        this.selectElement.className = 'w-full px-3 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-brand-500 focus:border-transparent text-sm';
        this.selectElement.disabled = this.options.disabled;

        // Add placeholder option
        const placeholderOption = document.createElement('option');
        placeholderOption.value = '';
        placeholderOption.textContent = this.options.placeholder;
        this.selectElement.appendChild(placeholderOption);

        // Add unassigned option if enabled
        if (this.options.includeUnassigned) {
            const unassignedOption = document.createElement('option');
            unassignedOption.value = 'unassigned';
            unassignedOption.textContent = 'Atanmamış';
            this.selectElement.appendChild(unassignedOption);
        }

        // Add team members
        this.members.forEach(member => {
            const option = document.createElement('option');
            option.value = member.id;
            option.textContent = `${member.name} (${this.formatRole(member.role)})`;
            this.selectElement.appendChild(option);
        });

        // Set selected value
        if (this.options.selectedValue) {
            this.selectElement.value = this.options.selectedValue;
        }

        // Add change event listener
        this.selectElement.addEventListener('change', (e) => {
            const selectedValue = e.target.value;
            const selectedMember = this.members.find(m => m.id == selectedValue);
            
            // Emit custom event
            const event = new CustomEvent('memberSelected', {
                detail: {
                    memberId: selectedValue === 'unassigned' ? null : (selectedValue || null),
                    member: selectedMember || null
                }
            });
            this.container.dispatchEvent(event);

            // Call onChange callback if provided
            if (this.options.onChange) {
                this.options.onChange(selectedValue === 'unassigned' ? null : (selectedValue || null), selectedMember);
            }
        });

        // Clear container and append select
        this.container.innerHTML = '';
        this.container.appendChild(this.selectElement);
    }

    // Format role for display
    formatRole(role) {
        const roleMap = {
            owner: 'Sahip',
            admin: 'Admin',
            member: 'Üye',
            viewer: 'Görüntüleyici'
        };
        return roleMap[role] || role;
    }

    // Update selected value programmatically
    setValue(value) {
        if (this.selectElement) {
            this.selectElement.value = value || '';
        }
    }

    // Get current selected value
    getValue() {
        if (!this.selectElement) return null;
        const value = this.selectElement.value;
        return value === 'unassigned' ? null : (value || null);
    }

    // Enable/disable the selector
    setDisabled(disabled) {
        if (this.selectElement) {
            this.selectElement.disabled = disabled;
        }
    }

    // Reload members and re-render
    async reload() {
        await this.loadMembers();
        this.render();
    }

    // Destroy the selector
    destroy() {
        if (this.container) {
            this.container.innerHTML = '';
        }
        this.selectElement = null;
    }
}

// Export for use in other scripts
if (typeof module !== 'undefined' && module.exports) {
    module.exports = TeamMemberSelector;
}
