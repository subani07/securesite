import html as _html
from flask import Blueprint, request, jsonify, session

owasp_bp = Blueprint('owasp', __name__)


@owasp_bp.route('/api/playground/sql-inject', methods=['POST'])
def sql_inject_demo():
    """Demonstrate SQL injection: vulnerable raw concat vs parameterised query."""
    from extensions import db
    data = request.get_json(silent=True) or {}
    user_input = data.get('input', '')

    vulnerable_sql = f"SELECT id, username, email, role FROM users WHERE username = '{user_input}'"
    secure_sql = "SELECT id, username, email, role FROM users WHERE username = ?"

    vuln_results, vuln_status = [], 'SUCCESS'
    secure_results, secure_status = [], 'SUCCESS'

    try:
        result = db.session.execute(
            db.text(f"SELECT id, username, email, role FROM users WHERE username = '{user_input}'")
        )
        vuln_results = [dict(row._mapping) for row in result]
    except Exception as e:
        vuln_status = f'ERROR: {e}'

    try:
        result = db.session.execute(
            db.text("SELECT id, username, email, role FROM users WHERE username = :u"),
            {'u': user_input}
        )
        secure_results = [dict(row._mapping) for row in result]
    except Exception as e:
        secure_status = f'ERROR: {e}'

    return jsonify({
        'vulnerable_query': vulnerable_sql,
        'vulnerable_results': vuln_results,
        'vulnerable_status': vuln_status,
        'secure_query': secure_sql,
        'secure_results': secure_results,
        'secure_status': secure_status,
        'explanation': (
            "Vulnerable: Direct string concatenation lets attackers inject SQL like ' OR '1'='1 "
            "to bypass authentication or dump all rows.\n\n"
            "Secure: Parameterised queries treat user input as data, never as executable SQL."
        )
    })


@owasp_bp.route('/api/playground/xss-sanitize', methods=['POST'])
def xss_demo():
    """Demonstrate XSS: raw output vs HTML-escaped output."""
    data = request.get_json(silent=True) or {}
    xss_input = data.get('input', '')
    sanitized = _html.escape(xss_input)

    return jsonify({
        'vulnerable_output': xss_input,
        'secure_output': sanitized,
        'explanation': (
            "Vulnerable: Rendering raw user input lets <script> tags execute arbitrary JS "
            "in the victim's browser (Stored/Reflected XSS).\n\n"
            "Secure: html.escape() converts < > & \" ' to HTML entities, "
            "rendering them as harmless text instead of executable code."
        )
    })
