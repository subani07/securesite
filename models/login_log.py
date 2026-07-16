from datetime import datetime
from extensions import db


class LoginLog(db.Model):
    """Tracks all login attempts — successful and failed — for security monitoring."""
    __tablename__ = 'login_logs'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'), nullable=True)
    username_attempted = db.Column(db.String(64), nullable=False)
    ip_address = db.Column(db.String(64), nullable=False)
    user_agent = db.Column(db.String(256), nullable=True)
    status = db.Column(db.String(20), nullable=False)  # 'SUCCESS', 'FAILED', 'LOCKED', 'OAUTH'
    login_time = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    details = db.Column(db.Text, nullable=True)

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'username_attempted': self.username_attempted,
            'ip_address': self.ip_address,
            'user_agent': self.user_agent,
            'status': self.status,
            'login_time': self.login_time.isoformat() if self.login_time else None,
            'details': self.details,
        }
