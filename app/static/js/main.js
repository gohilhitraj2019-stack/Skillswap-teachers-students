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
