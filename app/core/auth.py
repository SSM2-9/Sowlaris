"""Accounts, remember-me sessions, password reset, profile edit, account deletion.
Storage: SQLite file `sowlaris.db` (created automatically). Passwords use PBKDF2-SHA256."""
import hashlib, hmac, json, os, secrets, smtplib, sqlite3, ssl, time
from email.message import EmailMessage

DB = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "sowlaris.db")
SESSION_DAYS, RESET_MINUTES = 30, 15


def _c():
    c = sqlite3.connect(DB)
    c.row_factory = sqlite3.Row
    return c


def init():
    with _c() as c:
        c.executescript("""
        CREATE TABLE IF NOT EXISTS users(id INTEGER PRIMARY KEY, email TEXT UNIQUE, name TEXT,
            farm TEXT, region TEXT, pw_hash TEXT, salt TEXT, created REAL);
        CREATE TABLE IF NOT EXISTS sessions(token_hash TEXT PRIMARY KEY, user_id INTEGER, expires REAL);
        CREATE TABLE IF NOT EXISTS resets(user_id INTEGER, code_hash TEXT, expires REAL);
        CREATE TABLE IF NOT EXISTS setups(user_id INTEGER PRIMARY KEY, data TEXT);""")


def _hash(pw, salt):
    return hashlib.pbkdf2_hmac("sha256", pw.encode(), bytes.fromhex(salt), 200_000).hex()


def _sha(s):
    return hashlib.sha256(s.encode()).hexdigest()


def signup(name, email, password, farm="", region=""):
    email = email.strip().lower()
    if not name.strip() or "@" not in email:
        return None, "Enter your name and a valid email."
    if len(password) < 8:
        return None, "Use a password with at least 8 characters."
    salt = secrets.token_hex(16)
    try:
        with _c() as c:
            cur = c.execute("INSERT INTO users(email,name,farm,region,pw_hash,salt,created) VALUES(?,?,?,?,?,?,?)",
                            (email, name.strip(), farm, region, _hash(password, salt), salt, time.time()))
            return cur.lastrowid, ""
    except sqlite3.IntegrityError:
        return None, "An account with this email already exists."


def login(email, password):
    with _c() as c:
        u = c.execute("SELECT * FROM users WHERE email=?", (email.strip().lower(),)).fetchone()
    if u and hmac.compare_digest(u["pw_hash"], _hash(password, u["salt"])):
        return dict(u)
    return None


def create_session(user_id):
    token = secrets.token_urlsafe(32)
    with _c() as c:
        c.execute("INSERT INTO sessions VALUES(?,?,?)", (_sha(token), user_id, time.time() + SESSION_DAYS * 86400))
    return token, SESSION_DAYS


def user_from_token(token):
    with _c() as c:
        row = c.execute("SELECT u.* FROM sessions s JOIN users u ON u.id=s.user_id "
                        "WHERE s.token_hash=? AND s.expires>?", (_sha(token), time.time())).fetchone()
    return dict(row) if row else None


def end_session(token):
    with _c() as c:
        c.execute("DELETE FROM sessions WHERE token_hash=?", (_sha(token),))


def get_user(uid):
    with _c() as c:
        r = c.execute("SELECT * FROM users WHERE id=?", (uid,)).fetchone()
    return dict(r) if r else None


def update_profile(uid, name, email, farm, region):
    try:
        with _c() as c:
            c.execute("UPDATE users SET name=?,email=?,farm=?,region=? WHERE id=?",
                      (name.strip(), email.strip().lower(), farm, region, uid))
        return ""
    except sqlite3.IntegrityError:
        return "That email is already used by another account."


def change_password(uid, current, new):
    u = get_user(uid)
    if not hmac.compare_digest(u["pw_hash"], _hash(current, u["salt"])):
        return "Current password is not correct."
    if len(new) < 8:
        return "Use a password with at least 8 characters."
    salt = secrets.token_hex(16)
    with _c() as c:
        c.execute("UPDATE users SET pw_hash=?,salt=? WHERE id=?", (_hash(new, salt), salt, uid))
    return ""


def delete_account(uid):
    with _c() as c:
        for t in ("sessions", "resets", "setups"):
            c.execute(f"DELETE FROM {t} WHERE user_id=?", (uid,))
        c.execute("DELETE FROM users WHERE id=?", (uid,))


# ---- Forgot password (email code) ----
def _send_email(to, code):
    """Set SOWLARIS_SMTP_HOST / _PORT / _USER / _PASS to send real email (e.g. a Gmail app password).
    Returns True if sent. If not configured, the UI shows the code on screen (demo mode)."""
    host, user, pw = (os.getenv(k) for k in ("SOWLARIS_SMTP_HOST", "SOWLARIS_SMTP_USER", "SOWLARIS_SMTP_PASS"))
    if not (host and user and pw):
        return False
    msg = EmailMessage()
    msg["Subject"], msg["From"], msg["To"] = "Your Sowlaris reset code", user, to
    msg.set_content(f"Your Sowlaris password reset code is {code}. It expires in {RESET_MINUTES} minutes.\n"
                    "If you did not ask for this, you can ignore this email.")
    try:
        with smtplib.SMTP_SSL(host, int(os.getenv("SOWLARIS_SMTP_PORT", 465)), context=ssl.create_default_context()) as s:
            s.login(user, pw)
            s.send_message(msg)
        return True
    except Exception:
        return False


def request_reset(email):
    """Returns (emailed, demo_code). The UI shows the same message whether or not the email exists."""
    with _c() as c:
        u = c.execute("SELECT id FROM users WHERE email=?", (email.strip().lower(),)).fetchone()
        if not u:
            return False, None
        code = f"{secrets.randbelow(10**6):06d}"
        c.execute("DELETE FROM resets WHERE user_id=?", (u["id"],))
        c.execute("INSERT INTO resets VALUES(?,?,?)", (u["id"], _sha(code), time.time() + RESET_MINUTES * 60))
    sent = _send_email(email.strip().lower(), code)
    return sent, (None if sent else code)


def confirm_reset(email, code, new_pw):
    if len(new_pw) < 8:
        return "Use a password with at least 8 characters."
    with _c() as c:
        u = c.execute("SELECT id FROM users WHERE email=?", (email.strip().lower(),)).fetchone()
        r = u and c.execute("SELECT 1 FROM resets WHERE user_id=? AND code_hash=? AND expires>?",
                            (u["id"], _sha(code.strip()), time.time())).fetchone()
        if not r:
            return "That code is not valid or has expired."
        salt = secrets.token_hex(16)
        c.execute("UPDATE users SET pw_hash=?,salt=? WHERE id=?", (_hash(new_pw, salt), salt, u["id"]))
        c.execute("DELETE FROM resets WHERE user_id=?", (u["id"],))
        c.execute("DELETE FROM sessions WHERE user_id=?", (u["id"],))
    return ""


# ---- Saved field setup (so the farmer's inputs are remembered) ----
def save_setup(uid, data):
    with _c() as c:
        c.execute("INSERT OR REPLACE INTO setups VALUES(?,?)", (uid, json.dumps(data)))


def load_setup(uid):
    with _c() as c:
        r = c.execute("SELECT data FROM setups WHERE user_id=?", (uid,)).fetchone()
    return json.loads(r["data"]) if r else {}
