(function () {
  // ============================================
  // SEARCH LOGGER - Tracks user search behavior
  // ============================================
  class SearchLogger {
    constructor() {
      this.currentLogId = null;
      this.searchStartTime = null;
    }

    async logSearch(query, searchType, resultsCount = 0, entityType = null, filters = null) {
      if (!query || query.trim().length === 0) return;

      const duration = this.searchStartTime 
        ? Date.now() - this.searchStartTime 
        : null;

      try {
        const response = await fetch('/api/v1/search/log', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
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
        console.debug('Search logging failed:', error);
      }

      this.searchStartTime = null;
    }

    startSearch() {
      this.searchStartTime = Date.now();
    }

    async logClick(resultId, resultType) {
      if (!this.currentLogId) return;

      try {
        await fetch(`/api/v1/search/log/${this.currentLogId}/click`, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ result_id: resultId, result_type: resultType })
        });
      } catch (error) {
        console.debug('Click logging failed:', error);
      }

      this.currentLogId = null;
    }
  }

  // Initialize global search logger
  window.searchLogger = new SearchLogger();

  // ============================================
  // TOPBAR GLOBAL FUNCTIONALITY
  // ============================================
  var searchState = {
    panel: null,
    list: null,
    items: [],
    activeIndex: -1,
    open: false,
    loading: false,
    mode: "recent",
  };

  function renderAccountMenu(container, items) {
    if (!container) return;

    var groups = {};
    (items || []).forEach(function (item) {
      var key = item.group || "DIGER";
      if (!groups[key]) groups[key] = [];
      groups[key].push(item);
    });

    var html = Object.keys(groups)
      .map(function (group) {
        var links = groups[group]
          .map(function (item) {
            var isExit = (item.label || "").toLowerCase() === "cikis";
            var colorClasses = isExit
              ? "text-red-600 hover:bg-red-50"
              : "text-gray-700 hover:bg-gray-50";

            return (
              '<a href="' +
              (item.url || "#") +
              '" class="flex items-center gap-3 px-4 py-2.5 text-sm ' +
              colorClasses +
              ' transition-colors">' +
              '<i class="fas ' +
              (item.icon || "fa-circle") +
              ' w-4 text-center text-gray-500"></i>' +
              '<span>' +
              (item.label || "") +
              "</span>" +
              "</a>"
            );
          })
          .join("");

        return (
          '<div class="py-1">' +
          '<p class="px-4 py-1.5 text-[11px] font-bold text-gray-400 tracking-wide">' +
          group +
          "</p>" +
          links +
          "</div>"
        );
      })
      .join('<div class="border-t border-gray-100"></div>');

    container.innerHTML = html;
  }

  function escapeHtml(str) {
    return String(str || "")
      .replace(/&/g, "&amp;")
      .replace(/</g, "&lt;")
      .replace(/>/g, "&gt;")
      .replace(/\"/g, "&quot;")
      .replace(/'/g, "&#039;");
  }

  function iconForItem(item) {
    return item && item.icon ? item.icon : "fa-circle";
  }

  function rowHtml(item, index, isActive) {
    var activeCls = isActive ? "bg-slate-50" : "hover:bg-slate-50";
    var subtitle = item.subtitle
      ? '<div class="text-xs text-slate-500 truncate mt-0.5">' +
        escapeHtml(item.subtitle) +
        "</div>"
      : "";

    return (
      '<a href="' +
      escapeHtml(item.url || "#") +
      '" data-topbar-result-row data-result-index="' +
      index +
      '" class="flex items-start gap-3 px-4 py-2.5 transition-colors ' +
      activeCls +
      '">' +
      '<div class="w-6 h-6 rounded-md bg-slate-100 text-slate-600 flex items-center justify-center mt-0.5">' +
      '<i class="fas ' +
      iconForItem(item) +
      ' text-xs"></i>' +
      "</div>" +
      '<div class="min-w-0 flex-1">' +
      '<div class="text-sm font-semibold text-slate-800 truncate">' +
      escapeHtml(item.title || "") +
      "</div>" +
      subtitle +
      "</div>" +
      "</a>"
    );
  }

  function renderSearchPanel() {
    if (!searchState.list) return;

    if (searchState.loading) {
      searchState.list.innerHTML =
        '<div class="px-4 py-3 text-sm text-slate-500">Araniyor...</div>';
      return;
    }

    if (!searchState.items.length) {
      searchState.list.innerHTML =
        '<div class="px-4 py-3 text-sm text-slate-500">Sonuc bulunamadi</div>';
      return;
    }

    var title =
      searchState.mode === "recent" ? "Son goruntulenen" : "Arama sonuclari";

    var rows = searchState.items
      .map(function (item, index) {
        return rowHtml(item, index, index === searchState.activeIndex);
      })
      .join("");

    searchState.list.innerHTML =
      '<div class="px-4 py-2.5 text-sm font-semibold text-slate-600 border-b border-slate-100 bg-slate-50">' +
      title +
      "</div>" +
      '<div class="max-h-[420px] overflow-y-auto">' +
      rows +
      "</div>";
  }

  function showSearchPanel() {
    if (!searchState.panel) return;
    searchState.open = true;
    searchState.panel.classList.remove("hidden");
  }

  function hideSearchPanel() {
    if (!searchState.panel) return;
    searchState.open = false;
    searchState.panel.classList.add("hidden");
    searchState.activeIndex = -1;
  }

  function setActiveResult(index) {
    if (!searchState.items.length) return;
    var max = searchState.items.length - 1;
    if (index < 0) index = max;
    if (index > max) index = 0;
    searchState.activeIndex = index;
    renderSearchPanel();
  }

  async function fetchSearchResults(query) {
    searchState.loading = true;
    renderSearchPanel();
    
    const searchStartTime = Date.now();

    try {
      var url = "/api/settings/topbar/search?q=" + encodeURIComponent(query || "");
      var res = await fetch(url);
      if (!res.ok) throw new Error("search_failed");
      var data = await res.json();

      searchState.items = data.items || [];
      searchState.mode = data.mode || "search";
      searchState.activeIndex = -1;
      
      // Log search if query exists and searchLogger is available
      if (query && query.trim() && window.searchLogger) {
        const searchDuration = Date.now() - searchStartTime;
        window.searchLogger.logSearch(
          query.trim(),
          'global',
          searchState.items.length,
          null,
          null
        );
      }
    } catch (err) {
      console.error("Topbar arama hatasi:", err);
      searchState.items = [];
      searchState.mode = "search";
      searchState.activeIndex = -1;
    } finally {
      searchState.loading = false;
      renderSearchPanel();
    }
  }

  function debounce(fn, delay) {
    var timer = null;
    return function () {
      var args = arguments;
      clearTimeout(timer);
      timer = setTimeout(function () {
        fn.apply(null, args);
      }, delay);
    };
  }

  function setupSearch(searchInput) {
    if (!searchInput) return;

    var wrapper = searchInput.closest(".relative") || searchInput.parentElement;
    if (!wrapper) return;

    // Ensure search area does not feel glued to the left edge.
    wrapper.classList.add("ml-1", "md:ml-2");

    var panel = document.createElement("div");
    panel.setAttribute("data-topbar-search-panel", "true");
    panel.className =
      "hidden absolute left-0 top-[calc(100%+10px)] w-full max-w-lg bg-white border border-slate-200 rounded-xl shadow-2xl z-50 overflow-hidden";

    var list = document.createElement("div");
    panel.appendChild(list);
    wrapper.appendChild(panel);

    searchState.panel = panel;
    searchState.list = list;

    var debouncedSearch = debounce(function (value) {
      fetchSearchResults(value || "");
    }, 220);

    searchInput.addEventListener("focus", function () {
      showSearchPanel();
      debouncedSearch(searchInput.value || "");
    });

    searchInput.addEventListener("input", function (e) {
      showSearchPanel();
      debouncedSearch(e.target.value || "");
    });

    searchInput.addEventListener("keydown", function (e) {
      if (!searchState.open) return;

      if (e.key === "ArrowDown") {
        e.preventDefault();
        setActiveResult(searchState.activeIndex + 1);
      }

      if (e.key === "ArrowUp") {
        e.preventDefault();
        setActiveResult(searchState.activeIndex - 1);
      }

      if (e.key === "Enter" && searchState.activeIndex >= 0) {
        e.preventDefault();
        var active = searchState.items[searchState.activeIndex];
        if (active && active.url) {
          window.location.href = active.url;
        }
      }

      if (e.key === "Escape") {
        hideSearchPanel();
      }
    });

    panel.addEventListener("click", function (e) {
      e.stopPropagation();
    });

    document.addEventListener("click", function (e) {
      if (!wrapper.contains(e.target)) {
        hideSearchPanel();
      }
    });
  }

  async function initGlobalTopbar() {
    var search = document.querySelector("[data-topbar-search]");
    var avatar = document.querySelector("[data-topbar-avatar]");
    var name = document.querySelector("[data-topbar-name]");
    var menuButton = document.querySelector("[data-topbar-menu-button]");
    var menu = document.querySelector("[data-topbar-menu]");
    var menuContent = document.querySelector("[data-topbar-menu-content]");

    // Inject Assistant Button globally
    if (menuButton) {
      var wrapper = menuButton.closest('.relative') || menuButton.parentNode;
      if (wrapper && wrapper.parentNode) {
        if (!document.getElementById('global-assistant-btn')) {
          var asstHtml = document.createElement('div');
          asstHtml.innerHTML = '<button id="global-assistant-btn" onclick="if(typeof toggleAISidebar===\'function\'){toggleAISidebar()}else{window.location.href=\'/assistant\'}" class="h-9 px-3 mx-2 flex items-center justify-center gap-2 hover:bg-slate-100 rounded-lg transition-all cursor-pointer" title="Yapay Zeka Asistanı"><span class="text-[15px]">\ud83d\udc27</span><span class="hidden md:inline text-[14px] font-semibold text-transparent bg-clip-text bg-gradient-to-r from-blue-500 via-purple-500 to-pink-500 tracking-wide text-center">Asistan</span></button>';
          wrapper.parentNode.insertBefore(asstHtml.firstChild, wrapper);
        }
      }
    }

    if (!menuButton || !menu || !menuContent) {
      return;
    }

    try {
      var res = await fetch("/api/settings/topbar");
      if (res.ok) {
        var data = await res.json();

        if (search && data.search_placeholder) {
          search.placeholder = data.search_placeholder;
        }
        if (avatar && data.user && data.user.initials) {
          avatar.textContent = data.user.initials;
        }
        if (name && data.user && data.user.name) {
          name.textContent = data.user.name;
        }

        renderAccountMenu(menuContent, data.account_menu || []);
      }
    } catch (err) {
      console.error("Topbar config yuklenemedi:", err);
    }

    setupSearch(search);

    menuButton.addEventListener("click", function (e) {
      e.stopPropagation();
      menu.classList.toggle("hidden");
    });

    menu.addEventListener("click", function (e) {
      e.stopPropagation();
    });

    document.addEventListener("click", function () {
      menu.classList.add("hidden");
    });

    document.addEventListener("keydown", function (e) {
      if (e.key === "Escape") {
        menu.classList.add("hidden");
        hideSearchPanel();
      }
    });
  }

  document.addEventListener("DOMContentLoaded", initGlobalTopbar);
})();
