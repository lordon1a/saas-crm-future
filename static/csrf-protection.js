// CSRF Protection - Global Fetch Interceptor
// This file must be loaded BEFORE any other JavaScript that makes API calls

(function() {
    'use strict';
    
    // Get CSRF token from meta tag
    function getCSRFToken() {
        const meta = document.querySelector('meta[name="csrf-token"]');
        return meta ? meta.content : '';
    }
    
    // Wrap native fetch to automatically add CSRF token
    const originalFetch = window.fetch;
    
    window.fetch = function(url, options = {}) {
        // Only add CSRF token to same-origin requests
        const isSameOrigin = !url.startsWith('http') || url.startsWith(window.location.origin);
        
        if (isSameOrigin) {
            const csrfToken = getCSRFToken();
            
            if (csrfToken) {
                // Initialize headers if not present
                options.headers = options.headers || {};
                
                // Add CSRF token if not already present
                if (!options.headers['X-CSRFToken'] && !options.headers['X-CSRF-Token']) {
                    if (options.headers instanceof Headers) {
                        options.headers.set('X-CSRFToken', csrfToken);
                    } else {
                        options.headers['X-CSRFToken'] = csrfToken;
                    }
                }
            }
        }
        
        return originalFetch.call(this, url, options);
    };
    
    console.log('✅ CSRF Protection initialized');
})();
