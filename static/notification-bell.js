// NotificationBell - Real-time notification system for task management
// Handles Socket.IO connection, notification display, and user interactions

class NotificationBell {
    constructor() {
        this.bellIcon = null;
        this.badge = null;
        this.dropdown = null;
        this.unreadCount = 0;
        this.socket = null;
        this.notificationSound = null;
    }

    /**
     * Initialize the notification bell
     * Creates HTML, attaches listeners, connects Socket.IO
     */
    init() {
        this.createBellHTML();
        this.attachEventListeners();
        this.connectSocket();
        this.loadNotifications();
    }

    /**
     * Create notification bell HTML structure
     * Inserts bell icon with badge and dropdown into topbar
     */
    createBellHTML() {
        const topbar = document.querySelector('.topbar') || document.querySelector('header');
        if (!topbar) {
            console.error('Topbar not found for notification bell');
            return;
        }

        // Create bell container
        const bellContainer = document.createElement('div');
        bellContainer.id = 'notification-bell-container';
        bellContainer.className = 'relative';
        bellContainer.innerHTML = `
            <button id="notification-bell" class="relative p-2 text-slate-600 hover:text-brand-600 hover:bg-slate-50 rounded-lg transition-all">
                <i class="fas fa-bell text-lg"></i>
                <span id="notification-badge" class="hidden absolute -top-1 -right-1 min-w-[20px] h-5 px-1.5 text-[11px] font-bold text-white bg-red-500 rounded-full flex items-center justify-center shadow-sm">0</span>
            </button>
            
            <!-- Notification Dropdown -->
            <div id="notification-dropdown" class="hidden absolute right-0 mt-2 w-96 bg-white rounded-xl shadow-lg border border-slate-200 z-50">
                <!-- Header -->
                <div class="flex items-center justify-between p-4 border-b border-slate-100">
                    <h3 class="text-sm font-bold text-slate-700">Bildirimler</h3>
                    <button id="mark-all-read-btn" class="text-xs text-brand-600 hover:text-brand-700 font-semibold">
                        Tümünü Okundu İşaretle
                    </button>
                </div>
                
                <!-- Notification List -->
                <div id="notification-list" class="max-h-96 overflow-y-auto">
                    <!-- Notifications will be rendered here -->
                </div>
                
                <!-- Footer -->
                <div class="p-3 border-t border-slate-100 text-center">
                    <a href="#" class="text-xs text-slate-500 hover:text-brand-600 font-medium">
                        Tüm Bildirimleri Görüntüle
                    </a>
                </div>
            </div>
        `;

        // Insert before user menu or at the end of topbar
        const userMenu = topbar.querySelector('.user-menu') || topbar.querySelector('[data-user-menu]');
        if (userMenu) {
            topbar.insertBefore(bellContainer, userMenu);
        } else {
            topbar.appendChild(bellContainer);
        }

        // Store references
        this.bellIcon = document.getElementById('notification-bell');
        this.badge = document.getElementById('notification-badge');
        this.dropdown = document.getElementById('notification-dropdown');
    }

    /**
     * Attach event listeners to bell and dropdown
     */
    attachEventListeners() {
        if (!this.bellIcon || !this.dropdown) return;

        // Toggle dropdown on bell click
        this.bellIcon.addEventListener('click', (e) => {
            e.stopPropagation();
            this.toggleDropdown();
        });

        // Mark all as read button
        const markAllBtn = document.getElementById('mark-all-read-btn');
        if (markAllBtn) {
            markAllBtn.addEventListener('click', () => this.markAllAsRead());
        }

        // Close dropdown when clicking outside
        document.addEventListener('click', (e) => {
            if (!this.dropdown.contains(e.target) && !this.bellIcon.contains(e.target)) {
                this.closeDropdown();
            }
        });
    }

    /**
     * Connect to Socket.IO server for real-time notifications
     * Uses gevent async_mode
     */
    connectSocket() {
        try {
            // Use existing Socket.IO connection if available
            if (window.socketClient) {
                this.socket = window.socketClient;
            } else {
                this.socket = io({
                    transports: ['websocket', 'polling'],
                    reconnection: true,
                    reconnectionDelay: 1000,
                    reconnectionAttempts: 5
                });
            }

            // Join user-specific room
            const userId = window.currentUserId || (window.session && window.session.user_id);
            if (userId) {
                this.socket.emit('join', { room: `user_${userId}` });
                console.log(`Joined notification room: user_${userId}`);
            }

            // Listen for new notifications
            this.socket.on('new_notification', (data) => {
                this.onNewNotification(data);
            });

            // Connection status
            this.socket.on('connect', () => {
                console.log('Notification socket connected');
            });

            this.socket.on('disconnect', () => {
                console.log('Notification socket disconnected');
            });

        } catch (error) {
            console.error('Socket.IO connection error:', error);
        }
    }

    /**
     * Handle new notification event from Socket.IO
     * @param {Object} notification - Notification data
     */
    onNewNotification(notification) {
        console.log('New notification received:', notification);

        // Increment unread count
        this.unreadCount++;
        this.updateBadge();

        // If dropdown is open, prepend to list
        if (!this.dropdown.classList.contains('hidden')) {
            this.prependNotificationToList(notification);
        }

        // Show toast notification
        if (typeof showToast === 'function') {
            showToast(notification.message, 'info');
        }

        // Play notification sound
        this.playNotificationSound();
    }

    /**
     * Load notifications from API
     */
    async loadNotifications() {
        try {
            const response = await fetch('/api/v1/notifications?limit=20');
            if (response.status === 401) {
                window.location.href = '/login';
                return;
            }

            if (!response.ok) {
                console.error('Failed to load notifications');
                return;
            }

            const data = await response.json();
            this.unreadCount = data.unread_count || 0;
            this.updateBadge();
            this.renderNotifications(data.notifications || []);

        } catch (error) {
            console.error('Error loading notifications:', error);
        }
    }

    /**
     * Render notifications in dropdown list
     * @param {Array} notifications - Array of notification objects
     */
    renderNotifications(notifications) {
        const listContainer = document.getElementById('notification-list');
        if (!listContainer) return;

        listContainer.innerHTML = '';

        if (notifications.length === 0) {
            listContainer.innerHTML = `
                <div class="p-8 text-center">
                    <div class="w-12 h-12 bg-slate-50 rounded-full flex items-center justify-center mx-auto mb-3">
                        <i class="fas fa-bell-slash text-slate-300 text-xl"></i>
                    </div>
                    <p class="text-sm text-slate-500">Bildirim yok</p>
                </div>
            `;
            return;
        }

        notifications.forEach(notification => {
            const item = this.createNotificationItem(notification);
            listContainer.appendChild(item);
        });
    }

    /**
     * Create notification item HTML element
     * @param {Object} notification - Notification data
     * @returns {HTMLElement} Notification item element
     */
    createNotificationItem(notification) {
        const div = document.createElement('div');
        div.className = `notification-item p-3 border-b border-slate-100 hover:bg-slate-50 cursor-pointer transition-colors ${
            notification.is_read ? 'opacity-60' : ''
        }`;
        div.dataset.notificationId = notification.id;

        const icon = this.getNotificationIcon(notification.notification_type || notification.type);
        const message = this.escapeHtml(notification.message);
        const timeAgo = this.formatTimeAgo(notification.created_at);

        div.innerHTML = `
            <div class="flex items-start gap-3">
                <div class="flex-shrink-0 w-8 h-8 rounded-full bg-brand-50 text-brand-600 flex items-center justify-center text-sm">
                    ${icon}
                </div>
                <div class="flex-1 min-w-0">
                    <p class="text-sm text-slate-700 leading-relaxed">${message}</p>
                    <p class="text-xs text-slate-400 mt-1">${timeAgo}</p>
                </div>
                ${!notification.is_read ? '<div class="flex-shrink-0 w-2 h-2 rounded-full bg-brand-500 mt-2"></div>' : ''}
            </div>
        `;

        div.addEventListener('click', () => this.onNotificationClick(notification));

        return div;
    }

    /**
     * Prepend new notification to list (for real-time updates)
     * @param {Object} notification - Notification data
     */
    prependNotificationToList(notification) {
        const listContainer = document.getElementById('notification-list');
        if (!listContainer) return;

        // Remove empty state if exists
        const emptyState = listContainer.querySelector('.text-center');
        if (emptyState) {
            listContainer.innerHTML = '';
        }

        const item = this.createNotificationItem(notification);
        listContainer.insertBefore(item, listContainer.firstChild);
    }

    /**
     * Handle notification item click
     * @param {Object} notification - Notification data
     */
    async onNotificationClick(notification) {
        // Mark as read if unread
        if (!notification.is_read) {
            await this.markAsRead(notification.id);
            
            // Update UI
            const item = document.querySelector(`[data-notification-id="${notification.id}"]`);
            if (item) {
                item.classList.add('opacity-60');
                const unreadDot = item.querySelector('.bg-brand-500');
                if (unreadDot) unreadDot.remove();
            }
        }

        // Navigate to related task if exists
        if (notification.task_id) {
            // Check if task modal exists
            if (window.taskModal && typeof window.taskModal.open === 'function') {
                window.taskModal.open(notification.task_id);
            } else {
                // Fallback: navigate to tasks page
                window.location.href = `/tasks?task_id=${notification.task_id}`;
            }
        }

        this.closeDropdown();
    }

    /**
     * Mark notification as read
     * @param {number} notificationId - Notification ID
     */
    async markAsRead(notificationId) {
        try {
            const response = await fetch(`/api/v1/notifications/${notificationId}/read`, {
                method: 'PATCH'
            });

            if (response.ok) {
                this.unreadCount = Math.max(0, this.unreadCount - 1);
                this.updateBadge();
            }
        } catch (error) {
            console.error('Error marking notification as read:', error);
        }
    }

    /**
     * Mark all notifications as read
     */
    async markAllAsRead() {
        try {
            const response = await fetch('/api/v1/notifications/mark-all-read', {
                method: 'POST'
            });

            if (response.ok) {
                this.unreadCount = 0;
                this.updateBadge();
                
                // Update UI - mark all items as read
                const items = document.querySelectorAll('.notification-item');
                items.forEach(item => {
                    item.classList.add('opacity-60');
                    const unreadDot = item.querySelector('.bg-brand-500');
                    if (unreadDot) unreadDot.remove();
                });
            }
        } catch (error) {
            console.error('Error marking all as read:', error);
        }
    }

    /**
     * Update badge count display
     */
    updateBadge() {
        if (!this.badge) return;

        if (this.unreadCount > 0) {
            this.badge.textContent = this.unreadCount > 99 ? '99+' : this.unreadCount;
            this.badge.classList.remove('hidden');
        } else {
            this.badge.classList.add('hidden');
        }
    }

    /**
     * Toggle dropdown visibility
     */
    toggleDropdown() {
        if (!this.dropdown) return;

        const isHidden = this.dropdown.classList.contains('hidden');
        
        if (isHidden) {
            this.dropdown.classList.remove('hidden');
            // Reload notifications when opening
            this.loadNotifications();
        } else {
            this.closeDropdown();
        }
    }

    /**
     * Close dropdown
     */
    closeDropdown() {
        if (this.dropdown) {
            this.dropdown.classList.add('hidden');
        }
    }

    /**
     * Get icon for notification type
     * @param {string} type - Notification type
     * @returns {string} Icon HTML or emoji
     */
    getNotificationIcon(type) {
        const icons = {
            'task_reminder': '⏰',
            'task_overdue': '⚠️',
            'task_assigned': '👤',
            'task_updated': '✏️'
        };
        return icons[type] || '🔔';
    }

    /**
     * Play notification sound
     */
    playNotificationSound() {
        try {
            // Create audio element if not exists
            if (!this.notificationSound) {
                this.notificationSound = new Audio('/static/sounds/notification.mp3');
                this.notificationSound.volume = 0.3;
            }

            // Play sound (catch errors silently if sound file doesn't exist)
            this.notificationSound.play().catch(() => {
                // Fallback: use system beep or do nothing
                console.log('Notification sound not available');
            });
        } catch (error) {
            // Silent fail - sound is optional
        }
    }

    /**
     * Format time ago (e.g., "5dk önce", "2sa önce")
     * @param {string} timestamp - ISO timestamp
     * @returns {string} Formatted time ago string
     */
    formatTimeAgo(timestamp) {
        if (!timestamp) return 'Şimdi';
        
        try {
            const raw = String(timestamp);
            const date = new Date(raw + (raw.endsWith('Z') ? '' : 'Z'));
            
            if (isNaN(date.getTime())) return 'Şimdi';
            
            const now = new Date();
            const diff = now - date;
            const minutes = Math.floor(diff / 60000);
            const hours = Math.floor(diff / 3600000);
            const days = Math.floor(diff / 86400000);

            if (minutes < 1) return 'Şimdi';
            if (minutes < 60) return `${minutes}dk önce`;
            if (hours < 24) return `${hours}sa önce`;
            if (days < 7) return `${days}g önce`;
            
            return date.toLocaleDateString('tr-TR', { day: 'numeric', month: 'short' });
        } catch (error) {
            return 'Şimdi';
        }
    }

    /**
     * Escape HTML to prevent XSS
     * @param {string} str - String to escape
     * @returns {string} Escaped string
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
}

// Export for use in other modules
if (typeof module !== 'undefined' && module.exports) {
    module.exports = NotificationBell;
}
