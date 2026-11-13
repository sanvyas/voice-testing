import { h, mount } from '/lab/ui.js';
import { A, ic, ICONS } from '/assistant/net.js';

const TABS = [
  ['overview', 'Overview', ['M4 13h6V4H4z', 'M14 20h6V4h-6z', 'M4 20h6v-3H4z']],
  ['knowledge', 'Knowledge', ICONS.board], ['prompts', 'Prompts', ICONS.chat], ['integrations', 'Integrations', ICONS.sliders],
  ['costs', 'Costs', ['M12 3v18', 'M17 7.5C17 5.6 14.8 4.5 12 4.5S7 5.6 7 7.5 9.2 10.5 12 10.5s5 1.1 5 3-2.2 3-5 3-5-1.1-5-3']], ['activity', 'Activity', ['M4 6h16', 'M4 12h16', 'M4 18h10']],
];
const loaders = { overview: () => import('./views/overview.js'), knowledge: () => import('./views/knowledge.js'), prompts: () => import('./views/prompts.js'), integrations: () => import('./views/integrations.js'), costs: () => import('./views/costs.js'), activity: () => import('./views/activity.js') };
const view = document.getElementById('pview');
let token = 0; let attention = 0;

const current = () => { const n = location.hash.replace(/^#\/?/, '').split(/[/?]/)[0]; return loaders[n] ? n : 'overview'; };
const drawNav = (active) => mount(document.getElementById('sidenav'), ...TABS.map(([id, label, paths]) => h('a', { href: `#/${id}`, class: id === active ? 'on' : '', 'aria-current': id === active ? 'page' : null }, ic(paths, [], true), label, id === 'overview' && attention ? h('span', { class: 'n' }, String(attention)) : null)));

async function route() {
  const mine = ++token; const name = current(); drawNav(name);
  mount(view, h('div', { class: 'empty' }, 'Loading…'));
  try {
    const mod = await loaders[name]();
    if (mine !== token) return;
    const page = h('div', { class: 'page' }); mount(view, page);
    await mod.render(page);
    window.scrollTo(0, 0);
  } catch (err) { if (mine === token) mount(view, h('div', { class: 'card empty' }, h('p', {}, err.message || String(err)), h('button', { class: 'plain', onclick: route }, 'Try again'))); if (!err.status) console.error(err); }
}
async function live() {
  try {
    const [s, st] = await Promise.all([A('/status'), A('/stats')]);
    const modes = { reply: 'WhatsApp reply only', message: 'Taking a message', board: "Answering from Today's board" };
    mount(document.getElementById('live'), h('div', {}, h('b', {}, s.assistant_on ? 'Live in the app' : 'Assistant is off'), h('div', {}, `${modes[s.mode]} · ${st.needs_action} need you`)), h('div', { style: 'margin-top:8px' }, h('a', { href: '/assistant/', target: '_blank', rel: 'noopener' }, 'Open the app'), ' · ', h('a', { href: '/assistant/#/try', target: '_blank', rel: 'noopener' }, 'Try a call')));
  } catch { /* signed out */ }
}
window.addEventListener('hashchange', route);
window.addEventListener('portal-attention', (e) => { attention = e.detail; drawNav(current()); });
window.addEventListener('munshi-changed', live);
drawNav(current()); route(); live();
