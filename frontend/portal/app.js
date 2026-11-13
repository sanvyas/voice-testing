import { h, mount } from '/lab/ui.js';
import { A, ic, ICONS } from '/assistant/net.js';
import { businessList, choose, selectedId } from './ctx.js';

const MONEY = ['M12 3v18', 'M17 7.5C17 5.6 14.8 4.5 12 4.5S7 5.6 7 7.5 9.2 10.5 12 10.5s5 1.1 5 3-2.2 3-5 3-5-1.1-5-3'];
const TABS = [
  ['overview', 'Overview', ['M4 13h6V4H4z', 'M14 20h6V4h-6z', 'M4 20h6v-3H4z'], []], ['businesses', 'Businesses', ICONS.users, [[9.5, 7, 3.5]]], ['calls', 'Calls', ICONS.phone, []],
  ['knowledge', 'Knowledge', ICONS.board, []], ['prompts', 'Prompts', ICONS.chat, []], ['integrations', 'Integrations', ICONS.sliders, []], ['costs', 'Costs', MONEY, []], ['activity', 'Activity', ['M4 6h16', 'M4 12h16', 'M4 18h10'], []],
];
const loaders = Object.fromEntries(TABS.map(([id]) => [id, () => import(`./views/${id}.js`)]));
const view = document.getElementById('pview');
let token = 0; let attention = 0; let list = [];

const current = () => { const n = location.hash.replace(/^#\/?/, '').split(/[/?]/)[0]; return loaders[n] ? n : 'overview'; };
const drawNav = (active) => mount(document.getElementById('sidenav'), ...TABS.map(([id, label, paths, circles]) => h('a', { href: `#/${id}`, class: id === active ? 'on' : '', 'aria-current': id === active ? 'page' : null }, ic(paths, circles, true), label, id === 'overview' && attention ? h('span', { class: 'n' }, String(attention)) : null)));

function drawSwitcher() {
  if (selectedId() && !list.some((b) => b.id === selectedId())) choose('');  // the chosen business was deleted
  const sel = h('select', { id: 'bizpick', 'aria-label': 'Work on business', onchange: (e) => choose(e.target.value) }, h('option', { value: '' }, `All businesses (${list.length})`), ...list.map((b) => h('option', { value: b.id, selected: b.id === selectedId() }, b.name + (b.active ? '' : ' (paused)'))));
  mount(document.getElementById('switcher'), h('label', { for: 'bizpick' }, 'Working on'), sel);
}

async function route() {
  const mine = ++token; const name = current(); drawNav(name);
  mount(view, h('div', { class: 'empty' }, 'Loading…'));
  try {
    const mod = await loaders[name]();
    if (mine !== token) return;
    const page = h('div', { class: 'page' }); mount(view, page);
    await mod.render(page, { query: new URLSearchParams(location.hash.split('?')[1] || '') });
    window.scrollTo(0, 0);
  } catch (err) { if (mine === token) mount(view, h('div', { class: 'card empty' }, h('p', {}, err.message || String(err)), h('button', { class: 'plain', onclick: route }, 'Try again'))); if (!err.status) console.error(err); }
}

async function live() {
  try {
    list = await businessList();
    drawSwitcher();
    const sel = list.find((b) => b.id === selectedId());
    const need = sel ? sel.needs_action : list.reduce((n, b) => n + b.needs_action, 0);
    mount(document.getElementById('live'), sel
      ? h('div', {}, h('b', {}, sel.name), h('div', {}, `${sel.active ? 'Active' : 'Paused'} · ${need} need the owner`), h('div', { style: 'margin-top:8px' }, h('a', { href: '/assistant/', target: '_blank', rel: 'noopener' }, 'Open its app'), ' · ', h('a', { href: '/assistant/#/try', target: '_blank', rel: 'noopener' }, 'Try a call')))
      : h('div', {}, h('b', {}, 'All businesses'), h('div', {}, `${list.filter((b) => b.active).length} active · ${need} calls need owners`)));
  } catch { /* signed out */ }
}
window.addEventListener('hashchange', route);
window.addEventListener('business-changed', async () => { await live(); route(); });
window.addEventListener('portal-attention', (e) => { attention = e.detail; drawNav(current()); });
window.addEventListener('munshi-changed', live);
drawNav(current()); live().then(route);
