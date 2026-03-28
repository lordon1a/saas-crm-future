/**
 * Sidebar Early Init - Must be loaded synchronously in <head> to prevent flash
 * This runs BEFORE the first paint to set correct sidebar width
 */
(function() {
  // Check if sidebar should be collapsed
  if (localStorage.getItem('sidebarCollapsed') === 'true') {
    // Add class to html element BEFORE any rendering
    document.documentElement.classList.add('sidebar-collapsed');
  }
})();
