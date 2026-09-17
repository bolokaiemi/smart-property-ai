// ai-assistant-modal.js
// Handles opening and closing the AI assistant modal overlay
document.addEventListener('DOMContentLoaded', () => {
  const launcher = document.getElementById('assistant-launcher');
  const modal = document.getElementById('ai-assistant-modal');
  const closeBtn = document.getElementById('ai-assistant-modal-close');

  if (!launcher || !modal) return;

  const openModal = (e) => {
    e.preventDefault();
    modal.classList.remove('hidden');
    // Focus the iframe for accessibility
    const iframe = document.getElementById('ai-assistant-iframe');
    if (iframe) iframe.focus();
  };

  const closeModal = (e) => {
    e.preventDefault();
    modal.classList.add('hidden');
  };

  launcher.addEventListener('click', openModal);
  if (closeBtn) closeBtn.addEventListener('click', closeModal);

  // Close on overlay click (outside content)
  modal.addEventListener('click', (e) => {
    if (e.target === modal) closeModal(e);
  });

  // Close on Escape key
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && !modal.classList.contains('hidden')) {
      closeModal(e);
    }
  });
});
