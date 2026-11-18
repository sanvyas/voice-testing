import { h, mount } from '/lab/ui.js';
import { setBusinessKey } from '/lab/api.js';
import { t, setLang, getLang } from './i18n.js';
import { icon, isOnline, setOnline } from './kit.js';
import { shell, load, refreshBadge } from './shell.js';

// A business opens its private link (…/assistant/?k=KEY) once; the key is kept on this device and removed from the address bar.
const linkKey = new URLSearchParams(location.search).get('k');
if (linkKey) { setBusinessKey(linkKey); history.replaceState(null, '', location.pathname + location.hash); }

const ROUTES = {
  calls: () => import('./views/calls.js'), thread: () => import('./views/thread.js'), detail: () => import('./views/detail.js'), know: () => import('./views/know.js'),
  contacts: () => import('./views/contacts.js'), more: () => import('./views/more.js'), setup: () => import('./views/setup.js'), plan: () => import('./views/plan.js'),
  voice: () => import('./views/voice.js'), try: () => import('./views/try.js'),
};
const NAV = [['calls', ['कॉल', 'Calls'], 'phone'], ['know', ['जानकारी', 'Shop info'], 'book'], ['contacts', ['संपर्क', 'Contacts'], 'people'], ['more', ['सेटिंग', 'Settings'], 'more']];
const FULL = new Set(['thread', 'detail', 'setup', 'plan', 'voice', 'try']);
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
window.addEventListener('munshi-lang', route);
window.addEventListener('munshi-online', () => { drawBanner(); if (isOnline()) route(); });
window.addEventListener('munshi-badge', () => drawNav(parse().name));
window.addEventListener('munshi-changed', refreshBadge);

(async () => {
  try { await load(); } catch (e) { if (e.status === 0) setOnline(false); }
  route();
  refreshBadge();
})();
export { getLang, setLang };
