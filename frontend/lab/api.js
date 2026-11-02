import { h, dialog, field } from './ui.js';

const TOKEN_KEY = 'lab.token';
const getToken = () => { try { return localStorage.getItem(TOKEN_KEY) || ''; } catch { return ''; } };
export const setToken = (t) => { try { t ? localStorage.setItem(TOKEN_KEY, t) : localStorage.removeItem(TOKEN_KEY); } catch { /* storage blocked */ } };
export const hasToken = () => !!getToken();

export class ApiError extends Error {
  constructor(message, status) { super(message); this.status = status; }
}

function formatDetail(detail) {
  if (Array.isArray(detail)) {
    return detail.map((d) => {
      const where = (d.loc || []).filter((p) => p !== 'body').join(' → ');
      const msg = String(d.msg || '').replace(/^Value error, /, '');
      return where ? `${where}: ${msg}` : msg;
    }).join('\n');
  }
  return typeof detail === 'string' ? detail : 'Request failed';
}

let loginPromise = null;
function askForToken() {
  if (loginPromise) return loginPromise;
  loginPromise = new Promise((resolve) => {
    const input = h('input', { type: 'password', autocomplete: 'current-password', placeholder: 'Access token' });
    const save = () => { setToken(input.value.trim()); close(); resolve(); };
    const close = dialog('Sign in', h('form', { class: 'stack', onsubmit: (e) => { e.preventDefault(); save(); } },
      h('p', { class: 'muted', style: 'margin:0' }, 'Enter your access token (LAB_API_TOKENS on the server).'),
      field('Token', input), h('button', { class: 'go', type: 'submit' }, 'Continue')), { locked: true });
  }).finally(() => { loginPromise = null; });
  return loginPromise;
}

export async function api(path, { method = 'GET', body, raw = false, _retry = true } = {}) {
  const headers = {};
  const token = getToken();
  if (token) headers.Authorization = `Bearer ${token}`;
  if (body !== undefined) headers['Content-Type'] = 'application/json';
  let res;
  try {
    res = await fetch(`/api/lab${path}`, { method, headers, body: body === undefined ? undefined : JSON.stringify(body) });
  } catch {
    throw new ApiError('Cannot reach the server. Check your connection.', 0);
  }
  if (res.status === 401 && _retry) {
    await askForToken();
    return api(path, { method, body, raw, _retry: false });
  }
  if (!res.ok) {
    let detail = res.statusText;
    try { detail = formatDetail((await res.json()).detail); } catch { /* not json */ }
    throw new ApiError(detail, res.status);
  }
  if (res.status === 204) return null;
  return raw ? res.text() : res.json();
}

let configCache = null;
export async function getConfig(force = false) {
  if (!configCache || force) configCache = await api('/config');
  return configCache;
}

export async function apiForm(path, form) {
  const headers = {};
  const token = getToken();
  if (token) headers.Authorization = `Bearer ${token}`;
  let res;
  try { res = await fetch(`/api/lab${path}`, { method: 'POST', headers, body: form }); }
  catch { throw new ApiError('Cannot reach the server. Check your connection.', 0); }
  if (res.status === 401) { await askForToken(); return apiForm(path, form); }
  if (!res.ok) {
    let detail = res.statusText;
    try { detail = formatDetail((await res.json()).detail); } catch { /* not json */ }
    throw new ApiError(detail, res.status);
  }
  return res.json();
}
