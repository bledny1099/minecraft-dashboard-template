(() => {
  'use strict';
  const D = {
    ru: {
      title_login: 'Вход · Minecraft Worlds', title_dash: 'Миры · Minecraft Dashboard',
      title_console: 'Консоль · Minecraft Server', title_register: 'Регистрация · Minecraft Server',
      eyebrow: 'Minecraft Server', login_h: 'Вход', login_sub: 'Закрытая панель миров.',
      user: 'Логин', pass: 'Пароль', signin: 'Войти',
      err_bad: 'Неверный логин или пароль', err_lock: 'Слишком много попыток. Подождите немного.',
      err_csrf: 'Страница устарела. Войдите ещё раз.',
      status_on: 'Сервер онлайн', status_off: 'Сервер выключен', logout: 'Выйти',
      hero_h: 'Все миры в одном месте', hero_sub: 'Миры сервера, доступ игроков и статус — под одним замком.',
      open_worlds: 'Открыть миры', worlds: 'Миры', online: 'Онлайн:', nobody: 'никого',
      open_all: 'Открыт всем', by_list: 'По списку', access_to: 'Доступ у',
      list_ignored: 'Список (игнорируется, пока мир открыт)', updated: 'Обновлено',
      kind_hub: 'Хаб', kind_oneblock: 'OneBlock', kind_regular: 'Выживание', kind_legacy: 'OneBlock',
      w_world: 'Хаб', w_world_nether: 'Незер', w_world_the_end: 'Энд',
      w_ob_public: 'OneBlock (общий)', w_ob_private: 'OneBlock (приватный)',
      gb: 'ГБ', mb: 'МБ', kb: 'КБ', lang_btn: 'EN', locale: 'ru-RU',
      create_acc: 'Создать аккаунт', create_acc_title: 'Регистрация',
      contact_admin: 'Свяжитесь с администратором для создания аккаунта.',
      close: 'Закрыть',
      admin_btn: '⚙️ Настройки', console_btn: '💻 Консоль',
      how_to_connect: '🎮 Как подключиться', how_to_connect_short: '🎮 Вход',
      connect_title: '🎮 Как подключиться к серверу',
      connect_intro: 'Подключайтесь к нашему приватному серверу прямо из Minecraft Java Edition:',
      server_addr: 'Адрес сервера:', copy_btn: '📋 Копировать',
      port_label: 'Порт:', direct_ip_label: 'Прямой IP:', version_label: 'Версия игры:', prot_label: 'Защита:',
      steps_heading: 'Быстрые шаги:',
      step_1: 'Запустите Minecraft Java Edition 1.16.5.',
      step_2: 'Нажмите «Сетевая игра» → «По адресу» (или «Добавить»).',
      step_3: 'Введите адрес mc.dosimple.app в поле адреса.',
      step_4: 'Нажмите «Подключиться»!',
      whitelist_warn: '⚠️ Внимание: на сервере работает вайтлист. Если вашего ника ещё нет в списке, обратитесь к администратору.',
      got_it: 'Понятно / Закрыть',
      reg_h: 'Создание аккаунта', reg_sub: 'Регистрация в закрытом сообществе.',
      invite_type: 'Тип аккаунта:', mc_nickname: 'Ник в Minecraft', pass_confirm: 'Повторите пароль',
      register_btn: 'Зарегистрироваться', back_to_login: '← Назад ко входу',
      tab_invites: '🔗 Инвайты', tab_security: '🔐 2FA и безопасность',
      tab_users: '👥 Пользователи', tab_whitelist: '📜 Вайтлист',
      create_invite_h: 'Создание ссылки-приглашения',
      create_invite_sub: 'Создайте ссылку, по которой пользователь сам сможет зарегистрировать аккаунт.',
      account_role: 'Тип аккаунта:', max_uses: 'Число использований:',
      gen_link_btn: 'Сгенерировать ссылку ↵', link_ready: 'Ссылка готова:',
      active_invites_h: 'Активные ссылки-приглашения',
      open_reg_h: 'Открытая регистрация (без инвайтов)',
      open_reg_sub: 'Если включено, любой может зайти на /register и создать аккаунт игрока.',
      admin_2fa_h: 'Двухфакторная аутентификация (2FA) для админа',
      admin_2fa_sub: 'Защита админки через Google Authenticator, 1Password или Authy (TOTP).',
      users_list_h: 'Зарегистрированные пользователи',
      wl_mgmt_h: 'Управление вайтлистом сервера',
      wl_mgmt_sub: 'Управление списком игроков в реальном времени через RCON сервера.',
      admin_panel_title: '⚙️ Панель администратора и настройки',
      guest_link_h: 'Гостевая ссылка (Миры и консоль)',
      guest_link_sub: 'Ссылка для гостей: видны все публичные миры, онлайн игроков и live консоль только для чтения. Вход не требуется.',
      console_link_h: 'Прямой просмотр консоли без логина',
      console_link_sub: 'Ссылка для просмотра консоли сервера в реальном времени. Вход не требуется, команды отключены.',
      regen_console_key: '🔄 Сменить ключ',
      readonly_title: 'Режим просмотра (Только чтение)',
      readonly_sub: 'Ввод команд отключен без авторизации администратора. Доступен только живой просмотр логов.',
      login_as_admin: '🔑 Войти для управления',
      badge_readonly: '👁️ Только просмотр',
      badge_admin: '⚡ Админ (Полный доступ)',
      back_dash: '⬅️ Панель миров',
      nav_login: '🔑 Войти',
    },
    en: {
      title_login: 'Sign in · Minecraft Worlds', title_dash: 'Worlds · Minecraft Dashboard',
      title_console: 'Console · Minecraft Server', title_register: 'Register · Minecraft Server',
      eyebrow: 'Minecraft Server', login_h: 'Sign in', login_sub: 'Private worlds panel.',
      user: 'Username', pass: 'Password', signin: 'Sign in',
      err_bad: 'Wrong username or password', err_lock: 'Too many attempts. Please wait a bit.',
      err_csrf: 'The page expired. Please sign in again.',
      status_on: 'Server online', status_off: 'Server offline', logout: 'Log out',
      hero_h: 'All your worlds in one place', hero_sub: 'Server worlds, player access and status — behind one lock.',
      open_worlds: 'View worlds', worlds: 'Worlds', online: 'Online:', nobody: 'nobody',
      open_all: 'Open to all', by_list: 'Whitelist only', access_to: 'Access for',
      list_ignored: 'List (ignored while the world is open)', updated: 'Updated',
      kind_hub: 'Hub', kind_oneblock: 'OneBlock', kind_regular: 'Survival', kind_legacy: 'OneBlock',
      w_world: 'Hub', w_world_nether: 'Nether', w_world_the_end: 'The End',
      w_ob_public: 'OneBlock (public)', w_ob_private: 'OneBlock (private)',
      gb: 'GB', mb: 'MB', kb: 'KB', lang_btn: 'RU', locale: 'en-US',
      create_acc: 'Create account', create_acc_title: 'Registration',
      contact_admin: 'Contact admin so he can register you an account.',
      close: 'Close',
      admin_btn: '⚙️ Settings', console_btn: '💻 Console',
      how_to_connect: '🎮 How to connect', how_to_connect_short: '🎮 Connect',
      connect_title: '🎮 How to connect to server',
      connect_intro: 'Join our private Minecraft world directly from your Minecraft Java client:',
      server_addr: 'Server Address:', copy_btn: '📋 Copy',
      port_label: 'Port:', direct_ip_label: 'Direct IP:', version_label: 'Game Version:', prot_label: 'Protection:',
      steps_heading: 'Quick Steps:',
      step_1: 'Launch Minecraft Java Edition 1.16.5.',
      step_2: 'Click Multiplayer → Direct Connection (or Add Server).',
      step_3: 'Enter mc.dosimple.app into the server address.',
      step_4: 'Click Join Server!',
      whitelist_warn: '⚠️ Note: Server whitelist is strictly enforced. If you are not yet on the whitelist, contact an admin.',
      got_it: 'Got it! / Close',
      reg_h: 'Create Account', reg_sub: 'Join our private server community.',
      invite_type: 'Account Type:', mc_nickname: 'Minecraft Nickname', pass_confirm: 'Confirm Password',
      register_btn: 'Register', back_to_login: '← Back to Sign in',
      tab_invites: '🔗 Invites', tab_security: '🔐 2FA & Security',
      tab_users: '👥 Users', tab_whitelist: '📜 Whitelist',
      create_invite_h: 'Create Self-Registration Link',
      create_invite_sub: 'Generate a link allowing a user to register an account with a specific role.',
      account_role: 'Account Role:', max_uses: 'Max Uses:',
      gen_link_btn: 'Generate Link ↵', link_ready: 'Link Ready:',
      active_invites_h: 'Active Invite Links',
      open_reg_h: 'Open Registration (Without Invite)',
      open_reg_sub: 'If enabled, anyone can visit /register and create a player account without an invite link.',
      admin_2fa_h: 'Admin Two-Factor Authentication (2FA)',
      admin_2fa_sub: 'Protect your admin account using Google Authenticator, 1Password or Authy (TOTP).',
      users_list_h: 'Registered Dashboard Users',
      wl_mgmt_h: 'Minecraft Server Whitelist',
      wl_mgmt_sub: 'Manage player whitelist in real time via server RCON.',
      admin_panel_title: '⚙️ Admin Control & Settings',
      guest_link_h: 'Guest Link (Public Worlds & Read-Only Console)',
      guest_link_sub: 'Shareable link: views all public worlds, online players, and live read-only server console without login.',
      console_link_h: 'Direct Read-Only Console Link',
      console_link_sub: 'Live console viewing link without login. No credentials required, commands are blocked.',
      regen_console_key: '🔄 Regenerate Key',
      readonly_title: 'View-Only Mode (Read-Only)',
      readonly_sub: 'Command execution is disabled without administrator login. Live logs are view-only.',
      login_as_admin: '🔑 Login to Manage',
      badge_readonly: '👁️ Read-Only',
      badge_admin: '⚡ Admin (Full Access)',
      back_dash: '⬅️ Worlds Dashboard',
      nav_login: '🔑 Sign In',
    },
  };

  let lang = 'en';
  try {
    const saved = localStorage.getItem('lang');
    lang = D[saved] ? saved : 'en';
  } catch (_) { lang = 'en'; }

  const t = (key) => (D[lang] && D[lang][key]) || D.en[key] || key;

  const apply = () => {
    document.documentElement.lang = lang;
    document.querySelectorAll('[data-i18n]').forEach((n) => { n.textContent = t(n.dataset.i18n); });
    const ttl = document.documentElement.dataset.title;
    if (ttl) document.title = t(ttl);
    document.querySelectorAll('[data-lang-toggle]').forEach((b) => { b.textContent = t('lang_btn'); });
  };

  const setLang = (l) => {
    if (!D[l]) return;
    lang = l;
    try { localStorage.setItem('lang', l); } catch (_) {}
    apply();
    document.dispatchEvent(new CustomEvent('langchange'));
  };

  window.I18N = { t, apply, get lang() { return lang; } };
  document.querySelectorAll('[data-lang-toggle]').forEach((b) => {
    b.addEventListener('click', () => setLang(lang === 'ru' ? 'en' : 'ru'));
  });
  apply();
})();
