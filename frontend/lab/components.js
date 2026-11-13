import { h, mount, toast, ask, ago } from './ui.js';
import { api } from './api.js';

const PENDING = ['queued', 'running', 'evaluating'];
export const isPending = (c) => PENDING.includes(c.status);

/** pass | fail | wait | warn */
export function kind(c) {
  if (isPending(c) || c.status === 'live') return 'wait';
  if (c.status === 'cancelled') return 'warn';
  if (!c.verdict) return 'wait';
  return c.verdict === 'pass' ? 'pass' : c.verdict === 'fail' ? 'fail' : 'warn';
}
export const dotChar = { pass: '✓', fail: '✕', wait: '…', warn: '!' };

export function why(c) {
  if (isPending(c)) return c.status === 'evaluating' ? 'Scoring…' : 'Running…';
  if (c.status === 'live') return 'Session still open';
  if (c.status === 'completed' && !c.verdict) return 'Not scored';
  if (c.verdict === 'pass') return `Score ${Math.round(c.score)}`;
  return c.error || c.verdict_reason || '';
}

export function transcript(turns) {
  return h('div', { class: 'chat' }, ...turns.map((t) => h('div', { class: 'msg ' + t.role }, t.content)));
}

export function checkList(results) {
  const live = results.filter((r) => r.status !== 'skipped').sort((a, b) => (a.status === 'pass') - (b.status === 'pass'));
  return h('div', {}, ...live.map((r) => h('div', { class: 'check' },
    h('span', { class: 'dot ' + (r.status === 'pass' ? 'pass' : r.status === 'fail' ? 'fail' : 'warn') }, r.status === 'pass' ? '✓' : r.status === 'fail' ? '✕' : '!'),
    h('div', {}, h('div', { class: 't' }, r.name, r.required ? h('span', { class: 'small muted' }, '  · must pass') : null), r.reasoning ? h('div', { class: 'r' }, r.reasoning) : null,
      ...(r.evidence || []).filter((q) => q.verified).slice(0, 1).map((q) => h('div', { class: 'r', style: 'font-style:italic' }, `“${q.quote}”`))))));
}

/** One expandable row: title + result; loads transcript and checks when opened. */
export function conversationRow(c, { open = false, onToggle } = {}) {
  const k = kind(c);
  const body = h('div', { class: 'body' }, h('div', { class: 'muted small' }, 'Loading…'));
  const el = h('details', { class: 'item', open: open || null },
    h('summary', {}, h('span', { class: 'dot ' + k + (k === 'wait' ? ' spin' : '') }, dotChar[k]),
      h('div', { class: 'grow' }, h('div', { style: 'font-weight:600' }, c.title || 'Conversation'), h('div', { class: 'why' }, why(c))),
      c.status === 'completed' && c.verdict ? h('span', { class: 'badge ' + (k === 'pass' ? 'pass' : k === 'fail' ? 'fail' : 'warn') }, c.verdict === 'pass' ? 'PASS' : c.verdict === 'fail' ? 'FAIL' : 'ERROR') : null),
    body);
  let loaded = false;
  const load = async () => {
    try {
      const d = await api(`/conversations/${c.id}`);
      mount(body, d.results.length ? checkList(d.results) : null, d.turns.length ? h('div', {}, h('div', { class: 'small muted', style: 'margin-bottom:6px' }, 'Conversation'), transcript(d.turns)) : h('div', { class: 'muted' }, 'No messages yet.'),
        d.status === 'error' || (d.status === 'completed' && !d.verdict) || d.verdict === 'error' ? h('div', { class: 'row' }, h('button', { onclick: async () => { await api(`/conversations/${c.id}/reevaluate`, { method: 'POST', body: {} }).catch(() => {}); location.reload(); } }, d.verdict ? 'Retry scoring' : 'Score it now')) : null);
    } catch (e) { mount(body, h('div', { class: 'notice bad' }, e.message)); }
  };
  el.addEventListener('toggle', () => { onToggle && onToggle(el.open); if (el.open && !loaded) { loaded = true; load(); } });
  if (open) { loaded = true; load(); }
  return el;
}

/** Notes on a call: add while it is live or afterwards, edit, delete. Each note remembers where in the call it was written. */
export function notesPanel(convId, initial = [], { onCount } = {}) {
  const items = [...initial]; let editing = null;
  const list = h('div', { class: 'stack', style: 'gap:8px' });
  const input = h('textarea', { rows: 2, maxlength: 2000, 'aria-label': 'Add a note', placeholder: 'What do you notice? e.g. reply felt scripted, voice cut off, caller sounded calmer…', style: 'min-height:64px' });
  const add = h('button', { class: 'go' }, 'Add note');
  const where = (n) => (n.after_turn ? `After message ${n.after_turn}` : 'Before the first message');
  const draw = () => {
    mount(list, ...(items.length ? items.map(row) : [h('div', { class: 'small muted' }, 'No notes yet.')]));
    onCount?.(items.length);
  };
  function row(n) {
    if (editing === n.id) {
      const box = h('textarea', { rows: 2, maxlength: 2000, 'aria-label': 'Edit note', style: 'min-height:64px' }, n.body);
      return h('div', { class: 'note stack', style: 'gap:8px' }, box, h('div', { class: 'row' },
        h('button', { class: 'go', onclick: async () => { try { Object.assign(n, await api(`/notes/${n.id}`, { method: 'PUT', body: { body: box.value } })); editing = null; draw(); } catch (e) { toast(e.message, true); } } }, 'Save'),
        h('button', { class: 'link', onclick: () => { editing = null; draw(); } }, 'Cancel')));
    }
    return h('div', { class: 'note' }, h('div', { class: 'small muted' }, `${where(n)} · ${ago(n.created_at)}`), h('div', { class: 'notetext' }, n.body),
      h('div', { class: 'row' }, h('button', { class: 'link', onclick: () => { editing = n.id; draw(); } }, 'Edit'),
        h('button', { class: 'link danger', onclick: async () => { if (!(await ask('Delete this note?', { yes: 'Delete', danger: true }))) return; try { await api(`/notes/${n.id}`, { method: 'DELETE' }); items.splice(items.indexOf(n), 1); draw(); } catch (e) { toast(e.message, true); } } }, 'Delete')));
  }
  const submit = async () => {
    const body = input.value.trim(); if (!body) return;
    add.disabled = true;
    try { items.push(await api(`/conversations/${convId}/notes`, { method: 'POST', body: { body } })); input.value = ''; draw(); }
    catch (e) { toast(e.message, true); }
    add.disabled = false;
  };
  add.addEventListener('click', submit);
  input.addEventListener('keydown', (e) => { if (e.key === 'Enter' && (e.metaKey || e.ctrlKey)) { e.preventDefault(); submit(); } });
  draw();
  return h('div', { class: 'stack' }, list, input, h('div', { class: 'row between' }, h('span', { class: 'small muted' }, 'Ctrl or Cmd + Enter to add'), add));
}
