// Shop info: what Munshi may say. Rates and shop details, with how fresh each one is. Add or change them by photo, file, voice or typing, and check before saving.
import { h, mount } from '/lab/ui.js';
import { A, apiForm } from '../net.js';
import { t, getLang, money, freshness } from '../i18n.js';
import { icon, sheet, toast } from '../kit.js';
import { shrink } from '../photo.js';
import { makeListener, canRecord } from '../listener.js';

const FACT = { delivery: ['होम डिलीवरी', 'Home delivery'], address: ['दुकान का पता', 'Shop address'], hours: ['समय', 'Timing'], rules: ['नियम', 'Rules'], payment: ['पेमेंट', 'Payment'], offers: ['ऑफ़र', 'Offers'], services: ['सेवाएँ', 'Services'], other: ['अन्य', 'Other'] };
const FACT_KEYS = Object.keys(FACT);
const RATE_HEAD = ['रेट', 'Rate'];
const LIMIT = { address: 200, hours: 200, delivery: 300, rules: 600 };
/** What a row is called: the fixed heading, or the owner's own title for "Other". */
const headName = (f) => (f.field === 'other' && f.name && f.name !== 'Other' ? f.name : t(FACT[f.field]));
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

  const still = (id) => h('button', { class: 'pill-btn warn', onclick: (e) => { e.stopPropagation(); confirm(id); } }, t(['सही है', 'Still right']));
  const pen = () => h('span', { class: 'pen', 'aria-hidden': 'true' }, icon('pencil', 18));
  const rateRow = (r) => h('div', { class: 'krow tap', role: 'button', tabindex: 0, 'aria-label': t(['बदलें: ', 'Edit: ']) + r.name, onclick: () => editRate(r), onkeydown: (e) => { if (e.key === 'Enter') editRate(r); } },
    h('div', { class: 'main' }, h('div', { class: 'n' }, r.name), h('div', { class: 'f' + (r.stale ? ' stale' : '') }, r.status === 'sold_out' ? t(['खत्म', 'Sold out']) : freshness(r.age_hours))),
    h('b', { class: 'p' }, money(r.price)), r.stale ? still(r.id) : null, pen());
  const factRow = (f) => h('div', { class: 'krow tap', role: 'button', tabindex: 0, 'aria-label': t(['बदलें: ', 'Edit: ']) + headName(f), onclick: () => editFact(f), onkeydown: (e) => { if (e.key === 'Enter') editFact(f); } },
    h('div', { class: 'main' }, h('div', { class: 'n' }, headName(f)), h('div', { class: 'tx' }, f.text), h('div', { class: 'f' + (f.stale ? ' stale' : '') }, freshness(f.age_hours))),
    f.stale ? still(f.id) : null, pen());
  const refresh = async () => { shop = await A('/shop'); window.dispatchEvent(new Event('munshi-changed')); if (alive) draw(); };

  // ---- editing and removing a row ----
  const removeBtn = (close, what, run) => { let armed = false; const b = h('button', { class: 'outline danger', onclick: async () => {
    if (!armed) { armed = true; b.textContent = t(['फिर दबाएँ: हटा दें', 'Tap again to remove']); return; }
    try { await run(); close(); toast(t(['हटा दिया', 'Removed'])); await refresh(); } catch (e) { toast(e.message, { bad: true }); } } }, t(['हटाएँ', 'Remove'])); return b; };
  function editRate(r) {
    sheet(t(['रेट बदलें', 'Edit rate']), (close) => {
      const name = h('input', { value: r.name, maxlength: 120, 'aria-label': t(['नाम', 'Name']) });
      const price = h('input', { value: r.price, maxlength: 40, 'aria-label': t(['रेट', 'Rate']), placeholder: t(['रेट, जैसे 44/kg', 'Rate, e.g. 44/kg']) });
      let sold = r.status === 'sold_out';
      const label = () => (sold ? t(['अभी खत्म है। दबाएँ: चालू करें', 'Sold out now. Tap to mark in stock']) : t(['चालू है। दबाएँ: खत्म करें', 'In stock. Tap to mark sold out']));
      const tog = h('button', { class: 'outline' + (sold ? ' danger' : ''), onclick: () => { sold = !sold; tog.className = 'outline' + (sold ? ' danger' : ''); tog.textContent = label(); } }, label());
      const go = async () => {
        if (!name.value.trim()) return toast(t(['नाम लिखें', 'Enter a name']), { bad: true });
        try { await A(`/board/${r.id}`, { method: 'PUT', body: { name: name.value.trim(), price: price.value.trim(), status: sold ? 'sold_out' : 'in_stock' } }); close(); toast(t(['सेव हो गया', 'Saved'])); await refresh(); }
        catch (e) { toast(e.message, { bad: true }); }
      };
      return [name, price, tog, h('button', { class: 'primary', onclick: go }, t(['सेव करें', 'Save'])), removeBtn(close, r.name, () => A(`/board/${r.id}`, { method: 'DELETE' }))];
    });
  }
  function micBtn(target) {
    if (!canRecord) return null;
    let recording = false;
    const btn = h('button', { class: 'mic', type: 'button', 'aria-label': t(['बोलें', 'Speak']), onclick: async () => {
      if (recording) { listener.cancel(); return; }
      recording = true; btn.classList.add('rec');
      const got = await listener.listen({ silenceMs: 1600, waitMs: 9000 });
      recording = false; btn.classList.remove('rec');
      if (!got) return toast(t(['सुनाई नहीं दिया', 'Did not catch that']), { bad: true });
      try {
        const fd = new FormData(); fd.append('file', got.blob, FILE(got.blob)); fd.append('language', getLang() === 'hi' ? 'hi-IN' : 'en-IN');
        const r = await apiForm('/transcribe', fd);
        if (!r.text) return toast(t(['सुनाई नहीं दिया', 'Did not catch that']), { bad: true });
        target.value = target.value ? target.value + ' ' + r.text : r.text;
        target.dispatchEvent(new Event('input', { bubbles: true }));
        toast(t(['लिख दिया', 'Transcribed']));
      } catch (e) { toast(e.message, { bad: true }); }
    } }, icon('mic', 22));
    return btn;
  }
  function editFact(f) {
    sheet(headName(f), (close) => {
      const isOther = f.field === 'other';
      const title = isOther ? h('input', { value: f.name === 'Other' ? '' : f.name, maxlength: 40, placeholder: t(['शीर्षक (जैसे: पार्किंग)', 'Heading (e.g. Parking)']), 'aria-label': t(['शीर्षक', 'Heading']) }) : null;
      const area = h('textarea', { rows: 4, maxlength: LIMIT[f.field] || 700, 'aria-label': t(['जानकारी', 'Information']) }, f.text);
      const mic = micBtn(area);
      const go = async () => {
        if (!area.value.trim()) return toast(t(['जानकारी लिखें', 'Write the information']), { bad: true });
        try { await A(`/shop/fact/${encodeURIComponent(f.id)}`, { method: 'PUT', body: { text: area.value.trim(), title: isOther ? title.value.trim() : undefined } }); close(); toast(t(['सेव हो गया', 'Saved'])); await refresh(); }
        catch (e) { toast(e.message, { bad: true }); }
      };
      return [title, area, mic ? h('div', { style: 'display:flex;align-items:center;gap:8px' }, mic, h('span', { style: 'font-size:13px;color:var(--muted)' }, t(['बोलकर भी लिखें', 'Or say it']))) : null, h('button', { class: 'primary', onclick: go }, t(['सेव करें', 'Save'])), removeBtn(close, headName(f), () => A(`/shop/fact/${encodeURIComponent(f.id)}`, { method: 'DELETE' }))];
    });
  }

  // ---- adding by hand, under a heading ----
  function writeIt() {
    sheet(t(['जानकारी जोड़ें', 'Add information']), (close) => {
      let head = 'rate';
      const chips = h('div', { class: 'hchips', role: 'group', 'aria-label': t(['शीर्षक चुनें', 'Pick a heading']) });
      const fields = h('div', { class: 'hfields' });
      const name = h('input', { maxlength: 120, placeholder: t(['नाम (जैसे: आटा)', 'Item (e.g. atta)']), 'aria-label': t(['नाम', 'Name']) });
      const price = h('input', { maxlength: 40, placeholder: t(['रेट (जैसे: 44/kg)', 'Rate (e.g. 44/kg)']), 'aria-label': t(['रेट', 'Rate']) });
      const title = h('input', { maxlength: 40, placeholder: t(['शीर्षक (जैसे: पार्किंग)', 'Heading (e.g. Parking)']), 'aria-label': t(['शीर्षक', 'Heading']) });
      const area = h('textarea', { rows: 4, placeholder: t(['यहाँ लिखें, Munshi यही बोलेगा', 'Write it here. Munshi will say this']), 'aria-label': t(['जानकारी', 'Information']) });
      const note = h('p', {});
      const paint = () => {
        mount(chips, ...['rate', ...FACT_KEYS].map((k) => h('button', { class: 'rchip' + (k === head ? ' on' : ''), 'aria-pressed': String(k === head), onclick: () => { head = k; prefill(); paint(); } }, k === 'rate' ? t(RATE_HEAD) : t(FACT[k]))));
        mount(fields, ...(head === 'rate' ? [name, price] : [head === 'other' ? title : null, area, note]));
      };
      const prefill = () => {
        const old = shop.facts.find((f) => f.field === head && LIMIT[head]);  // address, timing, delivery and rules hold one text
        area.value = old ? old.text : ''; area.maxLength = LIMIT[head] || 700;
        note.textContent = old ? t(['इसकी पुरानी जानकारी नीचे है। बदलकर सेव करें।', 'The current text is below. Change it and save.']) : '';
      };
      const go = async () => {
        try {
          if (head === 'rate') {
            if (!name.value.trim() || !price.value.trim()) return toast(t(['नाम और रेट दोनों लिखें', 'Enter both the item and its rate']), { bad: true });
            await A('/board', { method: 'POST', body: { name: name.value.trim(), price: price.value.trim(), status: 'in_stock' } });
          } else {
            if (!area.value.trim()) return toast(t(['जानकारी लिखें', 'Write the information']), { bad: true });
            await A('/shop/fact', { method: 'POST', body: { heading: head, text: area.value.trim(), title: head === 'other' ? title.value.trim() : '' } });
          }
          close(); toast(t(['जानकारी सेव हुई', 'Knowledge saved'])); await refresh();
        } catch (e) { toast(e.message, { bad: true }); }
      };
      const mic = micBtn(area);
      paint();
      return [h('p', {}, t(['पहले शीर्षक चुनें, फिर लिखें।', 'Pick a heading first, then write it.'])), chips, fields, mic ? h('div', { style: 'display:flex;align-items:center;gap:8px' }, mic, h('span', { style: 'font-size:13px;color:var(--muted)' }, t(['बोलकर भी लिखें', 'Or say it']))) : null, h('button', { class: 'primary', onclick: go }, t(['सेव करें', 'Save']))];
    });
  }
  async function confirm(id) { try { shop = await A('/shop/confirm', { method: 'POST', body: { id } }); toast(t(['पक्का किया', 'Confirmed'])); draw(); } catch (e) { toast(e.message, { bad: true }); } }

  function pendingCard() {
    if (busy) return h('div', { class: 'pendcard' }, h('div', { class: 'from' }, busy));
    if (!pending) return null;
    const rows = [...(pending.rates || []).map((r) => h('div', { class: 'r' }, h('span', {}, r.name), h('b', {}, r.old_price && r.old_price !== r.price ? h('s', {}, money(r.old_price)) : null, money(r.price)))),
      ...(pending.facts || []).map((f) => h('div', { class: 'r' }, h('select', { class: 'headpick', 'aria-label': t(['शीर्षक', 'Heading']), onchange: (e) => { f.field = e.target.value; } },
        ...FACT_KEYS.map((k) => { const o = h('option', { value: k }, t(FACT[k])); if (k === f.field) o.selected = true; return o; })), h('b', { style: 'text-align:right;max-width:60%;font-size:15px' }, f.text)))];
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
      group(t(['और जानकारी', 'More info']), shop.facts.filter((f) => !f.stale && f.group === 'more').map(factRow)),
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
    ['pencil', t(['खुद लिखें (शीर्षक चुनकर)', 'Write it myself (pick a heading)']), writeIt], ['camera', t(['फ़ोटो खींचें', 'Take a photo']), () => fromPhoto('camera')], ['image', t(['गैलरी से चुनें', 'Pick from gallery']), () => fromPhoto('gallery')], ['file', t(['फ़ाइल चुनें', 'Choose a file']), fromFile],
    ['mic', t(['बोलकर बताएँ', 'Say it']), fromVoice], ['chat', t(['लिखें, Munshi समझेगा', 'Type it, Munshi reads it']), fromType]].map(([ic, label, fn]) => h('button', { class: 'opt', onclick: () => { close(); fn(); } }, h('i', {}, icon(ic)), label)));

  mount(root, body, h('button', { class: 'fab', onclick: addSheet }, icon('plus', 26), t(['जानकारी जोड़ें', 'Add info'])));
  draw();
  return () => { alive = false; listener.close(); };
}
