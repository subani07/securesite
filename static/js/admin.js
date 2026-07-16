/* ============================================================
   admin.js — Admin panel helpers
   ============================================================ */

// ── Confirm dialog for destructive actions ─────────────────────
function confirmAction(msg) {
  return window.confirm(msg);
}

// ── Live table search filter ───────────────────────────────────
const userSearch = document.getElementById('userSearch');
if (userSearch) {
  userSearch.addEventListener('input', function() {
    const q = this.value.toLowerCase();
    document.querySelectorAll('#usersTable tbody tr').forEach(row => {
      row.style.display = row.textContent.toLowerCase().includes(q) ? '' : 'none';
    });
  });
}

// ── Role badge colour update on select change ──────────────────
document.querySelectorAll('.role-select').forEach(sel => {
  sel.addEventListener('change', function() {
    if (confirmAction(`Change role to "${this.value}"?`)) {
      this.form.submit();
    } else {
      // Reset to original
      this.value = this.getAttribute('data-original') || this.value;
    }
  });
});
