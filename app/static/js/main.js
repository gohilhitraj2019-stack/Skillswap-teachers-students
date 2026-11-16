// Skill Swap Main JS
document.addEventListener('DOMContentLoaded', () => {
  // Automatically inject CSRF token into all POST forms
  const csrfMeta = document.querySelector('meta[name="csrf-token"]');
  if (csrfMeta) {
    const csrfToken = csrfMeta.getAttribute('content');
    document.querySelectorAll('form[method="POST"], form[method="post"]').forEach((form) => {
      if (!form.querySelector('input[name="csrf_token"]')) {
        const input = document.createElement('input');
        input.type = 'hidden';
        input.name = 'csrf_token';
        input.value = csrfToken;
        form.appendChild(input);
      }
    });
  }

  // Initialize Bootstrap tooltips if any
  const tooltipTriggerList = [].slice.call(document.querySelectorAll('[data-bs-toggle="tooltip"]'));
  tooltipTriggerList.map((el) => new bootstrap.Tooltip(el));

  // Auto-dismiss all popup alerts and notifications after 3 seconds (3000ms)
  const autoDismissAlert = (alertEl) => {
    if (!alertEl || alertEl.dataset.autoDismissSet === 'true') return;
    alertEl.dataset.autoDismissSet = 'true';

    setTimeout(() => {
      if (typeof bootstrap !== 'undefined' && bootstrap.Alert) {
        const bsAlert = bootstrap.Alert.getOrCreateInstance(alertEl);
        if (bsAlert) {
          bsAlert.close();
          return;
        }
      }
      alertEl.classList.remove('show');
      setTimeout(() => alertEl.remove(), 350);
    }, 3000);
  };

  const initDismissTimers = (root = document) => {
    const alerts = root.querySelectorAll('.alert-dismissible, .toast');
    alerts.forEach((alert) => autoDismissAlert(alert));
  };

  initDismissTimers();

  // Observe dynamically added popups or notifications to also dismiss in 3 seconds
  const observer = new MutationObserver((mutations) => {
    mutations.forEach((mutation) => {
      mutation.addedNodes.forEach((node) => {
        if (node.nodeType === Node.ELEMENT_NODE) {
          if (node.matches && (node.matches('.alert-dismissible') || node.matches('.toast'))) {
            autoDismissAlert(node);
          } else if (node.querySelectorAll) {
            initDismissTimers(node);
          }
        }
      });
    });
  });

  observer.observe(document.body, { childList: true, subtree: true });

  // Global toast notification helper
  window.showToast = (message, type = 'success') => {
    let container = document.getElementById('toast-notification-container');
    if (!container) {
      container = document.createElement('div');
      container.id = 'toast-notification-container';
      container.className = 'position-fixed top-0 end-0 p-3';
      container.style.zIndex = '9999';
      document.body.appendChild(container);
    }
    const toast = document.createElement('div');
    toast.className = `alert alert-${type} alert-dismissible fade show border shadow-sm mb-2`;
    toast.setAttribute('role', 'alert');
    toast.style.borderRadius = '8px';
    toast.innerHTML = `
      <div class="d-flex align-items-center gap-2 small">
        <i class="bi bi-info-circle-fill"></i>
        <div>${message}</div>
      </div>
      <button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close" style="padding: 0.75rem;"></button>
    `;
    container.appendChild(toast);
  };

  // Quick Demo Account Switcher for 1-click evaluation
  window.fillDemoLogin = (email, password) => {
    const emailInput = document.getElementById('login-email');
    const passInput = document.getElementById('login-password');
    if (emailInput && passInput) {
      emailInput.value = email;
      passInput.value = password;
      emailInput.focus();
    }
  };
});
