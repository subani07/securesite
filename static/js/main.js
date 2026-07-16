/* ============================================================
   main.js — Global interactions for SecureApp
   ============================================================ */

// ── Nav Toggle (mobile) ────────────────────────────────────────
const navToggle = document.getElementById('navToggle');
const navLinks  = document.getElementById('navLinks');
if (navToggle && navLinks) {
  navToggle.addEventListener('click', () => {
    navLinks.classList.toggle('open');
  });
}

// ── Auto-dismiss flash messages ────────────────────────────────
document.querySelectorAll('.flash').forEach(el => {
  setTimeout(() => {
    el.style.transition = 'opacity 0.5s, transform 0.5s';
    el.style.opacity = '0';
    el.style.transform = 'translateX(100%)';
    setTimeout(() => el.remove(), 500);
  }, 5000);
});

// ── Animated counter (hero stats) ─────────────────────────────
function animateCounters() {
  document.querySelectorAll('[data-count]').forEach(el => {
    const target = parseInt(el.getAttribute('data-count'), 10);
    const duration = 1500;
    const steps = 50;
    const stepVal = target / steps;
    let current = 0;
    const timer = setInterval(() => {
      current = Math.min(current + stepVal, target);
      el.textContent = Math.round(current);
      if (current >= target) clearInterval(timer);
    }, duration / steps);
  });
}

// Trigger counters when visible
const heroStats = document.querySelector('.hero-stats');
if (heroStats) {
  const observer = new IntersectionObserver(entries => {
    if (entries[0].isIntersecting) {
      animateCounters();
      observer.disconnect();
    }
  }, { threshold: 0.3 });
  observer.observe(heroStats);
}

// ── Feature cards stagger animation ───────────────────────────
document.querySelectorAll('.feature-card').forEach(card => {
  const delay = card.getAttribute('data-delay') || 0;
  card.style.animationDelay = `${delay}ms`;
});

// ── Terminal typing effect ─────────────────────────────────────
const typingEl = document.getElementById('typingText');
if (typingEl) {
  const phrases = [
    'curl /api/health',
    'python database/seed.py',
    'curl /api/users -H "Bearer ..."',
    'GET /admin/logs → 200 OK',
    'CSRF token validated ✓',
  ];
  let pi = 0, ci = 0, deleting = false;
  function typeLoop() {
    const phrase = phrases[pi];
    if (!deleting) {
      typingEl.textContent = phrase.slice(0, ci + 1);
      ci++;
      if (ci === phrase.length) {
        deleting = true;
        setTimeout(typeLoop, 2200);
        return;
      }
    } else {
      typingEl.textContent = phrase.slice(0, ci - 1);
      ci--;
      if (ci === 0) {
        deleting = false;
        pi = (pi + 1) % phrases.length;
      }
    }
    setTimeout(typeLoop, deleting ? 40 : 80);
  }
  setTimeout(typeLoop, 1200);
}

// ── Toast notification ─────────────────────────────────────────
function showToast(msg, type = 'success') {
  const el = document.createElement('div');
  el.className = `toast toast-${type}`;
  el.textContent = msg;
  document.body.appendChild(el);
  requestAnimationFrame(() => el.classList.add('show'));
  setTimeout(() => {
    el.classList.remove('show');
    setTimeout(() => el.remove(), 300);
  }, 3000);
}

// ── Confirm dialog ─────────────────────────────────────────────
function confirmAction(msg) {
  return window.confirm(msg);
}

// ── Toggle password visibility ─────────────────────────────────
function togglePassword(id) {
  const input = document.getElementById(id);
  if (!input) return;
  input.type = input.type === 'password' ? 'text' : 'password';
}

// ── Navbar scroll effect ───────────────────────────────────────
const navbar = document.getElementById('navbar');
if (navbar) {
  window.addEventListener('scroll', () => {
    navbar.style.boxShadow = window.scrollY > 20
      ? '0 4px 30px rgba(0,0,0,0.5)'
      : 'none';
  });
}

// ── OWASP items animation ──────────────────────────────────────
const owaspItems = document.querySelectorAll('.owasp-item');
if (owaspItems.length) {
  const io = new IntersectionObserver(entries => {
    entries.forEach((entry, i) => {
      if (entry.isIntersecting) {
        entry.target.style.animationDelay = `${i * 60}ms`;
        entry.target.classList.add('fade-in');
        io.unobserve(entry.target);
      }
    });
  }, { threshold: 0.1 });
  owaspItems.forEach(item => io.observe(item));
}
