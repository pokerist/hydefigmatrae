"""
Authentication utilities for dashboard
"""
import functools
from flask import session, redirect, url_for, request
from config import Config


def login_required(f):
    """Decorator to require login for dashboard routes"""
    @functools.wraps(f)
    def decorated_function(*args, **kwargs):
        if not session.get('logged_in'):
            return redirect(url_for('login', next=request.url))
        return f(*args, **kwargs)
    return decorated_function


def check_credentials(username: str, password: str) -> bool:
    """
    Validate username and password
    
    Args:
        username: Provided username
        password: Provided password
    
    Returns:
        True if credentials are valid, False otherwise
    """
    return (
        username == Config.DASHBOARD_USERNAME and
        password == Config.DASHBOARD_PASSWORD
    )