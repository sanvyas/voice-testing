import { h, mount, icon } from '/lab/ui.js';

const TABS = [['calls', 'Calls'], ['try', 'Try it'], ['contacts', 'Contacts'], ['setup', 'Setup']];
const ICONS = {
  calls: () => icon(['M5 4h4l2 5-2.5 1.5a11 11 0 0 0 5 5L15 13l5 2v4a2 2 0 0 1-2 2A16 16 0 0 1 3 6a2 2 0 0 1 2-2z']),
  try: () => icon(['M12 3a3 3 0 0 0-3 3v6a3 3 0 0 0 6 0V6a3 3 0 0 0-3-3z', 'M5 11a7 7 0 0 0 14 0', 'M12 18v3']),
  contacts: () => icon(['M16 21v-2a4 4 0 0 0-4-4H7a4 4 0 0 0-4 4v2', 'M20 8v6', 'M23 11h-6'], [[9.5, 7, 3.5]]),
  setup: () => icon(['M4 8h8', 'M16 8h4', 'M4 16h4', 'M12 16h8'], [[14, 8, 2], [10, 16, 2]]),
};
const loaders = { calls: () => import('./views/calls.js'), try: () => import('./views/try.js'), contacts: () => import('./views/contacts.js'), setup: () => import('./views/setup.js') };
const view = document.getElementById('view');
let cleanup = null; let token = 0;

function parse() {
  const [path, query = ''] = location.hash.replace(/^#\/?/, '').split('?');
  const [name = 'calls', ...rest] = path.split('/').filter(Boolean);
  return { name: loaders[name] ? name : 'calls', params: rest, query: new URLSearchParams(query) };
}
const drawNav = (active) => mount(document.getElementById('nav'), ...TABS.map(([id, label]) => h('a', { href: `#/${id}`, class: id === active ? 'on' : '', 'aria-current': id === active ? 'page' : null }, ICONS[id](), h('span', {}, label))));

async function route() {
  const mine = ++token;
  const { name, params, query } = parse();
  drawNav(name);
  if (cleanup) { try { cleanup(); } catch { /* ignore */ } cleanup = null; }
  mount(view, h('div', { class: 'empty' }, 'Loading…'));
  try {
    const mod = await loaders[name]();
    if (mine !== token) return;
    const box = h('div', { class: 'stack', style: 'gap:18px' });
    mount(view, box);
    cleanup = (await mod.render(box, { params, query })) || null;
    if (mine !== token && cleanup) { cleanup(); cleanup = null; }
    window.scrollTo(0, 0);
  } catch (err) {
    if (mine === token) mount(view, h('div', { class: 'card empty' }, h('p', {}, err.message || String(err)), h('button', { onclick: route }, 'Try again')));
    if (!err.status) console.error(err);
  }
}
window.addEventListener('hashchange', route);
drawNav(parse().name);
route();
