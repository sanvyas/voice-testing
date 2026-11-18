// Test your Munshi: a practice call from this screen, as a customer would make it. Nothing goes to any real customer.
import { h, mount } from '/lab/ui.js';
import { A, apiForm, getConfig } from '../net.js';
import { apiBlob } from '/lab/api.js';
import { makePlayer } from '/lab/voice.js';
import { t, getLang } from '../i18n.js';
import { icon, toast } from '../kit.js';
import { shell, go } from '../shell.js';
import { makeListener, canRecord } from '../listener.js';

const FILE = (blob) => `speech.${blob.type.includes('mp4') ? 'm4a' : blob.type.includes('ogg') ? 'ogg' : 'webm'}`;
const mm = (s) => `${Math.floor(s / 60)}:${String(s % 60).padStart(2, '0')}`;
const langOf = (text) => (/[ऀ-ॿ]/.test(text) ? 'hi-IN' : 'en-IN');

export async function render(root) {
  const cfg = await getConfig(); const profile = shell.profile; const player = makePlayer(); const listener = makeListener();
  const micMode = cfg.stt_ready && canRecord;
  const S = { callId: '', live: false, busy: false, ended: false, sec: 0, lines: [], result: null, status: '', reply: '' };
  let tick = null; let alive = true;
  const body = h('div', { class: 'scroll' }); const bar = h('div', { class: 'bar' }); const level = h('i');
  const draw = () => {
    const ready = shell.status.ai_ready && shell.status.profile_ready;
    mount(body, h('div', { class: 'lead', style: 'font-size:15px' }, t(['अपने Munshi को कॉल करके सुनिए, और बातें लिखी हुई देखिए।', 'Call your own Munshi. Listen, and watch the words appear.'])),
      !shell.status.ai_ready ? h('div', { class: 'cardw', style: 'margin-top:12px;border-color:var(--warn)' }, t(['AI अभी जुड़ा नहीं है। Munshi टीम से कहें।', 'The AI is not connected yet. Ask the Munshi team.'])) : null,
      shell.status.ai_ready && !shell.status.profile_ready ? h('div', { class: 'cardw', style: 'margin-top:12px;border-color:var(--warn)' }, t(['पहले दुकान और अपना नाम भरें: ', 'First add the shop name and your name: ']), h('a', { href: '#/setup', style: 'color:var(--green);font-weight:700' }, t(['सेटअप खोलें', 'Open setup']))) : null,
      S.live || S.ended ? h('div', { class: 'tryhead' }, h('b', {}, S.live ? h('i') : null, S.live ? t(['लाइव कॉल', 'Live call']) : t(['कॉल ख़त्म', 'Call ended'])), h('b', { class: 'hd', style: 'font-size:18px' }, mm(S.sec))) : null,
      S.reply ? h('div', { class: 'cardw', style: 'margin-top:14px;background:#D9F5E8;white-space:pre-line' }, h('div', { style: 'font-size:12px;font-weight:700;color:var(--green);margin-bottom:4px' }, t(['कॉल करने वाले को यह मैसेज जाएगा', 'The caller would get this message'])), S.reply) : null,
      h('div', { class: 'lines' }, ...S.lines.map((m) => h('div', { class: m.w }, h('div', { class: 'w' }, m.w === 'm' ? 'Munshi' : t(['आप', 'You'])), m.text))),
      S.live && micMode ? h('div', {}, h('div', { class: 'level' }, level), h('div', { class: 'note', style: 'margin-top:6px' }, S.status)) : (S.live ? h('div', { class: 'note', style: 'margin-top:8px' }, S.status) : null),
      S.result ? h('div', { class: 'dark', style: 'margin-top:14px;border-radius:16px;padding:14px 16px' }, h('div', { class: 'k' }, t(['आपको ऐसी लाइन मिलेगी (टेस्ट)', 'You would get this line (test)'])), h('div', { class: 'v', style: 'font-size:18px' }, S.result)) : null,
      h('div', { class: 'foot', style: 'text-align:left' }, t(['टेस्ट कॉल है। किसी ग्राहक को मैसेज नहीं जाएगा।', 'Test call. No message goes to any customer.'])));
    const typed = h('input', { placeholder: t(['या ग्राहक की बात यहाँ लिखें…', 'Or type what the caller says…']), 'aria-label': 'Message', style: 'flex:1;min-height:52px;border:1.5px solid var(--ring);border-radius:26px;padding:0 16px;font-size:16px', onkeydown: (e) => { if (e.key === 'Enter') sendTyped(); } });
    const sendTyped = () => { const v = typed.value.trim(); if (v) { typed.value = ''; send(v, 0); } };
    mount(bar, S.live ? h('div', { class: 'talkbar', style: 'margin-top:0' }, typed, h('button', { class: 'send ok', 'aria-label': 'Send', onclick: sendTyped }, icon('send'))) : null,
      S.ended ? h('button', { class: 'big', onclick: () => go('#/more') }, t(['हो गया', 'Done'])) : h('button', { class: 'big' + (S.live ? ' dark' : ''), disabled: !S.live && !ready, onclick: S.live ? finish : start }, icon('phone', 24), S.live ? t(['कॉल खत्म करें', 'End call']) : t(['Munshi को कॉल करें', 'Call your Munshi'])));
  };
  const status = (text) => { S.status = text; if (alive) draw(); };
  async function speak(text) {
    if (!alive) return; status(t(['Munshi बोल रहा है…', 'Munshi is speaking…']));
    try { const r = await apiBlob('/api/assistant/voices/sample', { text, language: langOf(text) }); await player.play(r.blob); return; }
    catch (e) { if (e.status !== 409 && e.status !== 0) toast(e.message, { bad: true }); }
    if (!('speechSynthesis' in window)) return;
    await new Promise((res) => { window.speechSynthesis.cancel(); const u = new SpeechSynthesisUtterance(text); u.lang = langOf(text); u.rate = 0.96; u.onend = res; u.onerror = res; window.speechSynthesis.speak(u); });
  }
  async function next() {
    if (!alive || S.busy || S.ended || !S.live) return;
    if (!micMode) return status(t(['आपकी बारी: ग्राहक की बात नीचे लिखें।', 'Your turn: type what the caller says below.']));
    status(t(['सुन रहा है… ग्राहक की तरह बोलिए।', 'Listening… speak like a customer would.']));
    try {
      const got = await listener.listen({ onLevel: (v) => { level.style.width = `${Math.min(100, Math.round(v * 100))}%`; } });
      if (!alive || S.ended) return; if (!got) return next();
      S.busy = true; status(t(['समझ रहा है…', 'Understanding…']));
      const form = new FormData(); form.append('file', got.blob, FILE(got.blob)); form.append('language', getLang() === 'hi' ? 'hi-IN' : 'en-IN');
      const { text } = await apiForm('/transcribe', form); S.busy = false;
      if (!text) return next();
      await send(text, got.seconds);
    } catch (e) { S.busy = false; status(e.name === 'NotAllowedError' ? t(['ब्राउज़र में माइक की अनुमति दें, या नीचे लिखें।', 'Allow the microphone in your browser, or type below.']) : e.message); }
  }
  async function send(text, seconds) {
    if (S.busy && !seconds) return; S.busy = true; listener.cancel(); status(t(['सोच रहा है…', 'Thinking…']));
    try {
      const r = await A(`/calls/${S.callId}/turns`, { method: 'POST', body: { content: text, ...(seconds ? { audio_seconds: seconds } : {}) } });
      S.lines.push({ w: 'u', text: r.caller.content }, { w: 'm', text: r.assistant.content }); draw();
      await speak(r.assistant.content); S.busy = false;
      if (r.ended) return finish(); status(''); next();
    } catch (e) { S.busy = false; status(e.message); setTimeout(next, 1500); }
  }
  async function start() {
    player.unlock();
    try {
      const r = await A('/calls', { method: 'POST', body: { caller_number: '' } });
      if (r.reply_only) { S.reply = r.preview; return draw(); }
      if (r.routed_to_owner) return toast(t(['यह नंबर “हमेशा रिंग” में है।', 'This number is on your always-ring list.']), { bad: true });
      S.callId = r.call.id; S.live = true; S.sec = 0; S.lines = [{ w: 'm', text: r.greeting }]; draw();
      const t0 = Date.now(); tick = setInterval(() => { S.sec = Math.floor((Date.now() - t0) / 1000); draw(); }, 1000);
      await speak(r.greeting); status(''); next();
    } catch (e) { toast(e.message, { bad: true }); }
  }
  async function finish() {
    if (S.ended) return; S.ended = true; S.live = false; clearInterval(tick); listener.cancel(); player.stop(); window.speechSynthesis?.cancel(); status('');
    try { const c = await A(`/calls/${S.callId}/end`, { method: 'POST' }); S.result = c.summary; window.dispatchEvent(new Event('munshi-changed')); } catch (e) { toast(e.message, { bad: true }); }
    if (alive) draw();
  }
  mount(root, h('div', { class: 'col' }, h('div', { class: 'sub-top' }, h('button', { class: 'btn-ic', 'aria-label': t(['वापस', 'Back']), onclick: () => go('#/more') }, icon('back', 28)), h('h1', {}, t(['Munshi को आज़माएँ', 'Test your Munshi']))), body, bar));
  draw();
  return () => { alive = false; clearInterval(tick); listener.close(); player.stop(); window.speechSynthesis?.cancel(); if (S.live && !S.ended && S.callId) A(`/calls/${S.callId}/end`, { method: 'POST' }).catch(() => {}); };
}
