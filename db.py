"""Database storage for Dashboard users, roles, 2FA, invite links, and settings."""
import hashlib
import hmac
import os
from pathlib import Path
import secrets
import sqlite3
import time

DB_PATH = Path(__file__).parent / "dashboard.db"


def get_conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH, timeout=5)
    conn.row_factory = sqlite3.Row
    return conn


def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    n, r, p = 16384, 8, 1
    digest = hashlib.scrypt(password.encode("utf-8"), salt=salt, n=n, r=r, p=p, dklen=32, maxmem=128 * 1024 * 1024)
    return f"scrypt${n}${r}${p}${salt.hex()}${digest.hex()}"


def verify_password(password: str, stored: str) -> bool:
    try:
        scheme, n, r, p, salt, digest = stored.split("$")
        if scheme != "scrypt":
            return False
        calc = hashlib.scrypt(
            password.encode("utf-8"),
            salt=bytes.fromhex(salt),
            n=int(n),
            r=int(r),
            p=int(p),
            dklen=len(bytes.fromhex(digest)),
            maxmem=128 * 1024 * 1024,
        )
        return hmac.compare_digest(calc, bytes.fromhex(digest))
    except Exception:
        return False


def init_db(default_user: str = "", default_pass_hash: str = ""):
    with get_conn() as conn:
        conn.execute("""
            CREATE TABLE IF NOT EXISTS users (
                username TEXT PRIMARY KEY COLLATE NOCASE,
                password_hash TEXT NOT NULL,
                role TEXT NOT NULL DEFAULT 'player',
                totp_secret TEXT DEFAULT NULL,
                totp_enabled INTEGER NOT NULL DEFAULT 0,
                created_at INTEGER NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS invites (
                code TEXT PRIMARY KEY,
                role TEXT NOT NULL DEFAULT 'player',
                created_by TEXT NOT NULL,
                created_at INTEGER NOT NULL,
                expires_at INTEGER NOT NULL DEFAULT 0,
                max_uses INTEGER NOT NULL DEFAULT 1,
                uses INTEGER NOT NULL DEFAULT 0
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
        """)
        conn.execute("""
            CREATE TABLE IF NOT EXISTS audit (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                action TEXT NOT NULL,
                details TEXT NOT NULL,
                actor TEXT NOT NULL,
                timestamp INTEGER NOT NULL
            )
        """)
        conn.commit()

        # Defaults
        cur = conn.execute("SELECT COUNT(*) FROM users")
        user_count = cur.fetchone()[0]
        if user_count == 0 and default_user and default_pass_hash:
            conn.execute(
                "INSERT OR REPLACE INTO users (username, password_hash, role, created_at) VALUES (?, ?, 'admin', ?)",
                (default_user, default_pass_hash, int(time.time())),
            )
            conn.commit()

        # Default settings
        conn.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('open_registration', '0')")
        conn.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('server_host', 'mc.dosimple.app')")
        conn.execute("INSERT OR IGNORE INTO settings (key, value) VALUES ('server_port', '25565')")
        cur_secret = conn.execute("SELECT value FROM settings WHERE key = 'console_view_secret'").fetchone()
        if not cur_secret or not cur_secret[0]:
            conn.execute(
                "INSERT OR REPLACE INTO settings (key, value) VALUES ('console_view_secret', ?)",
                (secrets.token_urlsafe(16),),
            )
        cur_guest = conn.execute("SELECT value FROM settings WHERE key = 'guest_view_token'").fetchone()
        if not cur_guest or not cur_guest[0]:
            conn.execute(
                "INSERT OR REPLACE INTO settings (key, value) VALUES ('guest_view_token', ?)",
                (secrets.token_urlsafe(16),),
            )
        conn.commit()


# ── Guest & Console View Secret ──
def get_console_view_secret() -> str:
    sec = get_setting("console_view_secret", "")
    if not sec:
        sec = secrets.token_urlsafe(16)
        set_setting("console_view_secret", sec)
    return sec


def set_console_view_secret(new_secret: str):
    set_setting("console_view_secret", new_secret)


def get_guest_token() -> str:
    tok = get_setting("guest_view_token", "")
    if not tok:
        tok = secrets.token_urlsafe(16)
        set_setting("guest_view_token", tok)
    return tok


def set_guest_token(new_tok: str):
    set_setting("guest_view_token", new_tok)


# ── Users ──
def get_user(username: str) -> dict | None:
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM users WHERE username = ?", (username,)).fetchone()
        return dict(row) if row else None


def list_users() -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute(
            "SELECT username, role, totp_enabled, created_at FROM users ORDER BY created_at ASC"
        ).fetchall()
        return [dict(r) for r in rows]


def create_user(username: str, password_raw: str, role: str = "player") -> bool:
    role = "admin" if role == "admin" else "player"
    p_hash = hash_password(password_raw)
    try:
        with get_conn() as conn:
            conn.execute(
                "INSERT INTO users (username, password_hash, role, created_at) VALUES (?, ?, ?, ?)",
                (username.strip(), p_hash, role, int(time.time())),
            )
            conn.commit()
        return True
    except sqlite3.IntegrityError:
        return False


def update_user_password(username: str, password_raw: str) -> bool:
    p_hash = hash_password(password_raw)
    with get_conn() as conn:
        cur = conn.execute("UPDATE users SET password_hash = ? WHERE username = ?", (p_hash, username))
        conn.commit()
        return cur.rowcount > 0


def update_user_role(username: str, role: str) -> bool:
    role = "admin" if role == "admin" else "player"
    with get_conn() as conn:
        cur = conn.execute("UPDATE users SET role = ? WHERE username = ?", (role, username))
        conn.commit()
        return cur.rowcount > 0


def delete_user(username: str) -> bool:
    with get_conn() as conn:
        # Prevent deleting the last admin
        cur = conn.execute("SELECT COUNT(*) FROM users WHERE role = 'admin' AND username != ?", (username,))
        if cur.fetchone()[0] == 0:
            return False
        del_cur = conn.execute("DELETE FROM users WHERE username = ?", (username,))
        conn.commit()
        return del_cur.rowcount > 0


def set_user_totp(username: str, secret: str | None, enabled: bool) -> bool:
    with get_conn() as conn:
        cur = conn.execute(
            "UPDATE users SET totp_secret = ?, totp_enabled = ? WHERE username = ?",
            (secret, 1 if enabled else 0, username),
        )
        conn.commit()
        return cur.rowcount > 0


# ── Invites ──
def create_invite(role: str = "player", created_by: str = "admin", max_uses: int = 1, days_valid: int = 7) -> str:
    code = secrets.token_urlsafe(16)
    role = "admin" if role == "admin" else "player"
    now = int(time.time())
    expires_at = now + (days_valid * 86400) if days_valid > 0 else 0
    with get_conn() as conn:
        conn.execute(
            "INSERT INTO invites (code, role, created_by, created_at, expires_at, max_uses, uses) VALUES (?, ?, ?, ?, ?, ?, 0)",
            (code, role, created_by, now, expires_at, max_uses),
        )
        conn.commit()
    return code


def get_invite(code: str) -> dict | None:
    now = int(time.time())
    with get_conn() as conn:
        row = conn.execute("SELECT * FROM invites WHERE code = ?", (code,)).fetchone()
        if not row:
            return None
        inv = dict(row)
        if inv["expires_at"] > 0 and inv["expires_at"] < now:
            return None
        if inv["max_uses"] > 0 and inv["uses"] >= inv["max_uses"]:
            return None
        return inv


def use_invite(code: str) -> bool:
    with get_conn() as conn:
        cur = conn.execute(
            "UPDATE invites SET uses = uses + 1 WHERE code = ? AND (max_uses = 0 OR uses < max_uses)",
            (code,),
        )
        conn.commit()
        return cur.rowcount > 0


def delete_invite(code: str) -> bool:
    with get_conn() as conn:
        cur = conn.execute("DELETE FROM invites WHERE code = ?", (code,))
        conn.commit()
        return cur.rowcount > 0


def list_invites() -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM invites ORDER BY created_at DESC").fetchall()
        return [dict(r) for r in rows]


# ── Settings ──
def get_setting(key: str, default: str = "") -> str:
    with get_conn() as conn:
        row = conn.execute("SELECT value FROM settings WHERE key = ?", (key,)).fetchone()
        return row[0] if row else default


def set_setting(key: str, value: str):
    with get_conn() as conn:
        conn.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, str(value)))
        conn.commit()


# ── Audit ──
def log_audit(action: str, details: str, actor: str = "system"):
    try:
        with get_conn() as conn:
            conn.execute(
                "INSERT INTO audit (action, details, actor, timestamp) VALUES (?, ?, ?, ?)",
                (action, details, actor, int(time.time())),
            )
            conn.commit()
    except Exception:
        pass


def list_audit(limit: int = 50) -> list[dict]:
    with get_conn() as conn:
        rows = conn.execute("SELECT * FROM audit ORDER BY id DESC LIMIT ?", (limit,)).fetchall()
        return [dict(r) for r in rows]
