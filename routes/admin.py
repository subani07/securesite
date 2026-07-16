from functools import wraps
from flask import (Blueprint, render_template, request, redirect,
                   url_for, flash, session, jsonify)
from extensions import db, bcrypt
from models.user import User
from models.login_log import LoginLog
from models.activity import UserActivity

admin_bp = Blueprint('admin', __name__, url_prefix='/admin')


# ── Admin guard ────────────────────────────────────────────────────────────────
def admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('user_id'):
            flash('Authentication required.', 'warning')
            return redirect(url_for('auth.login'))
        if session.get('role') != 'admin':
            flash('Administrator access required.', 'error')
            return redirect(url_for('dashboard.home'))
        return f(*args, **kwargs)
    return decorated


def _log(user_id, action, details=''):
    entry = UserActivity(
        user_id=user_id, action=action, details=details,
        ip_address=request.remote_addr or '127.0.0.1'
    )
    db.session.add(entry)
    db.session.commit()


# ── Admin Dashboard ────────────────────────────────────────────────────────────
@admin_bp.route('/')
@admin_required
def dashboard():
    total_users = User.query.count()
    admin_count = User.query.filter_by(role='admin').count()
    locked_count = User.query.filter_by(is_locked=True).count()
    failed_logins = LoginLog.query.filter_by(status='FAILED').count()
    recent_logs = LoginLog.query.order_by(LoginLog.login_time.desc()).limit(10).all()
    recent_activity = UserActivity.query.order_by(UserActivity.timestamp.desc()).limit(10).all()
    return render_template('admin/dashboard.html',
                           total_users=total_users,
                           admin_count=admin_count,
                           locked_count=locked_count,
                           failed_logins=failed_logins,
                           recent_logs=recent_logs,
                           recent_activity=recent_activity)


# ── User Management ────────────────────────────────────────────────────────────
@admin_bp.route('/users')
@admin_required
def users():
    search = request.args.get('q', '').strip()
    query = User.query
    if search:
        query = query.filter(
            (User.username.ilike(f'%{search}%')) |
            (User.email.ilike(f'%{search}%')) |
            (User.name.ilike(f'%{search}%'))
        )
    all_users = query.order_by(User.created_at.desc()).all()
    return render_template('admin/users.html', users=all_users, search=search)


@admin_bp.route('/users/<int:user_id>/delete', methods=['POST'])
@admin_required
def delete_user(user_id):
    current_admin_id = session.get('user_id')
    if user_id == current_admin_id:
        flash('You cannot delete your own account.', 'error')
        return redirect(url_for('admin.users'))

    user = User.query.get_or_404(user_id)
    username = user.username
    db.session.delete(user)
    db.session.commit()
    _log(current_admin_id, 'USER_DELETED', f'Admin deleted user: {username} (ID {user_id})')
    flash(f'User "{username}" deleted successfully.', 'success')
    return redirect(url_for('admin.users'))


@admin_bp.route('/users/<int:user_id>/role', methods=['POST'])
@admin_required
def change_role(user_id):
    current_admin_id = session.get('user_id')
    if user_id == current_admin_id:
        flash('You cannot change your own role.', 'error')
        return redirect(url_for('admin.users'))

    user = User.query.get_or_404(user_id)
    new_role = request.form.get('role')
    if new_role not in ('user', 'admin'):
        flash('Invalid role.', 'error')
        return redirect(url_for('admin.users'))

    old_role = user.role
    user.role = new_role
    db.session.commit()
    _log(current_admin_id, 'ROLE_CHANGED',
         f'Changed {user.username} role: {old_role} → {new_role}')
    flash(f'Role for "{user.username}" changed to {new_role}.', 'success')
    return redirect(url_for('admin.users'))


@admin_bp.route('/users/<int:user_id>/unlock', methods=['POST'])
@admin_required
def unlock_user(user_id):
    user = User.query.get_or_404(user_id)
    user.is_locked = False
    user.failed_attempts = 0
    user.locked_until = None
    db.session.commit()
    _log(session.get('user_id'), 'USER_UNLOCKED', f'Admin unlocked {user.username}')
    flash(f'Account "{user.username}" unlocked.', 'success')
    return redirect(url_for('admin.users'))


# ── Security Logs ──────────────────────────────────────────────────────────────
@admin_bp.route('/logs')
@admin_required
def logs():
    page = request.args.get('page', 1, type=int)
    status_filter = request.args.get('status', '')
    log_query = LoginLog.query
    if status_filter:
        log_query = log_query.filter_by(status=status_filter)
    login_logs = log_query.order_by(LoginLog.login_time.desc()).paginate(
        page=page, per_page=25, error_out=False)
    activity_logs = UserActivity.query.order_by(
        UserActivity.timestamp.desc()).limit(50).all()
    return render_template('admin/logs.html',
                           login_logs=login_logs,
                           activity_logs=activity_logs,
                           status_filter=status_filter)
