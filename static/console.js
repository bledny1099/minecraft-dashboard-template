(() => {
  'use strict';

  const logStream = document.getElementById('log-stream');
  const connStatus = document.getElementById('conn-status');
  const autoscrollToggle = document.getElementById('autoscroll-toggle');
  const clearBtn = document.getElementById('clear-btn');
  const pauseBtn = document.getElementById('pause-btn');
  const logFilter = document.getElementById('log-filter');
  const clearFilterBtn = document.getElementById('clear-filter-btn');
  const cmdForm = document.getElementById('cmd-form');
  const cmdInput = document.getElementById('cmd-input');
  const quickButtons = document.querySelectorAll('.quick-chip');

  // How to connect modal elements
  const howBtn = document.getElementById('how-to-connect-btn');
  const modal = document.getElementById('connect-modal');
  const modalClose = document.getElementById('modal-close');
  const modalDone = document.getElementById('modal-done');
  const copyIpBtn = document.getElementById('copy-ip-btn');
  const copyStatus = document.getElementById('copy-status');
  const ipCode = document.getElementById('server-ip-code');

  let isPaused = false;
  let eventSource = null;
  let commandHistory = [];
  let historyIndex = -1;
  const maxLines = 1000;

  // Format log lines with color coding
  function formatLogLine(rawText) {
    const div = document.createElement('div');
    div.className = 'log-line';

    let text = rawText;
    let lineType = 'info';

    if (text.includes('/WARN') || text.includes('WARN]:') || text.includes('WARNING:')) {
      lineType = 'warn';
    } else if (text.includes('/ERROR') || text.includes('ERROR]:') || text.includes('Exception') || text.includes('Error')) {
      lineType = 'error';
    } else if (text.includes('issued server command:') || text.includes('ServerCommandEvent')) {
      lineType = 'cmd';
    } else if (text.includes('<') && text.includes('>') && !text.includes('ServerLevel[')) {
      lineType = 'chat';
    }

    div.classList.add('log-' + lineType);

    // Escape HTML
    div.textContent = text;

    // Filter check
    const filterQuery = (logFilter.value || '').trim().toLowerCase();
    if (filterQuery && !text.toLowerCase().includes(filterQuery)) {
      div.style.display = 'none';
    }

    return div;
  }

  function appendLog(rawText) {
    if (isPaused) return;

    const line = formatLogLine(rawText);
    logStream.appendChild(line);

    // Trim old lines
    if (logStream.children.length > maxLines) {
      logStream.removeChild(logStream.firstChild);
    }

    if (autoscrollToggle.checked) {
      logStream.scrollTop = logStream.scrollHeight;
    }
  }

  function applyFilter() {
    const q = (logFilter.value || '').trim().toLowerCase();
    const children = logStream.children;
    for (let i = 0; i < children.length; i++) {
      const el = children[i];
      if (!q || el.textContent.toLowerCase().includes(q)) {
        el.style.display = '';
      } else {
        el.style.display = 'none';
      }
    }
    if (autoscrollToggle.checked) {
      logStream.scrollTop = logStream.scrollHeight;
    }
  }

  // Connect to SSE stream
  function startStream() {
    if (eventSource) {
      eventSource.close();
    }

    connStatus.textContent = '🟡 Connecting...';
    connStatus.className = 'pill';

    eventSource = new EventSource('/api/console/stream');

    eventSource.onopen = () => {
      connStatus.textContent = '🟢 Live';
      connStatus.className = 'pill ok';
    };

    eventSource.onmessage = (e) => {
      if (!e.data) return;
      appendLog(e.data);
    };

    eventSource.onerror = () => {
      connStatus.textContent = '🔴 Reconnecting...';
      connStatus.className = 'pill off';
    };
  }

  // Clear button
  clearBtn.addEventListener('click', () => {
    logStream.innerHTML = '';
  });

  // Pause button
  pauseBtn.addEventListener('click', () => {
    isPaused = !isPaused;
    pauseBtn.textContent = isPaused ? '▶️ Resume' : '⏸️ Pause';
    pauseBtn.classList.toggle('active', isPaused);
  });

  // Filter handlers
  logFilter.addEventListener('input', applyFilter);
  clearFilterBtn.addEventListener('click', () => {
    logFilter.value = '';
    applyFilter();
    logFilter.focus();
  });

  // Command submission
  async function sendCommand(cmd) {
    cmd = (cmd || '').trim();
    if (!cmd) return;

    if (cmd.startsWith('/')) cmd = cmd.substring(1);

    commandHistory.push(cmd);
    historyIndex = commandHistory.length;

    appendLog('[Console Input] > ' + cmd);

    try {
      const resp = await fetch('/api/console/cmd', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ cmd }),
      });
      const data = await resp.json();
      if (data.output) {
        appendLog('[Command Output]\n' + data.output);
      } else if (data.error) {
        appendLog('[Command Error] ' + data.error);
      }
    } catch (err) {
      appendLog('[Error sending command] ' + err.message);
    }
  }

  if (cmdForm && cmdInput) {
    cmdForm.addEventListener('submit', (e) => {
      e.preventDefault();
      const val = cmdInput.value;
      cmdInput.value = '';
      sendCommand(val);
    });

    // Command history navigation with up/down arrows
    cmdInput.addEventListener('keydown', (e) => {
      if (e.key === 'ArrowUp') {
        if (historyIndex > 0) {
          historyIndex--;
          cmdInput.value = commandHistory[historyIndex] || '';
        }
        e.preventDefault();
      } else if (e.key === 'ArrowDown') {
        if (historyIndex < commandHistory.length - 1) {
          historyIndex++;
          cmdInput.value = commandHistory[historyIndex] || '';
        } else {
          historyIndex = commandHistory.length;
          cmdInput.value = '';
        }
        e.preventDefault();
      }
    });
  }

  // Quick command buttons
  if (quickButtons && quickButtons.length > 0) {
    quickButtons.forEach((btn) => {
      btn.addEventListener('click', () => {
        const cmd = btn.dataset.cmd;
        if (cmd) sendCommand(cmd);
      });
    });
  }

  // Modal handlers
  function openModal() {
    modal.classList.remove('hidden');
    modal.setAttribute('aria-hidden', 'false');
  }

  function closeModal() {
    modal.classList.add('hidden');
    modal.setAttribute('aria-hidden', 'true');
  }

  if (howBtn) howBtn.addEventListener('click', openModal);
  if (modalClose) modalClose.addEventListener('click', closeModal);
  if (modalDone) modalDone.addEventListener('click', closeModal);
  modal.addEventListener('click', (e) => {
    if (e.target === modal) closeModal();
  });

  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && !modal.classList.contains('hidden')) {
      closeModal();
    }
  });

  // Copy IP handler
  if (copyIpBtn && ipCode) {
    copyIpBtn.addEventListener('click', () => {
      navigator.clipboard.writeText(ipCode.textContent.trim()).then(() => {
        copyStatus.textContent = '✅ Copied to clipboard!';
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

  startStream();
})();
