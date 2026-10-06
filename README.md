# 🎮 Minecraft Web Dashboard & Live Console

A modern, lightweight web dashboard and real-time live server console for Minecraft servers (Paper, Purpur, Spigot, Fabric, Vanilla) featuring an authentic Minecraft pixel art interface.

---

## ⚡ Features

- 🟩 **Authentic Minecraft UI:** Procedural dirt background (`dirt.png`), pixel-perfect `Monocraft` typography, and beveled stone buttons with interactive audio and hover effects.
- 💻 **Real-Time Server Console:** Instant streaming of server logs via Server-Sent Events (SSE) directly from `logs/latest.log` with zero latency.
- 🔍 **Smart Log Filtering & Search:** Filter by `WARN`, `ERROR`, player usernames, or arbitrary text, with autoscroll and pause/resume capabilities.
- 🔒 **Role-Based Access Control (RBAC):**
  - **Administrator:** Execute server commands via RCON, manage player whitelists, create registration invite links, and enforce 2FA.
  - **Player:** View server status, explore world cards, and inspect connection details.
  - **Guest / Viewer:** Access via guest links (`/view/<token>`) to see public worlds and player counts without login credentials. Console access is restricted to administrators.
- 🔐 **Built-in 2FA (TOTP):** Multi-factor authentication protection for admin accounts via Google Authenticator, 1Password, Authy, or Apple Passwords (pure Python stdlib, zero external dependencies).
- 🎮 **Interactive "How to Connect" Modal:** One-click IP copying, port configuration, game version guidelines, and whitelist instructions.
- 🌐 **Clean & Standalone:** Zero bloat, pure Python backend with async `aiohttp`, SQLite storage, and pure Python RCON client.

---

## 🚀 Quick Start in 3 Steps

### Step 1. Enable RCON on Your Minecraft Server
In your Minecraft server's `server.properties`, ensure RCON is enabled:
```properties
enable-rcon=true
rcon.port=25575
rcon.password=YourSecretRconPassword2026
```
*(Restart your Minecraft server after saving changes)*.

### Step 2. Install Dependencies
Requires Python 3.10+:
```bash
pip install -r requirements.txt
```

### Step 3. Configure Environment and Run
Copy the example configuration:
```bash
cp .env.example .env
```
Edit `.env` to match your server configuration:
```ini
DASH_USER=admin
DASH_PASS=ChangeMe_SecureAdminPassword2026
DASH_BIND=0.0.0.0:8095
MC_SERVER_DIR=/path/to/your/minecraft/server
RCON_HOST=127.0.0.1
RCON_PORT=25575
RCON_PASS=YourSecretRconPassword2026
SERVER_PUBLIC_HOST=mc.yourdomain.com
SERVER_PUBLIC_PORT=25565
```

Start the dashboard:
```bash
python3 server.py
```
Open `http://localhost:8095` in your browser!

---

## 🛠️ Production Deployment (Systemd + Caddy)

### 1. Systemd Service (Background Service)
Copy the service unit file to your systemd directory:
```bash
sudo cp deploy/systemd/minecraft-dashboard.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now minecraft-dashboard
```

### 2. Reverse Proxy with Caddy (Automatic HTTPS + SSE Streaming)
Add the following block to your `Caddyfile`:
```caddy
mc.yourdomain.com {
    reverse_proxy 127.0.0.1:8095 {
        flush_interval -1
    }
}
```
> **Important:** The `flush_interval -1` directive is essential — it disables response buffering so log lines stream to the browser in real time without lag.

### 3. Docker & Docker Compose
Alternatively, launch via Docker Compose:
```bash
cd deploy/docker
docker compose up -d
```

---

## 🔑 Access Points & Links

- **`/login`** — Authentication portal for administrators and registered players.
- **`/view/<token>`** — Shareable guest link providing access to public worlds and player list without login.
- **`/console`** — Live interactive console (restricted strictly to authenticated administrators).
- Invite links, guest tokens, and 2FA credentials can be configured directly inside **"⚙️ Settings"** on the dashboard.

---

## 📂 Repository Structure

```text
├── server.py             # Main aiohttp async server, API routes, SSE log streamer
├── db.py                 # SQLite storage for users, sessions, settings, and audit logs
├── rcon.py               # Pure-Python Minecraft RCON client using standard sockets
├── totp.py               # RFC 6238 TOTP generator and validator (2FA)
├── render.py             # Top-down Anvil world renderer generating world icon sprites
├── requirements.txt      # Minimal Python dependencies (aiohttp)
├── .env.example          # Environment variables configuration template
├── deploy/
│   ├── systemd/          # Linux systemd .service unit file
│   ├── caddy/            # Caddy reverse proxy example configuration
│   └── docker/           # Dockerfile and docker-compose.yml
└── static/               # Frontend assets: HTML, CSS, JavaScript, and Minecraft textures
```

---

## 📄 License
This project is open-source and available under the [MIT License](LICENSE).
