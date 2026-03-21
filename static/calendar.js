// Calendar View - Takvim ve Görev Yönetimi
// WhatsApp CRM SaaS - Calendar Task Management Feature

class CalendarView {
    constructor(containerId) {
        this.container = document.getElementById(containerId);
        this.currentView = 'month'; // month, week, day, agenda
        this.currentDate = new Date();
        this.events = [];
        this.filters = {
            task_type: null,
            assignee_id: null,
            status: null
        };
    }

    async init() {
        this.render();
        this.attachEventListeners();
        await this.loadEvents();
    }

    render() {
        if (!this.container) {
            console.error('Calendar container not found');
            return;
        }
        
        const html = this.generateCalendarHTML();
        this.container.innerHTML = html;
    }

    generateCalendarHTML() {
        switch(this.currentView) {
            case 'month':
                return this.generateMonthView();
            case 'week':
                return this.generateWeekView();
            case 'day':
                return this.generateDayView();
            case 'agenda':
                return this.generateAgendaView();
            default:
                return this.generateMonthView();
        }
    }

    generateMonthView() {
        const year = this.currentDate.getFullYear();
        const month = this.currentDate.getMonth();
        
        // Get first day of month and total days
        const firstDay = new Date(year, month, 1);
        const lastDay = new Date(year, month + 1, 0);
        const daysInMonth = lastDay.getDate();
        const startDayOfWeek = firstDay.getDay(); // 0 = Sunday
        
        // Month name
        const monthNames = ['Ocak', 'Şubat', 'Mart', 'Nisan', 'Mayıs', 'Haziran',
                           'Temmuz', 'Ağustos', 'Eylül', 'Ekim', 'Kasım', 'Aralık'];
        
        let html = `
            <div class="calendar-month-view">
                <div class="calendar-header">
                    <h2 class="text-xl font-bold text-slate-800">${monthNames[month]} ${year}</h2>
                </div>
                <div class="calendar-weekdays grid grid-cols-7 gap-1 mb-2">
                    <div class="text-center text-sm font-semibold text-slate-600 py-2">Paz</div>
                    <div class="text-center text-sm font-semibold text-slate-600 py-2">Pzt</div>
                    <div class="text-center text-sm font-semibold text-slate-600 py-2">Sal</div>
                    <div class="text-center text-sm font-semibold text-slate-600 py-2">Çar</div>
                    <div class="text-center text-sm font-semibold text-slate-600 py-2">Per</div>
                    <div class="text-center text-sm font-semibold text-slate-600 py-2">Cum</div>
                    <div class="text-center text-sm font-semibold text-slate-600 py-2">Cmt</div>
                </div>
                <div class="calendar-days grid grid-cols-7 gap-1">
        `;
        
        // Empty cells before first day
        for (let i = 0; i < startDayOfWeek; i++) {
            html += '<div class="calendar-day-cell empty"></div>';
        }
        
        // Days of month
        for (let day = 1; day <= daysInMonth; day++) {
            const date = new Date(year, month, day);
            const isToday = this.isToday(date);
            const dateStr = this.formatDateKey(date);
            
            html += `
                <div class="calendar-day-cell ${isToday ? 'today' : ''}" data-date="${dateStr}">
                    <div class="day-number text-sm font-semibold ${isToday ? 'text-brand-600' : 'text-slate-700'}">${day}</div>
                    <div class="day-events" id="events-${dateStr}"></div>
                </div>
            `;
        }
        
        html += `
                </div>
            </div>
        `;
        
        return html;
    }

    generateWeekView() {
        const startOfWeek = this.getStartOfWeek(this.currentDate);
        const days = [];
        
        for (let i = 0; i < 7; i++) {
            const date = new Date(startOfWeek);
            date.setDate(startOfWeek.getDate() + i);
            days.push(date);
        }
        
        const dayNames = ['Pazar', 'Pazartesi', 'Salı', 'Çarşamba', 'Perşembe', 'Cuma', 'Cumartesi'];
        
        let html = `
            <div class="calendar-week-view">
                <div class="calendar-header mb-4">
                    <h2 class="text-xl font-bold text-slate-800">
                        ${this.formatDate(days[0])} - ${this.formatDate(days[6])}
                    </h2>
                </div>
                <div class="week-grid">
                    <div class="time-column">
                        <div class="time-header"></div>
        `;
        
        // Time slots (8:00 - 20:00)
        for (let hour = 8; hour <= 20; hour++) {
            html += `<div class="time-slot">${hour}:00</div>`;
        }
        
        html += `</div>`;
        
        // Day columns
        days.forEach((date, index) => {
            const isToday = this.isToday(date);
            const dateStr = this.formatDateKey(date);
            
            html += `
                <div class="day-column" data-date="${dateStr}">
                    <div class="day-header ${isToday ? 'today' : ''}">
                        <div class="text-xs text-slate-500">${dayNames[index]}</div>
                        <div class="text-lg font-bold ${isToday ? 'text-brand-600' : 'text-slate-800'}">${date.getDate()}</div>
                    </div>
                    <div class="day-time-slots" id="slots-${dateStr}">
            `;
            
            for (let hour = 8; hour <= 20; hour++) {
                html += `<div class="time-slot-cell" data-hour="${hour}"></div>`;
            }
            
            html += `
                    </div>
                </div>
            `;
        });
        
        html += `
                </div>
            </div>
        `;
        
        return html;
    }

    generateDayView() {
        const date = this.currentDate;
        const dayNames = ['Pazar', 'Pazartesi', 'Salı', 'Çarşamba', 'Perşembe', 'Cuma', 'Cumartesi'];
        const isToday = this.isToday(date);
        const dateStr = this.formatDateKey(date);
        
        let html = `
            <div class="calendar-day-view">
                <div class="calendar-header mb-4">
                    <h2 class="text-xl font-bold text-slate-800">
                        ${dayNames[date.getDay()]}, ${this.formatDate(date)}
                    </h2>
                </div>
                <div class="day-schedule">
                    <div class="time-column">
        `;
        
        // Time slots (0:00 - 23:00)
        for (let hour = 0; hour < 24; hour++) {
            html += `
                <div class="time-slot-row">
                    <div class="time-label">${hour.toString().padStart(2, '0')}:00</div>
                    <div class="time-slot-content" data-date="${dateStr}" data-hour="${hour}" id="slot-${dateStr}-${hour}"></div>
                </div>
            `;
        }
        
        html += `
                    </div>
                </div>
            </div>
        `;
        
        return html;
    }

    generateAgendaView() {
        const startDate = new Date(this.currentDate);
        startDate.setDate(1); // First day of month
        const endDate = new Date(this.currentDate);
        endDate.setMonth(endDate.getMonth() + 1);
        endDate.setDate(0); // Last day of month
        
        const monthNames = ['Ocak', 'Şubat', 'Mart', 'Nisan', 'Mayıs', 'Haziran',
                           'Temmuz', 'Ağustos', 'Eylül', 'Ekim', 'Kasım', 'Aralık'];
        
        let html = `
            <div class="calendar-agenda-view">
                <div class="calendar-header mb-4">
                    <h2 class="text-xl font-bold text-slate-800">
                        ${monthNames[this.currentDate.getMonth()]} ${this.currentDate.getFullYear()} - Ajanda
                    </h2>
                </div>
                <div class="agenda-list" id="agenda-list">
                    <div class="text-center text-slate-500 py-8">Görevler yükleniyor...</div>
                </div>
            </div>
        `;
        
        return html;
    }

    async loadEvents() {
        try {
            const { start, end } = this.getDateRange();
            
            const params = new URLSearchParams({
                start: start.toISOString(),
                end: end.toISOString()
            });
            
            // Add filters if set
            if (this.filters.task_type) {
                params.set('task_type', this.filters.task_type);
            }
            if (this.filters.assignee_id) {
                params.set('assignee_id', this.filters.assignee_id);
            }
            if (this.filters.status) {
                params.set('status', this.filters.status);
            }
            
            const response = await fetch(`/api/v1/calendar/events?${params.toString()}`);
            
            if (response.status === 401) {
                window.location.href = '/login';
                return;
            }
            
            if (!response.ok) {
                console.error('Failed to load events:', response.statusText);
                return;
            }
            
            const data = await response.json();
            this.events = data.events || [];
            
            this.renderEvents();
            
        } catch (error) {
            console.error('Error loading events:', error);
        }
    }

    renderEvents() {
        if (!this.events || this.events.length === 0) {
            if (this.currentView === 'agenda') {
                const agendaList = document.getElementById('agenda-list');
                if (agendaList) {
                    agendaList.innerHTML = '<div class="text-center text-slate-500 py-8">Bu dönemde görev yok</div>';
                }
            }
            // Attach calendar cell handlers even when no events
            this.attachCalendarCellHandlers();
            return;
        }
        
        switch(this.currentView) {
            case 'month':
                this.renderMonthEvents();
                break;
            case 'week':
                this.renderWeekEvents();
                break;
            case 'day':
                this.renderDayEvents();
                break;
            case 'agenda':
                this.renderAgendaEvents();
                break;
        }
        
        // Attach calendar cell handlers after rendering events
        this.attachCalendarCellHandlers();
    }

    renderMonthEvents() {
        // Clear all event containers first
        document.querySelectorAll('[id^="events-"]').forEach(container => {
            container.innerHTML = '';
        });
        
        this.events.forEach(event => {
            const eventDate = new Date(event.start);
            const dateStr = this.formatDateKey(eventDate);
            const container = document.getElementById(`events-${dateStr}`);
            
            if (container) {
                const element = this.createEventElement(event, 'month');
                container.appendChild(element);
            }
        });
    }

    renderWeekEvents() {
        // Clear all slot containers first
        document.querySelectorAll('[id^="slots-"]').forEach(container => {
            container.innerHTML = '';
        });
        
        this.events.forEach(event => {
            const eventDate = new Date(event.start);
            const dateStr = this.formatDateKey(eventDate);
            const hour = eventDate.getHours();
            const container = document.getElementById(`slots-${dateStr}`);
            
            if (container) {
                const element = this.createEventElement(event, 'week');
                this.positionEventInWeek(element, event);
                container.appendChild(element);
            }
        });
    }

    renderDayEvents() {
        // Clear all slot containers first
        document.querySelectorAll('[id^="slot-"]').forEach(container => {
            container.innerHTML = '';
        });
        
        this.events.forEach(event => {
            const eventDate = new Date(event.start);
            const dateStr = this.formatDateKey(eventDate);
            const hour = eventDate.getHours();
            const container = document.getElementById(`slot-${dateStr}-${hour}`);
            
            if (container) {
                const element = this.createEventElement(event, 'day');
                container.appendChild(element);
            }
        });
    }

    renderAgendaEvents() {
        const agendaList = document.getElementById('agenda-list');
        if (!agendaList) return;
        
        agendaList.innerHTML = '';
        
        // Group events by date
        const eventsByDate = {};
        this.events.forEach(event => {
            const dateKey = this.formatDateKey(new Date(event.start));
            if (!eventsByDate[dateKey]) {
                eventsByDate[dateKey] = [];
            }
            eventsByDate[dateKey].push(event);
        });
        
        // Sort dates
        const sortedDates = Object.keys(eventsByDate).sort();
        
        sortedDates.forEach(dateKey => {
            const date = this.parseDateKey(dateKey);
            const dayEvents = eventsByDate[dateKey];
            
            const dateHeader = document.createElement('div');
            dateHeader.className = 'agenda-date-header text-sm font-bold text-slate-700 py-2 px-3 bg-slate-50 border-b border-slate-200';
            dateHeader.textContent = this.formatDate(date);
            agendaList.appendChild(dateHeader);
            
            dayEvents.forEach(event => {
                const element = this.createEventElement(event, 'agenda');
                agendaList.appendChild(element);
            });
        });
    }

    createEventElement(event, viewType) {
        const div = document.createElement('div');
        div.className = `calendar-event calendar-event-${viewType}`;
        div.dataset.eventId = event.id;
        div.style.borderLeftColor = event.color;
        div.draggable = true;
        
        const startTime = new Date(event.start);
        const endTime = event.end ? new Date(event.end) : null;
        
        if (viewType === 'month') {
            div.innerHTML = `
                <div class="flex items-center gap-1 text-xs">
                    <span class="event-type-icon">${this.getTypeIcon(event.type)}</span>
                    <span class="event-title truncate">${this.escapeHtml(event.title)}</span>
                </div>
            `;
        } else if (viewType === 'agenda') {
            div.innerHTML = `
                <div class="flex items-start gap-3 p-3 border-b border-slate-100 hover:bg-slate-50">
                    <div class="flex-shrink-0 text-sm text-slate-500">
                        ${this.formatTime(startTime)}${endTime ? ' - ' + this.formatTime(endTime) : ''}
                    </div>
                    <div class="flex-1">
                        <div class="flex items-center gap-2">
                            <span class="event-type-icon">${this.getTypeIcon(event.type)}</span>
                            <span class="font-semibold text-slate-800">${this.escapeHtml(event.title)}</span>
                            <span class="text-xs px-2 py-0.5 rounded ${this.getStatusClass(event.status)}">${this.getStatusLabel(event.status)}</span>
                        </div>
                        ${event.extendedProps?.description ? `<p class="text-sm text-slate-600 mt-1">${this.escapeHtml(event.extendedProps.description)}</p>` : ''}
                    </div>
                </div>
            `;
        } else {
            div.innerHTML = `
                <div class="event-time text-xs font-semibold">${this.formatTime(startTime)}</div>
                <div class="event-title text-sm truncate">${this.escapeHtml(event.title)}</div>
                <div class="event-type-badge">${this.getTypeIcon(event.type)}</div>
            `;
        }
        
        // Attach event handlers
        this.attachEventHandlers(div, event);
        
        return div;
    }

    attachEventHandlers(element, event) {
        // Drag start
        element.addEventListener('dragstart', (e) => this.onDragStart(e, event));
        element.addEventListener('dragend', (e) => this.onDragEnd(e, event));
        
        // Click - open detail modal
        element.addEventListener('click', (e) => this.onEventClick(e, event));
    }

    attachCalendarCellHandlers() {
        // Add drop zone handlers to all calendar cells
        const cells = this.container.querySelectorAll('[data-date]');
        
        cells.forEach(cell => {
            // Prevent default to allow drop
            cell.addEventListener('dragover', (e) => {
                e.preventDefault();
                e.dataTransfer.dropEffect = 'move';
                cell.classList.add('drag-over');
            });
            
            cell.addEventListener('dragleave', (e) => {
                cell.classList.remove('drag-over');
            });
            
            cell.addEventListener('drop', (e) => {
                e.preventDefault();
                cell.classList.remove('drag-over');
            });
            
            // Click on empty area to create new task
            cell.addEventListener('click', (e) => {
                // Only trigger if clicking on the cell itself or day-events container, not on an event
                if (e.target === cell || 
                    e.target.classList.contains('day-events') ||
                    e.target.classList.contains('day-time-slots') ||
                    e.target.classList.contains('time-slot-cell') ||
                    e.target.classList.contains('time-slot-content')) {
                    this.onEmptySlotClick(e);
                }
            });
        });
    }

    onDragStart(e, event) {
        e.dataTransfer.effectAllowed = 'move';
        e.dataTransfer.setData('text/plain', event.id.toString());
        e.target.classList.add('dragging');
        this.draggedEvent = event;
    }

    async onDragEnd(e, event) {
        e.target.classList.remove('dragging');
        
        // Calculate new date/time based on drop target
        const dropTarget = document.elementFromPoint(e.clientX, e.clientY);
        if (!dropTarget) return;
        
        const newDateTime = this.calculateNewDateTime(dropTarget, event);
        if (!newDateTime) return;
        
        // Update event time
        await this.updateEventTime(event.id, newDateTime);
        
        this.draggedEvent = null;
    }

    calculateNewDateTime(dropTarget, event) {
        // Find the calendar cell
        const cell = dropTarget.closest('[data-date]');
        if (!cell) return null;
        
        const dateStr = cell.dataset.date;
        const date = this.parseDateKey(dateStr);
        
        if (!date) return null;
        
        // For week/day view, also get hour
        const hourCell = dropTarget.closest('[data-hour]');
        if (hourCell) {
            const hour = parseInt(hourCell.dataset.hour);
            date.setHours(hour, 0, 0, 0);
        } else {
            // Keep original time for month view
            const originalStart = new Date(event.start);
            date.setHours(originalStart.getHours(), originalStart.getMinutes(), 0, 0);
        }
        
        return date;
    }

    async updateEventTime(eventId, newDateTime) {
        try {
            // Calculate duration
            const originalEvent = this.events.find(e => e.id === eventId);
            if (!originalEvent) return;
            
            const duration = originalEvent.end 
                ? new Date(originalEvent.end) - new Date(originalEvent.start)
                : 30 * 60 * 1000; // Default 30 minutes
            
            const endDateTime = new Date(newDateTime.getTime() + duration);
            
            const response = await fetch(`/api/v1/tasks/${eventId}`, {
                method: 'PATCH',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({
                    start_time: newDateTime.toISOString(),
                    end_time: endDateTime.toISOString()
                })
            });
            
            if (response.ok) {
                await this.loadEvents();
                this.showToast('Görev güncellendi', 'success');
            } else {
                const error = await response.json();
                this.showToast(error.error || 'Güncelleme başarısız', 'error');
            }
            
        } catch (error) {
            console.error('Error updating event:', error);
            this.showToast('Bir hata oluştu', 'error');
        }
    }

    onEventClick(e, event) {
        e.stopPropagation();
        // Open task modal (will be implemented in next task)
        if (window.taskModal) {
            window.taskModal.open(event.id);
        } else {
            console.log('Task modal not available, event:', event);
        }
    }

    onEmptySlotClick(e) {
        // Get the clicked cell's date and time
        const cell = e.target.closest('[data-date]');
        if (!cell) return;
        
        const dateStr = cell.dataset.date;
        const date = this.parseDateKey(dateStr);
        if (!date) return;
        
        // For week/day view, also get hour
        const hourCell = e.target.closest('[data-hour]');
        if (hourCell) {
            const hour = parseInt(hourCell.dataset.hour);
            date.setHours(hour, 0, 0, 0);
        } else {
            // For month view, set to 9:00 AM by default
            date.setHours(9, 0, 0, 0);
        }
        
        // Calculate end time (1 hour later)
        const endDate = new Date(date.getTime() + 60 * 60 * 1000);
        
        // Open task modal with default values
        if (window.taskModal) {
            window.taskModal.openNew({
                start_time: date.toISOString(),
                end_time: endDate.toISOString()
            });
        } else {
            console.log('Task modal not available, would create task at:', date);
        }
    }

    positionEventInWeek(element, event) {
        const startTime = new Date(event.start);
        const endTime = event.end ? new Date(event.end) : new Date(startTime.getTime() + 30 * 60000);
        
        const startHour = startTime.getHours();
        const startMinute = startTime.getMinutes();
        const duration = (endTime - startTime) / (60 * 1000); // minutes
        
        // Position relative to 8:00 start
        const topOffset = ((startHour - 8) * 60 + startMinute) / 60;
        const height = duration / 60;
        
        element.style.position = 'absolute';
        element.style.top = `${topOffset * 60}px`; // 60px per hour
        element.style.height = `${height * 60}px`;
        element.style.left = '0';
        element.style.right = '0';
    }

    attachEventListeners() {
        // View change buttons
        document.querySelectorAll('[data-view]').forEach(btn => {
            btn.addEventListener('click', (e) => {
                const view = e.target.dataset.view;
                this.changeView(view);
            });
        });
        
        // Navigation buttons
        const prevBtn = document.getElementById('calendar-prev');
        const nextBtn = document.getElementById('calendar-next');
        const todayBtn = document.getElementById('calendar-today');
        
        if (prevBtn) {
            prevBtn.addEventListener('click', () => this.navigatePrev());
        }
        if (nextBtn) {
            nextBtn.addEventListener('click', () => this.navigateNext());
        }
        if (todayBtn) {
            todayBtn.addEventListener('click', () => this.navigateToday());
        }
        
        // Filter dropdowns
        const typeFilter = document.getElementById('filter-task-type');
        const assigneeFilter = document.getElementById('filter-assignee');
        const statusFilter = document.getElementById('filter-status');
        
        if (typeFilter) {
            typeFilter.addEventListener('change', (e) => {
                this.applyFilter('task_type', e.target.value || null);
            });
        }
        if (assigneeFilter) {
            assigneeFilter.addEventListener('change', (e) => {
                this.applyFilter('assignee_id', e.target.value || null);
            });
        }
        if (statusFilter) {
            statusFilter.addEventListener('change', (e) => {
                this.applyFilter('status', e.target.value || null);
            });
        }
    }

    changeView(view) {
        this.currentView = view;
        this.render();
        this.loadEvents();
        
        // Update active button
        document.querySelectorAll('[data-view]').forEach(btn => {
            btn.classList.remove('active');
        });
        document.querySelector(`[data-view="${view}"]`)?.classList.add('active');
    }

    navigatePrev() {
        switch(this.currentView) {
            case 'month':
                this.currentDate.setMonth(this.currentDate.getMonth() - 1);
                break;
            case 'week':
                this.currentDate.setDate(this.currentDate.getDate() - 7);
                break;
            case 'day':
                this.currentDate.setDate(this.currentDate.getDate() - 1);
                break;
            case 'agenda':
                this.currentDate.setMonth(this.currentDate.getMonth() - 1);
                break;
        }
        this.render();
        this.loadEvents();
    }

    navigateNext() {
        switch(this.currentView) {
            case 'month':
                this.currentDate.setMonth(this.currentDate.getMonth() + 1);
                break;
            case 'week':
                this.currentDate.setDate(this.currentDate.getDate() + 7);
                break;
            case 'day':
                this.currentDate.setDate(this.currentDate.getDate() + 1);
                break;
            case 'agenda':
                this.currentDate.setMonth(this.currentDate.getMonth() + 1);
                break;
        }
        this.render();
        this.loadEvents();
    }

    navigateToday() {
        this.currentDate = new Date();
        this.render();
        this.loadEvents();
    }

    applyFilter(filterType, value) {
        this.filters[filterType] = value;
        this.loadEvents();
    }

    getDateRange() {
        let start, end;
        
        switch(this.currentView) {
            case 'month':
                start = new Date(this.currentDate.getFullYear(), this.currentDate.getMonth(), 1);
                end = new Date(this.currentDate.getFullYear(), this.currentDate.getMonth() + 1, 0, 23, 59, 59);
                break;
            case 'week':
                start = this.getStartOfWeek(this.currentDate);
                end = new Date(start);
                end.setDate(end.getDate() + 6);
                end.setHours(23, 59, 59);
                break;
            case 'day':
                start = new Date(this.currentDate);
                start.setHours(0, 0, 0, 0);
                end = new Date(this.currentDate);
                end.setHours(23, 59, 59);
                break;
            case 'agenda':
                start = new Date(this.currentDate.getFullYear(), this.currentDate.getMonth(), 1);
                end = new Date(this.currentDate.getFullYear(), this.currentDate.getMonth() + 1, 0, 23, 59, 59);
                break;
        }
        
        return { start, end };
    }

    // Helper functions
    getStartOfWeek(date) {
        const d = new Date(date);
        const day = d.getDay();
        const diff = d.getDate() - day; // Sunday as start
        return new Date(d.setDate(diff));
    }

    isToday(date) {
        const today = new Date();
        return date.getDate() === today.getDate() &&
               date.getMonth() === today.getMonth() &&
               date.getFullYear() === today.getFullYear();
    }

    formatDateKey(date) {
        return `${date.getFullYear()}-${String(date.getMonth() + 1).padStart(2, '0')}-${String(date.getDate()).padStart(2, '0')}`;
    }

    parseDateKey(dateStr) {
        const parts = dateStr.split('-');
        if (parts.length !== 3) return null;
        return new Date(parseInt(parts[0]), parseInt(parts[1]) - 1, parseInt(parts[2]));
    }

    formatDate(date) {
        const day = date.getDate();
        const monthNames = ['Ocak', 'Şubat', 'Mart', 'Nisan', 'Mayıs', 'Haziran',
                           'Temmuz', 'Ağustos', 'Eylül', 'Ekim', 'Kasım', 'Aralık'];
        const month = monthNames[date.getMonth()];
        const year = date.getFullYear();
        return `${day} ${month} ${year}`;
    }

    formatTime(date) {
        return date.toLocaleTimeString('tr-TR', { hour: '2-digit', minute: '2-digit' });
    }

    getTypeIcon(type) {
        const icons = {
            'call': '📞',
            'meeting': '👥',
            'email': '📧',
            'todo': '✅',
            'follow_up': '🔄',
            'other': '📋'
        };
        return icons[type] || '📋';
    }

    getStatusClass(status) {
        const classes = {
            'pending': 'bg-amber-100 text-amber-700',
            'completed': 'bg-emerald-100 text-emerald-700',
            'cancelled': 'bg-slate-100 text-slate-600',
            'overdue': 'bg-red-100 text-red-700'
        };
        return classes[status] || 'bg-slate-100 text-slate-600';
    }

    getStatusLabel(status) {
        const labels = {
            'pending': 'Bekliyor',
            'completed': 'Tamamlandı',
            'cancelled': 'İptal',
            'overdue': 'Gecikmiş'
        };
        return labels[status] || status;
    }

    escapeHtml(str) {
        if (!str) return '';
        return String(str)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#039;');
    }

    showToast(message, type = 'info') {
        // Use existing toast function from app.js if available
        if (typeof showToast === 'function') {
            showToast(message, type);
        } else {
            console.log(`[${type.toUpperCase()}] ${message}`);
        }
    }
}

// Export for use in other modules
if (typeof module !== 'undefined' && module.exports) {
    module.exports = CalendarView;
}
