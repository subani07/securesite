from datetime import datetime
from extensions import db


class MedicalRecord(db.Model):
    """AES-256-GCM encrypted medical record created by a doctor for a patient."""
    __tablename__ = 'medical_records'

    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patient_profiles.id', ondelete='CASCADE'),
                           nullable=False)
    doctor_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='SET NULL'),
                          nullable=True)
    diagnosis_enc = db.Column(db.Text, nullable=False)
    notes_enc = db.Column(db.Text, nullable=True)
    prescription_enc = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)
    updated_at = db.Column(db.DateTime, default=datetime.utcnow,
                           onupdate=datetime.utcnow)

    doctor = db.relationship('User', foreign_keys=[doctor_id])


class PatientUpload(db.Model):
    """Patient self-uploaded documents and files (AES-256-GCM encrypted metadata)."""
    __tablename__ = 'patient_uploads'

    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patient_profiles.id', ondelete='CASCADE'),
                           nullable=False)
    title_enc = db.Column(db.Text, nullable=False)
    description_enc = db.Column(db.Text, nullable=True)
    file_name_enc = db.Column(db.Text, nullable=True)
    file_path_enc = db.Column(db.Text, nullable=True)
    file_type = db.Column(db.String(50), nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)


class Appointment(db.Model):
    """Appointment request between patient and doctor."""
    __tablename__ = 'appointments'

    id = db.Column(db.Integer, primary_key=True)
    patient_id = db.Column(db.Integer, db.ForeignKey('patient_profiles.id', ondelete='CASCADE'),
                           nullable=False)
    doctor_id = db.Column(db.Integer, db.ForeignKey('users.id', ondelete='CASCADE'),
                          nullable=False)
    scheduled_date = db.Column(db.String(20), nullable=False)
    scheduled_time = db.Column(db.String(10), nullable=False)
    reason = db.Column(db.Text, nullable=True)
    status = db.Column(db.String(20), default='pending')  # pending/confirmed/completed/cancelled
    doctor_notes = db.Column(db.Text, nullable=True)
    created_at = db.Column(db.DateTime, default=datetime.utcnow, nullable=False)

    doctor = db.relationship('User', foreign_keys=[doctor_id])
