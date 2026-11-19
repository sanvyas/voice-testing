import { h, mount, ago } from '/lab/ui.js';
import { A, getConfig, ic, ICONS, rupees, who } from '/assistant/net.js';
import { apiDownload } from '/lab/api.js';
import { choose, selectedId } from '../ctx.js';

const kpi = (label, value, sub, hot) => h('div', { class: 'kpi' + (hot ? ' hot' : '') }, h('div', { class: 'l' }, label), h('div', { class: 'v' }, value), sub ? h('div', { class: 's' }, sub) : null);

async function businessOverview(page) {
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
    h('div', { class: 'pagehead' }, h('div', {}, h('h1', { class: 'title' }, 'Overview'), h('div', { class: 'sub' }, 'What the assistant is doing for this business, and what it costs. Changes here reach their app straight away.')), h('a', { class: 'btn', style: 'width:auto', href: '/assistant/#/try', target: '_blank', rel: 'noopener' }, ic(ICONS.mic, [], true), 'Try a practice call')),
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

const LINKS = { phone: ['businesses', 'Add number'], setup: ['businesses', 'Open'], off: ['businesses', 'Open'], budget: ['costs', 'Open'], stale: ['knowledge', 'Check prices'], backlog: ['calls', 'See calls'], link: ['businesses', 'Create link'], paused: ['businesses', 'Open'] };

async function platformOverview(page) {
  const [o, p, al, rd] = await Promise.all([A('/admin/overview?days=30'), A('/admin/platform'), A('/admin/alerts'), A('/admin/readiness')]);
  const todo = [...o.attention];
  if (!p.signed_in_required) todo.push({ business_id: '', business: 'Platform', kind: 'signin', level: 'bad', text: 'Sign-in is off: anyone with this address can open the portal and every business. Set LAB_OPEN_ACCESS=false and LAB_API_TOKENS on the server.' });
  window.dispatchEvent(new CustomEvent('portal-attention', { detail: todo.length + al.open }));
  const max = Math.max(1, ...o.daily.map((d) => d.calls));
  const resolve = async (id) => { await A(`/admin/alerts/${id}/resolve`, { method: 'POST' }); location.reload(); };
  const open = al.items.filter((a) => a.open);
  const needed = rd.checks.filter((c) => !c.ok);
  mount(page,
    h('div', { class: 'pagehead' }, h('div', {}, h('h1', { class: 'title' }, 'Overview'), h('div', { class: 'sub' }, 'Every business on the platform, last 30 days.')), h('a', { class: 'btn', style: 'width:auto', href: '#/businesses' }, 'Manage businesses')),
    open.length ? h('div', { class: 'card', role: 'alert', style: 'border:2px solid var(--bad,#b3261e)' }, h('h2', { class: 'sec', style: 'margin-bottom:6px' }, `Alerts (${open.length})`),
      ...open.map((a) => h('div', { class: 'attn' }, h('span', { class: 'ico warn' }, ic(ICONS.info)), h('div', { class: 'grow' }, h('div', { class: 't' }, a.title + (a.count > 1 ? ` · ${a.count}×` : '')), h('div', { class: 'd' }, `${a.detail} (last ${ago(a.last_at)})`)), h('button', { class: 'badge act', onclick: () => resolve(a.id) }, 'Dismiss'))),
      al.webhook ? null : h('div', { class: 'small muted', style: 'margin-top:8px' }, 'Nobody is told about these yet. Set ALERT_WEBHOOK_URL on the server to get them in Slack or Discord.')) : null,
    h('div', { class: 'card' }, h('div', { class: 'row between' }, h('h2', { class: 'sec', style: 'margin-bottom:6px' }, rd.ready ? 'Ready for real customers' : `Launch checklist: ${needed.filter((c) => c.level === 'required').length} required, ${needed.filter((c) => c.level !== 'required').length} recommended still open`),
      h('button', { class: 'small', style: 'color:var(--primary);font-weight:600;background:none;border:0;cursor:pointer', onclick: () => apiDownload('/api/assistant/admin/backup', 'munshi-backup.json.gz').catch((e) => alert(e.message)) }, 'Download backup')),
      h('div', {}, ...rd.checks.map((c) => h('div', { class: 'attn' }, h('span', { class: 'ico ' + (c.ok ? '' : 'warn') }, ic(c.ok ? ICONS.check : ICONS.info)), h('div', { class: 'grow' }, h('div', { class: 't' }, c.title + (!c.ok && c.level !== 'required' ? ' (recommended)' : '')), h('div', { class: 'd' }, c.ok ? c.detail : `${c.detail} ${c.fix}`)))))),
    h('div', { class: 'kpis' }, kpi('Businesses', String(o.businesses), `${o.active} active`), kpi('Calls answered', String(o.calls), 'by the assistant'), kpi('Waiting for owners', String(o.needs_action), o.needs_action ? 'across all businesses' : 'all clear', o.needs_action > 0),
      kpi('Spend', rupees(o.cost) || 'Rs 0', o.per_call ? `${rupees(o.per_call)} per call` : 'no calls yet')),
    h('div', { class: 'grid2' },
      h('div', { class: 'card' }, h('h2', { class: 'sec', style: 'margin-bottom:6px' }, todo.length ? `Needs attention (${todo.length})` : 'Nothing needs attention'),
        todo.length ? h('div', {}, ...todo.slice(0, 12).map((n) => { const [route, cta] = LINKS[n.kind] || ['businesses', 'Open'];
          return h('div', { class: 'attn' }, h('span', { class: 'ico ' + (n.level === 'info' ? '' : 'warn') }, ic(ICONS.info)), h('div', { class: 'grow' }, h('div', { class: 't' }, n.business), h('div', { class: 'd' }, n.text)),
            n.kind === 'signin' ? null : h('button', { class: 'badge act', onclick: () => { choose(n.business_id); location.hash = `#/${route}`; } }, cta)); })) : h('div', { class: 'muted' }, 'Every business is set up, prices are fresh and spend is on track.')),
      h('div', { class: 'stack' },
        h('div', { class: 'card stack' }, h('h2', { class: 'sec' }, 'Calls per day'), o.daily.length ? h('div', { class: 'chart', role: 'img', 'aria-label': 'Calls per day' }, ...o.daily.map((d) => h('div', { class: 'col', title: `${d.date}: ${d.calls} calls · ${rupees(d.cost)}`, style: `height:${Math.max(4, d.calls / max * 100)}%` }))) : h('div', { class: 'muted' }, 'No calls yet.')),
        h('div', { class: 'card stack' }, h('h2', { class: 'sec' }, 'Busiest businesses'), o.top.length ? h('div', {}, ...o.top.map((t) => h('div', { class: 'hist' }, h('b', {}, t.name), h('span', { class: 'small muted' }, `${t.calls} calls · ${rupees(t.cost) || 'Rs 0'}`)))) : h('div', { class: 'muted' }, 'Nothing yet.')))),
    h('div', { class: 'card' }, h('div', { class: 'row between' }, h('h2', { class: 'sec' }, 'Latest calls'), h('a', { href: '#/calls', class: 'small', style: 'color:var(--primary);font-weight:600' }, 'All calls')),
      o.recent.length ? h('div', {}, ...o.recent.map((c) => h('div', { class: 'hist' }, h('div', {}, h('b', {}, who(c)), h('div', { class: 'small muted' }, `${c.business} · ${c.summary || 'No summary'}`)), h('span', { class: 'small muted', style: 'white-space:nowrap' }, ago(c.started_at))))) : h('div', { class: 'muted' }, 'No calls yet.')));
}

export async function render(page) {
  const list = (await A('/admin/businesses')).items;
  if (selectedId() && list.some((b) => b.id === selectedId())) return businessOverview(page);
  return platformOverview(page);
}
