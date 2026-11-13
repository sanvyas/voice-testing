import { h, mount, toast } from '/lab/ui.js';
import { notesPanel } from '/lab/components.js';
import { LANGS, makePlayer, voiceSettings, ENGINE_NAMES } from '/lab/voice.js';
import { A, apiForm, getConfig, ic, ICONS } from '../net.js';
import { makeListener, canRecord } from '../listener.js';

const FILE = (blob) => `speech.${blob.type.includes('mp4') ? 'm4a' : blob.type.includes('ogg') ? 'ogg' : 'webm'}`;
const IDEAS = ['Mujhe 20 packet chawal chahiye', 'What is the price of basmati?', 'Mera payment pending hai', 'I want to complain'];
const MODES = { reply: 'WhatsApp reply only', message: 'Taking a message', board: "Answering from Today's board" };
const changed = () => window.dispatchEvent(new Event('munshi-changed'));

export async function render(root) {
  const [cfg, voice, profile, status] = await Promise.all([getConfig(), voiceSettings(), A('/profile'), A('/status')]);
  const player = makePlayer();
  const listener = makeListener();
  const mode = cfg.stt_ready && canRecord ? 'mic' : 'typed';
  const lang = h('select', { 'aria-label': 'Language the caller speaks', style: 'width:auto;min-height:44px' }, ...LANGS.map(([v, l]) => h('option', { value: v, selected: v === (profile.languages[0] === 'hi' ? 'hi-IN' : 'en-IN') }, l)));
  const number = h('input', { type: 'tel', placeholder: 'Optional, e.g. 98765 43210', 'aria-label': 'Calling from', inputmode: 'tel' });
  const startBtn = h('button', { class: 'btn lg' }, ic(ICONS.phone), profile.mode === 'reply' ? 'Show me the reply' : 'Start a practice call');
  let stop = () => {};

  startBtn.addEventListener('click', async () => {
    startBtn.disabled = true; player.unlock();
    try {
      const r = await A('/calls', { method: 'POST', body: { caller_number: number.value.trim() } });
      if (r.reply_only) return mount(root, replyPreview(r.preview));
      if (r.routed_to_owner) { mount(root, routed(r.call)); return; }
      stop = live(r.call.id, r.greeting);
    } catch (e) { toast(e.message, true); startBtn.disabled = false; }
  });

  function replyPreview(text) {
    const test = h('button', { class: 'btn ghost' }, 'Send this to my WhatsApp as a test');
    test.addEventListener('click', async () => { test.disabled = true; try { const r = await A('/whatsapp/test', { method: 'POST' }); toast(`Sent to ${r.to}`); } catch (e) { toast(e.message, true); } test.disabled = false; });
    return h('div', { class: 'screen' }, h('a', { href: '#/try', class: 'back', onclick: () => location.reload() }, ic(ICONS.back), 'Try it'),
      h('div', {}, h('h1', { class: 'title' }, 'What the caller gets'), h('div', { class: 'sub' }, 'In WhatsApp-only mode nobody talks to the caller. They get this message right after a missed call.')),
      h('div', { class: 'preview' }, text),
      status.whatsapp.connected ? test : h('div', { class: 'notice' }, ['WhatsApp is not connected yet, so nothing is sent. ', h('a', { href: '#/setup', style: 'font-weight:700;text-decoration:underline' }, 'Connect it in Setup')]));
  }

  function routed(c) {
    return h('div', { class: 'screen' }, h('div', { class: 'card stack' }, h('h2', { class: 'sec' }, `${c.caller_name || c.caller_number} rings you directly`),
      h('p', { class: 'muted', style: 'margin:0' }, 'This number is on your always-ring list, so the assistant does not answer it. On a real call your phone rings first. If you do not pick up, the caller hears that you are unavailable and you get a missed-call entry.'),
      h('a', { class: 'btn', href: '#/try', onclick: () => location.reload() }, 'Try another call')));
  }

  function live(callId, greeting) {
    document.body.classList.add('immersive');
    const S = { active: true, busy: false, ended: false };
    const t0 = Date.now();
    const clock = h('div', { class: 'clock' }, '00:00');
    const tick = setInterval(() => { const s = Math.floor((Date.now() - t0) / 1000); clock.textContent = `${String(Math.floor(s / 60)).padStart(2, '0')}:${String(s % 60).padStart(2, '0')}`; }, 1000);
    const state = h('div', { class: 'state' }, 'Starting…'); const hint = h('div', { class: 'hint' }, '');
    const orb = h('button', { class: 'orb', 'aria-label': 'Microphone: tap to talk or pause' }, ic(ICONS.mic));
    orb.firstChild.style.cssText = 'width:52px;height:52px;stroke-width:1.8';
    const stage = h('div', { class: 'stage', 'data-s': 'idle' }, h('div', { class: 'ring1' }, h('div', { class: 'ring2' }, orb)), state, hint);
    const chat = h('div', { class: 'talk', 'aria-live': 'polite' });
    const typed = h('input', { type: 'text', placeholder: 'Or type what the caller says…', 'aria-label': 'Message', style: 'flex:1', onkeydown: (e) => { if (e.key === 'Enter') sendTyped(); } });
    const sendBtn = h('button', { class: 'send', 'aria-label': 'Send', onclick: sendTyped }, ic(ICONS.send));
    const notes = h('div', { class: 'sheet', hidden: true }, h('div', { style: 'font-weight:700;margin-bottom:8px' }, 'Your notes on this call'), notesPanel(callId, [], { urls: { add: `/api/assistant/calls/${callId}/notes`, item: (nid) => `/api/assistant/call-notes/${nid}` } }));
    const noteBtn = h('button', { class: 'notebtn', onclick: () => { notes.hidden = !notes.hidden; if (!notes.hidden) notes.querySelector('textarea')?.focus(); } }, ic(ICONS.pencil, [], true), 'Add a note about this call');
    const endBtn = h('button', { class: 'endbtn' }, ic(ICONS.x, [], true), 'End call');
    const say = (s, text, hintText = '', bad = false) => { stage.dataset.s = s; if (s !== 'listening') stage.style.setProperty('--level', '0'); state.textContent = text; hint.textContent = hintText; hint.style.color = bad ? '#FF9A9A' : ''; };
    const turns = [{ role: 'assistant', content: greeting }];
    const draw = () => { mount(chat, ...turns.map((t) => h('div', { class: 'bubble ' + t.role }, t.content))); chat.scrollTop = chat.scrollHeight; };

    async function speak(text) {
      say('speaking', 'Speaking…');
      if (voice.active !== 'device') {
        try {
          const r = await player.say(text, lang.value); A(`/calls/${callId}/spoken?chars=${r.chars}&engine=${voice.active}`, { method: 'POST' }).catch(() => {});
          say('speaking', 'Speaking…', `${ENGINE_NAMES[voice.active]} voice, ${r.ms} ms to create`); await player.play(r.blob); return;
        } catch (e) { toast(`${e.message} Using your device voice instead.`, true); }
      }
      if (!('speechSynthesis' in window)) return;
      await new Promise((res) => { window.speechSynthesis.cancel(); const u = new SpeechSynthesisUtterance(text); u.lang = lang.value; u.rate = 0.96; u.onend = res; u.onerror = res; window.speechSynthesis.speak(u); });
    }
    async function next() {
      if (!S.active || S.busy || S.ended) return;
      if (mode !== 'mic') return say('idle', 'Your turn', 'Type what the caller says.');
      say('listening', 'Listening…', 'Speak like a customer would. Tap the orb to pause.');
      try {
        const got = await listener.listen({ onLevel: (v) => stage.style.setProperty('--level', String(Math.min(1, v))) });
        if (!S.active || S.ended) return;
        if (!got) return next();
        S.busy = true; say('thinking', 'Understanding…');
        const form = new FormData(); form.append('file', got.blob, FILE(got.blob)); form.append('language', lang.value);
        const { text } = await apiForm('/transcribe', form);
        S.busy = false;
        if (!text) { say('idle', 'Did not catch that'); return next(); }
        await send(text, got.seconds);
      } catch (e) { S.busy = false; say('idle', 'Microphone problem', e.name === 'NotAllowedError' ? 'Allow the microphone in your browser, or type below.' : e.message, true); }
    }
    async function send(text, seconds = 0) {
      if (S.busy && seconds === 0) return;
      S.busy = true; sendBtn.disabled = true; listener.cancel(); say('thinking', 'Thinking…');
      try {
        const r = await A(`/calls/${callId}/turns`, { method: 'POST', body: { content: text, ...(seconds ? { audio_seconds: seconds } : {}) } });
        turns.push(r.caller, r.assistant); draw();
        await speak(r.assistant.content);
        S.busy = false; sendBtn.disabled = false;
        if (r.ended) return finish(); say('idle', ''); next();
      } catch (e) { S.busy = false; sendBtn.disabled = false; say('idle', 'Something went wrong', e.message, true); setTimeout(next, 1500); }
    }
    function sendTyped() { const t = typed.value.trim(); if (t) { typed.value = ''; send(t); } }
    async function finish() {
      if (S.ended) return; S.ended = true; endBtn.disabled = true; listener.cancel(); player.stop(); window.speechSynthesis?.cancel();
      say('thinking', 'Writing the summary…');
      try { await A(`/calls/${callId}/end`, { method: 'POST' }); changed(); location.hash = `#/calls/${callId}`; }
      catch (e) { toast(e.message, true); S.ended = false; endBtn.disabled = false; }
    }
    endBtn.addEventListener('click', finish);
    orb.addEventListener('click', () => { player.unlock(); if (mode !== 'mic') return toast('Voice is not available here. Type instead.', true); if (stage.dataset.s === 'listening') { listener.cancel(); say('idle', 'Paused', 'Tap the orb to talk.'); } else if (!S.busy) next(); });
    typed.addEventListener('focus', () => listener.cancel());
    draw();
    mount(root, h('div', { class: 'call' },
      h('div', { class: 'head' }, h('div', {}, h('div', { class: 'lbl' }, 'Practice call'), clock), endBtn), stage, chat,
      h('div', { class: 'dock' }, notes, h('div', { class: 'row', style: 'flex-wrap:nowrap' }, typed, sendBtn),
        h('div', { class: 'quick' }, ...IDEAS.map((t) => h('button', { onclick: () => send(t) }, t))), noteBtn)));
    (async () => { await speak(greeting); say('idle', ''); next(); })();
    return () => { S.active = false; clearInterval(tick); listener.close(); player.stop(); window.speechSynthesis?.cancel(); };
  }

  mount(root, h('div', {}, h('h1', { class: 'title' }, 'Try it'), h('div', { class: 'sub' }, 'Call your own assistant from this page, as if you were a customer. No phone line needed.')),
    !status.ai_ready ? h('div', { class: 'notice' }, status.role === 'admin' ? ['The AI is not connected. ', h('a', { href: '/portal/#/integrations', style: 'font-weight:700;text-decoration:underline' }, 'Connect it in the portal')] : 'The assistant is not available right now. Please contact your Munshi administrator.') : null,
    status.ai_ready && !status.profile_ready ? h('div', { class: 'notice' }, ['Add your name and business name so it knows who it answers for. ', h('a', { href: '#/setup', style: 'font-weight:700;text-decoration:underline' }, 'Open Setup')]) : null,
    h('div', { class: 'card stack' },
      h('div', { class: 'row between' }, h('span', { class: 'badge ok' }, MODES[profile.mode]), h('a', { href: '#/setup', class: 'small', style: 'color:var(--primary);font-weight:600' }, 'Change')),
      profile.mode !== 'reply' ? h('label', { class: 'f' }, 'Calling from', number, h('small', {}, 'Type a number from Contacts marked “always ring me” to see how those callers are treated.')) : null,
      profile.mode !== 'reply' ? h('div', { class: 'row between' }, h('span', { class: 'small muted' }, `Voice: ${voice.active === 'device' ? 'your device' : ENGINE_NAMES[voice.active]} · ${mode === 'mic' ? 'mic on' : 'typing only here'}`), lang) : null,
      startBtn));
  return () => { stop(); listener.close(); player.stop(); document.body.classList.remove('immersive'); };
}
