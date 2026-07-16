"""
HealthPlus seed script — creates demo doctors, patients and medical records.
Usage:  python database/seed.py
"""
import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from app import app
from extensions import db, bcrypt
from models.user import User
from models.activity import UserActivity
from models.login_log import LoginLog
from models.doctor_profile import DoctorProfile
from models.patient_profile import PatientProfile
from models.medical import MedicalRecord, PatientUpload, Appointment
from security.crypto import encrypt_data


def seed():
    with app.app_context():
        db.create_all()

        # Clear all existing data
        Appointment.query.delete()
        PatientUpload.query.delete()
        MedicalRecord.query.delete()
        PatientProfile.query.delete()
        DoctorProfile.query.delete()
        UserActivity.query.delete()
        LoginLog.query.delete()
        User.query.delete()
        db.session.commit()

        def make_user(name, username, email, password, role):
            u = User(name=name, username=username, email=email,
                     password_hash=bcrypt.generate_password_hash(password).decode(),
                     role=role)
            db.session.add(u)
            db.session.flush()
            return u

        # ── Admin ──────────────────────────────────────────────────────────────
        admin = make_user('Admin User', 'admin', 'admin@healthplus.com', 'Admin@1234', 'admin')

        # ── Doctors ────────────────────────────────────────────────────────────
        doc1 = make_user('Dr. Sarah Johnson', 'dr_johnson', 'sarah@healthplus.com', 'Doctor@123', 'doctor')
        db.session.add(DoctorProfile(user_id=doc1.id, specialty='Cardiology',
                                     department='Heart & Vascular', license_no='MCI-2345',
                                     years_experience=12,
                                     bio='Specialist in cardiovascular diseases with 12 years of experience.'))

        doc2 = make_user('Dr. Rahul Mehta', 'dr_mehta', 'rahul@healthplus.com', 'Doctor@456', 'doctor')
        db.session.add(DoctorProfile(user_id=doc2.id, specialty='Neurology',
                                     department='Brain & Spine', license_no='MCI-6789',
                                     years_experience=8,
                                     bio='Neurologist specialising in migraine and epilepsy management.'))

        db.session.flush()

        # ── Patients ───────────────────────────────────────────────────────────
        pat1 = make_user('Alice Smith', 'alice', 'alice@example.com', 'Patient@123', 'patient')
        pp1  = PatientProfile(user_id=pat1.id, doctor_id=doc1.id,
                              dob='1988-06-15', gender='Female',
                              blood_group='O+', allergies='Penicillin')
        db.session.add(pp1)
        db.session.flush()

        pat2 = make_user('Bob Kumar', 'bob', 'bob@example.com', 'Patient@456', 'patient')
        pp2  = PatientProfile(user_id=pat2.id, doctor_id=doc2.id,
                              dob='1975-11-22', gender='Male',
                              blood_group='A+', allergies='None known')
        db.session.add(pp2)
        db.session.flush()

        pat3 = make_user('Priya Nair', 'priya', 'priya@example.com', 'Patient@789', 'patient')
        pp3  = PatientProfile(user_id=pat3.id, doctor_id=doc1.id,
                              dob='1995-03-10', gender='Female',
                              blood_group='B+', allergies='Sulfa drugs')
        db.session.add(pp3)
        db.session.flush()

        # ── Medical Records ────────────────────────────────────────────────────
        db.session.add(MedicalRecord(
            patient_id=pp1.id, doctor_id=doc1.id,
            diagnosis_enc=encrypt_data('Hypertension Stage 1'),
            notes_enc=encrypt_data('Patient reports persistent headache and fatigue. BP 145/92 mmHg.'),
            prescription_enc=encrypt_data('Amlodipine 5mg once daily. Review in 4 weeks.'),
        ))
        db.session.add(MedicalRecord(
            patient_id=pp1.id, doctor_id=doc1.id,
            diagnosis_enc=encrypt_data('Follow-up: Blood pressure improving'),
            notes_enc=encrypt_data('BP now 128/82. Patient tolerating medication well.'),
            prescription_enc=encrypt_data('Continue Amlodipine 5mg. Add lifestyle counselling.'),
        ))
        db.session.add(MedicalRecord(
            patient_id=pp2.id, doctor_id=doc2.id,
            diagnosis_enc=encrypt_data('Chronic Migraine'),
            notes_enc=encrypt_data('3-4 episodes per month. Triggered by stress and bright lights.'),
            prescription_enc=encrypt_data('Sumatriptan 50mg at onset. Max 2 per day. Topiramate 25mg nightly.'),
        ))
        db.session.add(MedicalRecord(
            patient_id=pp3.id, doctor_id=doc1.id,
            diagnosis_enc=encrypt_data('Atrial Fibrillation (paroxysmal)'),
            notes_enc=encrypt_data('Palpitations on exertion. ECG confirms AF. Echo ordered.'),
            prescription_enc=encrypt_data('Metoprolol 25mg twice daily. Anticoagulation pending Echo results.'),
        ))

        # ── Appointments ───────────────────────────────────────────────────────
        db.session.add(Appointment(
            patient_id=pp1.id, doctor_id=doc1.id,
            scheduled_date='2026-07-20', scheduled_time='10:00',
            reason='Routine blood pressure check', status='confirmed'))
        db.session.add(Appointment(
            patient_id=pp2.id, doctor_id=doc2.id,
            scheduled_date='2026-07-22', scheduled_time='14:30',
            reason='Migraine follow-up', status='pending'))
        db.session.add(Appointment(
            patient_id=pp3.id, doctor_id=doc1.id,
            scheduled_date='2026-07-18', scheduled_time='09:00',
            reason='Echo result review', status='confirmed'))

        db.session.commit()

        print('\n[OK] HealthPlus database seeded!\n')
        print('  Role    | Username     | Password')
        print('  --------+--------------+-------------')
        print('  admin   | admin        | Admin@1234')
        print('  doctor  | dr_johnson   | Doctor@123')
        print('  doctor  | dr_mehta     | Doctor@456')
        print('  patient | alice        | Patient@123')
        print('  patient | bob          | Patient@456')
        print('  patient | priya        | Patient@789')
        print('\n  Run: python app.py --> http://localhost:5000\n')


if __name__ == '__main__':
    seed()
