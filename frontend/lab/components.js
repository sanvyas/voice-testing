import { h, mount } from './ui.js';
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
