"""Login. Pages use a session cookie. The API also accepts the X-API-Key header (for Thunder Client / Postman)."""
from flask import current_app, jsonify, redirect, request, session, url_for
from werkzeug.security import check_password_hash

from .db import get_db


def check_login(email, password):
    row = get_db().execute("SELECT * FROM users WHERE email=?", (str(email).strip(),)).fetchone()
    return bool(row and check_password_hash(row["password_hash"], str(password)))


def is_logged_in():
    return bool(session.get("user")) or request.headers.get("X-API-Key") == current_app.config["API_KEY"]


def api_guard():
    """before_request for the API: every route needs a login except /api/login and /api/logout."""
    if request.endpoint in ("api.login", "api.logout") or is_logged_in():
        return None
    return jsonify(error="Unauthorized. Log in first (POST /api/login) or send the X-API-Key header."), 401


def page_guard():
    """before_request for the pages: send visitors to the login page."""
    if request.endpoint in ("pages.login",) or session.get("user"):
        return None
    return redirect(url_for("pages.login"))
