from datetime import datetime
from extensions import db


class DoctorProfile(db.Model):
    """Extended profile for doctor-role users."""
    __tablename__ = 'doctor_profiles'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'),
                        nullable=False, unique=True)
    specialty = db.Column(db.String(128), nullable=False, default='General Medicine')
    department = db.Column(db.String(128), nullable=True)
    license_no = db.Column(db.String(64), nullable=True)
    years_experience = db.Column(db.Integer, default=0)
    bio = db.Column(db.Text, nullable=True)
    available = db.Column(db.Boolean, default=True)

    user = db.relationship('User', backref=db.backref('doctor_profile', uselist=False))

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'specialty': self.specialty,
            'department': self.department,
            'license_no': self.license_no,
            'years_experience': self.years_experience,
            'bio': self.bio,
            'available': self.available,
        }
