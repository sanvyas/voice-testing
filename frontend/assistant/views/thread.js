// The thread with one person: every call as a dark summary card (only for the owner), WhatsApp messages as green bubbles, and a box to reply.
import { h, mount } from '/lab/ui.js';
import { A, apiForm } from '../net.js';
import { t, dayLabel, clock, duration, initial, getLang } from '../i18n.js';
import { icon, sheet, toast, isOnline, telLink } from '../kit.js';
import { go } from '../shell.js';
import { makeListener, canRecord } from '../listener.js';

const FILE = (blob) => `speech.${blob.type.includes('mp4') ? 'm4a' : blob.type.includes('ogg') ? 'ogg' : 'webm'}`;

export async function render(root, { param }) {
  let data = await A(`/thread?phone=${encodeURIComponent(param)}&lang=${getLang()}`);
  let text = ''; let micOn = false; let recording = false; let alive = true; let sending = false;
  const listener = makeListener();
  const body = h('div', { class: 'th-body', id: 'thbody' });
  const pendEl = h('div'); const chipsEl = h('div'); const micNote = h('div', { class: 'note', hidden: true }, t(['बोलकर लिखा गया। भेजने से पहले जाँच लें।', 'Written from your voice. Please check before sending.']));
  const input = h('input', { value: '', 'aria-label': t(['जवाब लिखें', 'Write a reply']), oninput: (e) => { text = e.target.value; micOn = false; micNote.hidden = true; paintSend(); }, onkeydown: (e) => { if (e.key === 'Enter') send(); } });
  const micBtn = h('button', { class: 'mic', 'aria-label': t(['बोलकर लिखें', 'Speak your reply']), onclick: speak }, icon('mic'));
  const sendBtn = h('button', { class: 'send', 'aria-label': t(['भेजें', 'Send']), onclick: send }, icon('send'));
  const first = () => (data.name || '').split(' ')[0];
  input.placeholder = t([`${first()} को जवाब लिखें`, `Write to ${first()}`]);
  function paintSend() { sendBtn.className = 'send' + (text.trim() ? ' ok' : ''); }
  function setText(v, fromMic = false) { text = v; input.value = v; micOn = fromMic; micNote.hidden = !fromMic; paintSend(); input.focus(); }

  function drawBody() {
    const out = []; let day = null; const hasOwner = data.items.some((i) => i.type === 'wa' && i.sender === 'owner');
    for (const it of data.items) {
      if (it.days_ago !== day) { day = it.days_ago; out.push(h('div', { class: 'day' }, dayLabel(day))); }
      if (it.type === 'call') {
        const pts = it.points.length ? it.points : (it.ask && !it.done ? [t(['आपको बताना है: ', 'You need to give: ']) + it.ask] : []);
        out.push(h('div', { class: 'sumcard' }, h('div', { class: 'lbl' }, t(['कॉल का सार · सिर्फ़ आपके लिए', 'Call summary · only for you']) + (it.done && it.importance === 'action' ? ' · ✓' : '')),
          h('div', { class: 'txt' }, it.summary), ...(it.importance === 'action' && !it.done ? pts : []).map((p) => h('div', { class: 'pt' }, h('span', {}, '!'), p)),
          h('div', { class: 'meta' }, h('span', {}, `${clock(it.at)} · ${duration(it.duration_s)}`), h('button', { onclick: () => go(`#/detail/${it.id}`) }, t(['पूरी जानकारी ›', 'Full details ›'])))));
      } else {
        const mine = it.sender !== 'customer';
        out.push(h('div', { class: 'bub ' + (mine ? 'out' : 'in') }, mine ? h('div', { class: 'by' + (it.sender === 'owner' ? ' you' : '') }, it.sender === 'ai' ? t(['Munshi (AI) ने भेजा', 'Sent by Munshi (AI)']) : t(['आपने भेजा', 'Sent by you'])) : null, it.text,
          h('div', { class: 'tm' }, h('span', {}, clock(it.at)), mine ? h('b', {}, ' ✓') : null)));
      }
    }
    if (data.resolved) out.push(h('div', { class: 'resolved' }, icon('check', 18), hasOwner ? t(['जवाब भेजा · हो गया', 'Reply sent · done']) : t(['हो गया', 'Done'])));
    mount(body, ...out);
    body.scrollTop = body.scrollHeight;
  }
  function drawComposerParts() {
    const pending = data.pending.length > 0;
    mount(pendEl, pending ? h('div', { class: 'pendrow' }, h('b', {}, '! ' + t(['जवाब बाकी: ', 'Reply needed: ']) + (data.ask || t(['जवाब', 'reply']))),
      h('button', { class: 'link', style: 'min-height:44px;padding:0 4px 0 8px;font-size:14px', onclick: markDone }, icon('check', 20), t(['हो गया', 'Done']))) : null);
    mount(chipsEl, pending && data.chips.length ? h('div', { class: 'chips' }, ...data.chips.map((c) => h('button', { class: 'rchip', onclick: () => setText((text ? text + ' ' : '') + c.text) }, '+ ' + c.label))) : null);
  }
  async function reload() { data = await A(`/thread?phone=${encodeURIComponent(param)}&lang=${getLang()}`); if (!alive) return; drawBody(); drawComposerParts(); window.dispatchEvent(new Event('munshi-changed')); }
  async function markDone() {
    try { for (const id of data.pending) await A(`/calls/${id}`, { method: 'PUT', body: { reviewed: true } }); toast(t(['हो गया में डाला', 'Marked done']), { high: true }); await reload(); } catch (e) { toast(e.message, { bad: true, high: true }); }
  }
  function failed(message) {
    sheet(t(['संदेश नहीं गया', 'Message not sent']), (close) => [h('p', {}, message), h('div', { class: 'two-btn' }, h('button', { class: 'outline main', onclick: close }, t(['बंद करें', 'Close'])),
      data.phone ? h('a', { class: 'primary', href: telLink(data.phone), onclick: close }, icon('phone', 22), t(['कॉल करें', 'Call back'])) : null)]);
  }
  async function send() {
    if (!text.trim() || sending) return;
    if (!isOnline()) return toast(t(['इंटरनेट नहीं है। संदेश नहीं गया।', 'No internet. Message not sent.']), { bad: true, high: true });
    sending = true;
    try { await A('/messages', { method: 'POST', body: { phone: data.phone, text: text.trim() } }); toast(t(['WhatsApp पर भेजा', 'Sent on WhatsApp']), { high: true }); setText(''); micNote.hidden = true; await reload(); }
    catch (e) { if (e.status === 0) toast(t(['इंटरनेट नहीं है। संदेश नहीं गया।', 'No internet. Message not sent.']), { bad: true, high: true }); else failed(e.message); }
    finally { sending = false; }
  }
  async function speak() {
    if (recording) { listener.cancel(); return; }
    if (!canRecord) return toast(t(['यहाँ माइक नहीं चल रहा। लिखकर भेजें।', 'The microphone is not available here. Type instead.']), { bad: true, high: true });
    recording = true; micBtn.classList.add('rec');
    try {
      const got = await listener.listen({ silenceMs: 1500, waitMs: 8000 });
      if (got) {
        const form = new FormData(); form.append('file', got.blob, FILE(got.blob)); form.append('language', getLang() === 'hi' ? 'hi-IN' : 'en-IN');
        const r = await apiForm('/transcribe', form);
        if (r.text) setText((text ? text + ' ' : '') + r.text, true); else toast(t(['सुनाई नहीं दिया। फिर बोलें।', 'Did not catch that. Try again.']), { bad: true, high: true });
      }
    } catch (e) { toast(e.name === 'NotAllowedError' ? t(['ब्राउज़र में माइक की अनुमति दें।', 'Allow the microphone in your browser.']) : e.message, { bad: true, high: true }); }
    finally { recording = false; micBtn.classList.remove('rec'); }
  }

  const call = data.phone ? h('a', { class: 'mini-call', href: telLink(data.phone), 'aria-label': t(['कॉल करें', 'Call back']) }, icon('phone', 24)) : null;
  const composer = data.spam ? h('div', { class: 'spamnote' }, t(['यह सेल्स कॉल थी। जवाब देने की ज़रूरत नहीं।', 'This was a sales call. No reply needed.']))
    : !data.can_reply ? h('div', { class: 'spamnote' }, t(['इस कॉल का नंबर नहीं मिला, इसलिए WhatsApp जवाब नहीं भेज सकते।', 'This call had no number, so a WhatsApp reply cannot be sent.']))
      : h('div', { class: 'composer' }, pendEl, micNote, chipsEl, h('div', { class: 'inputrow' }, h('div', { class: 'msgbox' }, input, micBtn), sendBtn));
  mount(root, h('div', { class: 'thread' },
    h('div', { class: 'th-top' }, h('button', { class: 'btn-ic', 'aria-label': t(['वापस', 'Back']), onclick: () => go('#/calls') }, icon('back', 28)),
      h('div', { class: 'av sm' + (data.pending.length ? ' wait' : '') }, initial(data.name)),
      h('div', { style: 'flex:1;min-width:0' }, h('b', { style: 'font-size:17px' }, data.name), h('div', { style: 'font-size:12.5px;color:var(--muted)' }, `${data.phone || '—'} · WhatsApp`)), call),
    body, composer));
  drawBody(); drawComposerParts();
  return () => { alive = false; listener.close(); };
}
