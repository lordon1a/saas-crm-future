let currentView = 'list';
let tasks = [];
let milestones = [];
let teamMembers = [];
let selectedTask = null;
let searchDebounce = null;

document.addEventListener('DOMContentLoaded', () => {
    bindEvents();
    initializePage();
});

function bindEvents() {
    document.getElementById('viewListBtn').addEventListener('click', () => switchView('list'));
    document.getElementById('viewGanttBtn').addEventListener('click', () => switchView('gantt'));
    document.getElementById('refreshTasksBtn').addEventListener('click', refreshAll);

    document.getElementById('filter-status').addEventListener('change', loadTasks);
    document.getElementById('filter-priority').addEventListener('change', loadTasks);
    document.getElementById('filter-milestone').addEventListener('change', loadTasks);
    document.getElementById('filter-customer-facing').addEventListener('change', loadTasks);
    document.getElementById('filter-search').addEventListener('input', () => {
        clearTimeout(searchDebounce);
        searchDebounce = setTimeout(() => renderTasks(), 250);
    });

    document.getElementById('taskForm').addEventListener('submit', saveTask);
    document.getElementById('milestoneForm').addEventListener('submit', saveMilestone);
}

async function initializePage() {
    await Promise.all([loadTeamMembers(), loadMilestones()]);
    await loadTasks();
}

async function refreshAll() {
    await Promise.all([loadTeamMembers(), loadMilestones(), loadTasks()]);
    showToast('Veriler güncellendi', 'success');
}

async function loadTeamMembers() {
    try {
        const response = await fetch('/api/settings/team');
        if (!response.ok) {
            teamMembers = [];
            updateAssigneeSelect();
            return;
        }

        teamMembers = await response.json();
        updateAssigneeSelect();
    } catch (error) {
        console.error('Team load error:', error);
        teamMembers = [];
        updateAssigneeSelect();
    }
}

function updateAssigneeSelect() {
    const select = document.getElementById('task-assignee');
    if (!select) return; // Element not found, skip update
    const options = teamMembers.map(user => `<option value="${user.id}">${escapeHtml(user.name)} (${escapeHtml(user.role)})</option>`).join('');
    select.innerHTML = '<option value="">Unassigned</option>' + options;
}

async function loadMilestones() {
    try {
        const response = await fetch('/api/v1/milestones');
        if (!response.ok) {
            milestones = [];
            renderMilestones();
            updateMilestoneSelects();
            return;
        }

        const data = await response.json();
        milestones = data.milestones || [];
        renderMilestones();
        updateMilestoneSelects();
    } catch (error) {
        console.error('Milestones load error:', error);
        milestones = [];
        renderMilestones();
        updateMilestoneSelects();
    }
}

function renderMilestones() {
    const grid = document.getElementById('milestonesGrid');
    document.getElementById('milestoneCount').textContent = `${milestones.length} milestone`;

    if (milestones.length === 0) {
        grid.innerHTML = '<div class="col-span-full text-sm text-slate-500 border border-dashed border-slate-300 rounded-xl px-4 py-6 text-center">Henüz milestone yok. “Yeni Milestone” ile başlayabilirsin.</div>';
        return;
    }

    grid.innerHTML = milestones.map(milestone => {
        const progress = milestone.progress?.progress_percentage ?? 0;
        const completed = milestone.progress?.completed_tasks ?? 0;
        const total = milestone.progress?.total_tasks ?? 0;

        return `
            <div class="rounded-2xl border border-slate-200 bg-slate-50 p-4">
                <div class="flex items-start justify-between mb-2 gap-3">
                    <h3 class="text-sm font-bold text-slate-800">${escapeHtml(milestone.name)}</h3>
                    <span class="text-xs px-2 py-0.5 bg-white border border-slate-200 rounded-full text-slate-600">%${progress}</span>
                </div>
                <div class="w-full h-2 bg-slate-200 rounded-full overflow-hidden mb-2">
                    <div class="h-full bg-emerald-500" style="width:${Math.min(progress, 100)}%"></div>
                </div>
                <div class="text-xs text-slate-600">${completed} / ${total} görev tamamlandı</div>
                <div class="text-xs text-slate-500 mt-1">${milestone.due_date ? `Bitiş: ${formatDate(milestone.due_date)}` : 'Bitiş tarihi yok'}</div>
            </div>
        `;
    }).join('');
}

function updateMilestoneSelects() {
    const options = milestones.map(m => `<option value="${m.id}">${escapeHtml(m.name)}</option>`).join('');
    document.getElementById('filter-milestone').innerHTML = '<option value="">Tüm Milestones</option>' + options;
    document.getElementById('task-milestone').innerHTML = '<option value="">None</option>' + options;
}

async function loadTasks() {
    try {
        const params = new URLSearchParams();
        const status = document.getElementById('filter-status').value;
        const priority = document.getElementById('filter-priority').value;
        const milestoneId = document.getElementById('filter-milestone').value;
        const customerFacing = document.getElementById('filter-customer-facing').checked;

        if (status) params.append('status', status);
        if (priority) params.append('priority', priority);
        if (milestoneId) params.append('milestone_id', milestoneId);
        if (customerFacing) params.append('is_customer_facing', 'true');

        const response = await fetch(`/api/v1/tasks?${params}`);
        if (!response.ok) {
            showToast('Görevler yüklenemedi', 'error');
            return;
        }

        const data = await response.json();
        tasks = data.tasks || [];
        renderTasks();
        renderStats();
    } catch (error) {
        console.error('Tasks load error:', error);
        showToast('Görevler yüklenirken hata oluştu', 'error');
    }
}

function renderTasks() {
    if (currentView === 'list') {
        renderTaskList();
    } else {
        renderGanttChart();
    }
}

function getVisibleTasks() {
    const search = document.getElementById('filter-search').value.trim().toLowerCase();
    if (!search) {
        return tasks;
    }

    return tasks.filter(task => {
        const title = (task.title || '').toLowerCase();
        const description = (task.description || '').toLowerCase();
        return title.includes(search) || description.includes(search);
    });
}

function renderStats() {
    const visibleTasks = getVisibleTasks();
    const now = new Date();

    const inProgress = visibleTasks.filter(task => task.status === 'in_progress').length;
    const completed = visibleTasks.filter(task => task.status === 'completed').length;
    const overdue = visibleTasks.filter(task => {
        if (!task.due_date) {
            return false;
        }

        if (task.status === 'completed' || task.status === 'cancelled') {
            return false;
        }

        return new Date(task.due_date) < now;
    }).length;

    document.getElementById('statsTotalTasks').textContent = visibleTasks.length;
    document.getElementById('statsInProgress').textContent = inProgress;
    document.getElementById('statsCompleted').textContent = completed;
    document.getElementById('statsOverdue').textContent = overdue;
    document.getElementById('tasksLiveInfo').textContent = `${visibleTasks.length} görev listeleniyor`;
}

function renderTaskList() {
    const container = document.getElementById('taskListView');
    const visibleTasks = getVisibleTasks();

    if (visibleTasks.length === 0) {
        container.innerHTML = '<div class="col-span-full text-sm text-slate-500 border border-dashed border-slate-300 rounded-xl px-4 py-10 text-center">Filtreye uygun görev bulunamadı.</div>';
        return;
    }

    container.innerHTML = visibleTasks.map(task => {
        const milestone = milestones.find(m => m.id === task.milestone_id);
        const assignee = teamMembers.find(member => member.id === task.assignee_id);

        return `
            <div class="bg-white border rounded-2xl p-4 shadow-sm hover:shadow-md transition-all cursor-pointer ${priorityBorderClass(task.priority)}" onclick="openTaskModal(${task.id})">
                <div class="flex items-start justify-between gap-3 mb-2">
                    <h3 class="text-sm font-bold text-slate-800 leading-5">${escapeHtml(task.title)}</h3>
                    <span class="text-[11px] px-2 py-1 rounded-full font-semibold ${statusBadgeClass(task.status)}">${formatStatus(task.status)}</span>
                </div>
                <p class="text-xs text-slate-500 line-clamp-2 min-h-[32px]">${escapeHtml(task.description || 'Açıklama girilmemiş.')}</p>
                <div class="mt-3 pt-3 border-t border-slate-100 grid grid-cols-2 gap-2 text-xs text-slate-600">
                    <span><i class="far fa-calendar mr-1"></i>${task.due_date ? formatDate(task.due_date) : 'Tarih yok'}</span>
                    <span><i class="fas fa-bolt mr-1"></i>${task.priority}</span>
                    <span><i class="fas fa-flag mr-1"></i>${milestone ? escapeHtml(milestone.name) : 'Milestone yok'}</span>
                    <span><i class="fas fa-user mr-1"></i>${assignee ? escapeHtml(assignee.name) : 'Unassigned'}</span>
                </div>
                ${task.is_customer_facing ? '<div class="mt-3 text-[11px] inline-flex items-center gap-1 px-2 py-1 bg-emerald-50 text-emerald-700 rounded-full"><i class="fas fa-eye"></i>Müşteriye açık</div>' : ''}
            </div>
        `;
    }).join('');
}

function renderGanttChart() {
    const content = document.getElementById('ganttContent');
    const visibleTasks = getVisibleTasks().filter(task => task.due_date);

    if (visibleTasks.length === 0) {
        content.innerHTML = '<div class="p-8 text-sm text-slate-500 text-center">Gantt görünümü için son tarihli görev bulunamadı.</div>';
        return;
    }

    const dueDates = visibleTasks.map(task => new Date(task.due_date));
    const minDate = new Date(Math.min(...dueDates));
    const maxDate = new Date(Math.max(...dueDates));
    const diffDays = Math.max(1, Math.ceil((maxDate - minDate) / (1000 * 60 * 60 * 24)) + 1);

    const headerDays = Array.from({ length: Math.min(diffDays, 30) }, (_, index) => {
        const date = new Date(minDate);
        date.setDate(date.getDate() + index);
        return `<div class="text-[11px] text-slate-500 text-center">${date.getDate()}/${date.getMonth() + 1}</div>`;
    }).join('');

    const rows = visibleTasks.map(task => {
        const dueDate = new Date(task.due_date);
        const offset = Math.max(0, Math.ceil((dueDate - minDate) / (1000 * 60 * 60 * 24)));
        const leftPercent = (offset / diffDays) * 100;
        const barColor = task.status === 'completed' ? 'bg-emerald-500' : task.status === 'blocked' ? 'bg-rose-500' : 'bg-brand-500';

        return `
            <div class="grid grid-cols-[280px_1fr] gap-4 px-4 py-3 border-t border-slate-100 items-center">
                <button class="text-left text-sm font-medium text-slate-700 hover:text-brand-600" onclick="openTaskModal(${task.id})">${escapeHtml(task.title)}</button>
                <div class="relative h-6 bg-slate-100 rounded-lg overflow-hidden">
                    <div class="absolute inset-y-0 ${barColor} rounded-lg" style="left:${leftPercent}%; width: max(8%, 44px);"></div>
                </div>
            </div>
        `;
    }).join('');

    content.innerHTML = `
        <div class="grid grid-cols-[280px_1fr] gap-4 px-4 py-3 bg-slate-50 border-b border-slate-200 sticky top-0">
            <div class="text-xs font-bold text-slate-500 uppercase tracking-wider">Görev</div>
            <div class="grid gap-2" style="grid-template-columns: repeat(${Math.min(diffDays, 30)}, minmax(24px, 1fr));">${headerDays}</div>
        </div>
        ${rows}
    `;
}

function switchView(view) {
    currentView = view;
    const listBtn = document.getElementById('viewListBtn');
    const ganttBtn = document.getElementById('viewGanttBtn');
    const listView = document.getElementById('taskListView');
    const ganttView = document.getElementById('ganttView');

    if (view === 'list') {
        listBtn.className = 'px-3 py-2 rounded-xl text-sm font-semibold bg-brand-50 text-brand-600 border border-brand-100';
        ganttBtn.className = 'px-3 py-2 rounded-xl text-sm font-semibold bg-white text-slate-600 border border-slate-200';
        listView.classList.remove('hidden');
        ganttView.classList.add('hidden');
    } else {
        ganttBtn.className = 'px-3 py-2 rounded-xl text-sm font-semibold bg-brand-50 text-brand-600 border border-brand-100';
        listBtn.className = 'px-3 py-2 rounded-xl text-sm font-semibold bg-white text-slate-600 border border-slate-200';
        ganttView.classList.remove('hidden');
        listView.classList.add('hidden');
    }

    renderTasks();
}

function openTaskModal(taskId = null) {
    const modal = document.getElementById('taskModal');
    modal.classList.remove('hidden');
    modal.classList.add('flex');

    if (taskId) {
        loadTaskDetails(taskId);
    } else {
        resetTaskForm();
    }
}

function closeTaskModal() {
    const modal = document.getElementById('taskModal');
    modal.classList.add('hidden');
    modal.classList.remove('flex');
    selectedTask = null;
}

function resetTaskForm() {
    document.getElementById('taskForm').reset();
    document.getElementById('task-id').value = '';
    document.getElementById('taskModalTitle').textContent = 'Yeni Görev';
    document.getElementById('taskDetailPanels').classList.add('hidden');
    document.getElementById('deleteTaskBtn').classList.add('hidden');
    document.getElementById('dependencies-list').innerHTML = '';
    document.getElementById('comments-list').innerHTML = '';
    document.getElementById('attachments-list').innerHTML = '';
    updateDependencySelect([]);
    if (typeof setTaskAssignee !== 'undefined') {
        setTaskAssignee('');
    }
}

async function loadTaskDetails(taskId) {
    try {
        const response = await fetch(`/api/v1/tasks/${taskId}`);
        if (!response.ok) {
            showToast('Görev detayları alınamadı', 'error');
            return;
        }

        const task = await response.json();
        selectedTask = task;

        document.getElementById('taskModalTitle').textContent = 'Görevi Düzenle';
        document.getElementById('task-id').value = task.id;
        document.getElementById('task-title').value = task.title || '';
        document.getElementById('task-description').value = task.description || '';
        document.getElementById('task-priority').value = task.priority || 'medium';
        document.getElementById('task-status').value = task.status || 'not_started';
        document.getElementById('task-milestone').value = task.milestone_id || '';
        
        if (typeof setTaskAssignee !== 'undefined') {
            setTaskAssignee(task.assignee_id || '');
        } else {
            const assigneeSelect = document.getElementById('task-assignee');
            if (assigneeSelect) assigneeSelect.value = task.assignee_id || '';
        }
        
        document.getElementById('task-customer-facing').checked = Boolean(task.is_customer_facing);
        document.getElementById('task-due-date').value = task.due_date ? toDateTimeLocal(task.due_date) : '';

        document.getElementById('taskDetailPanels').classList.remove('hidden');
        document.getElementById('deleteTaskBtn').classList.remove('hidden');

        renderDependencies(task.dependencies || []);
        updateDependencySelect(task.dependencies || []);
        await Promise.all([loadComments(task.id), loadAttachments(task.id)]);
    } catch (error) {
        console.error('Task detail error:', error);
        showToast('Görev detaylarında hata oluştu', 'error');
    }
}

async function saveTask(event) {
    event.preventDefault();

    const taskId = document.getElementById('task-id').value;
    const payload = {
        title: document.getElementById('task-title').value.trim(),
        description: document.getElementById('task-description').value.trim(),
        priority: document.getElementById('task-priority').value,
        status: document.getElementById('task-status').value,
        is_customer_facing: document.getElementById('task-customer-facing').checked
    };

    const dueDate = document.getElementById('task-due-date').value;
    const milestoneId = document.getElementById('task-milestone').value;
    const assigneeSelect = document.getElementById('task-assignee');
    const assigneeId = typeof getTaskAssignee !== 'undefined' ? getTaskAssignee() : (assigneeSelect ? assigneeSelect.value : null);

    if (dueDate) {
        payload.due_date = new Date(dueDate).toISOString();
    }
    if (milestoneId) {
        payload.milestone_id = Number(milestoneId);
    }
    if (assigneeId) {
        payload.assignee_id = Number(assigneeId);
    }

    // Prevent double submission
    if (window.isSavingTask) {
        return;
    }
    window.isSavingTask = true;

    const isUpdate = Boolean(taskId);
    let previousTaskSnapshot = null;

    // Adım 1: Mevcut Durumu Sakla
    if (isUpdate) {
        const existingTask = tasks.find(task => String(task.id) === String(taskId));
        previousTaskSnapshot = existingTask ? { ...existingTask } : null;
    }

    // Adım 2: Arayüzü Anında Güncelle
    if (isUpdate && previousTaskSnapshot) {
        const optimisticTask = {
            ...previousTaskSnapshot,
            ...payload,
            id: previousTaskSnapshot.id
        };

        tasks = tasks.map(task => String(task.id) === String(taskId) ? optimisticTask : task);
        if (selectedTask && String(selectedTask.id) === String(taskId)) {
            selectedTask = { ...selectedTask, ...optimisticTask };
        }
        renderTasks();
        renderStats();
    }

    try {
        // Adım 3: Arka Planda API İsteğini At
        const response = await fetch(isUpdate ? `/api/v1/tasks/${taskId}` : '/api/v1/tasks', {
            method: isUpdate ? 'PATCH' : 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        const responseData = await safeJson(response);

        if (!response.ok) {
            // Adım 4: Hata Yönetimi ve Geri Alma
            if (isUpdate && previousTaskSnapshot) {
                tasks = tasks.map(task => String(task.id) === String(taskId) ? previousTaskSnapshot : task);
                if (selectedTask && String(selectedTask.id) === String(taskId)) {
                    selectedTask = { ...selectedTask, ...previousTaskSnapshot };
                }
                renderTasks();
                renderStats();
            }

            showToast(responseData?.error || 'Görev kaydedilemedi', 'error');
            return;
        }

        if (isUpdate && responseData && typeof responseData === 'object') {
            tasks = tasks.map(task => String(task.id) === String(taskId) ? responseData : task);
            if (selectedTask && String(selectedTask.id) === String(taskId)) {
                selectedTask = responseData;
            }
        }

        showToast(isUpdate ? 'Görev güncellendi' : 'Görev oluşturuldu', 'success');
        closeTaskModal();
        await Promise.all([loadTasks(), loadMilestones()]);
    } catch (error) {
        console.error('Task save error:', error);

        // Adım 4: Hata Yönetimi ve Geri Alma
        if (isUpdate && previousTaskSnapshot) {
            tasks = tasks.map(task => String(task.id) === String(taskId) ? previousTaskSnapshot : task);
            if (selectedTask && String(selectedTask.id) === String(taskId)) {
                selectedTask = { ...selectedTask, ...previousTaskSnapshot };
            }
            renderTasks();
            renderStats();
        }

        showToast('Görev kaydı sırasında hata oluştu', 'error');
    } finally {
        window.isSavingTask = false;
    }
}

async function deleteCurrentTask() {
    const taskId = document.getElementById('task-id').value;
    if (!taskId) {
        return;
    }

    if (!window.confirm('Bu görevi silmek istediğine emin misin?')) {
        return;
    }

    try {
        const response = await fetch(`/api/v1/tasks/${taskId}`, { method: 'DELETE' });
        if (!response.ok) {
            const errorData = await safeJson(response);
            showToast(errorData?.error || 'Görev silinemedi', 'error');
            return;
        }

        showToast('Görev silindi', 'success');
        closeTaskModal();
        await Promise.all([loadTasks(), loadMilestones()]);
    } catch (error) {
        console.error('Task delete error:', error);
        showToast('Görev silinirken hata oluştu', 'error');
    }
}

function updateDependencySelect(existingDependencies) {
    const currentTaskId = Number(document.getElementById('task-id').value);
    const existingIds = new Set(existingDependencies.map(dep => dep.id));
    const candidates = tasks.filter(task => task.id !== currentTaskId && !existingIds.has(task.id));
    const select = document.getElementById('dependency-select');

    const options = candidates
        .map(task => `<option value="${task.id}">${escapeHtml(task.title)} (#${task.id})</option>`)
        .join('');

    select.innerHTML = '<option value="">Bağımlı görev seç</option>' + options;
}

function renderDependencies(dependencies) {
    const list = document.getElementById('dependencies-list');

    if (dependencies.length === 0) {
        list.innerHTML = '<div class="text-xs text-slate-500">Bağımlılık yok.</div>';
        return;
    }

    list.innerHTML = dependencies.map(dep => `
        <div class="flex items-center justify-between gap-2 px-3 py-2 bg-slate-50 border border-slate-200 rounded-xl text-xs">
            <div>
                <span class="font-semibold text-slate-700">${escapeHtml(dep.title)}</span>
                <span class="text-slate-500">(${formatStatus(dep.status)})</span>
            </div>
            <button type="button" onclick="removeDependency(${dep.id})" class="text-rose-600 hover:text-rose-700 font-semibold">Kaldır</button>
        </div>
    `).join('');
}

async function addDependency() {
    const taskId = document.getElementById('task-id').value;
    const dependsOnTaskId = document.getElementById('dependency-select').value;

    if (!taskId || !dependsOnTaskId) {
        showToast('Bağımlılık için görev seç', 'error');
        return;
    }

    try {
        const response = await fetch(`/api/v1/tasks/${taskId}/dependencies`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ depends_on_task_id: Number(dependsOnTaskId) })
        });

        if (!response.ok) {
            const errorData = await safeJson(response);
            showToast(errorData?.error || 'Bağımlılık eklenemedi', 'error');
            return;
        }

        showToast('Bağımlılık eklendi', 'success');
        await Promise.all([loadTaskDetails(Number(taskId)), loadTasks()]);
    } catch (error) {
        console.error('Add dependency error:', error);
        showToast('Bağımlılık ekleme hatası', 'error');
    }
}

async function removeDependency(dependsOnTaskId) {
    const taskId = document.getElementById('task-id').value;
    if (!taskId) {
        return;
    }

    try {
        const response = await fetch(`/api/v1/tasks/${taskId}/dependencies/${dependsOnTaskId}`, {
            method: 'DELETE'
        });

        if (!response.ok) {
            const errorData = await safeJson(response);
            showToast(errorData?.error || 'Bağımlılık kaldırılamadı', 'error');
            return;
        }

        showToast('Bağımlılık kaldırıldı', 'success');
        await Promise.all([loadTaskDetails(Number(taskId)), loadTasks()]);
    } catch (error) {
        console.error('Remove dependency error:', error);
        showToast('Bağımlılık kaldırma hatası', 'error');
    }
}

async function loadComments(taskId) {
    try {
        const response = await fetch(`/api/v1/tasks/${taskId}/comments`);
        if (!response.ok) {
            renderComments([]);
            return;
        }

        const data = await response.json();
        renderComments(data.comments || []);
    } catch (error) {
        console.error('Load comments error:', error);
        renderComments([]);
    }
}

function renderComments(comments) {
    const list = document.getElementById('comments-list');

    if (comments.length === 0) {
        list.innerHTML = '<div class="text-xs text-slate-500">Henüz yorum yok.</div>';
        return;
    }

    list.innerHTML = comments.map(comment => `
        <div class="px-3 py-2 bg-slate-50 border border-slate-200 rounded-xl group">
            <div class="flex items-center justify-between gap-2 mb-1">
                <span class="text-xs font-semibold text-slate-700">Kullanıcı #${comment.user_id}</span>
                <div class="flex items-center gap-2">
                    <span class="text-[11px] text-slate-500">${formatDateTime(comment.created_at)}</span>
                    <button onclick="deleteComment(${comment.id})" class="opacity-0 group-hover:opacity-100 text-rose-500 hover:text-rose-700 transition-opacity" title="Sil">
                        <i class="fas fa-trash text-xs"></i>
                    </button>
                </div>
            </div>
            <p class="text-xs text-slate-600">${escapeHtml(comment.content)}</p>
        </div>
    `).join('');
}

async function addComment() {
    const taskId = document.getElementById('task-id').value;
    const input = document.getElementById('comment-input');
    const content = input.value.trim();

    if (!taskId || !content) {
        return;
    }

    try {
        const response = await fetch(`/api/v1/tasks/${taskId}/comments`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ content })
        });

        if (!response.ok) {
            const errorData = await safeJson(response);
            showToast(errorData?.error || 'Yorum eklenemedi', 'error');
            return;
        }

        input.value = '';
        showToast('Yorum eklendi', 'success');
        await loadComments(Number(taskId));
    } catch (error) {
        console.error('Add comment error:', error);
        showToast('Yorum eklenirken hata oluştu', 'error');
    }
}

async function loadAttachments(taskId) {
    try {
        const response = await fetch(`/api/v1/tasks/${taskId}/attachments`);
        if (!response.ok) {
            renderAttachments([]);
            return;
        }

        const data = await response.json();
        renderAttachments(data.attachments || []);
    } catch (error) {
        console.error('Load attachments error:', error);
        renderAttachments([]);
    }
}

function renderAttachments(attachments) {
    const list = document.getElementById('attachments-list');

    if (attachments.length === 0) {
        list.innerHTML = '<div class="text-xs text-slate-500">Henüz dosya yüklenmemiş.</div>';
        return;
    }

    const taskId = document.getElementById('task-id').value;
    list.innerHTML = attachments.map(attachment => `
        <div class="flex items-center justify-between gap-2 px-3 py-2 bg-slate-50 border border-slate-200 rounded-xl text-xs group">
            <div class="min-w-0 flex-1">
                <p class="font-semibold text-slate-700 truncate">${escapeHtml(attachment.file_name)}</p>
                <p class="text-slate-500">${formatFileSize(attachment.file_size)} • ${formatDateTime(attachment.created_at)}</p>
            </div>
            <div class="flex items-center gap-2">
                <a href="/api/v1/tasks/attachments/${attachment.id}/download" class="text-brand-600 hover:text-brand-700 font-semibold" target="_blank" rel="noopener noreferrer">İndir</a>
                <button onclick="deleteAttachment(${attachment.id})" class="opacity-0 group-hover:opacity-100 text-rose-500 hover:text-rose-700 transition-opacity" title="Sil">
                    <i class="fas fa-trash text-xs"></i>
                </button>
            </div>
        </div>
    `).join('');
}

async function uploadAttachment() {
    const taskId = document.getElementById('task-id').value;
    const fileInput = document.getElementById('attachment-file');
    const file = fileInput.files[0];

    if (!taskId || !file) {
        showToast('Yüklenecek dosya seç', 'error');
        return;
    }

    const formData = new FormData();
    formData.append('file', file);

    try {
        const response = await fetch(`/api/v1/tasks/${taskId}/attachments`, {
            method: 'POST',
            body: formData
        });

        if (!response.ok) {
            const errorData = await safeJson(response);
            showToast(errorData?.error || 'Dosya yüklenemedi', 'error');
            return;
        }

        fileInput.value = '';
        showToast('Dosya yüklendi', 'success');
        await loadAttachments(Number(taskId));
    } catch (error) {
        console.error('Upload attachment error:', error);
        showToast('Dosya yükleme hatası', 'error');
    }
}

function openMilestoneModal() {
    const modal = document.getElementById('milestoneModal');
    modal.classList.remove('hidden');
    modal.classList.add('flex');
    document.getElementById('milestoneForm').reset();
}

function closeMilestoneModal() {
    const modal = document.getElementById('milestoneModal');
    modal.classList.add('hidden');
    modal.classList.remove('flex');
}

async function saveMilestone(event) {
    event.preventDefault();

    const payload = {
        name: document.getElementById('milestone-name').value.trim()
    };

    const dueDate = document.getElementById('milestone-due-date').value;
    if (dueDate) {
        payload.due_date = new Date(dueDate).toISOString();
    }

    try {
        const response = await fetch('/api/v1/milestones', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(payload)
        });

        if (!response.ok) {
            const errorData = await safeJson(response);
            showToast(errorData?.error || 'Milestone kaydedilemedi', 'error');
            return;
        }

        closeMilestoneModal();
        await loadMilestones();
        showToast('Milestone oluşturuldu', 'success');
    } catch (error) {
        console.error('Save milestone error:', error);
        showToast('Milestone kaydı sırasında hata oluştu', 'error');
    }
}

function statusBadgeClass(status) {
    if (status === 'completed') return 'bg-emerald-100 text-emerald-700';
    if (status === 'in_progress') return 'bg-blue-100 text-blue-700';
    if (status === 'blocked') return 'bg-rose-100 text-rose-700';
    if (status === 'cancelled') return 'bg-slate-200 text-slate-600';
    return 'bg-slate-100 text-slate-700';
}

function priorityBorderClass(priority) {
    if (priority === 'urgent') return 'border-rose-300';
    if (priority === 'high') return 'border-amber-300';
    if (priority === 'low') return 'border-emerald-300';
    return 'border-slate-200';
}

function formatStatus(status) {
    return (status || 'not_started').replaceAll('_', ' ');
}

function formatDate(value) {
    return new Date(value).toLocaleDateString('tr-TR', {
        day: '2-digit',
        month: 'short',
        year: 'numeric'
    });
}

function formatDateTime(value) {
    return new Date(value).toLocaleString('tr-TR', {
        day: '2-digit',
        month: 'short',
        year: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
    });
}

function toDateTimeLocal(value) {
    const date = new Date(value);
    const timezoneOffset = date.getTimezoneOffset() * 60000;
    return new Date(date.getTime() - timezoneOffset).toISOString().slice(0, 16);
}

function formatFileSize(bytes) {
    if (!bytes) {
        return '0 B';
    }

    const units = ['B', 'KB', 'MB', 'GB'];
    const index = Math.min(Math.floor(Math.log(bytes) / Math.log(1024)), units.length - 1);
    const value = bytes / (1024 ** index);
    return `${value.toFixed(index === 0 ? 0 : 1)} ${units[index]}`;
}

function showToast(message, type = 'success') {
    const container = document.getElementById('toastContainer');
    const toast = document.createElement('div');

    const colorClass = type === 'error'
        ? 'bg-rose-50 border-rose-200 text-rose-700'
        : 'bg-emerald-50 border-emerald-200 text-emerald-700';

    toast.className = `px-4 py-3 rounded-xl border shadow-sm text-sm font-medium ${colorClass}`;
    toast.textContent = message;

    container.appendChild(toast);
    setTimeout(() => {
        toast.remove();
    }, 2600);
}

function escapeHtml(value) {
    if (value === null || value === undefined) {
        return '';
    }

    return String(value)
        .replaceAll('&', '&amp;')
        .replaceAll('<', '&lt;')
        .replaceAll('>', '&gt;')
        .replaceAll('"', '&quot;')
        .replaceAll("'", '&#39;');
}

async function safeJson(response) {
    try {
        return await response.json();
    } catch (error) {
        return null;
    }
}


// Delete comment
async function deleteComment(commentId) {
    if (!confirm('Bu yorumu silmek istediğinizden emin misiniz?')) {
        return;
    }

    try {
        const response = await fetch(`/api/v1/tasks/comments/${commentId}`, {
            method: 'DELETE'
        });

        if (!response.ok) {
            const errorData = await safeJson(response);
            showToast(errorData?.error || 'Yorum silinemedi', 'error');
            return;
        }

        const taskId = document.getElementById('task-id').value;
        showToast('Yorum silindi', 'success');
        await loadComments(Number(taskId));
    } catch (error) {
        console.error('Delete comment error:', error);
        showToast('Yorum silinirken hata oluştu', 'error');
    }
}

// Delete attachment
async function deleteAttachment(attachmentId) {
    if (!confirm('Bu dosyayı silmek istediğinizden emin misiniz?')) {
        return;
    }

    try {
        const response = await fetch(`/api/v1/tasks/attachments/${attachmentId}`, {
            method: 'DELETE'
        });

        if (!response.ok) {
            const errorData = await safeJson(response);
            showToast(errorData?.error || 'Dosya silinemedi', 'error');
            return;
        }

        const taskId = document.getElementById('task-id').value;
        showToast('Dosya silindi', 'success');
        await loadAttachments(Number(taskId));
    } catch (error) {
        console.error('Delete attachment error:', error);
        showToast('Dosya silinirken hata oluştu', 'error');
    }
}
