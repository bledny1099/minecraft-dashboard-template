(() => {
  'use strict';
  const T = (k) => window.I18N.t(k);
  let csrf = '';
  let last = null;
  let currentUser = null;

  const el = (tag, cls, text) => {
    const n = document.createElement(tag);
    if (cls) n.className = cls;
    if (text !== undefined) n.textContent = text;
    return n;
  };

  const fmtSize = (b) => {
    if (b > 1073741824) return (b / 1073741824).toFixed(1) + ' ' + T('gb');
    if (b > 1048576) return Math.round(b / 1048576) + ' ' + T('mb');
    return Math.max(1, Math.round(b / 1024)) + ' ' + T('kb');
  };

  const worldTitle = (w) => {
    const key = 'w_' + w.id;
    const tr = T(key);
    return tr === key ? w.title : tr;
  };

  function card(w) {
    const c = el('article', 'card');
    c.dataset.kind = w.kind;

    const img = el('img', 'logo');
    img.alt = worldTitle(w);
    img.loading = 'lazy';
    img.width = 384; img.height = 384;
    img.src = '/api/logo/' + encodeURIComponent(w.id) + '.png?v=' + encodeURIComponent(w.mtime);
    c.appendChild(img);

    const body = el('div', 'card-body');
    const head = el('div', 'card-head');
    head.appendChild(el('h2', null, worldTitle(w)));
    head.appendChild(el('span', 'badge ' + (w.open ? 'open' : 'closed'), T(w.open ? 'open_all' : 'by_list')));
    body.appendChild(head);

    const kindKey = 'kind_' + w.kind;
    const kind = T(kindKey) === kindKey ? w.kind : T(kindKey);
    body.appendChild(el('p', 'meta', kind + ' · ' + w.id + ' · ' + fmtSize(w.size)));

    const chips = el('div', 'chips');
    if (w.access.length === 0) chips.appendChild(el('span', 'chip dim', T('nobody')));
    w.access.forEach((p) => chips.appendChild(el('span', 'chip', p)));
    body.appendChild(el('p', 'label', T(w.open ? 'list_ignored' : 'access_to')));
    body.appendChild(chips);

    c.appendChild(body);
    return c;
  }

  function render(state) {
    last = state;
    csrf = state.csrf;
    currentUser = state.user || null;

    const st = document.getElementById('server-status');
    st.textContent = T(state.server_online ? 'status_on' : 'status_off');
    st.className = 'pill ' + (state.server_online ? 'ok' : 'off');

    const pl = document.getElementById('players');
    pl.replaceChildren();
    if (!state.players.length) pl.appendChild(el('span', 'chip dim', T('nobody')));
    state.players.forEach((p) => pl.appendChild(el('span', 'chip live', p)));

    document.getElementById('worlds').replaceChildren(...state.worlds.map(card));
    document.getElementById('updated').textContent =
      T('updated') + ' ' + new Date().toLocaleTimeString(T('locale'));

    // Admin controls visibility
    const isAdmin = state.role === 'admin';
    const adminBtn = document.getElementById('admin-panel-btn');
    const consoleBtn = document.getElementById('console-btn');
    const heroConsoleBtn = document.getElementById('hero-console-btn');
    if (adminBtn) adminBtn.classList.toggle('hidden', !isAdmin);
    if (consoleBtn) consoleBtn.classList.remove('hidden');
    if (heroConsoleBtn) heroConsoleBtn.classList.remove('hidden');
  }

  async function load() {
    try {
      const r = await fetch('/api/state', { credentials: 'same-origin', cache: 'no-store' });
      if (r.status === 401) { window.location.href = '/login'; return; }
      if (r.ok) render(await r.json());
    } catch (_) { /* network offline */ }
  }

  document.addEventListener('langchange', () => { if (last) render(last); });

  document.getElementById('logout-btn').addEventListener('click', async () => {
    try {
      await fetch('/logout', { method: 'POST', credentials: 'same-origin', headers: { 'X-CSRF-Token': csrf } });
    } finally { window.location.href = '/login'; }
  });

  // ── How to connect modal ──
  const connectModal = document.getElementById('connect-modal');
  const openConnect = () => {
    connectModal.classList.remove('hidden');
    connectModal.setAttribute('aria-hidden', 'false');
  };
  const closeConnect = () => {
    connectModal.classList.add('hidden');
    connectModal.setAttribute('aria-hidden', 'true');
  };

  ['how-to-connect-btn', 'how-to-connect-bottom-btn', 'hero-connect-btn'].forEach((id) => {
    const b = document.getElementById(id);
    if (b) b.addEventListener('click', openConnect);
  });
  const mClose = document.getElementById('modal-close');
  const mDone = document.getElementById('modal-done');
  if (mClose) mClose.addEventListener('click', closeConnect);
  if (mDone) mDone.addEventListener('click', closeConnect);
  if (connectModal) {
    connectModal.addEventListener('click', (e) => {
      if (e.target === connectModal) closeConnect();
    });
  }

  const copyIpBtn = document.getElementById('copy-ip-btn');
  const ipCode = document.getElementById('server-ip-code');
  const copyStatus = document.getElementById('copy-status');
  if (copyIpBtn && ipCode) {
    copyIpBtn.addEventListener('click', () => {
      navigator.clipboard.writeText(ipCode.textContent.trim()).then(() => {
        copyStatus.textContent = '✅ Copied!';
        copyIpBtn.textContent = 'Copied!';
        setTimeout(() => {
          copyStatus.textContent = '';
          copyIpBtn.textContent = '📋 Copy';
        }, 2500);
      });
    });
  }

  // ── Admin Modal ──
  const adminModal = document.getElementById('admin-modal');
  const adminPanelBtn = document.getElementById('admin-panel-btn');
  const adminModalClose = document.getElementById('admin-modal-close');
  const adminModalDone = document.getElementById('admin-modal-done');

  function openAdminModal() {
    adminModal.classList.remove('hidden');
    adminModal.setAttribute('aria-hidden', 'false');
    loadInvites();
    loadSecurity();
    loadUsers();
    loadWhitelist();
  }

  function closeAdminModal() {
    adminModal.classList.add('hidden');
    adminModal.setAttribute('aria-hidden', 'true');
  }

  if (adminPanelBtn) adminPanelBtn.addEventListener('click', openAdminModal);
  if (adminModalClose) adminModalClose.addEventListener('click', closeAdminModal);
  if (adminModalDone) adminModalDone.addEventListener('click', closeAdminModal);
  if (adminModal) {
    adminModal.addEventListener('click', (e) => {
      if (e.target === adminModal) closeAdminModal();
    });
  }

  // Tabs
  document.querySelectorAll('.admin-tab').forEach((tab) => {
    tab.addEventListener('click', () => {
      document.querySelectorAll('.admin-tab').forEach((t) => t.classList.remove('active'));
      document.querySelectorAll('.tab-pane').forEach((p) => p.classList.remove('active'));
      tab.classList.add('active');
      const pane = document.getElementById(tab.dataset.tab);
      if (pane) pane.classList.add('active');
    });
  });

  // Admin Tab 1: Invites
  async function loadInvites() {
    try {
      const r = await fetch('/api/admin/invites', { credentials: 'same-origin' });
      if (!r.ok) return;
      const data = await r.json();
      const tbody = document.getElementById('invites-tbody');
      tbody.innerHTML = '';
      if (!data.invites || !data.invites.length) {
        tbody.innerHTML = '<tr><td colspan="4" class="muted">No active invites. Create one above!</td></tr>';
        return;
      }
      data.invites.forEach((inv) => {
        const tr = document.createElement('tr');
        const roleBadge = el('span', 'badge ' + (inv.role === 'admin' ? 'closed' : 'open'), inv.role);
        const tdRole = el('td'); tdRole.appendChild(roleBadge);
        
        const fullLink = window.location.origin + '/register?invite=' + encodeURIComponent(inv.code);
        const tdCode = el('td');
        const copyBtn = el('button', 'mc-btn small', '📋 Copy');
        copyBtn.addEventListener('click', () => {
          navigator.clipboard.writeText(fullLink).then(() => {
            copyBtn.textContent = 'Copied!';
            setTimeout(() => { copyBtn.textContent = '📋 Copy'; }, 2000);
          });
        });
        tdCode.appendChild(el('code', null, inv.code.slice(0, 10) + '… '));
        tdCode.appendChild(copyBtn);

        const tdUses = el('td', null, inv.uses + (inv.max_uses > 0 ? '/' + inv.max_uses : ' (unlimited)'));

        const tdAct = el('td');
        const delBtn = el('button', 'mc-btn small err-btn', '🗑️ Delete');
        delBtn.addEventListener('click', async () => {
          if (!confirm('Delete invite ' + inv.code + '?')) return;
          await fetch('/api/admin/invites/' + encodeURIComponent(inv.code), {
            method: 'DELETE',
            credentials: 'same-origin',
            headers: { 'X-CSRF-Token': csrf },
          });
          loadInvites();
        });
        tdAct.appendChild(delBtn);

        tr.append(tdRole, tdCode, tdUses, tdAct);
        tbody.appendChild(tr);
      });
    } catch (_) {}
  }

  const genInviteBtn = document.getElementById('gen-invite-btn');
  if (genInviteBtn) {
    genInviteBtn.addEventListener('click', async () => {
      const role = document.getElementById('invite-role').value;
      const max_uses = parseInt(document.getElementById('invite-uses').value, 10);
      try {
        const r = await fetch('/api/admin/invites', {
          method: 'POST',
          credentials: 'same-origin',
          headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': csrf },
          body: JSON.stringify({ role, max_uses }),
        });
        const d = await r.json();
        if (d.ok && d.link) {
          const resBox = document.getElementById('new-invite-box');
          const codeEl = document.getElementById('new-invite-link');
          const copyBtn = document.getElementById('copy-invite-btn');
          codeEl.textContent = d.link;
          resBox.classList.remove('hidden');
          copyBtn.onclick = () => {
            navigator.clipboard.writeText(d.link).then(() => {
              copyBtn.textContent = 'Copied!';
              setTimeout(() => { copyBtn.textContent = '📋 Copy'; }, 2000);
            });
          };
          loadInvites();
        }
      } catch (_) {}
    });
  }

  // Admin Tab 2: Security & 2FA
  async function loadSecurity() {
    try {
      const r = await fetch('/api/admin/settings', { credentials: 'same-origin' });
      if (!r.ok) return;
      const d = await r.json();
      const openReg = d.open_registration === '1';
      const regStatus = document.getElementById('open-reg-status');
      const regToggleBtn = document.getElementById('toggle-open-reg-btn');
      regStatus.textContent = openReg ? '🟢 Open to all' : '🔒 Invite only';
      regStatus.className = 'pill ' + (openReg ? 'ok' : 'off');
      regToggleBtn.textContent = openReg ? 'Disable Open Reg' : 'Enable Open Reg';

      // 2FA status
      const twoFaText = document.getElementById('2fa-status-text');
      const twoFaBtn = document.getElementById('2fa-action-btn');
      const setupBox = document.getElementById('2fa-setup-box');
      if (d.admin_2fa_enabled) {
        twoFaText.textContent = '🟢 Enabled';
        twoFaText.style.color = '#55ff55';
        twoFaBtn.textContent = 'Disable 2FA';
        setupBox.classList.add('hidden');
      } else {
        twoFaText.textContent = '🔴 Disabled';
        twoFaText.style.color = '#ff5555';
        twoFaBtn.textContent = 'Setup 2FA';
      }

      // Guest view link (public worlds + read-only console)
      const guestLinkEl = document.getElementById('guest-view-link');
      const copyGuestBtn = document.getElementById('copy-guest-link-btn');
      const regenGuestBtn = document.getElementById('regen-guest-link-btn');
      const guestLinkStatus = document.getElementById('guest-link-status');

      if (guestLinkEl && d.guest_view_link) {
        guestLinkEl.textContent = d.guest_view_link;
        if (copyGuestBtn) {
          copyGuestBtn.onclick = () => {
            navigator.clipboard.writeText(d.guest_view_link).then(() => {
              copyGuestBtn.textContent = 'Copied!';
              setTimeout(() => { copyGuestBtn.textContent = '📋 Copy'; }, 2000);
            });
          };
        }
        if (regenGuestBtn) {
          regenGuestBtn.onclick = async () => {
            if (!confirm('Regenerate guest share link? Previous links will stop working.')) return;
            try {
              const res = await fetch('/api/admin/guest-token/regenerate', {
                method: 'POST',
                credentials: 'same-origin',
                headers: { 'X-CSRF-Token': csrf },
              });
              const resData = await res.json();
              if (resData.ok && resData.guest_view_link) {
                guestLinkEl.textContent = resData.guest_view_link;
                if (guestLinkStatus) {
                  guestLinkStatus.textContent = '✅ Key updated!';
                  setTimeout(() => { guestLinkStatus.textContent = ''; }, 2500);
                }
              }
            } catch (_) {}
          };
        }
      }

      // Console read-only link
      const consoleLinkEl = document.getElementById('console-view-link');
      const copyConsoleBtn = document.getElementById('copy-console-link-btn');
      const regenConsoleBtn = document.getElementById('regen-console-link-btn');
      const consoleLinkStatus = document.getElementById('console-link-status');

      if (consoleLinkEl && d.console_view_link) {
        consoleLinkEl.textContent = d.console_view_link;
        if (copyConsoleBtn) {
          copyConsoleBtn.onclick = () => {
            navigator.clipboard.writeText(d.console_view_link).then(() => {
              copyConsoleBtn.textContent = 'Copied!';
              setTimeout(() => { copyConsoleBtn.textContent = '📋 Copy'; }, 2000);
            });
          };
        }
        if (regenConsoleBtn) {
          regenConsoleBtn.onclick = async () => {
            if (!confirm('Regenerate console read-only link? Previous links will stop working.')) return;
            try {
              const res = await fetch('/api/admin/console-secret/regenerate', {
                method: 'POST',
                credentials: 'same-origin',
                headers: { 'X-CSRF-Token': csrf },
              });
              const resData = await res.json();
              if (resData.ok && resData.console_view_link) {
                consoleLinkEl.textContent = resData.console_view_link;
                if (consoleLinkStatus) {
                  consoleLinkStatus.textContent = '✅ Key updated!';
                  setTimeout(() => { consoleLinkStatus.textContent = ''; }, 2500);
                }
              }
            } catch (_) {}
          };
        }
      }
    } catch (_) {}
  }

  const toggleOpenRegBtn = document.getElementById('toggle-open-reg-btn');
  if (toggleOpenRegBtn) {
    toggleOpenRegBtn.addEventListener('click', async () => {
      const current = document.getElementById('open-reg-status').textContent.includes('Open');
      await fetch('/api/admin/settings', {
        method: 'POST',
        credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': csrf },
        body: JSON.stringify({ open_registration: current ? '0' : '1' }),
      });
      loadSecurity();
    });
  }

  const twoFaBtn = document.getElementById('2fa-action-btn');
  if (twoFaBtn) {
    twoFaBtn.addEventListener('click', async () => {
      const isEnabled = document.getElementById('2fa-status-text').textContent.includes('Enabled');
      if (isEnabled) {
        if (!confirm('Disable 2FA for your account?')) return;
        await fetch('/api/admin/2fa/disable', {
          method: 'POST',
          credentials: 'same-origin',
          headers: { 'X-CSRF-Token': csrf },
        });
        loadSecurity();
      } else {
        // Setup 2FA
        const r = await fetch('/api/admin/2fa/setup', {
          method: 'POST',
          credentials: 'same-origin',
          headers: { 'X-CSRF-Token': csrf },
        });
        const d = await r.json();
        if (d.secret) {
          const setupBox = document.getElementById('2fa-setup-box');
          setupBox.classList.remove('hidden');
          document.getElementById('2fa-secret-code').textContent = d.secret;
          document.getElementById('2fa-otp-link').href = d.uri;
          document.getElementById('copy-secret-btn').onclick = () => {
            navigator.clipboard.writeText(d.secret);
          };
        }
      }
    });
  }

  const confirm2faBtn = document.getElementById('2fa-confirm-btn');
  if (confirm2faBtn) {
    confirm2faBtn.addEventListener('click', async () => {
      const code = document.getElementById('2fa-verify-code').value.trim();
      const errEl = document.getElementById('2fa-verify-err');
      errEl.textContent = '';
      const r = await fetch('/api/admin/2fa/verify', {
        method: 'POST',
        credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': csrf },
        body: JSON.stringify({ code }),
      });
      const d = await r.json();
      if (d.ok) {
        alert('✅ 2FA successfully enabled!');
        document.getElementById('2fa-verify-code').value = '';
        loadSecurity();
      } else {
        errEl.textContent = d.error || 'Invalid code';
      }
    });
  }

  // Admin Tab 3: Users
  async function loadUsers() {
    try {
      const r = await fetch('/api/admin/users', { credentials: 'same-origin' });
      if (!r.ok) return;
      const d = await r.json();
      const tbody = document.getElementById('users-tbody');
      tbody.innerHTML = '';
      if (!d.users || !d.users.length) {
        tbody.innerHTML = '<tr><td colspan="4" class="muted">No users found.</td></tr>';
        return;
      }
      d.users.forEach((u) => {
        const tr = document.createElement('tr');
        tr.appendChild(el('td', null, u.username));
        tr.appendChild(el('td', null, u.role));
        tr.appendChild(el('td', null, u.totp_enabled ? '🟢 Enabled' : '⚪ None'));

        const tdAct = el('td');
        if (u.username !== currentUser) {
          const delBtn = el('button', 'mc-btn small err-btn', '🗑️ Delete');
          delBtn.addEventListener('click', async () => {
            if (!confirm('Delete user ' + u.username + '?')) return;
            await fetch('/api/admin/users/' + encodeURIComponent(u.username), {
              method: 'DELETE',
              credentials: 'same-origin',
              headers: { 'X-CSRF-Token': csrf },
            });
            loadUsers();
          });
          tdAct.appendChild(delBtn);
        } else {
          tdAct.appendChild(el('span', 'muted', '(You)'));
        }
        tr.appendChild(tdAct);
        tbody.appendChild(tr);
      });
    } catch (_) {}
  }

  // Admin Tab 4: Whitelist
  async function loadWhitelist() {
    try {
      const r = await fetch('/api/admin/whitelist', { credentials: 'same-origin' });
      if (!r.ok) return;
      const d = await r.json();
      const tbody = document.getElementById('wl-tbody');
      tbody.innerHTML = '';
      if (!d.players || !d.players.length) {
        tbody.innerHTML = '<tr><td colspan="2" class="muted">Whitelist is empty.</td></tr>';
        return;
      }
      d.players.forEach((p) => {
        const tr = document.createElement('tr');
        tr.appendChild(el('td', null, p));
        const tdAct = el('td');
        const remBtn = el('button', 'mc-btn small err-btn', 'Remove');
        remBtn.addEventListener('click', async () => {
          if (!confirm('Remove ' + p + ' from whitelist?')) return;
          await fetch('/api/admin/whitelist/remove', {
            method: 'POST',
            credentials: 'same-origin',
            headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': csrf },
            body: JSON.stringify({ player: p }),
          });
          loadWhitelist();
        });
        tdAct.appendChild(remBtn);
        tr.appendChild(tdAct);
        tbody.appendChild(tr);
      });
    } catch (_) {}
  }

  const wlAddBtn = document.getElementById('wl-add-btn');
  const wlAddNick = document.getElementById('wl-add-nick');
  if (wlAddBtn && wlAddNick) {
    wlAddBtn.addEventListener('click', async () => {
      const p = wlAddNick.value.trim();
      if (!p) return;
      await fetch('/api/admin/whitelist/add', {
        method: 'POST',
        credentials: 'same-origin',
        headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': csrf },
        body: JSON.stringify({ player: p }),
      });
      wlAddNick.value = '';
      loadWhitelist();
    });
  }

  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape') {
      if (adminModal && !adminModal.classList.contains('hidden')) closeAdminModal();
      if (connectModal && !connectModal.classList.contains('hidden')) closeConnect();
    }
  });

  load();
  setInterval(load, 15000);
})();
