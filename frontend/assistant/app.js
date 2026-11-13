import { h, mount } from '/lab/ui.js';
import { setBusinessKey } from '/lab/api.js';
import { A, ic, ICONS } from './net.js';

// A business opens its private link (…/assistant/?k=KEY) once; the key is kept on this device and removed from the address bar.
const linkKey = new URLSearchParams(location.search).get('k');
if (linkKey) { setBusinessKey(linkKey); history.replaceState(null, '', location.pathname + location.hash); }

const TABS = [['calls', 'Calls', ICONS.phone, []], ['try', 'Try it', ICONS.mic, []], ['contacts', 'Contacts', ICONS.users, [[9.5, 7, 3.5]]], ['setup', 'Setup', ICONS.sliders, [[14, 8, 2], [10, 16, 2]]]];
const loaders = { calls: () => import('./views/calls.js'), try: () => import('./views/try.js'), contacts: () => import('./views/contacts.js'), setup: () => import('./views/setup.js'), board: () => import('./views/board.js') };
const view = document.getElementById('view');
let cleanup = null; let token = 0; let badge = 0;

function parse() {
  const [path, query = ''] = location.hash.replace(/^#\/?/, '').split('?');
  const [name = 'calls', ...rest] = path.split('/').filter(Boolean);
  return { name: loaders[name] ? name : 'calls', params: rest, query: new URLSearchParams(query) };
}
const tabFor = (name) => (name === 'board' ? 'setup' : name);
const drawNav = (active) => mount(document.getElementById('nav'), ...TABS.map(([id, label, paths, circles]) => h('a', { href: `#/${id}`, class: 'tab' + (id === tabFor(active) ? ' on' : ''), 'aria-current': id === tabFor(active) ? 'page' : null },
  ic(paths, circles), h('span', {}, label), id === 'calls' && badge ? h('span', { class: 'dot', 'aria-label': `${badge} need you` }, String(badge)) : null)));

async function route() {
  const mine = ++token;
  const { name, params, query } = parse();
  document.body.classList.remove('immersive');
  drawNav(name);
  if (cleanup) { try { cleanup(); } catch { /* ignore */ } cleanup = null; }
  mount(view, h('div', { class: 'empty' }, 'Loading…'));
  try {
    const mod = await loaders[name]();
    if (mine !== token) return;
    const box = h('div', { class: 'screen' });
    mount(view, box);
    cleanup = (await mod.render(box, { params, query })) || null;
    if (mine !== token && cleanup) { cleanup(); cleanup = null; }
    window.scrollTo(0, 0);
  } catch (err) {
    if (mine === token) mount(view, h('div', { class: 'screen' }, h('div', { class: 'card empty' }, h('p', {}, err.message || String(err)), h('button', { class: 'plain', onclick: route }, 'Try again'))));
    if (!err.status) console.error(err);
  }
}
async function refreshBadge() {
  try { const s = await A('/stats'); if (s.needs_action !== badge) { badge = s.needs_action; drawNav(parse().name); } } catch { /* signed out or offline */ }
}
window.addEventListener('hashchange', () => { route(); refreshBadge(); });
window.addEventListener('munshi-changed', refreshBadge);
drawNav(parse().name);
route();
refreshBadge();
