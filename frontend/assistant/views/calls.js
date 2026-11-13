import { h, mount, toast, ask, ago } from '/lab/ui.js';
import { notesPanel } from '/lab/components.js';
import { A, ic, ICONS, durationText, who, rupees, initials, avatarClass } from '../net.js';

const greeting = () => { const hr = new Date().getHours(); return hr < 12 ? 'Good morning' : hr < 17 ? 'Good afternoon' : 'Good evening'; };
const changed = () => window.dispatchEvent(new Event('munshi-changed'));

export async function render(root, { params }) {
  return params[0] ? detail(root, params[0]) : list(root);
}

async function list(root) {
  const [stats, status, profile, all] = await Promise.all([A('/stats'), A('/status'), A('/profile'), A('/calls?limit=100')]);
  let tab = stats.needs_action ? 'action' : 'all';
  const rows = h('div', { class: 'stack', style: 'gap:10px' });
  const pills = h('div', { class: 'pills' });
  const draw = () => {
    mount(pills, ...[['action', `Needs you${stats.needs_action ? ` ${stats.needs_action}` : ''}`], ['all', 'All calls'], ['ignore', 'Not worth it']].map(([id, l]) => h('button', { class: 'pill' + (tab === id ? ' on' : ''), onclick: () => { tab = id; draw(); } }, l)));
    const shown = all.items.filter((c) => (tab === 'all' ? true : tab === 'action' ? c.importance === 'action' && !c.reviewed : c.importance === tab));
    mount(rows, ...(shown.length ? shown.map(card) : [h('div', { class: 'card empty' }, all.items.length ? (tab === 'action' ? 'Nothing needs you. Nice.' : 'Nothing here.') : 'No calls yet. Make a practice call to see how it works.')]));
  };
  const steps = [
    [status.profile_ready, 'Describe your business', 'Your name, what you sell', '#/setup'],
    [all.total > 0, 'Make a practice call', 'Play a customer, see the summary', '#/try'],
  ];
  const first = steps.findIndex(([done]) => !done);
  const demo = h('button', { class: 'btn ghost', onclick: async () => { try { await A('/demo', { method: 'POST' }); toast('Sample shop added'); location.hash = '#/try'; location.reload(); } catch (e) { toast(e.message, true); } } }, 'Try with a sample shop');
  const board = status.board;
  mount(root,
    h('div', { class: 'row between', style: 'flex-wrap:nowrap' },
      h('div', {}, h('div', { class: 'small muted' }, greeting()), h('h1', { class: 'title' }, profile.owner_name || 'Welcome')),
      h('a', { href: '#/setup', class: 'power' + (profile.assistant_on ? '' : ' off') }, h('i', {}), profile.assistant_on ? 'Assistant on' : 'Assistant off')),
    first >= 0 ? h('div', { class: 'card stack' }, h('h2', { class: 'sec' }, 'Get started'),
      h('div', {}, ...steps.map(([done, t, d, href], i) => h('a', { href, class: 'rowlink', style: 'padding:0' }, h('span', { class: 'avatar sm ' + (done ? 'a1' : i === first ? 'a0' : 'a2') }, done ? ic(ICONS.check, [], true) : String(i + 1)), h('div', { class: 'grow' }, h('div', { class: 't' }, t), h('div', { class: 'd' }, d)), i === first ? h('span', { class: 'badge act' }, 'Next') : null))),
      !status.profile_ready ? demo : null) : null,
    h('div', { class: 'hero' }, h('div', { class: 'row between', style: 'align-items:flex-end;flex-wrap:nowrap' }, h('div', {}, h('div', { class: 'k' }, 'Needs you'), h('div', { class: 'n' }, String(stats.needs_action))), h('div', { class: 't' }, stats.needs_action === 1 ? 'call is waiting for your reply' : 'calls are waiting for your reply')),
      h('hr'), h('div', { class: 'stats' }, h('span', {}, h('b', {}, String(stats.answered_7d)), ' answered this week'), h('span', {}, h('b', {}, String(stats.not_worth_time_7d)), ' not worth your time'))),
    pills, rows,
    h('a', { href: '#/board', class: 'linkcard' }, h('span', { class: 'ico' }, ic(ICONS.board)), h('div', { class: 'grow' }, h('div', { style: 'font-weight:600' }, "Today's board"), h('div', { class: 'small muted' }, board.items ? `${board.items} item${board.items > 1 ? 's' : ''}${board.sold_out ? ` · ${board.sold_out} sold out` : ''}` : 'Set up prices and stock the assistant may share')), ic(ICONS.next, [], true)));
  draw();
}

function card(c) {
  const name = who(c);
  const acting = c.importance === 'action' && !c.reviewed;
  return h('a', { href: `#/calls/${c.id}`, class: 'callcard' }, h('span', { class: `avatar ${avatarClass(name)}` }, initials(c.caller_name) === '?' ? '?' : initials(c.caller_name)),
    h('div', { class: 'grow' }, h('div', { class: 'top' }, h('span', { class: 'nm' }, name), h('span', { class: 'tm' }, ago(c.started_at))), h('div', { class: 'sm' }, c.summary || '…'),
      h('div', { class: 'tags' }, acting && c.open_actions ? h('span', { class: 'badge act' }, `${c.open_actions} to do`) : null, c.category ? h('span', { class: 'badge' }, c.category) : null, c.importance === 'action' && c.reviewed ? h('span', { class: 'badge ok' }, 'Done') : null,
        c.source === 'test' ? h('span', { class: 'badge' }, 'practice') : null, c.note_count ? h('span', { class: 'badge' }, `${c.note_count} note${c.note_count > 1 ? 's' : ''}`) : null)));
}

async function detail(root, id) {
  const [c, status] = await Promise.all([A(`/calls/${id}`), A('/status')]);
  const admin = status.role === 'admin';  // what a call cost is for the platform, not for the business
  const name = who(c);
  const items = c.action_items;
  const todo = h('div', {});
  const drawTodo = () => mount(todo, ...items.map((a) => h('label', { class: 'todo' + (a.done ? ' done' : '') },
    h('input', { type: 'checkbox', class: 'ck', checked: a.done, onchange: async (e) => { try { const r = await A(`/calls/${id}/actions/${a.id}`, { method: 'PUT', body: { done: e.target.checked } }); a.done = e.target.checked; drawTodo(); changed(); if (r.reviewed) toast('All done. Moved off your list.'); } catch (err) { toast(err.message, true); e.target.checked = a.done; } } }), h('span', {}, a.text))));
  drawTodo();
  const dealt = h('input', { type: 'checkbox', class: 'sw', role: 'switch', checked: c.reviewed, 'aria-label': 'I have dealt with this', onchange: async (e) => { try { await A(`/calls/${id}`, { method: 'PUT', body: { reviewed: e.target.checked } }); changed(); toast(e.target.checked ? 'Marked as dealt with' : 'Back on your list'); } catch (err) { toast(err.message, true); } } });
  const label = c.importance === 'action' ? ['Needs you', 'act'] : c.importance === 'ignore' ? ['Not worth your time', ''] : ['Good to know', 'ok'];
  const wa = c.whatsapp;
  mount(root,
    h('a', { href: '#/calls', class: 'back' }, ic(ICONS.back), 'Calls'),
    h('div', { class: 'row', style: 'gap:14px;flex-wrap:nowrap' }, h('span', { class: `avatar lg ${avatarClass(name)}` }, initials(c.caller_name)),
      h('div', {}, h('h1', { class: 'title', style: 'font-size:26px' }, name), h('div', { class: 'small muted', style: 'margin-top:2px' }, [c.source === 'test' ? 'Practice call' : 'Phone call', ago(c.started_at), durationText(c.duration_s), c.language].filter(Boolean).join(' · ')))),
    h('div', { class: 'card stack' },
      h('div', { class: 'row', style: 'gap:6px' }, h('span', { class: 'badge ' + label[1] }, label[0]), c.category ? h('span', { class: 'badge' }, c.category) : null),
      h('div', { style: 'font-size:17px;font-weight:600;line-height:1.4' }, c.summary || 'No summary.'),
      c.summary_error ? h('div', { class: 'notice' }, c.summary_error) : null,
      wa ? h('div', { class: 'wa', style: wa.sent ? '' : 'background:var(--warn-soft);color:var(--warn-ink)' }, ic(ICONS.chat, [], true), h('div', {}, wa.sent ? [h('b', {}, 'Instant reply sent on WhatsApp: '), 'the caller got your address, hours and board before you saw this.'] : [h('b', {}, 'WhatsApp reply not sent: '), wa.error || 'not connected'])) : null,
      c.callback_number && c.handled_by === 'assistant' ? h('a', { class: 'btn lg', href: `tel:${c.callback_number}` }, ic(ICONS.phone), `Call back ${c.callback_number}`) : null,
      c.importance !== 'ignore' ? h('label', { class: 'row between', style: 'min-height:44px;font-weight:600;font-size:15px' }, 'I have dealt with this', dealt) : null),
    items.length ? h('div', { class: 'card' }, h('h2', { class: 'sec', style: 'margin-bottom:6px' }, 'To do'), todo) : null,
    c.turns.length ? h('div', { class: 'card stack' }, h('h2', { class: 'sec' }, 'What was said'), h('div', { class: 'chat' }, ...c.turns.map((t) => h('div', { class: 'bubble ' + (t.role === 'assistant' ? 'assistant' : 'caller') }, t.content)))) : null,
    h('div', { class: 'card stack' }, h('h2', { class: 'sec' }, 'Your notes'), h('div', { class: 'small muted' }, 'Write down what you noticed: was it right, what should change.'),
      notesPanel(id, c.notes, { urls: { add: `/api/assistant/calls/${id}/notes`, item: (nid) => `/api/assistant/call-notes/${nid}` } })),
    admin && c.cost && c.cost.total !== undefined ? h('div', { class: 'small muted', style: 'text-align:center;line-height:1.5' }, `Estimated cost of this call: ${rupees(c.cost.total)} (phone ${rupees(c.cost.phone)}, voice ${rupees(c.cost.voice)}, AI ${rupees(c.cost.ai + c.cost.speech_to_text)}${c.cost.whatsapp ? `, WhatsApp ${rupees(c.cost.whatsapp)}` : ''})`) : null,
    h('div', { style: 'text-align:center' }, h('button', { class: 'link danger', onclick: async () => { if (await ask('Delete this call and its notes?', { yes: 'Delete', danger: true })) { await A(`/calls/${id}`, { method: 'DELETE' }); changed(); location.hash = '#/calls'; } } }, 'Delete this call')));
}
