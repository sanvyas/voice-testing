import { h, dialog, field } from './ui.js';

const TOKEN_KEY = 'lab.token';
const url = (path) => (path.startsWith('/api/') ? path : `/api/lab${path}`);  // other products on this server pass their full path
const getToken = () => { try { return localStorage.getItem(TOKEN_KEY) || ''; } catch { return ''; } };
export const setToken = (t) => { try { t ? localStorage.setItem(TOKEN_KEY, t) : localStorage.removeItem(TOKEN_KEY); } catch { /* storage blocked */ } };
export const hasToken = () => !!getToken();

// A business owner opens a private link (?k=...); the key is kept here. The platform admin picks which business the portal is working on.
const read = (k) => { try { return localStorage.getItem(k) || ''; } catch { return ''; } };
const write = (k, v) => { try { v ? localStorage.setItem(k, v) : localStorage.removeItem(k); } catch { /* storage blocked */ } };
export const getBusinessKey = () => read('munshi.key');
export const setBusinessKey = (v) => write('munshi.key', v);
export const getBusiness = () => read('munshi.biz');
export const setBusiness = (v) => write('munshi.biz', v);
const inPortal = () => location.pathname.startsWith('/portal');

function authHeaders() {
  const headers = {};
  const token = getToken(); if (token) headers.Authorization = `Bearer ${token}`;
  const key = getBusinessKey(); if (key && !inPortal()) headers['X-Business-Key'] = key;  // the portal is always the admin, even in a browser that holds an owner link
  const biz = getBusiness(); if (biz && (inPortal() || !key)) headers['X-Business'] = biz;
  return headers;
}

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
  if (getBusinessKey() && !inPortal()) {  // an owner whose link was replaced or removed: a token would not help
    loginPromise = new Promise((resolve) => {
      setBusinessKey('');
      dialog('This link does not work any more', h('div', { class: 'stack' }, h('p', { class: 'muted', style: 'margin:0' }, 'Ask the person who runs your Munshi account for a new link, then open it on this phone.'),
        h('button', { class: 'go', type: 'button', onclick: () => location.reload() }, 'Try again')), { locked: true });
      resolve();
    }).finally(() => { loginPromise = null; });
    return loginPromise;
  }
  loginPromise = new Promise((resolve) => {
    const input = h('input', { type: 'password', autocomplete: 'current-password', placeholder: 'Access token' });
    const save = () => { setToken(input.value.trim()); close(); resolve(); };
    const close = dialog('Sign in', h('form', { class: 'stack', onsubmit: (e) => { e.preventDefault(); save(); } },
      h('p', { class: 'muted', style: 'margin:0' }, 'Open the private link you were sent, or enter the admin access token (LAB_API_TOKENS on the server).'),
      field('Token', input), h('button', { class: 'go', type: 'submit' }, 'Continue')), { locked: true });
  }).finally(() => { loginPromise = null; });
  return loginPromise;
}

export async function api(path, { method = 'GET', body, raw = false, _retry = true } = {}) {
  const headers = authHeaders();
  if (body !== undefined) headers['Content-Type'] = 'application/json';
  let res;
  try {
    res = await fetch(url(path), { method, headers, body: body === undefined ? undefined : JSON.stringify(body) });
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
  const headers = authHeaders();
  let res;
  try { res = await fetch(url(path), { method: 'POST', headers, body: form }); }
  catch { throw new ApiError('Cannot reach the server. Check your connection.', 0); }
  if (res.status === 401) { await askForToken(); return apiForm(path, form); }
  if (!res.ok) {
    let detail = res.statusText;
    try { detail = formatDetail((await res.json()).detail); } catch { /* not json */ }
    throw new ApiError(detail, res.status);
  }
  return res.json();
}

export async function apiBlob(path, body) {  // POST json, get audio back
  const headers = { ...authHeaders(), 'Content-Type': 'application/json' };
  let res;
  try { res = await fetch(url(path), { method: 'POST', headers, body: JSON.stringify(body) }); }
  catch { throw new ApiError('Cannot reach the server. Check your connection.', 0); }
  if (res.status === 401) { await askForToken(); return apiBlob(path, body); }
  if (!res.ok) {
    let detail = res.statusText;
    try { detail = formatDetail((await res.json()).detail); } catch { /* not json */ }
    throw new ApiError(detail, res.status);
  }
  return { blob: await res.blob(), engine: res.headers.get('X-TTS-Engine') || '', voice: res.headers.get('X-TTS-Voice') || '', chars: +res.headers.get('X-TTS-Chars') || 0, ms: +res.headers.get('X-TTS-Latency-Ms') || 0 };
}
