/**
 * Contact / Company Detail Sayfaları için Dinamik Özel Nesneler (Custom Objects) Yönetimi
 */

document.addEventListener('DOMContentLoaded', () => {
    // Sadece contact_detail veya company_detail sayfasındaysak çalıştır
    const pathParts = window.location.pathname.split('/').filter(Boolean);
    if ((pathParts[0] === 'contacts' || pathParts[0] === 'companies') && pathParts.length >= 2) {
        window.co_entityType = pathParts[0] === 'contacts' ? 'contact' : 'company';
        window.co_entityId = pathParts[1];
        
        // Modal container'ı ekle
        const modalContainer = document.createElement('div');
        modalContainer.id = 'co-record-modal-root';
        document.body.appendChild(modalContainer);
        
        loadDynamicSidebarCustomObjects();
    }
});

let allCustomObjects = [];

async function loadDynamicSidebarCustomObjects() {
    try {
        console.log("Custom Objects yükleniyor...");
        const container = document.getElementById('custom-objects-sidebar-container');
        if (!container) {
            console.warn("custom-objects-sidebar-container elementi bulunamadı!");
            return;
        }
        
        // 1. Tüm aktif özel nesneleri (şemaları) al
        const resObjects = await fetch('/api/custom-objects/');
        const dataObjects = await resObjects.json();
        allCustomObjects = dataObjects.custom_objects || [];
        
        if (allCustomObjects.length === 0) return; // Hiç özel nesne yok
        
        // 2. Bu entity'e (Müşteriye) bağlı kayıtları al
        const resLinked = await fetch(`/api/custom-objects/entity-records/${window.co_entityType}/${window.co_entityId}`);
        const dataLinked = await resLinked.json();
        const linkedObjects = dataLinked.data || [];
        
        // 3. İkisini birleştir: Her aktif Custom Object için UI çiz.
        let html = '';
        allCustomObjects.forEach(obj => {
            // Eğer varsa bu objenin bu kişiye bağlı kayıtları:
            const linkedData = linkedObjects.find(x => x.custom_object.id === obj.id);
            const records = linkedData ? linkedData.records : [];
            
            html += `
                <div class="sidebar-section group">
                    <div class="sidebar-section-header" onclick="toggleSection('co_${obj.id}')">
                        <span class="sidebar-section-title flex items-center gap-1.5" style="color: ${obj.icon_color}">
                            <i class="${obj.icon}"></i> ${obj.plural_label}
                        </span>
                        <div class="sidebar-section-icons">
                            <button class="sidebar-icon-btn opacity-0 group-hover:opacity-100" onclick="event.stopPropagation(); openCORecordModal(${obj.id})" title="Yeni ${obj.singular_label} Ekle">
                                <i class="fas fa-plus"></i>
                            </button>
                            <i id="co_${obj.id}-icon" class="fas fa-chevron-down text-[10px] text-gray-400 transition-transform"></i>
                        </div>
                    </div>
                    <div id="co_${obj.id}-content" class="hidden sidebar-section-body">
            `;
            
            if (records.length === 0) {
                html += `
                    <div class="text-center py-2">
                        <p class="text-[11px] text-gray-400 mb-2">Henüz eklenmemiş.</p>
                        <button onclick="openCORecordModal(${obj.id})" class="text-[11px] font-medium text-blue-600 hover:text-blue-700 bg-blue-50 hover:bg-blue-100 px-3 py-1 rounded-md transition border border-blue-100 block w-full">
                            + ${obj.singular_label} Ekle
                        </button>
                    </div>
                `;
            } else {
                html += '<div class="space-y-2">';
                records.forEach(rec => {
                    // Sadece ilk ana alanı göster (daha hoş bir görünüm için)
                    html += `
                        <div class="bg-gray-50 border border-gray-100 p-2.5 rounded-lg group/record relative">
                            <button onclick="unlinkCORecord(${rec.link_id})" class="absolute right-2 top-2 w-5 h-5 flex items-center justify-center text-gray-300 hover:text-red-500 rounded transition opacity-0 group-hover/record:opacity-100 bg-white shadow-sm border border-gray-100" title="Bağlantıyı Kaldır">
                                <i class="fas fa-unlink text-[9px]"></i>
                            </button>
                            <div class="text-[12px] font-semibold text-gray-800 break-words pr-6 mb-1">${rec.record_name}</div>
                            <div class="grid grid-cols-1 gap-1">
                    `;
                    
                    // Şemadaki özellikleri (properties) listele
                    if (obj.schema_config && Array.isArray(obj.schema_config)) {
                        obj.schema_config.slice(0, 3).forEach(f => {
                            let val = rec.properties[f.name];
                            if (val) {
                                html += `<div class="flex items-start text-[10px]"><span class="text-gray-400 w-14 shrink-0">${f.label}:</span> <span class="font-medium text-gray-700 break-words flex-1">${val}</span></div>`;
                            }
                        });
                    }
                    
                    html += `
                            </div>
                        </div>
                    `;
                });
                html += `
                    <button onclick="openCORecordModal(${obj.id})" class="mt-2 text-[11px] font-medium text-blue-600 hover:text-blue-700 flex items-center gap-1">
                        <i class="fas fa-plus"></i> Yeni Ekle
                    </button>
                </div>`;
            }
            
            html += `
                    </div>
                </div>
            `;
        });
        
        container.innerHTML = html;
        
    } catch (e) {
        console.error('Özel nesneler yüklenemedi:', e);
    }
}

// Global modal state
let activeCOForModal = null;

function openCORecordModal(objId) {
    const obj = allCustomObjects.find(x => x.id === objId);
    if (!obj) return;
    activeCOForModal = obj;
    
    // Create form fields dynamically from schema_config
    let formHtml = '';
    const schema = Array.isArray(obj.schema_config) ? obj.schema_config : [];
    
    // İlk alan otomatik title (record_name) alınacak
    schema.forEach((f, idx) => {
        const isRequired = f.required ? 'required' : '';
        const asterisk = f.required ? '<span class="text-red-500">*</span>' : '';
        const isFirst = idx === 0; // The first item will map to record_name natively
        
        let inputHtml = '';
        if (f.type === 'text') {
            inputHtml = `<input type="text" name="${f.name}" class="w-full text-sm border border-gray-200 bg-gray-50 rounded-lg px-3 py-2 outline-none focus:border-blue-400 focus:bg-white transition" ${isRequired}>`;
        } else if (f.type === 'number') {
            inputHtml = `<input type="number" name="${f.name}" class="w-full text-sm border border-gray-200 bg-gray-50 rounded-lg px-3 py-2 outline-none focus:border-blue-400 focus:bg-white transition" ${isRequired}>`;
        } else if (f.type === 'date') {
            inputHtml = `<input type="date" name="${f.name}" class="w-full text-sm border border-gray-200 bg-gray-50 rounded-lg px-3 py-2 outline-none focus:border-blue-400 focus:bg-white transition" ${isRequired}>`;
        } else if (f.type === 'select') {
            let opts = (f.options || []).map(opt => `<option value="${opt}">${opt}</option>`).join('');
            inputHtml = `<select name="${f.name}" class="w-full text-sm border border-gray-200 bg-gray-50 rounded-lg px-3 py-2 outline-none focus:border-blue-400 focus:bg-white transition" ${isRequired}><option value="">Seçiniz...</option>${opts}</select>`;
        } else if (f.type === 'textarea') {
            inputHtml = `<textarea name="${f.name}" class="w-full text-sm border border-gray-200 bg-gray-50 rounded-lg px-3 py-2 outline-none focus:border-blue-400 focus:bg-white transition" rows="2" ${isRequired}></textarea>`;
        } else if (f.type === 'boolean') {
            inputHtml = `
            <div class="flex items-center gap-2 mt-1">
                <input type="checkbox" name="${f.name}" class="w-4 h-4 rounded border-gray-300 text-blue-600 focus:ring-blue-500 cursor-pointer">
                <span class="text-xs text-gray-500 font-medium">Evet / Onayla</span>
            </div>`;
        }
        
        formHtml += `
            <div>
                <label class="block text-xs font-bold text-gray-600 mb-1">${f.label} ${asterisk}</label>
                ${inputHtml}
                ${isFirst ? '<p class="text-[10px] text-gray-400 mt-1">Bu alan ana tanımlayıcıdır.</p>' : ''}
            </div>
        `;
    });
    
    if (schema.length === 0) {
        formHtml = '<div class="text-sm text-yellow-600 bg-yellow-50 p-3 rounded-lg border border-yellow-200">Bunun için Ayarlar > Özel Nesneler menüsünden önce yapılandırma (alan/sütun) eklemelisiniz.</div>';
    }
    
    const root = document.getElementById('co-record-modal-root');
    root.innerHTML = `
    <div class="fixed inset-0 bg-slate-900/40 backdrop-blur-sm z-[100] flex items-center justify-center p-4" id="co-record-modal-overlay">
        <div class="bg-white rounded-3xl w-full max-w-lg shadow-2xl overflow-hidden flex flex-col max-h-[90vh]">
            <div class="px-6 py-4 border-b border-gray-100 flex items-center justify-between">
                <div class="flex items-center gap-3">
                    <div class="w-10 h-10 rounded-xl flex items-center justify-center" style="background-color: ${obj.icon_color}1a; color: ${obj.icon_color}">
                        <i class="${obj.icon} text-lg"></i>
                    </div>
                    <div>
                        <h3 class="font-bold text-gray-800 text-base">Yeni ${obj.singular_label}</h3>
                        <p class="text-xs text-gray-400 font-medium">Kişi dosyasına eklenecek</p>
                    </div>
                </div>
                <button onclick="closeCORecordModal()" class="w-8 h-8 rounded-full border border-gray-200 hover:bg-gray-100 text-gray-500 transition-colors flex items-center justify-center"><i class="fas fa-times"></i></button>
            </div>
            
            <form id="co-record-form" onsubmit="submitCORecord(event)" class="p-6 overflow-y-auto space-y-4">
                ${formHtml}
            </form>
            
            <div class="px-6 py-4 bg-gray-50 border-t border-gray-100 flex justify-end gap-3">
                <button onclick="closeCORecordModal()" class="px-5 py-2.5 rounded-xl text-sm font-bold text-gray-600 hover:bg-gray-200 transition-colors">İptal</button>
                <button onclick="document.getElementById('co-record-form').requestSubmit()" class="px-6 py-2.5 rounded-xl text-sm font-bold bg-blue-600 text-white hover:bg-blue-700 shadow-md transition-all flex items-center gap-2" ${schema.length===0?'disabled':''}>
                    <i class="fas fa-save"></i> Kaydet ve Bağla
                </button>
            </div>
        </div>
    </div>
    `;
}

function closeCORecordModal() {
    const root = document.getElementById('co-record-modal-root');
    if(root) root.innerHTML = '';
}

async function submitCORecord(e) {
    e.preventDefault();
    if (!activeCOForModal) return;
    
    const obj = activeCOForModal;
    const schema = Array.isArray(obj.schema_config) ? obj.schema_config : [];
    if (schema.length === 0) return;
    
    // Gather form data
    const formData = new FormData(e.target);
    const properties = {};
    
    schema.forEach(f => {
        let val = formData.get(f.name);
        if (f.type === 'boolean') val = formData.has(f.name) ? true : false;
        properties[f.name] = val;
    });
    
    // First field is naturally the record_name
    const recordNameDef = schema[0];
    const recordName = properties[recordNameDef.name];
    
    if (!recordName) {
        showGlobalToast('Ana alan boş olamaz', 'error');
        return;
    }
    
    const btn = e.target.querySelector('button[type="submit"]') || document.querySelector('#co-record-modal-root .bg-blue-600');
    if(btn) { btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> İşleniyor'; btn.disabled = true; }
    
    try {
        const token = document.querySelector('meta[name="csrf-token"]').content;
        
        // 1. Create the record
        const resCreate = await fetch('/api/custom-objects/' + obj.id + '/records', {
            method: 'POST',
            headers: {'Content-Type': 'application/json', 'X-CSRFToken': token},
            body: JSON.stringify({
                record_name: recordName.toString(),
                properties: properties
            })
        });
        
        if (!resCreate.ok) throw new Error('Kayıt oluşturulamadı');
        const dataCreate = await resCreate.json();
        const recordId = dataCreate.data.id;
        
        // 2. Link it to the current contact/company
        const resLink = await fetch('/api/custom-objects/links', {
            method: 'POST',
            headers: {'Content-Type': 'application/json', 'X-CSRFToken': token},
            body: JSON.stringify({
                from_type: window.co_entityType,
                from_id: parseInt(window.co_entityId),
                to_type: 'custom_object_record',
                to_id: recordId,
                label: 'Bağlı'
            })
        });
        
        if (!resLink.ok) throw new Error('Kayıt oluşturuldu fakat kişiye bağlanamadı');
        
        showGlobalToast('Kayıt başarıyla eklendi', 'success');
        closeCORecordModal();
        loadDynamicSidebarCustomObjects(); // Refresh sidebar UI
        
    } catch(err) {
        showGlobalToast(err.message, 'error');
        if(btn) { btn.innerHTML = '<i class="fas fa-save"></i> Kaydet ve Bağla'; btn.disabled = false; }
    }
}

async function unlinkCORecord(linkId) {
    if(!confirm('Bu öğenin bu kişiyle olan bağlantısını kaldırmak istediğinize emin misiniz? (Öğe silinmez, sadece bağ kopar)')) return;
    
    try {
        const token = document.querySelector('meta[name="csrf-token"]').content;
        const res = await fetch('/api/custom-objects/links/' + linkId, {
            method: 'DELETE',
            headers: {'X-CSRFToken': token}
        });
        if(!res.ok) throw new Error();
        loadDynamicSidebarCustomObjects();
    } catch(e) {
        showGlobalToast('Bağlantı kaldırılamadı.', 'error');
    }
}

function showGlobalToast(msg, type='info') {
    if (typeof showToast === 'function') {
        showToast(msg, type);
    } else {
        alert((type==='error'?'Hata: ':'') + msg);
    }
}

