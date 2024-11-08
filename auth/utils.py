import functools
from flask import session, redirect, url_for, request, current_app
from datetime import datetime, timedelta
from database.models import User, LoginAttempt, db
import re

def login_required(view):
    """Decorator to require login for views."""
    @functools.wraps(view)
    def wrapped_view(**kwargs):
        print(f"Checking login requirement. Session: {session}")  # Debug log
        if 'user_id' not in session:
            print("No user_id in session, redirecting to login")  # Debug log
            return redirect(url_for('auth.login', next=request.url))
        print(f"User {session['user_id']} is logged in")  # Debug log
        return view(**kwargs)
    return wrapped_view

def admin_required(view):
    """Decorator to require admin role for views."""
    @functools.wraps(view)
    def wrapped_view(**kwargs):
        if 'user_id' not in session:
            return redirect(url_for('auth.login', next=request.url))
        
        user = User.query.get(session['user_id'])
        if not user or not user.is_admin:
            return redirect(url_for('index'))
        
        return view(**kwargs)
    return wrapped_view

def is_safe_url(target):
    """Ensure URL is safe for redirection."""
    from urllib.parse import urlparse, urljoin
    from flask import request
    ref_url = urlparse(request.host_url)
    test_url = urlparse(urljoin(request.host_url, target))
    return test_url.scheme in ('http', 'https') and ref_url.netloc == test_url.netloc

def validate_password(password):
    """
    Validate password strength.
    Returns (bool, str) tuple - (is_valid, error_message)
    """
    if len(password) < 8:
        return False, "Password must be at least 8 characters long"
    
    if not re.search(r"[A-Z]", password):
        return False, "Password must contain at least one uppercase letter"
    
    if not re.search(r"[a-z]", password):
        return False, "Password must contain at least one lowercase letter"
    
    if not re.search(r"\d", password):
        return False, "Password must contain at least one number"
    
    if not re.search(r"[!@#$%^&*(),.?\":{}|<>]", password):
        return False, "Password must contain at least one special character"
    
    return True, ""

def log_login_attempt(username, success, ip_address):
    """Log login attempts for security monitoring."""
    attempt = LoginAttempt(
        username=username,
        success=success,
        ip_address=ip_address
    )
    db.session.add(attempt)
    db.session.commit()

def check_login_attempts(username, ip_address, max_attempts=5, lockout_time=300):
    """Check if user/IP is temporarily locked out due to failed attempts."""
    cutoff_time = datetime.utcnow() - timedelta(seconds=lockout_time)
    recent_attempts = LoginAttempt.query.filter(
        LoginAttempt.username == username,
        LoginAttempt.ip_address == ip_address,
        LoginAttempt.success == False,
        LoginAttempt.timestamp > cutoff_time
    ).count()
    
    return recent_attempts >= max_attempts

def send_reset_email(email, reset_url):
    """
    Simulate sending a password reset email.
    In production, replace this with actual email sending logic.
    """
    if current_app.debug:
        print(f"[DEBUG] Password reset email would be sent to: {email}")
        print(f"[DEBUG] Reset URL: {reset_url}")
    # In production, implement actual email sending here
    return True