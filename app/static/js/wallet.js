// Skill Swap Wallet & Payment Handler
document.addEventListener('DOMContentLoaded', () => {
  const packageCards = document.querySelectorAll('.package-select-card');
  const packageIdInput = document.getElementById('selected-package-id');

  packageCards.forEach((card) => {
    card.addEventListener('click', () => {
      packageCards.forEach((c) => c.classList.remove('border-primary', 'bg-light'));
      card.classList.add('border-primary', 'bg-light');
      const pid = card.getAttribute('data-package-id');
      if (packageIdInput) packageIdInput.value = pid;
    });
  });
});
