if ('serviceWorker' in navigator) navigator.serviceWorker.register('sw.js').catch(() => {});
try { const t = localStorage.getItem('munshi-theme'); if (t === 'dark' || t === 'light') document.documentElement.setAttribute('data-theme', t); } catch {}
import { h, mount } from '/lab/ui.js';
import { setBusinessKey, getBusinessKey, setUnauthorizedHandler } from '/lab/api.js';
import { t, setLang, getLang } from './i18n.js';
import { icon, isOnline, setOnline } from './kit.js';
import { shell, load, refreshBadge, saveProfile } from './shell.js';

// A business opens its private link (…/assistant/?k=KEY) once; the key is kept on this device and removed from the address bar.
// New links carry the key after '#' (browsers never send that part to the server, so it stays out of access logs); older links used '?k='.
const hashKey = (location.hash.match(/(?:^#|&)k=([^&]+)/) || [])[1];
const linkKey = hashKey || new URLSearchParams(location.search).get('k');
if (linkKey) { setBusinessKey(decodeURIComponent(linkKey)); history.replaceState(null, '', location.pathname + (hashKey ? '' : location.hash)); }

// No sign-in yet (or it has ended): ask for the phone number instead of an admin token.
setUnauthorizedHandler(() => import('./views/login.js').then((m) => m.showLogin()));

const ROUTES = {
  calls: () => import('./views/calls.js'), thread: () => import('./views/thread.js'), detail: () => import('./views/detail.js'), know: () => import('./views/know.js'),
  contacts: () => import('./views/contacts.js'), more: () => import('./views/more.js'), setup: () => import('./views/setup.js'), plan: () => import('./views/plan.js'),
  voice: () => import('./views/voice.js'), try: () => import('./views/try.js'), start: () => import('./views/start.js'), orders: () => import('./views/orders.js'),
};
const NAV = [['calls', ['कॉल', 'Calls'], 'phone'], ['know', ['जानकारी', 'Shop info'], 'book'], ['contacts', ['संपर्क', 'Contacts'], 'people'], ['more', ['सेटिंग', 'Settings'], 'more']];
const FULL = new Set(['thread', 'detail', 'setup', 'plan', 'voice', 'try', 'start', 'orders']);
const banner = document.getElementById('banner'); const view = document.getElementById('view'); const nav = document.getElementById('nav');
let cleanup = null; let token = 0;

function parse() {
  const [path, query = ''] = location.hash.replace(/^#\/?/, '').split('?');
  const [name = 'calls', ...rest] = path.split('/').filter(Boolean);
  return { name: ROUTES[name] ? name : 'calls', param: decodeURIComponent(rest.join('/')), query: new URLSearchParams(query) };
}
function drawBanner() {
  mount(banner, isOnline() ? null : h('div', { class: 'offline' }, icon('alert', 18), t(['इंटरनेट नहीं है। पुरानी कॉल दिख रही हैं।', 'No internet. Showing old calls.'])));
}
function drawNav(name) {
  nav.hidden = FULL.has(name);
  mount(nav, ...NAV.map(([id, label, ic]) => h('a', { href: `#/${id}`, class: 'nv' + (id === name ? ' on' : ''), 'aria-current': id === name ? 'page' : null },
    h('span', {}, icon(ic), id === 'calls' && shell.badge ? h('b', {}, String(shell.badge)) : null), t(label))));
}

async function route() {
  const mine = ++token;
  const { name, param, query } = parse();
  if (cleanup) { try { cleanup(); } catch { /* ignore */ } cleanup = null; }
  document.querySelectorAll('#app > .scrim, #app > .toast').forEach((el) => el.remove());
  drawNav(name); drawBanner();
  const box = h('div', { class: 'col' });
  mount(view, box);
  try {
    const mod = await ROUTES[name]();
    if (mine !== token) return;
    cleanup = (await mod.render(box, { param, query })) || null;
    if (mine !== token && cleanup) { cleanup(); cleanup = null; }
  } catch (err) {
    if (mine !== token) return;
    if (err && err.status === 0) setOnline(false);
    mount(box, h('div', { class: 'scroll' }, h('div', { class: 'empty' }, h('b', {}, t(['कुछ गड़बड़ हुई', 'Something went wrong'])), h('p', {}, err.message || String(err)),
      h('button', { class: 'big', style: 'margin-top:12px', onclick: route }, t(['फिर कोशिश करें', 'Try again'])))));
    if (!err.status && err.status !== 0) console.error(err);
  }
}

window.addEventListener('hashchange', () => { route(); refreshBadge(); });
window.addEventListener('munshi-lang', () => { route(); if (shell.profile && shell.profile.ui_lang !== getLang()) saveProfile({ ui_lang: getLang() }).catch(() => {}); });  // call notes are translated into this language
window.addEventListener('munshi-online', () => { drawBanner(); if (isOnline()) route(); });
window.addEventListener('munshi-badge', () => drawNav(parse().name));
window.addEventListener('munshi-changed', refreshBadge);

(async () => {
  // …/assistant/?signin=1 shows the phone sign-in even where the server still lets anyone in, so it can be tried before sign-in is made compulsory.
  if (new URLSearchParams(location.search).has('signin') && !getBusinessKey()) { history.replaceState(null, '', location.pathname + location.hash); await import('./views/login.js').then((m) => m.showLogin()); }
  try { await load(); } catch (e) { if (e.status === 0) setOnline(false); }
  const p = shell.profile;  // a new owner goes through the first-run steps; an existing shop that is already set up does not
  if (p && !p.onboarded && !(p.business_name && p.owner_name && p.business_name !== 'New business') && !location.hash.startsWith('#/start')) location.hash = '#/start';
  route();
  refreshBadge();
  // Push notifications: subscribe if supported and backend has VAPID keys
  if ('serviceWorker' in navigator && 'PushManager' in window) {
    navigator.serviceWorker.ready.then(async (reg) => {
      try {
        const r = await fetch('/api/assistant/push/key'); const { key, enabled } = await r.json();
        if (!enabled || !key) return;
        let sub = await reg.pushManager.getSubscription();
        if (!sub) {
          const pad = '='.repeat((4 - key.length % 4) % 4);
          const raw = atob((key + pad).replace(/-/g, '+').replace(/_/g, '/'));
          sub = await reg.pushManager.subscribe({ userVisibleOnly: true, applicationServerKey: Uint8Array.from([...raw].map(c => c.charCodeAt(0))) });
        }
        await fetch('/api/assistant/push/subscribe', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body: JSON.stringify(sub.toJSON()) });
      } catch { /* push not available or denied */ }
    }).catch(() => {});
  }
})();
export { getLang, setLang };
