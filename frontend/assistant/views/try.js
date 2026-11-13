import { h, mount, toast } from '/lab/ui.js';
import { notesPanel } from '/lab/components.js';
import { LANGS, makePlayer, voiceSettings, ENGINE_NAMES } from '/lab/voice.js';
import { A, apiForm, getConfig } from '../net.js';
import { makeListener, canRecord } from '../listener.js';

const FILE = (blob) => `speech.${blob.type.includes('mp4') ? 'm4a' : blob.type.includes('ogg') ? 'ogg' : 'webm'}`;
const IDEAS = ['Mujhe 20 packet chawal chahiye, kal tak mil jayega?', 'What is your price for basmati rice?', 'Mera payment pending hai, owner se baat karni hai', 'I want to speak to the owner about a complaint'];

export async function render(root) {
  const [cfg, voice, profile, status] = await Promise.all([getConfig(), voiceSettings(), A('/profile'), A('/status')]);
  const player = makePlayer();
  const listener = makeListener();
  const mode = cfg.stt_ready && canRecord ? 'mic' : 'typed';
  const lang = h('select', { 'aria-label': 'Language the caller speaks', style: 'width:auto' }, ...LANGS.map(([v, l]) => h('option', { value: v, selected: v === (profile.languages[0] === 'hi' ? 'hi-IN' : 'en-IN') }, l)));
  const number = h('input', { placeholder: 'Optional: the number you are calling from, e.g. 98765 43210', 'aria-label': 'Calling from', inputmode: 'tel' });
  const startBtn = h('button', { class: 'go' }, '📞  Start a practice call');
  let stop = () => {};

  startBtn.addEventListener('click', async () => {
    startBtn.disabled = true; player.unlock();
    try {
      const r = await A('/calls', { method: 'POST', body: { caller_number: number.value.trim() } });
      if (r.routed_to_owner) { toast('That number is on your always-ring list.'); mount(root, routed(r.call)); return; }
      stop = live(r.call.id, r.greeting);
    } catch (e) { toast(e.message, true); startBtn.disabled = false; }
  });

  function routed(c) {
    return h('div', { class: 'card stack' }, h('h2', { style: 'margin:0' }, `${c.caller_name || c.caller_number} rings you directly`), h('p', { class: 'muted', style: 'margin:0' }, 'This number is on your always-ring list, so the assistant does not answer it. On a real call your phone rings first. If you do not pick up, the caller hears that you are unavailable and you get a missed-call entry.'), h('a', { class: 'btn', href: '#/try', onclick: () => location.reload() }, 'Try another call'));
  }

  function live(callId, greeting) {
    const S = { active: true, busy: false, ended: false };
    const chat = h('div', { class: 'chat', style: 'max-height:38vh;overflow:auto' });
    const label = h('div', { class: 'caption', role: 'status', 'aria-live': 'polite' });
    const orb = h('button', { class: 'orb', 'aria-label': 'Microphone', 'data-s': 'idle' });
    const stage = h('div', { class: 'stage', 'data-s': 'idle' }, h('span', { class: 'ring' }), h('span', { class: 'ring' }), orb);
    const typed = h('input', { placeholder: 'Or type what the caller says…', 'aria-label': 'Message', style: 'flex:1', onkeydown: (e) => { if (e.key === 'Enter') sendTyped(); } });
    const sendBtn = h('button', { onclick: sendTyped }, 'Send');
    const endBtn = h('button', { class: 'go' }, 'End call and get the summary');
    const say = (s, t, bad = false) => { orb.dataset.s = s; stage.dataset.s = s; if (s !== 'listening') stage.style.setProperty('--level', '0'); label.textContent = t; label.style.color = bad ? 'var(--fail)' : ''; };
    const draw = (turns) => { mount(chat, ...turns.map((t) => h('div', { class: 'msg ' + (t.role === 'assistant' ? 'assistant' : 'user') }, t.content))); chat.scrollTop = chat.scrollHeight; };
    const turns = [{ role: 'assistant', content: greeting }];

    async function speak(text) {
      say('speaking', 'Speaking…');
      if (voice.active !== 'device') {
        try {
          const r = await player.say(text, lang.value); A(`/calls/${callId}/spoken?chars=${r.chars}&engine=${voice.active}`, { method: 'POST' }).catch(() => {});
          say('speaking', `Speaking · ${ENGINE_NAMES[voice.active]} · ${r.ms} ms to create`); await player.play(r.blob); return;
        } catch (e) { toast(`${e.message} Using your device voice instead.`, true); }
      }
      if (!('speechSynthesis' in window)) return;
      await new Promise((res) => { window.speechSynthesis.cancel(); const u = new SpeechSynthesisUtterance(text); u.lang = lang.value; u.rate = 0.96; u.onend = res; u.onerror = res; window.speechSynthesis.speak(u); });
    }
    async function next() {
      if (!S.active || S.busy || S.ended) return;
      if (mode !== 'mic') return say('idle', 'Type what the caller says.');
      say('listening', 'Listening…');
      try {
        const got = await listener.listen({ onLevel: (v) => stage.style.setProperty('--level', String(Math.min(1, v))) });
        if (!S.active || S.ended) return;
        if (!got) return next();
        S.busy = true; say('thinking', 'Listening back…');
        const form = new FormData(); form.append('file', got.blob, FILE(got.blob)); form.append('language', lang.value);
        const { text } = await apiForm('/transcribe', form);
        S.busy = false;
        if (!text) { say('idle', 'Did not catch that'); return next(); }
        await send(text, got.seconds);
      } catch (e) { S.busy = false; say('idle', e.name === 'NotAllowedError' ? 'Microphone is blocked. Allow it, or type below.' : e.message, true); }
    }
    async function send(text, seconds = 0) {
      if (S.busy && seconds === 0) return;
      S.busy = true; sendBtn.disabled = true; listener.cancel(); say('thinking', 'Thinking…');
      try {
        const r = await A(`/calls/${callId}/turns`, { method: 'POST', body: { content: text, ...(seconds ? { audio_seconds: seconds } : {}) } });
        turns.push(r.caller, r.assistant); draw(turns);
        await speak(r.assistant.content);
        S.busy = false; sendBtn.disabled = false;
        if (r.ended) return finish(); say('idle', ''); next();
      } catch (e) { S.busy = false; sendBtn.disabled = false; say('idle', e.message, true); setTimeout(next, 1200); }
    }
    function sendTyped() { const t = typed.value.trim(); if (t) { typed.value = ''; send(t); } }
    async function finish() {
      if (S.ended) return; S.ended = true; endBtn.disabled = true; listener.cancel(); player.stop(); window.speechSynthesis?.cancel();
      say('thinking', 'Writing the summary…');
      try { await A(`/calls/${callId}/end`, { method: 'POST' }); location.hash = `#/calls/${callId}`; }
      catch (e) { toast(e.message, true); S.ended = false; endBtn.disabled = false; }
    }
    endBtn.addEventListener('click', finish);
    orb.addEventListener('click', () => { player.unlock(); if (mode !== 'mic') return toast('Voice is not available here. Type instead.', true); if (orb.dataset.s === 'listening') { listener.cancel(); say('idle', 'Paused. Tap the orb to talk.'); } else if (!S.busy) next(); });
    typed.addEventListener('focus', () => listener.cancel());
    draw(turns);
    mount(root, h('div', {}, h('h1', {}, 'Practice call'), h('div', { class: 'muted' }, 'You are the caller. Talk or type like a real customer would.')),
      h('div', { class: 'card stack' }, mode === 'mic' ? stage : null, label, chat, h('div', { class: 'row', style: 'flex-wrap:nowrap' }, typed, sendBtn), h('div', { class: 'chips' }, ...IDEAS.map((t) => h('span', { class: 'chip plain', role: 'button', onclick: () => { typed.value = t; typed.focus(); } }, t.length > 34 ? t.slice(0, 32) + '…' : t)))),
      h('div', { class: 'card stack' }, h('strong', {}, 'Your notes on this call'), notesPanel(callId, [], { urls: { add: `/api/assistant/calls/${callId}/notes`, item: (nid) => `/api/assistant/call-notes/${nid}` } })), endBtn);
    (async () => { await speak(greeting); say('idle', ''); next(); })();
    return () => { S.active = false; listener.close(); player.stop(); window.speechSynthesis?.cancel(); };
  }

  mount(root, h('div', {}, h('h1', {}, 'Try it'), h('div', { class: 'muted' }, 'Call your own assistant from this page, as if you were a customer. No phone line needed.')),
    !status.ai_ready ? h('div', { class: 'notice' }, 'Connect your AI key first. ', h('a', { href: '#/setup' }, 'Open Setup')) : null,
    status.ai_ready && !status.profile_ready ? h('div', { class: 'notice' }, 'Add your name and business name so it knows who it answers for. ', h('a', { href: '#/setup' }, 'Open Setup')) : null,
    h('div', { class: 'card stack' }, h('label', { class: 'f' }, 'Calling from', number, h('small', {}, 'Type a number from your Contacts marked “always ring me” to see how those callers are treated.')), h('div', { class: 'row between' }, h('span', { class: 'small muted' }, `Voice: ${voice.active === 'device' ? 'your device' : ENGINE_NAMES[voice.active]} · ${mode === 'mic' ? 'speech is understood by Whisper on Groq' : 'typing only on this device'}`), lang), startBtn));
  return () => { stop(); listener.close(); player.stop(); };
}
