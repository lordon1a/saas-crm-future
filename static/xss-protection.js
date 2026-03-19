/**
 * XSS Protection Helper
 * Escapes HTML in user-provided content to prevent XSS attacks
 */

function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Make it globally available
window.escapeHtml = escapeHtml;
