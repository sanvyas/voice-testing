import { h, mount, toast, ask, ago } from '/lab/ui.js';
import { notesPanel } from '/lab/components.js';
import { A, IMPORTANCE, durationText, who, rupees } from '../net.js';

export async function render(root, { params }) {
  return params[0] ? detail(root, params[0]) : list(root);
}

async function list(root) {
  const [stats, status, profile, all] = await Promise.all([A('/stats'), A('/status'), A('/profile'), A('/calls?limit=100')]);
  let tab = stats.needs_action ? 'action' : 'all';
  const rows = h('div', { class: 'stack', style: 'gap:10px' });
  const chips = h('div', { class: 'chips' });
  const draw = () => {
    mount(chips, ...[['action', 'Needs you'], ['all', 'All calls'], ['ignore', 'Not worth your time']].map(([id, l]) => h('span', { class: 'chip plain' + (tab === id ? ' on' : ''), role: 'button', onclick: () => { tab = id; draw(); } }, l)));
    const shown = all.items.filter((c) => (tab === 'all' ? true : tab === 'action' ? c.importance === 'action' && !c.reviewed : c.importance === tab));
    mount(rows, ...(shown.length ? shown.map(row) : [h('div', { class: 'card empty' }, all.items.length ? (tab === 'action' ? 'Nothing needs you. Nice.' : 'Nothing here.') : 'No calls yet. Try a practice call to see how it works.')]));
  };
  const steps = [
    [status.ai_ready, 'Connect your AI', 'Paste your Groq key so the assistant can think and listen.', '#/setup'],
    [status.profile_ready, 'Tell it about your business', 'Your name, what you sell, prices it may quote.', '#/setup'],
    [all.total > 0, 'Make a practice call', 'Play a customer and see the summary it writes.', '#/try'],
    [status.phone.connected, 'Connect your phone line', 'When you are ready for real calls.', '#/setup'],
  ];
  const first = steps.findIndex(([done]) => !done);
  mount(root,
    h('div', {}, h('h1', {}, profile.business_name ? `Hello, ${profile.owner_name || 'there'}` : 'Your calls'), h('div', { class: 'muted' }, profile.assistant_on ? 'Missed calls are answered for you. Here is what you need to know.' : 'The assistant is switched off. Turn it on in Setup.')),
    first >= 0 ? h('div', { class: 'card' }, h('h2', {}, 'Get started'), h('div', { class: 'steps' }, ...steps.map(([done, t, d, href], i) => h('a', { href, class: 'step', style: 'color:inherit' },
      h('span', { class: 'dot ' + (done ? 'done' : i === first ? 'act' : 'skip') }, done ? '✓' : String(i + 1)), h('div', { class: 'grow' }, h('div', { class: 't' }, t), h('div', { class: 'd' }, d)), i === first ? h('span', { class: 'badge act' }, 'Next') : null)))) : null,
    h('div', { class: 'tiles3' }, tile(stats.needs_action, 'Need you', stats.needs_action > 0, 'action'), tile(stats.answered_7d, 'Answered this week'), tile(stats.not_worth_time_7d, 'Not worth your time')),
    chips, rows);
  draw();
  function tile(n, label, hot, to) { return h('div', { class: 'stat' + (hot ? ' hot' : '') }, h('b', {}, String(n)), h('span', {}, label)); }
}

function row(c) {
  const [, cls, ch] = IMPORTANCE[c.importance] || IMPORTANCE.fyi;
  const state = c.importance === 'action' && c.reviewed ? ['done', '✓'] : [cls, ch];
  return h('a', { href: `#/calls/${c.id}`, class: 'callrow' }, h('span', { class: 'dot ' + state[0] }, state[1]),
    h('div', { class: 'grow' }, h('div', { class: 't' }, who(c)), h('div', { class: 's' }, c.summary || '…')),
    h('div', { class: 'meta' }, h('span', {}, ago(c.started_at)), c.open_actions ? h('span', { class: 'badge act' }, `${c.open_actions} to do`) : null, c.source === 'test' ? h('span', { class: 'badge' }, 'practice') : null, c.note_count ? h('span', {}, `${c.note_count} note${c.note_count > 1 ? 's' : ''}`) : null));
}

async function detail(root, id) {
  const box = h('div', { class: 'stack', style: 'gap:18px' });
  mount(root, h('a', { href: '#/calls', class: 'small' }, '← All calls'), box);
  const c = await A(`/calls/${id}`);
  const [label, cls] = IMPORTANCE[c.importance] || IMPORTANCE.fyi;
  const items = c.action_items;
  const todo = h('div', {});
  const drawTodo = () => mount(todo, ...items.map((a) => h('label', { class: 'todo' + (a.done ? ' done' : '') },
    h('input', { type: 'checkbox', checked: a.done, onchange: async (e) => { try { const r = await A(`/calls/${id}/actions/${a.id}`, { method: 'PUT', body: { done: e.target.checked } }); a.done = e.target.checked; drawTodo(); if (r.reviewed) toast('All done. Moved off your list.'); } catch (err) { toast(err.message, true); e.target.checked = a.done; } } }), h('span', {}, a.text))));
  drawTodo();
  const dealt = h('input', { type: 'checkbox', checked: c.reviewed, onchange: async (e) => { try { await A(`/calls/${id}`, { method: 'PUT', body: { reviewed: e.target.checked } }); toast(e.target.checked ? 'Marked as dealt with' : 'Back on your list'); } catch (err) { toast(err.message, true); } } });
  mount(box,
    h('div', {}, h('h1', {}, who(c)), h('div', { class: 'muted small' }, [c.source === 'test' ? 'Practice call' : 'Phone call', ago(c.started_at), durationText(c.duration_s), c.language].filter(Boolean).join(' · '))),
    h('div', { class: 'card stack' }, h('div', {}, h('span', { class: 'badge ' + cls }, label), c.category ? h('span', { class: 'badge', style: 'margin-left:6px' }, c.category) : null),
      h('div', { style: 'font-size:17px;font-weight:600' }, c.summary || 'No summary.'), c.summary_error ? h('div', { class: 'notice' }, c.summary_error) : null,
      c.callback_number && c.handled_by === 'assistant' ? h('a', { class: 'btn', href: `tel:${c.callback_number}` }, `Call back ${c.callback_number}`) : null,
      c.importance !== 'ignore' ? h('label', { class: 'row', style: 'gap:10px;font-weight:600' }, dealt, 'I have dealt with this') : null),
    items.length ? h('div', { class: 'card' }, h('h2', {}, 'To do'), todo) : null,
    h('div', { class: 'card' }, h('h2', {}, 'What was said'), c.turns.length ? h('div', { class: 'chat' }, ...c.turns.map((t) => h('div', { class: 'msg ' + (t.role === 'assistant' ? 'assistant' : 'user') }, t.content))) : h('div', { class: 'muted' }, 'No conversation.')),
    h('div', { class: 'card stack' }, h('h2', { style: 'margin:0' }, 'Your notes'), h('div', { class: 'small muted' }, 'Write down what you noticed: was it right, what should change.'),
      notesPanel(id, c.notes, { urls: { add: `/api/assistant/calls/${id}/notes`, item: (nid) => `/api/assistant/call-notes/${nid}` } })),
    c.cost && c.cost.total !== undefined ? h('div', { class: 'small muted', style: 'text-align:center' }, `Estimated cost of this call: ${rupees(c.cost.total)} (phone ${rupees(c.cost.phone)}, voice ${rupees(c.cost.voice)}, AI ${rupees(c.cost.ai + c.cost.speech_to_text)})`) : null,
    h('div', { style: 'text-align:center' }, h('button', { class: 'link danger', onclick: async () => { if (await ask('Delete this call and its notes?', { yes: 'Delete', danger: true })) { await A(`/calls/${id}`, { method: 'DELETE' }); location.hash = '#/calls'; } } }, 'Delete this call')));
}
