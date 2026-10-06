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

  // Authentic Minecraft Formatting & Color Palette (§0-§f)
  const MC_COLORS = {
    '0': '#000000',
    '1': '#0000aa',
    '2': '#00aa00',
    '3': '#00aaaa',
    '4': '#aa0000',
    '5': '#aa00aa',
    '6': '#ffaa00',
    '7': '#aaaaaa',
    '8': '#555555',
    '9': '#5555ff',
    'a': '#55ff55',
    'b': '#55ffff',
    'c': '#ff5555',
    'd': '#ff55ff',
    'e': '#ffff55',
    'f': '#ffffff',
  };

  function parseFormattedContent(text) {
    if (!text.includes('§') && !text.includes('\x1b')) {
      return document.createTextNode(text);
    }

    const fragment = document.createDocumentFragment();
    // Strip ANSI escape codes
    const cleaned = text.replace(/\x1b\[[0-9;]*m/g, '');
    const parts = cleaned.split(/(§[0-9a-fk-or])/gi);
    let currentColor = null;
    let isBold = false;
    let isItalic = false;
    let isUnderline = false;

    for (const part of parts) {
      if (!part) continue;
      if (part.startsWith('§') && part.length === 2) {
        const code = part.charAt(1).toLowerCase();
        if (code in MC_COLORS) {
          currentColor = MC_COLORS[code];
        } else if (code === 'l') {
          isBold = true;
        } else if (code === 'o') {
          isItalic = true;
        } else if (code === 'n') {
          isUnderline = true;
        } else if (code === 'r') {
          currentColor = null;
          isBold = false;
          isItalic = false;
          isUnderline = false;
        }
      } else {
        const span = document.createElement('span');
        span.textContent = part;
        if (currentColor) span.style.color = currentColor;
        if (isBold) span.style.fontWeight = 'bold';
        if (isItalic) span.style.fontStyle = 'italic';
        if (isUnderline) span.style.textDecoration = 'underline';
        fragment.appendChild(span);
      }
    }
    return fragment;
  }

  // Format log lines with color coding & Minecraft text formatting
  function formatLogLine(rawText) {
    const div = document.createElement('div');
    div.className = 'log-line';

    const text = String(rawText || '');
    let lineType = 'info';

    if (text.startsWith('[Console Input]')) {
      lineType = 'cmd';
    } else if (text.startsWith('[Command Output]')) {
      lineType = 'info';
    } else if (text.startsWith('[Command Error]') || text.startsWith('[Error')) {
      lineType = 'error';
    } else if (text.includes('/WARN') || text.includes('WARN]:') || text.includes('WARNING:')) {
      lineType = 'warn';
    } else if (text.includes('/ERROR') || text.includes('ERROR]:') || text.includes('Exception') || text.includes('Error')) {
      lineType = 'error';
    } else if (text.includes('issued server command:') || text.includes('ServerCommandEvent')) {
      lineType = 'cmd';
    } else if (text.includes('<') && text.includes('>') && !text.includes('ServerLevel[')) {
      lineType = 'chat';
    }

    div.classList.add('log-' + lineType);
    div.appendChild(parseFormattedContent(text));

    // Filter check
    const filterQuery = (logFilter.value || '').trim().toLowerCase();
    if (filterQuery && !text.toLowerCase().includes(filterQuery)) {
      div.style.display = 'none';
    }

    return div;
  }

  function appendLog(rawText) {
    if (isPaused) return;

    const lines = String(rawText || '').split(/\r?\n/);
    for (const rawLine of lines) {
      if (rawLine === '' && lines.length > 1) continue;
      const line = formatLogLine(rawLine);
      logStream.appendChild(line);
    }

    // Trim old lines
    while (logStream.children.length > maxLines) {
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
    logStream.replaceChildren();
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

    const csrfMeta = document.querySelector('meta[name="csrf-token"]');
    const csrfToken = csrfMeta ? csrfMeta.getAttribute('content') : '';

    try {
      const resp = await fetch('/api/console/cmd', {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
          'X-CSRF-Token': csrfToken,
        },
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
