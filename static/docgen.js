/**
 * DocGen - Document Template Management
 * Documents sayfasına entegre edilmiş şablon yönetimi
 */

const DocGen = {
    API_BASE: '/api/docgen',
    
    async api(path, options) {
        const res = await fetch(path, options || {});
        const isJson = (res.headers.get('content-type') || '').includes('application/json');
        const data = isJson ? await res.json() : null;
        if (!res.ok) {
            throw new Error((data && data.error) || 'İşlem başarısız');
        }
        return data;
    },

    async loadTemplates() {
        try {
            const data = await this.api(`${this.API_BASE}/templates`);
            const templates = data.templates || [];
            
            const container = document.getElementById('docgenTemplateList');
            if (!container) return;
            
            if (templates.length === 0) {
                container.innerHTML = '<div class="p-6 text-sm text-slate-500">Henüz şablon yok. Yukarıdan yeni şablon yükleyin.</div>';
                return;
            }
            
            container.innerHTML = templates.map(t => `
                <div class="p-4 flex items-center justify-between gap-3 hover:bg-slate-50">
                    <div class="min-w-0 flex-1">
                        <p class="text-sm font-bold text-slate-800 truncate">${t.name}</p>
                        <p class="text-xs text-slate-500">
                            ${t.object_type || 'general'} | ${t.file_type} | v${t.version || 1}
                            ${t.is_active ? '<span class="text-green-600">● Aktif</span>' : '<span class="text-slate-400">○ Pasif</span>'}
                        </p>
                    </div>
                    <div class="flex items-center gap-2">
                        <button onclick="DocGen.generateFromTemplate(${t.id})" 
                            class="px-3 py-1.5 text-xs font-semibold bg-brand-600 text-white rounded-lg hover:bg-brand-700">
                            <i class="fas fa-file-export mr-1"></i>Oluştur
                        </button>
                        <button onclick="DocGen.toggleTemplate(${t.id}, ${!t.is_active})" 
                            class="px-2.5 py-1.5 text-xs font-semibold border border-slate-200 rounded-lg hover:bg-slate-50">
                            ${t.is_active ? 'Pasifleştir' : 'Aktifleştir'}
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
        const objectTypeInput = document.getElementById('docgenObjectType');
        const descInput = document.getElementById('docgenTemplateDesc');
        
        if (!fileInput.files[0]) {
            alert('Lütfen bir dosya seçin');
            return;
        }
        
        const formData = new FormData();
        formData.append('file', fileInput.files[0]);
        formData.append('name', nameInput.value.trim());
        formData.append('object_type', objectTypeInput.value);
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

    async generateFromTemplate(templateId) {
        const recordType = prompt('Kayıt tipi (deal/contact/company/quote/task/product):', 'deal');
        if (!recordType) return;
        
        const recordId = prompt('Kayıt ID:', '1');
        if (!recordId) return;
        
        const outputType = prompt('Çıktı formatı (docx/pptx):\n\nNOT: PDF dönüştürme şu an desteklenmiyor, DOCX kullanın.', 'docx');
        if (!outputType) return;
        
        try {
            const data = await this.api(`${this.API_BASE}/generate`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    template_id: templateId,
                    record_type: recordType,
                    record_id: parseInt(recordId),
                    output_type: outputType
                })
            });
            
            if (data.document && data.document.id) {
                alert('Doküman oluşturuldu! İndiriliyor...');
                window.open(`${this.API_BASE}/download/${data.document.id}`, '_blank');
            }
        } catch (err) {
            alert('Doküman oluşturma hatası: ' + err.message);
        }
    },

    init() {
        // Upload form event listener
        const uploadForm = document.getElementById('docgenTemplateUploadForm');
        if (uploadForm) {
            uploadForm.addEventListener('submit', (e) => this.uploadTemplate(e));
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
