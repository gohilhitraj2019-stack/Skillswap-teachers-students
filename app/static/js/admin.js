/**
 * SkillSwap Professional Admin Sidebar & Layout Controller
 * Handles sidebar collapse/expand, localStorage persistence, tooltips,
 * mobile off-canvas drawer, search shortcuts, and Lucide icons.
 */

(function () {
  'use strict';

  const STORAGE_KEY = 'skillswap_admin_sidebar_collapsed';

  // Restore collapsed state immediately
  function getSidebarPreference() {
    return localStorage.getItem(STORAGE_KEY) === 'true';
  }

  function setSidebarPreference(isCollapsed) {
    localStorage.setItem(STORAGE_KEY, isCollapsed ? 'true' : 'false');
  }

  function applySidebarState(isCollapsed) {
    if (isCollapsed) {
      document.body.classList.add('sidebar-collapsed');
    } else {
      document.body.classList.remove('sidebar-collapsed');
    }
    updateTooltips(isCollapsed);
    if (window.lucide) {
      window.lucide.createIcons();
    }
  }

  // Tooltips for collapsed state
  let tooltipInstances = [];

  function updateTooltips(isCollapsed) {
    // Dispose old tooltips
    tooltipInstances.forEach(t => t.dispose());
    tooltipInstances = [];

    if (isCollapsed && window.bootstrap && window.bootstrap.Tooltip) {
      const navItems = document.querySelectorAll('.admin-nav-item');
      navItems.forEach(el => {
        const title = el.getAttribute('data-nav-title') || el.querySelector('.admin-nav-label')?.textContent?.trim();
        if (title) {
          el.setAttribute('title', title);
          el.setAttribute('data-bs-placement', 'right');
          const instance = new window.bootstrap.Tooltip(el, { trigger: 'hover' });
          tooltipInstances.push(instance);
        }
      });
    } else {
      document.querySelectorAll('.admin-nav-item').forEach(el => {
        el.removeAttribute('title');
      });
    }
  }

  document.addEventListener('DOMContentLoaded', function () {
    // Initialize icons
    if (window.lucide) {
      window.lucide.createIcons();
    }

    // Initial state from preference
    const isCollapsed = getSidebarPreference();
    applySidebarState(isCollapsed);

    // Desktop Collapse Buttons (in top header and bottom of sidebar)
    const toggleBtns = document.querySelectorAll('.js-sidebar-toggle');
    toggleBtns.forEach(btn => {
      btn.addEventListener('click', function (e) {
        e.preventDefault();
        const currentlyCollapsed = document.body.classList.contains('sidebar-collapsed');
        const nextState = !currentlyCollapsed;
        applySidebarState(nextState);
        setSidebarPreference(nextState);
      });
    });

    // Mobile Drawer Hamburger and Close Buttons
    const mobileToggleBtn = document.getElementById('mobileSidebarToggle');
    const mobileCloseBtn = document.getElementById('mobileSidebarClose');
    const backdrop = document.getElementById('sidebarBackdrop');

    function openMobileDrawer() {
      document.body.classList.add('sidebar-mobile-open');
    }

    function closeMobileDrawer() {
      document.body.classList.remove('sidebar-mobile-open');
    }

    if (mobileToggleBtn) {
      mobileToggleBtn.addEventListener('click', function (e) {
        e.preventDefault();
        openMobileDrawer();
      });
    }

    if (mobileCloseBtn) {
      mobileCloseBtn.addEventListener('click', function (e) {
        e.preventDefault();
        closeMobileDrawer();
      });
    }

    if (backdrop) {
      backdrop.addEventListener('click', function () {
        closeMobileDrawer();
      });
    }

    // Auto-close mobile drawer when navigation links are clicked
    document.querySelectorAll('.admin-nav-item').forEach(link => {
      link.addEventListener('click', function () {
        if (window.innerWidth < 992) {
          closeMobileDrawer();
        }
      });
    });

    // Close mobile drawer on desktop resize
    window.addEventListener('resize', function () {
      if (window.innerWidth >= 992 && document.body.classList.contains('sidebar-mobile-open')) {
        closeMobileDrawer();
      }
    });

    // Keyboard Shortcut (Cmd+K or Ctrl+K) to focus search
    const searchInput = document.getElementById('adminHeaderSearch');
    if (searchInput) {
      window.addEventListener('keydown', function (e) {
        if ((e.metaKey || e.ctrlKey) && e.key.toLowerCase() === 'k') {
          e.preventDefault();
          searchInput.focus();
          searchInput.select();
        }
      });

      // Quick filter on Enter
      searchInput.addEventListener('keydown', function (e) {
        if (e.key === 'Enter') {
          const query = searchInput.value.trim().toLowerCase();
          if (!query) return;

          // Quick routes lookup
          if (query.includes('user') || query.includes('student')) {
            window.location.href = searchInput.getAttribute('data-users-url');
          } else if (query.includes('teach') || query.includes('instructor') || query.includes('apply')) {
            window.location.href = searchInput.getAttribute('data-teachers-url');
          } else if (query.includes('book') || query.includes('session') || query.includes('class')) {
            window.location.href = searchInput.getAttribute('data-bookings-url');
          } else if (query.includes('withdraw') || query.includes('payout')) {
            window.location.href = searchInput.getAttribute('data-withdrawals-url');
          } else if (query.includes('setting') || query.includes('commission') || query.includes('rate')) {
            window.location.href = searchInput.getAttribute('data-settings-url');
          } else if (query.includes('audit') || query.includes('log') || query.includes('security')) {
            window.location.href = searchInput.getAttribute('data-audit-url');
          } else if (query.includes('ledger') || query.includes('wallet') || query.includes('tx')) {
            window.location.href = searchInput.getAttribute('data-ledger-url');
          }
        }
      });
    }
  });
})();
