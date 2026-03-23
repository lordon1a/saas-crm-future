/**
 * DocGen - Document Template Management
 * Documents sayfasına entegre edilmiş şablon yönetimi
 */

const DocGen = {
    API_BASE: '/api/docgen',
    currentCategoryFilter: '',
    
    async api(path, options) {
        const res = await fetch(path, options || {});
        const isJson = (res.headers.get('content-type') || '').includes('application/json');
        const data = isJson ? await res.json() : null;
        if (!res.ok) {
            throw new Error((data && data.error) || 'İşlem başarısız');
        }
        return data;
    },
    
    getCategoryIcon(category) {
        const icons = {
            'contract': '📄',
            'quote': '💰',
            'invoice': '🧾',
            'report': '📊',
            'other': '📋'
        };
        return icons[category] || '📄';
    },
    
    getCategoryName(category) {
        const names = {
            'contract': 'Sözleşme',
            'quote': 'Teklif',
            'invoice': 'Fatura',
            'report': 'Rapor',
            'other': 'Diğer'
        };
        return names[category] || category;
    },

    async loadTemplates() {
        try {
            const data = await this.api(`${this.API_BASE}/templates`);
            let templates = data.templates || [];
            
            // Update template count
            const countEl = document.getElementById('templateCount');
            if (countEl) {
                countEl.textContent = templates.length;
            }
            
            // Apply category filter
            if (this.currentCategoryFilter) {
                templates = templates.filter(t => t.category === this.currentCategoryFilter);
            }
            
            const container = document.getElementById('docgenTemplateList');
            if (!container) return;
            
            if (templates.length === 0) {
                container.innerHTML = '<div class="p-6 text-sm text-slate-500">Henüz şablon yok. Yukarıdan yeni şablon yükleyin.</div>';
                return;
            }
            
            container.innerHTML = templates.map(t => `
                <div class="p-4 hover:bg-slate-50 transition-colors">
                    <div class="flex items-start justify-between gap-3 mb-2">
                        <div class="min-w-0 flex-1">
                            <div class="flex items-center gap-2 mb-1">
                                <span class="text-lg">${this.getCategoryIcon(t.category)}</span>
                                <p class="text-sm font-bold text-slate-800 truncate">${t.name}</p>
                                ${t.is_default ? '<span class="px-2 py-0.5 bg-amber-100 text-amber-700 text-[10px] font-bold rounded">VARSAYILAN</span>' : ''}
                            </div>
                            <p class="text-xs text-slate-500">
                                ${this.getCategoryName(t.category)} | ${t.object_type || 'general'} | ${t.file_type} | v${t.version || 1}
                            </p>
                            ${t.description ? `<p class="text-xs text-slate-600 mt-1">${t.description}</p>` : ''}
                        </div>
                        <div class="flex items-center gap-1">
                            ${t.is_active ? '<span class="w-2 h-2 bg-green-500 rounded-full" title="Aktif"></span>' : '<span class="w-2 h-2 bg-slate-300 rounded-full" title="Pasif"></span>'}
                        </div>
                    </div>
                    <div class="flex items-center gap-2 mt-3">
                        <button onclick="DocGen.previewTemplate(${t.id})" 
                            class="px-3 py-1.5 text-xs font-semibold bg-slate-100 text-slate-700 rounded-lg hover:bg-slate-200">
                            <i class="fas fa-eye mr-1"></i>Önizle
                        </button>
                        <button onclick="DocGen.setDefaultTemplate(${t.id})" 
                            class="px-3 py-1.5 text-xs font-semibold ${t.is_default ? 'bg-amber-100 text-amber-700' : 'bg-slate-100 text-slate-700'} rounded-lg hover:bg-amber-200">
                            <i class="fas fa-star mr-1"></i>${t.is_default ? 'Varsayılan' : 'Varsayılan Yap'}
                        </button>
                        <button onclick="DocGen.toggleTemplate(${t.id}, ${!t.is_active})" 
                            class="px-2.5 py-1.5 text-xs font-semibold border border-slate-200 rounded-lg hover:bg-slate-50">
                            ${t.is_active ? '<i class="fas fa-pause"></i>' : '<i class="fas fa-play"></i>'}
                        </button>
                        <button onclick="DocGen.deleteTemplate(${t.id})" 
                            class="px-2.5 py-1.5 text-xs font-semibold text-red-600 border border-red-200 rounded-lg hover:bg-red-50">
                            <i class="fas fa-trash"></i>
                        </button>
                    </div>
                </div>
            `).join('');
            
        } catch (err) {
            console.error('Template yükleme hatası:', err);
            alert('Şablonlar yüklenemedi: ' + err.message);
        }
    },

    async uploadTemplate(event) {
        event.preventDefault();
        
        const fileInput = document.getElementById('docgenTemplateFile');
        const nameInput = document.getElementById('docgenTemplateName');
        const categoryInput = document.getElementById('docgenTemplateCategory');
        const objectTypeInput = document.getElementById('docgenObjectType');
        const descInput = document.getElementById('docgenTemplateDesc');
        const isDefaultInput = document.getElementById('docgenIsDefault');
        
        if (!fileInput.files[0]) {
            alert('Lütfen bir dosya seçin');
            return;
        }
        
        if (!categoryInput.value) {
            alert('Lütfen bir kategori seçin');
            return;
        }
        
        const formData = new FormData();
        formData.append('file', fileInput.files[0]);
        formData.append('name', nameInput.value.trim());
        formData.append('category', categoryInput.value);
        formData.append('object_type', objectTypeInput.value);
        formData.append('is_default', isDefaultInput.checked ? 'true' : 'false');
        if (descInput.value.trim()) {
            formData.append('description', descInput.value.trim());
        }
        
        try {
            await this.api(`${this.API_BASE}/templates`, {
                method: 'POST',
                body: formData
            });
            
            alert('Şablon başarıyla yüklendi!');
            event.target.reset();
            await this.loadTemplates();
        } catch (err) {
            alert('Şablon yükleme hatası: ' + err.message);
        }
    },
    
    async setDefaultTemplate(templateId) {
        try {
            await this.api(`${this.API_BASE}/templates/${templateId}/set-default`, {
                method: 'POST'
            });
            
            await this.loadTemplates();
        } catch (err) {
            alert('Varsayılan şablon ayarlama hatası: ' + err.message);
        }
    },
    
    async previewTemplate(templateId) {
        try {
            const data = await this.api(`${this.API_BASE}/templates/${templateId}`);
            const template = data.template;
            
            const modal = document.createElement('div');
            modal.className = 'fixed inset-0 bg-black bg-opacity-50 z-50 flex items-center justify-center p-4';
            modal.innerHTML = `
                <div class="bg-white rounded-2xl shadow-2xl max-w-2xl w-full max-h-[80vh] overflow-y-auto">
                    <div class="p-6 border-b border-gray-200 sticky top-0 bg-white">
                        <div class="flex items-center justify-between">
                            <h3 class="text-xl font-bold text-gray-900">Şablon Önizleme</h3>
                            <button onclick="this.closest('.fixed').remove()" class="text-gray-400 hover:text-gray-600">
                                <i class="fas fa-times text-xl"></i>
                            </button>
                        </div>
                    </div>
                    <div class="p-6 space-y-4">
                        <div class="flex items-center gap-3">
                            <span class="text-4xl">${this.getCategoryIcon(template.category)}</span>
                            <div>
                                <h4 class="text-lg font-bold text-gray-900">${template.name}</h4>
                                <p class="text-sm text-gray-500">${this.getCategoryName(template.category)}</p>
                            </div>
                        </div>
                        <div class="grid grid-cols-2 gap-4 text-sm">
                            <div>
                                <span class="font-semibold text-gray-700">Dosya Tipi:</span>
                                <span class="text-gray-600">${template.file_type}</span>
                            </div>
                            <div>
                                <span class="font-semibold text-gray-700">Versiyon:</span>
                                <span class="text-gray-600">v${template.version || 1}</span>
                            </div>
                            <div>
                                <span class="font-semibold text-gray-700">Kayıt Tipi:</span>
                                <span class="text-gray-600">${template.object_type}</span>
                            </div>
                            <div>
                                <span class="font-semibold text-gray-700">Durum:</span>
                                <span class="text-gray-600">${template.is_active ? '✅ Aktif' : '⏸️ Pasif'}</span>
                            </div>
                        </div>
                        ${template.description ? `
                            <div class="bg-slate-50 border border-slate-200 rounded-lg p-4">
                                <p class="text-sm font-semibold text-slate-700 mb-1">Açıklama:</p>
                                <p class="text-sm text-slate-600">${template.description}</p>
                            </div>
                        ` : ''}
                        <div class="bg-blue-50 border border-blue-200 rounded-lg p-4">
                            <p class="text-sm font-semibold text-blue-900 mb-2">Kullanılabilir Placeholder'lar:</p>
                            <div class="text-xs text-blue-800 space-y-1">
                                <p>• <code>{{${template.object_type}.name}}</code> - Kayıt adı</p>
                                <p>• <code>{{${template.object_type}.created_at}}</code> - Oluşturulma tarihi</p>
                                <p>• <code>{{contact.email}}</code> - İlgili kişi email</p>
                                <p>• <code>{{company.name}}</code> - Şirket adı</p>
                                <p>• <code>{{user.name}}</code> - Kullanıcı adı</p>
                                <p>• <code>{{workspace.company_name}}</code> - Workspace adı</p>
                            </div>
                        </div>
                    </div>
                    <div class="p-6 bg-gray-50 border-t border-gray-200 flex gap-3">
                        <button onclick="this.closest('.fixed').remove()" class="flex-1 px-4 py-2 border border-gray-300 text-gray-700 rounded-lg hover:bg-gray-100 font-semibold">
                            Kapat
                        </button>
                        <button onclick="DocGen.downloadTemplate(${templateId})" class="flex-1 px-4 py-2 bg-brand-600 text-white rounded-lg hover:bg-brand-700 font-semibold">
                            <i class="fas fa-download mr-2"></i>İndir
                        </button>
                    </div>
                </div>
            `;
            
            document.body.appendChild(modal);
            
        } catch (err) {
            alert('Önizleme hatası: ' + err.message);
        }
    },
    
    async downloadTemplate(templateId) {
        window.open(`${this.API_BASE}/templates/${templateId}/download`, '_blank');
    },

    async toggleTemplate(templateId, isActive) {
        try {
            await this.api(`${this.API_BASE}/templates/${templateId}`, {
                method: 'PUT',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ is_active: isActive })
            });
            
            await this.loadTemplates();
        } catch (err) {
            alert('Durum değiştirme hatası: ' + err.message);
        }
    },

    async deleteTemplate(templateId) {
        if (!confirm('Bu şablonu silmek istediğinizden emin misiniz?')) return;
        
        try {
            await this.api(`${this.API_BASE}/templates/${templateId}`, {
                method: 'DELETE'
            });
            
            alert('Şablon silindi');
            await this.loadTemplates();
        } catch (err) {
            alert('Silme hatası: ' + err.message);
        }
    },

    init() {
        // Upload form event listener
        const uploadForm = document.getElementById('docgenTemplateUploadForm');
        if (uploadForm) {
            uploadForm.addEventListener('submit', (e) => this.uploadTemplate(e));
        }
        
        // Category filter event listener
        const categoryFilter = document.getElementById('templateCategoryFilter');
        if (categoryFilter) {
            categoryFilter.addEventListener('change', (e) => {
                this.currentCategoryFilter = e.target.value;
                this.loadTemplates();
            });
        }
        
        // İlk yükleme
        this.loadTemplates();
    }
};

// Sayfa yüklendiğinde başlat
if (document.readyState === 'loading') {
    document.addEventListener('DOMContentLoaded', () => DocGen.init());
} else {
    DocGen.init();
}
