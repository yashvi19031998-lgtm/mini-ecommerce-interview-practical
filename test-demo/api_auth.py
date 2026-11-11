"""
Authentication guard for the Flask API.

Every /api/* request must carry a valid Supabase access token:

    Authorization: Bearer <supabase access_token>

The token is verified against Supabase (GET /auth/v1/user) and the result is
cached briefly so we don't call Supabase on every request.

Environment variables:
    SUPABASE_URL / NEXT_PUBLIC_SUPABASE_URL          Supabase project URL
    SUPABASE_ANON_KEY / NEXT_PUBLIC_SUPABASE_ANON_KEY  public anon key
    ALLOWED_EMAILS     comma-separated list of emails allowed to use the API.
                       Strongly recommended: Supabase sign-up is open, so
                       without this list ANY registered user gets access.
    API_AUTH_DISABLED  "true" turns the check off. Only honoured when the
                       server is bound to localhost (used by run_hub.bat for
                       the legacy Flask UI, which has no login screen).
"""

import os
import time
import threading

import requests
from flask import request, jsonify


def _load_dotenv(path=os.path.join(os.path.dirname(os.path.abspath(__file__)), ".env")):
    if not os.path.exists(path):
        return
    with open(path, "r", encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if line and not line.startswith("#") and "=" in line:
                k, v = line.split("=", 1)
                os.environ.setdefault(k.strip(), v.strip().strip("'\""))


_load_dotenv()

# Public values (same ones shipped to the browser in frontend/lib/supabase.js)
_DEFAULT_SUPABASE_URL = "https://qmjwnfmcdepibytbirbl.supabase.co"
_DEFAULT_ANON_KEY = (
    "eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpc3MiOiJzdXBhYmFzZSIsInJlZiI6InFtanduZm1jZGVwaWJ5dGJpcmJsIiwi"
    "cm9sZSI6ImFub24iLCJpYXQiOjE3OTA4NDE5NTEsImV4cCI6MjEwNjQxNzk1MX0.DnM5kzWjwbXGuTlvbgO8Ert4HkqPJwC4sogZxIquI-Q"
)

SUPABASE_URL = (
    os.getenv("SUPABASE_URL") or os.getenv("NEXT_PUBLIC_SUPABASE_URL") or _DEFAULT_SUPABASE_URL
).rstrip("/ ")
SUPABASE_ANON_KEY = (
    os.getenv("SUPABASE_ANON_KEY") or os.getenv("NEXT_PUBLIC_SUPABASE_ANON_KEY") or _DEFAULT_ANON_KEY
).strip()

ALLOWED_EMAILS = {
    e.strip().lower() for e in os.getenv("ALLOWED_EMAILS", "").split(",") if e.strip()
}

LOOPBACK_HOSTS = {"127.0.0.1", "localhost", "::1"}
CACHE_TTL_SECONDS = 300

_token_cache = {}  # token -> (expires_at, email or None)
_cache_lock = threading.Lock()


def auth_disabled(bind_host: str) -> bool:
    flag = os.getenv("API_AUTH_DISABLED", "").lower() in ("1", "true", "yes")
    if flag and bind_host not in LOOPBACK_HOSTS:
        print("[auth] API_AUTH_DISABLED ignored: server is not bound to localhost.")
        return False
    return flag


def _verify_token(token: str):
    """Return the user's email if the token is valid (and allowed), else None."""
    now = time.time()
    with _cache_lock:
        cached = _token_cache.get(token)
        if cached and cached[0] > now:
            return cached[1]

    email = None
    try:
        resp = requests.get(
            f"{SUPABASE_URL}/auth/v1/user",
            headers={"apikey": SUPABASE_ANON_KEY, "Authorization": f"Bearer {token}"},
            timeout=8,
        )
        if resp.status_code == 200:
            email = (resp.json().get("email") or "").lower() or None
    except requests.RequestException as e:
        print(f"[auth] Could not reach Supabase to verify token: {e}")
        return None  # don't cache network failures

    if email and ALLOWED_EMAILS and email not in ALLOWED_EMAILS:
        email = None

    with _cache_lock:
        if len(_token_cache) > 500:
            _token_cache.clear()
        _token_cache[token] = (now + CACHE_TTL_SECONDS, email)
    return email


def init_auth(app, bind_host: str):
    """Register the /api/* guard on a Flask app."""
    if auth_disabled(bind_host):
        print("[auth] WARNING: API authentication is DISABLED (localhost only).")
        return

    if not ALLOWED_EMAILS:
        print("[auth] WARNING: ALLOWED_EMAILS is not set - any signed-up Supabase user can use the API.")

    @app.before_request
    def _require_auth():
        if not request.path.startswith("/api/") or request.method == "OPTIONS":
            return None

        # Local one-click login (X-Demo-User header). Only when the server itself is bound to localhost
        # AND the request comes from this machine - never when the API is exposed (FLASK_HOST=0.0.0.0),
        # otherwise anyone reaching the server could skip login. LOCAL_DEMO_LOGIN=false turns it off.
        if (request.headers.get("X-Demo-User")
                and os.getenv("LOCAL_DEMO_LOGIN", "true").lower() not in ("0", "false", "no")
                and bind_host in LOOPBACK_HOSTS
                and request.remote_addr in LOOPBACK_HOSTS):
            request.environ["auth.email"] = "admin@sangeetainfotech.com"
            return None

        header = request.headers.get("Authorization", "")
        token = header[7:].strip() if header.lower().startswith("bearer ") else ""
        if not token:
            return jsonify({"success": False, "error": "Authentication required. Please sign in."}), 401

        email = _verify_token(token)
        if not email:
            return jsonify({"success": False, "error": "Invalid or expired session, or account not allowed."}), 401

        request.environ["auth.email"] = email
        return None
