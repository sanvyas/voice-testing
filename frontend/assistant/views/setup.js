import { h, mount, toast, field } from '/lab/ui.js';
import { LANGS, ENGINE_NAMES, makePlayer, sampleFor, voiceSettings } from '/lab/voice.js';
import { A, lab, getConfig, ic, ICONS } from '../net.js';

const OTHER_LANGS = [['hi', 'Hindi'], ['en', 'English'], ['mr', 'Marathi'], ['gu', 'Gujarati'], ['ta', 'Tamil'], ['te', 'Telugu'], ['bn', 'Bengali'], ['kn', 'Kannada'], ['ml', 'Malayalam'], ['pa', 'Punjabi']];
const MODES = [
  ['reply', 'WhatsApp reply only', 'Lowest cost', 'The caller instantly gets your address, hours and prices on WhatsApp. No voice, nothing to misunderstand.'],
  ['message', 'Take a message', 'Recommended', 'Munshi answers in Hindi or English, listens, and sends you a summary with what to do. It never quotes a price.'],
  ['board', "Answer from Today's board", '', 'Also answers price and availability, but only for items on your board. Anything else becomes a message for you.'],
];
const copy = (t) => navigator.clipboard?.writeText(t).then(() => toast('Copied')).catch(() => toast('Select and copy it manually', true));
const copyRow = (text) => h('div', { class: 'copyrow' }, h('code', {}, text), h('button', { class: 'plain', onclick: () => copy(text) }, 'Copy'));
const changed = () => window.dispatchEvent(new Event('munshi-changed'));

export async function render(root) {
  const box = h('div', { class: 'stack', style: 'gap:16px' });
  mount(root, h('div', {}, h('h1', { class: 'title' }, 'Setup'), h('div', { class: 'sub' }, 'About 3 minutes, once. Change anything later.')), box);
  let openId = new URLSearchParams(location.hash.split('?')[1] || '').get('open') || '';
  await load();

  async function load() {
    const [status, profile, cfg, voice] = await Promise.all([A('/status'), A('/profile'), getConfig(true), voiceSettings()]);
    const ready = [status.ai_ready, status.profile_ready, status.voice.server_voice_ready, status.phone.connected];
    const done = ready.filter(Boolean).length;
    const left = ['Connect your AI', 'Describe your business', 'Pick a voice', 'Connect the phone line'][ready.findIndex((r) => !r)];
    const saveProfile = async (patch, msg) => { try { await A('/profile', { method: 'PUT', body: { ...profile, ...patch } }); if (msg) toast(msg); changed(); await load(); } catch (e) { toast(e.message, true); } };

    const panel = (id, icon, title, detail, ok, body) => {
      const el = h('details', { class: 'panel card tight', open: openId === id }, h('summary', { class: 'rowlink', style: 'border-top:0' },
        h('span', { class: 'ico' + (ok ? '' : ' warn') }, ic(ok ? ICONS.check : icon)), h('div', { class: 'grow' }, h('div', { class: 't' }, title), h('div', { class: 'd', style: ok ? '' : 'color:var(--warn);font-weight:600' }, detail)), ic(ICONS.next, [], true)), h('div', { class: 'inner' }, body));
      el.addEventListener('toggle', () => { if (el.open) openId = id; else if (openId === id) openId = ''; });
      return el;
    };

    mount(box,
      h('div', { class: 'hero', style: 'gap:12px;padding:18px 20px' }, h('div', { class: 'row between', style: 'align-items:baseline' }, h('div', { style: 'font:700 22px var(--display)' }, `${done} of 4 ready`), h('div', { class: 'small', style: 'color:#C9D6D1' }, left ? `Next: ${left}` : 'All set')),
        h('div', { class: 'progress' }, h('i', { style: `width:${done * 25}%` }))),
      h('label', { class: 'card row between', style: 'font-weight:700;flex-wrap:nowrap' }, h('span', {}, 'Assistant is on', h('div', { class: 'small muted', style: 'font-weight:400' }, 'When off, nobody is answered by the AI.')),
        h('input', { type: 'checkbox', class: 'sw', role: 'switch', checked: profile.assistant_on, 'aria-label': 'Assistant on', onchange: (e) => saveProfile({ assistant_on: e.target.checked }, e.target.checked ? 'Assistant is on' : 'Assistant is off') })),
      h('div', { class: 'stack', style: 'gap:10px' }, h('h2', { class: 'sec' }, 'When you miss a call'),
        ...MODES.map(([id, title, tag, text]) => h('label', { class: 'mode' + (profile.mode === id ? ' on' : '') }, h('input', { type: 'radio', class: 'rd', name: 'mode', checked: profile.mode === id, onchange: () => saveProfile({ mode: id }, `Now: ${title}`) }),
          h('div', {}, h('div', { class: 't' }, title, tag ? h('span', { class: 'badge ' + (tag === 'Recommended' ? 'ok' : '') }, tag) : null), h('div', { class: 'd' }, text)))),
        profile.mode === 'board' && !status.board.items ? h('div', { class: 'notice' }, ['Your board is empty. ', h('a', { href: '#/board', style: 'font-weight:700;text-decoration:underline' }, 'Add what you sell')]) : null),
      h('a', { href: '/portal/', class: 'linkcard' }, h('span', { class: 'ico' }, ic(ICONS.sliders)), h('div', { class: 'grow' }, h('div', { style: 'font-weight:600' }, 'Open the portal'), h('div', { class: 'small muted' }, 'Costs, prompts, connections and the full board on a bigger screen')), ic(ICONS.next, [], true)),
      panel('ai', ICONS.sliders, 'Your AI', status.ai_ready ? 'Connected' : 'Needs a key', status.ai_ready, aiBody(status)),
      panel('business', ICONS.board, 'Your business', status.profile_ready ? `${profile.business_name} · ${profile.owner_name}` : 'Add your name and business name', status.profile_ready, businessBody(profile, saveProfile)),
      h('a', { href: '#/board', class: 'linkcard' }, h('span', { class: 'ico' }, ic(ICONS.board)), h('div', { class: 'grow' }, h('div', { style: 'font-weight:600' }, "Today's board"), h('div', { class: 'small muted' }, status.board.items ? `${status.board.items} items${status.board.sold_out ? ` · ${status.board.sold_out} sold out` : ''}` : 'Prices and stock the assistant may share')), ic(ICONS.next, [], true)),
      panel('voice', ICONS.mic, 'Its voice', status.voice.server_voice_ready ? `${status.voice.label}` : 'Only your device voice. Phone calls need Google or Chatterbox', status.voice.server_voice_ready, voiceBody(voice)),
      panel('whatsapp', ICONS.chat, 'Instant WhatsApp reply', status.whatsapp.connected ? (profile.whatsapp_on ? 'On: callers get your details after a missed call' : 'Connected, switched off') : 'Not connected yet', status.whatsapp.connected, whatsappBody(status, profile, saveProfile)),
      panel('phone', ICONS.phone, 'Phone line', status.phone.connected ? status.phone.number : 'Not connected yet', status.phone.connected, phoneBody(status)),
      h('div', { class: 'notice ' + (cfg.open_access || !cfg.auth_required ? 'bad' : 'ok') }, cfg.open_access || !cfg.auth_required
        ? [h('b', {}, 'Anyone with this link can see your calls. '), 'Fine for testing with practice calls. Before real customers call, turn on sign-in: in your host set LAB_OPEN_ACCESS=false and LAB_API_TOKENS to a long secret, then redeploy.'] : [h('b', {}, 'Sign-in is on. '), 'Only people with the access token can use this.']));
  }

  function aiBody(s) {
    const key = h('input', { type: 'password', autocomplete: 'off', placeholder: s.ai_ready ? 'Paste a new Groq key to replace it' : 'gsk_…', 'aria-label': 'Groq API key' });
    const msg = h('div', { class: 'small', role: 'status' });
    const btn = h('button', { class: 'btn' }, s.ai_ready ? 'Save key' : 'Connect');
    btn.addEventListener('click', async () => {
      if (!key.value.trim()) return toast('Paste your key first', true);
      btn.disabled = true; msg.textContent = 'Connecting…'; msg.style.color = '';
      try {
        await lab('/settings/providers/groq', { method: 'PUT', body: { api_key: key.value } });
        const t = await lab('/settings/providers/groq/test', { method: 'POST' });
        msg.textContent = t.message; msg.style.color = t.ok ? 'var(--primary)' : 'var(--danger)';
        if (t.ok) { toast('AI connected'); setTimeout(load, 600); }
      } catch (e) { msg.textContent = e.message; msg.style.color = 'var(--danger)'; }
      btn.disabled = false;
    });
    return [h('div', { class: 'small muted' }, 'Get a free key at console.groq.com/keys. It is stored encrypted and is used to understand speech and to think.'), field('Groq API key', key), btn, msg];
  }

  function businessBody(p, saveProfile) {
    const f = { business_name: h('input', { type: 'text', value: p.business_name, maxlength: 120, placeholder: 'e.g. Sharma Traders' }), owner_name: h('input', { type: 'text', value: p.owner_name, maxlength: 80, placeholder: 'Your name, e.g. Ramesh' }),
      about: h('textarea', { rows: 2, maxlength: 600, placeholder: 'What you do, e.g. Wholesale rice and pulses in Indore.' }, p.about),
      address: h('input', { type: 'text', value: p.address, maxlength: 200, placeholder: 'Shop address (shared in the WhatsApp reply)' }), hours: h('input', { type: 'text', value: p.hours, maxlength: 200, placeholder: 'e.g. Mon to Sat, 9am to 8pm' }),
      faq: h('textarea', { rows: 4, maxlength: 3000, placeholder: 'Only used in “Today’s board” mode, one per line:\nDelivery: free above Rs 5,000\nPayment: UPI or cash' }, p.faq),
      rules: h('textarea', { rows: 2, maxlength: 600, placeholder: 'e.g. Never agree to credit. Always ask for the shop name.' }, p.rules), owner_phone: h('input', { type: 'tel', value: p.owner_phone, maxlength: 20, placeholder: 'Your own mobile number' }) };
    const greet = h('select', { 'aria-label': 'Greeting language' }, h('option', { value: 'hi', selected: p.languages[0] === 'hi' }, 'Hindi'), h('option', { value: 'en', selected: p.languages[0] !== 'hi' }, 'English'));
    const chosen = new Set(p.languages); const chips = h('div', { class: 'pills', style: 'flex-wrap:wrap;overflow:visible' });
    const drawChips = () => mount(chips, ...OTHER_LANGS.map(([c, l]) => h('button', { class: 'pill' + (chosen.has(c) ? ' on' : ''), onclick: () => { chosen.has(c) ? chosen.delete(c) : chosen.add(c); drawChips(); } }, l)));
    drawChips();
    const save = h('button', { class: 'btn' }, 'Save');
    save.addEventListener('click', async () => { save.disabled = true; await saveProfile({ ...Object.fromEntries(Object.entries(f).map(([k, el]) => [k, el.value])), languages: [greet.value, ...[...chosen].filter((c) => c !== greet.value)] }, 'Saved'); save.disabled = false; });
    return [field('Business name', f.business_name), field('Your name', f.owner_name), field('What you do', f.about), field('Address', f.address), field('Opening hours', f.hours), field('Your mobile number', f.owner_phone, 'Used for “Call back” and for test messages.'),
      field('Other answers it may give', f.faq, 'Used only in “Today’s board” mode.'), field('Extra rules', f.rules), field('It greets callers in', greet), h('div', { class: 'stack', style: 'gap:6px' }, h('div', { style: 'font-weight:600;font-size:14px' }, 'Languages it should understand'), chips), save];
  }

  function voiceBody(v) {
    const player = makePlayer(); const out = h('div', { class: 'small', role: 'status' });
    const set = async (body, msg) => { try { await lab('/settings/tts', { method: 'PUT', body }); if (msg) toast(msg); await load(); } catch (e) { toast(e.message, true); } };
    const FIELD = { google: 'google_key', chatterbox: 'deepinfra_key' };
    const hear = async (id, label) => { player.unlock(); out.textContent = `${label}: creating…`; out.style.color = '';
      try { const r = await player.say(sampleFor('hi-IN'), 'hi-IN', id); out.textContent = `${label}: ready in ${r.ms} ms`; await player.play(r.blob); } catch (e) { out.textContent = `${label}: ${e.message}`; out.style.color = 'var(--danger)'; } };
    const row = (id, title, detail, e) => {
      const key = e && !e.configured ? h('input', { type: 'password', autocomplete: 'off', placeholder: 'Paste API key', 'aria-label': `${title} API key` }) : null;
      return h('div', { class: 'stack', style: 'gap:8px;padding-top:10px;border-top:1px solid var(--line)' },
        h('label', { class: 'row', style: 'gap:10px;font-weight:700;flex-wrap:nowrap' }, h('input', { type: 'radio', class: 'rd', name: 'voice', checked: v.active === id, disabled: e ? !e.configured : false, onchange: () => set({ active: id }, 'Voice changed') }), title),
        h('div', { class: 'small muted' }, detail),
        key ? h('div', { class: 'row', style: 'flex-wrap:nowrap' }, h('div', { class: 'grow' }, key), h('button', { class: 'btn', style: 'width:auto', onclick: () => (key.value.trim() ? set({ [FIELD[id]]: key.value }, `${title} connected`) : toast('Paste the key first', true)) }, 'Save')) : null,
        e && e.configured ? h('div', { class: 'row' }, h('button', { class: 'plain', onclick: () => hear(id, title) }, 'Hear a sample'), h('span', { class: 'small muted' }, `${e.used_chars.toLocaleString()} characters this month · limit ${e.cap_chars.toLocaleString()}`)) : null);
    };
    const [g, c] = v.engines;
    return [h('div', { class: 'small muted' }, 'Pick who speaks to your callers. Phone calls need Google or Chatterbox. Google covers all major Indian languages; Chatterbox is cheaper but Hindi and English only.'),
      row('device', 'Your device’s voice', 'Free. Practice calls only: it cannot be used on real phone calls.'),
      row('google', 'Google', `Rs ${Math.round(g.price_per_m * 95 / 10) / 100} per 1,000 characters after the first ${g.free_chars / 1e6}M free each month. Ten Indian languages plus English.`, g),
      row('chatterbox', 'Chatterbox', `About Rs ${Math.round(c.price_per_m * 95) / 1000} per 1,000 characters. Hindi and English.`, c), out];
  }

  function whatsappBody(s, p, saveProfile) {
    const w = s.whatsapp;
    const pid = h('input', { type: 'text', value: w.phone_number_id, inputmode: 'numeric', placeholder: 'Phone number ID from Meta', 'aria-label': 'WhatsApp phone number ID' });
    const tok = h('input', { type: 'password', autocomplete: 'off', placeholder: w.token_saved ? 'Saved. Paste a new token to replace it' : 'Access token', 'aria-label': 'WhatsApp access token' });
    const tpl = h('input', { type: 'text', value: w.template, 'aria-label': 'Template name' });
    const save = h('button', { class: 'btn' }, 'Save');
    save.addEventListener('click', async () => { save.disabled = true; try { await A('/whatsapp', { method: 'PUT', body: { phone_number_id: pid.value, access_token: tok.value, template: tpl.value, language: w.language } }); toast('WhatsApp saved'); await load(); } catch (e) { toast(e.message, true); save.disabled = false; } });
    const test = h('button', { class: 'btn ghost' }, 'Send a test to my own number');
    test.addEventListener('click', async () => { test.disabled = true; try { const r = await A('/whatsapp/test', { method: 'POST' }); toast(`Sent to ${r.to}`); } catch (e) { toast(e.message, true); } test.disabled = false; });
    return [h('div', { class: 'small muted' }, 'After a missed call the caller gets an instant WhatsApp message with your address, hours and today’s board. It is sent through the WhatsApp Business Cloud API, which charges a small fee per message. Not yet tested with a live Meta account.'),
      h('label', { class: 'row between', style: 'font-weight:600;flex-wrap:nowrap' }, 'Send it after missed calls', h('input', { type: 'checkbox', class: 'sw', role: 'switch', checked: p.whatsapp_on, 'aria-label': 'Send the WhatsApp reply', onchange: (e) => saveProfile({ whatsapp_on: e.target.checked }) })),
      h('div', { class: 'stack', style: 'gap:6px' }, h('div', { class: 'small', style: 'font-weight:700' }, 'One time, in Meta Business Manager'), h('div', { class: 'small muted' }, `Create a message template named ${w.template}, category Utility, language English, with this text. Meta must approve it before messages can be sent.`), copyRow(w.template_body)),
      field('Phone number ID', pid), field('Access token', tok), field('Template name', tpl), save, w.connected ? test : null, w.token_unreadable ? h('div', { class: 'notice' }, 'The saved token can no longer be read. Paste it again.') : null];
  }

  function phoneBody(s) {
    const id = h('input', { type: 'text', value: s.phone.auth_id, placeholder: 'Plivo Auth ID', 'aria-label': 'Plivo Auth ID', autocomplete: 'off' });
    const token = h('input', { type: 'password', autocomplete: 'off', placeholder: s.phone.token_saved ? 'Saved. Paste a new token to replace it' : 'Plivo Auth Token', 'aria-label': 'Plivo Auth Token' });
    const number = h('input', { type: 'tel', value: s.phone.number, placeholder: 'Your Plivo number, e.g. +91 80 4711 2233', 'aria-label': 'Plivo number' });
    const save = h('button', { class: 'btn' }, 'Save phone line');
    save.addEventListener('click', async () => { save.disabled = true; try { await A('/phone', { method: 'PUT', body: { auth_id: id.value, auth_token: token.value, number: number.value } }); toast('Phone line saved'); await load(); } catch (e) { toast(e.message, true); save.disabled = false; } });
    return [h('div', { class: 'small muted' }, 'Optional until you want real calls. Your phone forwards calls you miss to a Plivo number and Munshi answers there. It is turn based, with a short pause after the caller stops. Not yet tested with a live Plivo account.'),
      h('div', { class: 'small', style: 'font-weight:700' }, '1. In Plivo (India region), rent a number and make an Application with these, method POST'), h('div', { class: 'small muted' }, 'Answer URL'), copyRow(s.webhooks.answer), h('div', { class: 'small muted' }, 'Hangup URL'), copyRow(s.webhooks.hangup),
      s.webhooks.https ? null : h('div', { class: 'notice' }, 'This page is not on https, so Plivo may not reach it.'),
      h('div', { class: 'small', style: 'font-weight:700' }, '2. Paste your Plivo details'), field('Auth ID', id), field('Auth Token', token), field('Your Plivo number', number), save,
      h('div', { class: 'small', style: 'font-weight:700' }, '3. Forward your missed calls (one time)'), h('div', { class: 'small muted' }, 'Dial one of these on your phone. Your phone still rings first, so people you always answer reach you. Codes can differ by operator.'),
      ...s.forwarding.map((c) => h('div', { class: 'stack', style: 'gap:4px' }, h('div', { class: 'small' }, c.when), copyRow(c.dial))),
      h('div', { class: 'small', style: 'font-weight:700' }, '4. Test it'), h('div', { class: 'small muted' }, 'Call your own number from another phone and let it ring out. The call appears under Calls after you hang up.')];
  }
}
