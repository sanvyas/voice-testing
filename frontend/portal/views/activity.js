import { h, mount, ago } from '/lab/ui.js';
import { A } from '/assistant/net.js';
import { selectedId } from '../ctx.js';

const AREAS = [['', 'Everything'], ['business', 'Business'], ['board', 'Board'], ['prompts', 'Prompts'], ['integrations', 'Connections'], ['budget', 'Budget'], ['system', 'System']];

export async function render(page) {
  let area = '';
  const list = h('div', { class: 'card timeline' }); const pills = h('div', { class: 'pills' });
  const draw = async () => {
    mount(pills, ...AREAS.map(([id, l]) => h('button', { class: 'pill' + (area === id ? ' on' : ''), onclick: () => { area = id; draw(); } }, l)));
    const all = !selectedId();
    const rows = await A(`/activity?limit=100${area ? `&area=${area}` : ''}${all ? '&all=true' : ''}`);
    mount(list, ...(rows.length ? rows.map((a) => h('div', { class: 'row' }, h('span', { class: 'badge', style: 'min-width:92px;text-align:center' }, a.area), h('div', { class: 'grow' }, all ? h('b', {}, a.business + ': ') : null, a.summary), h('span', { class: 'small muted', style: 'white-space:nowrap' }, `${ago(a.at)} · ${new Date(a.at).toLocaleString()}`))) : [h('div', { class: 'empty' }, 'Nothing here yet.')]));
  };
  mount(page, h('div', {}, h('h1', { class: 'title' }, 'Activity'), h('div', { class: 'sub' }, 'Every change, newest first. Pick a business at the top left to see only its changes.')), pills, list);
  await draw();
}
