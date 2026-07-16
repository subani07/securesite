from functools import wraps
from flask import (Blueprint, render_template, request, redirect,
                   url_for, flash, session)
from extensions import db
from models.user import User
from models.patient_profile import PatientProfile
from models.doctor_profile import DoctorProfile
from models.medical import MedicalRecord, PatientUpload, Appointment
from models.activity import UserActivity
from security.crypto import encrypt_data, decrypt_data

doctor_bp = Blueprint('doctor', __name__, url_prefix='/doctor')


def doctor_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('user_id'):
            flash('Please log in.', 'warning')
            return redirect(url_for('auth.login'))
        if session.get('role') != 'doctor':
            flash('Doctor access required.', 'error')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated


def _log(user_id, action, details=''):
    db.session.add(UserActivity(
        user_id=user_id, action=action, details=details,
        ip_address=request.remote_addr or '127.0.0.1'))
    db.session.commit()


def _current_doctor():
    user = User.query.get(session['user_id'])
    return user


# ── Dashboard ──────────────────────────────────────────────────────────────────
@doctor_bp.route('/dashboard')
@doctor_required
def dashboard():
    user = _current_doctor()
    doc_profile = DoctorProfile.query.filter_by(user_id=user.id).first()

    # Patients assigned to this doctor
    patients = PatientProfile.query.filter_by(doctor_id=user.id).all()

    # Pending appointments
    pending_appts = (Appointment.query
                     .filter_by(doctor_id=user.id, status='pending')
                     .order_by(Appointment.scheduled_date.asc())
                     .limit(5).all())

    confirmed_appts = (Appointment.query
                       .filter_by(doctor_id=user.id, status='confirmed')
                       .order_by(Appointment.scheduled_date.asc())
                       .limit(5).all())

    total_records = (MedicalRecord.query
                     .join(PatientProfile, MedicalRecord.patient_id == PatientProfile.id)
                     .filter(PatientProfile.doctor_id == user.id).count())

    return render_template('doctor/dashboard.html',
                           user=user, doc_profile=doc_profile,
                           patients=patients,
                           pending_appts=pending_appts,
                           confirmed_appts=confirmed_appts,
                           total_records=total_records,
                           decrypt=decrypt_data)


# ── Patient List ───────────────────────────────────────────────────────────────
@doctor_bp.route('/patients')
@doctor_required
def patients():
    user = _current_doctor()
    patient_profiles = PatientProfile.query.filter_by(doctor_id=user.id).all()
    _log(user.id, 'PATIENT_LIST_VIEWED', f'{len(patient_profiles)} patients viewed')
    return render_template('doctor/patients.html', user=user,
                           patients=patient_profiles)


# ── Patient Medical Record (View + Create/Update) ──────────────────────────────
@doctor_bp.route('/patient/<int:patient_profile_id>/record', methods=['GET', 'POST'])
@doctor_required
def patient_record(patient_profile_id):
    user = _current_doctor()
    profile = PatientProfile.query.get_or_404(patient_profile_id)

    # ReBAC: only assigned doctor
    if profile.doctor_id != user.id:
        _log(user.id, 'ACCESS_DENIED', f'Unauthorized access to patient {patient_profile_id}')
        flash('You are not assigned to this patient.', 'error')
        return redirect(url_for('doctor.patients'))

    if request.method == 'POST':
        diagnosis    = request.form.get('diagnosis', '').strip()
        notes        = request.form.get('notes', '').strip()
        prescription = request.form.get('prescription', '').strip()
        if not diagnosis:
            flash('Diagnosis is required.', 'error')
        else:
            rec = MedicalRecord(
                patient_id=profile.id,
                doctor_id=user.id,
                diagnosis_enc=encrypt_data(diagnosis),
                notes_enc=encrypt_data(notes) if notes else None,
                prescription_enc=encrypt_data(prescription) if prescription else None,
            )
            db.session.add(rec)
            db.session.commit()
            _log(user.id, 'RECORD_CREATED',
                 f'Doctor created record for patient profile {patient_profile_id}')
            flash('Medical record saved successfully.', 'success')
        return redirect(url_for('doctor.patient_record', patient_profile_id=patient_profile_id))

    records = (MedicalRecord.query
               .filter_by(patient_id=profile.id)
               .order_by(MedicalRecord.created_at.desc()).all())

    uploads = (PatientUpload.query
               .filter_by(patient_id=profile.id)
               .order_by(PatientUpload.created_at.desc()).all())

    _log(user.id, 'RECORD_VIEWED', f'Doctor viewed records for patient {patient_profile_id}')
    return render_template('doctor/record.html',
                           user=user, profile=profile,
                           records=records, uploads=uploads,
                           decrypt=decrypt_data)


# ── Appointments ───────────────────────────────────────────────────────────────
@doctor_bp.route('/appointments')
@doctor_required
def appointments():
    user = _current_doctor()
    status_filter = request.args.get('status', '')
    q = Appointment.query.filter_by(doctor_id=user.id)
    if status_filter:
        q = q.filter_by(status=status_filter)
    all_appts = q.order_by(Appointment.scheduled_date.asc()).all()
    return render_template('doctor/appointments.html',
                           user=user, appointments=all_appts,
                           status_filter=status_filter)


@doctor_bp.route('/appointments/<int:appt_id>/update', methods=['POST'])
@doctor_required
def update_appointment(appt_id):
    user = _current_doctor()
    appt = Appointment.query.filter_by(id=appt_id, doctor_id=user.id).first_or_404()
    new_status   = request.form.get('status', '').strip()
    doctor_notes = request.form.get('doctor_notes', '').strip()
    if new_status in ('confirmed', 'completed', 'cancelled'):
        appt.status = new_status
    if doctor_notes:
        appt.doctor_notes = doctor_notes
    db.session.commit()
    _log(user.id, 'APPOINTMENT_UPDATED', f'Appt {appt_id} → {new_status}')
    flash(f'Appointment marked as {new_status}.', 'success')
    return redirect(url_for('doctor.appointments'))
