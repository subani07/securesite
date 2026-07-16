/* ============================================================
   auth.js — Authentication form helpers
   ============================================================ */

// ── Password Strength Checker ──────────────────────────────────
function checkPasswordStrength(password) {
  const fill    = document.getElementById('strengthFill');
  const label   = document.getElementById('strengthLabel');
  if (!fill || !label) return;

  const checks = {
    len:     password.length >= 8,
    longer:  password.length >= 12,
    upper:   /[A-Z]/.test(password),
    lower:   /[a-z]/.test(password),
    digit:   /[0-9]/.test(password),
    special: /[!@#$%^&*()\-_=+\[\]{}|;:,.<>?]/.test(password),
  };
  const score = Object.values(checks).filter(Boolean).length;

  // Update checklist items
  const map = {
    'chk-len':     checks.len,
    'chk-upper':   checks.upper,
    'chk-lower':   checks.lower,
    'chk-digit':   checks.digit,
    'chk-special': checks.special,
  };
  Object.entries(map).forEach(([id, passed]) => {
    const el = document.getElementById(id);
    if (el) el.className = passed ? 'passed' : '';
  });

  const configs = [
    { pct: 0,   color: '#333', text: 'Enter a password', textColor: 'var(--text-muted)' },
    { pct: 16,  color: '#ff4d6d', text: 'Very Weak',    textColor: '#ff4d6d' },
    { pct: 33,  color: '#ff8c42', text: 'Weak',         textColor: '#ff8c42' },
    { pct: 50,  color: '#fbbf24', text: 'Fair',         textColor: '#fbbf24' },
    { pct: 66,  color: '#34d399', text: 'Good',         textColor: '#34d399' },
    { pct: 83,  color: '#00f5a0', text: 'Strong',       textColor: '#00f5a0' },
    { pct: 100, color: '#00d4ff', text: 'Very Strong',  textColor: '#00d4ff' },
  ];
  const cfg = password.length === 0 ? configs[0] : configs[Math.min(score, 6)];

  fill.style.width      = `${cfg.pct}%`;
  fill.style.background = cfg.color;
  label.textContent     = cfg.text;
  label.style.color     = cfg.textColor;
}

// ── Password Match Check ───────────────────────────────────────
function checkPasswordMatch() {
  const pw   = document.getElementById('password');
  const cpw  = document.getElementById('confirm_password');
  const hint = document.getElementById('matchHint');
  if (!pw || !cpw || !hint) return;
  if (!cpw.value) { hint.textContent = ''; return; }
  if (pw.value === cpw.value) {
    hint.textContent = '✓ Passwords match';
    hint.className   = 'match-hint match-ok';
  } else {
    hint.textContent = '✕ Passwords do not match';
    hint.className   = 'match-hint match-bad';
  }
}

// ── Register form client-side validation ──────────────────────
const registerForm = document.getElementById('registerForm');
if (registerForm) {
  registerForm.addEventListener('submit', e => {
    const pw  = document.getElementById('password')?.value || '';
    const cpw = document.getElementById('confirm_password')?.value || '';
    const username = document.getElementById('username')?.value || '';

    if (pw !== cpw) {
      e.preventDefault();
      showToast('Passwords do not match', 'error');
      return;
    }
    if (!/^[a-zA-Z0-9_]+$/.test(username)) {
      e.preventDefault();
      showToast('Username: only letters, numbers, underscores allowed', 'error');
      return;
    }
    const btn = document.getElementById('registerBtn');
    if (btn) { btn.disabled = true; btn.textContent = 'Creating account…'; }
  });
}

// ── Login form loader state ────────────────────────────────────
const loginForm = document.getElementById('loginForm');
if (loginForm) {
  loginForm.addEventListener('submit', () => {
    const btn = document.getElementById('loginBtn');
    if (btn) { btn.disabled = true; btn.innerHTML = '<span>Signing in…</span>'; }
  });
}

// ── showToast fallback (in case main.js not loaded yet) ───────
if (typeof showToast === 'undefined') {
  function showToast(msg) { console.log('[Toast]', msg); }
}
