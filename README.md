# 🎮 Minecraft Web Dashboard & Live Console

Современная веб-панель миров и живая серверная консоль для серверов Minecraft (Paper, Purpur, Spigot, Fabric, Vanilla) с аутентичным пиксельным дизайном в стиле Minecraft.

---

## ⚡ Особенности

- 🟩 **Аутентичный Minecraft UI:** текстура земли (`dirt`), пиксельный шрифт `Monocraft` с поддержкой кириллицы, скошенные каменные кнопки со звуками и ховером.
- 💻 **Живая консоль сервера:** потоковый вывод логов в реальном времени (Server-Sent Events / SSE) из `logs/latest.log` без задержек.
- 🔍 **Умный фильтр и поиск:** фильтрация по `WARN`, `ERROR`, нику игрока или тексту, автоскролл, пауза/возобновление.
- 🔒 **Разделение прав доступа:**
  - **Администратор:** ввод команд в консоль через RCON, управление вайтлистом, создание инвайт-ссылок, 2FA.
  - **Игрок:** просмотр статуса сервера, списка миров и карточки подключения.
  - **Гость / Зритель (без логина):** ссылка вида `/view/<token>` для публичного просмотра миров и **строго read-only консоли** (ввод команд заблокирован на уровне API).
- 🔐 **Встроенная 2FA (TOTP):** двухфакторка для защиты аккаунта админа через Google Authenticator, 1Password, Authy (чистый Python, без сторонних библиотек).
- 🎮 **Модальное окно «Как подключиться»:** кликабельное копирование IP сервера, порт, версия игры и инструкция по вайтлисту.
- 🌐 **Двуязычный интерфейс:** переключение языка RU / EN в один клик.

---

## 🚀 Быстрый старт за 3 шага

### Шаг 1. Включите RCON в Minecraft
В файле `server.properties` вашего Minecraft-сервера убедитесь, что включен RCON:
```properties
enable-rcon=true
rcon.port=25575
rcon.password=SuperSecretRconPassword2026
```
*(После изменения перезапустите сервер Minecraft)*.

### Шаг 2. Установка зависимостей
Требуется Python 3.10+:
```bash
pip install -r requirements.txt
```

### Шаг 3. Настройка окружения и запуск
Скопируйте пример конфига:
```bash
cp .env.example .env
```
Отредактируйте `.env`:
```ini
DASH_USER=admin
DASH_PASS=MySecureAdminPassword123
DASH_BIND=0.0.0.0:8095
MC_SERVER_DIR=/path/to/your/minecraft/server
RCON_HOST=127.0.0.1
RCON_PORT=25575
RCON_PASS=SuperSecretRconPassword2026
SERVER_PUBLIC_HOST=mc.yourdomain.com
SERVER_PUBLIC_PORT=25565
```

Запустите панель:
```bash
python3 server.py
```
Панель доступна по адресу `http://localhost:8095`!

---

## 🛠️ Развёртывание на production (Systemd + Caddy)

### 1. Служба Systemd
Скопируйте файл службы:
```bash
sudo cp deploy/systemd/minecraft-dashboard.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now minecraft-dashboard
```

### 2. Проксирование через Caddy (автоматический HTTPS + стриминг)
Добавьте в ваш `Caddyfile`:
```caddy
mc.yourdomain.com {
    reverse_proxy 127.0.0.1:8095 {
        flush_interval -1
    }
}
```
Флаг `flush_interval -1` критически важен — он отключает буферизацию для мгновенной передачи строк логов через SSE.

---

## 🔑 Ссылки доступа

- **`/login`** — вход администратора или зарегистрированных игроков.
- **`/view/<token>`** — гостевая ссылка (видны все публичные миры и read-only консоль без авторизации).
- **`/console/<secret>`** — прямая ссылка на live-консоль (без ввода команд).
- Ссылки и токены генерируются и ротируются в панели: **«⚙️ Настройки»** → вкладка **«🔐 2FA и безопасность»**.

---

## 📂 Структура проекта

```text
├── server.py             # Главный сервер aiohttp, роуты, SSE стриминг
├── db.py                 # SQLite хранилище пользователей, сессий, настроек
├── rcon.py               # Чистый клиент Minecraft RCON (сокеты)
├── totp.py               # RFC 6238 генератор и валидатор кодов 2FA
├── render.py             # Рендерер 3D иконок миров
├── requirements.txt      # Зависимости Python
├── .env.example          # Шаблон переменных окружения
├── deploy/
│   ├── systemd/          # Шаблон .service файла для Linux
│   ├── caddy/            # Пример Caddyfile
│   └── docker/           # Dockerfile и docker-compose.yml
└── static/               # HTML, CSS, JS и спрайты Minecraft UI
```
