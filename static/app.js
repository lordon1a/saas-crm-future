// WhatsApp CRM - Frontend Controller (V4 - Multi-Tenant + Assignment + SSE)
const API_BASE = '/api';

let currentConversationId = null;
window.currentConvId = null;  // SSE toast için global alias

let currentCustomerId = null;
let currentFilter = '';
let currentTag = '';
let currentSearch = '';
let currentChannel = 'all';
let currentInboxItemType = 'whatsapp';
let currentSendChannel = 'whatsapp';
let currentLastMessageId = 0;
let currentWorkspaceId = null;
let socketClient = null;
let currentSocketContactId = null;
let socketConnectErrorCount = 0;
let socketDisabled = false;
let fallbackRefreshInterval = null;
let quickReplies = [];
let emailTemplates = [];
let notifications = [];
let searchDebounceTimer = null;
let isRefreshingActiveMessages = false;
let lastUnreadSignalAt = 0;
let conversationsRefreshTimer = null;
let isUserScrolling = false;
let lastScrollPosition = 0;
const initialUrlParams = new URLSearchParams(window.location.search);
let pendingConversationPublicId = (initialUrlParams.get('conversationId') || '').trim() || null;
let currentConversationPublicId = null;

function setConversationUrl(conversationPublicId, mode = 'push') {
    const url = new URL(window.location.href);
    if (conversationPublicId) {
        url.searchParams.set('conversationId', conversationPublicId);
    } else {
        url.searchParams.delete('conversationId');
    }
    url.searchParams.delete('open_conversation');
    const nextUrl = `${url.pathname}${url.search}`;
    if (mode === 'replace') {
        window.history.replaceState({}, '', nextUrl);
        return;
    }
    window.history.pushState({}, '', nextUrl);
}

function showEmptyConversationState() {
    currentConversationId = null;
    currentConversationPublicId = null;
    currentCustomerId = null;
    currentInboxItemType = 'whatsapp';
    window.currentConvId = null;

    document.querySelectorAll('#conversationList > div[data-id]').forEach(el => {
        el.className = 'contact-card flex items-start gap-3 p-3 rounded-2xl cursor-pointer border border-transparent hover:bg-slate-50 hover:shadow-sm';
    });

    document.getElementById('chatContent')?.classList.add('hidden');
    document.getElementById('emptyChat')?.classList.remove('hidden');
}

async function openConversationByPublicId(conversationPublicId, opts = {}) {
    const { updateHistory = false } = opts;
    if (!conversationPublicId) return;

    try {
        const res = await fetch(`${API_BASE}/conversations/public/${encodeURIComponent(conversationPublicId)}/full`);
        if (res.status === 401) { window.location.href = '/login'; return; }
        if (!res.ok) return;

        const payload = await res.json();
        const conv = payload?.conversation;
        const customer = conv?.customer;
        if (!conv || !customer) return;

        const customerName = customer.profile_name || customer.phone_number || 'Bilinmeyen';
        const customerPhone = customer.phone_number || '';
        const initials = getInitials(customerName);
        const selectedPublicId = conv.public_id || conversationPublicId;

        await selectConversation(
            conv.id,
            customerName,
            customerPhone,
            initials,
            'whatsapp',
            selectedPublicId,
            { updateHistory }
        );
    } catch (error) {
        console.error('Error opening conversation by public id:', error);
    }
}

// ─── Scroll Management ──────────────────────────────────────────

function isUserNearBottom(container, threshold = 150) {
    if (!container) return true;
    const scrollBottom = container.scrollHeight - container.scrollTop - container.clientHeight;
    return scrollBottom <= threshold;
}

function showNewMessageNotification() {
    const btn = document.getElementById('newMessageNotification');
    if (btn) {
        btn.classList.remove('hidden');
    }
}

function hideNewMessageNotification() {
    const btn = document.getElementById('newMessageNotification');
    if (btn) {
        btn.classList.add('hidden');
    }
}

window.scrollToBottomAndHideNotification = function() {
    const container = getMessagesContainer();
    if (container) {
        container.scrollTo({ top: container.scrollHeight, behavior: 'smooth' });
    }
    hideNewMessageNotification();
};

function setupScrollListener() {
    const container = getMessagesContainer();
    if (!container) return;

    let scrollTimeout;
    container.addEventListener('scroll', () => {
        clearTimeout(scrollTimeout);
        isUserScrolling = true;
        
        // Hide notification if user scrolls to bottom
        if (isUserNearBottom(container, 100)) {
            hideNewMessageNotification();
        }

        scrollTimeout = setTimeout(() => {
            isUserScrolling = false;
        }, 150);
    });
}

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
    if (!timestamp) return '--:--';
    const raw = String(timestamp);
    const date = new Date(raw + (raw.endsWith('Z') ? '' : 'Z'));
    if (Number.isNaN(date.getTime())) return '--:--';
    return date.toLocaleTimeString('tr-TR', { hour: '2-digit', minute: '2-digit' });
}

function formatTimeAgo(timestamp) {
    if (!timestamp) return 'Şimdi';
    const raw = String(timestamp);
    const date = new Date(raw + (raw.endsWith('Z') ? '' : 'Z'));
    if (Number.isNaN(date.getTime())) return 'Şimdi';
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
        const params = new URLSearchParams();
        if (currentChannel) params.set('channel', currentChannel);
        params.set('limit', '200');

        const response = await fetch(`/api/v1/email/unified-inbox?${params.toString()}`);
        if (response.status === 401) { window.location.href = '/login'; return; }
        const json = await response.json();
        const data = json.data || {};
        let conversations = data.items || [];
        const counts = data.counts || { total: 0, open: 0, pending: 0, whatsapp: 0, telegram: 0, email: 0 };

        if (currentFilter) {
            conversations = conversations.filter(c => c.item_type !== 'email' && c.status === currentFilter);
        }
        if (currentTag) {
            conversations = conversations.filter(c => c.item_type !== 'email' && (c.tags || '').includes(currentTag));
        }
        if (currentSearch) {
            const q = currentSearch.toLowerCase();
            conversations = conversations.filter(c => {
                const hay = [
                    c.counterparty_name,
                    c.counterparty_email,
                    c.counterparty_phone,
                    c.preview,
                    c.subject,
                ].join(' ').toLowerCase();
                return hay.includes(q);
            });
        }

        document.getElementById('allCount').textContent = counts.total;
        document.getElementById('openCount').textContent = counts.open;
        document.getElementById('pendingCount').textContent = counts.pending;
        const allEl = document.getElementById('channelAllCount');
        const waEl = document.getElementById('channelWhatsappCount');
        const tgEl = document.getElementById('channelTelegramCount');
        const emEl = document.getElementById('channelEmailCount');
        if (allEl) allEl.textContent = counts.total;
        if (waEl) waEl.textContent = counts.whatsapp;
        if (tgEl) tgEl.textContent = counts.telegram || 0;
        if (emEl) emEl.textContent = counts.email;

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
            const resolvedId = conv.item_type === 'email' ? conv.item_id : conv.conversation_id;
            const isActive = resolvedId === currentConversationId;
            const hasUnread = conv.unread_count > 0;

            // Modern SaaS item classes with premium hover
            let baseClasses = "contact-card flex items-start gap-3 p-3 rounded-2xl cursor-pointer border border-transparent";
            if (isActive) {
                baseClasses += " bg-white shadow-sm border-slate-100 ring-1 ring-brand-500/10";
            } else {
                baseClasses += " hover:bg-slate-50 hover:shadow-sm";
            }

            div.className = baseClasses;
            div.dataset.id = resolvedId;
            div.dataset.itemType = conv.item_type;
            if (conv.conversation_public_id) {
                div.dataset.conversationPublicId = conv.conversation_public_id;
            }

            const name = conv.counterparty_name || conv.counterparty_email || conv.counterparty_phone || 'Bilinmeyen';
            const initials = getInitials(name);
            const preview = escapeHtml(conv.preview || conv.subject || 'Mesaj yok');

            // CRM Contact info
            let crmBadge = '';
            if (conv.item_type === 'whatsapp' && conv.customer && conv.customer.crm_contact) {
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
            let channelBadge = '<span class="px-1.5 py-0.5 rounded text-[10px] font-semibold border bg-emerald-50 text-emerald-700 border-emerald-200/50">WA</span>';
            if (conv.item_type === 'email') {
                channelBadge = '<span class="px-1.5 py-0.5 rounded text-[10px] font-semibold border bg-blue-50 text-blue-700 border-blue-200/50">EMAIL</span>';
            } else if (conv.item_type === 'telegram') {
                channelBadge = '<span class="px-1.5 py-0.5 rounded text-[10px] font-semibold border bg-sky-50 text-sky-700 border-sky-200/50"><i class="fab fa-telegram-plane mr-1"></i>TELEGRAM</span>';
            }

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
                            ${channelBadge}
                            ${crmBadge}
                        </div>
                        <span class="text-[11px] text-slate-400 whitespace-nowrap ml-2">${formatTimeAgo(conv.created_at || conv.last_message_at || new Date().toISOString())}</span>
                    </div>
                    <p class="text-[13px] truncate ${previewClass}">${preview}</p>
                    <div class="flex items-center gap-1.5 mt-2">
                        ${renderTagsForList(conv.tags)}
                        ${hasUnread ? `<span class="ml-auto inline-flex items-center justify-center min-w-[20px] h-5 px-1.5 text-[11px] font-bold text-white bg-brand-500 rounded-full shadow-sm">${conv.unread_count}</span>` : ''}
                    </div>
                </div>
            `;

            if (conv.item_type === 'email') {
                div.onclick = () => selectEmailItem(conv, initials);
            } else {
                div.onclick = () => selectConversation(
                    conv.conversation_id,
                    name,
                    conv.counterparty_phone,
                    initials,
                    conv.item_type,
                    conv.conversation_public_id,
                    { updateHistory: true }
                );
            }
            listEl.appendChild(div);
        });

        if (pendingConversationPublicId) {
            const targetConversation = conversations.find((conv) => (
                conv.item_type !== 'email' && conv.conversation_public_id === pendingConversationPublicId
            ));

            if (targetConversation) {
                const targetName = targetConversation.counterparty_name || targetConversation.counterparty_email || targetConversation.counterparty_phone || 'Bilinmeyen';
                const targetInitials = getInitials(targetName);
                const preferredChannel = targetConversation.item_type === 'telegram' ? 'telegram' : 'whatsapp';

                pendingConversationPublicId = null;
                await selectConversation(
                    targetConversation.conversation_id,
                    targetName,
                    targetConversation.counterparty_phone,
                    targetInitials,
                    preferredChannel,
                    targetConversation.conversation_public_id,
                    { updateHistory: false }
                );
            } else {
                await openConversationByPublicId(pendingConversationPublicId, { updateHistory: false });
                pendingConversationPublicId = null;
            }
        }
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

async function selectConversation(
    conversationId,
    customerName,
    customerPhone,
    initials,
    preferredChannel = 'whatsapp',
    conversationPublicId = null,
    opts = {}
) {
    const { updateHistory = true } = opts;
    const previousContactId = currentCustomerId;
    document.querySelectorAll('#conversationList > div[data-id]').forEach(el => {
        el.className = 'contact-card flex items-start gap-3 p-3 rounded-2xl cursor-pointer border border-transparent hover:bg-slate-50 hover:shadow-sm';
    });
    const activeItem = document.querySelector(`[data-id="${conversationId}"]`);
    if (activeItem) {
        activeItem.className = 'contact-card flex items-start gap-3 p-3 rounded-2xl cursor-pointer border border-brand-100 bg-brand-50/50 shadow-sm ring-1 ring-brand-500/20';
    }

    currentConversationId = conversationId;
    currentConversationPublicId = conversationPublicId || null;
    currentInboxItemType = 'whatsapp';
    currentSendChannel = preferredChannel === 'telegram' ? 'telegram' : 'whatsapp';
    window.currentConvId = conversationId;

    if (updateHistory && currentConversationPublicId) {
        setConversationUrl(currentConversationPublicId, 'push');
    }

    document.getElementById('emptyChat').classList.add('hidden');
    document.getElementById('chatContent').classList.remove('hidden');
    const closeBtn = document.getElementById('closeConvBtn');
    if (closeBtn) closeBtn.classList.remove('hidden');
    const tagSelect = document.getElementById('tagSelect');
    if (tagSelect) {
        tagSelect.disabled = false;
        tagSelect.classList.remove('opacity-60', 'cursor-not-allowed');
    }
    const messageInput = document.getElementById('messageInput');
    const sendBtn = document.getElementById('sendBtn');
    if (messageInput) {
        messageInput.disabled = false;
        messageInput.placeholder = 'Mesajınızı yazın... (/ ile hızlı yanıtlar)';
    }
    if (sendBtn) sendBtn.disabled = false;
    const sendChannelSelect = document.getElementById('sendChannelSelect');
    if (sendChannelSelect) {
        sendChannelSelect.disabled = false;
        sendChannelSelect.value = currentSendChannel;
    }
    closeCustomerInfo();
    hideNewMessageNotification();

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
            if (!res.ok) {
                // Fallback: keep chat usable by loading messages-only endpoint.
                const msgRes = await fetch(`${API_BASE}/conversations/${conversationId}/messages`);
                if (msgRes.ok) {
                    const messagesOnly = await msgRes.json();
                    fullData = { messages: messagesOnly, conversation: null };
                } else {
                    fullData = null;
                }
            }
            else {
                fullData = await res.json();
                _convCache.set(conversationId, { data: fullData, ts: Date.now() });
            }
        } catch {
            try {
                const msgRes = await fetch(`${API_BASE}/conversations/${conversationId}/messages`);
                if (msgRes.ok) {
                    const messagesOnly = await msgRes.json();
                    fullData = { messages: messagesOnly, conversation: null };
                } else {
                    fullData = null;
                }
            } catch {
                fullData = null;
            }
        }
    }

    const container = getMessagesContainer();
    if (!container) return;
    container.innerHTML = '';
    const messages = fullData?.messages || [];

    if (messages.length === 0) {
        container.innerHTML = `<div class="flex flex-col items-center justify-center h-full text-center py-16 text-slate-400"><p class="text-sm">Henüz mesaj yok</p></div>`;
        currentLastMessageId = 0;
    } else {
        const html = messages.map((msg) => buildMessageHTML(msg)).join('');
        container.innerHTML = html;
        updateLastMessageCursorFromDOM();
        requestAnimationFrame(() => { smoothScrollMessagesToBottom(true); });
    }

    // Setup scroll listener for this conversation
    setupScrollListener();

    const detail = fullData?.conversation;
    if (detail) {
        const c = detail.customer;
        currentCustomerId = c.id;
        updateSocketContactSubscription(previousContactId, currentCustomerId);
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
    } else {
        updateSocketContactSubscription(previousContactId, null);
    }
}

function selectEmailItem(item, initials) {
    updateSocketContactSubscription(currentCustomerId, null);
    currentCustomerId = null;
    currentConversationId = item.item_id;
    currentConversationPublicId = null;
    currentInboxItemType = 'email';
    currentLastMessageId = 0;
    window.currentConvId = null;
    setConversationUrl(null, 'push');

    document.querySelectorAll('#conversationList > div[data-id]').forEach(el => {
        el.className = 'contact-card flex items-start gap-3 p-3 rounded-2xl cursor-pointer border border-transparent hover:bg-slate-50 hover:shadow-sm';
    });
    const activeItem = document.querySelector(`[data-id="${item.item_id}"]`);
    if (activeItem) {
        activeItem.className = 'contact-card flex items-start gap-3 p-3 rounded-2xl cursor-pointer border border-brand-100 bg-brand-50/50 shadow-sm ring-1 ring-brand-500/20';
    }

    document.getElementById('emptyChat').classList.add('hidden');
    document.getElementById('chatContent').classList.remove('hidden');
    closeCustomerInfo();

    document.getElementById('customerName').textContent = item.counterparty_name || item.counterparty_email || 'Email';
    document.getElementById('customerPhone').textContent = item.counterparty_email || 'Email';
    if (initials) {
        document.getElementById('customerInitials').textContent = initials;
        document.getElementById('infoInitials').textContent = initials;
    }

    const closeBtn = document.getElementById('closeConvBtn');
    if (closeBtn) closeBtn.classList.add('hidden');
    const tagSelect = document.getElementById('tagSelect');
    if (tagSelect) {
        tagSelect.disabled = true;
        tagSelect.classList.add('opacity-60', 'cursor-not-allowed');
        tagSelect.value = '';
    }

    const messageInput = document.getElementById('messageInput');
    const sendBtn = document.getElementById('sendBtn');
    if (messageInput) {
        messageInput.disabled = true;
        messageInput.value = '';
        messageInput.placeholder = 'Email kayıtları salt okunurdur';
    }
    if (sendBtn) sendBtn.disabled = true;
    const sendChannelSelect = document.getElementById('sendChannelSelect');
    if (sendChannelSelect) {
        sendChannelSelect.disabled = true;
        sendChannelSelect.value = 'email';
    }

    const body = item.preview || item.subject || '';
    const container = document.getElementById('messagesContainer');
    container.innerHTML = `
        <div class="flex mb-4 justify-start">
            <div class="max-w-[75%] px-5 py-3.5 bg-white text-slate-800 rounded-2xl rounded-tl-md border border-slate-200/80 shadow-sm hover:shadow-md transition-all">
                <div class="text-[10px] font-bold text-blue-600 uppercase tracking-wider mb-1 flex items-center gap-1.5"><i class="fas fa-envelope text-[9px]"></i>Email ${escapeHtml((item.direction || 'received').toUpperCase())}</div>
                <div class="text-[13px] font-semibold text-slate-700 mb-1">${escapeHtml(item.subject || '(Konu yok)')}</div>
                <div class="text-[14px] leading-relaxed break-words">${escapeHtml(body)}</div>
                <div class="text-[10px] text-slate-500 text-right mt-1.5 font-medium">${formatTime(item.created_at || new Date().toISOString())}</div>
            </div>
        </div>
    `;
}

function getMessagesContainer() {
    const container = document.getElementById('messagesContainer')
        || document.getElementById('chat-messages')
        || document.querySelector('.messages-container');
    
    if (!container) {
        console.error('❌ CRITICAL: Messages container not found in DOM!');
        console.log('Available elements:', {
            byId: document.getElementById('messagesContainer'),
            byChatId: document.getElementById('chat-messages'),
            byClass: document.querySelector('.messages-container')
        });
    } else {
        console.log('✅ Messages container found:', container.id || container.className);
    }
    
    return container;
}

function buildMessageHTML(msg) {
    const isAgent = msg.sender_type !== 'customer';
    const rowClasses = `flex mb-4 animate-slide-up-fade ${isAgent ? 'justify-end' : 'justify-start'}`;
    const rowMessageId = escapeHtml(msg.id || '');

    // Premium bubble classes with gradient and shadows
    let bubbleClasses = 'max-w-[70%] px-5 py-3.5 relative group transition-all ';
    if (isAgent) {
        bubbleClasses += 'message-bubble-agent';
    } else {
        bubbleClasses += 'message-bubble-customer';
    }

    let mediaHtml = '';
    if (msg.media_url) {
        if (msg.media_type === 'image') {
            mediaHtml = `<div class="mb-2 rounded-xl overflow-hidden max-w-full border ${isAgent ? 'border-white/20' : 'border-slate-200'}"><img src="${escapeHtml(msg.media_url)}" alt="Görsel" class="max-h-64 w-auto object-cover" loading="lazy" onerror="this.style.display='none'"></div>`;
        } else if (msg.media_type === 'document' || msg.media_type === 'audio' || msg.media_type === 'video') {
            const label = msg.media_type === 'document' ? '📄 Belge' : msg.media_type === 'audio' ? '🎵 Ses' : '🎥 Video';
            mediaHtml = `<a href="${escapeHtml(msg.media_url)}" target="_blank" rel="noopener" class="inline-flex items-center gap-2 text-sm underline font-medium mb-2 hover:opacity-80 transition-opacity ${isAgent ? 'text-white/90' : 'text-brand-600'}">${label} – İndir</a>`;
        }
    }

    return `
        <div class="${rowClasses}" data-message-id="${rowMessageId}" style="margin-bottom: 1rem;">
        <div class="${bubbleClasses}">
            ${msg.sender_name && isAgent ? `<div class="text-[10px] font-bold text-white/70 uppercase tracking-wider mb-1">${escapeHtml(msg.sender_name)}</div>` : ''}
            ${msg.channel === 'telegram' ? `<div class="text-[10px] font-bold uppercase tracking-wider mb-1 ${isAgent ? 'text-white/80' : 'text-sky-600'}"><i class="fab fa-telegram-plane mr-1"></i>Telegram</div>` : ''}
            ${mediaHtml}
            <div class="text-[14.5px] leading-relaxed break-words">${escapeHtml(msg.message_body)}</div>
            <div class="text-[10px] text-opacity-60 text-right mt-1.5 ${isAgent ? 'text-white' : 'text-slate-500'} font-medium">${formatTime(msg.created_at)}</div>
        </div>
        </div>
    `;
}

function appendMessageToDOM(msg, tempId) {
    const container = getMessagesContainer();
    if (!container) {
        console.error('❌ Container not found!');
        return null;
    }

    const messageId = msg?.id;
    if (messageId !== undefined && messageId !== null && String(messageId).trim() !== '') {
        const existing = container.querySelector(`[data-message-id="${String(messageId)}"]`);
        if (existing) {
            console.log('⚠️ Message already exists:', messageId);
            return existing;
        }
    }

    // Check if user is near bottom before adding message
    const wasNearBottom = isUserNearBottom(container, 150);
    console.log('📊 Before append - wasNearBottom:', wasNearBottom, 'scrollTop:', container.scrollTop, 'scrollHeight:', container.scrollHeight);

    container.insertAdjacentHTML('beforeend', buildMessageHTML(msg));
    const insertedItems = container.querySelectorAll('[data-message-id]');
    const el = insertedItems.length > 0 ? insertedItems[insertedItems.length - 1] : null;
    if (tempId && el) el.dataset.tempId = tempId;

    const numericMessageId = Number(messageId);
    if (!Number.isNaN(numericMessageId) && numericMessageId > currentLastMessageId) {
        currentLastMessageId = numericMessageId;
    }

    // Memory Management: Limit messages in DOM to prevent memory issues (keep last 100 messages)
    const allMessages = container.querySelectorAll('[data-message-id]');
    if (allMessages.length > 100) {
        const toRemove = allMessages.length - 100;
        for (let i = 0; i < toRemove; i++) {
            allMessages[i].remove();
        }
        console.log(`🗑️ Removed ${toRemove} old messages from DOM (memory optimization)`);
    }

    console.log('📊 After append - scrollTop:', container.scrollTop, 'scrollHeight:', container.scrollHeight);

    // Smart Auto-Scroll: Only scroll if user was near bottom or if it's our own message
    const isOwnMessage = msg.sender_type === 'agent';
    if (wasNearBottom || isOwnMessage) {
        console.log('✅ Auto-scrolling (wasNearBottom:', wasNearBottom, 'isOwnMessage:', isOwnMessage, ')');
        
        // IMMEDIATE SCROLL - No delays
        container.scrollTop = container.scrollHeight;
        
        // Double-check with multiple attempts
        setTimeout(() => {
            container.scrollTop = container.scrollHeight;
        }, 0);
        
        setTimeout(() => {
            container.scrollTop = container.scrollHeight;
        }, 50);
        
        setTimeout(() => {
            container.scrollTop = container.scrollHeight;
            console.log('📍 Final position after append:', container.scrollTop, '/', container.scrollHeight);
        }, 100);
        
        hideNewMessageNotification();
    } else {
        // User is reading old messages - show notification instead of forcing scroll
        console.log('📢 Showing notification (user not at bottom)');
        showNewMessageNotification();
    }

    return el;
}

function smoothScrollMessagesToBottom(force = false) {
    const container = getMessagesContainer();
    if (!container) {
        console.error('❌ Container not found for scroll');
        return;
    }
    
    console.log('📜 Scrolling to bottom, force:', force, 'scrollHeight:', container.scrollHeight);
    
    // If user is scrolling and not forced, don't interrupt
    if (isUserScrolling && !force) {
        showNewMessageNotification();
        return;
    }
    
    // AGGRESSIVE SCROLL: Multiple attempts to ensure scroll happens
    // Attempt 1: Immediate scroll
    container.scrollTop = container.scrollHeight;
    
    // Attempt 2: After a tiny delay
    setTimeout(() => {
        container.scrollTop = container.scrollHeight;
    }, 10);
    
    // Attempt 3: Smooth scroll with requestAnimationFrame
    requestAnimationFrame(() => {
        container.scrollTop = container.scrollHeight;
        try {
            container.scrollTo({ 
                top: container.scrollHeight, 
                behavior: 'smooth' 
            });
        } catch (e) {
            console.warn('Smooth scroll failed, using direct:', e);
            container.scrollTop = container.scrollHeight;
        }
    });
    
    // Attempt 4: Final check after animation
    setTimeout(() => {
        container.scrollTop = container.scrollHeight;
        console.log('✅ Final scroll position:', container.scrollTop, '/', container.scrollHeight);
    }, 100);
    
    hideNewMessageNotification();
}

function removeTempMessage(tempId) {
    if (!tempId) return;
    const container = getMessagesContainer();
    const el = container && container.querySelector(`[data-temp-id="${tempId}"]`);
    if (el) el.remove();
}

function updateLastMessageCursorFromDOM() {
    const container = getMessagesContainer();
    if (!container) {
        currentLastMessageId = 0;
        return;
    }

    const messageNodes = container.querySelectorAll('[data-message-id]');
    let maxId = 0;
    messageNodes.forEach((node) => {
        const id = Number(node.dataset.messageId);
        if (!Number.isNaN(id) && id > maxId) maxId = id;
    });
    currentLastMessageId = maxId;
}

function updateSocketContactSubscription(previousContactId, nextContactId) {
    if (!socketClient || !socketClient.connected) {
        currentSocketContactId = nextContactId || null;
        return;
    }

    if (previousContactId && String(previousContactId) !== String(nextContactId || '')) {
        socketClient.emit('leave_contact_room', { contact_id: previousContactId });
    }

    if (nextContactId && String(previousContactId || '') !== String(nextContactId)) {
        socketClient.emit('join_contact_room', { contact_id: nextContactId });
    }

    currentSocketContactId = nextContactId || null;
}

function normalizeRealtimeMessage(payload) {
    return {
        id: payload.id || payload.message_id,
        sender_type: payload.sender_type || (payload.message_side === 'outbound' ? 'agent' : 'customer'),
        sender_name: payload.sender_name || null,
        message_body: payload.message_body || payload.text || payload.message || payload.body || '',
        channel: payload.channel || currentSendChannel || 'whatsapp',
        created_at: payload.created_at || payload.timestamp || new Date().toISOString(),
        media_type: payload.media_type || null,
        media_url: payload.media_url || null,
    };
}

function renderMessage(payload) {
    console.log('🎨 renderMessage called with:', payload);
    const normalized = normalizeRealtimeMessage(payload);
    console.log('🔄 Normalized message:', normalized);
    const result = appendMessageToDOM(normalized);
    console.log('📌 appendMessageToDOM result:', result);
}

function scheduleConversationsRefresh(delayMs = 1000) {
    if (conversationsRefreshTimer) clearTimeout(conversationsRefreshTimer);
    conversationsRefreshTimer = setTimeout(() => {
        conversationsRefreshTimer = null;
        loadConversations();
    }, delayMs);
}

function triggerUnreadSignal() {
    const now = Date.now();
    if ((now - lastUnreadSignalAt) < 800) return;
    lastUnreadSignalAt = now;

    try {
        const audioCtx = new (window.AudioContext || window.webkitAudioContext)();
        const oscillator = audioCtx.createOscillator();
        const gainNode = audioCtx.createGain();

        oscillator.type = 'sine';
        oscillator.frequency.value = 880;
        gainNode.gain.value = 0.03;

        oscillator.connect(gainNode);
        gainNode.connect(audioCtx.destination);

        oscillator.start();
        oscillator.stop(audioCtx.currentTime + 0.08);
    } catch {
        // Ignore autoplay policy restrictions.
    }
}

function handleIncomingSocketMessage(payload) {
    console.log('🔔 WebSocket event received:', payload);

    if (!payload || currentInboxItemType === 'email') {
        console.log('⚠️ Skipping: No payload or email type');
        scheduleConversationsRefresh(800);
        return;
    }

    // Type-safe ID comparison: convert both to Number for accurate matching
    const payloadConversationId = Number(payload.conversation_id);
    const activeConversationId = Number(currentConversationId);
    const payloadContactId = Number(payload.contact_id || payload.customer_id || 0);
    const activeContactId = Number(currentCustomerId || 0);

    console.log('🔍 ID Comparison:', {
        payloadConversationId,
        activeConversationId,
        payloadContactId,
        activeContactId,
        match: (payloadConversationId && payloadConversationId === activeConversationId) ||
               (payloadContactId && payloadContactId === activeContactId)
    });

    // Check if message belongs to currently active conversation
    const isActiveConversation = (
        (payloadConversationId && payloadConversationId === activeConversationId) ||
        (payloadContactId && payloadContactId === activeContactId)
    );

    if (!isActiveConversation) {
        // Message is for a different conversation - just update sidebar
        console.log('📋 Message for different conversation - updating sidebar only');
        triggerUnreadSignal();
        scheduleConversationsRefresh(800);
        return;
    }

    console.log('✅ Message for ACTIVE conversation - injecting into chat window');

    // Message belongs to active conversation - inject it into chat window
    const container = getMessagesContainer();
    if (!container) {
        console.error('❌ ERROR: Messages container not found!');
        scheduleConversationsRefresh(800);
        return;
    }

    console.log('📦 Container found:', container.id || container.className);

    // Remove empty state if present
    const emptyState = container.querySelector('.text-slate-400');
    if (emptyState) {
        console.log('🗑️ Removing empty state');
        container.innerHTML = '';
    }

    // Inject message into active chat window
    console.log('💬 Rendering message...');
    renderMessage(payload);
    smoothScrollMessagesToBottom();
    scheduleConversationsRefresh(1200);
    console.log('✅ Message rendered successfully');
}

function initRealtimeSocket() {
    if (socketClient || socketDisabled || typeof io === 'undefined') return;

    socketClient = io({
        transports: ['polling'],
        upgrade: false,
        reconnection: true,
        reconnectionAttempts: 10,
        reconnectionDelay: 1000,
        timeout: 20000,
        withCredentials: true
    });

    socketClient.on('connect', () => {
        socketConnectErrorCount = 0;
        console.log('✅ WebSocket Connected Successfully!');
        if (currentWorkspaceId) {
            socketClient.emit('join_workspace', { workspace_id: currentWorkspaceId });
        }
        if (currentSocketContactId) {
            socketClient.emit('join_contact_room', { contact_id: currentSocketContactId });
        }
    });

    socketClient.on('connect_error', (error) => {
        socketConnectErrorCount += 1;
        console.error('❌ Connection Error:', error);

        // If realtime endpoint is unstable (502/xhr post error), stop retry storm.
        if (socketConnectErrorCount >= 3) {
            socketDisabled = true;
            try {
                socketClient.io.opts.reconnection = false;
                socketClient.disconnect();
            } catch (_) {
                // no-op
            }
            socketClient = null;
            console.warn('Realtime disabled after repeated connection failures. Falling back to API polling.');
            startFallbackPolling();
        }
    });

    socketClient.off('new_message');
    socketClient.off('new_incoming_message');
    socketClient.off('inbox_updated');

    socketClient.on('new_message', (data) => {
        console.log('WebSocket event received:', data);
        handleIncomingSocketMessage(data);
    });
    socketClient.on('new_incoming_message', (data) => {
        console.log('WebSocket event received:', data);
        handleIncomingSocketMessage(data);
    });
    socketClient.on('inbox_updated', (data) => {
        console.log('WebSocket event received:', data);
        handleInboxUpdatedEvent(data);
    });
    socketClient.on('disconnect', (reason) => {
        console.warn('WebSocket disconnected', reason || 'unknown');

        // Transport/server disconnects can cause noisy reconnect loops in some environments.
        if (reason && reason !== 'io client disconnect') {
            socketDisabled = true;
            try {
                socketClient.io.opts.reconnection = false;
            } catch (_) {
                // no-op
            }
            socketClient = null;
            startFallbackPolling();
        }
    });
}

function startFallbackPolling() {
    if (fallbackRefreshInterval) return;

    fallbackRefreshInterval = setInterval(() => {
        loadConversations();
        refreshActiveConversationMessages();
    }, 8000);
}

async function refreshActiveConversationMessages() {
    if (isRefreshingActiveMessages || !currentConversationId || currentInboxItemType === 'email') return;

    isRefreshingActiveMessages = true;
    try {
        const afterId = Number(currentLastMessageId || 0);
        const res = await fetch(`${API_BASE}/conversations/${currentConversationId}/messages?after_id=${afterId}`);
        if (!res.ok) return;

        const newMessages = await res.json();
        if (!Array.isArray(newMessages) || newMessages.length === 0) return;

        const container = getMessagesContainer();
        if (!container) return;

        const emptyState = container.querySelector('.text-slate-400');
        if (emptyState) container.innerHTML = '';

        newMessages.forEach((msg) => appendMessageToDOM(msg));
        updateLastMessageCursorFromDOM();
    } catch (err) {
        console.error('Active conversation refresh error:', err);
    } finally {
        isRefreshingActiveMessages = false;
    }
}

function handleInboxUpdatedEvent(payload) {
    console.log('WebSocket inbox_updated event received:', payload);
    scheduleConversationsRefresh(1000);

    if (!payload || currentInboxItemType === 'email') return;

    // Type-safe ID comparison: convert both to Number
    const incomingConversationId = Number(payload.conversation_id || 0);
    const activeConversationId = Number(currentConversationId || 0);
    const incomingContactId = Number(payload.contact_id || payload.customer_id || 0);
    const activeContactId = Number(currentCustomerId || 0);

    // Check if update is for currently active conversation
    const isActiveConversation = (
        (incomingConversationId && incomingConversationId === activeConversationId) ||
        (incomingContactId && incomingContactId === activeContactId)
    );

    if (isActiveConversation) {
        // If message data is included, inject it into chat window
        if (payload.message_body || payload.text || payload.message) {
            const container = getMessagesContainer();
            if (container) {
                const emptyState = container.querySelector('.text-slate-400');
                if (emptyState) container.innerHTML = '';
                
                renderMessage(payload);
            }
        }
        
        // Smart scroll: only if user is near bottom
        const container = getMessagesContainer();
        if (container && isUserNearBottom(container, 150)) {
            smoothScrollMessagesToBottom(true);
        }
    } else {
        triggerUnreadSignal();
    }
}

async function sendMessage() {
    const input = document.getElementById('messageInput');
    const sendBtn = document.getElementById('sendBtn');
    const sendChannelSelect = document.getElementById('sendChannelSelect');
    const messageBody = input.value.trim();
    const selectedChannel = (sendChannelSelect?.value || currentSendChannel || 'whatsapp').toLowerCase();

    if (!messageBody || !currentConversationId || currentInboxItemType !== 'whatsapp') return;

    input.disabled = true;
    sendBtn.disabled = true;

    const tempId = 'temp-' + Date.now();
    const tempMsg = {
        id: tempId,
        sender_type: 'agent',
        message_body: messageBody,
        channel: selectedChannel,
        created_at: new Date().toISOString()
    };
    appendMessageToDOM(tempMsg, tempId);
    input.value = '';

    try {
        const response = await fetch(`${API_BASE}/messages/send`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                conversation_id: currentConversationId,
                message_body: messageBody,
                channel: selectedChannel,
            })
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
    if (!currentConversationId || currentInboxItemType !== 'whatsapp') return;
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

async function loadNotifications() {
    try {
        const res = await fetch('/api/collaboration/notifications?limit=20');
        if (!res.ok) return;
        const json = await res.json();
        notifications = json.items || [];
        renderNotifications();
        updateNotificationBadge(json.unread_count || 0);
    } catch (e) {
        console.error('Notification load failed', e);
    }
}

function updateNotificationBadge(unreadCount) {
    const badge = document.getElementById('notificationBellCount');
    if (!badge) return;
    if (!unreadCount) {
        badge.classList.add('hidden');
        return;
    }
    badge.classList.remove('hidden');
    badge.textContent = String(unreadCount > 99 ? '99+' : unreadCount);
}

function renderNotifications() {
    const list = document.getElementById('notificationList');
    if (!list) return;

    if (!notifications.length) {
        list.innerHTML = '<div class="p-4 text-xs text-slate-500">Henüz bildiriminiz yok.</div>';
        return;
    }

    list.innerHTML = notifications.map(n => `
        <button class="w-full text-left p-3 hover:bg-slate-50 transition-all ${n.is_read ? '' : 'bg-brand-50/30'}" data-notification-id="${n.id}">
            <div class="flex items-start gap-2">
                <div class="w-2 h-2 rounded-full mt-1.5 ${n.is_read ? 'bg-slate-300' : 'bg-brand-500'}"></div>
                <div class="min-w-0">
                    <p class="text-xs font-semibold text-slate-700 break-words">${escapeHtml(n.message || '')}</p>
                    <p class="text-[10px] text-slate-400 mt-1">${formatTimeAgo(n.created_at || new Date().toISOString())}</p>
                </div>
            </div>
        </button>
    `).join('');

    list.querySelectorAll('[data-notification-id]').forEach(btn => {
        btn.addEventListener('click', async () => {
            const id = btn.getAttribute('data-notification-id');
            try {
                await fetch(`/api/collaboration/notifications/${id}/read`, { method: 'POST' });
                loadNotifications();
            } catch (_) {
                // no-op
            }
        });
    });
}

function toggleNotificationDropdown() {
    const dropdown = document.getElementById('notificationDropdown');
    if (!dropdown) return;
    const isHidden = dropdown.classList.contains('hidden');
    if (isHidden) {
        dropdown.classList.remove('hidden');
        loadNotifications();
        return;
    }
    dropdown.classList.add('hidden');
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

document.querySelectorAll('.channel-tab').forEach(tab => {
    tab.addEventListener('click', () => {
        document.querySelectorAll('.channel-tab').forEach(t => t.classList.remove('active', 'bg-white', 'shadow-sm', 'text-brand-600'));
        tab.classList.add('active', 'bg-white', 'shadow-sm', 'text-brand-600');
        currentChannel = tab.dataset.channel || 'all';
        loadConversations();
    });
});

document.getElementById('sendChannelSelect')?.addEventListener('change', (e) => {
    currentSendChannel = (e.target.value || 'whatsapp').toLowerCase();
});

async function loadEmailTemplates() {
    try {
        const res = await fetch('/api/v1/email/templates');
        const json = await res.json();
        emailTemplates = (json.data || []);
        const select = document.getElementById('emailTemplateSelect');
        if (!select) return;
        select.innerHTML = '<option value="">Template seç (opsiyonel)</option>';
        emailTemplates.forEach(t => {
            select.innerHTML += `<option value="${t.id}">${escapeHtml(t.name)}</option>`;
        });
    } catch (e) {
        console.error('Template load failed', e);
    }
}

function openEmailComposer() {
    const modal = document.getElementById('emailComposerModal');
    if (!modal) return;
    modal.classList.remove('hidden');
    modal.classList.add('flex');
    loadEmailTemplates();
}

function closeEmailComposer() {
    const modal = document.getElementById('emailComposerModal');
    if (!modal) return;
    modal.classList.add('hidden');
    modal.classList.remove('flex');
}

async function previewSelectedTemplate() {
    const templateId = Number(document.getElementById('emailTemplateSelect')?.value || 0);
    if (!templateId) return;

    const variables = {
        customer_name: document.getElementById('customerName')?.textContent || '',
        customer_email: document.getElementById('customerPhone')?.textContent || '',
        today_date: new Date().toISOString().slice(0, 10),
    };

    try {
        const res = await fetch(`/api/v1/email/templates/${templateId}/render`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ variables }),
        });
        const json = await res.json();
        if (!res.ok) {
            showToast(json.error || 'Template önizlenemedi', 'error');
            return;
        }
        document.getElementById('emailSubjectInput').value = json.data.subject || '';
        document.getElementById('emailBodyInput').value = json.data.body || '';
    } catch (e) {
        showToast('Template önizlenemedi', 'error');
    }
}

async function sendComposedEmail() {
    const toEmail = (document.getElementById('emailToInput')?.value || '').trim();
    const subject = (document.getElementById('emailSubjectInput')?.value || '').trim();
    const body = (document.getElementById('emailBodyInput')?.value || '').trim();
    if (!toEmail || !subject || !body) {
        showToast('Alıcı, konu ve içerik zorunlu', 'error');
        return;
    }

    try {
        const res = await fetch('/api/v1/email/send', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                to_email: toEmail,
                subject,
                body_text: body,
                body_html: `<p>${escapeHtml(body).split('\n').join('<br>')}</p>`,
            }),
        });
        const json = await res.json();
        if (!res.ok) {
            showToast(json.error || 'Email gönderilemedi', 'error');
            return;
        }
        showToast('Email gönderildi');
        closeEmailComposer();
        loadConversations();
    } catch (e) {
        showToast('Email gönderilemedi', 'error');
    }
}

document.getElementById('openEmailComposerBtn')?.addEventListener('click', openEmailComposer);
document.getElementById('closeEmailComposerBtn')?.addEventListener('click', closeEmailComposer);
document.getElementById('previewEmailTemplateBtn')?.addEventListener('click', previewSelectedTemplate);
document.getElementById('sendEmailBtn')?.addEventListener('click', sendComposedEmail);
document.getElementById('notificationBellBtn')?.addEventListener('click', (e) => {
    e.stopPropagation();
    toggleNotificationDropdown();
});
document.getElementById('markAllNotificationsReadBtn')?.addEventListener('click', async () => {
    try {
        await fetch('/api/collaboration/notifications/read-all', { method: 'POST' });
        loadNotifications();
    } catch (_) {
        // no-op
    }
});

async function loadUserInfo() {
    try {
        const r = await fetch(`/api/me`);
        const u = await r.json();
        currentWorkspaceId = u.workspace_id || null;
        if (document.getElementById('topbarName')) document.getElementById('topbarName').textContent = u.name;
        if (document.getElementById('topbarAvatar')) document.getElementById('topbarAvatar').textContent = u.name.charAt(0).toUpperCase();
        initRealtimeSocket();
        if (socketClient && socketClient.connected && currentWorkspaceId) {
            socketClient.emit('join_workspace', { workspace_id: currentWorkspaceId });
        }
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

window.addEventListener('popstate', () => {
    const urlParams = new URLSearchParams(window.location.search);
    const targetPublicId = (urlParams.get('conversationId') || '').trim();
    if (!targetPublicId) {
        showEmptyConversationState();
        return;
    }
    if (targetPublicId === (currentConversationPublicId || '')) {
        return;
    }
    openConversationByPublicId(targetPublicId, { updateHistory: false });
});

// DEBUG: Test function for manual WebSocket message injection
window.testMessageInjection = function(testMessage) {
    console.log('🧪 TEST: Manual message injection');
    const payload = testMessage || {
        id: 999999,
        message_id: 999999,
        conversation_id: currentConversationId,
        contact_id: currentCustomerId,
        customer_id: currentCustomerId,
        text: 'TEST MESSAGE - Bu bir test mesajıdır',
        message_body: 'TEST MESSAGE - Bu bir test mesajıdır',
        timestamp: new Date().toISOString(),
        created_at: new Date().toISOString(),
        channel: 'whatsapp',
        sender_type: 'customer',
        message_side: 'inbound',
        sender_name: 'Test User',
    };
    
    console.log('Current state:', {
        currentConversationId,
        currentCustomerId,
        currentInboxItemType,
        payload
    });
    
    handleIncomingSocketMessage(payload);
};

loadConversations();
loadQuickReplies();
loadUserInfo();
loadNotifications();

// ─── CRITICAL: Cleanup on Page Unload (Worker Starvation Fix) ───────────────
function cleanupConnections() {
    console.log('Cleaning up socket and refresh timers...');
    
    // Disconnect only when there is an established socket.
    // Disconnecting during initial handshake can trigger noisy console errors.
    if (socketClient && socketClient.connected) {
        socketClient.disconnect();
        console.log('Socket connection closed');
    }
    socketClient = null;
    
    if (conversationsRefreshTimer) {
        clearTimeout(conversationsRefreshTimer);
        conversationsRefreshTimer = null;
        console.log('Conversations refresh timer cleared');
    }
}

// Cleanup when user navigates away (prevents worker starvation)
window.addEventListener('beforeunload', cleanupConnections);

// Cleanup when user clicks on navigation links
document.addEventListener('click', function(e) {
    const dropdown = document.getElementById('notificationDropdown');
    const bell = document.getElementById('notificationBellBtn');
    if (dropdown && bell && !dropdown.contains(e.target) && !bell.contains(e.target)) {
        dropdown.classList.add('hidden');
    }
    // Intentionally avoid forcing socket cleanup on click.
    // Actual navigation is already handled by beforeunload/pagehide.
});
