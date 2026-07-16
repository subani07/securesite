import os
from flask import Flask, render_template, session, redirect, url_for
from config import config
from extensions import db, bcrypt, jwt, csrf, mail, oauth


def create_app(config_name='development'):
    app = Flask(__name__)
    app.config.from_object(config[config_name])

    os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)

    # ── Extensions ────────────────────────────────────────────────────────────
    db.init_app(app)
    bcrypt.init_app(app)
    jwt.init_app(app)
    csrf.init_app(app)
    mail.init_app(app)
    oauth.init_app(app)

    if app.config.get('GOOGLE_CLIENT_ID'):
        oauth.register(
            name='google',
            client_id=app.config['GOOGLE_CLIENT_ID'],
            client_secret=app.config['GOOGLE_CLIENT_SECRET'],
            server_metadata_url=app.config['GOOGLE_DISCOVERY_URL'],
            client_kwargs={'scope': 'openid email profile'},
        )

    # ── Blueprints ─────────────────────────────────────────────────────────────
    from routes.auth import auth_bp
    from routes.dashboard import dashboard_bp
    from routes.patient import patient_bp
    from routes.doctor import doctor_bp
    from routes.admin import admin_bp
    from routes.api import api_bp
    from security.owasp_demos import owasp_bp

    app.register_blueprint(auth_bp)
    app.register_blueprint(dashboard_bp)
    app.register_blueprint(patient_bp)
    app.register_blueprint(doctor_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(api_bp)
    app.register_blueprint(owasp_bp)

    csrf.exempt(api_bp)
    csrf.exempt(owasp_bp)

    # ── Security Headers ───────────────────────────────────────────────────────
    @app.after_request
    def set_security_headers(response):
        response.headers['X-Content-Type-Options'] = 'nosniff'
        response.headers['X-Frame-Options'] = 'DENY'
        response.headers['X-XSS-Protection'] = '1; mode=block'
        response.headers['Referrer-Policy'] = 'strict-origin-when-cross-origin'
        response.headers['Content-Security-Policy'] = (
            "default-src 'self'; "
            "script-src 'self' 'unsafe-inline'; "
            "style-src 'self' 'unsafe-inline' https://fonts.googleapis.com; "
            "font-src https://fonts.gstatic.com 'self'; "
            "img-src 'self' data: https:; "
            "connect-src 'self';"
        )
        return response

    # ── Core routes ────────────────────────────────────────────────────────────
    @app.route('/')
    def index():
        return render_template('index.html', authenticated=bool(session.get('user_id')),
                               role=session.get('role', ''))

    # ── Error handlers ─────────────────────────────────────────────────────────
    @app.errorhandler(403)
    def forbidden(e):
        return render_template('errors/403.html'), 403

    @app.errorhandler(404)
    def not_found(e):
        return render_template('errors/404.html'), 404

    @app.errorhandler(500)
    def server_error(e):
        return render_template('errors/500.html'), 500

    # ── DB init ────────────────────────────────────────────────────────────────
    with app.app_context():
        from models.user import User              # noqa
        from models.login_log import LoginLog     # noqa
        from models.activity import UserActivity  # noqa
        from models.doctor_profile import DoctorProfile  # noqa
        from models.patient_profile import PatientProfile  # noqa
        from models.medical import MedicalRecord, PatientUpload, Appointment  # noqa
        db.create_all()

    return app


app = create_app('development')

if __name__ == '__main__':
    app.run(debug=True, port=5000)
