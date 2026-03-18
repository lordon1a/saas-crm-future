/**
 * Super Admin Panel - Shared API Utilities
 */

// API Base URL - read from environment or default to relative path
const API_BASE_URL = window.SUPER_ADMIN_API_URL || '';

/**
 * Check if user is authenticated
 * Redirects to login page if no token found
 */
function checkAuth() {
    const token = localStorage.getItem('super_admin_token');
    
    if (!token) {
        window.location.href = 'index.html';
        return false;
    }
    
    return true;
}

/**
 * Make authenticated API call
 * @param {string} endpoint - API endpoint (e.g., '/tenants')
 * @param {object} options - Fetch options (method, body, etc.)
 * @returns {Promise<any>} - Response data
 */
async function apiCall(endpoint, options = {}) {
    const token = localStorage.getItem('super_admin_token');
    
    if (!token) {
        window.location.href = 'index.html';
        throw new Error('No authentication token');
    }
    
    const defaultOptions = {
        headers: {
            'Authorization': `Bearer ${token}`,
            'Content-Type': 'application/json'
        }
    };
    
    const mergedOptions = {
        ...defaultOptions,
        ...options,
        headers: {
            ...defaultOptions.headers,
            ...(options.headers || {})
        }
    };
    
    try {
        const response = await fetch(`${API_BASE_URL}${endpoint}`, mergedOptions);
        
        // Handle 401 - token expired or invalid
        if (response.status === 401) {
            localStorage.removeItem('super_admin_token');
            localStorage.removeItem('super_admin_user');
            window.location.href = 'index.html';
            throw new Error('Authentication expired');
        }
        
        const data = await response.json();
        
        if (!response.ok) {
            throw new Error(data.error || `HTTP ${response.status}`);
        }
        
        return data;
        
    } catch (error) {
        console.error('API call failed:', error);
        throw error;
    }
}

/**
 * Logout user
 * Clears local storage and redirects to login
 */
function logout() {
    localStorage.removeItem('super_admin_token');
    localStorage.removeItem('super_admin_user');
    window.location.href = 'index.html';
}

/**
 * Format date to readable string
 * @param {string} dateString - ISO date string
 * @returns {string} - Formatted date
 */
function formatDate(dateString) {
    const date = new Date(dateString);
    return date.toLocaleDateString('en-US', {
        year: 'numeric',
        month: 'short',
        day: 'numeric'
    });
}

/**
 * Format datetime to readable string
 * @param {string} dateString - ISO date string
 * @returns {string} - Formatted datetime
 */
function formatDateTime(dateString) {
    const date = new Date(dateString);
    return date.toLocaleString('en-US', {
        year: 'numeric',
        month: 'short',
        day: 'numeric',
        hour: '2-digit',
        minute: '2-digit'
    });
}

/**
 * Format number with thousands separator
 * @param {number} num - Number to format
 * @returns {string} - Formatted number
 */
function formatNumber(num) {
    return num.toLocaleString('en-US');
}
