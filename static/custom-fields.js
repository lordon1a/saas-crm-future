/**
 * Custom Fields Management
 */

let customFields = [];
let currentEntityType = 'contact';

// Load custom fields
async function loadCustomFields(entityType = null) {
    try {
        const url = entityType ? 
            `/api/v1/custom-fields?entity_type=${entityType}` : 
            '/api/v1/custom-fields';
        
        const response = await fetch(url);
        const data = await response.json();
        
        customFields = data;
        renderCustomFields();
    } catch (error) {
        console.error('Error loading custom fields:', error);
    }
}

// Render custom fields list
function renderCustomFields() {
    const container = document.getElementById('customFieldsList');
    if (!container) return;
    
    // Group by entity type
    const grouped = {
        contact: customFields.filter(f => f.entity_type === 'contact'),
        company: customFields.filter(f => f.entity_type === 'company'),
        deal: customFields.filter(f => f.entity_type === 'deal')
    };
    
    const entityLabels = {
        contact: 'Kişiler',
        company: 'Şirketler',
        deal: 'Fırsatlar'
    };
    
    let html = '';
    
    for (const [entityType, fields] of Object.entries(grouped)) {
        if (fields.length === 0) continue;
        
        html += `
            <div class="mb-6">
                <h4 class="text-sm font-bold text-slate-700 mb-3">${entityLabels[entityType]}</h4>
                <div class="space-y-2">
                    ${fields.map(field => `
                        <div class="flex items-center justify-between p-4 bg-white rounded-xl border border-slate-200 hover:border-brand-300 transition-all group">
                            <div class="flex-1">
                                <div class="flex items-center gap-3 mb-1">
                                    <p class="text-sm font-semibold text-slate-800">${field.field_name}</p>
                                    <span class="px-2 py-0.5 bg-slate-100 text-slate-600 rounded-full text-xs font-semibold">${getFieldTypeLabel(field.field_type)}</span>
                                    ${field.is_required ? '<span class="px-2 py-0.5 bg-red-100 text-red-600 rounded-full text-xs font-semibold">Zorunlu</span>' : ''}
                                </div>
                                ${field.options ? `<p class="text-xs text-slate-500">Seçenekler: ${field.options}</p>` : ''}
                            </div>
                            <div class="flex gap-2 opacity-0 group-hover:opacity-100 transition-opacity">
                                <button onclick="editCustomField(${field.id})" class="px-3 py-1.5 bg-white border border-slate-200 text-slate-600 rounded-lg text-xs font-bold hover:bg-slate-50 transition-all">
                                    <i class="fas fa-edit"></i> Düzenle
                                </button>
                                <button onclick="deleteCustomField(${field.id})" class="px-3 py-1.5 bg-white border border-slate-200 text-red-600 rounded-lg text-xs font-bold hover:bg-red-50 hover:border-red-300 transition-all">
                                    <i class="fas fa-trash"></i> Sil
                                </button>
                            </div>
                        </div>
                    `).join('')}
                </div>
            </div>
        `;
    }
    
    if (html === '') {
        html = `
            <div class="text-center py-12">
                <div class="w-16 h-16 bg-slate-100 rounded-2xl flex items-center justify-center mx-auto mb-4">
                    <i class="fas fa-list-check text-slate-400 text-2xl"></i>
                </div>
                <p class="text-sm font-semibold text-slate-600">Henüz özel alan yok</p>
                <p class="text-xs text-slate-400 mt-1">Kişiler, şirketler veya fırsatlar için özel alanlar oluşturun</p>
            </div>
        `;
    }
    
    container.innerHTML = html;
}

// Get field type label
function getFieldTypeLabel(fieldType) {
    const labels = {
        text: 'Metin',
        number: 'Sayı',
        date: 'Tarih',
        dropdown: 'Açılır Liste',
        checkbox: 'Onay Kutusu',
        multi_select: 'Çoklu Seçim'
    };
    return labels[fieldType] || fieldType;
}

// Open create custom field modal
function openCustomFieldModal() {
    document.getElementById('customFieldModal').classList.remove('hidden');
    document.getElementById('customFieldModal').classList.add('flex');
    
    // Reset form
    document.getElementById('customFieldId').value = '';
    document.getElementById('cfEntityType').value = 'contact';
    document.getElementById('cfFieldName').value = '';
    document.getElementById('cfFieldType').value = 'text';
    document.getElementById('cfOptions').value = '';
    document.getElementById('cfIsRequired').checked = false;
    document.getElementById('cfOptionsContainer').classList.add('hidden');
    
    document.getElementById('customFieldModalTitle').textContent = 'Yeni Özel Alan';
}

// Close custom field modal
function closeCustomFieldModal() {
    document.getElementById('customFieldModal').classList.add('hidden');
    document.getElementById('customFieldModal').classList.remove('flex');
}

// Field type change handler
function onFieldTypeChange() {
    const fieldType = document.getElementById('cfFieldType').value;
    const optionsContainer = document.getElementById('cfOptionsContainer');
    
    if (fieldType === 'dropdown' || fieldType === 'multi_select') {
        optionsContainer.classList.remove('hidden');
    } else {
        optionsContainer.classList.add('hidden');
    }
}

// Save custom field
async function saveCustomField() {
    const fieldId = document.getElementById('customFieldId').value;
    const entityType = document.getElementById('cfEntityType').value;
    const fieldName = document.getElementById('cfFieldName').value.trim();
    const fieldType = document.getElementById('cfFieldType').value;
    const optionsStr = document.getElementById('cfOptions').value.trim();
    const isRequired = document.getElementById('cfIsRequired').checked;
    
    if (!fieldName) {
        alert('Alan adı gerekli');
        return;
    }
    
    // Parse options
    let options = null;
    if (fieldType === 'dropdown' || fieldType === 'multi_select') {
        if (!optionsStr) {
            alert('Seçenekler gerekli');
            return;
        }
        options = optionsStr.split(',').map(o => o.trim()).filter(o => o);
        if (options.length === 0) {
            alert('En az bir seçenek gerekli');
            return;
        }
    }
    
    try {
        const body = {
            entity_type: entityType,
            field_name: fieldName,
            field_type: fieldType,
            options: options,
            is_required: isRequired
        };
        
        let response;
        if (fieldId) {
            // Update
            response = await fetch(`/api/v1/custom-fields/${fieldId}`, {
                method: 'PATCH',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify(body)
            });
        } else {
            // Create
            response = await fetch('/api/v1/custom-fields', {
                method: 'POST',
                headers: {'Content-Type': 'application/json'},
                body: JSON.stringify(body)
            });
        }
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.error || 'Kaydetme başarısız');
        }
        
        closeCustomFieldModal();
        await loadCustomFields();
        showToast(fieldId ? 'Özel alan güncellendi' : 'Özel alan oluşturuldu', 'success');
        
    } catch (error) {
        console.error('Error saving custom field:', error);
        alert(error.message);
    }
}

// Edit custom field
function editCustomField(fieldId) {
    const field = customFields.find(f => f.id === fieldId);
    if (!field) return;
    
    document.getElementById('customFieldId').value = field.id;
    document.getElementById('cfEntityType').value = field.entity_type;
    document.getElementById('cfFieldName').value = field.field_name;
    document.getElementById('cfFieldType').value = field.field_type;
    document.getElementById('cfIsRequired').checked = field.is_required;
    
    if (field.options) {
        try {
            const options = JSON.parse(field.options);
            document.getElementById('cfOptions').value = options.join(', ');
            document.getElementById('cfOptionsContainer').classList.remove('hidden');
        } catch (e) {
            document.getElementById('cfOptions').value = '';
        }
    } else {
        document.getElementById('cfOptions').value = '';
        document.getElementById('cfOptionsContainer').classList.add('hidden');
    }
    
    document.getElementById('customFieldModalTitle').textContent = 'Özel Alanı Düzenle';
    document.getElementById('customFieldModal').classList.remove('hidden');
    document.getElementById('customFieldModal').classList.add('flex');
}

// Delete custom field
async function deleteCustomField(fieldId) {
    if (!confirm('Bu özel alanı silmek istediğinizden emin misiniz? Tüm değerler silinecek.')) {
        return;
    }
    
    try {
        const response = await fetch(`/api/v1/custom-fields/${fieldId}`, {
            method: 'DELETE'
        });
        
        if (!response.ok) {
            throw new Error('Silme başarısız');
        }
        
        await loadCustomFields();
        showToast('Özel alan silindi', 'success');
        
    } catch (error) {
        console.error('Error deleting custom field:', error);
        alert('Silme başarısız');
    }
}

// Show toast notification
function showToast(message, type = 'success') {
    const toast = document.getElementById('toast');
    if (!toast) return;
    
    toast.textContent = message;
    toast.classList.remove('translate-x-[150%]', 'bg-emerald-500', 'bg-red-500');
    
    if (type === 'success') {
        toast.classList.add('bg-emerald-500', 'text-white');
    } else {
        toast.classList.add('bg-red-500', 'text-white');
    }
    
    setTimeout(() => {
        toast.classList.add('translate-x-[150%]');
    }, 3000);
}
