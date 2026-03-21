/**
 * Dashboard.js - Gerçek zamanlı CRM Dashboard
 * Tüm API'larla entegre, canlı veri gösterimi
 */

class Dashboard {
    constructor() {
        this.refreshInterval = null;
        this.init();
    }

    async init() {
        console.log('Dashboard initializing...');
        await this.loadAllData();
        this.setupEventListeners();
        this.startAutoRefresh();
    }

    async loadAllData() {
        try {
            await Promise.all([
                this.loadStats(),
                this.loadPipelineData(),
                this.loadRecentContacts(),
                this.loadRecentDeals(),
                this.loadUpcomingTasks(),
                this.loadRecentActivities()
            ]);
        } catch (error) {
            console.error('Error loading dashboard data:', error);
            this.showError('Veri yüklenirken hata oluştu');
        }
    }

    async loadStats() {
        try {
            // Kişi sayısı
            const contactsRes = await fetch('/api/v1/contacts?per_page=1');
            if (contactsRes.ok) {
                const contactsData = await contactsRes.json();
                const totalContacts = contactsData.pagination?.total || 0;
                this.updateStatCard('total-contacts', totalContacts.toLocaleString('tr-TR'));
            }

            // Aktif anlaşmalar
            const dealsRes = await fetch('/api/v1/deals?status=open&per_page=1');
            if (dealsRes.ok) {
                const dealsData = await dealsRes.json();
                const activeDeals = dealsData.pagination?.total || 0;
                this.updateStatCard('active-deals', activeDeals.toLocaleString('tr-TR'));
            }

            // Pipeline analytics
            const analyticsRes = await fetch('/api/v1/deals/analytics');
            if (analyticsRes.ok) {
                const analyticsData = await analyticsRes.json();
                const totalValue = analyticsData.total_value || 0;
                this.updateStatCard('total-revenue', this.formatCurrency(totalValue));
            }

            // Bekleyen görevler
            const tasksRes = await fetch('/api/v1/tasks?status=not_started,in_progress&per_page=1');
            if (tasksRes.ok) {
                const tasksData = await tasksRes.json();
                const pendingTasks = tasksData.pagination?.total || 0;
                this.updateStatCard('pending-tasks', pendingTasks.toLocaleString('tr-TR'));
            }

        } catch (error) {
            console.error('Error loading stats:', error);
        }
    }

    async loadPipelineData() {
        try {
            const response = await fetch('/api/v1/pipelines');
            const pipelines = await response.json();
            
            if (pipelines && pipelines.length > 0) {
                const defaultPipeline = pipelines.find(p => p.is_default) || pipelines[0];
                await this.loadPipelineStages(defaultPipeline.id);
            }
        } catch (error) {
            console.error('Error loading pipeline data:', error);
        }
    }

    async loadPipelineStages(pipelineId) {
        try {
            const response = await fetch(`/api/v1/deals?pipeline_id=${pipelineId}&status=open`);
            const data = await response.json();
            const deals = data.deals || [];

            // Stage'lere göre grupla
            const stageGroups = {};
            deals.forEach(deal => {
                const stageName = deal.stage?.name || 'Diğer';
                if (!stageGroups[stageName]) {
                    stageGroups[stageName] = [];
                }
                stageGroups[stageName].push(deal);
            });

            this.renderPipelineStages(stageGroups);
        } catch (error) {
            console.error('Error loading pipeline stages:', error);
        }
    }

    renderPipelineStages(stageGroups) {
        const container = document.getElementById('pipeline-stages');
        if (!container) return;

        const stages = ['Keşif', 'Teklif', 'Müzakere', 'Kapanış'];
        const colors = ['#8b5cf6', '#0ea5e9', '#f59e0b', '#22c55e'];
        const colorClasses = ['brand', 'sky', 'amber', 'emerald'];
        
        let html = '';
        stages.forEach((stageName, index) => {
            const deals = stageGroups[stageName] || [];
            const count = deals.length;
            const percentage = Math.min((count / 50) * 100, 100);
            const color = colors[index];
            const colorClass = colorClasses[index];

            html += `
                <div>
                    <div class="flex justify-between text-xs mb-1.5">
                        <span class="text-dark-300 font-medium">${stageName}</span>
                        <span class="text-${colorClass}-400 font-bold">${count}</span>
                    </div>
                    <div class="h-2 bg-dark-700 rounded-full overflow-hidden">
                        <div class="h-full rounded-full" style="width:${percentage}%;background:linear-gradient(90deg,${color},${color}dd);"></div>
                    </div>
                </div>
            `;
        });

        if (html === '') {
            html = '<div class="text-center text-dark-500 text-xs py-4">Henüz anlaşma yok</div>';
        }

        container.innerHTML = html;
    }

    async loadRecentContacts() {
        try {
            const response = await fetch('/api/v1/contacts?per_page=10&sort_by=created_at&sort_order=desc');
            const data = await response.json();
            const contacts = data.contacts || [];

            this.renderContactsTable(contacts);
        } catch (error) {
            console.error('Error loading recent contacts:', error);
        }
    }

    renderContactsTable(contacts) {
        const tbody = document.getElementById('contacts-table-body');
        if (!tbody) return;

        if (contacts.length === 0) {
            tbody.innerHTML = '<tr><td colspan="8" class="px-4 py-8 text-center text-dark-400">Henüz kişi eklenmemiş</td></tr>';
            return;
        }

        tbody.innerHTML = contacts.map(contact => {
            const fullName = contact.full_name || contact.first_name || 'İsimsiz';
            const initials = this.getInitials(fullName);
            const statusClass = contact.lifecycle_stage === 'customer' ? 'emerald' : 
                               contact.lifecycle_stage === 'qualified_lead' ? 'sky' : 'amber';
            const statusText = contact.lifecycle_stage === 'customer' ? 'Müşteri' :
                              contact.lifecycle_stage === 'qualified_lead' ? 'Nitelikli' : 'Lead';

            return `
                <tr class="table-row cursor-pointer" onclick="window.location.href='/contacts/${contact.id}'">
                    <td class="px-4 py-3">
                        <input type="checkbox" class="w-3.5 h-3.5 rounded border-dark-500 bg-dark-700 text-brand-500" onclick="event.stopPropagation()">
                    </td>
                    <td class="px-4 py-3">
                        <div class="flex items-center gap-3">
                            <div class="w-8 h-8 rounded-lg flex items-center justify-center text-xs font-bold text-white flex-shrink-0" style="background:linear-gradient(135deg,#8b5cf6,#6d28d9);">
                                ${initials}
                            </div>
                            <div>
                                <div class="text-sm font-semibold text-dark-100">${this.escapeHtml(fullName)}</div>
                                <div class="text-[11px] text-dark-400">${this.escapeHtml(contact.job_title || '-')}</div>
                            </div>
                        </div>
                    </td>
                    <td class="px-4 py-3"><span class="text-sm text-dark-300">${this.escapeHtml(contact.company_name || '-')}</span></td>
                    <td class="px-4 py-3"><span class="text-sm text-dark-400">${this.escapeHtml(contact.email || '-')}</span></td>
                    <td class="px-4 py-3">
                        <div class="flex items-center gap-2">
                            <span class="text-sm font-bold text-brand-300">${contact.lead_score || 0}</span>
                            <div class="w-12 h-1.5 bg-dark-700 rounded-full overflow-hidden">
                                <div class="h-full rounded-full" style="width:${Math.min(contact.lead_score || 0, 100)}%;background:linear-gradient(90deg,#8b5cf6,#a78bfa);"></div>
                            </div>
                        </div>
                    </td>
                    <td class="px-4 py-3">
                        <span class="pill-neon text-[10px] font-bold px-2.5 py-1 rounded-full bg-${statusClass}-500/10 text-${statusClass}-400 border-${statusClass}-500/20">
                            <i class="fas fa-circle text-[5px] mr-1"></i>${statusText}
                        </span>
                    </td>
                    <td class="px-4 py-3"><span class="text-xs text-dark-400">${this.timeAgo(contact.updated_at || contact.created_at)}</span></td>
                    <td class="px-4 py-3">
                        <button class="w-7 h-7 flex items-center justify-center text-dark-400 hover:text-dark-200 hover:bg-dark-700/50 rounded-lg transition-all" onclick="event.stopPropagation()">
                            <i class="fas fa-ellipsis-v text-xs"></i>
                        </button>
                    </td>
                </tr>
            `;
        }).join('');
    }

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }

    async loadRecentDeals() {
        try {
            const response = await fetch('/api/v1/deals?status=open&per_page=5&sort_by=created_at&sort_order=desc');
            const data = await response.json();
            const deals = data.deals || [];

            // Deals listesini göster (eğer UI'da yer varsa)
            console.log('Recent deals loaded:', deals.length);
        } catch (error) {
            console.error('Error loading recent deals:', error);
        }
    }

    async loadTasks() {
        try {
            const response = await fetch('/api/v1/tasks?status=not_started,in_progress&per_page=5');
            const data = await response.json();
            const tasks = data.tasks || [];

            console.log('Tasks loaded:', tasks.length);
        } catch (error) {
            console.error('Error loading tasks:', error);
        }
    }

    async loadUpcomingTasks() {
        try {
            // Yaklaşan görevleri çek (start_time'a göre sıralı, gelecek tarihli)
            const now = new Date().toISOString();
            const response = await fetch(`/api/v1/tasks?per_page=5&sort_by=start_time&sort_order=asc`);
            
            if (!response.ok) {
                throw new Error('Tasks API failed');
            }

            const data = await response.json();
            const tasks = data.tasks || [];

            // Sadece gelecek tarihli görevleri filtrele
            const upcomingTasks = tasks.filter(task => {
                if (!task.start_time) return false;
                return new Date(task.start_time) >= new Date();
            }).slice(0, 5);

            this.renderUpcomingTasks(upcomingTasks);
        } catch (error) {
            console.error('Error loading upcoming tasks:', error);
            const container = document.getElementById('upcoming-tasks');
            if (container) {
                container.innerHTML = '<div class="text-center text-dark-500 text-xs py-4">Görev yüklenemedi</div>';
            }
        }
    }

    renderUpcomingTasks(tasks) {
        const container = document.getElementById('upcoming-tasks');
        if (!container) return;

        if (tasks.length === 0) {
            container.innerHTML = '<div class="text-center text-dark-500 text-xs py-4">Yaklaşan görev yok</div>';
            return;
        }

        container.innerHTML = tasks.map(task => {
            const isOverdue = task.start_time && new Date(task.start_time) < new Date();
            const priorityEmoji = {
                'urgent': '🔴',
                'high': '🟠',
                'medium': '🟡',
                'low': '🔵'
            }[task.priority] || '🟡';

            const priorityColor = {
                'urgent': 'red',
                'high': 'amber',
                'medium': 'brand',
                'low': 'sky'
            }[task.priority] || 'brand';

            const timeText = task.start_time ? this.formatTaskTime(task.start_time) : 'Tarih yok';
            const statusText = isOverdue ? 'Gecikmiş' : this.getTaskDaysUntil(task.start_time);

            const borderColor = isOverdue ? 'red-500/20' : `${priorityColor}-500/20`;
            const bgColor = isOverdue ? 'red-500/5' : `${priorityColor}-500/5`;
            const hoverBg = isOverdue ? 'red-500/10' : `${priorityColor}-500/10`;

            return `
                <div class="flex items-center gap-3 p-3 rounded-xl border border-${borderColor} bg-${bgColor} hover:bg-${hoverBg} transition-all cursor-pointer" onclick="window.location.href='/tasks/${task.id}'">
                    <div class="w-5 h-5 rounded-md border-2 border-${priorityColor}-400/50 flex items-center justify-center flex-shrink-0">
                        ${task.status === 'completed' ? '<i class="fas fa-check text-emerald-400 text-[8px]"></i>' : ''}
                    </div>
                    <div class="flex-1 min-w-0">
                        <p class="text-xs font-semibold text-dark-100 ${task.status === 'completed' ? 'line-through text-dark-400' : ''}">${this.escapeHtml(task.title)}</p>
                        <span class="text-[10px] text-${priorityColor}-400 font-medium">${priorityEmoji} ${this.getPriorityText(task.priority)} · ${timeText}</span>
                    </div>
                    <span class="text-[10px] text-${priorityColor}-400 bg-${priorityColor}-500/10 px-2 py-0.5 rounded-full font-bold">${statusText}</span>
                </div>
            `;
        }).join('');
    }

    async loadRecentActivities() {
        try {
            // Son aktiviteleri çek - contacts API'den son güncellemeleri al
            const response = await fetch('/api/v1/contacts?per_page=5&sort_by=updated_at&sort_order=desc');
            
            if (!response.ok) {
                throw new Error('Activities API failed');
            }

            const data = await response.json();
            const contacts = data.contacts || [];

            // Aktiviteleri oluştur
            const activities = contacts.map(contact => ({
                type: 'contact_updated',
                title: `${contact.full_name || contact.first_name}`,
                description: 'güncellendi',
                time: contact.updated_at || contact.created_at,
                icon: 'user-plus',
                color: 'brand'
            }));

            this.renderRecentActivities(activities);
        } catch (error) {
            console.error('Error loading recent activities:', error);
            const container = document.getElementById('recent-activities');
            if (container) {
                container.innerHTML = '<div class="text-center text-dark-500 text-xs py-4">Aktivite yüklenemedi</div>';
            }
        }
    }

    renderRecentActivities(activities) {
        const container = document.getElementById('recent-activities');
        if (!container) return;

        if (activities.length === 0) {
            container.innerHTML = '<div class="text-center text-dark-500 text-xs py-4">Henüz aktivite yok</div>';
            return;
        }

        const iconMap = {
            'message': 'fa-message',
            'handshake': 'fa-handshake',
            'envelope': 'fa-envelope',
            'user-plus': 'fa-user-plus',
            'phone': 'fa-phone',
            'calendar': 'fa-calendar'
        };

        const colorMap = {
            'emerald': 'emerald-500/10',
            'brand': 'brand-500/10',
            'sky': 'sky-500/10',
            'amber': 'amber-500/10'
        };

        container.innerHTML = activities.map(activity => {
            const icon = iconMap[activity.icon] || 'fa-circle';
            const bgColor = colorMap[activity.color] || 'brand-500/10';
            const textColor = `${activity.color}-400`;

            return `
                <div class="flex items-start gap-3 p-2.5 rounded-xl hover:bg-dark-700/30 transition-all cursor-pointer">
                    <div class="w-8 h-8 rounded-lg bg-${bgColor} flex items-center justify-center flex-shrink-0 mt-0.5">
                        <i class="fas ${icon} text-${textColor} text-xs"></i>
                    </div>
                    <div class="flex-1 min-w-0">
                        <p class="text-xs text-dark-200"><span class="font-semibold text-dark-100">${this.escapeHtml(activity.title)}</span> ${activity.description}</p>
                        <span class="text-[10px] text-dark-500 mt-0.5 block">${this.timeAgo(activity.time)}</span>
                    </div>
                </div>
            `;
        }).join('');
    }

    formatTaskTime(dateString) {
        if (!dateString) return '';
        const date = new Date(dateString);
        const today = new Date();
        const tomorrow = new Date(today);
        tomorrow.setDate(tomorrow.getDate() + 1);

        if (date.toDateString() === today.toDateString()) {
            return `Bugün ${date.toLocaleTimeString('tr-TR', { hour: '2-digit', minute: '2-digit' })}`;
        } else if (date.toDateString() === tomorrow.toDateString()) {
            return `Yarın ${date.toLocaleTimeString('tr-TR', { hour: '2-digit', minute: '2-digit' })}`;
        } else {
            return date.toLocaleDateString('tr-TR', { day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' });
        }
    }

    getTaskDaysUntil(dateString) {
        if (!dateString) return '';
        const date = new Date(dateString);
        const now = new Date();
        const diffTime = date - now;
        const diffDays = Math.ceil(diffTime / (1000 * 60 * 60 * 24));

        if (diffDays < 0) return 'Gecikmiş';
        if (diffDays === 0) return 'Bugün';
        if (diffDays === 1) return 'Yarın';
        return `${diffDays} gün`;
    }

    getPriorityText(priority) {
        const map = {
            'urgent': 'Acil',
            'high': 'Yüksek',
            'medium': 'Orta',
            'low': 'Düşük'
        };
        return map[priority] || 'Orta';
    }

    updateStatCard(id, value) {
        const element = document.getElementById(id);
        if (element) {
            element.textContent = value;
        }
    }

    formatCurrency(value) {
        if (value >= 1000000) {
            return `₺${(value / 1000000).toFixed(1)}M`;
        } else if (value >= 1000) {
            return `₺${(value / 1000).toFixed(0)}K`;
        }
        return `₺${value.toFixed(0)}`;
    }

    getInitials(name) {
        if (!name) return '?';
        const parts = name.split(' ');
        if (parts.length >= 2) {
            return (parts[0][0] + parts[1][0]).toUpperCase();
        }
        return name.substring(0, 2).toUpperCase();
    }

    timeAgo(dateString) {
        if (!dateString) return '-';
        const date = new Date(dateString);
        const now = new Date();
        const seconds = Math.floor((now - date) / 1000);

        if (seconds < 60) return 'Az önce';
        if (seconds < 3600) return `${Math.floor(seconds / 60)} dakika önce`;
        if (seconds < 86400) return `${Math.floor(seconds / 3600)} saat önce`;
        if (seconds < 604800) return `${Math.floor(seconds / 86400)} gün önce`;
        return date.toLocaleDateString('tr-TR');
    }

    setupEventListeners() {
        // Yenile butonu
        const refreshBtn = document.getElementById('refresh-dashboard');
        if (refreshBtn) {
            refreshBtn.addEventListener('click', () => this.loadAllData());
        }

        // Dışa aktar butonu
        const exportBtn = document.getElementById('export-dashboard');
        if (exportBtn) {
            exportBtn.addEventListener('click', () => this.exportData());
        }

        // Yeni kişi butonu
        const newContactBtn = document.getElementById('new-contact-btn');
        if (newContactBtn) {
            newContactBtn.addEventListener('click', () => {
                window.location.href = '/contacts?action=new';
            });
        }
    }

    startAutoRefresh() {
        // Her 30 saniyede bir otomatik yenile
        this.refreshInterval = setInterval(() => {
            this.loadStats();
        }, 30000);
    }

    stopAutoRefresh() {
        if (this.refreshInterval) {
            clearInterval(this.refreshInterval);
        }
    }

    async exportData() {
        try {
            const response = await fetch('/api/v1/contacts?per_page=1000');
            const data = await response.json();
            
            // CSV formatında indir
            const csv = this.convertToCSV(data.contacts || []);
            const blob = new Blob([csv], { type: 'text/csv' });
            const url = window.URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = `dashboard-export-${new Date().toISOString().split('T')[0]}.csv`;
            a.click();
            window.URL.revokeObjectURL(url);
        } catch (error) {
            console.error('Error exporting data:', error);
            this.showError('Dışa aktarma başarısız');
        }
    }

    convertToCSV(data) {
        if (data.length === 0) return '';
        
        const headers = ['Ad', 'Şirket', 'E-posta', 'Telefon', 'Lead Skor', 'Durum'];
        const rows = data.map(contact => [
            contact.full_name || contact.first_name,
            contact.company_name || '',
            contact.email || '',
            contact.phone || '',
            contact.lead_score || 0,
            contact.lifecycle_stage || ''
        ]);

        return [headers, ...rows].map(row => row.join(',')).join('\n');
    }

    showError(message) {
        // Basit hata gösterimi (toast notification eklenebilir)
        console.error(message);
        alert(message);
    }
}

// Dashboard'u başlat
document.addEventListener('DOMContentLoaded', () => {
    window.dashboard = new Dashboard();
});
