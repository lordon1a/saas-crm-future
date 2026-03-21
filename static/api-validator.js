/**
 * API Endpoint Validator
 * Her API çağrısından önce endpoint'in varlığını ve formatını kontrol eder
 */

class APIValidator {
    constructor() {
        // Bilinen endpoint'lerin listesi
        this.knownEndpoints = {
            // Contacts
            'GET /api/v1/contacts': true,
            'GET /api/v1/contacts/:id': true,
            'POST /api/v1/contacts': true,
            'PATCH /api/v1/contacts/:id': true,
            'DELETE /api/v1/contacts/:id': true,
            'POST /api/v1/contacts/:id/restore': true,
            'GET /api/v1/contacts/export': true,
            'POST /api/v1/contacts/import': true,
            'POST /api/v1/contacts/bulk-update': true,
            'POST /api/v1/contacts/bulk-delete': true,
            'POST /api/v1/contacts/bulk-delete-all': true,
            'POST /api/v1/contacts/reorder': true,
            'POST /api/v1/contacts/:id/toggle-star': true,
            'POST /api/v1/contacts/export-filtered': true,
            
            // Saved Filters
            'POST /api/v1/contacts/filters': true,
            'GET /api/v1/contacts/filters': true,
            'DELETE /api/v1/contacts/filters/:id': true,
            'POST /api/v1/contacts/filters/:id/share': true,
            
            // Companies
            'GET /api/v1/companies': true,
            'GET /api/v1/companies/:id': true,
            'POST /api/v1/companies': true,
            'PATCH /api/v1/companies/:id': true,
            'DELETE /api/v1/companies/:id': true,
            'POST /api/v1/companies/:id/restore': true,
            'GET /api/v1/companies/export': true,
            'POST /api/v1/companies/bulk-delete-all': true,
            'POST /api/v1/companies/reorder': true,
            
            // Custom Fields
            'GET /api/v1/custom-fields/:entity_type': true,
            'POST /api/v1/custom-fields': true,
            'PATCH /api/v1/custom-fields/:id': true,
            'DELETE /api/v1/custom-fields/:id': true,
            
            // User Preferences
            'GET /api/v1/user-preferences/contacts-columns': true,
            'POST /api/v1/user-preferences/contacts-columns': true,
            'GET /api/v1/user-preferences/contacts-column-widths': true,
            'POST /api/v1/user-preferences/contacts-column-widths': true,
            
            // Pipeline
            'GET /api/v1/pipeline/stages': true,
            'POST /api/v1/pipeline/stages': true,
            'PATCH /api/v1/pipeline/stages/:id': true,
            'DELETE /api/v1/pipeline/stages/:id': true,
            'POST /api/v1/pipeline/stages/reorder': true,
            
            // Tasks
            'GET /api/v1/tasks': true,
            'POST /api/v1/tasks': true,
            'PATCH /api/v1/tasks/:id': true,
            'DELETE /api/v1/tasks/:id': true,
            'POST /api/v1/tasks/:id/complete': true
        };
        
        this.validationEnabled = true; // Development'ta true, production'da false yapılabilir
    }
    
    /**
     * Endpoint'i normalize et (ID'leri :id ile değiştir)
     */
    normalizeEndpoint(url) {
        // Query string'i kaldır
        const urlWithoutQuery = url.split('?')[0];
        
        // Numeric ID'leri :id ile değiştir
        return urlWithoutQuery.replace(/\/\d+/g, '/:id');
    }
    
    /**
     * API çağrısını validate et
     */
    validate(method, url) {
        if (!this.validationEnabled) return { valid: true };
        
        const normalizedUrl = this.normalizeEndpoint(url);
        const key = `${method.toUpperCase()} ${normalizedUrl}`;
        
        if (!this.knownEndpoints[key]) {
            console.warn(`⚠️ API Endpoint Warning: ${key} is not in known endpoints list!`);
            console.warn(`   This might be a typo or missing backend endpoint.`);
            console.warn(`   Known endpoints:`, Object.keys(this.knownEndpoints).filter(k => k.startsWith(method.toUpperCase())));
            
            return {
                valid: false,
                warning: `Endpoint ${key} not found in known endpoints`,
                suggestions: this.findSimilarEndpoints(key)
            };
        }
        
        return { valid: true };
    }
    
    /**
     * Benzer endpoint'leri bul (typo kontrolü için)
     */
    findSimilarEndpoints(key) {
        const [method, path] = key.split(' ');
        const suggestions = [];
        
        for (const endpoint in this.knownEndpoints) {
            const [endpointMethod, endpointPath] = endpoint.split(' ');
            
            // Aynı method ve benzer path
            if (endpointMethod === method && this.similarity(path, endpointPath) > 0.6) {
                suggestions.push(endpoint);
            }
        }
        
        return suggestions;
    }
    
    /**
     * İki string arasındaki benzerliği hesapla (Levenshtein distance)
     */
    similarity(s1, s2) {
        const longer = s1.length > s2.length ? s1 : s2;
        const shorter = s1.length > s2.length ? s2 : s1;
        
        if (longer.length === 0) return 1.0;
        
        const editDistance = this.levenshteinDistance(longer, shorter);
        return (longer.length - editDistance) / longer.length;
    }
    
    levenshteinDistance(s1, s2) {
        const costs = [];
        for (let i = 0; i <= s1.length; i++) {
            let lastValue = i;
            for (let j = 0; j <= s2.length; j++) {
                if (i === 0) {
                    costs[j] = j;
                } else if (j > 0) {
                    let newValue = costs[j - 1];
                    if (s1.charAt(i - 1) !== s2.charAt(j - 1)) {
                        newValue = Math.min(Math.min(newValue, lastValue), costs[j]) + 1;
                    }
                    costs[j - 1] = lastValue;
                    lastValue = newValue;
                }
            }
            if (i > 0) costs[s2.length] = lastValue;
        }
        return costs[s2.length];
    }
    
    /**
     * Yeni endpoint ekle (runtime'da öğrenme için)
     */
    addEndpoint(method, url) {
        const normalizedUrl = this.normalizeEndpoint(url);
        const key = `${method.toUpperCase()} ${normalizedUrl}`;
        this.knownEndpoints[key] = true;
        console.log(`✅ Added new endpoint to validator: ${key}`);
    }
}

// Global instance
const apiValidator = new APIValidator();

/**
 * Fetch wrapper with validation
 */
window.validatedFetch = async function(url, options = {}) {
    const method = options.method || 'GET';
    
    // Validate endpoint
    const validation = apiValidator.validate(method, url);
    
    if (!validation.valid) {
        console.error('❌ API Validation Failed:', validation.warning);
        if (validation.suggestions.length > 0) {
            console.log('💡 Did you mean one of these?', validation.suggestions);
        }
    }
    
    // Make the actual fetch call
    return fetch(url, options);
};

// Export for use in other modules
window.apiValidator = apiValidator;

console.log('✅ API Validator loaded. Use validatedFetch() instead of fetch() for automatic validation.');
