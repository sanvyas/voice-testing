import { h, mount, toast, detectVariables } from '../ui.js';
import { api, apiForm, getConfig } from '../api.js';
import { saved, ensureVersion } from '../workspace.js';
import { creativityWord, lengthLabel } from '../style.js';

const SR = window.SpeechRecognition || window.webkitSpeechRecognition;
const CAN_RECORD = !!(navigator.mediaDevices && navigator.mediaDevices.getUserMedia && window.MediaRecorder);
const pickMime = () => ['audio/webm;codecs=opus', 'audio/webm', 'audio/mp4', 'audio/ogg;codecs=opus'].find((m) => window.MediaRecorder && MediaRecorder.isTypeSupported(m)) || '';
const unlockAudio = () => { try { const u = new SpeechSynthesisUtterance(''); u.volume = 0; window.speechSynthesis.speak(u); } catch { /* not supported */ } };  // iOS needs a tap first
const LANGS = [['en-IN', 'English (India)'], ['en-US', 'English (US)'], ['en-GB', 'English (UK)'], ['hi-IN', 'Hindi']];

export async function render(root) {
  const stop = { fn: null };
  const [cfg, prompts, scenarios, evalsets, open] = await Promise.all([getConfig(), api('/prompts'), api('/scenarios'), api('/eval-sets'), api('/conversations?status=live&source=live&limit=1')]);
  const ws = saved();
  const gen = await api('/settings/generation');
  const prompt = await api(`/prompts/${prompts.some((p) => p.id === ws.promptId) ? ws.promptId : prompts[0].id}`);
  const version = prompt.versions[0];
  const text = (ws.promptId === prompt.id && ws.text) || version.content;
  const mode = cfg.stt_ready && CAN_RECORD ? 'server' : SR ? 'browser' : 'typed';
  let mood = '';
  const moodChips = h('div', { class: 'chips' });
  const card = h('div', { class: 'small muted' });
  const lang = h('select', { 'aria-label': 'Language', style: 'width:auto' }, ...LANGS.map(([v, l]) => h('option', { value: v }, l)));
  const startBtn = h('button', { class: 'go' }, '🎙  Start talking');

  const drawMoods = () => {
    mount(moodChips, h('span', { class: 'chip' + (!mood ? ' on' : ''), role: 'button', onclick: () => { mood = ''; drawMoods(); } }, 'Just talk'),
      ...scenarios.map((s) => h('span', { class: 'chip' + (mood === s.id ? ' on' : ''), role: 'button', onclick: () => { mood = s.id; drawMoods(); } }, s.name)));
    const s = scenarios.find((x) => x.id === mood);
    mount(card, s ? h('div', { class: 'stack', style: 'gap:4px' }, h('strong', {}, 'You play this caller'), h('div', {}, s.persona), h('div', {}, 'Start with: ', h('em', {}, `“${s.opening_message}”`))) : null);
  };

  startBtn.addEventListener('click', async () => {
    unlockAudio(); startBtn.disabled = true;
    try {
      const v = await ensureVersion({ promptId: prompt.id, text, values: { ...version.variable_defaults, ...(ws.promptId === prompt.id ? ws.values : {}) }, version });
      const conv = await api('/live', { method: 'POST', body: { prompt_version_id: v.versionId, variables: v.variables, ...(mood ? { scenario_id: mood } : {}) } });
      session(conv);
    } catch (e) { toast(e.message, true); startBtn.disabled = false; }
  });

  function session(conv) {
    const turns = [];
    const S = { active: true, busy: false, listening: false, paused: false, finishing: false, timer: null, rec: null, stream: null, ctx: null, lock: null };
    const chat = h('div', { class: 'chat', style: 'max-height:40vh;overflow:auto' });
    const label = h('div', { class: 'caption', role: 'status', 'aria-live': 'polite' });
    const orb = h('button', { class: 'orb', 'aria-label': 'Pause or resume the microphone', 'data-s': 'idle' });
    const stage = h('div', { class: 'stage', 'data-s': 'idle' }, h('span', { class: 'ring' }), h('span', { class: 'ring' }), orb);
    const level = (v) => stage.style.setProperty('--level', String(Math.max(0, Math.min(1, v))));
    const typed = h('input', { placeholder: 'Or type here…', 'aria-label': 'Message', style: 'flex:1', onkeydown: (e) => { if (e.key === 'Enter') sendTyped(); } });
    const sendBtn = h('button', { onclick: sendTyped }, 'Send');
    const doneBtn = h('button', { class: 'go' }, 'Finish and get result');
    const say = (s, t, bad = false) => { orb.dataset.s = s; stage.dataset.s = s; S.thinking = s === 'thinking'; if (s !== 'listening') level(0); label.textContent = t; label.className = 'caption' + (s === 'listening' && t && t !== 'Listening…' ? ' live' : ''); label.style.color = bad ? 'var(--fail)' : ''; if (S.thinking) typingOn(); else typingOff(); };
    const typingEl = h('div', { class: 'typing', 'aria-label': 'Thinking' }, h('i', {}), h('i', {}), h('i', {}));
    const typingOn = () => { if (!typingEl.isConnected) { chat.append(typingEl); chat.scrollTop = chat.scrollHeight; } };
    const typingOff = () => typingEl.remove();
    const draw = (speakingLast = false) => { mount(chat, ...turns.map((t, i) => h('div', { class: 'msg ' + t.role + (speakingLast && i === turns.length - 1 ? ' speaking' : '') }, t.content))); if (S.thinking) chat.append(typingEl); chat.scrollTop = chat.scrollHeight; };

    function stopListening() {
      clearTimeout(S.timer); S.timer = null;
      if (mode === 'browser' && S.rec && S.listening) { try { S.rec.stop(); } catch { /* ignore */ } }
      if (mode === 'server' && S.rec && S.rec.state === 'recording') { S.rec.discard = true; try { S.rec.stop(); } catch { /* ignore */ } }
      S.listening = false;
    }
    function again(delay = 400) {
      if (!S.active || S.busy || S.paused || S.finishing || mode === 'typed') return;
      clearTimeout(S.timer);
      S.timer = setTimeout(() => { S.timer = null; if (S.active && !S.busy && !S.paused && !S.listening) (mode === 'server' ? record : recognize)(); }, delay);
    }
    async function record() {
      try {
        S.stream ||= await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true } });
        S.ctx ||= new (window.AudioContext || window.webkitAudioContext)();
        if (S.ctx.state === 'suspended') await S.ctx.resume();
        const an = S.ctx.createAnalyser(); an.fftSize = 1024; const src = S.ctx.createMediaStreamSource(S.stream); src.connect(an);
        const mime = pickMime(); const chunks = []; const rec = new MediaRecorder(S.stream, mime ? { mimeType: mime } : undefined); S.rec = rec;
        const buf = new Float32Array(an.fftSize); const t0 = performance.now(); let heard = false; let last = t0;
        rec.ondataavailable = (e) => e.data?.size && chunks.push(e.data);
        rec.onstop = async () => { clearInterval(vad_); src.disconnect(); S.listening = false; if (rec.discard || !S.active) return; if (!heard) return again(200); await sendAudio(new Blob(chunks, { type: rec.mimeType || mime || 'audio/webm' })); };
        const vad_ = setInterval(() => {  // stop after about 1.3 s of silence once speech was heard
          an.getFloatTimeDomainData(buf); let sum = 0; for (let i = 0; i < buf.length; i++) sum += buf[i] * buf[i];
          const now = performance.now(); const rms = Math.sqrt(sum / buf.length); level(rms * 7); if (rms > 0.02) { heard = true; last = now; }
          if ((heard && now - last > 1300) || (!heard && now - t0 > 9000) || now - t0 > 30000) { clearInterval(vad_); if (rec.state === 'recording') rec.stop(); }
        }, 100);
        rec.start(); S.listening = true; say('listening', 'Listening…');
      } catch (e) { S.listening = false; S.paused = true; say('idle', e.name === 'NotAllowedError' ? 'Microphone is blocked. Allow it in your browser, or type below.' : `Microphone problem: ${e.message}`, true); }
    }
    async function sendAudio(blob) {
      S.busy = true; say('thinking', 'Listening back…');
      try {
        const form = new FormData(); form.append('file', blob, `speech.${blob.type.includes('mp4') ? 'm4a' : blob.type.includes('ogg') ? 'ogg' : 'webm'}`); form.append('language', lang.value);
        const { text: heard } = await apiForm('/transcribe', form); S.busy = false;
        if (!heard) { say('idle', 'Did not catch that'); return again(300); }
        await send(heard);
      } catch (e) { S.busy = false; say('idle', e.message, true); again(1500); }
    }
    function recognize() {
      if (!S.rec) {
        const r = new SR(); r.lang = lang.value; r.continuous = false; r.interimResults = true;
        r.onstart = () => { S.listening = true; say('listening', 'Listening…'); };
        r.onresult = (ev) => { let fin = '', interim = ''; for (let i = ev.resultIndex; i < ev.results.length; i++) (ev.results[i].isFinal ? (fin += ev.results[i][0].transcript) : (interim += ev.results[i][0].transcript)); if (interim && !fin) say('listening', interim); if (fin.trim()) send(fin.trim()); };
        r.onerror = (ev) => { S.listening = false; if (ev.error === 'not-allowed' || ev.error === 'service-not-allowed') { S.paused = true; say('idle', 'Microphone is blocked. Allow it, or type below.', true); } };
        r.onend = () => { S.listening = false; again(450); };
        S.rec = r;
      }
      try { S.rec.start(); } catch { say('idle', 'Could not start the microphone.', true); }
    }
    async function send(t) {
      if (!t || S.busy || !S.active) return;
      S.busy = true; stopListening(); say('thinking', 'Thinking…'); sendBtn.disabled = true;
      try { const r = await api(`/live/${conv.id}/turns`, { method: 'POST', body: { content: t } }); turns.push(r.user, r.assistant); draw(true); speak(r.assistant.content); }
      catch (e) { S.busy = false; sendBtn.disabled = false; say('idle', e.message, true); again(1200); }
    }
    function speak(t) {
      sendBtn.disabled = false;
      const done = () => { S.busy = false; draw(false); if (S.active) { say('idle', S.paused ? 'Paused. Tap the orb to resume.' : ''); again(450); } };
      if (!('speechSynthesis' in window)) return done();
      window.speechSynthesis.cancel(); const u = new SpeechSynthesisUtterance(t); u.lang = lang.value; u.rate = 0.96;
      u.onstart = () => say('speaking', 'Speaking…'); u.onend = done; u.onerror = done; window.speechSynthesis.speak(u);
    }
    function sendTyped() { const t = typed.value.trim(); if (t) { typed.value = ''; send(t); } }
    orb.addEventListener('click', () => {
      unlockAudio();
      if (mode === 'typed') return toast('Voice is not available here. Type your message.', true);
      if (S.paused) { S.paused = false; return again(50); }
      if (S.listening || S.timer) { S.paused = true; stopListening(); say('idle', 'Paused. Tap the orb to resume.'); } else again(50);
    });
    doneBtn.addEventListener('click', async () => {
      if (!turns.length) return toast('Say something first.', true);
      S.finishing = true; doneBtn.disabled = true; stopListening(); window.speechSynthesis?.cancel();
      try { await api(`/live/${conv.id}/finish`, { method: 'POST', body: { eval_set_id: evalsets[0].id } }); location.hash = `#/results/${conv.id}`; }
      catch (e) { toast(e.message, true); S.finishing = false; doneBtn.disabled = false; }
    });
    const wake = async () => { try { S.lock = await navigator.wakeLock?.request('screen'); } catch { /* optional */ } };
    const vis = () => { if (document.visibilityState === 'visible' && S.active) wake(); };
    document.addEventListener('visibilitychange', vis); wake();
    stop.fn = () => { S.active = false; clearTimeout(S.timer); document.removeEventListener('visibilitychange', vis); try { S.rec && mode === 'browser' && S.rec.abort(); } catch { /* ignore */ } if (S.rec && S.rec.state === 'recording') { S.rec.discard = true; try { S.rec.stop(); } catch { /* ignore */ } } S.stream?.getTracks().forEach((t) => t.stop()); S.ctx?.close().catch(() => {}); S.lock?.release().catch(() => {}); window.speechSynthesis?.cancel(); };
    draw();
    mount(root, h('div', {}, h('h1', {}, 'Talking'), h('div', { class: 'muted' }, conv.scenario?.opening_message ? `You are the caller. Start with: “${conv.scenario.opening_message}”` : 'Speak naturally. It replies out loud.')),
      h('div', { class: 'card stack' }, mode === 'typed' ? null : stage, label, chat, h('div', { class: 'row', style: 'flex-wrap:nowrap' }, typed, sendBtn)), doneBtn);
    say('idle', mode === 'typed' ? 'Type a message to begin' : 'Starting the microphone…');
    if (mode !== 'typed') again(300);
  }

  mount(root, h('div', {}, h('h1', {}, 'Talk to it'), h('div', { class: 'muted' }, `Uses the prompt you are working on (${prompt.name}).`), h('div', { class: 'small muted' }, `${creativityWord(gen.temperature)} · ${lengthLabel(gen.max_tokens)} replies · `, h('a', { href: '#/test' }, 'change'))),
    window.isSecureContext ? null : h('div', { class: 'notice' }, 'The microphone needs an https:// address. Open the lab over https on your phone.'),
    startBtn,
    h('div', { class: 'row between' }, h('span', { class: 'small muted' }, mode === 'server' ? 'Voice: Whisper on Groq (works on iPhone and Android)' : mode === 'browser' ? 'Voice: your browser' : 'Voice off: connect Groq in Settings, or type'), lang),
    h('div', { class: 'card stack' }, h('strong', {}, 'Optional: pretend to be…'), moodChips, card),
    open.items.length ? h('div', { class: 'small muted' }, 'You have an unfinished talk. ', h('a', { href: `#/results/${open.items[0].id}` }, 'Open it')) : null);
  drawMoods();
  return () => stop.fn && stop.fn();
}
