from flask import Blueprint, render_template, request, redirect, url_for, flash, session, current_app, jsonify
from database.models import User, db, PasswordResetRequest
from .utils import (
    login_required, admin_required, is_safe_url, validate_password,
    log_login_attempt, check_login_attempts, send_reset_email
)
from config.config_utils import config
from datetime import datetime, timedelta
import secrets

auth_bp = Blueprint('auth', __name__, url_prefix='/auth')


@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if 'user_id' in session:
        return redirect(url_for('index'))

    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']
        ip_address = request.remote_addr

        user = User.query.filter_by(username=username).first()

        if user and user.check_password(password):
            if user.status == 'pending':
                flash('Your account is pending approval.', 'error')
                log_login_attempt(username, False, ip_address)
                return render_template('auth/login.html')

            if user.status == 'rejected':
                flash('Your account has been rejected.', 'error')
                log_login_attempt(username, False, ip_address)
                return render_template('auth/login.html')

            if not user.is_active:
                flash('This account has been deactivated.', 'error')
                log_login_attempt(username, False, ip_address)
                return render_template('auth/login.html')

            session.clear()
            session.permanent = True
            session['user_id'] = user.id
            session['username'] = user.username  # Add username to session
            session['is_admin'] = user.is_admin
            session['_fresh'] = True
            session.modified = True

            user.last_login = db.func.now()
            db.session.commit()

            log_login_attempt(username, True, ip_address)

            next_page = request.args.get('next')
            if not next_page or not is_safe_url(next_page):
                next_page = url_for('index')

            return redirect(next_page)
        else:
            flash('Invalid username or password', 'error')
            log_login_attempt(username, False, ip_address)

    return render_template('auth/login.html')


@auth_bp.route('/logout')
def logout():
    session.clear()
    return redirect(url_for('auth.login'))


@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        confirm_password = request.form['confirm_password']

        if password != confirm_password:
            flash('Passwords do not match', 'error')
            return render_template('auth/register.html')

        is_valid, error_message = validate_password(password)
        if not is_valid:
            flash(error_message, 'error')
            return render_template('auth/register.html')

        if User.query.filter_by(username=username).first():
            flash('Username already exists', 'error')
            return render_template('auth/register.html')

        if User.query.filter_by(email=email).first():
            flash('Email already registered', 'error')
            return render_template('auth/register.html')

        user = User(username=username, email=email, password=password)
        db.session.add(user)

        try:
            db.session.commit()
            flash('Registration successful! Please wait for admin approval.', 'success')
            return redirect(url_for('auth.login'))
        except Exception as e:
            db.session.rollback()
            flash('An error occurred during registration', 'error')
            return render_template('auth/register.html')

    return render_template('auth/register.html')


@auth_bp.route('/change-password', methods=['POST'])
@login_required
def change_password():
    try:
        current_password = request.form['current_password']
        new_password = request.form['new_password']
        confirm_password = request.form['confirm_password']

        user = User.query.get(session['user_id'])
        if not user:
            flash('User not found', 'error')
            return redirect(url_for('index'))

        if not user.check_password(current_password):
            flash('Current password is incorrect', 'error')
            return redirect(url_for('index'))

        if new_password != confirm_password:
            flash('New passwords do not match', 'error')
            return redirect(url_for('index'))

        is_valid, error_message = validate_password(new_password)
        if not is_valid:
            flash(error_message, 'error')
            return redirect(url_for('index'))

        user.set_password(new_password)
        db.session.commit()
        flash('Password changed successfully', 'success')
        return redirect(url_for('index'))

    except Exception as e:
        flash('An error occurred while changing the password', 'error')
        return redirect(url_for('index'))


@auth_bp.route('/reset-password', methods=['GET', 'POST'])
def reset_password_request():
    if request.method == 'POST':
        email = request.form['email']
        user = User.query.filter_by(email=email).first()

        if user:
            if user.status != 'approved':
                flash('This account is not approved. Please contact an administrator.', 'error')
                return redirect(url_for('auth.reset_password_request'))

            # Generate a temporary token
            token = secrets.token_urlsafe(32)

            reset_request = PasswordResetRequest(
                user_id=user.id,
                token=token,
                status='pending'
            )

            db.session.add(reset_request)
            db.session.commit()

            # In a production environment, you would send this via email
            # For development, we'll just display it
            if current_app.debug:
                flash(f'Debug: Reset link would be: {url_for("auth.reset_password", token=token, _external=True)}',
                      'info')

            flash('Password reset request submitted. An administrator will review your request.', 'success')
        else:
            # Don't reveal if email exists
            flash('If an account exists with this email, a reset link will be sent to you.', 'info')

        return redirect(url_for('auth.login'))

    return render_template('auth/reset_password_request.html')


@auth_bp.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    reset_request = PasswordResetRequest.query.filter_by(token=token).first()

    if not reset_request:
        flash('Invalid reset token', 'error')
        return redirect(url_for('auth.login'))

    # Check if request is approved
    if reset_request.status != 'approved':
        if reset_request.status == 'pending':
            flash('Your password reset request is still pending admin approval.', 'info')
        elif reset_request.status == 'rejected':
            flash('Your password reset request was rejected.', 'error')
        elif reset_request.status == 'completed':
            flash('This password reset link has already been used.', 'error')
        return redirect(url_for('auth.login'))

    # Check if token is expired (24 hours after approval)
    if not reset_request.is_valid():
        flash('This password reset link has expired.', 'error')
        return redirect(url_for('auth.login'))

    user = User.query.get(reset_request.user_id)
    if not user:
        flash('User not found', 'error')
        return redirect(url_for('auth.login'))

    if request.method == 'POST':
        password = request.form['password']
        confirm_password = request.form['confirm_password']

        if password != confirm_password:
            flash('Passwords do not match', 'error')
            return render_template('auth/reset_password.html')

        is_valid, error_message = validate_password(password)
        if not is_valid:
            flash(error_message, 'error')
            return render_template('auth/reset_password.html')

        # Update password and mark request as completed
        user.set_password(password)
        reset_request.status = 'completed'
        db.session.commit()

        flash('Your password has been reset successfully. Please log in with your new password.', 'success')
        return redirect(url_for('auth.login'))

    return render_template('auth/reset_password.html', token=token)


@auth_bp.route('/debug-users')
def debug_users():
    users = User.query.all()
    output = []
    for user in users:
        output.append({
            'username': user.username,
            'email': user.email,
            'is_admin': user.is_admin,
            'is_active': user.is_active,
            'password_hash_exists': bool(user.password_hash)
        })
    return jsonify(output)