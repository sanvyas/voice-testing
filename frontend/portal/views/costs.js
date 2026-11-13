import { h, mount, toast, ago } from '/lab/ui.js';
import { A, rupees } from '/assistant/net.js';
import { choose, selectedId } from '../ctx.js';

const COLORS = { phone: '#0B7A5B', voice: '#7C5CE0', ai: '#E8590C', speech_to_text: '#2F8FD8', whatsapp: '#C2A100' };

async function businessCosts(page) {
  let days = 30;
  const body = h('div', { class: 'stack', style: 'gap:18px' });
  const draw = async () => {
    const c = await A(`/costs?days=${days}`);
    const m = c.month; const max = Math.max(1, ...c.daily.map((d) => d.total));
    const cap = h('input', { type: 'text', inputmode: 'numeric', value: m.budget || '', placeholder: 'e.g. 1500', 'aria-label': 'Monthly budget in rupees', style: 'max-width:180px' });
    const hard = h('input', { type: 'checkbox', class: 'sw', role: 'switch', checked: m.hard_stop, 'aria-label': 'Stop AI answers when the budget is used up' });
    const save = h('button', { class: 'btn', style: 'width:auto' }, 'Save budget');
    save.addEventListener('click', async () => { save.disabled = true; try { await A('/budget', { method: 'PUT', body: { monthly_inr: parseInt(cap.value || '0', 10) || 0, hard_stop: hard.checked } }); toast('Budget saved'); draw(); } catch (e) { toast(e.message, true); save.disabled = false; } });
    mount(body,
      h('div', { class: 'kpis' }, ...[['Spend this month', rupees(m.spend) || 'Rs 0', `projected ${rupees(m.projected) || 'Rs 0'} by month end`], [`Spend, last ${days} days`, rupees(c.total) || 'Rs 0', `${c.priced_calls} priced call${c.priced_calls === 1 ? '' : 's'}`], ['Average per call', c.per_call ? rupees(c.per_call) : '—', ''], ['Average per minute', c.per_minute ? rupees(c.per_minute) : '—', '']].map(([l, v, s]) => h('div', { class: 'kpi' }, h('div', { class: 'l' }, l), h('div', { class: 'v' }, v), s ? h('div', { class: 's' }, s) : null))),
      h('div', { class: 'grid2' },
        h('div', { class: 'card stack' }, h('h2', { class: 'sec' }, 'Where the money goes'), c.total ? h('div', { class: 'bar thick' }, ...c.parts.filter((p) => p.amount > 0).map((p) => h('i', { style: `width:${p.share * 100}%;background:${COLORS[p.id]}`, title: `${p.label}: ${rupees(p.amount)}` }))) : h('div', { class: 'muted' }, 'No priced calls in this period yet.'),
          h('div', { class: 'legend' }, ...c.parts.map((p) => h('span', {}, h('i', { style: `background:${COLORS[p.id]}` }), `${p.label} ${rupees(p.amount) || 'Rs 0'}${p.share ? ` (${Math.round(p.share * 100)}%)` : ''}`))),
          h('div', { class: 'small muted' }, c.note)),
        h('div', { class: 'card stack' }, h('h2', { class: 'sec' }, 'Monthly budget'),
          m.budget ? h('div', {}, h('div', { class: 'bar thick' }, h('i', { style: `width:${Math.min(100, (m.used || 0) * 100)}%;background:${(m.used || 0) >= 1 ? 'var(--danger)' : (m.used || 0) >= 0.8 ? 'var(--warn)' : 'var(--primary)'}` })), h('div', { class: 'small muted', style: 'margin-top:6px' }, `${rupees(m.spend) || 'Rs 0'} of Rs ${m.budget.toLocaleString()} used (${Math.round((m.used || 0) * 100)}%)`)) : h('div', { class: 'small muted' }, 'No budget set. Add one to get a warning on the Overview page.'),
          h('div', { class: 'row' }, h('span', { class: 'small' }, 'Rs'), cap, save),
          h('label', { class: 'row between', style: 'font-weight:600;font-size:14px;flex-wrap:nowrap' }, h('span', {}, 'Stop AI answers when it is used up', h('div', { class: 'small muted', style: 'font-weight:400' }, 'Callers then hear a polite “not available”. Their number still appears in your log.')), hard))),
      h('div', { class: 'card stack' }, h('div', { class: 'row between' }, h('h2', { class: 'sec' }, 'Spend by day'), h('div', { class: 'pills' }, ...[7, 30, 90].map((d) => h('button', { class: 'pill' + (days === d ? ' on' : ''), onclick: () => { days = d; draw(); } }, `${d} days`)))),
        c.daily.length ? h('div', { class: 'chart', role: 'img', 'aria-label': 'Spend by day in rupees' }, ...c.daily.map((d) => h('div', { class: 'col', title: `${d.date}: ${rupees(d.total)} · ${d.calls} call${d.calls > 1 ? 's' : ''}`, style: `height:${Math.max(4, d.total / max * 100)}%` }))) : h('div', { class: 'muted' }, 'No calls in this period.')),
      h('div', { class: 'grid2' },
        h('div', { class: 'card stack' }, h('h2', { class: 'sec' }, 'Most expensive calls'), c.top_calls.length ? h('table', { class: 'tbl' }, h('tbody', {}, ...c.top_calls.map((t) => h('tr', {}, h('td', {}, h('a', { href: `/assistant/#/calls/${t.id}`, target: '_blank', rel: 'noopener', style: 'color:var(--primary);font-weight:600' }, t.caller)), h('td', { class: 'small muted' }, ago(t.at)), h('td', { style: 'text-align:right;font-weight:600' }, rupees(t.total)))))) : h('div', { class: 'muted' }, 'None yet.')),
        h('div', { class: 'card stack' }, h('h2', { class: 'sec' }, 'Voice usage this month'), h('table', { class: 'tbl' }, h('thead', {}, h('tr', {}, h('th', {}, 'Voice'), h('th', {}, 'Characters'), h('th', {}, 'Estimate'))), h('tbody', {}, ...c.voice_usage.map((v) => h('tr', {}, h('td', {}, v.label), h('td', {}, `${v.chars.toLocaleString()} / ${v.limit.toLocaleString()}`), h('td', {}, v.reported_usd ? `$${v.reported_usd.toFixed(4)} billed` : `$${v.estimated_usd.toFixed(4)}`)))))),
        ),
      h('div', { class: 'card stack' }, h('h2', { class: 'sec' }, 'Prices these estimates use'), h('table', { class: 'tbl' }, h('tbody', {}, ...c.unit_prices.map((u) => h('tr', {}, h('td', { style: 'font-weight:600;width:42%' }, u.item), h('td', { class: 'muted' }, u.price))))), h('div', { class: 'small muted' }, 'Read from each vendor’s public price page. They can change.')));
  };
  mount(page, h('div', {}, h('h1', { class: 'title' }, 'Costs'), h('div', { class: 'sub' }, 'What each call costs, where it goes, and a budget so nothing surprises you.')), body);
  await draw();
}

async function platformCosts(page) {
  let days = 30;
  const body = h('div', { class: 'stack', style: 'gap:18px' });
  const draw = async () => {
    const c = await A(`/admin/costs?days=${days}`);
    const max = Math.max(1, ...c.daily.map((d) => d.total));
    mount(body,
      h('div', { class: 'kpis' }, ...[[`Spend, last ${days} days`, rupees(c.total) || 'Rs 0', `${c.calls} priced call${c.calls === 1 ? '' : 's'}`], ['Average per call', c.per_call ? rupees(c.per_call) : '—', ''], ['Call minutes', String(c.minutes), ''], ['Businesses with spend', String(c.businesses.length), '']].map(([l, v, s]) => h('div', { class: 'kpi' }, h('div', { class: 'l' }, l), h('div', { class: 'v' }, v), s ? h('div', { class: 's' }, s) : null))),
      h('div', { class: 'card stack' }, h('div', { class: 'row between' }, h('h2', { class: 'sec' }, 'By business'), h('div', { class: 'pills' }, ...[7, 30, 90].map((d) => h('button', { class: 'pill' + (days === d ? ' on' : ''), onclick: () => { days = d; draw(); } }, `${d} days`)))),
        c.businesses.length ? h('table', { class: 'tbl' }, h('thead', {}, h('tr', {}, h('th', {}, 'Business'), h('th', {}, 'Calls'), h('th', {}, 'Phone'), h('th', {}, 'AI + speech'), h('th', {}, 'Voice'), h('th', {}, 'WhatsApp'), h('th', {}, 'Per call'), h('th', { style: 'text-align:right' }, 'Total'))),
          h('tbody', {}, ...c.businesses.map((b) => h('tr', {}, h('td', {}, h('button', { class: 'link', style: 'font-weight:700', onclick: () => choose(b.id) }, b.name)), h('td', {}, String(b.calls)), h('td', {}, rupees(b.phone) || '—'), h('td', {}, rupees(b.ai + b.speech_to_text) || '—'), h('td', {}, rupees(b.voice) || '—'), h('td', {}, rupees(b.whatsapp) || '—'), h('td', {}, rupees(b.per_call) || '—'), h('td', { style: 'text-align:right;font-weight:700' }, rupees(b.total)))))) : h('div', { class: 'muted' }, 'No priced calls in this period yet.'),
        h('div', { class: 'small muted' }, 'Choose a business to set its monthly budget.')),
      h('div', { class: 'grid2' },
        h('div', { class: 'card stack' }, h('h2', { class: 'sec' }, 'Where the money goes'), c.total ? h('div', { class: 'bar thick' }, ...c.parts.filter((p) => p.amount > 0).map((p) => h('i', { style: `width:${p.share * 100}%;background:${COLORS[p.id]}`, title: `${p.label}: ${rupees(p.amount)}` }))) : h('div', { class: 'muted' }, 'Nothing yet.'),
          h('div', { class: 'legend' }, ...c.parts.map((p) => h('span', {}, h('i', { style: `background:${COLORS[p.id]}` }), `${p.label} ${rupees(p.amount) || 'Rs 0'}${p.share ? ` (${Math.round(p.share * 100)}%)` : ''}`))), h('div', { class: 'small muted' }, c.note)),
        h('div', { class: 'card stack' }, h('h2', { class: 'sec' }, 'Spend by day'), c.daily.length ? h('div', { class: 'chart', role: 'img', 'aria-label': 'Spend by day in rupees' }, ...c.daily.map((d) => h('div', { class: 'col', title: `${d.date}: ${rupees(d.total)} · ${d.calls} call${d.calls > 1 ? 's' : ''}`, style: `height:${Math.max(4, d.total / max * 100)}%` }))) : h('div', { class: 'muted' }, 'No calls in this period.'))),
      h('div', { class: 'card stack' }, h('h2', { class: 'sec' }, 'Prices used for the estimate'), h('table', { class: 'tbl' }, h('tbody', {}, ...c.unit_prices.map((u) => h('tr', {}, h('td', {}, u.item), h('td', { class: 'muted' }, u.price)))))));
  };
  mount(page, h('div', {}, h('h1', { class: 'title' }, 'Costs'), h('div', { class: 'sub' }, 'What the assistant costs across all businesses, in rupees. Estimated from published list prices.')), body);
  await draw();
}

export async function render(page) {
  const list = (await A('/admin/businesses')).items;
  return selectedId() && list.some((b) => b.id === selectedId()) ? businessCosts(page) : platformCosts(page);
}
