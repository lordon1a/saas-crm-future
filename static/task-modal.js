/**
 * TaskModal - Görev oluşturma ve düzenleme modalı
 * WhatsApp CRM SaaS - Calendar & Task Management
 */

class TaskModal {
    constructor() {
        this.modal = null;
        this.taskId = null;
        this.mode = 'create'; // create, edit
    }

    /**
     * Modal'ı başlat - HTML oluştur ve event listener'ları ekle
     */
    init() {
        this.createModalHTML();
        this.attachEventListeners();
        this.loadDropdownData();
    }

    /**
     * Modal HTML yapısını oluştur
     */
    createModalHTML() {
        const modalHTML = `
            <div id="taskModal" class="fixed inset-0 bg-slate-900/50 backdrop-blur-sm z-50 hidden flex items-center justify-center p-4">
                <div class="bg-white rounded-2xl shadow-2xl w-full max-w-2xl max-h-[90vh] overflow-hidden flex flex-col">
                    <!-- Header -->
                    <div class="flex items-center justify-between px-6 py-4 border-b border-slate-200">
                        <h2 id="taskModalTitle" class="text-xl font-bold text-slate-800">Yeni Görev</h2>
                        <button id="closeTaskModal" class="w-8 h-8 rounded-lg hover:bg-slate-100 flex items-center justify-center text-slate-400 hover:text-slate-600 transition-colors">
                            <i class="fas fa-times"></i>
                        </button>
                    </div>

                    <!-- Body -->
                    <div class="flex-1 overflow-y-auto px-6 py-4">
                        <form id="taskForm" class="space-y-4">
                            <!-- Başlık -->
                            <div>
                                <label for="task-title" class="block text-sm font-semibold text-slate-700 mb-2">
                                    Görev Başlığı <span class="text-red-500">*</span>
                                </label>
                                <input 
                                    type="text" 
                                    id="task-title" 
                                    class="w-full px-4 py-2.5 border border-slate-200 rounded-xl focus:ring-2 focus:ring-brand-500 focus:border-transparent transition-all"
                                    placeholder="Örn: Müşteri Araması"
                                    required
                                />
                            </div>

                            <!-- Açıklama -->
                            <div>
                                <label for="task-description" class="block text-sm font-semibold text-slate-700 mb-2">
                                    Açıklama
                                </label>
                                <textarea 
                                    id="task-description" 
                                    rows="3"
                                    class="w-full px-4 py-2.5 border border-slate-200 rounded-xl focus:ring-2 focus:ring-brand-500 focus:border-transparent transition-all resize-none"
                                    placeholder="Görev detayları..."
                                ></textarea>
                            </div>

                            <!-- Görev Tipi ve Öncelik -->
                            <div class="grid grid-cols-2 gap-4">
                                <div>
                                    <label for="task-type" class="block text-sm font-semibold text-slate-700 mb-2">
                                        Görev Tipi
                                    </label>
                                    <select 
                                        id="task-type" 
                                        class="w-full px-4 py-2.5 border border-slate-200 rounded-xl focus:ring-2 focus:ring-brand-500 focus:border-transparent transition-all"
                                    >
                                        <option value="task">📋 Görev</option>
                                        <option value="call">📞 Arama</option>
                                        <option value="meeting">👥 Toplantı</option>
                                        <option value="email">📧 Email</option>
                                        <option value="follow_up">🔄 Takip</option>
                                        <option value="other">📝 Diğer</option>
                                    </select>
                                </div>

                                <div>
                                    <label for="task-priority" class="block text-sm font-semibold text-slate-700 mb-2">
                                        Öncelik
                                    </label>
                                    <select 
                                        id="task-priority" 
                                        class="w-full px-4 py-2.5 border border-slate-200 rounded-xl focus:ring-2 focus:ring-brand-500 focus:border-transparent transition-all"
                                    >
                                        <option value="low">🟢 Düşük</option>
                                        <option value="medium" selected>🟡 Orta</option>
                                        <option value="high">🔴 Yüksek</option>
                                    </select>
                                </div>
                            </div>

                            <!-- Başlangıç ve Bitiş Zamanı -->
                            <div class="grid grid-cols-2 gap-4">
                                <div>
                                    <label for="task-start-time" class="block text-sm font-semibold text-slate-700 mb-2">
                                        Başlangıç Zamanı
                                    </label>
                                    <input 
                                        type="datetime-local" 
                                        id="task-start-time" 
                                        class="w-full px-4 py-2.5 border border-slate-200 rounded-xl focus:ring-2 focus:ring-brand-500 focus:border-transparent transition-all"
                                    />
                                </div>

                                <div>
                                    <label for="task-end-time" class="block text-sm font-semibold text-slate-700 mb-2">
                                        Bitiş Zamanı
                                    </label>
                                    <input 
                                        type="datetime-local" 
                                        id="task-end-time" 
                                        class="w-full px-4 py-2.5 border border-slate-200 rounded-xl focus:ring-2 focus:ring-brand-500 focus:border-transparent transition-all"
                                    />
                                </div>
                            </div>

                            <!-- İlişkili Kayıtlar -->
                            <div class="grid grid-cols-3 gap-4">
                                <div>
                                    <label for="task-contact" class="block text-sm font-semibold text-slate-700 mb-2">
                                        Kişi
                                    </label>
                                    <select 
                                        id="task-contact" 
                                        class="w-full px-4 py-2.5 border border-slate-200 rounded-xl focus:ring-2 focus:ring-brand-500 focus:border-transparent transition-all"
                                    >
                                        <option value="">Seçiniz...</option>
                                    </select>
                                </div>

                                <div>
                                    <label for="task-company" class="block text-sm font-semibold text-slate-700 mb-2">
                                        Şirket
                                    </label>
                                    <select 
                                        id="task-company" 
                                        class="w-full px-4 py-2.5 border border-slate-200 rounded-xl focus:ring-2 focus:ring-brand-500 focus:border-transparent transition-all"
                                    >
                                        <option value="">Seçiniz...</option>
                                    </select>
                                </div>

                                <div>
                                    <label for="task-deal" class="block text-sm font-semibold text-slate-700 mb-2">
                                        Fırsat
                                    </label>
                                    <select 
                                        id="task-deal" 
                                        class="w-full px-4 py-2.5 border border-slate-200 rounded-xl focus:ring-2 focus:ring-brand-500 focus:border-transparent transition-all"
                                    >
                                        <option value="">Seçiniz...</option>
                                    </select>
                                </div>
                            </div>

                            <!-- Atanan Kişi -->
                            <div>
                                <label for="task-assignee" class="block text-sm font-semibold text-slate-700 mb-2">
                                    Atanan Kişi
                                </label>
                                <select 
                                    id="task-assignee" 
                                    class="w-full px-4 py-2.5 border border-slate-200 rounded-xl focus:ring-2 focus:ring-brand-500 focus:border-transparent transition-all"
                                >
                                    <option value="">Seçiniz...</option>
                                </select>
                            </div>
                        </form>
                    </div>

                    <!-- Footer -->
                    <div class="flex items-center justify-between px-6 py-4 border-t border-slate-200 bg-slate-50">
                        <button 
                            id="deleteTaskBtn" 
                            type="button"
                            class="px-5 py-2.5 rounded-xl font-semibold text-red-600 hover:bg-red-50 transition-colors hidden"
                        >
                            <i class="fas fa-trash mr-2"></i>Sil
                        </button>
                        <div class="flex items-center gap-3">
                            <button 
                                id="cancelTaskBtn" 
                                type="button"
                                class="px-5 py-2.5 rounded-xl font-semibold text-slate-600 hover:bg-slate-200 transition-colors"
                            >
                                İptal
                            </button>
                            <button 
                                id="saveTaskBtn" 
                                type="button"
                                class="px-5 py-2.5 rounded-xl font-semibold text-white bg-brand-500 hover:bg-brand-600 shadow-sm hover:shadow-md transition-all"
                            >
                                Kaydet
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        `;

        // Modal'ı body'ye ekle
        document.body.insertAdjacentHTML('beforeend', modalHTML);
        this.modal = document.getElementById('taskModal');
    }

    /**
     * Event listener'ları ekle
     */
    attachEventListeners() {
        // Kapat butonları
        document.getElementById('closeTaskModal').addEventListener('click', () => this.close());
        document.getElementById('cancelTaskBtn').addEventListener('click', () => this.close());

        // Kaydet butonu
        document.getElementById('saveTaskBtn').addEventListener('click', () => this.save());

        // Sil butonu
        document.getElementById('deleteTaskBtn').addEventListener('click', () => this.delete());

        // Modal dışına tıklama
        this.modal.addEventListener('click', (e) => {
            if (e.target === this.modal) {
                this.close();
            }
        });

        // ESC tuşu ile kapat
        document.addEventListener('keydown', (e) => {
            if (e.key === 'Escape' && !this.modal.classList.contains('hidden')) {
                this.close();
            }
        });
    }

    /**
     * Dropdown verilerini yükle (contacts, companies, deals, assignees)
     */
    async loadDropdownData() {
        try {
            // Load contacts
            const contactsRes = await fetch('/api/v1/contacts?per_page=1000');
            if (contactsRes.ok) {
                const contactsData = await contactsRes.json();
                const contactSelect = document.getElementById('task-contact');
                contactSelect.innerHTML = '<option value="">Seçiniz...</option>';
                contactsData.contacts.forEach(contact => {
                    contactSelect.innerHTML += `<option value="${contact.id}">${contact.name}</option>`;
                });
            }

            // Load companies
            const companiesRes = await fetch('/api/v1/companies?per_page=1000');
            if (companiesRes.ok) {
                const companiesData = await companiesRes.json();
                const companySelect = document.getElementById('task-company');
                companySelect.innerHTML = '<option value="">Seçiniz...</option>';
                companiesData.companies.forEach(company => {
                    companySelect.innerHTML += `<option value="${company.id}">${company.name}</option>`;
                });
            }

            // Load deals
            const dealsRes = await fetch('/api/v1/deals?per_page=1000');
            if (dealsRes.ok) {
                const dealsData = await dealsRes.json();
                const dealSelect = document.getElementById('task-deal');
                dealSelect.innerHTML = '<option value="">Seçiniz...</option>';
                dealsData.deals.forEach(deal => {
                    dealSelect.innerHTML += `<option value="${deal.id}">${deal.title}</option>`;
                });
            }

            // Load team members (assignees)
            const teamRes = await fetch('/api/team/members');
            if (teamRes.ok) {
                const teamData = await teamRes.json();
                const assigneeSelect = document.getElementById('task-assignee');
                assigneeSelect.innerHTML = '<option value="">Seçiniz...</option>';
                teamData.members.forEach(member => {
                    assigneeSelect.innerHTML += `<option value="${member.id}">${member.name}</option>`;
                });
            }

        } catch (error) {
            console.error('Error loading dropdown data:', error);
        }
    }

    /**
     * Modal'ı düzenleme modunda aç
     * @param {number} taskId - Görev ID
     */
    async open(taskId) {
        this.taskId = taskId;
        this.mode = 'edit';

        // Başlığı güncelle
        document.getElementById('taskModalTitle').textContent = 'Görevi Düzenle';
        
        // Delete butonunu göster
        document.getElementById('deleteTaskBtn').classList.remove('hidden');

        // Görev verilerini yükle
        await this.loadTask(taskId);

        // Modal'ı göster
        this.modal.classList.remove('hidden');
    }

    /**
     * Modal'ı yeni görev oluşturma modunda aç
     * @param {object} defaults - Varsayılan değerler (opsiyonel)
     */
    openNew(defaults = {}) {
        this.taskId = null;
        this.mode = 'create';

        // Başlığı güncelle
        document.getElementById('taskModalTitle').textContent = 'Yeni Görev';
        
        // Delete butonunu gizle (create mode'da gösterilmez)
        document.getElementById('deleteTaskBtn').classList.add('hidden');

        // Formu sıfırla
        this.resetForm();

        // Varsayılan değerleri doldur
        if (defaults.start_time) {
            document.getElementById('task-start-time').value = 
                this.formatDateTimeLocal(defaults.start_time);
        }
        if (defaults.end_time) {
            document.getElementById('task-end-time').value = 
                this.formatDateTimeLocal(defaults.end_time);
        }
        if (defaults.contact_id) {
            document.getElementById('task-contact').value = defaults.contact_id;
        }
        if (defaults.company_id) {
            document.getElementById('task-company').value = defaults.company_id;
        }
        if (defaults.deal_id) {
            document.getElementById('task-deal').value = defaults.deal_id;
        }

        // Modal'ı göster
        this.modal.classList.remove('hidden');
    }

    /**
     * Mevcut görev verilerini yükle
     * @param {number} taskId - Görev ID
     */
    async loadTask(taskId) {
        try {
            const response = await fetch(`/api/v1/tasks/${taskId}`);
            
            if (response.status === 401) {
                window.location.href = '/login';
                return;
            }

            if (!response.ok) {
                throw new Error('Görev yüklenemedi');
            }

            const task = await response.json();

            // Form alanlarını doldur
            document.getElementById('task-title').value = task.title || '';
            document.getElementById('task-description').value = task.description || '';
            document.getElementById('task-type').value = task.task_type || 'task';
            document.getElementById('task-priority').value = task.priority || 'medium';

            // Tarih/saat alanları - datetime-local formatına çevir
            if (task.start_time) {
                document.getElementById('task-start-time').value = 
                    this.formatDateTimeLocal(new Date(task.start_time));
            }
            if (task.end_time) {
                document.getElementById('task-end-time').value = 
                    this.formatDateTimeLocal(new Date(task.end_time));
            }

            // İlişkili kayıtlar
            if (task.contact_id) {
                document.getElementById('task-contact').value = task.contact_id;
            }
            if (task.company_id) {
                document.getElementById('task-company').value = task.company_id;
            }
            if (task.deal_id) {
                document.getElementById('task-deal').value = task.deal_id;
            }
            if (task.assignee_id) {
                document.getElementById('task-assignee').value = task.assignee_id;
            }

        } catch (error) {
            console.error('Error loading task:', error);
            this.showToast('Görev yüklenirken hata oluştu', 'error');
        }
    }

    /**
     * Formu kaydet (oluştur veya güncelle)
     */
    async save() {
        // Form validasyonu
        if (!this.validateForm()) {
            return;
        }

        // Form verilerini al
        const data = this.getFormData();

        try {
            const url = this.mode === 'create' 
                ? '/api/v1/tasks'
                : `/api/v1/tasks/${this.taskId}`;

            const method = this.mode === 'create' ? 'POST' : 'PATCH';

            const response = await fetch(url, {
                method: method,
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify(data)
            });

            if (response.status === 401) {
                window.location.href = '/login';
                return;
            }

            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.error || 'Bir hata oluştu');
            }

            // Başarılı
            this.close();
            
            // Takvimi yenile (eğer varsa)
            if (window.calendar && typeof window.calendar.loadEvents === 'function') {
                window.calendar.loadEvents();
            }

            // Toast göster
            this.showToast(
                this.mode === 'create' ? 'Görev oluşturuldu' : 'Görev güncellendi',
                'success'
            );

        } catch (error) {
            console.error('Error saving task:', error);
            this.showToast(error.message || 'Görev kaydedilirken hata oluştu', 'error');
        }
    }

    /**
     * Form validasyonu
     * @returns {boolean} - Geçerli ise true
     */
    validateForm() {
        const title = document.getElementById('task-title').value.trim();
        const startTime = document.getElementById('task-start-time').value;
        const endTime = document.getElementById('task-end-time').value;

        // Başlık kontrolü
        if (!title) {
            this.showToast('Görev başlığı zorunludur', 'error');
            document.getElementById('task-title').focus();
            return false;
        }

        // Zaman aralığı kontrolü
        if (startTime && endTime) {
            const start = new Date(startTime);
            const end = new Date(endTime);

            if (start >= end) {
                this.showToast('Bitiş zamanı başlangıç zamanından sonra olmalıdır', 'error');
                document.getElementById('task-end-time').focus();
                return false;
            }
        }

        return true;
    }

    /**
     * Form verilerini al
     * @returns {object} - Form verileri
     */
    getFormData() {
        const data = {
            title: document.getElementById('task-title').value.trim(),
            description: document.getElementById('task-description').value.trim(),
            task_type: document.getElementById('task-type').value,
            priority: document.getElementById('task-priority').value,
            timezone: Intl.DateTimeFormat().resolvedOptions().timeZone || 'UTC'
        };

        // Tarih/saat alanları - ISO formatına çevir
        const startTime = document.getElementById('task-start-time').value;
        const endTime = document.getElementById('task-end-time').value;

        if (startTime) {
            data.start_time = new Date(startTime).toISOString();
        }
        if (endTime) {
            data.end_time = new Date(endTime).toISOString();
        }

        // İlişkili kayıtlar (boş değilse ekle)
        const contactId = document.getElementById('task-contact').value;
        const companyId = document.getElementById('task-company').value;
        const dealId = document.getElementById('task-deal').value;
        const assigneeId = document.getElementById('task-assignee').value;

        if (contactId) data.contact_id = parseInt(contactId);
        if (companyId) data.company_id = parseInt(companyId);
        if (dealId) data.deal_id = parseInt(dealId);
        if (assigneeId) data.assignee_id = parseInt(assigneeId);

        return data;
    }

    /**
     * Formu sıfırla
     */
    resetForm() {
        document.getElementById('taskForm').reset();
        
        // Select alanlarını varsayılan değerlere döndür
        document.getElementById('task-type').value = 'task';
        document.getElementById('task-priority').value = 'medium';
        document.getElementById('task-contact').value = '';
        document.getElementById('task-company').value = '';
        document.getElementById('task-deal').value = '';
        document.getElementById('task-assignee').value = '';
    }

    /**
     * Modal'ı kapat
     */
    close() {
        this.modal.classList.add('hidden');
        this.resetForm();
        this.taskId = null;
        this.mode = 'create';
    }

    /**
     * Date objesini datetime-local input formatına çevir
     * @param {Date} date - Tarih objesi
     * @returns {string} - YYYY-MM-DDTHH:mm formatında string
     */
    formatDateTimeLocal(date) {
        if (!(date instanceof Date)) {
            date = new Date(date);
        }

        const year = date.getFullYear();
        const month = String(date.getMonth() + 1).padStart(2, '0');
        const day = String(date.getDate()).padStart(2, '0');
        const hours = String(date.getHours()).padStart(2, '0');
        const minutes = String(date.getMinutes()).padStart(2, '0');

        return `${year}-${month}-${day}T${hours}:${minutes}`;
    }

    /**
     * Görevi sil
     */
    async delete() {
        if (!this.taskId) {
            console.error('No task ID to delete');
            return;
        }

        // Onay iste
        if (!confirm('Bu görevi silmek istediğinizden emin misiniz?')) {
            return;
        }

        try {
            const response = await fetch(`/api/v1/tasks/${this.taskId}`, {
                method: 'DELETE'
            });

            if (response.status === 401) {
                window.location.href = '/login';
                return;
            }

            if (!response.ok) {
                const error = await response.json();
                throw new Error(error.error || 'Silme işlemi başarısız');
            }

            // Başarılı
            this.close();
            
            // Takvimi yenile (eğer varsa)
            if (window.calendar && typeof window.calendar.loadEvents === 'function') {
                window.calendar.loadEvents();
            }

            // Toast göster
            this.showToast('Görev silindi', 'success');

        } catch (error) {
            console.error('Error deleting task:', error);
            this.showToast(error.message || 'Görev silinirken hata oluştu', 'error');
        }
    }

    /**
     * HTML escape (XSS koruması)
     * @param {string} str - Escape edilecek string
     * @returns {string} - Escape edilmiş string
     */
    escapeHtml(str) {
        if (!str) return '';
        return String(str)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#039;');
    }

    /**
     * Toast bildirimi göster (app.js'deki showToast fonksiyonunu kullan)
     * @param {string} message - Mesaj
     * @param {string} type - Tip (success, error, info)
     */
    showToast(message, type = 'info') {
        // app.js'deki global showToast fonksiyonunu kullan
        if (typeof window.showToast === 'function') {
            window.showToast(message, type);
        } else {
            // Fallback: console'a yaz
            console.log(`[${type.toUpperCase()}] ${message}`);
        }
    }
}

// Global instance oluştur
window.taskModal = new TaskModal();

// Sayfa yüklendiğinde başlat
document.addEventListener('DOMContentLoaded', () => {
    window.taskModal.init();
});
