/**
 * Search Logger - Tracks user search behavior
 * Minimal implementation for search analytics
 */

class SearchLogger {
    constructor() {
        this.currentLogId = null;
        this.searchStartTime = null;
    }

    /**
     * Log a search query
     * @param {string} query - Search query
     * @param {string} searchType - Type: 'contact', 'company', 'deal', 'global'
     * @param {number} resultsCount - Number of results
     * @param {string} entityType - Optional entity type
     * @param {object} filters - Optional filters object
     */
    async logSearch(query, searchType, resultsCount = 0, entityType = null, filters = null) {
        if (!query || query.trim().length === 0) return;

        const duration = this.searchStartTime 
            ? Date.now() - this.searchStartTime 
            : null;

        try {
            const response = await fetch('/api/v1/search/log', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    search_query: query.trim(),
                    search_type: searchType,
                    entity_type: entityType,
                    results_count: resultsCount,
                    search_duration_ms: duration,
                    filters_applied: filters ? JSON.stringify(filters) : null
                })
            });

            if (response.ok) {
                const data = await response.json();
                this.currentLogId = data.log_id;
            }
        } catch (error) {
            // Silent fail - don't break user experience
            console.debug('Search logging failed:', error);
        }

        this.searchStartTime = null;
    }

    /**
     * Mark search start time (for duration tracking)
     */
    startSearch() {
        this.searchStartTime = Date.now();
    }

    /**
     * Log when user clicks on a search result
     * @param {number} resultId - ID of clicked result
     * @param {string} resultType - Type: 'contact', 'company', 'deal'
     */
    async logClick(resultId, resultType) {
        if (!this.currentLogId) return;

        try {
            await fetch(`/api/v1/search/log/${this.currentLogId}/click`, {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json'
                },
                body: JSON.stringify({
                    result_id: resultId,
                    result_type: resultType
                })
            });
        } catch (error) {
            console.debug('Click logging failed:', error);
        }

        this.currentLogId = null;
    }

    /**
     * Get user's search history
     * @param {number} limit - Number of results
     * @param {string} entityType - Optional filter
     */
    async getHistory(limit = 20, entityType = null) {
        try {
            const params = new URLSearchParams({ limit });
            if (entityType) params.append('entity_type', entityType);

            const response = await fetch(`/api/v1/search/history?${params}`);
            if (response.ok) {
                return await response.json();
            }
        } catch (error) {
            console.error('Failed to get search history:', error);
        }
        return { history: [], count: 0 };
    }

    /**
     * Get popular searches
     * @param {number} days - Days to look back
     * @param {number} limit - Number of results
     */
    async getPopular(days = 7, limit = 10) {
        try {
            const params = new URLSearchParams({ days, limit });
            const response = await fetch(`/api/v1/search/popular?${params}`);
            if (response.ok) {
                return await response.json();
            }
        } catch (error) {
            console.error('Failed to get popular searches:', error);
        }
        return { popular_searches: [], count: 0 };
    }
}

// Global instance
window.searchLogger = new SearchLogger();
