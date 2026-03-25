// static/custom-objects.js

document.addEventListener('DOMContentLoaded', () => {
    // Sadece Settings sayfasındaysak devam et
    if (!document.getElementById('panel-custom-objects')) return;
    
    // Tab geçişi için observer eklenebilir, şimdilik ilk açılışta yükleyelim.
    loadCustomObjects();
    
    // Tab geçişini yakalamak için MutationObserver veya polling
    const panel = document.getElementById('panel-custom-objects');
    const observer = new MutationObserver((mutations) => {
        mutations.forEach((mutation) => {
            if (mutation.attributeName === 'class' && panel.classList.contains('active')) {
                loadCustomObjects();
            }
        });
    });
    observer.observe(panel, { attributes: true });
});

async function loadCustomObjects() {
    const listEl = document.getElementById('customObjectsList');
    if (!listEl) return;
    
    listEl.innerHTML = '<div class="bg-white border rounded-lg p-8 text-center text-slate-500"><i class="fas fa-spinner fa-spin mr-2"></i> Yükleniyor...</div>';
    
    try {
        const res = await fetch('/api/custom-objects');
        if (!res.ok) throw new Error('API hatası');
        
        const data = await res.json();
        const objects = data.custom_objects;
        
        if (objects.length === 0) {
            listEl.innerHTML = `
                <div class="bg-white border text-sm rounded-lg p-8 text-center bg-slate-50/50">
                    <div class="w-12 h-12 bg-white border border-slate-200 rounded-full flex items-center justify-center text-slate-300 mx-auto border-dashed mb-3">
                        <i class="fas fa-cubes"></i>
                    </div>
                    <p class="font-semibold text-slate-600">Henüz hiçbir özel nesne tanımlanmamış</p>
                    <p class="text-xs text-slate-500 mt-1 mb-4">Örn: "Mülk", "Araç", "Sipariş" gibi kendinize özel modülleri sisteme ekleyin.</p>
                </div>
            `;
            return;
        }
        
        let html = '';
        objects.forEach(obj => {
            const iconStr = obj.icon || 'fas fa-cube';
            const colorStr = obj.icon_color || '#8b5cf6';
            
            html += `
            <div class="flex items-center justify-between p-5 bg-white border border-slate-200 rounded-2xl hover:shadow-lg transition-all hover:border-[color:var(--color-bg)]" style="--color-bg: ${colorStr}40">
                <div class="flex items-center gap-4 border-r border-slate-100 pr-4 w-1/3">
                    <div class="w-14 h-14 rounded-2xl flex items-center justify-center shadow-inner" style="background-color: ${colorStr}15; color: ${colorStr}; border: 1px solid ${colorStr}30">
                        <i class="${iconStr} text-2xl drop-shadow-sm"></i>
                    </div>
                    <div>
                        <h4 class="font-bold text-slate-800 text-base">${obj.plural_label} <span class="text-[10px] bg-slate-100 px-1.5 py-0.5 rounded font-mono text-slate-500 font-bold ml-1">${obj.name}</span></h4>
                        <p class="text-xs font-medium text-slate-500 mt-1">${obj.singular_label} Modülü</p>
                    </div>
                </div>
                
                <div class="flex-1 px-4 text-xs text-slate-500">
                    <span class="bg-slate-50 border border-slate-200 px-2 py-1 rounded text-[10px] font-bold uppercase tracking-wider text-slate-400">Alanlar:</span>
                    <span class="ml-1 font-medium text-slate-600">${(obj.schema_config && obj.schema_config.length) || 0} Yapılandırılmış Alan</span>
                </div>
                
                <div class="flex items-center gap-2 pl-4">
                    <button onclick="editCustomObject(${obj.id})" class="text-slate-400 hover:text-brand-600 hover:bg-brand-50 w-9 h-9 flex items-center justify-center rounded-xl transition-all" title="Düzenle">
                        <i class="fas fa-edit"></i>
                    </button>
                    <button onclick="editSchema(${obj.id})" class="text-slate-400 hover:text-orange-500 hover:bg-orange-50 w-9 h-9 flex items-center justify-center rounded-xl transition-all" title="Yapılandırma (Alan Düzenle)">
                        <i class="fas fa-clipboard-list"></i>
                    </button>
                    <button onclick="deleteCustomObject(${obj.id})" class="text-slate-400 hover:text-red-500 hover:bg-red-50 w-9 h-9 flex items-center justify-center rounded-xl transition-all" title="Sil">
                        <i class="fas fa-trash-alt"></i>
                    </button>
                </div>
            </div>
            `;
        });
        listEl.innerHTML = html;
        
    } catch (e) {
        listEl.innerHTML = '<div class="text-sm text-red-500 p-4 bg-red-50 border border-red-100 rounded-lg"><i class="fas fa-exclamation-circle mr-2"></i> Yüklenirken bir sorun oluştu.</div>';
    }
}

function openCustomObjectModal(obj = null) {
    // Var olan modalı sil
    const existing = document.getElementById('co-modal-overlay');
    if (existing) existing.remove();
    
    const isEdit = obj !== null;
    const title = isEdit ? 'Özel Nesneyi Düzenle' : 'Yeni Özel Nesne Oluştur';
    
    const baseName = obj?.name || '';
    const pluralLabel = obj?.plural_label || '';
    const singularLabel = obj?.singular_label || '';
    const description = obj?.description || '';
    const icon = obj?.icon || 'fas fa-cube';
    const iconColor = obj?.icon_color || '#6366f1';
    
    const overlay = document.createElement('div');
    overlay.id = 'co-modal-overlay';
    overlay.className = 'fixed inset-0 bg-slate-900/40 backdrop-blur-sm z-[100] flex items-center justify-center p-4 transition-opacity';
    
    // Simple inline style info for animations
    overlay.style.opacity = '0';
    setTimeout(() => {
        overlay.style.opacity = '1';
        overlay.style.transition = 'opacity 0.2s cubic-bezier(0.4, 0, 0.2, 1)';
    }, 10);
    
    overlay.innerHTML = `
    <div class="bg-white rounded-3xl shadow-2xl w-full max-w-lg overflow-hidden flex flex-col max-h-[90vh] transform transition-transform duration-200 scale-95 origin-bottom" id="co-modal-content">
        <div class="px-7 py-5 border-b border-slate-100 flex items-center justify-between bg-slate-50/50">
            <div>
                <h3 class="font-bold text-slate-800 text-lg">${title}</h3>
                <p class="text-[11px] font-medium text-slate-400 uppercase tracking-widest mt-0.5">SİSTEM YAPILANDIRMASI</p>
            </div>
            <button onclick="closeCustomObjectModal()" class="w-8 h-8 flex items-center justify-center rounded-full text-slate-400 hover:text-slate-700 hover:bg-slate-200 transition-all">
                <i class="fas fa-times"></i>
            </button>
        </div>
        <div class="p-7 overflow-y-auto flex-1 space-y-6 bg-white">
            
            <div class="space-y-1.5">
                <label class="block text-[11px] font-bold text-slate-500 uppercase tracking-wider ml-1">Kimlik (API Adı)</label>
                <input type="text" id="co_name" value="${baseName}" ${isEdit ? 'disabled' : ''} class="w-full text-sm bg-slate-50 border border-slate-200 rounded-xl px-4 py-3 focus:bg-white focus:ring-2 focus:ring-brand-500/20 focus:border-brand-500 outline-none transition-all placeholder:text-slate-300" placeholder="orn: mülk_karti, arac" autocomplete="off">
                ${isEdit ? '<p class="text-[10px] text-slate-400 font-medium ml-1">Sistem adı sonradan değiştirilemez.</p>' : '<p class="text-[10px] text-slate-400 font-medium ml-1">Veritabanındaki tablo adı olarak kullanılır (sadece küçük harf ve alt tire).</p>'}
            </div>

            <div class="grid grid-cols-2 gap-5">
                <div class="space-y-1.5">
                    <label class="block text-[11px] font-bold text-slate-500 uppercase tracking-wider ml-1">Çoğul İsim</label>
                    <input type="text" id="co_plural" value="${pluralLabel}" class="w-full text-sm bg-slate-50 border border-slate-200 rounded-xl px-4 py-3 focus:bg-white focus:ring-2 focus:ring-brand-500/20 focus:border-brand-500 outline-none transition-all placeholder:text-slate-300" placeholder="Örn: Araçlar">
                </div>
                <div class="space-y-1.5">
                    <label class="block text-[11px] font-bold text-slate-500 uppercase tracking-wider ml-1">Tekil İsim</label>
                    <input type="text" id="co_singular" value="${singularLabel}" class="w-full text-sm bg-slate-50 border border-slate-200 rounded-xl px-4 py-3 focus:bg-white focus:ring-2 focus:ring-brand-500/20 focus:border-brand-500 outline-none transition-all placeholder:text-slate-300" placeholder="Örn: Araç">
                </div>
            </div>

            <div class="grid grid-cols-2 gap-5">
                <div class="space-y-1.5">
                    <label class="block text-[11px] font-bold text-slate-500 uppercase tracking-wider ml-1">Menü İkonu</label>
                    <div class="relative">
                        <i class="${icon} absolute left-4 top-1/2 -translate-y-1/2 text-slate-400" id="co_icon_preview"></i>
                        <input type="text" id="co_icon" value="${icon}" onkeyup="document.getElementById('co_icon_preview').className = this.value + ' absolute left-4 top-1/2 -translate-y-1/2 text-slate-400'" class="w-full text-sm bg-slate-50 border border-slate-200 rounded-xl pl-10 pr-4 py-3 focus:bg-white focus:ring-2 focus:ring-brand-500/20 focus:border-brand-500 outline-none transition-all" placeholder="fas fa-car">
                    </div>
                </div>
                <div class="space-y-1.5">
                    <label class="block text-[11px] font-bold text-slate-500 uppercase tracking-wider ml-1">Marka Rengi</label>
                    <div class="flex items-center gap-3">
                        <input type="color" id="co_color" value="${iconColor}" class="w-12 h-[46px] bg-slate-50 border border-slate-200 rounded-xl cursor-pointer p-1">
                        <div class="text-[10px] font-mono font-bold text-slate-400 flex-1 truncate uppercase" id="co_color_hex">${iconColor}</div>
                    </div>
                </div>
            </div>
            
            <div class="space-y-1.5">
                <label class="block text-[11px] font-bold text-slate-500 uppercase tracking-wider ml-1">Ek Açıklama</label>
                <textarea id="co_desc" rows="2" class="w-full text-sm bg-slate-50 border border-slate-200 rounded-xl px-4 py-3 focus:bg-white focus:ring-2 focus:ring-brand-500/20 focus:border-brand-500 outline-none transition-all resize-none placeholder:text-slate-300" placeholder="Bu modül ne için kullanılıyor? Kullanıcılarınıza yardımcı olacak kısa bir açıklama.">${description}</textarea>
            </div>

        </div>
        <div class="px-7 py-5 border-t border-slate-100 bg-slate-50 rounded-b-3xl flex items-center justify-between">
            <span class="text-[10px] text-slate-400 font-bold"><i class="fas fa-magic mr-1"></i> Yapılandırma alanları kayıt sonrası düzenlenebilir.</span>
            <div class="flex gap-3">
                <button onclick="closeCustomObjectModal()" class="px-5 py-2.5 rounded-xl text-sm font-bold text-slate-600 hover:bg-slate-200 transition-colors">İptal et</button>
                <button onclick="saveCustomObject(${obj?.id || 'null'})" class="px-6 py-2.5 rounded-xl text-sm font-bold bg-brand-600 text-white hover:bg-brand-700 shadow-md shadow-brand-600/20 transition-all flex items-center gap-2" id="co_save_btn">
                    <span>${isEdit ? 'Güncelle' : 'Oluştur'}</span>
                    <i class="fas ${isEdit ? 'fa-check' : 'fa-arrow-right'} text-[10px]"></i>
                </button>
            </div>
        </div>
    </div>
    `;
    
    document.body.appendChild(overlay);
    
    // Animate inner content
    setTimeout(() => {
        const content = document.getElementById('co-modal-content');
        if(content) {
            content.style.transform = 'scale(1)';
        }
        
        const cc = document.getElementById('co_color');
        if(cc) {
            cc.addEventListener('input', (e) => {
                document.getElementById('co_color_hex').textContent = e.target.value;
            });
        }
    }, 20);
}

function closeCustomObjectModal() {
    const el = document.getElementById('co-modal-overlay');
    if (el) {
        el.style.opacity = '0';
        const content = document.getElementById('co-modal-content');
        if(content) content.style.transform = 'scale(0.95) translateY(10px)';
        setTimeout(() => el.remove(), 200);
    }
}

async function saveCustomObject(id = null) {
    const name = document.getElementById('co_name').value.trim();
    const plural = document.getElementById('co_plural').value.trim();
    const singular = document.getElementById('co_singular').value.trim();
    const icon = document.getElementById('co_icon').value.trim();
    const color = document.getElementById('co_color').value.trim();
    const desc = document.getElementById('co_desc').value.trim();
    
    if (!name || !plural || !singular) {
        showGlobalToast('Lütfen kimlik, çoğul ve tekil isim alanlarını doldurun.', 'error');
        return;
    }
    
    const btn = document.getElementById('co_save_btn');
    const oldHtml = btn.innerHTML;
    btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> İşleniyor';
    btn.disabled = true;
    
    // Yeni oluştururken örnek şema olarak sadece Ad alanı koyuyoruz
    const payload = {
        name,
        plural_label: plural,
        singular_label: singular,
        description: desc,
        icon,
        icon_color: color
    };
    
    if (id === null) {
        payload.schema_config = [
            { "name": "isim", "label": "Tanım", "type": "text", "required": true }
        ];
    }
    
    try {
        const csrfMeta = document.querySelector('meta[name="csrf-token"]');
        const token = csrfMeta ? csrfMeta.content : '';
        
        const url = id ? '/api/custom-objects/' + id : '/api/custom-objects';
        const method = id ? 'PUT' : 'POST';
        
        const res = await fetch(url, {
            method: method,
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': token
            },
            body: JSON.stringify(payload)
        });
        
        if (!res.ok) {
            const err = await res.json();
            throw new Error(err.error || 'İşlem başarısız');
        }
        
        showGlobalToast(`Özel nesne başarıyla ${id ? 'güncellendi' : 'oluşturuldu'}.`, 'success');
        closeCustomObjectModal();
        loadCustomObjects();
        
    } catch (e) {
        btn.innerHTML = oldHtml;
        btn.disabled = false;
        showGlobalToast(e.message, 'error');
    }
}

async function deleteCustomObject(id) {
    if (!confirm('DİKKAT! Bu özel nesneyi silmek istediğinize emin misiniz? Bu işlem, eklediğiniz araç/mülk vb. gibi TÜM KAYITLARI da silecektir. Geri alınamaz!')) return;
    
    try {
        const csrfMeta = document.querySelector('meta[name="csrf-token"]');
        const token = csrfMeta ? csrfMeta.content : '';
        
        const res = await fetch('/api/custom-objects/' + id, {
            method: 'DELETE',
            headers: {
                'X-CSRFToken': token
            }
        });
        
        if (!res.ok) throw new Error('Silinemedi');
        
        showGlobalToast('Özel nesne ve bağlı tüm kayıtlar silindi.', 'success');
        loadCustomObjects();
        
    } catch (e) {
        showGlobalToast(e.message, 'error');
    }
}

async function editCustomObject(id) {
    try {
        const res = await fetch('/api/custom-objects');
        if(!res.ok) throw new Error();
        const data = await res.json();
        const obj = data.custom_objects.find(x => x.id === id);
        if (obj) openCustomObjectModal(obj);
    } catch(e) {
        showGlobalToast('Nesne bilgisi alınamadı.', 'error');
    }
}

function showGlobalToast(msg, type='info') {
    if (typeof showToast === 'function') {
        showToast(msg, type);   // settings.html'deki mevcut global toast yapısı
    } else {
        alert((type==='error'?'Hata: ':'') + msg);
    }
}

// ============================================
// SCHEMA DESIGNER (ALAN YAPILANDIRICI)
// ============================================

let currentSchemaObj = null;

async function editSchema(id) {
    try {
        const res = await fetch('/api/custom-objects');
        if(!res.ok) throw new Error();
        const data = await res.json();
        currentSchemaObj = data.custom_objects.find(x => x.id === id);
        
        if (currentSchemaObj) {
            if (!Array.isArray(currentSchemaObj.schema_config)) {
                currentSchemaObj.schema_config = [];
            }
            openSchemaModal();
            renderSchemaFields();
        }
    } catch(e) {
        showGlobalToast('Nesne bilgisi alınamadı.', 'error');
    }
}

function openSchemaModal() {
    const existing = document.getElementById('co-schema-modal-overlay');
    if (existing) existing.remove();
    
    const obj = currentSchemaObj;
    
    const overlay = document.createElement('div');
    overlay.id = 'co-schema-modal-overlay';
    overlay.className = 'fixed inset-0 bg-slate-900/40 backdrop-blur-sm z-[100] flex items-center justify-center p-4 transition-opacity';
    
    overlay.style.opacity = '0';
    setTimeout(() => {
        overlay.style.opacity = '1';
        overlay.style.transition = 'opacity 0.2s cubic-bezier(0.4, 0, 0.2, 1)';
    }, 10);
    
    overlay.innerHTML = `
    <div class="bg-white rounded-3xl shadow-2xl w-full max-w-2xl overflow-hidden flex flex-col max-h-[90vh] transform transition-transform duration-200 scale-95 origin-bottom" id="co-schema-content">
        <div class="px-7 py-5 border-b border-slate-100 flex items-center justify-between shadow-sm z-10">
            <div class="flex items-center gap-4">
                <div class="w-12 h-12 rounded-2xl flex items-center justify-center" style="background-color: ${obj.icon_color}15; color: ${obj.icon_color}">
                    <i class="${obj.icon} text-xl"></i>
                </div>
                <div>
                    <h3 class="font-bold text-slate-800 text-lg">${obj.plural_label} > Alan Yapılandırması</h3>
                    <p class="text-xs font-medium text-slate-500 mt-0.5">Bu nesne için tutulacak bilgi alanlarını yönetin.</p>
                </div>
            </div>
            <button onclick="closeSchemaModal()" class="w-8 h-8 flex items-center justify-center rounded-full text-slate-400 hover:text-slate-700 hover:bg-slate-200 transition-all">
                <i class="fas fa-times"></i>
            </button>
        </div>
        
        <div class="p-7 overflow-y-auto flex-1 bg-slate-50/50 space-y-4" id="schema-fields-container">
            <!-- Fields will be rendered here -->
        </div>
        
        <div class="px-7 py-5 border-t border-slate-100 bg-white flex items-center justify-between">
            <button onclick="addSchemaField()" class="px-4 py-2 rounded-xl text-sm font-bold text-brand-600 bg-brand-50 hover:bg-brand-100 transition-colors flex items-center gap-2 border border-brand-100">
                <i class="fas fa-plus"></i>
                <span>Yeni Alan Ekle</span>
            </button>
            <div class="flex gap-3">
                <button onclick="closeSchemaModal()" class="px-5 py-2.5 rounded-xl text-sm font-bold text-slate-600 hover:bg-slate-200 transition-colors">Vazgeç</button>
                <button onclick="saveSchema()" class="px-6 py-2.5 rounded-xl text-sm font-bold bg-slate-800 text-white hover:bg-slate-900 shadow-md transition-all flex items-center gap-2" id="co_schema_save_btn">
                    <i class="fas fa-save"></i>
                    <span>Şemayı Kaydet</span>
                </button>
            </div>
        </div>
    </div>
    `;
    
    document.body.appendChild(overlay);
    
    setTimeout(() => {
        const content = document.getElementById('co-schema-content');
        if(content) content.style.transform = 'scale(1)';
    }, 20);
}

function closeSchemaModal() {
    const el = document.getElementById('co-schema-modal-overlay');
    if (el) {
        el.style.opacity = '0';
        const content = document.getElementById('co-schema-content');
        if(content) content.style.transform = 'scale(0.95) translateY(10px)';
        setTimeout(() => el.remove(), 200);
    }
}

function renderSchemaFields() {
    const container = document.getElementById('schema-fields-container');
    if (!container) return;
    
    if (currentSchemaObj.schema_config.length === 0) {
        container.innerHTML = `
            <div class="text-center py-10 bg-white border border-slate-200 border-dashed rounded-2xl">
                <i class="fas fa-stream text-3xl text-slate-300 mb-3 block"></i>
                <p class="text-sm font-bold text-slate-600">Henüz hiçbir alan eklenmemiş.</p>
                <p class="text-xs text-slate-400 mt-1">Örn: "Plaka", "Marka", "Açıklama" gibi alanlarınızı hemen ekleyin.</p>
            </div>
        `;
        return;
    }
    
    let html = '';
    currentSchemaObj.schema_config.forEach((field, index) => {
        const typeOptions = [
            {val: 'text', label: 'Metin (Tek Satır)'},
            {val: 'textarea', label: 'Uzun Metin (Açıklama)'},
            {val: 'number', label: 'Sayı / Tutar'},
            {val: 'date', label: 'Tarih'},
            {val: 'select', label: 'Açılır Liste (Seçim)'},
            {val: 'boolean', label: 'Onay Kutusu (Evet/Hayır)'}
        ];
        
        let selectHtml = '<select class="w-full text-xs font-medium bg-slate-50 border border-slate-200 rounded-lg px-3 py-2 outline-none field-type-select" data-index="'+index+'" onchange="updateFieldType('+index+', this.value)">';
        typeOptions.forEach(opt => {
            selectHtml += `<option value="${opt.val}" ${field.type === opt.val ? 'selected' : ''}>${opt.label}</option>`;
        });
        selectHtml += '</select>';
        
        // Show options input ONLY if type is 'select'
        const optionsHtml = field.type === 'select' 
            ? `<div class="mt-3">
                 <label class="block text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-1">Seçenekler (Virgülle ayırın)</label>
                 <input type="text" class="w-full text-xs bg-slate-50 border border-slate-200 rounded-lg px-3 py-2 outline-none field-options-input" data-index="${index}" value="${field.options ? field.options.join(', ') : ''}" placeholder="Örn: Honda, Toyota, BMW" onchange="updateFieldOptions(${index}, this.value)">
               </div>` 
            : '';

        html += `
        <div class="bg-white border border-slate-200 rounded-2xl p-5 relative shadow-sm hover:border-brand-200 transition-colors group">
            <button onclick="removeSchemaField(${index})" class="absolute right-4 top-4 w-7 h-7 flex items-center justify-center rounded-lg text-slate-300 hover:text-red-500 hover:bg-red-50 transition-colors" title="Alanı Sil">
                <i class="fas fa-trash-alt text-xs"></i>
            </button>
            
            <div class="flex items-start gap-4 pr-8">
                <div class="w-10 h-10 rounded-xl bg-slate-50 border border-slate-100 flex items-center justify-center text-slate-400 shrink-0">
                    <span class="font-mono text-xs font-bold">${index + 1}</span>
                </div>
                
                <div class="flex-1 grid grid-cols-2 gap-4">
                    <div>
                        <label class="block text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-1">Görünür İsim (Label)</label>
                        <input type="text" class="w-full text-sm font-bold text-slate-700 border-b border-transparent hover:border-slate-200 focus:border-brand-500 outline-none pb-1 bg-transparent transition-colors field-label-input" placeholder="Örn: Araç Plakası" value="${field.label}" data-index="${index}" onchange="updateFieldLabel(${index}, this.value)">
                        
                        <div class="mt-2 flex items-center gap-2">
                            <input type="checkbox" id="req_${index}" class="rounded border-slate-300 text-brand-500 focus:ring-brand-500 cursor-pointer w-3.5 h-3.5" ${field.required ? 'checked' : ''} onchange="updateFieldRequired(${index}, this.checked)">
                            <label for="req_${index}" class="text-xs font-medium text-slate-500 cursor-pointer">Bu alan doldurulması zorunludur</label>
                        </div>
                    </div>
                    
                    <div>
                        <label class="block text-[10px] font-bold text-slate-400 uppercase tracking-widest mb-1">Veri Tipi</label>
                        ${selectHtml}
                        ${optionsHtml}
                    </div>
                </div>
            </div>
            
            <div class="mt-3 pt-3 border-t border-slate-100 flex items-center justify-between">
                <p class="text-[10px] font-medium text-slate-400"><i class="fas fa-terminal mr-1"></i> API Anahtarı: <span class="font-mono font-bold text-slate-500">${field.name}</span></p>
                <p class="text-[10px] text-slate-400">Veritabanında saklanan eşsiz anahtar (otomatik oluşturuldu).</p>
            </div>
        </div>
        `;
    });
    
    container.innerHTML = html;
}

// -- Alan Güncelleme Fonksiyonları --
function updateFieldLabel(idx, val) {
    if(!val.trim()) return;
    currentSchemaObj.schema_config[idx].label = val.trim();
    // API anahtarını otomatik güncelle eğer yeni oluşturulmuş, henüz kaydedilmemiş bir alansa.
    if (currentSchemaObj.schema_config[idx].is_new) {
        currentSchemaObj.schema_config[idx].name = val.trim().toLowerCase().replace(/[^a-z0-9]/g, '_').replace(/_+/g, '_').replace(/^_|_$/g, '');
        renderSchemaFields();
    }
}
function updateFieldType(idx, val) {
    currentSchemaObj.schema_config[idx].type = val;
    renderSchemaFields(); // Re-render to show/hide options input
}
function updateFieldOptions(idx, val) {
    // Split by comma, trim spaces, remove empty
    currentSchemaObj.schema_config[idx].options = val.split(',').map(s => s.trim()).filter(s => s.length > 0);
}
function updateFieldRequired(idx, isChecked) {
    currentSchemaObj.schema_config[idx].required = isChecked;
}

function addSchemaField() {
    const newField = {
        name: "yeni_alan_" + Date.now().toString().slice(-4),
        label: "Yeni Alan",
        type: "text",
        required: false,
        is_new: true // Temp flag
    };
    currentSchemaObj.schema_config.push(newField);
    renderSchemaFields();
    
    // Scroll to bottom
    setTimeout(() => {
        const cont = document.getElementById('schema-fields-container');
        cont.scrollTop = cont.scrollHeight;
    }, 50);
}

function removeSchemaField(index) {
    if(!confirm('Bu alanı silmek istediğinize emin misiniz? (Kaydedilene kadar silinmez)')) return;
    currentSchemaObj.schema_config.splice(index, 1);
    renderSchemaFields();
}

async function saveSchema() {
    const btn = document.getElementById('co_schema_save_btn');
    const oldHtml = btn.innerHTML;
    
    // Temizle (temp bayrakları kaldır)
    const cleanedConfig = currentSchemaObj.schema_config.map(f => {
        const nf = {...f};
        delete nf.is_new;
        if (!nf.name) nf.name = 'field_' + Math.random().toString(36).substr(2, 5);
        return nf;
    });
    
    btn.innerHTML = '<i class="fas fa-spinner fa-spin"></i> İşleniyor';
    btn.disabled = true;
    
    try {
        const csrfMeta = document.querySelector('meta[name="csrf-token"]');
        const token = csrfMeta ? csrfMeta.content : '';
        
        const res = await fetch('/api/custom-objects/' + currentSchemaObj.id, {
            method: 'PUT',
            headers: {
                'Content-Type': 'application/json',
                'X-CSRFToken': token
            },
            body: JSON.stringify({
                schema_config: cleanedConfig
            })
        });
        
        if (!res.ok) {
            const err = await res.json();
            throw new Error(err.error || 'İşlem başarısız');
        }
        
        showGlobalToast('Şeması başarıyla kaydedildi!', 'success');
        closeSchemaModal();
        loadCustomObjects(); // Refresh parent list to update field count
        
    } catch (e) {
        showGlobalToast(e.message, 'error');
        btn.innerHTML = oldHtml;
        btn.disabled = false;
    }
}

