from flask import Blueprint, jsonify, request, session
from flask_jwt_extended import (
    jwt_required, create_access_token, create_refresh_token,
    get_jwt_identity, get_jwt
)
from extensions import db, bcrypt
from models.user import User
from models.activity import UserActivity

api_bp = Blueprint('api', __name__, url_prefix='/api')


def _log(user_id, action, details=''):
    entry = UserActivity(
        user_id=user_id, action=action, details=details,
        ip_address=request.remote_addr or '127.0.0.1'
    )
    db.session.add(entry)
    db.session.commit()


# ── Public: Health Check ───────────────────────────────────────────────────────
@api_bp.route('/health', methods=['GET'])
def health():
    return jsonify({'status': 'ok', 'message': 'SecureApp API is running.'})


# ── Public: Generate JWT Token (login via API) ─────────────────────────────────
@api_bp.route('/token', methods=['POST'])
def get_token():
    """Issue a JWT access + refresh token pair via JSON credentials."""
    data = request.get_json(silent=True) or {}
    identifier = data.get('username') or data.get('email') or ''
    password = data.get('password', '')

    user = (User.query.filter_by(username=identifier).first()
            or User.query.filter_by(email=identifier).first())

    if not user or not user.password_hash:
        return jsonify({'error': 'Invalid credentials.'}), 401

    if user.is_locked:
        return jsonify({'error': 'Account is locked. Contact an administrator.'}), 403

    if not bcrypt.check_password_hash(user.password_hash, password):
        user.failed_attempts += 1
        db.session.commit()
        return jsonify({'error': 'Invalid credentials.'}), 401

    user.failed_attempts = 0
    db.session.commit()
    _log(user.id, 'API_LOGIN', 'JWT token issued')

    access_token = create_access_token(
        identity=str(user.id),
        additional_claims={'role': user.role, 'username': user.username}
    )
    refresh_token = create_refresh_token(identity=str(user.id))
    return jsonify({
        'access_token': access_token,
        'refresh_token': refresh_token,
        'token_type': 'Bearer',
        'user': user.to_dict()
    })


# ── Refresh Token ──────────────────────────────────────────────────────────────
@api_bp.route('/token/refresh', methods=['POST'])
@jwt_required(refresh=True)
def refresh_token():
    identity = get_jwt_identity()
    user = User.query.get(int(identity))
    if not user:
        return jsonify({'error': 'User not found.'}), 404
    new_token = create_access_token(
        identity=str(user.id),
        additional_claims={'role': user.role, 'username': user.username}
    )
    return jsonify({'access_token': new_token})


# ── Protected: Get Current Profile ────────────────────────────────────────────
@api_bp.route('/profile', methods=['GET'])
@jwt_required()
def get_profile():
    """JWT-protected: returns current user profile."""
    identity = get_jwt_identity()
    user = User.query.get(int(identity))
    if not user:
        return jsonify({'error': 'User not found.'}), 404
    _log(user.id, 'API_PROFILE_VIEW', 'Profile fetched via API')
    return jsonify({'user': user.to_dict()})


# ── Protected: Update Profile ─────────────────────────────────────────────────
@api_bp.route('/update-profile', methods=['PUT'])
@jwt_required()
def update_profile():
    """JWT-protected: update name, bio."""
    identity = get_jwt_identity()
    user = User.query.get(int(identity))
    if not user:
        return jsonify({'error': 'User not found.'}), 404

    data = request.get_json(silent=True) or {}
    name = data.get('name', '').strip()
    bio = data.get('bio', '').strip()

    if name:
        if len(name) < 2:
            return jsonify({'error': 'Name must be at least 2 characters.'}), 400
        user.name = name
    if bio is not None:
        user.bio = bio[:500]

    db.session.commit()
    _log(user.id, 'API_PROFILE_UPDATED', f'Name updated to {user.name}')
    return jsonify({'message': 'Profile updated.', 'user': user.to_dict()})


# ── Admin Only: List All Users ─────────────────────────────────────────────────
@api_bp.route('/users', methods=['GET'])
@jwt_required()
def list_users():
    """JWT-protected, admin only: returns all users."""
    claims = get_jwt()
    if claims.get('role') != 'admin':
        return jsonify({'error': 'Administrator access required.'}), 403

    users = User.query.order_by(User.created_at.desc()).all()
    return jsonify({'users': [u.to_dict() for u in users], 'count': len(users)})
