import { h, mount, toast, field } from '/lab/ui.js';
import { LANGS, ENGINE_NAMES, makePlayer, sampleFor, voiceSettings } from '/lab/voice.js';
import { A, lab, getConfig } from '../net.js';

const OTHER_LANGS = [['hi', 'Hindi'], ['en', 'English'], ['mr', 'Marathi'], ['gu', 'Gujarati'], ['ta', 'Tamil'], ['te', 'Telugu'], ['bn', 'Bengali'], ['kn', 'Kannada'], ['ml', 'Malayalam'], ['pa', 'Punjabi']];
const copy = (t) => navigator.clipboard?.writeText(t).then(() => toast('Copied')).catch(() => toast('Select and copy it manually', true));
const copyRow = (text) => h('div', { class: 'copyrow' }, h('code', {}, text), h('button', { onclick: () => copy(text) }, 'Copy'));

export async function render(root) {
  const box = h('div', { class: 'stack', style: 'gap:18px' });
  mount(root, h('h1', {}, 'Setup'), box);
  await load();

  async function load() {
    const [status, profile, cfg, voice] = await Promise.all([A('/status'), A('/profile'), getConfig(true), voiceSettings()]);
    mount(box, powerCard(profile), aiCard(status), businessCard(profile), voiceCard(voice), phoneCard(status), securityCard(cfg));
  }

  function powerCard(p) {
    return h('div', { class: 'card' }, h('label', { class: 'row between', style: 'font-weight:700' }, h('span', {}, 'Assistant is on', h('div', { class: 'small muted', style: 'font-weight:400' }, 'When off, nobody is answered by the AI.')),
      h('span', { class: 'switch' }, h('input', { type: 'checkbox', checked: p.assistant_on, 'aria-label': 'Assistant on', onchange: async (e) => { try { await A('/profile', { method: 'PUT', body: { ...p, assistant_on: e.target.checked } }); toast(e.target.checked ? 'Assistant is on' : 'Assistant is off'); load(); } catch (err) { toast(err.message, true); } } }), h('i', {}))));
  }

  function aiCard(s) {
    const key = h('input', { type: 'password', autocomplete: 'off', placeholder: s.ai_ready ? 'Paste a new Groq key to replace it' : 'gsk_…', 'aria-label': 'Groq API key' });
    const msg = h('div', { class: 'small', role: 'status' });
    const btn = h('button', { class: 'go' }, s.ai_ready ? 'Save key' : 'Connect');
    btn.addEventListener('click', async () => {
      if (!key.value.trim()) return toast('Paste your key first', true);
      btn.disabled = true; msg.textContent = 'Connecting…'; msg.style.color = '';
      try {
        await lab('/settings/providers/groq', { method: 'PUT', body: { api_key: key.value } });
        const t = await lab('/settings/providers/groq/test', { method: 'POST' });
        msg.textContent = t.message; msg.style.color = t.ok ? 'var(--pass)' : 'var(--fail)';
        if (t.ok) { toast('AI connected'); setTimeout(load, 600); }
      } catch (e) { msg.textContent = e.message; msg.style.color = 'var(--fail)'; }
      btn.disabled = false;
    });
    const form = h('div', { class: 'stack' }, !s.ai_ready ? h('div', { class: 'small muted' }, 'Get a free key at console.groq.com/keys. It is stored encrypted and is used to understand speech and to think.') : null, field('Groq API key', key), btn, msg);
    return h('div', { class: 'card stack' }, h('div', { class: 'row between' }, h('h2', { style: 'margin:0' }, 'Your AI'), h('span', { class: 'badge ' + (s.ai_ready ? 'done' : 'act') }, s.ai_ready ? 'Connected' : 'Needs a key')),
      s.ai_ready ? h('details', { class: 'more' }, h('summary', {}, 'Change key'), h('div', { style: 'margin-top:12px' }, form)) : form);
  }

  function businessCard(p) {
    const f = { business_name: h('input', { value: p.business_name, maxlength: 120, placeholder: 'e.g. Sharma Traders' }), owner_name: h('input', { value: p.owner_name, maxlength: 80, placeholder: 'Your name, e.g. Ramesh' }),
      about: h('textarea', { rows: 2, maxlength: 600, style: 'min-height:72px', placeholder: 'What you do, e.g. Wholesale rice and pulses in Indore, delivery in the city.' }, p.about),
      hours: h('input', { value: p.hours, maxlength: 200, placeholder: 'e.g. Mon to Sat, 9am to 8pm' }),
      faq: h('textarea', { rows: 5, maxlength: 3000, style: 'min-height:120px', placeholder: 'Only what it may tell callers, one per line:\nBasmati rice: Rs 90 per kg\nDelivery: free above Rs 5,000\nPayment: UPI or cash' }, p.faq),
      rules: h('textarea', { rows: 2, maxlength: 600, style: 'min-height:72px', placeholder: 'Anything else, e.g. Never agree to credit. Always ask for the shop name.' }, p.rules),
      owner_phone: h('input', { value: p.owner_phone, maxlength: 20, inputmode: 'tel', placeholder: 'Your own mobile number' }) };
    const greet = h('select', { 'aria-label': 'Greeting language' }, h('option', { value: 'hi', selected: p.languages[0] === 'hi' }, 'Hindi'), h('option', { value: 'en', selected: p.languages[0] !== 'hi' }, 'English'));
    const chosen = new Set(p.languages);
    const chips = h('div', { class: 'langs' });
    const drawChips = () => mount(chips, ...OTHER_LANGS.map(([c, l]) => h('span', { class: 'chip plain' + (chosen.has(c) ? ' on' : ''), role: 'button', onclick: () => { chosen.has(c) ? chosen.delete(c) : chosen.add(c); drawChips(); } }, l)));
    drawChips();
    const save = h('button', { class: 'go' }, 'Save');
    save.addEventListener('click', async () => {
      save.disabled = true;
      try {
        const langs = [greet.value, ...[...chosen].filter((c) => c !== greet.value)];
        await A('/profile', { method: 'PUT', body: { ...Object.fromEntries(Object.entries(f).map(([k, el]) => [k, el.value])), languages: langs, assistant_on: p.assistant_on } });
        toast('Saved'); load();
      } catch (e) { toast(e.message, true); save.disabled = false; }
    });
    return h('div', { class: 'card stack' }, h('h2', { style: 'margin:0' }, 'Your business'),
      field('Business name', f.business_name), field('Your name', f.owner_name), field('What you do', f.about), field('Opening hours', f.hours),
      field('Prices and answers it may give', f.faq, 'It will only state what is written here. For anything else it takes a message for you.'), field('Extra rules', f.rules),
      field('Your mobile number', f.owner_phone, 'Used for “Call back” and shown in the summary.'),
      field('It greets callers in', greet), h('div', { class: 'stack', style: 'gap:6px' }, h('div', { style: 'font-weight:600;font-size:14px' }, 'Languages it should understand'), chips), save);
  }

  function voiceCard(v) {
    const player = makePlayer(); const out = h('div', { class: 'small', role: 'status' });
    const set = async (body, msg) => { try { await lab('/settings/tts', { method: 'PUT', body }); if (msg) toast(msg); await load(); } catch (e) { toast(e.message, true); } };
    const FIELD = { google: 'google_key', chatterbox: 'deepinfra_key' };
    const hear = async (id, label) => { player.unlock(); out.textContent = `${label}: creating…`; out.style.color = '';
      try { const r = await player.say(sampleFor('hi-IN'), 'hi-IN', id); out.textContent = `${label}: ready in ${r.ms} ms`; await player.play(r.blob); } catch (e) { out.textContent = `${label}: ${e.message}`; out.style.color = 'var(--fail)'; } };
    const row = (id, title, detail, e) => {
      const key = e && !e.configured ? h('input', { type: 'password', autocomplete: 'off', placeholder: 'Paste API key', 'aria-label': `${title} API key` }) : null;
      return h('div', { class: 'stack', style: 'gap:8px;padding-top:12px;border-top:1px solid var(--line)' },
        h('label', { class: 'row', style: 'gap:10px;font-weight:700' }, h('input', { type: 'radio', name: 'voice', checked: v.active === id, disabled: e ? !e.configured : false, onchange: () => set({ active: id }, 'Voice changed') }), title),
        h('div', { class: 'small muted' }, detail),
        key ? h('div', { class: 'row', style: 'flex-wrap:nowrap' }, h('div', { class: 'grow' }, key), h('button', { class: 'go', onclick: () => (key.value.trim() ? set({ [FIELD[id]]: key.value }, `${title} connected`) : toast('Paste the key first', true)) }, 'Save key')) : null,
        e && e.configured ? h('div', { class: 'row' }, h('button', { onclick: () => hear(id, title) }, 'Hear a sample'), h('span', { class: 'small muted' }, `${e.used_chars.toLocaleString()} characters used this month · stops at ${e.cap_chars.toLocaleString()}`)) : null);
    };
    const [g, c] = v.engines;
    return h('div', { class: 'card stack' }, h('h2', { style: 'margin:0' }, 'Its voice'),
      h('div', { class: 'small muted' }, 'Pick who speaks to your callers. Google handles all major Indian languages. Chatterbox is cheaper but speaks only Hindi and English among Indian languages. Phone calls need Google or Chatterbox, and Hindi on the phone needs one of them.'),
      row('device', 'Your device’s voice (practice calls only)', 'Free. Sounds like your phone or browser. Cannot be used on real phone calls.'),
      row('google', 'Google', `Rs ${Math.round(g.price_per_m * 95 / 10) / 100} per 1,000 characters after the first ${g.free_chars / 1e6}M free each month. Ten Indian languages plus English.`, g),
      row('chatterbox', 'Chatterbox', `About Rs ${Math.round(c.price_per_m * 95) / 1000} per 1,000 characters. Hindi and English.`, c), out);
  }

  function phoneCard(s) {
    const id = h('input', { value: s.phone.auth_id, placeholder: 'Plivo Auth ID, e.g. MAXXXXXXXXXXXXXXXXXX', 'aria-label': 'Plivo Auth ID', autocomplete: 'off' });
    const token = h('input', { type: 'password', autocomplete: 'off', placeholder: s.phone.token_saved ? 'Saved. Paste a new token to replace it' : 'Plivo Auth Token', 'aria-label': 'Plivo Auth Token' });
    const number = h('input', { value: s.phone.number, placeholder: 'Your Plivo number, e.g. +91 80 4711 2233', 'aria-label': 'Plivo number', inputmode: 'tel' });
    const save = h('button', { class: 'go' }, 'Save phone line');
    save.addEventListener('click', async () => {
      save.disabled = true;
      try { await A('/phone', { method: 'PUT', body: { auth_id: id.value, auth_token: token.value, number: number.value } }); toast('Phone line saved'); load(); }
      catch (e) { toast(e.message, true); save.disabled = false; }
    });
    const step = (n, ...kids) => h('div', { class: 'step' }, h('span', { class: 'dot ' + 'skip' }, String(n)), h('div', { class: 'grow stack', style: 'gap:6px' }, ...kids));
    return h('div', { class: 'card stack' }, h('div', { class: 'row between' }, h('h2', { style: 'margin:0' }, 'Phone line'), h('span', { class: 'badge ' + (s.phone.connected ? 'done' : '') }, s.phone.connected ? 'Connected' : 'Not connected')),
      h('div', { class: 'small muted' }, 'Optional until you want real calls. Your phone forwards calls you miss to a Plivo number, and Munshi answers there. You can keep using the practice call without this.'),
      h('details', { class: 'more', open: !s.phone.connected }, h('summary', {}, s.phone.connected ? 'Phone line settings' : 'Connect a phone line'), h('div', { class: 'steps', style: 'margin-top:8px' },
        step(1, h('div', { class: 't' }, 'Get a Plivo number'), h('div', { class: 'd' }, 'Create a Plivo account, complete the Indian number verification (KYC), and rent a number.')),
        step(2, h('div', { class: 't' }, 'Point Plivo at Munshi'), h('div', { class: 'd' }, 'In Plivo, create an Application with these two addresses (method POST), and attach your number to it.'), h('div', { class: 'small muted' }, 'Answer URL'), copyRow(s.webhooks.answer), h('div', { class: 'small muted' }, 'Hangup URL'), copyRow(s.webhooks.hangup),
          s.webhooks.https ? null : h('div', { class: 'notice' }, 'This page is not on https, so Plivo may not be able to reach it.')),
        step(3, h('div', { class: 't' }, 'Paste your Plivo details'), h('div', { class: 'd' }, 'Munshi uses the token to check that calls really come from Plivo. It is stored encrypted.'), field('Auth ID', id), field('Auth Token', token), field('Your Plivo number', number), save),
        step(4, h('div', { class: 't' }, 'Forward your missed calls'), h('div', { class: 'd' }, 'On your phone, open the dialler and dial one of these. Codes can differ by operator (Jio, Airtel, Vi); if one does not work, ask your operator for “call forwarding”.'),
          h('div', { class: 'codes' }, ...s.forwarding.map((c) => h('div', { class: 'code' }, h('div', {}, h('div', { style: 'font-weight:600;font-size:14px' }, c.when), c.note ? h('div', { class: 'small muted' }, c.note) : null), h('div', { class: 'row' }, h('code', {}, c.dial), h('button', { onclick: () => copy(c.dial) }, 'Copy'))))),
          h('div', { class: 'small muted' }, 'Use the first three so your phone rings first. That is also how “always ring me” contacts reach you: the assistant only answers if you do not.')),
        step(5, h('div', { class: 't' }, 'Test it'), h('div', { class: 'd' }, 'Call your own number from another phone and let it ring out. The call appears under Calls after you hang up.')))));
  }

  function securityCard(cfg) {
    return h('div', { class: 'card stack' }, h('h2', { style: 'margin:0' }, 'Who can see this'),
      cfg.open_access || !cfg.auth_required ? h('div', { class: 'notice bad' }, 'Anyone with this link can read your calls and use your AI key. That is fine for testing with practice calls. Before real customer calls, turn on sign-in: in your host set LAB_OPEN_ACCESS=false and LAB_API_TOKENS to a long secret, then redeploy.')
        : h('div', { class: 'notice ok' }, 'Sign-in is on. Only people with the access token can use this.'));
  }
}
