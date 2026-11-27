// "Full details" of one call: what they asked, what is left for the owner to do, the order, what Munshi said, the conversation.
import { h, mount } from '/lab/ui.js';
import { A } from '../net.js';
import { t, dayLabel, clock, duration, waitingFor, getLang } from '../i18n.js';
import { icon, sheet, toast, isOnline, telLink } from '../kit.js';
import { go } from '../shell.js';

export async function render(root, { param }) {
  const load = (turns = false) => A(`/calls/${param}?lang=${getLang()}${turns ? '&turns=true' : ''}`);
  let c = await load();
  const phoneKey = c.caller_number || `call:${c.id}`;
  let trOpen = false;
  const days = Math.max(0, Math.round((Date.now() - new Date(c.started_at).getTime()) / 86400000));
  const pending = c.importance === 'action' && !c.reviewed;
  const name = c.caller_name || c.caller_number || t(['अनजान कॉलर', 'Unknown caller']);
  const body = h('div', { class: 'scroll', style: 'padding-top:12px;display:flex;flex-direction:column;gap:12px' });
  const left = () => c.action_items.filter((a) => !a.done).length;

  async function tick(a) {
    try { const r = await A(`/calls/${c.id}/actions/${a.id}`, { method: 'PUT', body: { done: !a.done } }); c.action_items = r.action_items; c.reviewed = r.reviewed; draw(); window.dispatchEvent(new Event('munshi-changed')); }
    catch (e) { toast(e.message, { bad: true }); }
  }
  function addNote() {
    sheet(t(['अपना नोट जोड़ें', 'Add your note']), (close) => { const inp = h('input', { placeholder: t(['जैसे: कल सुबह फ़ोन करना', 'e.g. call again tomorrow morning']), maxlength: 300 });
      return [inp, h('button', { class: 'primary', onclick: async () => { const v = inp.value.trim(); if (!v) return; try { await A(`/calls/${c.id}/notes`, { method: 'POST', body: { body: v } }); close(); c = await load(trOpen); draw(); toast(t(['नोट जुड़ गया', 'Note added'])); } catch (e) { toast(e.message, { bad: true }); } } }, t(['सेव करें', 'Save']))]; });
  }
  async function done() {
    try { await A(`/calls/${c.id}`, { method: 'PUT', body: { reviewed: true } }); window.dispatchEvent(new Event('munshi-changed')); toast(t(['हो गया में डाला', 'Marked done'])); go(`#/thread/${encodeURIComponent(phoneKey)}`); } catch (e) { toast(e.message, { bad: true }); }
  }
  function draw() {
    const order = c.order && c.order.items && c.order.items.length ? c.order : null;
    const did = [t(['कॉल करने वाले को बताया: “मैं AI सहायक हूँ”', 'Told the caller: “I am an AI assistant”']),
      c.importance === 'action' ? t(['रेट, छूट या समय का वादा नहीं किया। आपको बताना है।', 'Promised no price, discount or time. You confirm.']) : c.importance === 'fyi' ? t(['सिर्फ़ आपकी दी जानकारी से जवाब दिया।', 'Answered only from the information you gave.']) : t(['बात आगे नहीं बढ़ाई।', 'Did not continue the conversation.'])];
    const todoCard = c.importance === 'action' && c.action_items.length ? h('div', { class: 'todo' }, h('div', { class: 'head' }, h('b', {}, t(['आपको करना है', 'For you to do'])), h('span', {}, left() ? t([`${left()} बाकी`, `${left()} left`]) : t(['सब हो गया ✓', 'All done ✓']))),
      ...c.action_items.map((a) => h('div', { class: 'titem' }, h('button', { class: 'tick' + (a.done ? ' done' : ''), 'aria-label': a.text, onclick: () => tick(a) }, h('i', {}, icon('check', 20))), h('div', { class: 't' + (a.done ? ' done' : '') }, a.text)))) : null;
    const keeps = [...(c.keep || []).map((k) => h('div', { class: 'titem' }, h('div', { class: 't' }, k))), ...c.notes.map((n) => h('div', { class: 'titem' }, h('div', { class: 't' }, n.body)))];
    mount(body,
      h('div', { class: 'dark' }, h('div', { class: 'k' }, t(['उन्हें क्या चाहिए', 'What they asked for'])), h('div', { class: 'v' }, c.summary), pending && days > 0 ? h('div', { class: 'age' }, waitingFor(days)) : null),
      todoCard,
      keeps.length ? h('div', { class: 'nlist' }, h('div', { class: 'h' }, t(['ध्यान रखें', 'Keep in mind'])), ...keeps) : null,
      order ? h('div', { class: 'cardw orderbox', style: 'padding:6px 18px' }, ...order.items.map((i) => h('div', { class: 'rowline' }, h('span', {}, i.name), h('b', {}, [i.qty_n, i.unit].filter((x) => x !== null && x !== '').join(' ')))),
        order.mode ? h('div', { class: 'plain' }, (order.mode === 'delivery' ? t(['डिलीवरी', 'Delivery']) : t(['पिकअप', 'Pickup'])) + (order.when ? ' · ' + order.when : '')) : null,
        h('div', { class: 'plain' }, order.address ? t(['पता: ', 'Address: ']) + order.address : t(['पता: नहीं बताया', 'Address: not given']))) : null,
      h('div', { class: 'cardw did' }, h('b', {}, t(['Munshi ने क्या कहा', 'What Munshi said'])), ...did.map((x) => h('div', {}, icon('check', 20), x))),
      h('button', { class: 'link', onclick: async () => { trOpen = !trOpen; if (trOpen) { try { c = await load(true); } catch { /* the saved text is still shown */ } } draw(); } }, trOpen ? t(['पूरी बातचीत छिपाएँ', 'Hide full conversation']) : t(['पूरी बातचीत पढ़ें', 'Read full conversation'])),
      trOpen ? h('div', { class: 'tr', style: 'margin-top:-6px' }, ...c.turns.map((m) => h('div', { class: m.role === 'assistant' ? 'm' : 'c' }, m.content))) : null);
  }
  const dial = c.caller_number || c.callback_number;
  mount(root, h('div', { class: 'col' },
    h('div', { class: 'sub-top', style: 'padding-bottom:4px' }, h('button', { class: 'btn-ic', 'aria-label': t(['वापस', 'Back']), onclick: () => go(`#/thread/${encodeURIComponent(phoneKey)}`) }, icon('back', 28)),
      h('div', { style: 'flex:1;min-width:0' }, h('div', { class: 'hd', style: 'font:700 20px/1.3 \'Space Grotesk\',\'Noto Sans Devanagari\'' }, name), h('div', { style: 'font-size:13px;color:var(--muted)' }, `${dayLabel(days)} · ${clock(c.started_at)} · ${duration(c.duration_s)}`))),
    body,
    h('div', { class: 'bar' }, dial ? h('a', { class: 'big', href: telLink(dial) }, icon('phone', 24), t(['कॉल करें', 'Call back'])) : null,
      h('div', { class: 'acts' }, h('button', { class: 'act', onclick: () => go(`#/thread/${encodeURIComponent(phoneKey)}`) }, icon('chat', 20), t(['संदेश', 'Messages'])),
        h('button', { class: 'act', onclick: addNote }, icon('pencil', 20), t(['नोट जोड़ें', 'Add note'])),
        h('button', { class: 'act' + (c.reviewed ? ' on' : ''), onclick: done }, icon('check', 20), c.reviewed ? t(['हो गया', 'Done']) : t(['हो गया', 'Mark done']))))));
  draw();
}
