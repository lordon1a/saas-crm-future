/**
 * FilterExport Component - Export filtered data to CSV/Excel
 * Handles column selection and file download
 * 
 * Requirements: 13.1, 13.2, 13.3, 13.4, 13.7
 */

class FilterExport {
    constructor(entityType) {
        this.entityType = entityType; // 'contact' or 'company'
        this.selectedColumns = [];
        this.availableColumns = this.getAvailableColumns();
    }
    
    /**
     * Get available columns for export based on entity type
     */
    getAvailableColumns() {
        if (this.entityType === 'contact') {
            return [
                { name: 'first_name', label: 'Ad', selected: true },
                { name: 'last_name', label: 'Soyad', selected: true },
                { name: 'email', label: 'E-posta', selected: true },
                { name: 'phone', label: 'Telefon', selected: true },
                { name: 'whatsapp_phone', label: 'WhatsApp', selected: false },
                { name: 'telegram_chat_id', label: 'Telegram', selected: false },
                { name: 'role', label: 'Rol', selected: true },
                { name: 'job_title', label: 'İş Ünvanı', selected: false },
                { name: 'lead_score', label: 'Lead Score', selected: false },
                { name: 'is_starred', label: 'Yıldızlı', selected: false },
                { name: 'company_name', label: 'Şirket', selected: true },
                { name: 'created_at', label: 'Oluşturulma Tarihi', selected: false },
                { name: 'updated_at', label: 'Güncellenme Tarihi', selected: false }
            ];
        } else {
            return [
                { name: 'name', label: 'Şirket Adı', selected: true },
                { name: 'industry', label: 'Sektör', selected: true },
                { name: 'size', label: 'Büyüklük', selected: true },
                { name: 'website', label: 'Website', selected: true },
                { name: 'phone', label: 'Telefon', selected: true },
                { name: 'address', label: 'Adres', selected: false },
                { name: 'parent_company_name', label: 'Ana Şirket', selected: false },
                { name: 'created_at', label: 'Oluşturulma Tarihi', selected: false },
                { name: 'updated_at', label: 'Güncellenme Tarihi', selected: false }
            ];
        }
    }
    
    /**
     * Open export modal with format selection
     * @param {string} format - 'csv' or 'xlsx'
     * @param {object} filters - Current active filters
     */
    openExportModal(format, filters = {}) {
        const modalHtml = `
            <div id="export-modal" class="fixed inset-0 bg-black bg-opacity-50 flex items-center justify-center z-50">
                <div class="bg-white rounded-lg shadow-xl p-6 w-full max-w-2xl max-h-[90vh] overflow-y-auto">
                    <div class="flex items-center justify-between mb-4">
                        <h3 class="text-lg font-semibold">
                            ${format.toUpperCase()} Olarak Dışa Aktar
                        </h3>
                        <button id="close-export-modal" class="text-gray-400 hover:text-gray-600 transition-colors">
                            <i class="fas fa-times text-xl"></i>
                        </button>
                    </div>
                    
                    <div class="mb-4 p-3 bg-blue-50 border border-blue-200 rounded-lg">
                        <p class="text-sm text-blue-800">
                            <i class="fas fa-info-circle mr-2"></i>
                            Maksimum 10,000 kayıt dışa aktarılabilir. Aktif filtreler uygulanacaktır.
                        </p>
                    </div>
                    
                    <div class="mb-4">
                        <div class="flex items-center justify-between mb-3">
                            <h4 class="text-sm font-semibold text-gray-700">Sütun Seçimi</h4>
                            <div class="space-x-2">
                                <button id="select-all-columns" class="text-xs text-blue-600 hover:text-blue-700 font-medium">
                                    Tümünü Seç
                                </button>
                                <button id="deselect-all-columns" class="text-xs text-gray-600 hover:text-gray-700 font-medium">
                                    Tümünü Kaldır
                                </button>
                            </div>
                        </div>
                        
                        <div id="column-selection-container" class="grid grid-cols-2 gap-2 max-h-64 overflow-y-auto p-2 border border-gray-200 rounded-lg">
                            ${this.availableColumns.map(col => `
                                <label class="flex items-center space-x-2 p-2 hover:bg-gray-50 rounded cursor-pointer">
                                    <input 
                                        type="checkbox" 
                                        class="export-column-checkbox w-4 h-4 text-blue-600 border-gray-300 rounded focus:ring-blue-500"
                                        data-column="${col.name}"
                                        ${col.selected ? 'checked' : ''}
                                    />
                                    <span class="text-sm text-gray-700">${col.label}</span>
                                </label>
                            `).join('')}
                        </div>
                    </div>
                    
                    <div id="export-progress" class="hidden mb-4">
                        <div class="flex items-center space-x-3">
                            <div class="animate-spin rounded-full h-5 w-5 border-b-2 border-blue-600"></div>
                            <span class="text-sm text-gray-600">Dışa aktarılıyor...</span>
                        </div>
                        <div class="mt-2 w-full bg-gray-200 rounded-full h-2">
                            <div id="export-progress-bar" class="bg-blue-600 h-2 rounded-full transition-all duration-300" style="width: 0%"></div>
                        </div>
                    </div>
                    
                    <div class="flex justify-end space-x-3">
                        <button 
                            id="cancel-export" 
                            class="px-4 py-2 text-gray-700 bg-gray-100 rounded-md hover:bg-gray-200 transition-colors"
                        >
                            İptal
                        </button>
                        <button 
                            id="confirm-export" 
                            class="px-4 py-2 text-white bg-blue-600 rounded-md hover:bg-blue-700 transition-colors flex items-center space-x-2"
                        >
                            <i class="fas fa-download"></i>
                            <span>Dışa Aktar</span>
                        </button>
                    </div>
                </div>
            </div>
        `;
        
        // Append modal to body
        document.body.insertAdjacentHTML('beforeend', modalHtml);
        
        const modal = document.getElementById('export-modal');
        const closeBtn = document.getElementById('close-export-modal');
        const cancelBtn = document.getElementById('cancel-export');
        const confirmBtn = document.getElementById('confirm-export');
        const selectAllBtn = document.getElementById('select-all-columns');
        const deselectAllBtn = document.getElementById('deselect-all-columns');
        
        // Close modal function
        const closeModal = () => {
            modal.remove();
        };
        
        // Close button
        closeBtn.addEventListener('click', closeModal);
        cancelBtn.addEventListener('click', closeModal);
        
        // Click outside to close
        modal.addEventListener('click', (e) => {
            if (e.target === modal) {
                closeModal();
            }
        });
        
        // Escape key to close
        const escapeHandler = (e) => {
            if (e.key === 'Escape') {
                closeModal();
                document.removeEventListener('keydown', escapeHandler);
            }
        };
        document.addEventListener('keydown', escapeHandler);
        
        // Select all columns
        selectAllBtn.addEventListener('click', () => {
            document.querySelectorAll('.export-column-checkbox').forEach(cb => {
                cb.checked = true;
            });
        });
        
        // Deselect all columns
        deselectAllBtn.addEventListener('click', () => {
            document.querySelectorAll('.export-column-checkbox').forEach(cb => {
                cb.checked = false;
            });
        });
        
        // Confirm export
        confirmBtn.addEventListener('click', () => {
            const selectedColumns = Array.from(document.querySelectorAll('.export-column-checkbox:checked'))
                .map(cb => cb.dataset.column);
            
            if (selectedColumns.length === 0) {
                alert('Lütfen en az bir sütun seçin.');
                return;
            }
            
            this.exportData(format, selectedColumns, filters, closeModal);
        });
    }
    
    /**
     * Export data with selected columns and filters
     * @param {string} format - 'csv' or 'xlsx'
     * @param {array} columns - Selected column names
     * @param {object} filters - Active filters
     * @param {function} closeModal - Callback to close modal
     */
    async exportData(format, columns, filters, closeModal) {
        const confirmBtn = document.getElementById('confirm-export');
        const progressContainer = document.getElementById('export-progress');
        const progressBar = document.getElementById('export-progress-bar');
        
        // Disable button and show progress
        confirmBtn.disabled = true;
        confirmBtn.innerHTML = '<i class="fas fa-spinner fa-spin mr-2"></i>Dışa aktarılıyor...';
        progressContainer.classList.remove('hidden');
        
        try {
            // Simulate progress (since we don't have real progress from backend)
            let progress = 0;
            const progressInterval = setInterval(() => {
                progress += 10;
                if (progress <= 90) {
                    progressBar.style.width = `${progress}%`;
                }
            }, 200);
            
            const response = await fetch(`/api/v1/${this.entityType}s/export`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    format,
                    columns,
                    filters
                })
            });
            
            clearInterval(progressInterval);
            progressBar.style.width = '100%';
            
            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.error || 'Dışa aktarma başarısız oldu');
            }
            
            // Get filename from Content-Disposition header or generate one
            const contentDisposition = response.headers.get('Content-Disposition');
            let filename = `${this.entityType}s_filtered_${new Date().toISOString().split('T')[0]}.${format}`;
            
            if (contentDisposition) {
                const filenameMatch = contentDisposition.match(/filename="?(.+)"?/);
                if (filenameMatch) {
                    filename = filenameMatch[1];
                }
            }
            
            // Download file
            const blob = await response.blob();
            this.downloadFile(blob, filename);
            
            // Close modal
            closeModal();
            
            // Show success message
            this.showToast('Dosya başarıyla indirildi!', 'success');
            
        } catch (error) {
            console.error('Export error:', error);
            confirmBtn.disabled = false;
            confirmBtn.innerHTML = '<i class="fas fa-download mr-2"></i>Dışa Aktar';
            progressContainer.classList.add('hidden');
            alert(`Dışa aktarma hatası: ${error.message}`);
        }
    }
    
    /**
     * Download file to user's computer
     * @param {Blob} blob - File data
     * @param {string} filename - File name
     */
    downloadFile(blob, filename) {
        const url = window.URL.createObjectURL(blob);
        const a = document.createElement('a');
        a.style.display = 'none';
        a.href = url;
        a.download = filename;
        document.body.appendChild(a);
        a.click();
        window.URL.revokeObjectURL(url);
        document.body.removeChild(a);
    }
    
    /**
     * Show toast notification
     * @param {string} message - Message to display
     * @param {string} type - Type of toast: 'success', 'error', 'warning', 'info'
     */
    showToast(message, type = 'info') {
        // Remove existing toast if any
        const existingToast = document.getElementById('export-toast');
        if (existingToast) {
            existingToast.remove();
        }
        
        // Color classes by type
        const colorClasses = {
            success: 'bg-green-500',
            error: 'bg-red-500',
            warning: 'bg-yellow-500',
            info: 'bg-blue-500'
        };
        
        // Icons by type
        const icons = {
            success: '✓',
            error: '✕',
            warning: '⚠',
            info: 'ℹ'
        };
        
        const bgColor = colorClasses[type] || colorClasses.info;
        const icon = icons[type] || icons.info;
        
        // Create toast element
        const toast = document.createElement('div');
        toast.id = 'export-toast';
        toast.className = `fixed top-4 right-4 ${bgColor} text-white px-4 py-3 rounded-lg shadow-lg flex items-center space-x-2 z-50 transition-opacity duration-300`;
        toast.innerHTML = `
            <span class="text-lg font-bold">${icon}</span>
            <span>${message}</span>
        `;
        
        document.body.appendChild(toast);
        
        // Fade in
        setTimeout(() => {
            toast.style.opacity = '1';
        }, 10);
        
        // Auto remove after 3 seconds
        setTimeout(() => {
            toast.style.opacity = '0';
            setTimeout(() => {
                toast.remove();
            }, 300);
        }, 3000);
    }
}

// Global instance (will be initialized by page)
let filterExport = null;
