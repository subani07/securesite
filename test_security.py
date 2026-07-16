import unittest
import sqlite3
import json
import os
import sys
from app import app, get_totp_code
import crypto

class HealthPulseSecurityTests(unittest.TestCase):
    def setUp(self):
        # Configure app for testing
        app.config['TESTING'] = True
        self.client = app.test_client()
        
        # Initialize and seed database
        with self.client.session_transaction() as sess:
            sess['csrf_token'] = 'test_csrf_token_value'
            
        self.client.post('/api/admin/seed-demo', headers={'X-CSRF-Token': 'test_csrf_token_value'})

    def get_csrf_session_token(self):
        """Inject a mock CSRF token in the test session and return it."""
        with self.client.session_transaction() as sess:
            sess['csrf_token'] = 'test_csrf_token_value'
            return 'test_csrf_token_value'

    def test_unauthenticated_access_denied(self):
        """Test that unauthenticated requests to patient and doctor portals return 403 Forbidden."""
        response = self.client.get('/api/patient/record')
        self.assertEqual(response.status_code, 403)
        
        response = self.client.get('/api/doctor/patients')
        self.assertEqual(response.status_code, 403)
        
        response = self.client.get('/api/admin/audit-logs')
        self.assertEqual(response.status_code, 403)

    def test_database_encryption_at_rest(self):
        """Test that sensitive patient medical data is stored as ciphertext in SQLite database."""
        conn = sqlite3.connect('healthpulse.db')
        conn.row_factory = sqlite3.Row
        row = conn.execute('SELECT * FROM medical_records LIMIT 1').fetchone()
        conn.close()
        
        # Verify encryption exists
        diag_cipher = row['diagnosis_encrypted']
        notes_cipher = row['notes_encrypted']
        presc_cipher = row['prescription_encrypted']
        
        # Plaintext secrets must not be visible in raw database columns
        self.assertNotIn('Migraine', diag_cipher)
        self.assertNotIn('Sumatriptan', presc_cipher)
        
        # Must decrypt correctly using crypto keys
        self.assertEqual(crypto.decrypt_data(diag_cipher), "Chronic Migraine")
        self.assertEqual(crypto.decrypt_data(presc_cipher), "Sumatriptan 50mg, take 1 tablet at onset of migraine; limit to max 2/day.")

    def test_unauthorized_relationship_access(self):
        """Test Relationship-Based Access Control: Doctor is restricted from access to unassigned patient charts."""
        csrf = self.get_csrf_session_token()
        
        # 1. Login as dr_johnson (assigned doctor for Alice Smith)
        login_res = self.client.post('/api/auth/login', 
                                    data=json.dumps({'username': 'dr_johnson', 'password': 'doctor123'}),
                                    content_type='application/json',
                                    headers={'X-CSRF-Token': csrf})
        self.assertEqual(login_res.status_code, 200)
        login_data = json.loads(login_res.data)
        self.assertEqual(login_data['status'], 'mfa_required')
        
        # 2. Complete simulated MFA Verification
        mfa_code = get_totp_code(login_data['mfa_secret'])
        mfa_res = self.client.post('/api/auth/mfa-verify',
                                    data=json.dumps({'code': mfa_code}),
                                    content_type='application/json',
                                    headers={'X-CSRF-Token': csrf})
        self.assertEqual(mfa_res.status_code, 200)
        
        # 3. Inject an unassigned patient record directly in SQLite
        conn = sqlite3.connect('healthpulse.db')
        cursor = conn.cursor()
        # Insert user (role: patient), patient profile (assigned to Doctor ID 999), and medical record
        cursor.execute("INSERT INTO users (id, username, email, password_hash, role) VALUES (100, 'unassigned_pat', 'un@assigned.com', 'fake', 'patient')")
        cursor.execute("INSERT INTO patients (id, user_id, doctor_id, name, dob, gender) VALUES (100, 100, 999, 'Unassigned Patient', '1990-01-01', 'Male')")
        cursor.execute("INSERT INTO medical_records (patient_id, diagnosis_encrypted, notes_encrypted, prescription_encrypted) VALUES (100, 'fake', 'fake', 'fake')")
        conn.commit()
        conn.close()
        
        # 4. Attempt to request record of Patient 100 as Doctor 1 (who is not assigned to Patient 100)
        res = self.client.get('/api/doctor/patient/100/record')
        # Response should be blocked with 403 Access Denied
        self.assertEqual(res.status_code, 403)
        self.assertIn("Access Denied", json.loads(res.data)['error'])

    def test_audit_log_tamper_detection(self):
        """Test that raw modifications to the logs (bypassing the application layer) trigger verification failure."""
        conn = sqlite3.connect('healthpulse.db')
        conn.row_factory = sqlite3.Row
        log = conn.execute('SELECT * FROM audit_logs LIMIT 1').fetchone()
        
        # Signature must initially be correct
        self.assertTrue(crypto.verify_log_entry(log))
        
        # Simulate SQL database tampering (modifying log details directly on disk)
        cursor = conn.cursor()
        cursor.execute('UPDATE audit_logs SET details = "TAMPERED: Admin login succeeded" WHERE id = ?', (log['id'],))
        conn.commit()
        
        # Re-fetch tampered log
        tampered_log = conn.execute('SELECT * FROM audit_logs WHERE id = ?', (log['id'],)).fetchone()
        conn.close()
        
        # Verification check should now catch the signature failure
        self.assertFalse(crypto.verify_log_entry(tampered_log))

    def test_patient_self_records_and_secure_download(self):
        """Test patient uploading self-records and secure ReBAC rules for downloads."""
        csrf = self.get_csrf_session_token()
        
        # 1. Login as patient (alice_smith / patient123)
        login_res = self.client.post('/api/auth/login', 
                                    data=json.dumps({'username': 'alice_smith', 'password': 'patient123'}),
                                    content_type='application/json',
                                    headers={'X-CSRF-Token': csrf})
        self.assertEqual(login_res.status_code, 200)
        login_data = json.loads(login_res.data)
        
        mfa_code = get_totp_code(login_data['mfa_secret'])
        mfa_res = self.client.post('/api/auth/mfa-verify',
                                    data=json.dumps({'code': mfa_code}),
                                    content_type='application/json',
                                    headers={'X-CSRF-Token': csrf})
        self.assertEqual(mfa_res.status_code, 200)
        
        # 2. Add self-reported record via API
        import io
        record_res = self.client.post('/api/patient/upload-record',
                                       data={
                                           'title': 'My Symptom Log',
                                           'description': 'Feeling mild headaches in the evening.',
                                           'file': (io.BytesIO(b"dummy pdf content"), 'symptoms.pdf')
                                       },
                                       content_type='multipart/form-data',
                                       headers={'X-CSRF-Token': csrf})
        self.assertEqual(record_res.status_code, 200)
        
        # 3. Check encryption at rest in DB
        conn = sqlite3.connect('healthpulse.db')
        conn.row_factory = sqlite3.Row
        row = conn.execute('SELECT * FROM patient_records ORDER BY id DESC LIMIT 1').fetchone()
        conn.close()
        
        self.assertIsNotNone(row)
        # Ensure plaintext title and description are NOT visible directly in DB
        self.assertNotIn('My Symptom Log', row['title_encrypted'])
        self.assertNotIn('mild headaches', row['description_encrypted'])
        
        # Decrypt check
        self.assertEqual(crypto.decrypt_data(row['title_encrypted']), "My Symptom Log")
        self.assertEqual(crypto.decrypt_data(row['description_encrypted']), "Feeling mild headaches in the evening.")
        
        # 4. Verify patient can download the file
        download_res = self.client.get(f"/api/patient/download-file/{row['id']}")
        self.assertEqual(download_res.status_code, 200)
        self.assertEqual(download_res.data, b"dummy pdf content")
        
        # 5. Verify assigned doctor (dr_johnson) can download
        # First logout patient
        self.client.post('/api/auth/logout', headers={'X-CSRF-Token': csrf})
        csrf = self.get_csrf_session_token()
        
        # Login as dr_johnson
        login_res = self.client.post('/api/auth/login', 
                                    data=json.dumps({'username': 'dr_johnson', 'password': 'doctor123'}),
                                    content_type='application/json',
                                    headers={'X-CSRF-Token': csrf})
        self.assertEqual(login_res.status_code, 200)
        login_data = json.loads(login_res.data)
        mfa_code = get_totp_code(login_data['mfa_secret'])
        self.client.post('/api/auth/mfa-verify',
                        data=json.dumps({'code': mfa_code}),
                        content_type='application/json',
                        headers={'X-CSRF-Token': csrf})
                        
        # Download as doctor
        download_res = self.client.get(f"/api/patient/download-file/{row['id']}")
        self.assertEqual(download_res.status_code, 200)
        self.assertEqual(download_res.data, b"dummy pdf content")
        
        # 6. Verify unassigned doctor CANNOT download
        # Create unassigned doctor in DB with correct password hash
        conn = sqlite3.connect('healthpulse.db')
        cursor = conn.cursor()
        stranger_hash = crypto.hash_password("stranger123")
        cursor.execute("INSERT INTO users (id, username, email, password_hash, mfa_secret, role) VALUES (40, 'dr_stranger', 'stranger@docs.com', ?, 'STR_SECRET', 'doctor')", (stranger_hash,))
        conn.commit()
        conn.close()
        
        # Logout dr_johnson
        self.client.post('/api/auth/logout', headers={'X-CSRF-Token': csrf})
        csrf = self.get_csrf_session_token()
        
        # Login as dr_stranger
        login_res = self.client.post('/api/auth/login', 
                                    data=json.dumps({'username': 'dr_stranger', 'password': 'stranger123'}),
                                    content_type='application/json',
                                    headers={'X-CSRF-Token': csrf})
        self.assertEqual(login_res.status_code, 200)
        login_data = json.loads(login_res.data)
        mfa_code = get_totp_code(login_data['mfa_secret'])
        self.client.post('/api/auth/mfa-verify',
                        data=json.dumps({'code': mfa_code}),
                        content_type='application/json',
                        headers={'X-CSRF-Token': csrf})
                        
        # Attempt download as unassigned doctor
        download_res = self.client.get(f"/api/patient/download-file/{row['id']}")
        self.assertEqual(download_res.status_code, 403) # Blocked!


    def test_admin_doctor_assignment(self):
        """Test that Admin can retrieve all users and assign doctors to patients."""
        csrf = self.get_csrf_session_token()
        
        # 1. Login as admin_sec
        login_res = self.client.post('/api/auth/login', 
                                    data=json.dumps({'username': 'admin_sec', 'password': 'admin123'}),
                                    content_type='application/json',
                                    headers={'X-CSRF-Token': csrf})
        login_data = json.loads(login_res.data)
        mfa_code = get_totp_code(login_data['mfa_secret'])
        self.client.post('/api/auth/mfa-verify',
                        data=json.dumps({'code': mfa_code}),
                        content_type='application/json',
                        headers={'X-CSRF-Token': csrf})
                        
        # 2. Get user list as admin
        users_res = self.client.get('/api/admin/users')
        self.assertEqual(users_res.status_code, 200)
        users_data = json.loads(users_res.data)
        self.assertTrue(len(users_data['users']) > 0)
        
        # 3. Assign patient 1 to doctor None
        assign_res = self.client.post('/api/admin/assign-doctor',
                                      data=json.dumps({'patient_id': 1, 'doctor_id': 'none'}),
                                      content_type='application/json',
                                      headers={'X-CSRF-Token': csrf})
        self.assertEqual(assign_res.status_code, 200)
        
        # 4. Verify doctor_id is updated in SQLite
        conn = sqlite3.connect('healthpulse.db')
        conn.row_factory = sqlite3.Row
        pat = conn.execute('SELECT * FROM patients WHERE id = 1').fetchone()
        conn.close()
        self.assertIsNone(pat['doctor_id'])

if __name__ == '__main__':
    unittest.main()

