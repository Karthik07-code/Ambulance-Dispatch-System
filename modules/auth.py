"""
Role-Based Authentication Module
================================
Supports Admin and Driver authentication, password hashing, and session guards.
"""

from functools import wraps
from typing import Optional, Dict, Any, Tuple
from flask import session, redirect, url_for, flash, request
from werkzeug.security import check_password_hash, generate_password_hash
from database import get_db_connection


def authenticate(username: str, password: str) -> Tuple[bool, Optional[Dict[str, Any]], str]:
    """
    Validates username and password against the accounts table.
    Returns (success, account_dict, message).
    """
    username = username.strip()
    if not username or not password:
        return False, None, "Username and password are required."

    conn = get_db_connection()
    cursor = conn.cursor()
    cursor.execute("""
        SELECT a.account_id, a.username, a.password_hash, a.role, a.is_active,
               d.driver_id, d.full_name, d.phone, d.ambulance_id
        FROM accounts a
        LEFT JOIN drivers d ON a.account_id = d.account_id
        WHERE a.username = ?;
    """, (username,))
    row = cursor.fetchone()
    conn.close()

    if not row:
        return False, None, "Invalid username or password."

    account = dict(row)

    if not account["is_active"]:
        return False, None, "This account has been deactivated. Please contact an administrator."

    if not check_password_hash(account["password_hash"], password):
        return False, None, "Invalid username or password."

    return True, account, "Authentication successful."


def login_user(account: Dict[str, Any]) -> None:
    """Store authenticated user details in the session."""
    session.clear()
    session["user_id"] = account["account_id"]
    session["username"] = account["username"]
    session["role"] = account["role"]
    session["driver_id"] = account.get("driver_id")
    session["full_name"] = account.get("full_name") or account["username"]
    session.permanent = True


def logout_user() -> None:
    """Clear session on logout."""
    session.clear()


def get_current_user() -> Optional[Dict[str, Any]]:
    """Return dict of current authenticated user from session, or None."""
    if "user_id" in session:
        return {
            "account_id": session.get("user_id"),
            "username": session.get("username"),
            "role": session.get("role"),
            "driver_id": session.get("driver_id"),
            "full_name": session.get("full_name")
        }
    return None


def login_required(f):
    """Decorator ensuring a user is logged in."""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if "user_id" not in session:
            flash("Please sign in to access this page.", "warning")
            return redirect(url_for("login", next=request.url))
        return f(*args, **kwargs)
    return decorated_function


def role_required(*allowed_roles):
    """Decorator enforcing role-based access control (e.g. 'Admin' or 'Driver')."""
    def decorator(f):
        @wraps(f)
        def decorated_function(*args, **kwargs):
            if "user_id" not in session:
                flash("Please sign in to access this page.", "warning")
                return redirect(url_for("login", next=request.url))
            user_role = session.get("role")
            if user_role not in allowed_roles:
                flash(f"Unauthorized. This area requires {' or '.join(allowed_roles)} privileges.", "danger")
                if user_role == "Driver":
                    return redirect(url_for("driver_dashboard"))
                return redirect(url_for("dashboard"))
            return f(*args, **kwargs)
        return decorated_function
    return decorator

