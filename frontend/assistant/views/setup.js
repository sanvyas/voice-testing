import { h, mount, toast, field } from '/lab/ui.js';
import { A, ic, ICONS } from '../net.js';

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
  mount(root, h('div', {}, h('h1', { class: 'title' }, 'Setup'), h('div', { class: 'sub' }, 'About 2 minutes, once. Change anything later.')), box);
  let openId = new URLSearchParams(location.hash.split('?')[1] || '').get('open') || '';
  await load();

  async function load() {
    const [status, profile] = await Promise.all([A('/status'), A('/profile')]);
    const ready = [status.profile_ready, status.phone.connected, status.assistant_on];
    const done = ready.filter(Boolean).length;
    const left = ['Describe your business', 'Get your Munshi number', 'Switch the assistant on'][ready.findIndex((r) => !r)];
    const saveProfile = async (patch, msg) => { try { await A('/profile', { method: 'PUT', body: { ...profile, ...patch } }); if (msg) toast(msg); changed(); await load(); } catch (e) { toast(e.message, true); } };

    const panel = (id, icon, title, detail, ok, body) => {
      const el = h('details', { class: 'panel card tight', open: openId === id }, h('summary', { class: 'rowlink', style: 'border-top:0' },
        h('span', { class: 'ico' + (ok ? '' : ' warn') }, ic(ok ? ICONS.check : icon)), h('div', { class: 'grow' }, h('div', { class: 't' }, title), h('div', { class: 'd', style: ok ? '' : 'color:var(--warn);font-weight:600' }, detail)), ic(ICONS.next, [], true)), h('div', { class: 'inner' }, body));
      el.addEventListener('toggle', () => { if (el.open) openId = id; else if (openId === id) openId = ''; });
      return el;
    };

    mount(box,
      h('div', { class: 'hero', style: 'gap:12px;padding:18px 20px' }, h('div', { class: 'row between', style: 'align-items:baseline' }, h('div', { style: 'font:700 22px var(--display)' }, `${done} of 3 ready`), h('div', { class: 'small', style: 'color:#C9D6D1' }, left ? `Next: ${left}` : 'All set')),
        h('div', { class: 'progress' }, h('i', { style: `width:${Math.round(done * 100 / 3)}%` }))),
      status.business.active ? null : h('div', { class: 'notice bad' }, [h('b', {}, 'Your account is paused. '), 'Munshi is not answering your calls. Contact your Munshi administrator.']),
      h('label', { class: 'card row between', style: 'font-weight:700;flex-wrap:nowrap' }, h('span', {}, 'Assistant is on', h('div', { class: 'small muted', style: 'font-weight:400' }, 'When off, nobody is answered by the AI.')),
        h('input', { type: 'checkbox', class: 'sw', role: 'switch', checked: profile.assistant_on, 'aria-label': 'Assistant on', onchange: (e) => saveProfile({ assistant_on: e.target.checked }, e.target.checked ? 'Assistant is on' : 'Assistant is off') })),
      h('div', { class: 'stack', style: 'gap:10px' }, h('h2', { class: 'sec' }, 'When you miss a call'),
        ...MODES.map(([id, title, tag, text]) => h('label', { class: 'mode' + (profile.mode === id ? ' on' : '') }, h('input', { type: 'radio', class: 'rd', name: 'mode', checked: profile.mode === id, onchange: () => saveProfile({ mode: id }, `Now: ${title}`) }),
          h('div', {}, h('div', { class: 't' }, title, tag ? h('span', { class: 'badge ' + (tag === 'Recommended' ? 'ok' : '') }, tag) : null), h('div', { class: 'd' }, text)))),
        profile.mode === 'board' && !status.board.items ? h('div', { class: 'notice' }, ['Your board is empty. ', h('a', { href: '#/board', style: 'font-weight:700;text-decoration:underline' }, 'Add what you sell')]) : null),
      status.role === 'admin' ? h('a', { href: '/portal/', class: 'linkcard' }, h('span', { class: 'ico' }, ic(ICONS.sliders)), h('div', { class: 'grow' }, h('div', { style: 'font-weight:600' }, 'Open the portal'), h('div', { class: 'small muted' }, 'All businesses, prompts, connections and costs')), ic(ICONS.next, [], true)) : null,
      panel('business', ICONS.board, 'Your business', status.profile_ready ? `${profile.business_name} · ${profile.owner_name}` : 'Add your name and business name', status.profile_ready, businessBody(profile, saveProfile)),
      h('a', { href: '#/board', class: 'linkcard' }, h('span', { class: 'ico' }, ic(ICONS.board)), h('div', { class: 'grow' }, h('div', { style: 'font-weight:600' }, "Today's board"), h('div', { class: 'small muted' }, status.board.items ? `${status.board.items} items${status.board.sold_out ? ` · ${status.board.sold_out} sold out` : ''}` : 'Prices and stock the assistant may share')), ic(ICONS.next, [], true)),
      panel('phone', ICONS.phone, 'Your Munshi number', status.phone.connected ? status.phone.number : 'Not assigned yet. Your Munshi administrator will add it', status.phone.connected, phoneBody(status)),
      panel('whatsapp', ICONS.chat, 'Instant WhatsApp reply', status.whatsapp.connected ? (profile.whatsapp_on ? 'On: callers get your details after a missed call' : 'Available, switched off') : 'Not available on your account yet', status.whatsapp.connected, whatsappBody(status, profile, saveProfile)));
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

  function whatsappBody(s, p, saveProfile) {
    return [h('div', { class: 'small muted' }, 'After a missed call the caller gets an instant WhatsApp message with your address, hours and today’s board. It is the cheapest way to answer, and callers do not need to wait or repeat themselves.'),
      s.whatsapp.connected ? h('label', { class: 'row between', style: 'font-weight:600;flex-wrap:nowrap' }, 'Send it after missed calls', h('input', { type: 'checkbox', class: 'sw', role: 'switch', checked: p.whatsapp_on, 'aria-label': 'Send the WhatsApp reply', onchange: (e) => saveProfile({ whatsapp_on: e.target.checked }) }))
        : h('div', { class: 'notice' }, 'Your Munshi administrator has not connected WhatsApp yet.')];
  }

  function phoneBody(s) {
    if (!s.phone.connected) return [h('div', { class: 'small muted' }, 'Munshi gives each business its own phone number. Your phone forwards the calls you miss to it. Your administrator will add the number here.')];
    return [h('div', { class: 'small muted' }, 'This is the number your phone forwards missed calls to. Dial one of these codes on your phone, once. Your phone still rings first, so people you always answer reach you. Codes can differ by operator.'),
      h('div', { class: 'small', style: 'font-weight:700' }, 'Your Munshi number'), copyRow(s.phone.number),
      ...s.forwarding.map((c) => h('div', { class: 'stack', style: 'gap:4px' }, h('div', { class: 'small' }, c.when), copyRow(c.dial))),
      h('div', { class: 'small', style: 'font-weight:700' }, 'Test it'), h('div', { class: 'small muted' }, 'Call your own number from another phone and let it ring out. The call appears under Calls after you hang up.')];
  }
}
