import os
from functools import wraps
from flask import (Blueprint, render_template, request, redirect,
                   url_for, flash, session, current_app, send_file, jsonify)
from extensions import db
from models.user import User
from models.patient_profile import PatientProfile
from models.medical import MedicalRecord, PatientUpload, Appointment
from models.activity import UserActivity
from security.crypto import encrypt_data, decrypt_data
from werkzeug.utils import secure_filename

patient_bp = Blueprint('patient', __name__, url_prefix='/patient')

ALLOWED_EXT = {'pdf', 'png', 'jpg', 'jpeg', 'gif', 'doc', 'docx', 'txt'}


def patient_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get('user_id'):
            flash('Please log in.', 'warning')
            return redirect(url_for('auth.login'))
        if session.get('role') != 'patient':
            flash('Patient access required.', 'error')
            return redirect(url_for('auth.login'))
        return f(*args, **kwargs)
    return decorated


def _log(user_id, action, details=''):
    db.session.add(UserActivity(
        user_id=user_id, action=action, details=details,
        ip_address=request.remote_addr or '127.0.0.1'))
    db.session.commit()


def _current_patient():
    user = User.query.get(session['user_id'])
    if not user:
        return None, None
    profile = PatientProfile.query.filter_by(user_id=user.id).first()
    return user, profile


# ── Dashboard ──────────────────────────────────────────────────────────────────
@patient_bp.route('/dashboard')
@patient_required
def dashboard():
    user, profile = _current_patient()
    if not profile:
        flash('Patient profile not set up. Contact admin.', 'warning')
        return redirect(url_for('auth.logout'))

    doctor = User.query.get(profile.doctor_id) if profile.doctor_id else None
    doctor_profile = doctor.doctor_profile if doctor else None

    recent_records = (MedicalRecord.query
                      .filter_by(patient_id=profile.id)
                      .order_by(MedicalRecord.created_at.desc())
                      .limit(3).all())

    upcoming_appts = (Appointment.query
                      .filter_by(patient_id=profile.id)
                      .filter(Appointment.status.in_(['pending', 'confirmed']))
                      .order_by(Appointment.scheduled_date.asc())
                      .limit(3).all())

    record_count = MedicalRecord.query.filter_by(patient_id=profile.id).count()
    upload_count = PatientUpload.query.filter_by(patient_id=profile.id).count()
    appt_count   = Appointment.query.filter_by(patient_id=profile.id).count()

    return render_template('patient/dashboard.html',
                           user=user, profile=profile, doctor=doctor,
                           doctor_profile=doctor_profile,
                           recent_records=recent_records,
                           upcoming_appts=upcoming_appts,
                           record_count=record_count,
                           upload_count=upload_count,
                           appt_count=appt_count,
                           decrypt=decrypt_data)


# ── Medical Records ────────────────────────────────────────────────────────────
@patient_bp.route('/records')
@patient_required
def records():
    user, profile = _current_patient()
    if not profile:
        return redirect(url_for('auth.logout'))
    all_records = (MedicalRecord.query
                   .filter_by(patient_id=profile.id)
                   .order_by(MedicalRecord.created_at.desc()).all())
    _log(user.id, 'RECORDS_VIEWED', 'Patient viewed medical records list')
    return render_template('patient/records.html', user=user, profile=profile,
                           records=all_records, decrypt=decrypt_data)


# ── File Uploads ───────────────────────────────────────────────────────────────
@patient_bp.route('/uploads', methods=['GET', 'POST'])
@patient_required
def uploads():
    user, profile = _current_patient()
    if not profile:
        return redirect(url_for('auth.logout'))

    if request.method == 'POST':
        title = request.form.get('title', '').strip()
        description = request.form.get('description', '').strip()
        if not title:
            flash('Title is required.', 'error')
            return redirect(url_for('patient.uploads'))

        file = request.files.get('file')
        file_name_enc = file_path_enc = file_type = None

        if file and file.filename:
            ext = file.filename.rsplit('.', 1)[-1].lower() if '.' in file.filename else ''
            if ext not in ALLOWED_EXT:
                flash('File type not allowed. Use PDF, image, DOC or TXT.', 'error')
                return redirect(url_for('patient.uploads'))
            orig = secure_filename(file.filename)
            unique = f"pat_{profile.id}_{os.urandom(8).hex()}.{ext}"
            save_path = os.path.join(current_app.config['UPLOAD_FOLDER'], unique)
            os.makedirs(os.path.dirname(save_path), exist_ok=True)
            file.save(save_path)
            file_name_enc = encrypt_data(orig)
            file_path_enc = encrypt_data(save_path)
            file_type = ext.upper()

        upload = PatientUpload(
            patient_id=profile.id,
            title_enc=encrypt_data(title),
            description_enc=encrypt_data(description) if description else None,
            file_name_enc=file_name_enc,
            file_path_enc=file_path_enc,
            file_type=file_type,
        )
        db.session.add(upload)
        db.session.commit()
        _log(user.id, 'FILE_UPLOADED', f'Patient uploaded: {title[:40]}')
        flash('Document uploaded successfully.', 'success')
        return redirect(url_for('patient.uploads'))

    all_uploads = (PatientUpload.query
                   .filter_by(patient_id=profile.id)
                   .order_by(PatientUpload.created_at.desc()).all())
    return render_template('patient/uploads.html', user=user, profile=profile,
                           uploads=all_uploads, decrypt=decrypt_data)


@patient_bp.route('/uploads/download/<int:upload_id>')
@patient_required
def download_file(upload_id):
    user, profile = _current_patient()
    if not profile:
        return redirect(url_for('auth.logout'))
    upload = PatientUpload.query.filter_by(id=upload_id, patient_id=profile.id).first_or_404()
    if not upload.file_path_enc:
        flash('No file attached to this record.', 'error')
        return redirect(url_for('patient.uploads'))
    file_path = decrypt_data(upload.file_path_enc)
    orig_name = decrypt_data(upload.file_name_enc) if upload.file_name_enc else 'download'
    if not os.path.exists(file_path):
        flash('File not found on disk.', 'error')
        return redirect(url_for('patient.uploads'))
    _log(user.id, 'FILE_DOWNLOADED', f'Upload ID {upload_id}')
    return send_file(file_path, as_attachment=True, download_name=orig_name)


@patient_bp.route('/uploads/delete/<int:upload_id>', methods=['POST'])
@patient_required
def delete_upload(upload_id):
    user, profile = _current_patient()
    if not profile:
        return redirect(url_for('auth.logout'))
    upload = PatientUpload.query.filter_by(id=upload_id, patient_id=profile.id).first_or_404()
    if upload.file_path_enc:
        try:
            os.remove(decrypt_data(upload.file_path_enc))
        except Exception:
            pass
    db.session.delete(upload)
    db.session.commit()
    _log(user.id, 'FILE_DELETED', f'Upload ID {upload_id} deleted')
    flash('Record deleted.', 'success')
    return redirect(url_for('patient.uploads'))


# ── Appointments ───────────────────────────────────────────────────────────────
@patient_bp.route('/appointments', methods=['GET', 'POST'])
@patient_required
def appointments():
    user, profile = _current_patient()
    if not profile:
        return redirect(url_for('auth.logout'))

    if request.method == 'POST':
        doctor_id  = request.form.get('doctor_id', type=int)
        sched_date = request.form.get('scheduled_date', '').strip()
        sched_time = request.form.get('scheduled_time', '').strip()
        reason     = request.form.get('reason', '').strip()

        if not doctor_id or not sched_date or not sched_time:
            flash('Doctor, date and time are required.', 'error')
        else:
            appt = Appointment(
                patient_id=profile.id, doctor_id=doctor_id,
                scheduled_date=sched_date, scheduled_time=sched_time,
                reason=reason, status='pending')
            db.session.add(appt)
            db.session.commit()
            _log(user.id, 'APPOINTMENT_BOOKED', f'With doctor ID {doctor_id} on {sched_date}')
            flash('Appointment request sent.', 'success')
        return redirect(url_for('patient.appointments'))

    all_appts = (Appointment.query
                 .filter_by(patient_id=profile.id)
                 .order_by(Appointment.created_at.desc()).all())
    doctors = User.query.filter_by(role='doctor').all()
    from datetime import datetime
    return render_template('patient/appointments.html', user=user, profile=profile,
                           appointments=all_appts, doctors=doctors,
                           now=datetime.utcnow())
