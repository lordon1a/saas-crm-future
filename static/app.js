// WhatsApp CRM - Frontend Controller (V4 - Multi-Tenant + Assignment + SSE)
const API_BASE = '/api';

let currentConversationId = null;
window.currentConvId = null;  // SSE toast için global alias

let currentCustomerId = null;
let currentFilter = '';
let currentTag = '';
let currentSearch = '';
let quickReplies = [];
let searchDebounceTimer = null;

// ─── Yardımcı Fonksiyonlar ──────────────────────────────────────────

function escapeHtml(str) {
    if (!str) return '';
    return String(str)
        .replace(/&/g, '&amp;')
        .replace(/</g, '&lt;')
        .replace(/>/g, '&gt;')
        .replace(/"/g, '&quot;')
        .replace(/'/g, '&#039;');
}

function formatTime(timestamp) {
    const date = new Date(timestamp + (timestamp.endsWith('Z') ? '' : 'Z'));
    return date.toLocaleTimeString('tr-TR', { hour: '2-digit', minute: '2-digit' });
}

function formatTimeAgo(timestamp) {
    const date = new Date(timestamp + (timestamp.endsWith('Z') ? '' : 'Z'));
    const now = new Date();
    const diff = now - date;
    const minutes = Math.floor(diff / 60000);
    const hours = Math.floor(diff / 3600000);
    const days = Math.floor(diff / 86400000);

    if (minutes < 1) return 'Şimdi';
    if (minutes < 60) return `${minutes}dk`;
    if (hours < 24) return `${hours}sa`;
    if (days < 7) return `${days}g`;
    return date.toLocaleDateString('tr-TR', { day: 'numeric', month: 'short' });
}

function getInitials(name) {
    if (!name) return '??';
    const parts = name.trim().split(' ');
    if (parts.length > 1) return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
    return name.substring(0, 2).toUpperCase();
}

function renderTagsForList(tagsStr) {
    if (!tagsStr) return '';
    const tags = tagsStr.split(',').map(t => t.trim());
    return tags.map(tag => {
        const conf = {
            'yeni_siparis': { label: 'Yeni Sipariş', color: 'bg-amber-100 text-amber-700 border-amber-200/50' },
            'kargo_sorunu': { label: 'Kargo Sorunu', color: 'bg-purple-100 text-purple-700 border-purple-200/50' },
            'odeme_bekliyor': { label: 'Ödeme Bekliyor', color: 'bg-red-100 text-red-700 border-red-200/50' },
            'kargolandi': { label: 'Kargolandı', color: 'bg-emerald-100 text-emerald-700 border-emerald-200/50' }
        };
        const activeConf = conf[tag] || { label: tag, color: 'bg-slate-100 text-slate-600 border-slate-200/50' };
        return `<span class="inline-flex items-center px-2 py-0.5 rounded text-[10px] font-semibold border ${activeConf.color}">${activeConf.label}</span>`;
    }).join('');
}

// ─── Toast Bildirimi (Modern) ─────────────────────────────────────

function showToast(message, type = 'info') {
    const container = document.getElementById('toastContainer');
    if (!container) return;

    const toast = document.createElement('div');
    const isError = type === 'error';

    toast.className = `flex items-center gap-3 px-4 py-3 rounded-xl shadow-lg shadow-slate-200/50 border bg-white ${isError ? 'border-red-100' : 'border-emerald-100'} animate-fade-in-up`;

    toast.innerHTML = `
        <div class="w-8 h-8 rounded-full flex items-center justify-center ${isError ? 'bg-red-50 text-red-500 shadow-sm' : 'bg-emerald-50 text-emerald-500 shadow-sm'}">
            <i class="fas ${isError ? 'fa-exclamation-circle' : 'fa-check'}"></i>
        </div>
        <span class="text-sm font-semibold text-slate-700">${escapeHtml(message)}</span>
    `;

    container.appendChild(toast);
    setTimeout(() => {
        toast.style.opacity = '0';
        toast.style.transform = 'translateY(10px)';
        toast.style.transition = 'all 0.3s ease-out';
        setTimeout(() => toast.remove(), 300);
    }, 4000);
}

// ─── Sohbetleri Yükleme ──────────────────────────────────────────

async function loadConversations() {
    try {
        let url = `${API_BASE}/conversations`;
        const params = new URLSearchParams();
        if (currentFilter) params.set('status', currentFilter);
        if (currentTag) params.set('tag', currentTag);
        if (currentSearch) params.set('search', currentSearch);
        if (params.toString()) url += '?' + params.toString();

        const response = await fetch(url);
        if (response.status === 401) { window.location.href = '/login'; return; }
        const data = await response.json();

        const conversations = data.conversations || [];
        const counts = data.counts || { total: 0, open: 0, pending: 0 };

        document.getElementById('allCount').textContent = counts.total;
        document.getElementById('openCount').textContent = counts.open;
        document.getElementById('pendingCount').textContent = counts.pending;

        const listEl = document.getElementById('conversationList');
        listEl.innerHTML = '';

        if (conversations.length === 0) {
            listEl.innerHTML = `
                <div class="flex flex-col items-center justify-center py-12 px-4 text-center">
                    <div class="w-12 h-12 bg-slate-50 rounded-full flex items-center justify-center mb-3">
                        <i class="fas fa-inbox text-slate-300 text-xl"></i>
                    </div>
                    <p class="text-sm font-medium text-slate-500">${currentSearch ? 'Sonuç bulunamadı' : 'Listeniz şu an boş'}</p>
                </div>`;
            return;
        }

        conversations.forEach(conv => {
            const div = document.createElement('div');
            const isActive = conv.id === currentConversationId;
            const hasUnread = conv.unread_count > 0;

            // Modern SaaS item classes
            let baseClasses = "flex items-start gap-3 p-3 rounded-2xl cursor-pointer transition-all duration-300 border border-transparent";
            if (isActive) {
                baseClasses += " bg-white shadow-sm border-slate-100 ring-1 ring-brand-500/10";
            } else {
                baseClasses += " hover:bg-white hover:shadow-sm";
            }

            div.className = baseClasses;
            div.dataset.id = conv.id;

            const name = conv.customer.profile_name || conv.customer.phone_number || 'Bilinmeyen';
            const initials = getInitials(name);
            const timeAgo = formatTimeAgo(conv.last_message_at);
            const preview = escapeHtml(conv.last_message || 'Mesaj yok');

            // CRM Contact info
            let crmBadge = '';
            if (conv.customer && conv.customer.crm_contact) {
                const crmContact = conv.customer.crm_contact;
                const roleEmoji = {
                    'Decision Maker': '👑',
                    'Champion': '⭐',
                    'Influencer': '📊',
                    'Blocker': '🚫',
                    'User': '👤'
                }[crmContact.role] || '';
                
                const roleColor = {
                    'Decision Maker': 'bg-purple-100 text-purple-700',
                    'Champion': 'bg-yellow-100 text-yellow-700',
                    'Influencer': 'bg-blue-100 text-blue-700',
                    'Blocker': 'bg-red-100 text-red-700',
                    'User': 'bg-slate-100 text-slate-600'
                }[crmContact.role] || 'bg-slate-100 text-slate-600';
                
                if (crmContact.role) {
                    crmBadge = `<span class="px-1.5 py-0.5 rounded text-[10px] font-bold ${roleColor}">${roleEmoji} ${crmContact.role}</span>`;
                }
            }

            // Unread styling
            const nameClass = hasUnread ? "font-bold text-slate-900" : "font-semibold text-slate-700";
            const previewClass = hasUnread ? "text-slate-800 font-medium" : "text-slate-500";

            div.innerHTML = `
                <div class="relative flex-shrink-0 mt-0.5">
                    <div class="w-11 h-11 rounded-full bg-gradient-to-br from-indigo-50 to-indigo-100 flex items-center justify-center text-indigo-500 font-bold text-sm border border-white shadow-sm">
                        ${initials}
                    </div>
                </div>
                <div class="flex-1 min-w-0">
                    <div class="flex justify-between items-center mb-1">
                        <div class="flex items-center gap-2 min-w-0">
                            <h4 class="text-sm truncate ${nameClass}">${escapeHtml(name)}</h4>
                            ${crmBadge}
                        </div>
                        <span class="text-[11px] text-slate-400 whitespace-nowrap ml-2">${timeAgo}</span>
                    </div>
                    <p class="text-[13px] truncate ${previewClass}">${preview}</p>
                    <div class="flex items-center gap-1.5 mt-2">
                        ${renderTagsForList(conv.tags)}
                        ${hasUnread ? `<span class="ml-auto inline-flex items-center justify-center min-w-[20px] h-5 px-1.5 text-[11px] font-bold text-white bg-brand-500 rounded-full shadow-sm">${conv.unread_count}</span>` : ''}
                    </div>
                </div>
            `;

            div.onclick = () => selectConversation(conv.id, name, conv.customer.phone_number, initials);
            listEl.appendChild(div);
        });
    } catch (error) {
        console.error('Error loading conversations:', error);
    }
}

// ─── Sohbet Seçimi ─────────────────────────────────────── 
const _convCache = new Map();
const _CACHE_TTL = 120000;

function showMessagesSkeleton() {
    const container = document.getElementById('messagesContainer');
    container.innerHTML = `
        <div class="flex mb-4 justify-start animate-pulse">
            <div class="bg-slate-100 rounded-2xl rounded-tl-sm h-12 w-48"></div>
        </div>
        <div class="flex mb-4 justify-end animate-pulse">
            <div class="bg-indigo-100 rounded-2xl rounded-tr-sm h-10 w-64"></div>
        </div>
        <div class="flex mb-4 justify-start animate-pulse">
            <div class="bg-slate-100 rounded-2xl rounded-tl-sm h-14 w-52"></div>
        </div>
    `;
}

async function selectConversation(conversationId, customerName, customerPhone, initials) {
    document.querySelectorAll('#conversationList > div[data-id]').forEach(el => {
        el.className = 'flex items-start gap-3 p-3 rounded-2xl cursor-pointer transition-all duration-200 border border-transparent hover:bg-white hover:shadow-sm';
    });
    const activeItem = document.querySelector(`[data-id="${conversationId}"]`);
    if (activeItem) {
        activeItem.className = 'flex items-start gap-3 p-3 rounded-2xl cursor-pointer transition-all duration-200 border border-slate-100 bg-white shadow-sm ring-1 ring-brand-500/10';
    }

    currentConversationId = conversationId;
    window.currentConvId = conversationId;

    document.getElementById('emptyChat').classList.add('hidden');
    document.getElementById('chatContent').classList.remove('hidden');
    closeCustomerInfo();

    if (customerName) document.getElementById('customerName').textContent = customerName;
    if (customerPhone) document.getElementById('customerPhone').textContent = customerPhone;
    if (initials) {
        document.getElementById('customerInitials').textContent = initials;
        document.getElementById('infoInitials').textContent = initials;
    }

    showMessagesSkeleton();

    const cached = _convCache.get(conversationId);
    const now = Date.now();
    let fullData;

    if (cached && (now - cached.ts) < _CACHE_TTL) {
        fullData = cached.data;
    } else {
        try {
            const res = await fetch(`${API_BASE}/conversations/${conversationId}/full`);
            if (res.status === 401) { window.location.href = '/login'; return; }
            if (!res.ok) { fullData = null; }
            else {
                fullData = await res.json();
                _convCache.set(conversationId, { data: fullData, ts: Date.now() });
            }
        } catch { fullData = null; }
    }

    const container = document.getElementById('messagesContainer');
    container.innerHTML = '';
    const messages = fullData?.messages || [];

    if (messages.length === 0) {
        container.innerHTML = `<div class="flex flex-col items-center justify-center h-full text-center py-16 text-slate-400"><p class="text-sm">Henüz mesaj yok</p></div>`;
    } else {
        const fragment = document.createDocumentFragment();
        messages.forEach(msg => fragment.appendChild(buildMessageElement(msg)));
        container.appendChild(fragment);
        requestAnimationFrame(() => { container.scrollTop = container.scrollHeight; });
    }

    const detail = fullData?.conversation;
    if (detail) {
        const c = detail.customer;
        currentCustomerId = c.id;
        document.getElementById('customerName').textContent = c.profile_name || c.phone_number;
        document.getElementById('customerPhone').textContent = c.phone_number;
        document.getElementById('privateNotesInput').value = c.private_notes || '';
        const tagSelectEl = document.getElementById('tagSelect');
        if (tagSelectEl) {
            tagSelectEl.value = detail.tags || '';
            tagSelectEl.dataset.previousTag = detail.tags || '';
        }
        loadTeamForDropdown(detail.assigned_to);
        switchProfileTab('summary');
        loadCustomerProfile(c.id);
    }
}

function buildMessageElement(msg) {
    const div = document.createElement('div');
    const isAgent = msg.sender_type !== 'customer';
    div.className = `flex mb-4 animate-fade-in-up ${isAgent ? 'justify-end' : 'justify-start'}`;
    div.dataset.messageId = msg.id;

    let bubbleClasses = 'max-w-[70%] px-5 py-3.5 shadow-sm relative group ';
    if (isAgent) {
        bubbleClasses += 'bg-brand-600 text-white rounded-2xl rounded-tr-sm';
    } else {
        bubbleClasses += 'bg-white text-slate-800 rounded-2xl rounded-tl-sm border border-slate-200/60';
    }

    let mediaHtml = '';
    if (msg.media_url) {
        if (msg.media_type === 'image') {
            mediaHtml = `<div class="mb-2 rounded-xl overflow-hidden max-w-full"><img src="${escapeHtml(msg.media_url)}" alt="Görsel" class="max-h-64 w-auto object-cover" loading="lazy" onerror="this.style.display=\'none\'"></div>`;
        } else if (msg.media_type === 'document' || msg.media_type === 'audio' || msg.media_type === 'video') {
            const label = msg.media_type === 'document' ? '📄 Belge' : msg.media_type === 'audio' ? '🎵 Ses' : '🎥 Video';
            mediaHtml = `<a href="${escapeHtml(msg.media_url)}" target="_blank" rel="noopener" class="inline-flex items-center gap-2 text-sm underline font-medium mb-2 ${isAgent ? 'text-white/90' : 'text-brand-600'}">${label} – İndir</a>`;
        }
    }

    div.innerHTML = `
        <div class="${bubbleClasses}">
            ${msg.sender_name && isAgent ? `<div class="text-[10px] font-bold text-white/70 uppercase tracking-wider mb-1">${escapeHtml(msg.sender_name)}</div>` : ''}
            ${mediaHtml}
            <div class="text-[14.5px] leading-relaxed break-words">${escapeHtml(msg.message_body)}</div>
            <div class="text-[10px] text-opacity-60 text-right mt-1.5 ${isAgent ? 'text-white' : 'text-slate-500'} font-medium">${formatTime(msg.created_at)}</div>
        </div>
    `;
    return div;
}

function appendMessageToDOM(msg, tempId) {
    const container = document.getElementById('messagesContainer');
    if (!container) return null;
    const el = buildMessageElement(msg);
    if (tempId) el.dataset.tempId = tempId;
    container.appendChild(el);
    requestAnimationFrame(() => { container.scrollTop = container.scrollHeight; });
    return el;
}

function removeTempMessage(tempId) {
    if (!tempId) return;
    const container = document.getElementById('messagesContainer');
    const el = container && container.querySelector(`[data-temp-id="${tempId}"]`);
    if (el) el.remove();
}

async function sendMessage() {
    const input = document.getElementById('messageInput');
    const sendBtn = document.getElementById('sendBtn');
    const messageBody = input.value.trim();

    if (!messageBody || !currentConversationId) return;

    input.disabled = true;
    sendBtn.disabled = true;

    const tempId = 'temp-' + Date.now();
    const tempMsg = {
        id: tempId,
        sender_type: 'agent',
        message_body: messageBody,
        created_at: new Date().toISOString()
    };
    appendMessageToDOM(tempMsg, tempId);
    input.value = '';

    try {
        const response = await fetch(`${API_BASE}/messages/send`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ conversation_id: currentConversationId, message_body: messageBody })
        });
        const data = await response.json().catch(() => ({}));
        if (!response.ok) {
            removeTempMessage(tempId);
            input.value = messageBody;
            showToast(data.error || 'Gönderilemedi', 'error');
            return;
        }
        removeTempMessage(tempId);
        appendMessageToDOM(data.message || tempMsg);
        loadConversations();
    } catch (error) {
        removeTempMessage(tempId);
        input.value = messageBody;
        showToast('Gönderilemedi', 'error');
    } finally {
        input.disabled = false;
        sendBtn.disabled = false;
        input.focus();
    }
}

async function updateTag(tagValue) {
    if (!currentConversationId) return;
    const tagSelect = document.getElementById('tagSelect');
    if (!tagSelect) return;
    const previousValue = tagSelect.dataset.previousTag || '';
    tagSelect.dataset.previousTag = tagValue;
    try {
        const res = await fetch(`${API_BASE}/conversations/${currentConversationId}/tags`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ tags: tagValue || '' })
        });
        const data = await res.json().catch(() => ({}));
        if (!res.ok) {
            tagSelect.value = previousValue;
            tagSelect.dataset.previousTag = previousValue;
            showToast(data.error || 'Etiket güncellenemedi', 'error');
            return;
        }
        showToast('Etiket güncellendi');
        loadConversations();
    } catch (e) {
        tagSelect.value = previousValue;
        tagSelect.dataset.previousTag = previousValue;
        showToast('Etiket güncellenemedi', 'error');
    }
}

async function sendMedia(file) {
    if (!file || !currentConversationId) return;
    const sendBtn = document.getElementById('sendBtn');
    const attachBtn = document.getElementById('attachMediaBtn');
    const isImage = (file.type || '').startsWith('image/');
    const mediaType = isImage ? 'image' : 'document';
    sendBtn.disabled = true;
    if (attachBtn) attachBtn.disabled = true;
    const form = new FormData();
    form.append('conversation_id', currentConversationId);
    form.append('type', mediaType);
    form.append('file', file);
    try {
        const res = await fetch(`${API_BASE}/messages/send-media`, { method: 'POST', body: form });
        const data = await res.json().catch(() => ({}));
        if (!res.ok) {
            showToast(data.error || 'Medya gönderilemedi', 'error');
            return;
        }
        appendMessageToDOM(data.message);
        loadConversations();
        showToast('Gönderildi');
        document.getElementById('mediaFileInput').value = '';
    } catch (e) {
        showToast('Gönderilemedi', 'error');
    } finally {
        sendBtn.disabled = false;
        if (attachBtn) attachBtn.disabled = false;
    }
}

// ─── UI Helpers ───────────────────────────────────────────────────

function toggleCustomerInfo() {
    const panel = document.getElementById('customerInfoPanel');
    panel.classList.toggle('hidden');
    panel.classList.toggle('translate-x-full');
}

function closeCustomerInfo() {
    const panel = document.getElementById('customerInfoPanel');
    panel.classList.add('hidden');
    panel.classList.add('translate-x-full');
}

async function savePrivateNote() {
    if (!currentCustomerId) return;
    const note = document.getElementById('privateNotesInput').value;
    try {
        await fetch(`${API_BASE}/customers/${currentCustomerId}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ private_notes: note })
        });
        showToast('Not kaydedildi');
    } catch (e) { showToast('Hata oluştu', 'error'); }
}

// ─── Quick Replies ────────────────────────────────────────────────

async function loadQuickReplies() {
    try {
        const res = await fetch(`${API_BASE}/quick-replies`);
        const data = await res.json();
        quickReplies = Array.isArray(data) ? data : (data.quick_replies || []);
    } catch (e) { console.error('Quick replies error:', e); }
}

function renderQuickReplies(replies) {
    const list = document.getElementById('quickRepliesList');
    if (!list) return;
    list.innerHTML = '';

    if (replies.length === 0) {
        list.innerHTML = '<div class="p-4 text-center text-slate-400 text-xs">Hızlı yanıt bulunamadı. Ayarlar üzerinden ekleyebilirsiniz.</div>';
        return;
    }

    replies.forEach((reply, index) => {
        const title = reply.title || reply.shortcut || '';
        const body = reply.body || reply.content || '';
        const btn = document.createElement('button');
        btn.type = 'button';
        btn.className = `w-full text-left p-3 rounded-xl hover:bg-slate-50 transition-all group flex items-start gap-3 border border-transparent hover:border-slate-100 ${index === 0 ? 'bg-slate-50/50' : ''}`;
        btn.innerHTML = `
            <div class="w-8 h-8 rounded-lg bg-white border border-slate-100 flex items-center justify-center text-slate-400 group-hover:text-brand-500 transition-colors shrink-0 shadow-sm">
                <i class="fas fa-bolt text-xs"></i>
            </div>
            <div class="flex-1 min-w-0">
                <div class="flex items-center justify-between mb-0.5">
                    <span class="font-bold text-slate-700 text-xs truncate">${escapeHtml(title)}</span>
                </div>
                <p class="text-[11px] text-slate-500 line-clamp-2 leading-relaxed font-medium">${escapeHtml(body)}</p>
            </div>
        `;
        btn.onclick = () => {
            const input = document.getElementById('messageInput');
            input.value = body;
            closeQuickReplies();
            input.focus();
        };
        list.appendChild(btn);
    });
}

function showQuickReplies() {
    const modal = document.getElementById('quickRepliesModal');
    if (!modal) return;
    const isHidden = modal.classList.contains('hidden');
    if (isHidden) {
        modal.classList.remove('hidden');
        const qrSearchInput = document.getElementById('qrSearchInput');
        if (qrSearchInput) {
            qrSearchInput.value = '';
            qrSearchInput.focus();
        }
        renderQuickReplies(quickReplies);
    } else {
        closeQuickReplies();
    }
}

function closeQuickReplies() {
    const modal = document.getElementById('quickRepliesModal');
    if (modal) modal.classList.add('hidden');
}

// Search quick replies (title ve body ile ara)
document.getElementById('qrSearchInput')?.addEventListener('input', (e) => {
    const search = (e.target.value || '').toLowerCase();
    if (!search) {
        renderQuickReplies(quickReplies);
        return;
    }
    const filtered = quickReplies.filter(r => {
        const title = (r.title || r.shortcut || '').toLowerCase();
        const body = (r.body || r.content || '').toLowerCase();
        return title.includes(search) || body.includes(search);
    });
    renderQuickReplies(filtered);
});

// Hızlı yanıt butonu (şimşek ikonu) — tıklanınca paneli aç/kapat
document.getElementById('quickRepliesBtn')?.addEventListener('click', (e) => {
    e.preventDefault();
    e.stopPropagation();
    showQuickReplies();
});

document.getElementById('attachMediaBtn')?.addEventListener('click', () => {
    document.getElementById('mediaFileInput')?.click();
});
document.getElementById('mediaFileInput')?.addEventListener('change', (e) => {
    const f = e.target.files?.[0];
    if (f) sendMedia(f);
});

// Pane dışına tıklanınca hızlı yanıt panelini kapat
document.addEventListener('click', (e) => {
    const modal = document.getElementById('quickRepliesModal');
    const btn = document.getElementById('quickRepliesBtn');
    if (modal && !modal.classList.contains('hidden') && !modal.contains(e.target) && !btn?.contains(e.target))
        closeQuickReplies();
});

// ─── Profil & Geçmiş ──────────────────────────────────────────────

function switchProfileTab(name) {
    ['summary', 'history', 'notes'].forEach(t => {
        if (document.getElementById(`ppanel-${t}`)) document.getElementById(`ppanel-${t}`).classList.add('hidden');
    });
    if (document.getElementById(`ppanel-${name}`)) document.getElementById(`ppanel-${name}`).classList.remove('hidden');
    if (name === 'history') renderConvHistory();
}

async function loadCustomerProfile(customerId) {
    if (!customerId) return;
    try {
        const res = await fetch(`${API_BASE}/customers/${customerId}/profile`);
        const data = await res.json();
        if (document.getElementById('statTotal')) document.getElementById('statTotal').textContent = data.stats.total_conversations;
        if (document.getElementById('statOpen')) document.getElementById('statOpen').textContent = data.stats.open_conversations;
        window._customerConvHistory = data.conversations;
    } catch (e) {}
}

function renderConvHistory() {
    const list = document.getElementById('convHistoryList');
    if (!list) return;
    const convs = window._customerConvHistory || [];
    list.innerHTML = convs.map(c => `
        <div class="p-3 hover:bg-slate-50 cursor-pointer" onclick="selectConversation(${c.id},'','','')">
            <p class="text-[11px] font-bold text-slate-700">${escapeHtml(c.last_message || 'Mesaj yok')}</p>
            <p class="text-[9px] text-slate-400">${new Date(c.last_message_at).toLocaleDateString('tr-TR')}</p>
        </div>
    `).join('');
}

// ─── Init & Listeners ─────────────────────────────────────────────

document.getElementById('searchInput')?.addEventListener('input', (e) => {
    clearTimeout(searchDebounceTimer);
    searchDebounceTimer = setTimeout(() => {
        currentSearch = e.target.value.trim();
        loadConversations();
    }, 350);
});

document.getElementById('messageInput')?.addEventListener('input', (e) => {
    if (e.target.value === '/') showQuickReplies();
    else if (!e.target.value.startsWith('/')) closeQuickReplies();
});

document.getElementById('messageInput')?.addEventListener('keydown', (e) => {
    if (e.key === 'Enter' && !e.shiftKey) {
        e.preventDefault();
        sendMessage();
    }
    if (e.key === 'Escape') closeQuickReplies();
});

document.querySelectorAll('.filter-tab').forEach(tab => {
    tab.addEventListener('click', () => {
        document.querySelectorAll('.filter-tab').forEach(t => t.classList.remove('active', 'bg-white', 'shadow-sm'));
        tab.classList.add('active', 'bg-white', 'shadow-sm');
        currentFilter = tab.dataset.status || '';
        currentTag = tab.dataset.tag || '';
        loadConversations();
    });
});

async function loadUserInfo() {
    try {
        const r = await fetch(`/api/me`);
        const u = await r.json();
        if (document.getElementById('topbarName')) document.getElementById('topbarName').textContent = u.name;
        if (document.getElementById('topbarAvatar')) document.getElementById('topbarAvatar').textContent = u.name.charAt(0).toUpperCase();
    } catch {}
}

async function loadTeamForDropdown(currentId) {
    try {
        const res = await fetch('/api/team');
        const users = await res.json();
        const sel = document.getElementById('assigneeSelect');
        if (!sel) return;
        sel.innerHTML = '<option value="">Temsilci Ata...</option>';
        users.forEach(u => {
            sel.innerHTML += `<option value="${u.id}" ${u.id === currentId ? 'selected' : ''}>${u.name}</option>`;
        });
    } catch {}
}

window.openConversation = (id) => selectConversation(id, '', '', '');

loadConversations();
loadQuickReplies();
loadUserInfo();
// Auto-refresh her 30 saniyede bir (production için optimize edildi)
setInterval(loadConversations, 30000);

// ─── SSE (Server-Sent Events) Listener ───────────────────────────────────────
let sseSource = null;
let sseEnabled = false; // Production'da SSE devre dışı (Render free tier sorunu)

function initSSE() {
    // SSE devre dışı - production'da sorun yaratıyor
    if (!sseEnabled) {
        console.log('SSE disabled for production stability');
        return;
    }
    
    if (sseSource) return;
    
    try {
        sseSource = new EventSource('/api/notifications/stream');
        
        sseSource.addEventListener('connected', () => {
            console.log('SSE connected');
        });
        
        sseSource.addEventListener('new_message', (e) => {
            try {
                const data = JSON.parse(e.data);
                if (data.conversation_id === window.currentConvId) {
                    selectConversation(data.conversation_id, '', '', '');
                }
                loadConversations();
                showToast('Yeni mesaj geldi: ' + (data.preview || ''), 'info');
            } catch (err) {
                console.error('SSE parse error:', err);
            }
        });
        
        sseSource.onerror = () => {
            console.warn('SSE connection error');
            if (sseSource) {
                sseSource.close();
                sseSource = null;
            }
        };
    } catch (err) {
        console.error('SSE initialization failed:', err);
    }
}

// SSE devre dışı - manuel yenileme kullanılacak
// initSSE();
