import { h, mount, toast, icon } from './ui.js';
import { getConfig } from './api.js';

const TABS = [['test', 'Test'], ['talk', 'Talk'], ['results', 'Results'], ['settings', 'Settings']];
const ICONS = {
  test: () => icon(['M9 3h6', 'M10 3v6l-5.2 9.2A2 2 0 0 0 6.5 21h11a2 2 0 0 0 1.7-2.8L14 9V3', 'M8 15h8']),
  talk: () => icon(['M12 3a3 3 0 0 0-3 3v6a3 3 0 0 0 6 0V6a3 3 0 0 0-3-3z', 'M5 11a7 7 0 0 0 14 0', 'M12 18v3']),
  results: () => icon(['M5 20V11', 'M12 20V4', 'M19 20v-7']),
  settings: () => icon(['M4 8h8', 'M16 8h4', 'M4 16h4', 'M12 16h8'], [[14, 8, 2], [10, 16, 2]]),
};
const loaders = {
  test: () => import('./views/test.js'), talk: () => import('./views/talk.js'),
  results: () => import('./views/results.js'), settings: () => import('./views/settings.js'),
};
const view = document.getElementById('view');
let cleanup = null; let token = 0;

function parse() {
  const [path, query = ''] = location.hash.replace(/^#\/?/, '').split('?');
  const [name = 'test', ...rest] = path.split('/').filter(Boolean);
  return { name: loaders[name] ? name : 'test', params: rest, query: new URLSearchParams(query) };
}

function drawNav(active) {
  mount(document.getElementById('nav'), ...TABS.map(([id, label]) => h('a', { href: `#/${id}`, class: id === active ? 'on' : '', 'aria-current': id === active ? 'page' : null }, ICONS[id](), h('span', {}, label))));
}

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

async function banner(force = false) {
  const el = document.getElementById('banner');
  try {
    const cfg = await getConfig(force);
    mount(el, cfg.llm_ready ? null : h('div', { class: 'notice' }, 'Connect Groq to start testing. ', h('a', { href: '#/settings' }, 'Open Settings')),
      cfg.open_access ? h('div', { class: 'notice bad' }, 'Sign-in is off: anyone with this link can use your Groq key, change what your app says and read its conversations. To turn sign-in back on, set LAB_OPEN_ACCESS=false in Render.') : null,
      cfg.storage === 'temporary' ? h('div', { class: 'notice bad' }, 'Temporary storage: your data is lost whenever this server restarts. Set DATABASE_URL to a Postgres database to keep it.') : null);
  } catch (err) { if (err.status !== 401) toast(err.message, true); }
}

window.addEventListener('hashchange', () => { route(); banner(true); });
window.addEventListener('lab-config', () => banner(false));
drawNav(parse().name);  // tabs are visible even before sign-in
banner();
route();
