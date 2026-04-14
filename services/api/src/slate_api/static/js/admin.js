'use strict';

const API = '/api/v1';
const state = { editingUserId: null };

// ── Load users ────────────────────────────────────────────────────────────────
async function loadUsers() {
  try {
    const res = await fetch(`${API}/users/?limit=500`);
    const users = await res.json();
    renderTable(users);
  } catch (e) {
    renderEmpty('Error al cargar usuarios: ' + e.message);
  }
}

function renderTable(users) {
  const tbody = document.getElementById('users-tbody');
  if (!users.length) {
    tbody.innerHTML = '<tr class="empty-row"><td colspan="6">Sin usuarios registrados.</td></tr>';
    return;
  }
  tbody.innerHTML = users.map((u) => `
    <tr>
      <td style="color:#64748b;">#${u.id}</td>
      <td><strong>${u.first_name} ${u.last_name}</strong></td>
      <td style="color:#94a3b8;">${u.email}</td>
      <td style="color:#94a3b8;">${u.phone || '—'}</td>
      <td style="color:#475569;">${fmtDate(u.created_at)}</td>
      <td style="display:flex;gap:6px;">
        <button class="btn btn-edit"   onclick="editUser(${u.id})">✏️ Editar</button>
        <button class="btn btn-danger" onclick="deleteUser(${u.id}, '${u.first_name} ${u.last_name}')">🗑</button>
      </td>
    </tr>
  `).join('');
}

function renderEmpty(msg) {
  document.getElementById('users-tbody').innerHTML =
    `<tr class="empty-row"><td colspan="6">${msg}</td></tr>`;
}

function fmtDate(iso) {
  if (!iso) return '—';
  return new Date(iso).toLocaleDateString('es-MX', {
    day: '2-digit', month: 'short', year: 'numeric',
  });
}

// ── Form show/hide ────────────────────────────────────────────────────────────
function showForm(user = null) {
  state.editingUserId = user ? user.id : null;
  document.getElementById('form-title').textContent =
    user ? `Editar Usuario #${user.id}` : 'Nuevo Usuario';
  document.getElementById('f-fname').value = user?.first_name || '';
  document.getElementById('f-lname').value = user?.last_name  || '';
  document.getElementById('f-email').value = user?.email      || '';
  document.getElementById('f-phone').value = user?.phone      || '';
  document.getElementById('form-error').style.display = 'none';
  document.getElementById('user-form').style.display = 'block';
  document.getElementById('f-fname').focus();
  document.getElementById('user-form').scrollIntoView({ behavior: 'smooth' });
}

function hideForm() {
  document.getElementById('user-form').style.display = 'none';
  state.editingUserId = null;
}

function showFormError(msg) {
  const el = document.getElementById('form-error');
  el.textContent = msg;
  el.style.display = 'block';
}

// ── Submit (create or update) ─────────────────────────────────────────────────
async function submitForm() {
  const fname = document.getElementById('f-fname').value.trim();
  const lname = document.getElementById('f-lname').value.trim();
  const email = document.getElementById('f-email').value.trim();
  const phone = document.getElementById('f-phone').value.trim() || null;

  if (!fname || !lname || !email) {
    showFormError('Nombre, apellido y email son obligatorios.');
    return;
  }

  const payload = { first_name: fname, last_name: lname, email, phone };

  try {
    let res;
    if (state.editingUserId) {
      res = await fetch(`${API}/users/${state.editingUserId}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
    } else {
      res = await fetch(`${API}/users/`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(payload),
      });
    }

    if (!res.ok) {
      const err = await res.json();
      showFormError(err.detail || 'Error al guardar.');
      return;
    }

    hideForm();
    await loadUsers();
    showToast(state.editingUserId ? '✅ Usuario actualizado.' : '✅ Usuario creado.');
  } catch (e) {
    showFormError('Error de red: ' + e.message);
  }
}

// ── Edit ──────────────────────────────────────────────────────────────────────
async function editUser(userId) {
  try {
    const res = await fetch(`${API}/users/${userId}`);
    const user = await res.json();
    showForm(user);
  } catch (e) {
    showToast('Error al cargar usuario.');
  }
}

// ── Delete ────────────────────────────────────────────────────────────────────
async function deleteUser(userId, name) {
  if (!confirm(`¿Eliminar a ${name}? Los siniestros asociados se mantendrán.`)) return;

  try {
    const res = await fetch(`${API}/users/${userId}`, { method: 'DELETE' });
    if (!res.ok && res.status !== 204) {
      const err = await res.json();
      showToast('Error: ' + (err.detail || res.statusText));
      return;
    }
    await loadUsers();
    showToast('🗑 Usuario eliminado.');
  } catch (e) {
    showToast('Error de red: ' + e.message);
  }
}

// ── Toast notification ────────────────────────────────────────────────────────
let _toastTimer = null;
function showToast(msg) {
  const el = document.getElementById('toast');
  el.textContent = msg;
  el.style.display = 'block';
  clearTimeout(_toastTimer);
  _toastTimer = setTimeout(() => { el.style.display = 'none'; }, 3000);
}

// ── Init ──────────────────────────────────────────────────────────────────────
loadUsers();
