// Contacts Pagination & Bulk Actions
let currentPage = 1;
let totalPages = 1;
let totalContacts = 0;
let perPage = 50;
let selectedContactIds = new Set();

// Initialize pagination
function initPagination() {
    // Select all checkbox handler
    const selectAllCheckbox = document.getElementById('selectAll');
    if (selectAllCheckbox) {
        selectAllCheckbox.addEventListener('change', function() {
            toggleSelectAll(this.checked);
        });
    }
}

// Toggle select all contacts on current page
function toggleSelectAll(checked) {
    const checkboxes = document.querySelectorAll('.contact-checkbox');
    checkboxes.forEach(cb => {
        cb.checked = checked;
        const contactId = parseInt(cb.dataset.contactId);
        if (checked) {
            selectedContactIds.add(contactId);
        } else {
            selectedContactIds.delete(contactId);
        }
    });
    updateBulkActionsBar();
}

// Toggle individual contact selection
function toggleContactSelection(contactId, checked) {
    if (checked) {
        selectedContactIds.add(contactId);
    } else {
        selectedContactIds.delete(contactId);
    }
    updateBulkActionsBar();
    
    // Update select all checkbox
    const selectAllCheckbox = document.getElementById('selectAll');
    const checkboxes = document.querySelectorAll('.contact-checkbox');
    const allChecked = Array.from(checkboxes).every(cb => cb.checked);
    if (selectAllCheckbox) {
        selectAllCheckbox.checked = allChecked;
    }
}

// Update bulk actions bar visibility and count
function updateBulkActionsBar() {
    const bulkActionsBar = document.getElementById('bulkActionsBar');
    const selectedCount = document.getElementById('selectedCount');
    
    if (selectedContactIds.size > 0) {
        bulkActionsBar.classList.remove('hidden');
        selectedCount.textContent = `${selectedContactIds.size} kişi seçildi`;
    } else {
        bulkActionsBar.classList.add('hidden');
    }
}

// Load contacts with pagination
async function loadContactsWithPagination(page = 1) {
    currentPage = page;
    const loading = document.getElementById('loadingState');
    loading.classList.remove('hidden');
    
    try {
        const search = document.getElementById('contactsSearchInput')?.value.trim() || '';
        const role = document.getElementById('roleFilter')?.value || '';
        
        let url = `/api/v1/contacts?page=${page}&per_page=${perPage}`;
        if (search) url += `&search=${encodeURIComponent(search)}`;
        if (role) url += `&role=${encodeURIComponent(role)}`;
        if (window.companyIdFilter) url += `&company_id=${window.companyIdFilter}`;
        
        const res = await fetch(url);
        if (!res.ok) {
            throw new Error(`Contacts API failed: ${res.status}`);
        }
        const data = await res.json();
        
        // Update pagination info
        if (data.pagination) {
            totalPages = data.pagination.pages || 1;
            totalContacts = data.pagination.total || 0;
            currentPage = data.pagination.page || 1;
        }
        
        // Render contacts
        window.allContacts = Array.isArray(data.contacts) ? data.contacts : [];
        if (typeof window.renderContacts === 'function') {
            window.renderContacts(window.allContacts);
        }
        
        // Update pagination UI
        updatePaginationUI();
        
        // Update contact count
        const contactCount = document.getElementById('contactCount');
        if (contactCount) {
            contactCount.textContent = totalContacts;
        }
        
        // Clear selections on page change
        selectedContactIds.clear();
        updateBulkActionsBar();
        
    } catch (e) {
        console.error(e);
        if (typeof window.showToast === 'function') {
            window.showToast('Kişiler yüklenirken bir hata oluştu.', 'error');
        }
    } finally {
        loading.classList.add('hidden');
    }
}

// Update pagination UI
function updatePaginationUI() {
    const paginationBar = document.getElementById('paginationBar');
    const paginationInfo = document.getElementById('paginationInfo');
    const pageNumbers = document.getElementById('pageNumbers');
    const prevBtn = document.getElementById('prevPageBtn');
    const nextBtn = document.getElementById('nextPageBtn');
    
    if (!paginationBar) return;
    
    // Show/hide pagination bar
    if (totalContacts > 0) {
        paginationBar.classList.remove('hidden');
    } else {
        paginationBar.classList.add('hidden');
        return;
    }
    
    // Update info text
    const start = (currentPage - 1) * perPage + 1;
    const end = Math.min(currentPage * perPage, totalContacts);
    paginationInfo.textContent = `${start}-${end} / ${totalContacts}`;
    
    // Update prev/next buttons
    prevBtn.disabled = currentPage <= 1;
    nextBtn.disabled = currentPage >= totalPages;
    
    // Generate page numbers
    pageNumbers.innerHTML = '';
    const maxVisiblePages = 5;
    let startPage = Math.max(1, currentPage - Math.floor(maxVisiblePages / 2));
    let endPage = Math.min(totalPages, startPage + maxVisiblePages - 1);
    
    // Adjust start if we're near the end
    if (endPage - startPage < maxVisiblePages - 1) {
        startPage = Math.max(1, endPage - maxVisiblePages + 1);
    }
    
    // First page
    if (startPage > 1) {
        pageNumbers.innerHTML += `
            <button onclick="goToPage(1)" class="px-3 py-2 border border-gray-300 rounded-lg text-sm font-semibold text-gray-700 hover:bg-gray-50 transition-all">
                1
            </button>
        `;
        if (startPage > 2) {
            pageNumbers.innerHTML += `<span class="px-2 text-gray-400">...</span>`;
        }
    }
    
    // Page numbers
    for (let i = startPage; i <= endPage; i++) {
        const isActive = i === currentPage;
        pageNumbers.innerHTML += `
            <button onclick="goToPage(${i})" class="px-3 py-2 border ${isActive ? 'border-brand-600 bg-brand-50 text-brand-600' : 'border-gray-300 text-gray-700 hover:bg-gray-50'} rounded-lg text-sm font-semibold transition-all">
                ${i}
            </button>
        `;
    }
    
    // Last page
    if (endPage < totalPages) {
        if (endPage < totalPages - 1) {
            pageNumbers.innerHTML += `<span class="px-2 text-gray-400">...</span>`;
        }
        pageNumbers.innerHTML += `
            <button onclick="goToPage(${totalPages})" class="px-3 py-2 border border-gray-300 rounded-lg text-sm font-semibold text-gray-700 hover:bg-gray-50 transition-all">
                ${totalPages}
            </button>
        `;
    }
}

// Go to specific page
function goToPage(page) {
    if (page < 1 || page > totalPages || page === currentPage) return;
    loadContactsWithPagination(page);
}

// Bulk delete selected contacts
async function bulkDeleteContacts() {
    if (selectedContactIds.size === 0) return;
    
    const confirmed = confirm(`${selectedContactIds.size} kişiyi silmek istediğinizden emin misiniz? Bu işlem geri alınamaz.`);
    if (!confirmed) return;
    
    try {
        const contactIds = Array.from(selectedContactIds);
        const promises = contactIds.map(id => 
            fetch(`/api/v1/contacts/${id}`, { method: 'DELETE' })
        );
        
        const results = await Promise.all(promises);
        const successCount = results.filter(r => r.ok).length;
        
        if (successCount > 0) {
            if (typeof window.showToast === 'function') {
                window.showToast(`${successCount} kişi başarıyla silindi.`, 'success');
            }
            selectedContactIds.clear();
            loadContactsWithPagination(currentPage);
        } else {
            throw new Error('Hiçbir kişi silinemedi');
        }
    } catch (e) {
        console.error(e);
        if (typeof window.showToast === 'function') {
            window.showToast('Kişiler silinirken bir hata oluştu.', 'error');
        }
    }
}

// Delete all contacts
async function deleteAllContacts() {
    const confirmed = confirm(`TÜM KİŞİLERİ (${totalContacts} adet) silmek istediğinizden emin misiniz? Bu işlem geri alınamaz ve tüm verileriniz kaybolacak!`);
    if (!confirmed) return;
    
    const doubleConfirm = confirm('Bu işlem GERİ ALINAMAZ! Devam etmek istediğinizden EMİN MİSİNİZ?');
    if (!doubleConfirm) return;
    
    try {
        const res = await fetch('/api/v1/contacts/bulk-delete-all', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' }
        });
        
        if (!res.ok) {
            throw new Error('Toplu silme başarısız');
        }
        
        const data = await res.json();
        if (typeof window.showToast === 'function') {
            window.showToast(`${data.deleted_count || totalContacts} kişi başarıyla silindi.`, 'success');
        }
        
        selectedContactIds.clear();
        loadContactsWithPagination(1);
    } catch (e) {
        console.error(e);
        if (typeof window.showToast === 'function') {
            window.showToast('Tüm kişiler silinirken bir hata oluştu.', 'error');
        }
    }
}

// Override original loadContacts function
if (typeof window.loadContacts !== 'undefined') {
    window.originalLoadContacts = window.loadContacts;
}
window.loadContacts = loadContactsWithPagination;

// Initialize on page load
document.addEventListener('DOMContentLoaded', function() {
    initPagination();
});
