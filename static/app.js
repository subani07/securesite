// --- Global Application State ---
let currentUser = null;
let mfaPollInterval = null;
let mfaTimeRemaining = 0;

// Initialize App
document.addEventListener('DOMContentLoaded', () => {
    checkAuthStatus();
    startMfaLocalTicker();
    toggleRegistrationRoleFields();
});

// --- API Helper Function ---
async function makeRequest(url, method = 'GET', body = null) {
    const options = {
        method,
        headers: {
            'Content-Type': 'application/json',
            'X-CSRF-Token': window.csrfToken || ''
        }
    };
    
    if (body && method !== 'GET') {
        options.body = JSON.stringify(body);
    }

    try {
        const response = await fetch(url, options);
        const data = await response.json();
        
        if (data.csrf_token) {
            window.csrfToken = data.csrf_token;
        }

        if (!response.ok) {
            return { error: data.error || 'Server request failed.' };
        }
        return data;
    } catch (err) {
        return { error: 'Network communication failure.' };
    }
}

// --- Check Session Status ---
async function checkAuthStatus() {
    const res = await makeRequest('/api/auth/status');
    if (res.authenticated) {
        currentUser = res.user;
        renderStatusBar();
        showDashboardView();
    } else {
        currentUser = null;
        renderStatusBar();
        switchView('view-auth');
    }
}

// --- UI Navigation ---
function switchView(viewId) {
    document.querySelectorAll('.workspace-view').forEach(view => {
        view.classList.remove('active');
    });
    const targetView = document.getElementById(viewId);
    if (targetView) targetView.classList.add('active');
}

function switchAuthTab(type) {
    const tabLogin = document.getElementById('tab-login');
    const tabRegister = document.getElementById('tab-register');
    const containerLogin = document.getElementById('form-login-container');
    const containerRegister = document.getElementById('form-register-container');
    const mfaContainer = document.getElementById('mfa-verify-container');

    mfaContainer.classList.add('hidden');

    if (type === 'login') {
        tabLogin.classList.add('active');
        tabRegister.classList.remove('active');
        containerLogin.classList.remove('hidden');
        containerRegister.classList.add('hidden');
    } else {
        tabLogin.classList.remove('active');
        tabRegister.classList.add('active');
        containerLogin.classList.add('hidden');
        containerRegister.classList.remove('hidden');
        toggleRegistrationRoleFields();
    }
}

// Toggle role specific fields in registration form
function toggleRegistrationRoleFields() {
    const roleSelect = document.getElementById('reg-role');
    if (!roleSelect) return;
    const role = roleSelect.value;
    const fields = document.getElementById('patient-registration-fields');
    if (role === 'patient') {
        fields.style.display = 'block';
        loadRegistrationDoctors();
    } else {
        fields.style.display = 'none';
    }
}

async function loadRegistrationDoctors() {
    const res = await makeRequest('/api/doctors');
    const select = document.getElementById('reg-doctor');
    if (!select) return;
    select.innerHTML = '<option value="none">Choose Primary Physician...</option>';
    if (res && !res.error) {
        res.forEach(doc => {
            const opt = document.createElement('option');
            opt.value = doc.id;
            opt.textContent = `Dr. ${doc.username}`;
            select.appendChild(opt);
        });
    }
}

// --- Render Status Header ---
function renderStatusBar() {
    const statusBar = document.getElementById('user-status-bar');
    if (currentUser) {
        let roleBadgeClass = 'badge-secure';
        if (currentUser.role === 'doctor') roleBadgeClass = 'badge-primary';
        if (currentUser.role === 'admin') roleBadgeClass = 'badge-danger';
        
        statusBar.innerHTML = `
            <span class="status-online">Secure Session Active</span>
            <span class="badge ${roleBadgeClass}">${currentUser.role}</span>
            <strong style="color: var(--text-primary); font-size: 14px;">${currentUser.username}</strong>
            <button class="btn btn-outline btn-small" onclick="handleLogout()" style="padding: 4px 8px; font-size: 11px;">Logout</button>
        `;
    } else {
        statusBar.innerHTML = `
            <span class="status-offline">Offline</span>
            <button class="btn btn-primary btn-small" onclick="switchView('view-auth')" style="padding: 4px 8px; font-size: 11px;">Login</button>
        `;
    }
}

// --- Show Dashboard for Logged In User ---
function showDashboardView() {
    if (!currentUser) return;
    
    if (currentUser.role === 'patient') {
        switchView('view-patient');
        loadPatientDashboard();
    } else if (currentUser.role === 'doctor') {
        switchView('view-doctor');
        loadDoctorDashboard();
    } else if (currentUser.role === 'admin') {
        switchView('view-admin');
        loadAdminAuditLogs();
    }
}

// --- AUTHENTICATION ACTIONS ---
async function handleRegister(e) {
    e.preventDefault();
    const username = document.getElementById('reg-username').value;
    const email = document.getElementById('reg-email').value;
    const password = document.getElementById('reg-password').value;
    const role = document.getElementById('reg-role').value;

    const body = { username, email, password, role };
    if (role === 'patient') {
        body.name = document.getElementById('reg-name').value;
        body.dob = document.getElementById('reg-dob').value;
        body.gender = document.getElementById('reg-gender').value;
        body.doctor_id = document.getElementById('reg-doctor').value;
    }

    const res = await makeRequest('/api/auth/register', 'POST', body);
    if (res.error) {
        alert(`Registration Error: ${res.error}`);
    } else {
        alert(res.success || 'Registration complete.');
        document.getElementById('form-register').reset();
        switchAuthTab('login');
    }
}

async function handleLogin(e) {
    e.preventDefault();
    const username = document.getElementById('login-username').value;
    const password = document.getElementById('login-password').value;

    const res = await makeRequest('/api/auth/login', 'POST', { username, password });
    if (res.error) {
        alert(`Login Authentication Failed: ${res.error}`);
    } else if (res.status === 'mfa_required') {
        document.getElementById('form-login-container').classList.add('hidden');
        document.getElementById('mfa-verify-container').classList.remove('hidden');
        document.getElementById('mfa-code').value = '';
        document.getElementById('mfa-code').focus();
        
        triggerSmsAlert();
        
        pollMfaCode();
        if (mfaPollInterval) clearInterval(mfaPollInterval);
        mfaPollInterval = setInterval(pollMfaCode, 5000);
    }
}

async function handleMfaVerify(e) {
    e.preventDefault();
    const code = document.getElementById('mfa-code').value;

    const res = await makeRequest('/api/auth/mfa-verify', 'POST', { code });
    if (res.error) {
        alert(`Verification Rejected: ${res.error}`);
    } else {
        currentUser = res.user;
        renderStatusBar();
        showDashboardView();
        
        document.getElementById('mfa-verify-container').classList.add('hidden');
        document.getElementById('form-login-container').classList.remove('hidden');
        document.getElementById('form-login').reset();
        
        if (mfaPollInterval) clearInterval(mfaPollInterval);
    }
}

function cancelMfa() {
    document.getElementById('mfa-verify-container').classList.add('hidden');
    document.getElementById('form-login-container').classList.remove('hidden');
    if (mfaPollInterval) clearInterval(mfaPollInterval);
    makeRequest('/api/auth/logout', 'POST');
}

async function handleLogout() {
    await makeRequest('/api/auth/logout', 'POST');
    currentUser = null;
    renderStatusBar();
    switchView('view-auth');
}

// --- MFA PHONE EMULATOR ---
async function pollMfaCode() {
    const res = await fetch('/api/mfa/emulator-code');
    if (!res.ok) return;
    const data = await res.json();
    
    document.getElementById('phone-totp-code').textContent = data.code;
    document.getElementById('phone-sms-code').textContent = data.code;
    mfaTimeRemaining = data.time_left;
    updateMfaProgress();
}

function startMfaLocalTicker() {
    setInterval(() => {
        if (mfaTimeRemaining > 0) {
            mfaTimeRemaining--;
            updateMfaProgress();
        }
    }, 1000);
}

function updateMfaProgress() {
    const bar = document.getElementById('phone-totp-progress');
    const timerLabel = document.getElementById('phone-totp-timer');
    if (!bar) return;
    
    const percentage = (mfaTimeRemaining / 30) * 100;
    bar.style.width = `${percentage}%`;
    timerLabel.textContent = `${mfaTimeRemaining}s remaining`;
    
    if (mfaTimeRemaining < 6) {
        bar.style.backgroundColor = 'var(--color-danger)';
    } else {
        bar.style.backgroundColor = 'var(--color-primary)';
    }
}

function triggerSmsAlert() {
    const notification = document.getElementById('phone-sms-alert');
    notification.classList.add('active');
    setTimeout(() => {
        notification.classList.remove('active');
    }, 6000);
}

// --- PATIENT VIEW LOAD ---
async function loadPatientDashboard() {
    const docRes = await makeRequest('/api/patient/record');
    if (docRes && !docRes.error) {
        document.getElementById('patient-welcome').textContent = `Welcome back, ${docRes.patient_name}`;
        document.getElementById('patient-diagnosis').textContent = docRes.record.diagnosis;
        document.getElementById('patient-notes').textContent = docRes.record.notes;
        document.getElementById('patient-prescription').textContent = docRes.record.prescription;
    } else {
        document.getElementById('patient-diagnosis').textContent = 'No clinical diagnosis recorded.';
        document.getElementById('patient-notes').textContent = 'No physician observations recorded yet.';
        document.getElementById('patient-prescription').textContent = 'None';
    }
    
    loadPatientSelfRecords();
}

async function loadPatientSelfRecords() {
    const res = await makeRequest('/api/patient/my-records');
    const tbody = document.getElementById('patient-uploads-body');
    if (!tbody) return;
    tbody.innerHTML = '';
    
    if (!res || res.error || res.length === 0) {
        tbody.innerHTML = '<tr><td colspan="4" style="text-align: center; color: var(--text-muted); padding: 15px;">No self-reported records or documents saved yet.</td></tr>';
        return;
    }
    
    res.forEach(r => {
        const row = document.createElement('tr');
        row.style.borderBottom = '1px solid var(--border-color)';
        
        let attachmentLink = '<span style="color: var(--text-muted);">None</span>';
        if (r.file_name) {
            attachmentLink = `<a href="/api/patient/download-file/${r.id}" class="btn btn-outline btn-small" style="padding: 2px 6px; font-size: 11px;">📥 Download (${r.file_name})</a>`;
        }
        
        row.innerHTML = `
            <td style="padding: 10px 5px; color: var(--text-muted);">${r.created_at}</td>
            <td style="padding: 10px 5px; font-weight: 500;">${escapeHtml(r.title)}</td>
            <td style="padding: 10px 5px;">${escapeHtml(r.description)}</td>
            <td style="padding: 10px 5px;">${attachmentLink}</td>
        `;
        tbody.appendChild(row);
    });
}

async function handlePatientUpload(e) {
    e.preventDefault();
    const title = document.getElementById('upload-title').value;
    const description = document.getElementById('upload-description').value;
    const fileInput = document.getElementById('upload-file');
    
    const formData = new FormData();
    formData.append('title', title);
    formData.append('description', description);
    if (fileInput.files.length > 0) {
        formData.append('file', fileInput.files[0]);
    }
    
    const options = {
        method: 'POST',
        headers: {
            'X-CSRF-Token': window.csrfToken || ''
        },
        body: formData
    };
    
    try {
        const response = await fetch('/api/patient/upload-record', options);
        const data = await response.json();
        
        if (!response.ok) {
            alert(`Save Error: ${data.error || 'Server error.'}`);
        } else {
            alert('Medical record and file secured successfully!');
            document.getElementById('form-patient-upload').reset();
            loadPatientSelfRecords();
        }
    } catch (err) {
        alert('Network communication error uploading record.');
    }
}

// --- DOCTOR VIEW LOAD ---
let doctorPatientsList = [];
let selectedPatientId = null;

async function loadDoctorDashboard() {
    const res = await makeRequest('/api/doctor/patients');
    if (res.error) {
        alert(res.error);
        return;
    }
    
    doctorPatientsList = res;
    const listContainer = document.getElementById('doc-patient-list');
    listContainer.innerHTML = '';
    
    if (doctorPatientsList.length === 0) {
        listContainer.innerHTML = '<p class="empty-list-msg">No assigned patients found.</p>';
        return;
    }

    doctorPatientsList.forEach(p => {
        const item = document.createElement('button');
        item.className = 'patient-item';
        item.dataset.patientId = p.id;
        if (selectedPatientId === p.id) item.classList.add('active');
        
        item.innerHTML = `
            <h4>${p.name}</h4>
            <p>DOB: ${p.dob} | Gender: ${p.gender}</p>
        `;
        
        item.onclick = () => selectPatientForEdit(p.id);
        listContainer.appendChild(item);
    });
}

async function selectPatientForEdit(patientId) {
    selectedPatientId = patientId;
    
    document.querySelectorAll('.patient-item').forEach(item => item.classList.remove('active'));
    
    const res = await makeRequest(`/api/doctor/patient/${patientId}/record`);
    if (res.error) {
        alert(res.error);
        return;
    }

    document.getElementById('doc-empty-state').classList.add('hidden');
    document.getElementById('doc-editor-form-container').classList.remove('hidden');
    
    document.getElementById('editing-patient-name').textContent = `Chart: ${res.patient_name}`;
    document.getElementById('edit-diagnosis').value = res.record.diagnosis || '';
    document.getElementById('edit-notes').value = res.record.notes || '';
    document.getElementById('edit-prescription').value = res.record.prescription || '';
    
    // Highlight list item
    const activeItem = document.querySelector(`.patient-item[data-patient-id="${patientId}"]`);
    if (activeItem) activeItem.classList.add('active');
    
    loadDoctorPatientUploads(patientId);
}

async function loadDoctorPatientUploads(patientId) {
    const res = await makeRequest(`/api/doctor/patient/${patientId}/patient-records`);
    const tbody = document.getElementById('doc-patient-uploads-body');
    if (!tbody) return;
    tbody.innerHTML = '';
    
    if (!res || res.error || res.length === 0) {
        tbody.innerHTML = '<tr><td colspan="4" style="text-align: center; color: var(--text-muted); padding: 15px;">No patient-uploaded records found.</td></tr>';
        return;
    }
    
    res.forEach(r => {
        const row = document.createElement('tr');
        row.style.borderBottom = '1px solid var(--border-color)';
        
        let attachmentLink = '<span style="color: var(--text-muted);">None</span>';
        if (r.file_name) {
            attachmentLink = `<a href="/api/patient/download-file/${r.id}" class="btn btn-outline btn-small" style="padding: 2px 6px; font-size: 11px;">📥 Download</a>`;
        }
        
        row.innerHTML = `
            <td style="padding: 10px 5px; color: var(--text-muted);">${r.created_at}</td>
            <td style="padding: 10px 5px; font-weight: 500;">${escapeHtml(r.title)}</td>
            <td style="padding: 10px 5px;">${escapeHtml(r.description)}</td>
            <td style="padding: 10px 5px;">${attachmentLink}</td>
        `;
        tbody.appendChild(row);
    });
}

async function handleDocSubmit(e) {
    e.preventDefault();
    if (!selectedPatientId) return;

    const diagnosis = document.getElementById('edit-diagnosis').value;
    const notes = document.getElementById('edit-notes').value;
    const prescription = document.getElementById('edit-prescription').value;

    const res = await makeRequest(`/api/doctor/patient/${selectedPatientId}/record`, 'POST', {
        diagnosis,
        notes,
        prescription
    });

    if (res.error) {
        alert(res.error);
    } else {
        alert('Chart secured and database updated successfully!');
    }
}

// --- ADMIN AUDIT VIEWS ---
async function loadAdminAuditLogs() {
    const res = await makeRequest('/api/admin/audit-logs');
    if (res.error) {
        alert(res.error);
        return;
    }

    const tbody = document.getElementById('audit-table-body');
    tbody.innerHTML = '';
    
    let logsTampered = false;

    res.forEach(log => {
        const row = document.createElement('tr');
        
        let statusBadge = '';
        if (log.integrity_check) {
            statusBadge = '<span class="badge badge-success">✓ Secured</span>';
        } else {
            statusBadge = '<span class="badge badge-danger">⚠️ TAMPERED</span>';
            row.style.backgroundColor = 'rgba(244, 63, 94, 0.08)';
            logsTampered = true;
        }

        row.innerHTML = `
            <td><code>${log.id}</code></td>
            <td>${log.timestamp}</td>
            <td>${log.user_id ? log.user_id : 'Guest'}</td>
            <td><strong>${log.action}</strong></td>
            <td>${log.details}</td>
            <td>${log.ip_address}</td>
            <td>${statusBadge}</td>
        `;
        
        tbody.appendChild(row);
    });

    const headerBadge = document.getElementById('audit-integrity-header');
    if (logsTampered) {
        headerBadge.innerHTML = '<span class="badge badge-danger" style="animation: pulse 1s infinite alternate">System Audit Log Compromised!</span>';
    } else {
        headerBadge.innerHTML = '<span class="badge badge-success">System Logs Intact</span>';
    }
    
    loadAdminUsersList();
}

async function loadAdminUsersList() {
    const res = await makeRequest('/api/admin/users');
    const tbody = document.getElementById('admin-users-table-body');
    if (!tbody) return;
    tbody.innerHTML = '';
    
    if (!res || res.error) {
        tbody.innerHTML = '<tr><td colspan="6" style="text-align: center; padding: 15px;">Failed to load user list.</td></tr>';
        return;
    }
    
    const doctors = res.doctors || [];
    const users = res.users || [];
    
    users.forEach(u => {
        const row = document.createElement('tr');
        row.style.borderBottom = '1px solid var(--border-color)';
        
        let patientProfileCell = '<span style="color: var(--text-muted);">N/A</span>';
        
        row.innerHTML = `
            <td style="padding: 10px;"><code>${u.id}</code></td>
            <td style="padding: 10px; font-weight: 500;">${escapeHtml(u.username)}</td>
            <td style="padding: 10px;"><span class="badge ${u.role === 'admin' ? 'badge-danger' : (u.role === 'doctor' ? 'badge-primary' : 'badge-secure')}">${u.role}</span></td>
            <td style="padding: 10px;">${escapeHtml(u.email)}</td>
            <td style="padding: 10px;" class="pat-profile-cell"></td>
            <td style="padding: 10px;" class="physician-td-select"></td>
        `;
        
        const patTd = row.querySelector('.pat-profile-cell');
        const docTd = row.querySelector('.physician-td-select');
        
        if (u.role === 'patient') {
            patTd.innerHTML = `<strong>${escapeHtml(u.patient_name || 'Profile Missing')}</strong> (ID: ${u.patient_id})`;
            
            const select = document.createElement('select');
            select.style.padding = '4px 8px';
            select.style.fontSize = '12px';
            select.style.background = 'rgba(255, 255, 255, 0.04)';
            select.style.color = 'var(--text-primary)';
            select.style.border = '1px solid var(--border-color)';
            select.style.borderRadius = '4px';
            select.onchange = (e) => assignDoctorToPatient(u.patient_id, e.target.value);
            
            const optNone = document.createElement('option');
            optNone.value = 'none';
            optNone.textContent = 'Unassigned';
            if (!u.doctor_id) optNone.selected = true;
            select.appendChild(optNone);
            
            doctors.forEach(doc => {
                const opt = document.createElement('option');
                opt.value = doc.id;
                opt.textContent = `Dr. ${escapeHtml(doc.username)}`;
                if (doc.id == u.doctor_id) opt.selected = true;
                select.appendChild(opt);
            });
            
            docTd.appendChild(select);
        } else {
            patTd.innerHTML = '<span style="color: var(--text-muted);">N/A</span>';
            docTd.innerHTML = '<span style="color: var(--text-muted);">N/A</span>';
        }
        tbody.appendChild(row);
    });
}

async function assignDoctorToPatient(patientId, doctorId) {
    const res = await makeRequest('/api/admin/assign-doctor', 'POST', {
        patient_id: patientId,
        doctor_id: doctorId
    });
    
    if (res.error) {
        alert(`Error Assigning Doctor: ${res.error}`);
    } else {
        alert('Doctor assignment updated successfully!');
        loadAdminUsersList();
    }
}

// --- HELPERS ---
function escapeHtml(str) {
    if (!str) return '';
    return str
        .replace(/&/g, "&amp;")
        .replace(/</g, "&lt;")
        .replace(/>/g, "&gt;")
        .replace(/"/g, "&quot;")
        .replace(/'/g, "&#039;");
}
