"""Standalone Minecraft Worlds Dashboard & Real-Time Live Server Console.

Features:
- Authentic pixelated Minecraft UI (dirt background, Monocraft font, stone buttons).
- Live Server Console with Server-Sent Events (SSE) streaming from logs/latest.log.
- Role-based security (Admin with RCON command execution, Player, Guest/Viewer read-only).
- Dedicated shareable guest link (/view/<token>) for viewing public worlds & read-only console without login.
- Two-Factor Authentication (TOTP RFC 6238) for admin accounts.
- Whitelist management in real-time via RCON.
"""
import asyncio
import hashlib
import hmac
import ipaddress
import json
import logging
import os
from pathlib import Path
import re
import secrets
import sqlite3
import sys
import time

from aiohttp import web
from dotenv import dotenv_values

BASE = Path(__file__).parent.resolve()

from render import render_world, placeholder, WORLD_ID_RE
import db
import totp
from rcon import send_rcon_command, RconError

# ───────────── configuration ─────────────
cfg = {**dotenv_values(BASE / ".env"), **os.environ}
DASH_USER = cfg.get("DASH_USER") or "admin"
DASH_PASS_HASH = cfg.get("DASH_PASS_HASH") or ""
DEFAULT_PASS = cfg.get("DASH_PASS") or "admin123"
if not DASH_PASS_HASH and DEFAULT_PASS:
    DASH_PASS_HASH = db.hash_password(DEFAULT_PASS)

BIND_HOST, _, BIND_PORT = (cfg.get("DASH_BIND") or "0.0.0.0:8095").rpartition(":")
SERVER_DIR = Path(cfg.get("MC_SERVER_DIR") or BASE.parent).resolve()
DB_FILE = SERVER_DIR / "bot" / "stats.db"
CACHE = BASE / "cache"

RCON_HOST = cfg.get("RCON_HOST") or "127.0.0.1"
RCON_PORT = int(cfg.get("RCON_PORT") or 25575)
RCON_PASS = cfg.get("RCON_PASS") or "minecraft_rcon_password"

PUBLIC_HOST = cfg.get("SERVER_PUBLIC_HOST") or "mc.example.com"
PUBLIC_PORT = cfg.get("SERVER_PUBLIC_PORT") or "25565"

SESSION_TTL = 12 * 3600
SESSION_IDLE = 4 * 3600
LOGO_TTL = 30 * 60
MAX_FAILS, LOCK_SECONDS = 6, 15 * 60
TRUSTED_PROXY = ipaddress.ip_network("172.16.0.0/12")

sessions: dict[str, dict] = {}
pre_auth_2fa: dict[str, dict] = {}
fails: dict[str, list] = {}
hits: dict[str, list] = {}
_cache: dict[str, tuple] = {}
_logo_locks: dict[str, asyncio.Lock] = {}

CSP = ("default-src 'none'; script-src 'self' 'unsafe-inline'; style-src 'self' 'unsafe-inline'; "
       "img-src 'self' data:; font-src 'self' data:; connect-src 'self'; form-action 'self'; "
       "frame-ancestors 'none'; base-uri 'none'")


# ───────────── helpers ─────────────
def client_ip(req: web.Request) -> str:
    peer = req.remote or "0.0.0.0"
    try:
        if ipaddress.ip_address(peer) in TRUSTED_PROXY:
            cand = req.headers.get("CF-Connecting-IP") or req.headers.get("X-Real-IP") or peer
            ipaddress.ip_address(cand)
            return cand
    except ValueError:
        pass
    return peer


def get_session(req: web.Request) -> dict | None:
    tok = req.cookies.get("__Host-session", "")
    if not tok or len(tok) > 128:
        return None
    key = hashlib.sha256(tok.encode()).hexdigest()
    s = sessions.get(key)
    now = time.time()
    if not s or s["exp"] < now or now - s["last"] > SESSION_IDLE:
        sessions.pop(key, None)
        return None
    s["last"] = now
    return s


def set_cookie(resp: web.Response, name: str, value: str, max_age: int, http_only=True):
    resp.set_cookie(name, value, max_age=max_age, path="/", secure=True, httponly=http_only, samesite="Strict")


_ASSET_RE = re.compile(r'(/static/[A-Za-z0-9_.\-]+\.(?:css|js))"')


def _versioned(m: re.Match) -> str:
    try:
        v = int((BASE / m.group(1).lstrip("/")).stat().st_mtime)
    except OSError:
        v = 0
    return f'{m.group(1)}?v={v}"'


def page(path: str) -> str:
    text = (BASE / "static" / path).read_text(encoding="utf-8")
    return _ASSET_RE.sub(_versioned, text)


def rcon_exec(cmd: str, timeout: float = 5.0) -> str:
    return send_rcon_command(RCON_HOST, RCON_PORT, RCON_PASS, cmd, timeout=timeout)


# ───────────── middleware ─────────────
@web.middleware
async def guard(req: web.Request, handler):
    ip = client_ip(req)
    now = time.time()
    w = hits.setdefault(ip, [now, 0])
    if now - w[0] > 60:
        w[0], w[1] = now, 0
    w[1] += 1
    if w[1] > 360:
        return web.Response(status=429, text="Too many requests")
    if len(hits) > 5000:
        hits.clear()

    if req.method not in ("GET", "HEAD", "POST", "DELETE"):
        return web.Response(status=405)

    is_public = (
        req.path in ("/login", "/register", "/login/2fa")
        or req.path.startswith("/console/")
        or req.path.startswith("/view/")
        or req.path.startswith("/share/")
        or req.path.startswith("/static/")
    )
    if not is_public and get_session(req) is None:
        if req.path.startswith("/api/"):
            resp = web.json_response({"error": "unauthorized"}, status=401)
        else:
            resp = web.HTTPFound("/login")
        resp.headers["Cache-Control"] = "no-store"
        return resp

    try:
        resp = await handler(req)
    except web.HTTPException as e:
        resp = e
    except Exception:
        logging.exception("handler error")
        resp = web.Response(status=500, text="Internal error")

    resp.headers.update({
        "Content-Security-Policy": CSP,
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
        "Referrer-Policy": "no-referrer",
        "Permissions-Policy": "camera=(), microphone=(), geolocation=()",
        "Cross-Origin-Resource-Policy": "same-origin",
    })
    if req.path.startswith("/static/"):
        resp.headers["Cache-Control"] = "no-cache"
    elif "Cache-Control" not in resp.headers:
        resp.headers["Cache-Control"] = "no-store"
    return resp


# ───────────── auth routes ─────────────
_CSRF_KEY = secrets.token_bytes(32)
CSRF_TTL = 3600


def make_login_csrf(ip: str) -> str:
    ts = str(int(time.time()))
    mac = hmac.new(_CSRF_KEY, f"{ip}|{ts}".encode(), hashlib.sha256).hexdigest()
    return f"{ts}.{mac}"


def check_login_csrf(token: str, ip: str) -> bool:
    try:
        ts, mac = token.split(".", 1)
        if not (0 <= time.time() - int(ts) <= CSRF_TTL):
            return False
        good = hmac.new(_CSRF_KEY, f"{ip}|{ts}".encode(), hashlib.sha256).hexdigest()
        return hmac.compare_digest(mac, good)
    except Exception:
        return False


ERRORS = {
    "e": ("err_bad", "Invalid username or password."),
    "l": ("err_lock", "Too many attempts. Please wait a moment."),
    "c": ("err_csrf", "Session expired. Please sign in again."),
    "inv": ("err_bad_invite", "Invalid or expired invite link."),
    "reg_fail": ("err_reg", "Registration failed (username already taken?)."),
}


async def login_get(req: web.Request):
    if get_session(req):
        raise web.HTTPFound("/")
    err = ""
    for k, (key, text) in ERRORS.items():
        if req.query.get(k):
            err = f'<p class="err" role="alert" data-i18n="{key}">{text}</p>'
            break
    html_ = page("login.html").replace("{{CSRF}}", make_login_csrf(client_ip(req))).replace("{{ERROR}}", err)
    return web.Response(text=html_, content_type="text/html")


async def login_post(req: web.Request):
    ip = client_ip(req)
    now = time.time()
    f = fails.get(ip)
    if f and f[2] > now:
        raise web.HTTPFound("/login?l=1")
    data = await req.post()
    if not check_login_csrf(str(data.get("csrf", "")), ip):
        raise web.HTTPFound("/login?c=1")

    user = str(data.get("username", "")).strip()[:64]
    password = str(data.get("password", ""))[:256]

    user_record = db.get_user(user)
    authenticated = False
    role = "player"

    if user_record and db.verify_password(password, user_record["password_hash"]):
        authenticated = True
        role = user_record["role"]
    elif user == DASH_USER and DASH_PASS_HASH and db.verify_password(password, DASH_PASS_HASH):
        authenticated = True
        role = "admin"

    if not authenticated:
        f = fails.setdefault(ip, [0, now, 0])
        if now - f[1] > LOCK_SECONDS:
            f[0], f[1] = 0, now
        f[0] += 1
        if f[0] >= MAX_FAILS:
            f[2] = now + LOCK_SECONDS
        logging.warning("failed login for '%s' from %s", user, ip)
        await asyncio.sleep(1)
        raise web.HTTPFound("/login?e=1")

    fails.pop(ip, None)

    if user_record and user_record.get("totp_enabled") and user_record.get("totp_secret"):
        temp_tok = secrets.token_urlsafe(32)
        pre_auth_2fa[temp_tok] = {"user": user, "role": role, "exp": now + 300}
        html_ = page("login.html").replace("{{CSRF}}", make_login_csrf(ip)).replace(
            "{{ERROR}}",
            '<form method="post" action="/login/2fa" class="twofa-form">'
            f'<input type="hidden" name="token" value="{temp_tok}">'
            '<label>Enter 6-digit Authenticator Code (2FA):</label>'
            '<input name="code" type="text" maxlength="6" pattern="[0-9]{6}" required autofocus placeholder="123456" class="verify-input" style="margin: 8px 0;">'
            '<button type="submit" class="mc-btn cta">Confirm 2FA ↵</button>'
            '</form>'
        )
        return web.Response(text=html_, content_type="text/html")

    token = secrets.token_urlsafe(32)
    sessions[hashlib.sha256(token.encode()).hexdigest()] = {
        "exp": now + SESSION_TTL,
        "last": now,
        "csrf": secrets.token_hex(24),
        "user": user,
        "role": role,
    }
    db.log_audit("login", f"Successful login for {user}", user)
    resp = web.HTTPFound("/")
    set_cookie(resp, "__Host-session", token, SESSION_TTL)
    return resp


async def login_2fa_post(req: web.Request):
    data = await req.post()
    token = str(data.get("token", "")).strip()
    code = str(data.get("code", "")).strip()
    now = time.time()

    item = pre_auth_2fa.get(token)
    if not item or item["exp"] < now:
        pre_auth_2fa.pop(token, None)
        raise web.HTTPFound("/login?c=1")

    user = item["user"]
    u = db.get_user(user)
    if not u or not u.get("totp_secret") or not totp.verify_totp(u["totp_secret"], code):
        raise web.HTTPFound("/login?e=1")

    pre_auth_2fa.pop(token, None)
    sess_tok = secrets.token_urlsafe(32)
    sessions[hashlib.sha256(sess_tok.encode()).hexdigest()] = {
        "exp": now + SESSION_TTL,
        "last": now,
        "csrf": secrets.token_hex(24),
        "user": user,
        "role": item["role"],
    }
    db.log_audit("login_2fa", f"2FA verified login for {user}", user)
    resp = web.HTTPFound("/")
    set_cookie(resp, "__Host-session", sess_tok, SESSION_TTL)
    return resp


async def logout_post(req: web.Request):
    s = get_session(req)
    if not s or not hmac.compare_digest(req.headers.get("X-CSRF-Token", ""), s["csrf"]):
        return web.json_response({"error": "forbidden"}, status=403)
    sessions.clear()
    resp = web.json_response({"ok": True})
    resp.del_cookie("__Host-session", path="/")
    return resp


# ───────────── console & guest view ─────────────
def render_console_page(role: str, csrf_token: str = "") -> str:
    raw = page("console.html")
    csrf_meta = f'<meta name="csrf-token" content="{csrf_token}">' if (role == "admin" and csrf_token) else ""
    raw = raw.replace("{{CSRF_META}}", csrf_meta)
    if role == "admin":
        badge_html = '<span id="role-badge" class="pill ok" data-i18n="badge_admin">⚡ Admin (Full Access)</span>'
        nav_btn = '<a href="/" class="mc-btn ghost small" data-i18n="back_dash">⬅️ Dashboard</a>'
        cmd_content = (
            '<form id="cmd-form" class="cmd-form" autocomplete="off">\n'
            '        <span class="cmd-prompt">&gt;</span>\n'
            '        <input id="cmd-input" type="text" placeholder="Enter command (e.g. whitelist list, list, tps)..." class="mc-input cmd-input" autocomplete="off" spellcheck="false">\n'
            '        <button id="cmd-send" type="submit" class="mc-btn cta cmd-submit">Send ↵</button>\n'
            '      </form>\n'
            '      <div class="quick-commands">\n'
            '        <span class="quick-label">Quick:</span>\n'
            '        <button class="quick-chip" type="button" data-cmd="list">/list</button>\n'
            '        <button class="quick-chip" type="button" data-cmd="whitelist list">/whitelist list</button>\n'
            '        <button class="quick-chip" type="button" data-cmd="tps">/tps</button>\n'
            '      </div>'
        )
    else:
        badge_html = '<span id="role-badge" class="pill" data-i18n="badge_readonly">👁️ Read-Only</span>'
        nav_btn = '<a href="/" class="mc-btn ghost small" data-i18n="back_dash">⬅️ Worlds Dashboard</a>'
        cmd_content = (
            '<div class="readonly-banner">\n'
            '        <span class="readonly-icon">👁️</span>\n'
            '        <div class="readonly-text">\n'
            '          <strong class="readonly-title" data-i18n="readonly_title">View-Only Mode (Read-Only)</strong>\n'
            '          <span class="readonly-sub" data-i18n="readonly_sub">Command execution is disabled without administrator credentials. Only live logs are streamed.</span>\n'
            '        </div>\n'
            '        <a href="/login" class="mc-btn small cta" data-i18n="login_as_admin">🔑 Login to Manage</a>\n'
            '      </div>'
        )
    return (
        raw.replace("{{ROLE_BADGE}}", badge_html)
           .replace("{{NAV_BUTTON}}", nav_btn)
           .replace("{{COMMAND_BAR_CONTENT}}", cmd_content)
    )


async def console_direct(req: web.Request):
    provided_pass = req.match_info.get("password", "")
    now = time.time()

    view_secret = db.get_console_view_secret()
    guest_tok = db.get_guest_token()

    is_valid = False
    if view_secret and hmac.compare_digest(provided_pass, view_secret):
        is_valid = True
    elif guest_tok and hmac.compare_digest(provided_pass, guest_tok):
        is_valid = True
    elif DASH_PASS_HASH and db.verify_password(provided_pass, DASH_PASS_HASH):
        is_valid = True
    elif hmac.compare_digest(provided_pass, RCON_PASS):
        is_valid = True
    else:
        for u in db.list_users():
            if u["role"] == "admin":
                full = db.get_user(u["username"])
                if full and db.verify_password(provided_pass, full["password_hash"]):
                    is_valid = True
                    break

    if not is_valid:
        return web.Response(
            text="<!doctype html><html><body style='background:#14100d;color:#ff5555;font-family:monospace;padding:40px;text-align:center;'>"
                 "<h1>403 Forbidden</h1><p>Invalid console password or secret key in URL.</p>"
                 "<p><a href='/login' style='color:#ffff55;'>Go to Login</a></p></body></html>",
            status=403,
            content_type="text/html",
        )

    existing = get_session(req)
    if existing and existing.get("role") == "admin":
        role = "admin"
        token = None
    else:
        role = "viewer"
        token = secrets.token_urlsafe(32)
        sessions[hashlib.sha256(token.encode()).hexdigest()] = {
            "exp": now + SESSION_TTL,
            "last": now,
            "csrf": secrets.token_hex(24),
            "user": "Guest",
            "role": "viewer",
        }
        db.log_audit("console_view", f"Read-only console session started from {client_ip(req)}", "viewer")

    resp = web.Response(text=render_console_page(role), content_type="text/html")
    if token:
        set_cookie(resp, "__Host-session", token, SESSION_TTL)
    return resp


async def guest_view(req: web.Request):
    token = req.match_info.get("token", "")
    now = time.time()

    valid_guest_tok = db.get_guest_token()
    valid_console_tok = db.get_console_view_secret()

    is_valid = False
    if valid_guest_tok and hmac.compare_digest(token, valid_guest_tok):
        is_valid = True
    elif valid_console_tok and hmac.compare_digest(token, valid_console_tok):
        is_valid = True

    if not is_valid:
        return web.Response(
            text="<!doctype html><html><body style='background:#14100d;color:#ff5555;font-family:monospace;padding:40px;text-align:center;'>"
                 "<h1>403 Forbidden</h1><p>Invalid guest view link or expired token.</p>"
                 "<p><a href='/login' style='color:#ffff55;'>Go to Login</a></p></body></html>",
            status=403,
            content_type="text/html",
        )

    sess_tok = secrets.token_urlsafe(32)
    sessions[hashlib.sha256(sess_tok.encode()).hexdigest()] = {
        "exp": now + SESSION_TTL,
        "last": now,
        "csrf": secrets.token_hex(24),
        "user": "Guest",
        "role": "viewer",
    }
    db.log_audit("guest_view", f"Guest view access from {client_ip(req)}", "guest")

    target = "/console" if req.path.rstrip("/").endswith("/console") else "/"
    resp = web.HTTPFound(target)
    set_cookie(resp, "__Host-session", sess_tok, SESSION_TTL)
    return resp


async def console_page(req: web.Request):
    s = get_session(req)
    if not s:
        raise web.HTTPFound("/login")
    if s.get("role") != "admin":
        return web.Response(
            text="<!doctype html><html><body style='background:#14100d;color:#ff5555;font-family:monospace;padding:40px;text-align:center;'>"
                 "<h1>403 Forbidden</h1><p>Console access is restricted to administrators only.</p>"
                 "<p><a href='/' style='color:#ffff55;'>Return to Dashboard</a></p></body></html>",
            status=403,
            content_type="text/html",
        )
    return web.Response(text=render_console_page("admin", s.get("csrf", "")), content_type="text/html")


async def console_stream(req: web.Request):
    s = get_session(req)
    if not s or s.get("role") != "admin":
        return web.Response(status=403, text="Forbidden: Console access restricted to administrators")

    resp = web.StreamResponse(
        status=200,
        reason="OK",
        headers={
            "Content-Type": "text/event-stream",
            "Cache-Control": "no-cache, no-transform",
            "Connection": "keep-alive",
            "X-Accel-Buffering": "no",
        },
    )
    await resp.prepare(req)

    log_path = SERVER_DIR / "logs" / "latest.log"

    rcon_noise = (
        "issued server command: /list",
        "issued server command: list",
        "Thread RCON Client",
        "RCON Listener",
        "Thread RCON",
        "[RCON Client",
    )

    try:
        if log_path.exists():
            with open(log_path, "r", encoding="utf-8", errors="replace") as f:
                lines = f.readlines()[-160:]
                for line in lines:
                    msg = line.rstrip("\r\n")
                    if any(p in msg for p in rcon_noise):
                        continue
                    await resp.write(f"data: {msg}\n\n".encode("utf-8"))
    except Exception as e:
        await resp.write(f"data: [Console] Error reading log history: {e}\n\n".encode("utf-8"))

    last_ping = time.time()
    try:
        with open(log_path, "r", encoding="utf-8", errors="replace") as f:
            f.seek(0, os.SEEK_END)
            while True:
                line = f.readline()
                if line:
                    msg = line.rstrip("\r\n")
                    if not any(p in msg for p in rcon_noise):
                        await resp.write(f"data: {msg}\n\n".encode("utf-8"))
                else:
                    await asyncio.sleep(0.35)

                if time.time() - last_ping > 12:
                    await resp.write(b": ping\n\n")
                    last_ping = time.time()
    except (asyncio.CancelledError, ConnectionResetError):
        pass

    return resp


async def console_cmd(req: web.Request):
    s = get_session(req)
    if not s or s.get("role") != "admin":
        return web.json_response({
            "error": "Forbidden: Read-only console. Login as administrator to execute commands."
        }, status=403)

    csrf = req.headers.get("X-CSRF-Token", "")
    if not csrf or not hmac.compare_digest(csrf, s.get("csrf", "")):
        return web.json_response({"error": "Forbidden: Invalid or missing CSRF token"}, status=403)

    data = await req.json()
    cmd = str(data.get("cmd", "")).strip()
    if not cmd:
        return web.json_response({"error": "Empty command"}, status=400)

    if "\n" in cmd or "\r" in cmd or "\x00" in cmd:
        return web.json_response({"error": "Forbidden: Newlines and control characters are not allowed."}, status=400)

    if len(cmd) > 256:
        return web.json_response({"error": "Command too long (maximum 256 characters)."}, status=400)

    try:
        out = await asyncio.to_thread(rcon_exec, cmd, 8)
        db.log_audit("rcon_cmd", f"Command executed: {cmd}", s.get("user", "admin"))
    except Exception as e:
        out = f"RCON execution error: {e}"

    return web.json_response({"ok": True, "output": out or "Command executed (no output)."})


# ───────────── self-registration ─────────────
async def register_get(req: web.Request):
    invite_code = req.query.get("invite", "").strip()
    open_reg = db.get_setting("open_registration", "0") == "1"

    role_name = "Player"
    invite_class = ""

    if invite_code:
        inv = db.get_invite(invite_code)
        if not inv:
            raise web.HTTPFound("/login?inv=1")
        role_name = "Administrator" if inv["role"] == "admin" else "Player"
        invite_class = "admin" if inv["role"] == "admin" else ""
    elif not open_reg:
        raise web.HTTPFound("/login?inv=1")

    html_ = (
        page("register.html")
        .replace("{{CSRF}}", make_login_csrf(client_ip(req)))
        .replace("{{INVITE_CODE}}", invite_code)
        .replace("{{INVITE_ROLE_NAME}}", role_name)
        .replace("{{INVITE_CLASS}}", invite_class)
        .replace("{{ERROR}}", "")
    )
    return web.Response(text=html_, content_type="text/html")


async def register_post(req: web.Request):
    ip = client_ip(req)
    data = await req.post()
    if not check_login_csrf(str(data.get("csrf", "")), ip):
        raise web.HTTPFound("/register?c=1")

    username = str(data.get("username", "")).strip()
    password = str(data.get("password", ""))
    confirm = str(data.get("password_confirm", ""))
    invite_code = str(data.get("invite", "")).strip()
    open_reg = db.get_setting("open_registration", "0") == "1"

    if len(username) < 3 or len(username) > 24 or not re.match(r"^[A-Za-z0-9_]+$", username):
        return web.Response(text="Invalid username format. Use 3-24 letters/numbers/underscores.", status=400)
    if password != confirm:
        return web.Response(text="Passwords do not match.", status=400)
    if len(password) < 8:
        return web.Response(text="Password must be at least 8 characters long.", status=400)
    if len(password) > 128:
        return web.Response(text="Password must not exceed 128 characters.", status=400)

    assigned_role = "player"
    if invite_code:
        inv = db.get_invite(invite_code)
        if not inv:
            raise web.HTTPFound("/login?inv=1")
        assigned_role = inv["role"]
        db.use_invite(invite_code)
    elif not open_reg:
        raise web.HTTPFound("/login?inv=1")

    ok = db.create_user(username, password, role=assigned_role)
    if not ok:
        raise web.HTTPFound("/login?reg_fail=1")

    db.log_audit("register", f"User {username} registered ({assigned_role})", username)

    now = time.time()
    token = secrets.token_urlsafe(32)
    sessions[hashlib.sha256(token.encode()).hexdigest()] = {
        "exp": now + SESSION_TTL,
        "last": now,
        "csrf": secrets.token_hex(24),
        "user": username,
        "role": assigned_role,
    }
    resp = web.HTTPFound("/")
    set_cookie(resp, "__Host-session", token, SESSION_TTL)
    return resp


# ───────────── admin api ─────────────
def require_admin(req: web.Request):
    s = get_session(req)
    if not s or s.get("role") != "admin":
        raise web.HTTPForbidden(text=json.dumps({"error": "Admin required"}), content_type="application/json")
    if req.method in ("POST", "PUT", "DELETE", "PATCH"):
        csrf = req.headers.get("X-CSRF-Token", "")
        if not csrf or not hmac.compare_digest(csrf, s.get("csrf", "")):
            raise web.HTTPForbidden(text=json.dumps({"error": "Forbidden: Invalid or missing CSRF token"}), content_type="application/json")
    return s


async def admin_get_invites(req: web.Request):
    require_admin(req)
    return web.json_response({"invites": db.list_invites()})


async def admin_create_invite(req: web.Request):
    s = require_admin(req)
    data = await req.json()
    role = str(data.get("role", "player")).strip()
    if role not in ("player", "admin"):
        return web.json_response({"error": "Invalid role. Allowed values: player, admin"}, status=400)
    try:
        max_uses = int(data.get("max_uses", 1))
        if max_uses < 0 or max_uses > 1000:
            max_uses = 1
    except (ValueError, TypeError):
        max_uses = 1
    code = db.create_invite(role=role, created_by=s.get("user", "admin"), max_uses=max_uses, days_valid=30)
    origin = f"{req.scheme}://{req.host}"
    link = f"{origin}/register?invite={code}"
    db.log_audit("create_invite", f"Created {role} invite ({code})", s.get("user", "admin"))
    return web.json_response({"ok": True, "code": code, "link": link})


async def admin_delete_invite(req: web.Request):
    s = require_admin(req)
    code = req.match_info.get("code", "")
    if not re.match(r"^[a-zA-Z0-9_\-]{4,64}$", code):
        return web.json_response({"error": "Invalid invite code format"}, status=400)
    db.delete_invite(code)
    db.log_audit("delete_invite", f"Deleted invite {code}", s.get("user", "admin"))
    return web.json_response({"ok": True})


async def admin_get_settings(req: web.Request):
    s = require_admin(req)
    u = db.get_user(s.get("user", "admin"))
    view_secret = db.get_console_view_secret()
    guest_tok = db.get_guest_token()
    origin = f"{req.scheme}://{req.host}"
    return web.json_response({
        "open_registration": db.get_setting("open_registration", "0"),
        "admin_2fa_enabled": bool(u and u.get("totp_enabled")),
        "console_view_secret": view_secret,
        "console_view_link": f"{origin}/console/{view_secret}",
        "guest_view_token": guest_tok,
        "guest_view_link": f"{origin}/view/{guest_tok}",
    })


async def admin_regen_console_secret(req: web.Request):
    s = require_admin(req)
    new_secret = secrets.token_urlsafe(16)
    db.set_console_view_secret(new_secret)
    db.log_audit("regen_console_secret", "Regenerated console view secret", s.get("user", "admin"))
    origin = f"{req.scheme}://{req.host}"
    return web.json_response({
        "ok": True,
        "console_view_secret": new_secret,
        "console_view_link": f"{origin}/console/{new_secret}",
    })


async def admin_regen_guest_token(req: web.Request):
    s = require_admin(req)
    new_tok = secrets.token_urlsafe(16)
    db.set_guest_token(new_tok)
    db.log_audit("regen_guest_token", "Regenerated guest view token", s.get("user", "admin"))
    origin = f"{req.scheme}://{req.host}"
    return web.json_response({
        "ok": True,
        "guest_view_token": new_tok,
        "guest_view_link": f"{origin}/view/{new_tok}",
    })


async def admin_post_settings(req: web.Request):
    s = require_admin(req)
    data = await req.json()
    if "open_registration" in data:
        val = "1" if str(data["open_registration"]) in ("1", "true", "True") else "0"
        db.set_setting("open_registration", val)
        db.log_audit("setting_change", f"Open registration set to {val}", s.get("user", "admin"))
    return web.json_response({"ok": True})


async def admin_setup_2fa(req: web.Request):
    s = require_admin(req)
    username = s.get("user", "admin")
    secret = totp.generate_secret()
    uri = totp.get_totp_uri(username, secret, issuer="Minecraft Server")
    db.set_user_totp(username, secret, enabled=False)
    return web.json_response({"secret": secret, "uri": uri})


async def admin_verify_2fa(req: web.Request):
    s = require_admin(req)
    username = s.get("user", "admin")
    data = await req.json()
    code = str(data.get("code", "")).strip()
    u = db.get_user(username)
    if not u or not u.get("totp_secret"):
        return web.json_response({"ok": False, "error": "No 2FA secret pending"})

    if totp.verify_totp(u["totp_secret"], code):
        db.set_user_totp(username, u["totp_secret"], enabled=True)
        db.log_audit("enable_2fa", f"2FA enabled for {username}", username)
        return web.json_response({"ok": True})
    return web.json_response({"ok": False, "error": "Invalid verification code"})


async def admin_disable_2fa(req: web.Request):
    s = require_admin(req)
    username = s.get("user", "admin")
    db.set_user_totp(username, None, enabled=False)
    db.log_audit("disable_2fa", f"2FA disabled for {username}", username)
    return web.json_response({"ok": True})


async def admin_get_users(req: web.Request):
    require_admin(req)
    return web.json_response({"users": db.list_users()})


async def admin_delete_user(req: web.Request):
    s = require_admin(req)
    username = req.match_info.get("username", "")
    if not re.match(r"^[a-zA-Z0-9_\-\.]{1,32}$", username):
        return web.json_response({"error": "Invalid username format"}, status=400)
    if username.lower() == s.get("user", "").lower():
        return web.json_response({"error": "Cannot delete your own active administrator account"}, status=400)
    ok = db.delete_user(username)
    if ok:
        db.log_audit("delete_user", f"Deleted user {username}", s.get("user", "admin"))
        return web.json_response({"ok": True})
    return web.json_response({"error": "Cannot delete user (last admin?)"}, status=400)


async def admin_get_whitelist(req: web.Request):
    require_admin(req)
    try:
        out = await asyncio.to_thread(rcon_exec, "whitelist list", 4)
        players = []
        if ":" in out:
            players = [p.strip() for p in out.split(":", 1)[1].split(",") if p.strip()]
        return web.json_response({"whitelist": players})
    except Exception as e:
        return web.json_response({"whitelist": [], "error": str(e)})


async def admin_whitelist_add(req: web.Request):
    s = require_admin(req)
    data = await req.json()
    player = str(data.get("player", "")).strip()
    if not player or not re.match(r"^[A-Za-z0-9_]{1,16}$", player):
        return web.json_response({"error": "Invalid nickname (1-16 alphanumeric characters or underscores)"}, status=400)

    try:
        out = await asyncio.to_thread(rcon_exec, f"whitelist add {player}", 4)
        db.log_audit("whitelist_add", f"Added {player} to whitelist", s.get("user", "admin"))
        return web.json_response({"ok": True, "output": out})
    except Exception as e:
        return web.json_response({"error": str(e)}, status=500)


async def admin_whitelist_remove(req: web.Request):
    s = require_admin(req)
    data = await req.json()
    player = str(data.get("player", "")).strip()
    if not player or not re.match(r"^[A-Za-z0-9_]{1,16}$", player):
        return web.json_response({"error": "Invalid nickname (1-16 alphanumeric characters or underscores)"}, status=400)

    try:
        out = await asyncio.to_thread(rcon_exec, f"whitelist remove {player}", 4)
        db.log_audit("whitelist_remove", f"Removed {player} from whitelist", s.get("user", "admin"))
        return web.json_response({"ok": True, "output": out})
    except Exception as e:
        return web.json_response({"error": str(e)}, status=500)


# ───────────── data ─────────────
def _query_worlds():
    if DB_FILE.exists():
        con = sqlite3.connect(f"file:{DB_FILE}?mode=ro", uri=True, timeout=3)
        try:
            worlds = con.execute("SELECT id, title, kind, is_open FROM worlds ORDER BY rowid").fetchall()
            access = {}
            for wid, player in con.execute("SELECT world_id, player FROM world_access ORDER BY player"):
                access.setdefault(wid, []).append(player)
            return worlds, access
        finally:
            con.close()

    # Automatic discovery for standard Minecraft servers
    worlds = []
    try:
        for d in sorted(SERVER_DIR.iterdir()):
            if d.is_dir() and (d / "level.dat").exists() and not d.name.endswith(("_nether", "_the_end")):
                wid = d.name
                title = wid.replace("_", " ").title()
                kind = "hub" if wid == "world" else "regular"
                worlds.append((wid, title, kind, 1))
    except Exception:
        pass

    if not worlds:
        worlds.append(("world", "Main World", "hub", 1))
    return worlds, {}


def _dir_size(path: Path) -> int:
    total = 0
    for root, _dirs, files in os.walk(path, followlinks=False):
        for name in files:
            try:
                total += os.lstat(os.path.join(root, name)).st_size
            except OSError:
                pass
    return total


def _world_size(wid: str) -> int:
    total = 0
    for suffix in ("", "_nether", "_the_end"):
        d = SERVER_DIR / f"{wid}{suffix}"
        if d.is_dir():
            total += _dir_size(d)
    return total


def cached(key: str, ttl: float, fn):
    hit = _cache.get(key)
    if hit and time.time() - hit[0] < ttl:
        return hit[1]
    val = fn()
    _cache[key] = (time.time(), val)
    return val


def _mc_ping(host="127.0.0.1", port=25565, timeout=1.5):
    """Query Minecraft Java server status via standard Server List Ping protocol."""
    import socket
    import json
    try:
        with socket.create_connection((host, int(port)), timeout=timeout) as s:
            s.settimeout(timeout)
            host_b = host.encode('utf-8')
            data = b'\x00\x2f' + bytes([len(host_b)]) + host_b + (int(port)).to_bytes(2, 'big') + b'\x01'
            s.sendall(bytes([len(data)]) + data + b'\x01\x00')
            resp = b''
            while True:
                chunk = s.recv(4096)
                if not chunk:
                    break
                resp += chunk
                if b'}' in resp:
                    break
            idx = resp.find(b'{')
            if idx != -1:
                js = json.loads(resp[idx:].decode('utf-8', errors='ignore'))
                p_data = js.get("players", {})
                online_count = p_data.get("online", 0)
                sample = p_data.get("sample") or []
                names = [p.get("name") for p in sample if p.get("name")]
                return True, online_count, names
    except Exception:
        pass
    return False, 0, []


def _players():
    ok, count, names = _mc_ping()
    if ok and count == 0:
        return True, []
    if ok and names and len(names) >= count:
        return True, names
    # Only if players are active and sample omitted names, fallback to RCON
    try:
        out = rcon_exec("list", 4)
    except Exception:
        return ok, names
    if ":" in out:
        names = [p.strip() for p in out.split(":", 1)[1].split(",") if p.strip().replace("_", "").isalnum()]
    return True, names


async def api_state(req: web.Request):
    s = get_session(req)
    try:
        worlds, access = await asyncio.to_thread(_query_worlds)
    except Exception:
        logging.exception("db error")
        worlds, access = [], {}
    online, players = await asyncio.to_thread(cached, "players", 15, _players)
    out = []
    is_viewer = (s.get("role") == "viewer")
    for wid, title, kind, is_open in worlds:
        if not WORLD_ID_RE.match(wid):
            continue
        if is_viewer and not is_open:
            continue
        size = await asyncio.to_thread(cached, f"size:{wid}", 300, lambda w=wid: _world_size(w))
        try:
            mtime = int((SERVER_DIR / wid / "level.dat").stat().st_mtime)
        except OSError:
            mtime = 0
        out.append({"id": wid, "title": title, "kind": kind, "open": bool(is_open),
                    "access": access.get(wid, []), "size": size, "mtime": mtime})
    return web.json_response({
        "csrf": s["csrf"],
        "user": s.get("user", "player"),
        "role": s.get("role", "player"),
        "server_online": online,
        "players": players,
        "worlds": out,
    })


async def api_logo(req: web.Request):
    wid = req.match_info["wid"]
    if not WORLD_ID_RE.match(wid):
        raise web.HTTPNotFound()
    worlds, _ = await asyncio.to_thread(_query_worlds)
    if wid not in {w[0] for w in worlds}:
        raise web.HTTPNotFound()
    CACHE.mkdir(exist_ok=True)
    f = CACHE / f"{wid}.png"
    lock = _logo_locks.setdefault(wid, asyncio.Lock())
    async with lock:
        if not f.exists() or time.time() - f.stat().st_mtime > LOGO_TTL:
            try:
                data = await asyncio.to_thread(render_world, SERVER_DIR, wid)
            except Exception:
                logging.exception("render failed for %s", wid)
                data = placeholder("x")
            f.write_bytes(data)
    resp = web.FileResponse(f)
    resp.headers["Cache-Control"] = "private, max-age=300"
    return resp


async def index(req: web.Request):
    return web.Response(text=page("dashboard.html"), content_type="text/html")


def build_app() -> web.Application:
    db.init_db(default_user=DASH_USER, default_pass_hash=DASH_PASS_HASH)

    app = web.Application(middlewares=[guard], client_max_size=32768)
    app.add_routes([
        web.get("/", index),
        web.get("/login", login_get),
        web.post("/login", login_post),
        web.post("/login/2fa", login_2fa_post),
        web.post("/logout", logout_post),
        web.get("/register", register_get),
        web.post("/register", register_post),
        # Guest share/view link routes
        web.get(r"/view/{token}", guest_view),
        web.get(r"/view/{token}/console", guest_view),
        web.get(r"/share/{token}", guest_view),
        web.get(r"/share/{token}/console", guest_view),
        web.post("/api/admin/guest-token/regenerate", admin_regen_guest_token),
        # Live console routes
        web.get(r"/console/{password}", console_direct),
        web.get("/console", console_page),
        web.get("/api/console/stream", console_stream),
        web.post("/api/console/cmd", console_cmd),
        # Dashboard state & logos
        web.get("/api/state", api_state),
        web.get(r"/api/logo/{wid}.png", api_logo),
        # Admin management endpoints
        web.get("/api/admin/invites", admin_get_invites),
        web.post("/api/admin/invites", admin_create_invite),
        web.delete(r"/api/admin/invites/{code}", admin_delete_invite),
        web.get("/api/admin/settings", admin_get_settings),
        web.post("/api/admin/settings", admin_post_settings),
        web.post("/api/admin/console-secret/regenerate", admin_regen_console_secret),
        web.post("/api/admin/2fa/setup", admin_setup_2fa),
        web.post("/api/admin/2fa/verify", admin_verify_2fa),
        web.post("/api/admin/2fa/disable", admin_disable_2fa),
        web.get("/api/admin/users", admin_get_users),
        web.delete(r"/api/admin/users/{username}", admin_delete_user),
        web.get("/api/admin/whitelist", admin_get_whitelist),
        web.post("/api/admin/whitelist/add", admin_whitelist_add),
        web.post("/api/admin/whitelist/remove", admin_whitelist_remove),
        # Static assets
        web.static("/static", BASE / "static", follow_symlinks=False),
    ])
    return app


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
    print(f"🚀 Starting Minecraft Dashboard on {BIND_HOST}:{BIND_PORT} ...")
    web.run_app(build_app(), host=BIND_HOST, port=int(BIND_PORT), access_log=None)
