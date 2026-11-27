// First-run guide for a new owner: six short steps, each saved as they go. Nothing is lost if they leave and come back.
import { h, mount } from '/lab/ui.js';
import { A } from '../net.js';
import { t, isHi } from '../i18n.js';
import { icon, toast, telLink } from '../kit.js';
import { shell, saveProfile, go } from '../shell.js';

const KINDS = [['kirana', ['किराना', 'Grocery'], 'A neighbourhood grocery store.'], ['sweets', ['मिठाई / रेस्तराँ', 'Sweets / food'], 'A sweet shop and food business.'], ['salon', ['सैलून', 'Salon'], 'A salon.'], ['clinic', ['क्लिनिक', 'Clinic'], 'A clinic.'],
  ['tailor', ['टेलर / कपड़े', 'Tailor / clothes'], 'A tailor and clothing shop.'], ['garage', ['गैराज', 'Garage'], 'A vehicle garage.'], ['coaching', ['कोचिंग', 'Coaching'], 'A coaching class.'], ['factory', ['फ़ैक्ट्री / थोक', 'Factory / wholesale'], 'A small factory or wholesale business.'], ['other', ['कुछ और', 'Something else'], '']];
const LANGS = [['hi', ['हिन्दी', 'Hindi']], ['en', ['English', 'English']], ['hing', ['Hinglish', 'Hinglish']]];
const ORDER = ['hi', 'en', 'hing'];
const TOTAL = 6;

export async function render(root, { param }) {
  const p = shell.profile;
  let step = Math.min(TOTAL, Math.max(1, parseInt(param, 10) || 1));
  const f = { owner: p.owner_name || '', biz: p.business_name === 'New business' ? '' : p.business_name || '', kind: '', open: p.open || '09:00', close: p.close || '21:00', addr: p.address || '', delivery: p.delivery || '',
    langs: new Set((p.languages || ['hi', 'en']).filter((c) => ORDER.includes(c))), rates: [{ name: '', price: '' }, { name: '', price: '' }, { name: '', price: '' }] };
  const body = h('div', { class: 'scroll start' }); const dots = h('div', { class: 'steps', role: 'progressbar', 'aria-valuemin': 1, 'aria-valuemax': TOTAL });
  const input = (label, key, extra = {}) => h('label', { class: 'f' }, label, h('input', { value: f[key], ...extra, oninput: (e) => { f[key] = e.target.value; } }));
  const number = shell.status && shell.status.phone && shell.status.phone.number; const code = number ? `**61*${number}**20#` : '';

  async function next(save) {
    try { if (save) await save(); } catch (e) { return toast(e.message, { bad: true }); }
    if (step < TOTAL) { step += 1; history.replaceState(null, '', `#/start/${step}`); paint(); body.scrollTop = 0; }
  }
  const back = () => { if (step > 1) { step -= 1; history.replaceState(null, '', `#/start/${step}`); paint(); } else go('#/calls'); };
  async function finish() { try { await saveProfile({ onboarded: true }); toast(t(['सब तैयार है!', 'All set!'])); go('#/calls'); } catch (e) { toast(e.message, { bad: true }); } }

  const steps = {
    1: () => ({ title: t(['आपकी दुकान', 'Your shop']), sub: t(['Munshi कॉल पर इन्हीं नामों से बात करेगा।', 'Munshi will use these names on calls.']),
      view: [h('div', { class: 'cardw form' }, input(t(['आपका नाम', 'Your name']), 'owner', { autocomplete: 'name', maxlength: 80 }), input(t(['दुकान का नाम', 'Shop name']), 'biz', { maxlength: 120 })),
        h('div', { class: 'f', style: 'margin:6px 2px 0' }, t(['आप क्या करते हैं?', 'What do you do?'])), h('div', { class: 'chips' }, ...KINDS.map(([k, l]) => h('button', { class: 'rchip' + (f.kind === k ? ' on' : ''), 'aria-pressed': String(f.kind === k), onclick: () => { f.kind = k; paint(); } }, t(l)))),
        h('p', { class: 'note' }, t(['Munshi कॉल करने वाले को बताता है कि वह AI सहायक है और बातचीत नोट की जाती है।', 'Munshi tells callers it is an AI assistant and that the conversation is noted.']))],
      ok: () => f.owner.trim() && f.biz.trim() || toast(t(['अपना और दुकान का नाम लिखें', 'Enter your name and the shop name']), { bad: true }),
      save: () => saveProfile({ owner_name: f.owner.trim(), business_name: f.biz.trim(), about: (KINDS.find((k) => k[0] === f.kind) || [])[2] || p.about || '' }) }),
    2: () => ({ title: t(['समय और पता', 'Timing and address']), sub: t(['ग्राहक पूछते हैं, तो Munshi यही बताएगा।', 'Munshi tells callers this when they ask.']),
      view: [h('div', { class: 'cardw form' }, h('div', { class: 'two' }, input(t(['दुकान खुलती है', 'Opens at']), 'open', { type: 'time' }), input(t(['बंद होती है', 'Closes at']), 'close', { type: 'time' })),
        input(t(['दुकान का पता', 'Shop address']), 'addr', { maxlength: 200, autocomplete: 'street-address' }), input(t(['होम डिलीवरी (अगर है)', 'Home delivery (if you have it)']), 'delivery', { maxlength: 300, placeholder: t(['जैसे: 3 किमी तक, ₹500 से ऊपर मुफ़्त', 'e.g. within 3 km, free above ₹500']) }))],
      ok: () => (f.open && f.close && f.addr.trim()) || toast(t(['समय और पता लिखें', 'Enter the timing and the address']), { bad: true }),
      save: () => saveProfile({ open: f.open, close: f.close, address: f.addr.trim(), delivery: f.delivery.trim() }) }),
    3: () => ({ title: t(['कुछ रेट जोड़ें', 'Add a few rates']), sub: t(['जो रेट यहाँ होंगे, सिर्फ़ वही Munshi बोलेगा। बाकी रेट बाद में फ़ोटो से भी जोड़ सकते हैं।', 'Munshi quotes only the rates you add here. You can add the rest later, even from a photo.']),
      view: [h('div', { class: 'cardw form' }, ...f.rates.map((r, i) => h('div', { class: 'two' }, h('label', { class: 'f' }, i === 0 ? t(['नाम', 'Item']) : '', h('input', { value: r.name, maxlength: 120, placeholder: [t(['आटा', 'Atta']), t(['चीनी', 'Sugar']), t(['चावल', 'Rice'])][i], 'aria-label': t(['नाम', 'Item']) + ' ' + (i + 1), oninput: (e) => { r.name = e.target.value; } })),
        h('label', { class: 'f' }, i === 0 ? t(['रेट', 'Rate']) : '', h('input', { value: r.price, maxlength: 40, placeholder: '44/kg', 'aria-label': t(['रेट', 'Rate']) + ' ' + (i + 1), oninput: (e) => { r.price = e.target.value; } }))))),
        h('button', { class: 'outline', onclick: () => go('#/know') }, t(['फ़ोटो या फ़ाइल से जोड़ें', 'Add from a photo or file instead']))],
      ok: () => true,
      save: async () => { let any = false; for (const r of f.rates) if (r.name.trim() && r.price.trim()) { try { await A('/board', { method: 'POST', body: { name: r.name.trim(), price: r.price.trim(), status: 'in_stock' } }); any = true; } catch (e) { if (e.status !== 409) throw e; any = true; } } if (any) await saveProfile({ mode: 'board' }); } }),
    4: () => ({ title: t(['भाषा और आवाज़', 'Language and voice']), sub: t(['Munshi किन भाषाओं में बात करे, और कैसी आवाज़ में।', 'Which languages Munshi speaks, and in what voice.']),
      view: [h('div', { class: 'cardw', style: 'display:flex;flex-direction:column;gap:10px' }, h('div', { class: 'f' }, t(['भाषाएँ', 'Languages'])), h('div', { class: 'langs' }, ...LANGS.map(([k, l]) => h('button', { class: 'lg' + (f.langs.has(k) ? ' on' : ''), onclick: () => { f.langs.has(k) ? f.langs.delete(k) : f.langs.add(k); paint(); } }, (f.langs.has(k) ? '✓ ' : '') + t(l))))),
        h('button', { class: 'pick', onclick: async () => { try { await saveProfile({ languages: ORDER.filter((c) => f.langs.has(c)) }); } catch { /* the voice screen still opens */ } go('#/voice?from=start'); } }, h('div', { class: 'o' }, icon('sound')), h('div', { style: 'flex:1' }, h('div', { class: 'f' }, t(['Munshi की आवाज़', "Munshi's voice"])), h('div', { style: 'font-size:16px;font-weight:600' }, t(['चुनें और सुनें', 'Choose and listen']))), h('span', { style: 'color:#8a9a95' }, icon('next')))],
      ok: () => f.langs.size > 0 || toast(t(['कम से कम एक भाषा चुनें', 'Pick at least one language']), { bad: true }),
      save: () => saveProfile({ languages: ORDER.filter((c) => f.langs.has(c)) }) }),
    5: () => ({ title: t(['कॉल Munshi तक पहुँचाएँ', 'Send missed calls to Munshi']), sub: t(['आपका फ़ोन पहले बजेगा। 20 सेकंड में न उठाएँ तो कॉल Munshi के पास जाएगी।', 'Your phone rings first. If you do not pick up in 20 seconds, the call goes to Munshi.']),
      view: [h('div', { class: 'codebox' }, h('b', { style: 'font-size:16px' }, t(['यह कोड डायल करें', 'Dial this code'])), h('div', { class: 'code' }, code || t(['आपका Munshi नंबर अभी तय नहीं है', 'Your Munshi number is not set yet'])),
        h('div', { style: 'font-size:12.5px;color:#9db5ac;margin-top:6px' }, code ? t(['यह कोड आपके Munshi नंबर से बना है। बंद करने के लिए ##61# डायल करें।', 'Made from your Munshi number. To switch off, dial ##61#.']) : t(['Munshi टीम से नंबर मिलते ही कोड यहाँ दिखेगा। तब तक आप आगे बढ़ सकते हैं।', 'The code appears here once the Munshi team gives you a number. You can carry on until then.'])),
        h('div', { class: 'row' }, h('a', { class: 'go', href: code ? telLink(code) : '#', 'aria-disabled': code ? null : 'true', onclick: async (e) => { if (!code) return e.preventDefault(); try { await saveProfile({ forwarding_done: true }); } catch { /* the dialer still opens */ } } }, t(['डायल करें', 'Dial now'])),
          h('button', { class: 'cp', onclick: async () => { if (!code) return; try { await navigator.clipboard.writeText(code); toast(t(['कोड कॉपी हुआ', 'Code copied'])); } catch { toast(code); } } }, t(['कॉपी', 'Copy']))))],
      ok: () => true, save: null }),
    6: () => ({ title: t(['एक कॉल आज़माएँ', 'Try a call']), sub: t(['खुद ग्राहक बनकर Munshi से बात करके देखें।', 'Talk to Munshi as if you were a customer.']),
      view: [h('button', { class: 'pick', onclick: async () => { await finish(); go('#/try'); } }, h('div', { class: 'o' }, icon('mic')), h('div', { style: 'flex:1' }, h('div', { style: 'font-size:17px;font-weight:700' }, t(['अभी आज़माएँ', 'Try it now'])), h('div', { class: 'f' }, t(['माइक से बोलें या लिखें', 'Speak or type'])), ), h('span', { style: 'color:#8a9a95' }, icon('next'))),
        h('div', { class: 'cardw', style: 'margin-top:14px;padding:14px 16px' },
          h('div', { style: 'font-size:14px;font-weight:600;margin-bottom:8px' }, t(['ऐसे बोलकर देखें:', 'Try saying:'])),
          h('div', { style: 'display:flex;flex-direction:column;gap:6px;font-size:14px;color:var(--muted)' },
            h('div', {}, '• ', t(['"आटे का रेट क्या है?"', '"What\'s the rate for atta?"'])),
            h('div', {}, '• ', t(['"दुकान कब तक खुली है?"', '"When does the shop close?"'])),
            h('div', {}, '• ', t(['"5 किलो चीनी भेज दो"', '"Send 5 kg sugar"'])))),
        h('p', { class: 'note' }, t(['बाद में सेटिंग में सब बदल सकते हैं।', 'You can change everything later in Settings.']))],
      ok: () => true, save: null }),
  };

  function paint() {
    const s = steps[step]();
    dots.setAttribute('aria-valuenow', String(step));
    mount(dots, ...Array.from({ length: TOTAL }, (_, i) => h('i', { class: i + 1 < step ? 'done' : i + 1 === step ? 'now' : '' })));
    mount(body, h('div', { class: 'stepno' }, t([`चरण ${step} / ${TOTAL}`, `Step ${step} of ${TOTAL}`])), h('h1', { class: 'page-title', style: 'margin-top:4px' }, s.title), h('div', { class: 'lead' }, s.sub), ...s.view);
    const last = step === TOTAL;
    mount(bar, last ? h('button', { class: 'big', onclick: finish }, t(['पूरा करें', 'Finish'])) : h('button', { class: 'big', onclick: () => { if (s.ok()) next(s.save); } }, t(['आगे', 'Next'])),
      step === 5 || step === 3 ? h('button', { class: 'link skip', onclick: () => next(null) }, t(['बाद में', 'Skip for now'])) : null);
  }
  const bar = h('div', { class: 'bar start-bar' });
  mount(root, h('div', { class: 'col' }, h('div', { class: 'sub-top' }, h('button', { class: 'btn-ic', 'aria-label': t(['वापस', 'Back']), onclick: back }, icon('back', 28)), h('h1', {}, 'Munshi'), dots), body, bar));
  paint();
}
