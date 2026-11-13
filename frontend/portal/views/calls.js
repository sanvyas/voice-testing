import { h, mount, dialog, ago } from '/lab/ui.js';
import { A, who, durationText, rupees } from '/assistant/net.js';
import { businessList, selectedId } from '../ctx.js';

const TABS = [['action', 'Need the owner'], ['all', 'All calls'], ['ignore', 'Not worth it']];

export async function render(page) {
  const list = await businessList();
  let tab = 'action'; let biz = selectedId(); let q = ''; let offset = 0; let total = 0;
  const pills = h('div', { class: 'pills' }); const rows = h('div', { class: 'card' }); const more = h('div', {});
  const pick = h('select', { 'aria-label': 'Business', style: 'width:auto;min-width:220px', onchange: (e) => { biz = e.target.value; reload(); } }, h('option', { value: '' }, 'All businesses'), ...list.map((b) => h('option', { value: b.id, selected: b.id === biz }, b.name)));
  const search = h('input', { type: 'search', placeholder: 'Search caller or summary', 'aria-label': 'Search calls', style: 'max-width:300px', oninput: () => { q = search.value.trim(); clearTimeout(search.t); search.t = setTimeout(reload, 300); } });
  mount(page, h('div', {}, h('h1', { class: 'title' }, 'Calls'), h('div', { class: 'sub' }, 'Every call the assistant answered, across the platform. Click one to read it.')), h('div', { class: 'row' }, pick, search), pills, rows, more);
  const drawPills = () => mount(pills, ...TABS.map(([id, l]) => h('button', { class: 'pill' + (tab === id ? ' on' : ''), onclick: () => { tab = id; reload(); } }, l)));
  async function fetchPage() {
    const qs = new URLSearchParams({ limit: '40', offset: String(offset) });
    if (biz) qs.set('business', biz); if (q) qs.set('q', q);
    if (tab === 'action') qs.set('open_only', 'true'); else if (tab === 'ignore') qs.set('importance', 'ignore');
    return A(`/admin/calls?${qs}`);
  }
  const row = (c) => h('div', { class: 'crow', role: 'button', tabindex: '0', onclick: () => open(c), onkeydown: (e) => { if (e.key === 'Enter') open(c); } },
    h('div', {}, h('div', { style: 'font-weight:700' }, who(c)), h('div', { class: 'small muted' }, c.business)), h('div', {}, c.summary || 'No summary', c.open_actions ? h('span', { class: 'badge act', style: 'margin-left:8px' }, `${c.open_actions} to do`) : null),
    h('div', { class: 'small muted' }, durationText(c.duration_s) || '—'), h('div', { class: 'small muted' }, ago(c.started_at)));
  async function reload() {
    offset = 0; drawPills();
    const r = await fetchPage(); total = r.total;
    mount(rows, ...(r.items.length ? r.items.map(row) : [h('div', { class: 'empty' }, tab === 'action' ? 'Nothing is waiting for an owner.' : 'No calls here.')]));
    offset = r.items.length; drawMore();
  }
  function drawMore() { mount(more, offset < total ? h('button', { class: 'plain', onclick: async () => { const r = await fetchPage(); r.items.forEach((c) => rows.append(row(c))); offset += r.items.length; drawMore(); } }, `Show more (${total - offset} left)`) : h('div', { class: 'small muted' }, total ? `${total} call${total > 1 ? 's' : ''}` : '')); }

  async function open(summary) {
    const c = await A(`/admin/calls/${summary.id}`);
    dialog(`${who(c)} · ${c.business}`, h('div', { class: 'stack' },
      h('div', { class: 'small muted' }, [c.source === 'test' ? 'Practice call' : 'Phone call', ago(c.started_at), durationText(c.duration_s), c.language, c.cost && c.cost.total !== undefined ? `cost ${rupees(c.cost.total)}` : ''].filter(Boolean).join(' · ')),
      h('div', { style: 'font-size:17px;font-weight:600;line-height:1.4' }, c.summary || 'No summary.'),
      c.action_items.length ? h('div', {}, h('div', { class: 'small', style: 'font-weight:700;margin-bottom:4px' }, 'To do'), ...c.action_items.map((a) => h('div', { class: 'small', style: a.done ? 'text-decoration:line-through;color:var(--muted)' : '' }, `${a.done ? '✓' : '•'} ${a.text}`))) : null,
      c.summary_error ? h('div', { class: 'notice bad' }, c.summary_error) : null,
      h('div', { class: 'small', style: 'font-weight:700' }, 'Conversation'),
      h('div', { class: 'stack', style: 'gap:8px;max-height:320px;overflow:auto' }, ...c.turns.map((t) => h('div', { class: 'small', style: `padding:8px 12px;border-radius:12px;background:${t.role === 'assistant' ? 'var(--soft)' : '#E4F5EE'}` }, h('b', {}, t.role === 'assistant' ? 'Assistant: ' : 'Caller: '), t.content))),
      c.notes.length ? h('div', {}, h('div', { class: 'small', style: 'font-weight:700' }, 'Owner’s notes'), ...c.notes.map((n) => h('div', { class: 'small' }, `• ${n.body}`))) : null));
  }

  await reload();
}
