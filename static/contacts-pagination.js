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
    
    // Initialize global variables
    window.currentPage = 1;
    window.totalPages = 1;
    window.totalContacts = 0;
    window.perPage = 50;
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

// Update pagination UI
function updatePaginationUI() {
    const paginationBar = document.getElementById('paginationBar');
    const paginationInfo = document.getElementById('paginationInfo');
    const pageNumbers = document.getElementById('pageNumbers');
    const prevBtn = document.getElementById('prevPageBtn');
    const nextBtn = document.getElementById('nextPageBtn');
    
    if (!paginationBar) return;
    
    // Use global variables
    currentPage = window.currentPage || 1;
    totalPages = window.totalPages || 1;
    totalContacts = window.totalContacts || 0;
    perPage = window.perPage || 50;
    
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
    if (page < 1 || page > (window.totalPages || 1) || page === (window.currentPage || 1)) return;
    
    // Clear selections on page change
    selectedContactIds.clear();
    updateBulkActionsBar();
    
    // Call the original loadContacts function with page parameter
    if (typeof loadContacts === 'function') {
        loadContacts(page);
    }
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
            if (typeof showToast === 'function') {
                showToast(`${successCount} kişi başarıyla silindi.`, 'success');
            }
            selectedContactIds.clear();
            if (typeof loadContacts === 'function') {
                loadContacts(window.currentPage || 1);
            }
        } else {
            throw new Error('Hiçbir kişi silinemedi');
        }
    } catch (e) {
        console.error(e);
        if (typeof showToast === 'function') {
            showToast('Kişiler silinirken bir hata oluştu.', 'error');
        }
    }
}

// Delete all contacts
async function deleteAllContacts() {
    const totalCount = window.totalContacts || 0;
    const confirmed = confirm(`TÜM KİŞİLERİ (${totalCount} adet) silmek istediğinizden emin misiniz? Bu işlem geri alınamaz ve tüm verileriniz kaybolacak!`);
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
        if (typeof showToast === 'function') {
            showToast(`${data.deleted_count || totalCount} kişi başarıyla silindi.`, 'success');
        }
        
        selectedContactIds.clear();
        if (typeof loadContacts === 'function') {
            loadContacts(1);
        }
    } catch (e) {
        console.error(e);
        if (typeof showToast === 'function') {
            showToast('Tüm kişiler silinirken bir hata oluştu.', 'error');
        }
    }
}

// Initialize on page load
document.addEventListener('DOMContentLoaded', function() {
    initPagination();
});
