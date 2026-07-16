from datetime import datetime
from extensions import db


class User(db.Model):
    """Core User model with full security fields."""
    __tablename__ = 'users'

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(128), nullable=False)
    username = db.Column(db.String(64), unique=True, nullable=False, index=True)
    email = db.Column(db.String(256), unique=True, nullable=False, index=True)
    password_hash = db.Column(db.Text, nullable=True)  # nullable for OAuth-only users
    role = db.Column(db.String(20), default='user', nullable=False)  # 'user' or 'admin'

    # OAuth fields
    oauth_provider = db.Column(db.String(50), nullable=True)  # 'google'
    oauth_id = db.Column(db.String(256), nullable=True, unique=True)

    # Profile
    profile_picture = db.Column(db.String(256), nullable=True)
    bio = db.Column(db.Text, nullable=True)

    # Security fields
    is_active = db.Column(db.Boolean, default=True, nullable=False)
    is_locked = db.Column(db.Boolean, default=False, nullable=False)
    failed_attempts = db.Column(db.Integer, default=0, nullable=False)
    locked_until = db.Column(db.DateTime, nullable=True)

    # Password reset
    reset_token = db.Column(db.String(256), nullable=True)
    reset_token_expires = db.Column(db.DateTime, nullable=True)

    # Timestamps
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    last_login = db.Column(db.DateTime, nullable=True)

    # Relationships
    login_logs = db.relationship('LoginLog', backref='user', lazy='dynamic',
                                  foreign_keys='LoginLog.user_id')
    activities = db.relationship('UserActivity', backref='user', lazy='dynamic')

    def __repr__(self):
        return f'<User {self.username} [{self.role}]>'

    def to_dict(self):
        return {
            'id': self.id,
            'name': self.name,
            'username': self.username,
            'email': self.email,
            'role': self.role,
            'oauth_provider': self.oauth_provider,
            'profile_picture': self.profile_picture,
            'bio': self.bio,
            'is_active': self.is_active,
            'is_locked': self.is_locked,
            'created_at': self.created_at.isoformat() if self.created_at else None,
            'last_login': self.last_login.isoformat() if self.last_login else None,
        }
