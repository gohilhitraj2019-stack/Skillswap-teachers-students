// Skill Swap Main JS
document.addEventListener('DOMContentLoaded', () => {
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
