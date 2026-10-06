(() => {
  'use strict';
  const trigger = document.getElementById('register-trigger');
  const box = document.getElementById('register-box');
  const closeBtn = document.getElementById('register-close');

  const howBtn = document.getElementById('how-to-connect-btn');
  const modal = document.getElementById('connect-modal');
  const modalClose = document.getElementById('modal-close');
  const modalDone = document.getElementById('modal-done');
  const copyIpBtn = document.getElementById('copy-ip-btn');
  const copyStatus = document.getElementById('copy-status');
  const ipCode = document.getElementById('server-ip-code');

  if (trigger && box) {
    const show = () => {
      box.classList.remove('hidden');
      box.setAttribute('aria-hidden', 'false');
      if (closeBtn) closeBtn.focus();
    };

    const hide = () => {
      box.classList.add('hidden');
      box.setAttribute('aria-hidden', 'true');
      trigger.focus();
    };

    trigger.addEventListener('click', () => {
      if (box.classList.contains('hidden')) {
        show();
      } else {
        hide();
      }
    });

    if (closeBtn) {
      closeBtn.addEventListener('click', hide);
    }
  }

  // How to connect modal
  if (modal) {
    const openModal = () => {
      modal.classList.remove('hidden');
      modal.setAttribute('aria-hidden', 'false');
    };

    const closeModal = () => {
      modal.classList.add('hidden');
      modal.setAttribute('aria-hidden', 'true');
    };

    if (howBtn) howBtn.addEventListener('click', openModal);
    if (modalClose) modalClose.addEventListener('click', closeModal);
    if (modalDone) modalDone.addEventListener('click', closeModal);

    modal.addEventListener('click', (e) => {
      if (e.target === modal) closeModal();
    });

    document.addEventListener('keydown', (e) => {
      if (e.key === 'Escape') {
        if (!modal.classList.contains('hidden')) closeModal();
        if (box && !box.classList.contains('hidden')) box.classList.add('hidden');
      }
    });

    if (copyIpBtn && ipCode) {
      copyIpBtn.addEventListener('click', () => {
        navigator.clipboard.writeText(ipCode.textContent.trim()).then(() => {
          copyStatus.textContent = '✅ Copied / Скопировано!';
          copyIpBtn.textContent = 'Copied!';
          setTimeout(() => {
            copyStatus.textContent = '';
            copyIpBtn.textContent = '📋 Copy';
          }, 2500);
        }).catch(() => {
          copyStatus.textContent = 'Ctrl+C to copy';
        });
      });
    }
  }
})();
