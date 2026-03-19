const PORTAL_TOKEN_KEY = 'portal_token';
let activeConversationId = null;
let currentPortalDealId = null;
let messagePollingTimer = null;
let portalBranding = null;

const portalState = {
    tasks: [],
    milestones: [],
    documents: [],
    conversations: [],
    activeDeal: null,
    messagesByConversation: {},
};

function portalToken() {
    return localStorage.getItem(PORTAL_TOKEN_KEY) || '';
}

function setPortalToken(token) {
    localStorage.setItem(PORTAL_TOKEN_KEY, token);
}

function clearPortalToken() {
    localStorage.removeItem(PORTAL_TOKEN_KEY);
}

function embeddedBranding() {
    const script = document.getElementById('portalBrandingData');
    if (!script) return null;

    try {
        return JSON.parse(script.textContent || '{}');
    } catch (_) {
        return null;
    }
}

function applyPortalBranding(branding) {
    if (!branding || typeof branding !== 'object') return;
    portalBranding = branding;

    const root = document.documentElement;
    if (branding.primary_color) {
        root.style.setProperty('--portal-primary', branding.primary_color);
    }
    if (branding.secondary_color) {
        root.style.setProperty('--portal-secondary', branding.secondary_color);
    }

    const sidebarLogo = document.getElementById('portalSidebarLogo');
    if (sidebarLogo && branding.logo_url) {
        if (sidebarLogo.tagName.toLowerCase() === 'img') {
            sidebarLogo.src = branding.logo_url;
        } else {
            const replacement = document.createElement('img');
            replacement.id = 'portalSidebarLogo';
            replacement.src = branding.logo_url;
            replacement.alt = 'Portal Logo';
            replacement.className = 'h-9 w-9 rounded-xl object-contain border border-slate-200';
            sidebarLogo.replaceWith(replacement);
        }
    }

    let customStyle = document.getElementById('portalBrandingCustomCss');
    if (!customStyle) {
        customStyle = document.createElement('style');
        customStyle.id = 'portalBrandingCustomCss';
        document.head.appendChild(customStyle);
    }
    customStyle.textContent = String(branding.custom_css || '');
}

async function loadPortalBrandingConfig() {
    const result = await requestJson('/portal/api/branding');
    if (!result.ok) return;
    applyPortalBranding(result.data);
}

function ensureToastRoot() {
    let root = document.getElementById('portalToastRoot');
    if (root) return root;

    root = document.createElement('div');
    root.id = 'portalToastRoot';
    root.className = 'fixed top-4 right-4 z-[9999] space-y-2 pointer-events-none';
    document.body.appendChild(root);
    return root;
}

function showToast(message, type = 'info') {
    const root = ensureToastRoot();
    const toast = document.createElement('div');

    const variantClass = type === 'success'
        ? 'bg-emerald-600 text-white'
        : type === 'error'
            ? 'bg-rose-600 text-white'
            : 'bg-slate-900 text-white';

    toast.className = `pointer-events-auto min-w-[260px] max-w-[360px] px-4 py-3 rounded-xl shadow-md text-sm ${variantClass}`;
    toast.textContent = message;
    root.appendChild(toast);

    window.setTimeout(() => {
        toast.remove();
    }, 3200);
}

async function portalFetch(url, options = {}) {
    const headers = options.headers || {};
    headers.Authorization = `Bearer ${portalToken()}`;
    if (!headers['Content-Type'] && !(options.body instanceof FormData)) {
        headers['Content-Type'] = 'application/json';
    }

    try {
        const response = await fetch(url, {
            ...options,
            headers,
        });

        if (response.status === 401) {
            clearPortalToken();
            window.location.href = '/portal/login';
            return null;
        }

        return response;
    } catch (_) {
        showToast('Ağ hatası oluştu. Lütfen tekrar deneyin.', 'error');
        return null;
    }
}

async function requestJson(url, options = {}, messages = {}) {
    const response = await portalFetch(url, options);
    if (!response) return { ok: false, data: null, status: 0 };

    let data = {};
    try {
        data = await response.json();
    } catch (_) {
        data = {};
    }

    if (!response.ok) {
        showToast(data.error || messages.error || 'İşlem başarısız oldu.', 'error');
        return { ok: false, data, status: response.status };
    }

    if (messages.success) {
        showToast(messages.success, 'success');
    }
    return { ok: true, data, status: response.status };
}

function fmtDate(value) {
    if (!value) return '—';
    return new Date(value).toLocaleString('tr-TR', {
        day: '2-digit',
        month: 'short',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit',
    });
}

function formatCurrency(value) {
    const numeric = Number(value || 0);
    return new Intl.NumberFormat('tr-TR', {
        style: 'currency',
        currency: 'TRY',
        maximumFractionDigits: 0,
    }).format(numeric);
}

function htmlEscape(value) {
    return String(value || '')
        .replaceAll('&', '&amp;')
        .replaceAll('<', '&lt;')
        .replaceAll('>', '&gt;')
        .replaceAll('"', '&quot;')
        .replaceAll("'", '&#39;');
}

function taskPriorityBadge(priority) {
    const value = String(priority || 'medium').toLowerCase();
    if (value === 'high' || value === 'urgent') {
        return '<span class="text-[11px] px-2 py-1 rounded-full bg-rose-100 text-rose-700 font-semibold">High</span>';
    }
    if (value === 'low') {
        return '<span class="text-[11px] px-2 py-1 rounded-full bg-emerald-100 text-emerald-700 font-semibold">Low</span>';
    }
    return '<span class="text-[11px] px-2 py-1 rounded-full bg-amber-100 text-amber-700 font-semibold">Medium</span>';
}

function taskStatusBadge(status) {
    const value = String(status || '').toLowerCase();
    if (value === 'completed') {
        return '<span class="text-[11px] px-2 py-1 rounded-full bg-emerald-100 text-emerald-700 font-semibold">Completed</span>';
    }
    if (value === 'in_progress' || value === 'in progress') {
        return '<span class="text-[11px] px-2 py-1 rounded-full bg-violet-100 text-violet-700 font-semibold">In Progress</span>';
    }
    return '<span class="text-[11px] px-2 py-1 rounded-full bg-slate-200 text-slate-700 font-semibold">Not Started</span>';
}

function buildDealSteps(deal) {
    const stageNames = ['Lead', 'Qualified', 'Proposal', 'Negotiation', 'Closed Won'];
    const totalStages = Number(deal?.stage?.total_stages || stageNames.length);
    const currentOrder = Number(deal?.stage?.order || 0);

    const names = stageNames.slice(0, totalStages);
    if (names.length < totalStages) {
        for (let index = names.length + 1; index <= totalStages; index += 1) {
            names.push(`Stage ${index}`);
        }
    }

    return names.map((name, index) => {
        const order = index + 1;
        const isActive = order === currentOrder;
        const isDone = order < currentOrder;

        const dotClass = isDone
            ? 'bg-violet-600 text-white border-violet-600'
            : isActive
                ? 'bg-violet-100 text-violet-700 border-violet-600'
                : 'bg-white text-slate-400 border-slate-300';

        const lineClass = order < currentOrder ? 'bg-violet-600' : 'bg-slate-200';
        return { name, dotClass, lineClass, isLast: order === names.length };
    });
}

function computeAttention() {
    const pendingApprovals = portalState.documents.filter(doc => doc.requires_approval && !doc.is_approved).length;
    const overdueTasks = portalState.tasks.filter(task => {
        if (!task.due_date) return false;
        return new Date(task.due_date) < new Date() && String(task.status || '').toLowerCase() !== 'completed';
    }).length;
    const activeConversations = portalState.conversations.filter(conv => String(conv.status || '').toLowerCase() === 'open').length;

    return { pendingApprovals, overdueTasks, activeConversations };
}

function renderAttentionCards() {
    const cardsEl = document.getElementById('portalAttentionCards');
    if (!cardsEl) return;

    const attention = computeAttention();
    cardsEl.innerHTML = `
        <div class="bg-white rounded-xl border border-slate-200 shadow-sm p-4">
            <p class="text-xs uppercase tracking-wide text-slate-500 mb-2">Belge Onayı</p>
            <p class="text-2xl font-bold text-slate-900">${attention.pendingApprovals}</p>
            <p class="text-xs text-slate-500 mt-1">Belge onay bekliyor</p>
        </div>
        <div class="bg-white rounded-xl border border-slate-200 shadow-sm p-4">
            <p class="text-xs uppercase tracking-wide text-slate-500 mb-2">Geciken Task</p>
            <p class="text-2xl font-bold text-slate-900">${attention.overdueTasks}</p>
            <p class="text-xs text-slate-500 mt-1">Takip gerektiren görev</p>
        </div>
        <div class="bg-white rounded-xl border border-slate-200 shadow-sm p-4">
            <p class="text-xs uppercase tracking-wide text-slate-500 mb-2">Açık Konuşma</p>
            <p class="text-2xl font-bold text-slate-900">${attention.activeConversations}</p>
            <p class="text-xs text-slate-500 mt-1">Yanıt bekleyen sohbet</p>
        </div>
    `;
}

function renderDealSummary() {
    const el = document.getElementById('portalDealSummary');
    if (!el) return;

    const deal = portalState.activeDeal;
    if (!deal) {
        el.innerHTML = '<p class="text-sm text-slate-500">Aktif CRM deal bulunamadı.</p>';
        return;
    }

    currentPortalDealId = deal.id;
    const steps = buildDealSteps(deal);

    el.innerHTML = `
        <div class="border border-slate-200 rounded-xl p-4 bg-slate-50 shadow-sm">
            <div class="flex flex-wrap items-center justify-between gap-3 mb-4">
                <h3 class="font-semibold text-sm lg:text-base">${htmlEscape(deal.name)}</h3>
                <span class="text-xs px-2 py-1 rounded-full bg-violet-100 text-violet-700 font-semibold">${htmlEscape(deal.stage?.name || 'N/A')}</span>
            </div>

            <div class="overflow-x-auto pb-2">
                <div class="min-w-[620px] flex items-start">
                    ${steps.map(step => `
                        <div class="flex items-center flex-1">
                            <div class="flex flex-col items-center min-w-[90px]">
                                <div class="w-8 h-8 rounded-full border-2 flex items-center justify-center text-xs font-bold ${step.dotClass}">•</div>
                                <p class="text-[11px] text-slate-600 mt-2 text-center">${htmlEscape(step.name)}</p>
                            </div>
                            ${step.isLast ? '' : `<div class="h-1 flex-1 rounded-full ${step.lineClass} mx-2 mb-5"></div>`}
                        </div>
                    `).join('')}
                </div>
            </div>

            <p class="text-xs text-slate-600 mt-3">Pipeline: ${htmlEscape(deal.pipeline || 'N/A')} • Değer: ${formatCurrency(deal.value)}</p>
            <p class="text-xs text-slate-500 mt-1">Aşama ${deal.stage?.order || 0}/${deal.stage?.total_stages || 0} • Beklenen kapanış: ${deal.expected_close_date ? fmtDate(deal.expected_close_date) : '—'}</p>
        </div>
    `;
}

function showApprovalInfo(message, type = 'success') {
    const infoEl = document.getElementById('portalApprovalInfo');
    if (!infoEl) return;

    infoEl.className = 'mb-4 px-4 py-3 rounded-xl text-sm';
    if (type === 'error') {
        infoEl.classList.add('bg-rose-50', 'text-rose-700');
    } else {
        infoEl.classList.add('bg-emerald-50', 'text-emerald-700');
    }
    infoEl.textContent = message;
}

function bindLogout() {
    const logoutBtn = document.getElementById('portalLogoutBtn');
    if (!logoutBtn) return;

    logoutBtn.addEventListener('click', () => {
        clearPortalToken();
        window.location.href = '/portal/login';
    });
}

async function loadPortalProfile() {
    const result = await requestJson('/portal/api/me');
    return result.ok ? result.data : null;
}

function renderTasks() {
    const tasksEl = document.getElementById('portalTasks');
    if (!tasksEl) return;

    if (portalState.tasks.length === 0) {
        tasksEl.innerHTML = '<p class="text-sm text-slate-500">Gösterilecek görev yok.</p>';
        return;
    }

    tasksEl.innerHTML = portalState.tasks.map(task => {
        const isCompleted = String(task.status || '').toLowerCase() === 'completed';
        return `
            <div class="border border-slate-200 rounded-xl p-3 bg-slate-50 shadow-sm" data-task-card-id="${task.id}">
                <div class="flex items-start justify-between gap-2 mb-2">
                    <div class="flex items-start gap-3">
                        <input
                            type="checkbox"
                            class="portal-task-toggle mt-0.5 h-4 w-4 rounded border-slate-300 text-violet-600 focus:ring-violet-300"
                            data-task-id="${task.id}"
                            ${isCompleted ? 'checked disabled' : ''}
                        />
                        <div>
                            <h3 class="font-semibold text-sm ${isCompleted ? 'line-through text-slate-400' : 'text-slate-800'}">${htmlEscape(task.title)}</h3>
                            <p class="text-xs mt-1 ${isCompleted ? 'line-through text-slate-400' : 'text-slate-600'}">${htmlEscape(task.description || 'Açıklama yok')}</p>
                        </div>
                    </div>
                    <div class="flex items-center gap-2">
                        ${taskPriorityBadge(task.priority)}
                        ${taskStatusBadge(task.status)}
                    </div>
                </div>
                <p class="text-xs text-slate-500">Due: ${fmtDate(task.due_date)}</p>
            </div>
        `;
    }).join('');

    document.querySelectorAll('.portal-task-toggle').forEach(checkbox => {
        checkbox.addEventListener('change', async () => {
            if (!checkbox.checked) {
                checkbox.checked = true;
                return;
            }

            const taskId = Number(checkbox.getAttribute('data-task-id'));
            checkbox.disabled = true;

            const result = await requestJson(
                `/portal/api/tasks/${taskId}`,
                {
                    method: 'PATCH',
                    body: JSON.stringify({ status: 'completed' }),
                },
                { success: 'Görev tamamlandı.' }
            );

            if (!result.ok) {
                checkbox.disabled = false;
                checkbox.checked = false;
                return;
            }

            portalState.tasks = portalState.tasks.map(task => (
                task.id === taskId
                    ? { ...task, status: 'completed', completed_at: new Date().toISOString() }
                    : task
            ));

            renderTasks();
            renderAttentionCards();
        });
    });
}

function renderMilestones() {
    const milestonesEl = document.getElementById('portalMilestones');
    if (!milestonesEl) return;

    if (portalState.milestones.length === 0) {
        milestonesEl.innerHTML = '<p class="text-sm text-slate-500">Gösterilecek milestone yok.</p>';
        return;
    }

    milestonesEl.innerHTML = portalState.milestones.map(m => `
        <div class="border border-slate-200 rounded-xl p-3 bg-slate-50 shadow-sm">
            <div class="flex items-center justify-between mb-2">
                <h3 class="font-semibold text-sm">${htmlEscape(m.name)}</h3>
                <span class="text-xs text-slate-500">%${m.progress.progress_percentage}</span>
            </div>
            <div class="w-full h-2 bg-slate-200 rounded-full overflow-hidden">
                <div class="h-full bg-violet-500" style="width:${Math.min(100, m.progress.progress_percentage)}%"></div>
            </div>
            <p class="text-xs text-slate-500 mt-2">${m.progress.completed_tasks}/${m.progress.total_tasks} task tamamlandı</p>
        </div>
    `).join('');
}

function renderDocuments() {
    const listEl = document.getElementById('portalDocuments');
    if (!listEl) return;

    if (portalState.documents.length === 0) {
        listEl.innerHTML = '<p class="text-sm text-slate-500">Paylaşılan doküman bulunamadı.</p>';
        return;
    }

    listEl.innerHTML = portalState.documents.map(doc => {
        const approvalBadge = doc.requires_approval
            ? (doc.is_approved
                ? '<span class="text-[11px] px-2 py-1 rounded-full bg-emerald-100 text-emerald-700 font-semibold">Approved</span>'
                : '<span class="text-[11px] px-2 py-1 rounded-full bg-amber-100 text-amber-700 font-semibold">Approval Required</span>')
            : '<span class="text-[11px] px-2 py-1 rounded-full bg-slate-200 text-slate-700 font-semibold">Info</span>';

        const approveButton = doc.requires_approval
            ? (doc.is_approved
                ? '<button disabled class="px-3 py-2 rounded-xl bg-emerald-500 text-white text-xs font-semibold opacity-80 cursor-not-allowed shadow-sm">Approved</button>'
                : `<button data-doc-id="${doc.id}" data-deal-id="${doc.linked_deal_id || ''}" class="portal-doc-approve px-4 py-2 rounded-xl bg-violet-600 text-white text-xs font-semibold hover:bg-violet-700 shadow-md transition-colors">Approve</button>`)
            : '';

        return `
            <div class="border border-slate-200 rounded-xl p-3 flex items-center justify-between gap-3 bg-slate-50 shadow-sm">
                <div>
                    <div class="flex items-center gap-2 mb-1">
                        <h3 class="font-semibold text-sm">${htmlEscape(doc.name)}</h3>
                        ${approvalBadge}
                    </div>
                    <p class="text-xs text-slate-500 mt-1">${htmlEscape(doc.category || 'General')} • ${fmtDate(doc.created_at)}</p>
                </div>
                <div class="flex items-center gap-2">
                    ${approveButton}
                    <button data-doc-id="${doc.id}" class="portal-doc-download px-3 py-2 rounded-xl bg-white border border-slate-300 text-slate-700 text-xs font-semibold hover:bg-slate-100">Download</button>
                </div>
            </div>
        `;
    }).join('');

    bindDocumentActions();
}

function bindDocumentActions() {
    document.querySelectorAll('.portal-doc-download').forEach(btn => {
        btn.addEventListener('click', async () => {
            const docId = btn.getAttribute('data-doc-id');
            const response = await portalFetch(`/portal/api/documents/${docId}/download`, { method: 'GET' });
            if (!response || !response.ok) {
                showToast('Doküman indirilemedi.', 'error');
                return;
            }

            const blob = await response.blob();
            const url = window.URL.createObjectURL(blob);
            const anchor = document.createElement('a');
            anchor.href = url;
            anchor.download = `document-${docId}`;
            document.body.appendChild(anchor);
            anchor.click();
            anchor.remove();
            window.URL.revokeObjectURL(url);
            showToast('Doküman indiriliyor...', 'success');
        });
    });

    document.querySelectorAll('.portal-doc-approve').forEach(btn => {
        btn.addEventListener('click', async () => {
            const docId = btn.getAttribute('data-doc-id');
            const dealId = btn.getAttribute('data-deal-id') || currentPortalDealId || null;

            btn.disabled = true;
            const originalHtml = btn.innerHTML;
            btn.innerHTML = '<span class="inline-flex items-center gap-2"><svg class="animate-spin h-3.5 w-3.5" viewBox="0 0 24 24" fill="none"><circle cx="12" cy="12" r="10" stroke="currentColor" stroke-opacity="0.3" stroke-width="3"></circle><path d="M22 12a10 10 0 00-10-10" stroke="currentColor" stroke-width="3" stroke-linecap="round"></path></svg>Approving...</span>';

            const payload = dealId ? { deal_id: Number(dealId) } : {};
            const result = await requestJson(
                `/portal/api/documents/${docId}/approve`,
                {
                    method: 'POST',
                    body: JSON.stringify(payload),
                },
                { success: 'Belge başarıyla onaylandı.' }
            );

            if (!result.ok) {
                btn.disabled = false;
                btn.innerHTML = originalHtml;
                showApprovalInfo('Belge onaylanamadı.', 'error');
                return;
            }

            const responseData = result.data || {};
            if (responseData.deal) {
                portalState.activeDeal = responseData.deal;
                renderDealSummary();
            }

            portalState.documents = portalState.documents.map(doc => (
                doc.id === Number(docId)
                    ? { ...doc, is_approved: true }
                    : doc
            ));

            btn.innerHTML = 'Approved';
            btn.classList.remove('bg-violet-600', 'hover:bg-violet-700', 'shadow-md');
            btn.classList.add('bg-emerald-500', 'cursor-not-allowed', 'shadow-sm');
            btn.disabled = true;

            renderAttentionCards();

            if (responseData.stage_transition) {
                showApprovalInfo(`Onay alındı. CRM stage ilerledi: ${responseData.stage_transition.from} → ${responseData.stage_transition.to}`, 'success');
                showToast(`Deal stage güncellendi: ${responseData.stage_transition.to}`, 'success');
            } else if (responseData.status === 'already_approved') {
                showApprovalInfo('Bu doküman zaten onaylanmış.', 'success');
            } else {
                showApprovalInfo('Onay alındı ve CRM kaydına işlendi.', 'success');
            }
        });
    });
}

function renderConversationsList() {
    const listEl = document.getElementById('portalConversationList');
    if (!listEl) return;

    if (portalState.conversations.length === 0) {
        listEl.innerHTML = '<p class="text-sm text-slate-500">Konuşma bulunamadı.</p>';
        return;
    }

    listEl.innerHTML = portalState.conversations.map(conv => `
        <button data-conv-id="${conv.id}" class="portal-conv-btn w-full text-left p-3 rounded-xl border border-slate-200 bg-slate-50 hover:bg-slate-100">
            <p class="font-semibold text-sm">${htmlEscape(conv.customer_name || 'Customer')}</p>
            <p class="text-xs text-slate-500 mt-1 truncate">${htmlEscape(conv.last_message || '')}</p>
        </button>
    `).join('');

    document.querySelectorAll('.portal-conv-btn').forEach(btn => {
        btn.addEventListener('click', async () => {
            activeConversationId = Number(btn.getAttribute('data-conv-id'));
            await loadConversationDetail(activeConversationId);
        });
    });
}

function renderMessageBubbles(messages) {
    const messagesEl = document.getElementById('portalMessages');
    if (!messagesEl) return;

    messagesEl.innerHTML = messages.map(msg => {
        const isCustomer = msg.sender_type === 'customer';
        const bubbleClass = isCustomer
            ? 'bg-violet-50 border border-violet-100 ml-8'
            : 'bg-slate-100 border border-slate-200 mr-8';

        const messageIdAttr = msg.id ? `data-message-id="${msg.id}"` : `data-temp-id="${msg.temp_id || ''}"`;
        return `
            <div ${messageIdAttr} class="px-3 py-2 rounded-xl ${bubbleClass}">
                <p class="text-xs font-semibold text-slate-600 mb-1">${htmlEscape(msg.sender_type)}</p>
                <p class="text-sm text-slate-800">${htmlEscape(msg.message_body)}</p>
                <p class="text-[11px] text-slate-500 mt-1">${fmtDate(msg.created_at)}</p>
            </div>
        `;
    }).join('');

    messagesEl.scrollTop = messagesEl.scrollHeight;
}

async function loadConversationDetail(conversationId) {
    const result = await requestJson(`/portal/api/messages/${conversationId}`);
    if (!result.ok) return;

    const data = result.data || {};
    const titleEl = document.getElementById('portalConversationTitle');
    if (titleEl) {
        titleEl.textContent = data.customer_name || 'Conversation';
    }

    portalState.messagesByConversation[conversationId] = data.messages || [];
    renderMessageBubbles(portalState.messagesByConversation[conversationId]);
}

function updateConversationPreview(conversationId, lastMessage) {
    portalState.conversations = portalState.conversations.map(conv => (
        conv.id === conversationId
            ? { ...conv, last_message: lastMessage, last_message_at: new Date().toISOString() }
            : conv
    ));
    renderConversationsList();
}

function startMessagePolling() {
    if (messagePollingTimer) {
        window.clearInterval(messagePollingTimer);
    }

    messagePollingTimer = window.setInterval(async () => {
        if (!activeConversationId) return;

        const result = await requestJson(`/portal/api/messages/${activeConversationId}`);
        if (!result.ok) return;

        const incoming = result.data?.messages || [];
        const existing = portalState.messagesByConversation[activeConversationId] || [];
        const existingIds = new Set(existing.filter(m => m.id).map(m => Number(m.id)));
        const fresh = incoming.filter(m => m.id && !existingIds.has(Number(m.id)));

        if (fresh.length > 0) {
            portalState.messagesByConversation[activeConversationId] = incoming;
            renderMessageBubbles(incoming);

            const newestAgent = fresh.filter(msg => msg.sender_type === 'agent').pop();
            if (newestAgent) {
                showToast('Yeni bir ajan mesajı geldi.', 'info');
                updateConversationPreview(activeConversationId, newestAgent.message_body || '');
            }
        }
    }, 5000);
}

async function initLoginPage() {
    if (portalToken()) {
        window.location.href = '/portal/dashboard';
        return;
    }

    const form = document.getElementById('portalLoginForm');
    const errorEl = document.getElementById('portalLoginError');
    const loginBtn = document.getElementById('portalLoginBtn');

    form.addEventListener('submit', async (event) => {
        event.preventDefault();
        errorEl.classList.add('hidden');
        loginBtn.disabled = true;

        try {
            const response = await fetch('/portal/login', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    email: document.getElementById('portalEmail').value.trim(),
                    password: document.getElementById('portalPassword').value,
                }),
            });

            const data = await response.json();
            if (!response.ok) {
                errorEl.textContent = data.error || 'Login failed';
                errorEl.classList.remove('hidden');
                loginBtn.disabled = false;
                showToast(data.error || 'Login başarısız.', 'error');
                return;
            }

            setPortalToken(data.token);
            showToast('Giriş başarılı.', 'success');
            window.location.href = '/portal/dashboard';
        } catch (_) {
            errorEl.textContent = 'Login sırasında hata oluştu';
            errorEl.classList.remove('hidden');
            loginBtn.disabled = false;
            showToast('Login sırasında hata oluştu.', 'error');
        }
    });
}

async function initDashboardPage() {
    bindLogout();
    await loadPortalBrandingConfig();

    const profile = await loadPortalProfile();
    if (!profile) return;

    const welcome = document.getElementById('portalWelcome');
    if (welcome) {
        welcome.textContent = `${profile.full_name} • ${profile.company_name || 'Company'}`;
    }

    const [tasksRes, milestonesRes, dealRes, docsRes, convRes] = await Promise.all([
        requestJson('/portal/api/tasks'),
        requestJson('/portal/api/milestones'),
        requestJson('/portal/api/deal-summary'),
        requestJson('/portal/api/documents'),
        requestJson('/portal/api/messages'),
    ]);

    if (!tasksRes.ok || !milestonesRes.ok || !dealRes.ok || !docsRes.ok || !convRes.ok) {
        showToast('Dashboard verileri yüklenemedi.', 'error');
        return;
    }

    portalState.tasks = tasksRes.data.tasks || [];
    portalState.milestones = milestonesRes.data.milestones || [];
    portalState.documents = docsRes.data.documents || [];
    portalState.conversations = convRes.data.conversations || [];
    portalState.activeDeal = dealRes.data.deal || null;

    renderAttentionCards();
    renderDealSummary();
    renderTasks();
    renderMilestones();
}

async function initDocumentsPage() {
    bindLogout();
    await loadPortalBrandingConfig();

    const [docsRes, dealRes] = await Promise.all([
        requestJson('/portal/api/documents'),
        requestJson('/portal/api/deal-summary'),
    ]);

    if (!docsRes.ok || !dealRes.ok) {
        showToast('Dokümanlar yüklenemedi.', 'error');
        return;
    }

    portalState.documents = docsRes.data.documents || [];
    portalState.activeDeal = dealRes.data.deal || null;
    currentPortalDealId = portalState.activeDeal?.id || null;

    renderDocuments();
}

async function initMessagesPage() {
    bindLogout();
    await loadPortalBrandingConfig();

    const listRes = await requestJson('/portal/api/messages');
    if (!listRes.ok) {
        showToast('Mesaj listesi yüklenemedi.', 'error');
        return;
    }

    portalState.conversations = listRes.data.conversations || [];
    renderConversationsList();

    if (portalState.conversations.length > 0) {
        activeConversationId = Number(portalState.conversations[0].id);
        await loadConversationDetail(activeConversationId);
        startMessagePolling();
    }

    const sendForm = document.getElementById('portalSendForm');
    sendForm?.addEventListener('submit', async (event) => {
        event.preventDefault();
        if (!activeConversationId) return;

        const input = document.getElementById('portalMessageInput');
        const text = (input?.value || '').trim();
        if (!text) return;

        const tempId = `temp-${Date.now()}`;
        const optimisticMessage = {
            temp_id: tempId,
            sender_type: 'customer',
            message_body: text,
            created_at: new Date().toISOString(),
        };

        if (!portalState.messagesByConversation[activeConversationId]) {
            portalState.messagesByConversation[activeConversationId] = [];
        }
        portalState.messagesByConversation[activeConversationId].push(optimisticMessage);
        renderMessageBubbles(portalState.messagesByConversation[activeConversationId]);
        updateConversationPreview(activeConversationId, text);

        if (input) {
            input.value = '';
            input.focus();
        }

        const result = await requestJson(
            `/portal/api/messages/${activeConversationId}`,
            {
                method: 'POST',
                body: JSON.stringify({ message_body: text }),
            },
            { success: 'Mesaj gönderildi.' }
        );

        if (!result.ok) {
            portalState.messagesByConversation[activeConversationId] = portalState.messagesByConversation[activeConversationId]
                .filter(msg => msg.temp_id !== tempId);
            renderMessageBubbles(portalState.messagesByConversation[activeConversationId]);
            showToast('Mesaj gönderilemedi.', 'error');
            return;
        }

        await loadConversationDetail(activeConversationId);
    });
}

(function initPortalPage() {
    const page = document.body?.dataset?.portalPage;
    if (!page) return;

    applyPortalBranding(embeddedBranding());

    if (page !== 'login' && !portalToken()) {
        window.location.href = '/portal/login';
        return;
    }

    if (page === 'login') {
        initLoginPage();
    } else if (page === 'dashboard') {
        initDashboardPage();
    } else if (page === 'documents') {
        initDocumentsPage();
    } else if (page === 'messages') {
        initMessagesPage();
    }

    window.addEventListener('beforeunload', () => {
        if (messagePollingTimer) {
            window.clearInterval(messagePollingTimer);
            messagePollingTimer = null;
        }
    });
})();
