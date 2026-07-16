import os
import re
from datetime import datetime
from flask import (Blueprint, render_template, request, redirect,
                   url_for, flash, session, current_app)
from extensions import db, bcrypt, oauth, mail
from models.user import User
from models.login_log import LoginLog
from models.activity import UserActivity
from models.doctor_profile import DoctorProfile
from models.patient_profile import PatientProfile
from security.crypto import generate_reset_token, check_password_strength

auth_bp = Blueprint('auth', __name__)
EMAIL_RE = re.compile(r'^[^@\s]+@[^@\s]+\.[^@\s]+$')

ROLE_DASHBOARD = {
    'doctor':  'doctor.dashboard',
    'patient': 'patient.dashboard',
    'admin':   'admin.dashboard',
}


def _log_login(user_id, username, status, details=''):
    db.session.add(LoginLog(
        user_id=user_id, username_attempted=username,
        ip_address=request.remote_addr or '127.0.0.1',
        user_agent=request.headers.get('User-Agent', '')[:256],
        status=status, details=details))
    db.session.commit()


def _log_activity(user_id, action, details=''):
    db.session.add(UserActivity(
        user_id=user_id, action=action, details=details,
        ip_address=request.remote_addr or '127.0.0.1'))
    db.session.commit()


def _role_home(role):
    return redirect(url_for(ROLE_DASHBOARD.get(role, 'index')))


# ── Register ───────────────────────────────────────────────────────────────────
@auth_bp.route('/register', methods=['GET', 'POST'])
def register():
    if session.get('user_id'):
        return _role_home(session.get('role'))

    doctors = User.query.filter_by(role='doctor').all()

    if request.method == 'POST':
        name     = request.form.get('name', '').strip()
        username = request.form.get('username', '').strip()
        email    = request.form.get('email', '').strip().lower()
        password = request.form.get('password', '')
        confirm  = request.form.get('confirm_password', '')
        role     = request.form.get('role', 'patient')

        errors = []
        if not name or len(name) < 2:
            errors.append('Full name must be at least 2 characters.')
        if not username or len(username) < 3:
            errors.append('Username must be at least 3 characters.')
        if not re.match(r'^[a-zA-Z0-9_]+$', username):
            errors.append('Username: letters, numbers and underscores only.')
        if not EMAIL_RE.match(email):
            errors.append('Enter a valid email address.')
        if role not in ('patient', 'doctor'):
            errors.append('Select a valid role.')
        if password != confirm:
            errors.append('Passwords do not match.')
        strength = check_password_strength(password)
        if not strength['is_acceptable']:
            errors += strength['issues']
        if User.query.filter_by(username=username).first():
            errors.append('Username already taken.')
        if User.query.filter_by(email=email).first():
            errors.append('Email already registered.')

        if errors:
            for e in errors:
                flash(e, 'error')
            return render_template('register.html', name=name, username=username,
                                   email=email, role=role, doctors=doctors)

        pw_hash = bcrypt.generate_password_hash(password).decode('utf-8')
        user = User(name=name, username=username, email=email,
                    password_hash=pw_hash, role=role)
        db.session.add(user)
        db.session.flush()   # get user.id before commit

        if role == 'doctor':
            specialty = request.form.get('specialty', 'General Medicine').strip()
            department = request.form.get('department', '').strip()
            license_no = request.form.get('license_no', '').strip()
            dp = DoctorProfile(user_id=user.id, specialty=specialty or 'General Medicine',
                               department=department, license_no=license_no)
            db.session.add(dp)
        elif role == 'patient':
            dob         = request.form.get('dob', '').strip()
            gender      = request.form.get('gender', '').strip()
            blood_group = request.form.get('blood_group', '').strip()
            doctor_id   = request.form.get('doctor_id', None)
            if doctor_id == '' or doctor_id is None:
                doctor_id = None
            else:
                try:
                    doctor_id = int(doctor_id)
                except ValueError:
                    doctor_id = None
            pp = PatientProfile(user_id=user.id, dob=dob, gender=gender,
                                blood_group=blood_group, doctor_id=doctor_id)
            db.session.add(pp)

        db.session.commit()
        _log_activity(user.id, 'REGISTER', f'Registered as {role}')
        flash('Account created! Please log in.', 'success')
        return redirect(url_for('auth.login'))

    return render_template('register.html', doctors=doctors)


# ── Login ──────────────────────────────────────────────────────────────────────
@auth_bp.route('/login', methods=['GET', 'POST'])
def login():
    if session.get('user_id'):
        return _role_home(session.get('role'))

    if request.method == 'POST':
        identifier = request.form.get('identifier', '').strip()
        password   = request.form.get('password', '')
        max_att    = current_app.config.get('MAX_LOGIN_ATTEMPTS', 5)

        user = (User.query.filter_by(username=identifier).first()
                or User.query.filter_by(email=identifier).first())

        if not user:
            _log_login(None, identifier, 'FAILED', 'User not found')
            flash('Invalid credentials.', 'error')
            return render_template('login.html')

        if user.is_locked:
            if user.locked_until and datetime.utcnow() < user.locked_until:
                mins = int((user.locked_until - datetime.utcnow()).total_seconds() // 60)
                flash(f'Account locked. Try again in {mins} minutes.', 'error')
                _log_login(user.id, identifier, 'LOCKED')
                return render_template('login.html')
            else:
                user.is_locked = False
                user.failed_attempts = 0
                user.locked_until = None
                db.session.commit()

        if not user.password_hash or not bcrypt.check_password_hash(user.password_hash, password):
            user.failed_attempts += 1
            if user.failed_attempts >= max_att:
                from datetime import timedelta
                user.is_locked = True
                user.locked_until = datetime.utcnow() + timedelta(minutes=30)
                db.session.commit()
                _log_login(user.id, identifier, 'LOCKED', 'Too many attempts')
                flash('Too many failed attempts. Account locked for 30 minutes.', 'error')
            else:
                db.session.commit()
                left = max_att - user.failed_attempts
                _log_login(user.id, identifier, 'FAILED', f'{user.failed_attempts} attempts')
                flash(f'Invalid credentials. {left} attempt(s) remaining.', 'error')
            return render_template('login.html')

        # Success
        user.failed_attempts = 0
        user.is_locked = False
        user.last_login = datetime.utcnow()
        db.session.commit()

        session.clear()
        session['user_id']  = user.id
        session['username'] = user.username
        session['role']     = user.role
        session.permanent   = True

        _log_login(user.id, identifier, 'SUCCESS')
        _log_activity(user.id, 'LOGIN', f'Role: {user.role}')
        flash(f'Welcome back, {user.name}!', 'success')
        return _role_home(user.role)

    return render_template('login.html')


# ── OAuth Google ───────────────────────────────────────────────────────────────
@auth_bp.route('/oauth/login')
def oauth_login():
    if not current_app.config.get('GOOGLE_CLIENT_ID'):
        flash('Google OAuth not configured. Use standard login.', 'warning')
        return redirect(url_for('auth.login'))
    return oauth.google.authorize_redirect(url_for('auth.oauth_callback', _external=True))


@auth_bp.route('/oauth/callback')
def oauth_callback():
    if not current_app.config.get('GOOGLE_CLIENT_ID'):
        return redirect(url_for('auth.login'))
    try:
        token    = oauth.google.authorize_access_token()
        userinfo = token.get('userinfo') or oauth.google.userinfo()
    except Exception:
        flash('OAuth failed. Please try again.', 'error')
        return redirect(url_for('auth.login'))

    google_id = userinfo.get('sub')
    email     = userinfo.get('email', '').lower()
    name      = userinfo.get('name', 'Google User')
    picture   = userinfo.get('picture', '')

    user = User.query.filter_by(oauth_id=google_id).first()
    if not user:
        user = User.query.filter_by(email=email).first()
        if user:
            user.oauth_provider = 'google'
            user.oauth_id = google_id
        else:
            base = re.sub(r'[^a-zA-Z0-9_]', '', email.split('@')[0])[:20] or 'user'
            uname, c = base, 1
            while User.query.filter_by(username=uname).first():
                uname = f'{base}{c}'; c += 1
            user = User(name=name, username=uname, email=email,
                        oauth_provider='google', oauth_id=google_id,
                        profile_picture=picture, role='patient')
            db.session.add(user)
            db.session.flush()
            db.session.add(PatientProfile(user_id=user.id))

    user.last_login = datetime.utcnow()
    db.session.commit()
    session.clear()
    session['user_id']  = user.id
    session['username'] = user.username
    session['role']     = user.role
    _log_login(user.id, user.username, 'OAUTH', 'Google')
    flash(f'Welcome, {user.name}!', 'success')
    return _role_home(user.role)


# ── Logout ─────────────────────────────────────────────────────────────────────
@auth_bp.route('/logout', methods=['GET', 'POST'])
def logout():
    uid = session.get('user_id')
    if uid:
        _log_activity(uid, 'LOGOUT')
    session.clear()
    flash('Logged out securely.', 'info')
    return redirect(url_for('auth.login'))


# ── Forgot / Reset Password ────────────────────────────────────────────────────
@auth_bp.route('/forgot-password', methods=['GET', 'POST'])
def forgot_password():
    if request.method == 'POST':
        email = request.form.get('email', '').strip().lower()
        user  = User.query.filter_by(email=email).first()
        if user and user.password_hash:
            token, expires = generate_reset_token()
            user.reset_token = token
            user.reset_token_expires = expires
            db.session.commit()
            reset_url = url_for('auth.reset_password', token=token, _external=True)
            _send_reset_email(user, reset_url)
        flash('If that email exists, a reset link has been sent.', 'info')
        return redirect(url_for('auth.login'))
    return render_template('forgot_password.html')


@auth_bp.route('/reset-password/<token>', methods=['GET', 'POST'])
def reset_password(token):
    user = User.query.filter_by(reset_token=token).first()
    if not user or not user.reset_token_expires or datetime.utcnow() > user.reset_token_expires:
        flash('Invalid or expired reset link.', 'error')
        return redirect(url_for('auth.forgot_password'))
    if request.method == 'POST':
        pw = request.form.get('password', '')
        cp = request.form.get('confirm_password', '')
        if pw != cp:
            flash('Passwords do not match.', 'error')
        else:
            s = check_password_strength(pw)
            if not s['is_acceptable']:
                for i in s['issues']:
                    flash(i, 'error')
            else:
                user.password_hash = bcrypt.generate_password_hash(pw).decode('utf-8')
                user.reset_token = user.reset_token_expires = None
                user.failed_attempts = 0
                user.is_locked = False
                db.session.commit()
                flash('Password reset. Please log in.', 'success')
                return redirect(url_for('auth.login'))
    return render_template('reset_password.html', token=token)


def _send_reset_email(user, reset_url):
    try:
        from flask_mail import Message
        mail.send(Message('HealthPlus – Password Reset', recipients=[user.email],
                          html=f'<p>Hi {user.name},</p><p><a href="{reset_url}">{reset_url}</a></p>'))
    except Exception:
        print(f'\n[DEV] Reset URL for {user.email}:\n{reset_url}\n')
