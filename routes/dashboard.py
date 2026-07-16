import os
from functools import wraps
from flask import (Blueprint, render_template, request, redirect,
                   url_for, flash, session, current_app)
from extensions import db, bcrypt
from models.user import User
from models.activity import UserActivity
from security.crypto import check_password_strength
from werkzeug.utils import secure_filename

dashboard_bp = Blueprint('dashboard', __name__)


# ── Auth guard ─────────────────────────────────────────────────────────────────
def login_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('user_id'):
            flash('Please log in to access this page.', 'warning')
            return redirect(url_for('auth.login', next=request.path))
        return f(*args, **kwargs)
    return decorated


def _current_user():
    return User.query.get(session.get('user_id'))


def _log(user_id, action, details=''):
    entry = UserActivity(
        user_id=user_id, action=action, details=details,
        ip_address=request.remote_addr or '127.0.0.1'
    )
    db.session.add(entry)
    db.session.commit()


def _allowed_file(filename):
    allowed = current_app.config.get('ALLOWED_EXTENSIONS', {'png', 'jpg', 'jpeg', 'gif'})
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in allowed


# ── Dashboard Home — redirects to role-specific dashboard ─────────────────────
@dashboard_bp.route('/dashboard')
@login_required
def home():
    role = session.get('role', '')
    if role == 'doctor':
        return redirect(url_for('doctor.dashboard'))
    elif role == 'patient':
        return redirect(url_for('patient.dashboard'))
    elif role == 'admin':
        return redirect(url_for('admin.dashboard'))
    # Fallback: admin-style
    user = _current_user()
    if not user:
        session.clear()
        return redirect(url_for('auth.login'))
    recent_activity = UserActivity.query.filter_by(user_id=user.id)\
        .order_by(UserActivity.timestamp.desc()).limit(5).all()
    return render_template('dashboard.html', user=user, activity=recent_activity)


# ── Profile ────────────────────────────────────────────────────────────────────
@dashboard_bp.route('/profile', methods=['GET', 'POST'])
@login_required
def profile():
    user = _current_user()

    if request.method == 'POST':
        name = request.form.get('name', '').strip()
        bio = request.form.get('bio', '').strip()
        email = request.form.get('email', '').strip().lower()

        errors = []
        if not name or len(name) < 2:
            errors.append('Full name must be at least 2 characters.')
        if email != user.email:
            if User.query.filter(User.email == email, User.id != user.id).first():
                errors.append('Email already in use by another account.')

        # Profile picture upload
        picture_file = request.files.get('profile_picture')
        if picture_file and picture_file.filename:
            if not _allowed_file(picture_file.filename):
                errors.append('Invalid file type. Only PNG, JPG, GIF allowed.')
            elif picture_file.content_length and picture_file.content_length > 2 * 1024 * 1024:
                errors.append('Profile picture must be under 2MB.')
            else:
                filename = f"profile_{user.id}_{secure_filename(picture_file.filename)}"
                upload_folder = current_app.config['UPLOAD_FOLDER']
                os.makedirs(upload_folder, exist_ok=True)
                picture_file.save(os.path.join(upload_folder, filename))
                user.profile_picture = filename

        if errors:
            for e in errors:
                flash(e, 'error')
        else:
            user.name = name
            user.email = email
            user.bio = bio[:500] if bio else None
            db.session.commit()
            _log(user.id, 'PROFILE_UPDATED', f'Name: {name}, Email: {email}')
            flash('Profile updated successfully.', 'success')
            return redirect(url_for('dashboard.profile'))

    return render_template('profile.html', user=user)


# ── Security Settings ──────────────────────────────────────────────────────────
@dashboard_bp.route('/security', methods=['GET', 'POST'])
@login_required
def security_settings():
    from flask_jwt_extended import create_access_token
    user = _current_user()

    if request.method == 'POST':
        action = request.form.get('action')

        if action == 'change_password':
            current_pw = request.form.get('current_password', '')
            new_pw = request.form.get('new_password', '')
            confirm_pw = request.form.get('confirm_password', '')

            if not user.password_hash:
                flash('OAuth accounts cannot change password this way.', 'error')
            elif not bcrypt.check_password_hash(user.password_hash, current_pw):
                flash('Current password is incorrect.', 'error')
            elif new_pw != confirm_pw:
                flash('New passwords do not match.', 'error')
            else:
                strength = check_password_strength(new_pw)
                if not strength['is_acceptable']:
                    for issue in strength['issues']:
                        flash(issue, 'error')
                else:
                    user.password_hash = bcrypt.generate_password_hash(new_pw).decode('utf-8')
                    db.session.commit()
                    _log(user.id, 'PASSWORD_CHANGED', 'Password changed from security settings')
                    flash('Password changed successfully.', 'success')

        return redirect(url_for('dashboard.security_settings'))

    # Generate a demo JWT for the security page
    demo_jwt = create_access_token(identity=str(user.id),
                                   additional_claims={'role': user.role, 'username': user.username})
    return render_template('security.html', user=user, demo_jwt=demo_jwt)
