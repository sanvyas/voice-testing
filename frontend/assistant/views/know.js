// Shop info: what Munshi may say. Rates and shop details, with how fresh each one is. Add or change them by photo, file, voice or typing, and check before saving.
import { h, mount } from '/lab/ui.js';
import { A, apiForm } from '../net.js';
import { t, getLang, money, freshness } from '../i18n.js';
import { icon, sheet, toast } from '../kit.js';
import { shrink } from '../photo.js';
import { makeListener, canRecord } from '../listener.js';

const FACT = { delivery: ['होम डिलीवरी', 'Home delivery'], address: ['दुकान का पता', 'Shop address'], hours: ['समय', 'Timing'], rules: ['नियम', 'Rules'] };
const FILE = (blob) => `speech.${blob.type.includes('mp4') ? 'm4a' : blob.type.includes('ogg') ? 'ogg' : 'webm'}`;

/** "Atta, 42" / "Toor dal 165/kg" per line -> items. */
function parseList(text) {
  const out = [];
  for (const line of text.split(/\r?\n/).slice(0, 200)) {
    const m = line.trim().match(/^(.*?)[\s,;:\t-]+(?:rs\.?|₹)?\s*(\d[\d.,]*(?:\s*\/\s*[A-Za-z]+)?)\s*$/i);
    if (m && m[1].trim()) out.push({ name: m[1].trim().replace(/^["']|["']$/g, ''), price: m[2].replace(/\s+/g, ''), status: 'in_stock' });
  }
  return out;
}

export async function render(root) {
  let shop = await A('/shop'); let pending = null; let busy = '';
  const body = h('div', { class: 'scroll pad-fab' }); let alive = true; const listener = makeListener();

  const rateRow = (r) => h('div', { class: 'krow' }, h('div', { class: 'main' }, h('div', { class: 'n' }, r.name), h('div', { class: 'f' + (r.stale ? ' stale' : '') }, r.status === 'sold_out' ? t(['खत्म', 'Sold out']) : freshness(r.age_hours))),
    h('b', { class: 'p' }, money(r.price)), r.stale ? h('button', { class: 'pill-btn warn', onclick: () => confirm(r.id) }, t(['सही है', 'Still right'])) : null);
  const factRow = (f) => h('div', { class: 'krow' }, h('div', { class: 'main' }, h('div', { class: 'n' }, t(FACT[f.field])), h('div', { class: 'tx' }, f.text), h('div', { class: 'f' + (f.stale ? ' stale' : '') }, freshness(f.age_hours))),
    f.stale ? h('button', { class: 'pill-btn warn', onclick: () => confirm(f.id) }, t(['सही है', 'Still right'])) : null);
  async function confirm(id) { try { shop = await A('/shop/confirm', { method: 'POST', body: { id } }); toast(t(['पक्का किया', 'Confirmed'])); draw(); } catch (e) { toast(e.message, { bad: true }); } }

  function pendingCard() {
    if (busy) return h('div', { class: 'pendcard' }, h('div', { class: 'from' }, busy));
    if (!pending) return null;
    const rows = [...(pending.rates || []).map((r) => h('div', { class: 'r' }, h('span', {}, r.name), h('b', {}, r.old_price && r.old_price !== r.price ? h('s', {}, money(r.old_price)) : null, money(r.price)))),
      ...(pending.facts || []).map((f) => h('div', { class: 'r' }, h('span', {}, t(FACT[f.field])), h('b', { style: 'text-align:right;max-width:60%;font-size:15px' }, f.text)))];
    return h('div', { class: 'pendcard' }, h('div', { class: 'from' }, pending.from), ...rows,
      h('div', { class: 'btns' }, h('button', { class: 'big', style: 'flex:1;min-height:54px;border-radius:14px;font-size:16px', onclick: save }, t(['सही है, सेव करें', 'Correct, save'])), h('button', { class: 'link', style: 'padding:0 18px', onclick: () => { pending = null; draw(); } }, t(['रद्द', 'Cancel']))));
  }
  async function save() {
    try {
      if (pending.via === 'items') await A('/board/apply', { method: 'POST', body: { items: pending.items } });
      else await A('/shop/apply', { method: 'POST', body: { rates: pending.rates, facts: pending.facts } });
      pending = null; toast(t(['जानकारी सेव हुई', 'Knowledge saved'])); shop = await A('/shop'); window.dispatchEvent(new Event('munshi-changed')); draw();
    } catch (e) { toast(e.message, { bad: true }); }
  }

  function draw() {
    const staleItems = [...shop.rates.filter((r) => r.stale).map(rateRow), ...shop.facts.filter((f) => f.stale).map(factRow)];
    const group = (title, rows, cls = '') => rows.length ? h('div', { class: 'group ' + cls }, h('h3', {}, title), h('div', { class: 'gbox' }, ...rows)) : null;
    mount(body, h('h1', { class: 'page-title' }, t(['दुकान की जानकारी', 'Shop info'])),
      h('div', { class: 'lead' }, t(['Munshi सिर्फ़ यही बोलता है। जो यहाँ नहीं है, उसपर कहेगा कि आप कॉल करेंगे।', 'Munshi says only this. For anything missing, it says you will call back.'])),
      pendingCard(),
      group(t([`फिर से जाँचें · ${staleItems.length} पुरानी`, `Recheck · ${staleItems.length} out of date`]), staleItems, 'stale'),
      group(t(['रेट', 'Rates']), shop.rates.filter((r) => !r.stale).map(rateRow)),
      group(t(['डिलीवरी', 'Delivery']), shop.facts.filter((f) => !f.stale && f.group === 'delivery').map(factRow)),
      group(t(['पता, समय और नियम', 'Address, hours and rules']), shop.facts.filter((f) => !f.stale && f.group === 'shop').map(factRow)),
      !shop.rates.length && !shop.facts.length ? h('div', { class: 'empty' }, h('b', {}, t(['अभी कुछ नहीं जोड़ा', 'Nothing added yet'])), h('p', {}, t(['नीचे “जानकारी जोड़ें” दबाएँ: रेट की फ़ोटो खींचें या बोलकर बताएँ।', 'Tap “Add info” below: take a photo of your rate list or just say it.']))) : null);
  }

  // ---- adding ----
  const picker = (accept, capture) => { const i = h('input', { type: 'file', accept, hidden: true }); if (capture) i.setAttribute('capture', 'environment'); return i; };
  function fromPhoto(kind) {
    const input = picker('image/*', kind === 'camera'); document.body.append(input);
    input.addEventListener('change', async () => {
      const file = input.files[0]; input.remove(); if (!file) return;
      busy = t(['Munshi आपकी फ़ोटो पढ़ रहा है…', 'Munshi is reading your photo…']); draw();
      try {
        const fd = new FormData(); fd.append('file', await shrink(file), 'photo.jpg');
        const r = await apiForm('/api/assistant/board/photo', fd);
        pending = { via: 'items', from: t(['फ़ोटो से Munshi ने यह समझा। सही है?', 'Here is what Munshi understood from the photo. Correct?']), rates: r.items.map((i) => ({ name: i.name, price: i.price, old_price: i.old_price })), items: r.items.map(({ name, price, status }) => ({ name, price, status })) };
      } catch (e) { toast(e.message, { bad: true }); }
      busy = ''; if (alive) draw();
    });
    input.click();
  }
  function fromFile() {
    const input = picker('.csv,.txt,.tsv,text/csv,text/plain'); document.body.append(input);
    input.addEventListener('change', async () => {
      const file = input.files[0]; input.remove(); if (!file) return;
      if (/\.xlsx?$/i.test(file.name)) return toast(t(['Excel फ़ाइल अभी नहीं पढ़ सकते। CSV या टेक्स्ट में सेव करके चुनें।', 'Excel files cannot be read yet. Save as CSV or text and choose that.']), { bad: true });
      const items = parseList(await file.text());
      if (!items.length) return toast(t(['फ़ाइल में “नाम, रेट” वाली लाइनें नहीं मिलीं।', 'No “name, rate” lines found in the file.']), { bad: true });
      pending = { via: 'items', from: t([`फ़ाइल (${file.name}) से Munshi ने यह समझा। सही है?`, `Here is what Munshi understood from ${file.name}. Correct?`]), rates: items, items }; draw();
    });
    input.click();
  }
  async function understand(text) {
    busy = t(['Munshi समझ रहा है…', 'Munshi is reading it…']); draw();
    try { const r = await A('/shop/understand', { method: 'POST', body: { text } }); pending = { via: 'text', rates: r.rates, facts: r.facts, from: t([`आपने कहा: “${text}”। Munshi ने यह समझा। सही है?`, `You said: “${text}”. Here is what Munshi understood. Correct?`]) }; }
    catch (e) { toast(e.message, { bad: true }); }
    busy = ''; if (alive) draw();
  }
  function fromType() {
    sheet(t(['लिखकर बताएँ', 'Type it']), (close) => { const inp = h('input', { placeholder: t(['जैसे: आटा 44, रविवार बंद', 'e.g. atta 44, closed Sunday']), maxlength: 600, onkeydown: (e) => { if (e.key === 'Enter') go(); } });
      const go = () => { const v = inp.value.trim(); if (v) { close(); understand(v); } };
      return [inp, h('button', { class: 'primary', onclick: go }, t(['आगे', 'Next']))]; });
  }
  function fromVoice() {
    if (!canRecord) return toast(t(['यहाँ माइक नहीं चल रहा। लिखकर बताएँ।', 'The microphone is not available here. Type it instead.']), { bad: true });
    let closeSheet; let cancelled = false;
    closeSheet = sheet(t(['बोलिए…', 'Say it…']), (close) => [h('p', {}, t(['जैसे: “तूर दाल 170 हो गई”। बोलकर रुकिए, Munshi सुन लेगा।', 'For example: “toor dal 170 ho gayi”. Pause when you are done.'])),
      h('button', { class: 'outline main', onclick: () => { cancelled = true; listener.cancel(); close(); } }, t(['रद्द', 'Cancel']))]);
    (async () => {
      try {
        const got = await listener.listen({ silenceMs: 1600, waitMs: 9000 }); closeSheet();
        if (cancelled || !got) return toast(t(['सुनाई नहीं दिया। फिर कोशिश करें।', 'Did not catch that. Try again.']), { bad: true });
        const fd = new FormData(); fd.append('file', got.blob, FILE(got.blob)); fd.append('language', getLang() === 'hi' ? 'hi-IN' : 'en-IN');
        const r = await apiForm('/transcribe', fd);
        if (!r.text) return toast(t(['सुनाई नहीं दिया। फिर कोशिश करें।', 'Did not catch that. Try again.']), { bad: true });
        understand(r.text);
      } catch (e) { closeSheet(); toast(e.name === 'NotAllowedError' ? t(['ब्राउज़र में माइक की अनुमति दें।', 'Allow the microphone in your browser.']) : e.message, { bad: true }); }
    })();
  }
  const addSheet = () => sheet(t(['Munshi को कैसे बताएँ?', 'How do you want to tell Munshi?']), (close) => [
    ['camera', t(['फ़ोटो खींचें', 'Take a photo']), () => fromPhoto('camera')], ['image', t(['गैलरी से चुनें', 'Pick from gallery']), () => fromPhoto('gallery')], ['file', t(['फ़ाइल चुनें', 'Choose a file']), fromFile],
    ['mic', t(['बोलकर बताएँ', 'Say it']), fromVoice], ['pencil', t(['लिखकर बताएँ', 'Type it']), fromType]].map(([ic, label, fn]) => h('button', { class: 'opt', onclick: () => { close(); fn(); } }, h('i', {}, icon(ic)), label)));

  mount(root, body, h('button', { class: 'fab', onclick: addSheet }, icon('plus', 26), t(['जानकारी जोड़ें', 'Add info'])));
  draw();
  return () => { alive = false; listener.close(); };
}
