from datetime import datetime
from extensions import db


class PatientProfile(db.Model):
    """Extended profile for patient-role users."""
    __tablename__ = 'patient_profiles'

    id = db.Column(db.Integer, primary_key=True)
    user_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'),
                        nullable=False, unique=True)
    doctor_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'),
                          nullable=True)
    dob = db.Column(db.String(20), nullable=True)
    gender = db.Column(db.String(20), nullable=True)
    blood_group = db.Column(db.String(10), nullable=True)
    allergies = db.Column(db.Text, nullable=True)
    emergency_contact = db.Column(db.String(128), nullable=True)
    emergency_phone = db.Column(db.String(30), nullable=True)

    user = db.relationship('User', foreign_keys=[user_id],
                           backref=db.backref('patient_profile', uselist=False))
    doctor = db.relationship('User', foreign_keys=[doctor_id],
                             backref=db.backref('assigned_patients', lazy='dynamic'))

    # Medical records linked to this patient
    medical_records = db.relationship('MedicalRecord', backref='patient',
                                      lazy='dynamic', cascade='all, delete-orphan')
    uploads = db.relationship('PatientUpload', backref='patient',
                              lazy='dynamic', cascade='all, delete-orphan')
    appointments = db.relationship('Appointment', backref='patient',
                                   lazy='dynamic', cascade='all, delete-orphan')

    def to_dict(self):
        return {
            'id': self.id,
            'user_id': self.user_id,
            'doctor_id': self.doctor_id,
            'dob': self.dob,
            'gender': self.gender,
            'blood_group': self.blood_group,
            'allergies': self.allergies,
        }
