import { h, mount, ago } from '/lab/ui.js';
import { A, getConfig, ic, ICONS, rupees } from '/assistant/net.js';

const kpi = (label, value, sub, hot) => h('div', { class: 'kpi' + (hot ? ' hot' : '') }, h('div', { class: 'l' }, label), h('div', { class: 'v' }, value), sub ? h('div', { class: 's' }, sub) : null);

export async function render(page) {
  const [costs, stats, status, integ, board, asked, activity, cfg] = await Promise.all([A('/costs?days=30'), A('/stats'), A('/status'), A('/integrations'), A('/board'), A('/board/asked'), A('/activity?limit=6'), getConfig()]);
  const m = costs.month;
  const todo = [];
  if (!status.assistant_on) todo.push(['Assistant is switched off', 'Nobody is answered by the AI.', '/assistant/#/setup', 'Turn on']);
  for (const i of integ) if (!i.connected && ['ai', 'phone', 'whatsapp', 'vision'].includes(i.id)) todo.push([`${i.name} is not connected`, i.what, '#/integrations', 'Connect']);
  for (const i of integ) if (i.last_check && !i.last_check.ok) todo.push([`${i.name} failed its last test`, i.last_check.message, '#/integrations', 'Look']);
  if (board.stale) todo.push([`${board.stale} price${board.stale > 1 ? 's' : ''} out of date`, 'The assistant treats them as “ask me” until you check.', '#/knowledge', 'Check']);
  if (asked.length) todo.push([`Callers asked about ${asked.length} item${asked.length > 1 ? 's' : ''} you have not priced`, asked.slice(0, 3).map((a) => a.term).join(', '), '#/knowledge', 'Add prices']);
  if (m.used !== null && m.used >= 0.8) todo.push([`${Math.round(m.used * 100)}% of this month's budget is used`, m.hard_stop ? 'The AI stops answering when it is used up.' : 'Raise the budget or turn on a hard stop.', '#/costs', 'Open']);
  if (cfg.open_access || !cfg.auth_required) todo.push(['Anyone with the link can see your calls', 'Fine for testing. Turn on sign-in before real customers call.', '#/integrations', 'How']);
  window.dispatchEvent(new CustomEvent('portal-attention', { detail: todo.length }));
  const max = Math.max(1, ...costs.daily.map((d) => d.total));
  mount(page,
    h('div', { class: 'pagehead' }, h('div', {}, h('h1', { class: 'title' }, 'Overview'), h('div', { class: 'sub' }, 'Everything the assistant is doing, and what it costs. Changes here reach the app straight away.')), h('a', { class: 'btn', style: 'width:auto', href: '/assistant/#/try', target: '_blank', rel: 'noopener' }, ic(ICONS.mic, [], true), 'Try a practice call')),
    h('div', { class: 'kpis' }, kpi('Calls, last 30 days', String(costs.calls), `${costs.minutes} minutes`), kpi('Need you now', String(stats.needs_action), stats.needs_action ? 'waiting for a reply' : 'all clear', stats.needs_action > 0),
      kpi('Spend this month', rupees(m.spend) || 'Rs 0', m.budget ? `of Rs ${m.budget.toLocaleString()} budget` : `projected ${rupees(m.projected) || 'Rs 0'}`), kpi('Average per call', costs.per_call ? rupees(costs.per_call) : '—', costs.per_minute ? `${rupees(costs.per_minute)} per minute` : 'no calls yet')),
    h('div', { class: 'grid2' },
      h('div', { class: 'card' }, h('h2', { class: 'sec', style: 'margin-bottom:6px' }, todo.length ? `Needs attention (${todo.length})` : 'Nothing needs attention'),
        todo.length ? h('div', {}, ...todo.map(([t, d, href, cta]) => h('div', { class: 'attn' }, h('span', { class: 'ico warn' }, ic(ICONS.info)), h('div', { class: 'grow' }, h('div', { class: 't' }, t), h('div', { class: 'd' }, d)), h('a', { class: 'badge act', href }, cta)))) : h('div', { class: 'muted' }, 'Connections work, prices are fresh and spend is on track.')),
      h('div', { class: 'card stack' }, h('h2', { class: 'sec' }, 'Daily spend'), costs.daily.length ? h('div', { class: 'chart', role: 'img', 'aria-label': 'Daily spend in rupees' }, ...costs.daily.map((d) => h('div', { class: 'col', title: `${d.date}: ${rupees(d.total)} · ${d.calls} call${d.calls > 1 ? 's' : ''}`, style: `height:${Math.max(4, d.total / max * 100)}%` }))) : h('div', { class: 'muted' }, 'No calls yet.'),
        h('a', { href: '#/costs', class: 'small', style: 'color:var(--primary);font-weight:600' }, 'Open costs'))),
    h('div', { class: 'card' }, h('div', { class: 'row between' }, h('h2', { class: 'sec' }, 'Recent changes'), h('a', { href: '#/activity', class: 'small', style: 'color:var(--primary);font-weight:600' }, 'All activity')),
      activity.length ? h('div', { class: 'timeline' }, ...activity.map((a) => h('div', { class: 'row' }, h('span', { class: 'badge' }, a.area), h('div', { class: 'grow' }, a.summary), h('span', { class: 'small muted', style: 'white-space:nowrap' }, ago(a.at))))) : h('div', { class: 'muted' }, 'Nothing has changed yet.')));
}
