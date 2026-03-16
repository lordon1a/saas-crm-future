// WhatsApp CRM - Automation Management Frontend
const API_BASE = '/api/automation';

let currentTab = 'auto-replies';
let autoReplies = [];
let assignmentRules = [];
let automationRules = [];
let scheduledMessages = [];

// ═══ UTILITY FUNCTIONS ═══

function escapeHtml(str) {
    if (!str) return '';
    return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
}

function showToast(message, type = 'success') {
    const toast = document.createElement('div');
    const isError = type === 'error';
    
    toast.className = `fixed top-4 right-4 z-50 flex items-center gap-3 px-4 py-3 rounded-xl shadow-lg bg-white border ${isError ? 'border-red-100' : 'border-emerald-100'} animate-fade-in-up`;
    
    toast.innerHTML = `
        <div class="w-8 h-8 rounded-full flex items-center justify-center ${isError ? 'bg-red-50 text-red-500' : 'bg-emerald-50 text-emerald-500'}">
            <i class="fas ${isError ? 'fa-exclamation-circle' : 'fa-check'}"></i>
        </div>
        <span class="text-sm font-semibold text-slate-700">${escapeHtml(message)}</span>
    `;
    
    document.body.appendChild(toast);
    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transform = 'translateY(-10px)';
        toast.style.transition = 'all 0.3s ease-out';
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}

// ═══ TAB SWITCHING ═══

function switchTab(tabName) {
    currentTab = tabName;
    
    // Update tab buttons
    document.querySelectorAll('.tab-btn').forEach(btn => {
        btn.classList.remove('active', 'bg-white', 'text-brand-600', 'shadow-sm', 'ring-1', 'ring-slate-200/50');
        btn.classList.add('text-slate-600');
    });
    
    const activeBtn = document.getElementById(`tab-${tabName}`);
    if (activeBtn) {
        activeBtn.classList.add('active', 'bg-white', 'text-brand-600', 'shadow-sm', 'ring-1', 'ring-slate-200/50');
        activeBtn.classList.remove('text-slate-600');
    }
    
    // Update panels
    document.querySelectorAll('.tab-panel').forEach(panel => {
        panel.classList.remove('active');
    });
    
    const activePanel = document.getElementById(`panel-${tabName}`);
    if (activePanel) {
        activePanel.classList.add('active');
    }
    
    // Load data for the active tab
    switch(tabName) {
        case 'auto-replies':
            loadAutoReplies();
            break;
        case 'assignment':
            loadAssignmentRules();
            break;
        case 'rules':
            loadAutomationRules();
            break;
        case 'scheduled':
            loadScheduledMessages();
            break;
    }
}

// ═══ MODAL FUNCTIONS ═══

function openModal(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) {
        modal.classList.remove('hidden');
        modal.classList.add('flex');
    }
}

function closeModal(modalId) {
    const modal = document.getElementById(modalId);
    if (modal) {
        modal.classList.add('hidden');
        modal.classList.remove('flex');
    }
}

function openAutoReplyModal(replyId = null) {
    if (replyId) {
        const reply = autoReplies.find(r => r.id === replyId);
        if (reply) {
            document.getElementById('ar_id').value = reply.id;
            document.getElementById('ar_name').value = reply.name;
            document.getElementById('ar_keywords').value = reply.keywords;
            document.getElementById('ar_message').value = reply.reply_message;
            document.getElementById('ar_match_type').value = reply.match_type;
            document.getElementById('ar_delay').value = reply.reply_delay || 1;
        }
    } else {
        document.getElementById('ar_id').value = '';
        document.getElementById('ar_name').value = '';
        document.getElementById('ar_keywords').value = '';
        document.getElementById('ar_message').value = '';
        document.getElementById('ar_match_type').value = 'contains';
        document.getElementById('ar_delay').value = 1;
    }
    openModal('autoReplyModal');
}

function openAssignmentModal() {
    showToast('Atama kuralı oluşturma yakında eklenecek', 'info');
}

function openRuleModal() {
    showToast('Otomasyon kuralı oluşturma yakında eklenecek', 'info');
}

function openScheduledModal() {
    const modal = document.getElementById('scheduledModal');
    modal.classList.remove('hidden');
    modal.classList.add('flex');
    
    // Reset form
    document.getElementById('sm_id').value = '';
    document.getElementById('sm_target_type').value = 'broadcast';
    document.getElementById('sm_target_id').value = '';
    document.getElementById('sm_target_segment').value = '';
    document.getElementById('sm_message').value = '';
    document.getElementById('sm_schedule_type').value = 'once';
    document.getElementById('sm_scheduled_at').value = '';
    document.getElementById('sm_recurrence_pattern').value = 'daily';
    
    // Hide conditional fields
    document.getElementById('sm_target_id_container').classList.add('hidden');
    document.getElementById('sm_target_segment_container').classList.add('hidden');
    document.getElementById('sm_recurrence_container').classList.add('hidden');
    
    document.getElementById('scheduledModalTitle').textContent = 'Mesaj Zamanla';
}

function toggleRecurrence() {
    const scheduleType = document.getElementById('sm_schedule_type').value;
    const recurrenceContainer = document.getElementById('sm_recurrence_container');
    
    if (scheduleType === 'recurring') {
        recurrenceContainer.classList.remove('hidden');
    } else {
        recurrenceContainer.classList.add('hidden');
    }
}

// Target type change handler
document.addEventListener('DOMContentLoaded', () => {
    const targetTypeSelect = document.getElementById('sm_target_type');
    if (targetTypeSelect) {
        targetTypeSelect.addEventListener('change', (e) => {
            const targetType = e.target.value;
            const targetIdContainer = document.getElementById('sm_target_id_container');
            const targetSegmentContainer = document.getElementById('sm_target_segment_container');
            
            targetIdContainer.classList.add('hidden');
            targetSegmentContainer.classList.add('hidden');
            
            if (targetType === 'customer' || targetType === 'conversation') {
                targetIdContainer.classList.remove('hidden');
            } else if (targetType === 'segment') {
                targetSegmentContainer.classList.remove('hidden');
            }
        });
    }
});

async function saveScheduledMessage() {
    const targetType = document.getElementById('sm_target_type').value;
    const message = document.getElementById('sm_message').value.trim();
    const scheduledAt = document.getElementById('sm_scheduled_at').value;
    const scheduleType = document.getElementById('sm_schedule_type').value;
    
    if (!message) {
        showToast('Mesaj içeriği gerekli', 'error');
        return;
    }
    
    if (!scheduledAt) {
        showToast('Gönderim zamanı gerekli', 'error');
        return;
    }
    
    const payload = {
        target_type: targetType,
        message_body: message,
        scheduled_at: new Date(scheduledAt).toISOString(),
        schedule_type: scheduleType
    };
    
    // Add target-specific fields
    if (targetType === 'customer' || targetType === 'conversation') {
        const targetId = document.getElementById('sm_target_id').value;
        if (!targetId) {
            showToast('Hedef ID gerekli', 'error');
            return;
        }
        payload.target_id = parseInt(targetId);
    } else if (targetType === 'segment') {
        const targetSegment = document.getElementById('sm_target_segment').value.trim();
        if (!targetSegment) {
            showToast('Segment gerekli', 'error');
            return;
        }
        payload.target_segment = targetSegment;
    }
    
    // Add recurrence if recurring
    if (scheduleType === 'recurring') {
        payload.recurrence_pattern = document.getElementById('sm_recurrence_pattern').value;
    }
    
    try {
        const response = await fetch('/api/v1/scheduled-messages', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.error || 'Kaydetme başarısız');
        }
        
        closeModal('scheduledModal');
        showToast('Mesaj zamanlandı');
        loadScheduledMessages();
    } catch (error) {
        console.error('Save scheduled message error:', error);
        showToast(error.message || 'Mesaj zamanlanamadı', 'error');
    }
}

// ═══ AUTO REPLIES ═══

async function loadAutoReplies() {
    try {
        const response = await fetch(`${API_BASE}/auto-replies`);
        if (!response.ok) throw new Error('Failed to load');
        
        autoReplies = await response.json();
        renderAutoReplies();
    } catch (error) {
        console.error('Error loading auto-replies:', error);
        showToast('Otomatik yanıtlar yüklenemedi', 'error');
    }
}

function renderAutoReplies() {
    const grid = document.getElementById('autoRepliesGrid');
    if (!grid) return;
    
    if (autoReplies.length === 0) {
        grid.innerHTML = `
            <div class="col-span-2 flex flex-col items-center justify-center py-16 text-center">
                <div class="w-16 h-16 bg-slate-50 rounded-full flex items-center justify-center mb-4">
                    <i class="fas fa-bolt text-slate-300 text-2xl"></i>
                </div>
                <p class="text-sm font-medium text-slate-500 mb-2">Henüz otomatik yanıt yok</p>
                <p class="text-xs text-slate-400">Yeni bir otomatik yanıt oluşturarak başlayın</p>
            </div>
        `;
        return;
    }
    
    grid.innerHTML = autoReplies.map(reply => `
        <div class="bg-white rounded-2xl border border-slate-200 p-5 hover:shadow-md transition-all">
            <div class="flex items-start justify-between mb-3">
                <div class="flex items-center gap-3">
                    <div class="w-10 h-10 rounded-xl bg-brand-50 flex items-center justify-center">
                        <i class="fas fa-bolt text-brand-600"></i>
                    </div>
                    <div>
                        <h3 class="font-bold text-slate-800 text-sm">${escapeHtml(reply.name)}</h3>
                        <p class="text-xs text-slate-500">${reply.trigger_count || 0} kez çalıştı</p>
                    </div>
                </div>
                <label class="relative inline-flex items-center cursor-pointer">
                    <input type="checkbox" ${reply.is_active ? 'checked' : ''} 
                           onchange="toggleAutoReply(${reply.id})" 
                           class="sr-only peer">
                    <div class="w-11 h-6 bg-slate-200 peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-slate-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-brand-600"></div>
                </label>
            </div>
            
            <div class="space-y-2 mb-4">
                <div class="flex items-center gap-2 text-xs">
                    <span class="text-slate-400 font-medium">Anahtar Kelimeler:</span>
                    <span class="text-slate-700 font-semibold">${escapeHtml(reply.keywords)}</span>
                </div>
                <div class="flex items-center gap-2 text-xs">
                    <span class="text-slate-400 font-medium">Eşleşme:</span>
                    <span class="px-2 py-0.5 bg-slate-100 text-slate-700 rounded-lg font-semibold">${escapeHtml(reply.match_type)}</span>
                </div>
            </div>
            
            <div class="bg-slate-50 rounded-xl p-3 mb-4">
                <p class="text-xs text-slate-600 line-clamp-2">${escapeHtml(reply.reply_message)}</p>
            </div>
            
            <div class="flex gap-2">
                <button onclick="openAutoReplyModal(${reply.id})" 
                        class="flex-1 px-3 py-2 bg-slate-50 text-slate-600 rounded-xl text-xs font-bold hover:bg-slate-100 transition-all">
                    <i class="fas fa-edit mr-1"></i> Düzenle
                </button>
                <button onclick="deleteAutoReply(${reply.id})" 
                        class="px-3 py-2 bg-red-50 text-red-600 rounded-xl text-xs font-bold hover:bg-red-100 transition-all">
                    <i class="fas fa-trash"></i>
                </button>
            </div>
        </div>
    `).join('');
}

async function saveAutoReply() {
    const id = document.getElementById('ar_id').value;
    const name = document.getElementById('ar_name').value.trim();
    const keywords = document.getElementById('ar_keywords').value.trim();
    const message = document.getElementById('ar_message').value.trim();
    const matchType = document.getElementById('ar_match_type').value;
    const delay = parseInt(document.getElementById('ar_delay').value) || 1;
    
    if (!name || !keywords || !message) {
        showToast('Lütfen tüm alanları doldurun', 'error');
        return;
    }
    
    const data = {
        name,
        keywords,
        reply_message: message,
        match_type: matchType,
        reply_delay: delay,
        is_active: true
    };
    
    try {
        const url = id ? `${API_BASE}/auto-replies/${id}` : `${API_BASE}/auto-replies`;
        const method = id ? 'PUT' : 'POST';
        
        const response = await fetch(url, {
            method,
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(data)
        });
        
        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.error || 'Kaydedilemedi');
        }
        
        showToast(id ? 'Otomatik yanıt güncellendi' : 'Otomatik yanıt oluşturuldu');
        closeModal('autoReplyModal');
        loadAutoReplies();
    } catch (error) {
        showToast(error.message, 'error');
    }
}

async function toggleAutoReply(replyId) {
    try {
        const reply = autoReplies.find(r => r.id === replyId);
        if (!reply) return;
        
        const response = await fetch(`${API_BASE}/auto-replies/${replyId}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ is_active: !reply.is_active })
        });
        
        if (!response.ok) throw new Error('Güncellenemedi');
        
        showToast(reply.is_active ? 'Otomatik yanıt devre dışı' : 'Otomatik yanıt aktif');
        loadAutoReplies();
    } catch (error) {
        showToast('Durum değiştirilemedi', 'error');
        loadAutoReplies();
    }
}

async function deleteAutoReply(replyId) {
    if (!confirm('Bu otomatik yanıtı silmek istediğinizden emin misiniz?')) return;
    
    try {
        const response = await fetch(`${API_BASE}/auto-replies/${replyId}`, {
            method: 'DELETE'
        });
        
        if (!response.ok) throw new Error('Silinemedi');
        
        showToast('Otomatik yanıt silindi');
        loadAutoReplies();
    } catch (error) {
        showToast('Silinemedi', 'error');
    }
}

// ═══ ASSIGNMENT RULES ═══

async function loadAssignmentRules() {
    try {
        const response = await fetch(`${API_BASE}/assignment-rules`);
        if (!response.ok) throw new Error('Failed to load');
        
        assignmentRules = await response.json();
        renderAssignmentRules();
    } catch (error) {
        console.error('Error loading assignment rules:', error);
        showToast('Atama kuralları yüklenemedi', 'error');
    }
}

function renderAssignmentRules() {
    const grid = document.getElementById('assignmentGrid');
    if (!grid) return;
    
    if (assignmentRules.length === 0) {
        grid.innerHTML = `
            <div class="flex flex-col items-center justify-center py-16 text-center">
                <div class="w-16 h-16 bg-slate-50 rounded-full flex items-center justify-center mb-4">
                    <i class="fas fa-user-check text-slate-300 text-2xl"></i>
                </div>
                <p class="text-sm font-medium text-slate-500 mb-2">Henüz atama kuralı yok</p>
                <p class="text-xs text-slate-400">Yeni bir atama kuralı oluşturarak başlayın</p>
            </div>
        `;
        return;
    }
    
    grid.innerHTML = assignmentRules.map(rule => `
        <div class="bg-white rounded-2xl border border-slate-200 p-5 hover:shadow-md transition-all">
            <div class="flex items-start justify-between mb-3">
                <div class="flex items-center gap-3">
                    <div class="w-10 h-10 rounded-xl bg-purple-50 flex items-center justify-center">
                        <i class="fas fa-user-check text-purple-600"></i>
                    </div>
                    <div>
                        <h3 class="font-bold text-slate-800 text-sm">${escapeHtml(rule.name)}</h3>
                        <p class="text-xs text-slate-500">${rule.assignment_count || 0} kez atandı</p>
                    </div>
                </div>
                <span class="px-2 py-1 ${rule.is_active ? 'bg-emerald-50 text-emerald-700' : 'bg-slate-100 text-slate-500'} rounded-lg text-xs font-bold">
                    ${rule.is_active ? 'Aktif' : 'Pasif'}
                </span>
            </div>
            
            <div class="space-y-2 mb-4">
                <div class="flex items-center gap-2 text-xs">
                    <span class="text-slate-400 font-medium">Tip:</span>
                    <span class="text-slate-700 font-semibold">${escapeHtml(rule.assignment_type)}</span>
                </div>
                <div class="flex items-center gap-2 text-xs">
                    <span class="text-slate-400 font-medium">Öncelik:</span>
                    <span class="px-2 py-0.5 bg-slate-100 text-slate-700 rounded-lg font-semibold">${rule.priority}</span>
                </div>
            </div>
        </div>
    `).join('');
}

// ═══ AUTOMATION RULES ═══

async function loadAutomationRules() {
    try {
        const response = await fetch(`${API_BASE}/rules`);
        if (!response.ok) throw new Error('Failed to load');
        
        automationRules = await response.json();
        renderAutomationRules();
    } catch (error) {
        console.error('Error loading automation rules:', error);
        showToast('Otomasyon kuralları yüklenemedi', 'error');
    }
}

function renderAutomationRules() {
    const grid = document.getElementById('rulesGrid');
    if (!grid) return;
    
    if (automationRules.length === 0) {
        grid.innerHTML = `
            <div class="flex flex-col items-center justify-center py-16 text-center">
                <div class="w-16 h-16 bg-slate-50 rounded-full flex items-center justify-center mb-4">
                    <i class="fas fa-diagram-project text-slate-300 text-2xl"></i>
                </div>
                <p class="text-sm font-medium text-slate-500 mb-2">Henüz otomasyon kuralı yok</p>
                <p class="text-xs text-slate-400">Yeni bir kural oluşturarak başlayın</p>
            </div>
        `;
        return;
    }
    
    grid.innerHTML = automationRules.map(rule => `
        <div class="bg-white rounded-2xl border border-slate-200 p-5 hover:shadow-md transition-all">
            <div class="flex items-start justify-between mb-3">
                <div class="flex items-center gap-3">
                    <div class="w-10 h-10 rounded-xl bg-indigo-50 flex items-center justify-center">
                        <i class="fas fa-diagram-project text-indigo-600"></i>
                    </div>
                    <div>
                        <h3 class="font-bold text-slate-800 text-sm">${escapeHtml(rule.name)}</h3>
                        <p class="text-xs text-slate-500">${rule.execution_count || 0} kez çalıştı</p>
                    </div>
                </div>
                <span class="px-2 py-1 ${rule.is_active ? 'bg-emerald-50 text-emerald-700' : 'bg-slate-100 text-slate-500'} rounded-lg text-xs font-bold">
                    ${rule.is_active ? 'Aktif' : 'Pasif'}
                </span>
            </div>
            
            ${rule.description ? `<p class="text-xs text-slate-600 mb-3">${escapeHtml(rule.description)}</p>` : ''}
            
            <div class="space-y-2">
                <div class="flex items-center gap-2 text-xs">
                    <span class="text-slate-400 font-medium">Tetikleyici:</span>
                    <span class="px-2 py-0.5 bg-slate-100 text-slate-700 rounded-lg font-semibold">${escapeHtml(rule.trigger_type)}</span>
                </div>
                <div class="flex items-center gap-2 text-xs">
                    <span class="text-slate-400 font-medium">Aksiyonlar:</span>
                    <span class="text-slate-700 font-semibold">${rule.actions?.length || 0} adet</span>
                </div>
            </div>
        </div>
    `).join('');
}

// ═══ SCHEDULED MESSAGES ═══

async function loadScheduledMessages() {
    try {
        const response = await fetch('/api/v1/scheduled-messages?status=pending');
        if (!response.ok) throw new Error('Failed to load');
        
        const data = await response.json();
        scheduledMessages = data.messages || [];
        renderScheduledMessages();
    } catch (error) {
        console.error('Error loading scheduled messages:', error);
        showToast('Zamanlanmış mesajlar yüklenemedi', 'error');
    }
}

function renderScheduledMessages() {
    const grid = document.getElementById('scheduledGrid');
    if (!grid) return;
    
    if (scheduledMessages.length === 0) {
        grid.innerHTML = `
            <div class="flex flex-col items-center justify-center py-16 text-center">
                <div class="w-16 h-16 bg-slate-50 rounded-full flex items-center justify-center mb-4">
                    <i class="fas fa-clock text-slate-300 text-2xl"></i>
                </div>
                <p class="text-sm font-medium text-slate-500 mb-2">Henüz zamanlanmış mesaj yok</p>
                <p class="text-xs text-slate-400">Yeni bir mesaj zamanlayarak başlayın</p>
            </div>
        `;
        return;
    }
    
    grid.innerHTML = scheduledMessages.map(msg => {
        const scheduledDate = new Date(msg.scheduled_at);
        const dateStr = scheduledDate.toLocaleDateString('tr-TR', { 
            day: 'numeric', 
            month: 'short', 
            year: 'numeric',
            hour: '2-digit',
            minute: '2-digit'
        });
        
        return `
            <div class="bg-white rounded-2xl border border-slate-200 p-5 hover:shadow-md transition-all">
                <div class="flex items-start justify-between mb-3">
                    <div class="flex items-center gap-3">
                        <div class="w-10 h-10 rounded-xl bg-amber-50 flex items-center justify-center">
                            <i class="fas fa-clock text-amber-600"></i>
                        </div>
                        <div>
                            <h3 class="font-bold text-slate-800 text-sm">${dateStr}</h3>
                            <p class="text-xs text-slate-500">${escapeHtml(msg.schedule_type)}</p>
                        </div>
                    </div>
                    <span class="px-2 py-1 bg-amber-50 text-amber-700 rounded-lg text-xs font-bold">
                        Bekliyor
                    </span>
                </div>
                
                <div class="bg-slate-50 rounded-xl p-3 mb-4">
                    <p class="text-xs text-slate-600 line-clamp-2">${escapeHtml(msg.message_body)}</p>
                </div>
                
                <button onclick="cancelScheduledMessage(${msg.id})" 
                        class="w-full px-3 py-2 bg-red-50 text-red-600 rounded-xl text-xs font-bold hover:bg-red-100 transition-all">
                    <i class="fas fa-times mr-1"></i> İptal Et
                </button>
            </div>
        `;
    }).join('');
}

async function cancelScheduledMessage(msgId) {
    if (!confirm('Bu zamanlanmış mesajı iptal etmek istediğinizden emin misiniz?')) return;
    
    try {
        const response = await fetch(`/api/v1/scheduled-messages/${msgId}`, {
            method: 'DELETE'
        });
        
        if (!response.ok) throw new Error('İptal edilemedi');
        
        showToast('Zamanlanmış mesaj iptal edildi');
        loadScheduledMessages();
    } catch (error) {
        showToast('İptal edilemedi', 'error');
    }
}

// ═══ STATISTICS ═══

async function loadStats() {
    try {
        const response = await fetch(`${API_BASE}/stats`);
        if (!response.ok) throw new Error('Failed to load stats');
        
        const stats = await response.json();
        
        // Update active count in header
        const totalActive = (stats.auto_replies?.active || 0) + 
                           (stats.assignment_rules?.active || 0) + 
                           (stats.rules?.active || 0);
        document.getElementById('activeCount').textContent = `${totalActive} Aktif Kural`;
        
        // Update sidebar stats
        document.getElementById('statExecutions').textContent = stats.executions_30d || 0;
        document.getElementById('statSuccessRate').textContent = `${stats.success_rate || 0}%`;
        
    } catch (error) {
        console.error('Error loading stats:', error);
    }
}

// ═══ INITIALIZATION ═══

document.addEventListener('DOMContentLoaded', () => {
    loadAutoReplies();
    loadStats();
    
    // Refresh stats every 30 seconds
    setInterval(loadStats, 30000);
});
