// Contacts: numbers Munshi never answers ("always ring me") and customers.
import { h, mount } from '/lab/ui.js';
import { A } from '../net.js';
import { t, initial } from '../i18n.js';
import { icon, sheet, toast } from '../kit.js';

const MAX_IMPORT = 500;
const canPick = typeof navigator !== 'undefined' && 'contacts' in navigator && 'ContactsManager' in window;  // Android Chrome

const cleanName = (n) => String(n || '').replace(/[,;\r\n\t]+/g, ' ').replace(/\s+/g, ' ').trim();
const digits = (s) => String(s || '').replace(/\D/g, '');
/** Phone-book export (.vcf) or a plain "name, number" list -> ["Name, number", ...]. One line per number. */
export function parseContacts(text) {
  const out = []; const seen = new Set();
  const add = (name, tel) => { const d = digits(tel); if (d.length < 8 || d.length > 15 || seen.has(d.slice(-10))) return; seen.add(d.slice(-10)); out.push(`${cleanName(name)}, ${String(tel).trim()}`); };
  if (/BEGIN:VCARD/i.test(text)) {
    for (const card of text.replace(/\r?\n[ \t]/g, '').split(/BEGIN:VCARD/i).slice(1)) {
      const fn = card.match(/^FN[^:\n]*:(.*)$/im); const n = card.match(/^N[^:\n]*:(.*)$/im);
      const name = fn ? fn[1] : n ? n[1].split(';').reverse().join(' ') : '';
      for (const m of card.matchAll(/^TEL[^:\n]*:(.*)$/gim)) add(name.replace(/\\,/g, ','), m[1]);
    }
  } else {
    for (const line of text.split(/\r?\n/)) {
      const parts = line.split(/[,\t;]/).map((x) => x.trim()).filter(Boolean);
      const tel = parts.find((x) => /^[+\d][\d\s()-]{7,}$/.test(x));
      if (tel) add(parts.filter((x) => x !== tel).join(' '), tel);
    }
  }
  return out.slice(0, MAX_IMPORT);
}

export async function render(root) {
  let data = await A('/people/known');
  const body = h('div', { class: 'scroll pad-fab' });
  const reload = async () => { data = await A('/people/known'); draw(); };
  async function flip(c, always) {
    try {
      if (c.id) await A(`/contacts/${c.id}`, { method: 'PUT', body: { always_ring: always } });
      else await A('/contacts', { method: 'POST', body: { name: c.name, phone: c.phone, always_ring: true } });
      toast(always ? t(['जुड़ गया। Munshi इनकी कॉल नहीं उठाएगा।', 'Added. Munshi will not answer this number.']) : t(['हटा दिया', 'Removed']));
      await reload();
    } catch (e) { toast(e.message, { bad: true }); }
  }
  const row = (c, always) => h('div', { class: 'crow' }, h('div', { class: 'cav' + (always ? ' dark' : '') }, initial(c.name)), h('div', { class: 'main' }, h('div', { class: 'n' }, c.name), h('div', { class: 's' }, c.phone)),
    h('button', { class: 'pill-btn' + (always ? ' quiet' : ''), onclick: () => flip(c, !always) }, always ? t(['हटाएँ', 'Remove']) : t(['हमेशा रिंग', 'Always ring'])));
  function draw() {
    mount(body, h('h1', { class: 'page-title' }, t(['संपर्क', 'Contacts'])),
      h('button', { class: 'importcard', onclick: fromPhoneBook }, h('i', {}, icon('people', 24)), h('span', { class: 'main' }, h('b', {}, t(['फ़ोन बुक से जोड़ें', 'Import from phone book'])), h('small', {}, canPick ? t(['अपने फ़ोन से संपर्क चुनें', 'Choose people from your phone']) : t(['फ़ोन की संपर्क फ़ाइल (.vcf) चुनें', 'Choose your phone\'s contacts file (.vcf)'])))),
      !canPick ? null : h('button', { class: 'link small', onclick: fromFile }, t(['या फ़ाइल (.vcf, .csv) से', 'or from a file (.vcf, .csv)'])),
      h('div', { style: 'margin-top:20px;font-size:16px;font-weight:700' }, t(['हमेशा मेरा फ़ोन बजे', 'Always ring me'])),
      h('div', { class: 'lead', style: 'margin-top:2px' }, t(['इन नंबरों की कॉल Munshi कभी नहीं उठाएगा। सिर्फ़ आपका फ़ोन बजेगा।', 'Munshi never answers these numbers. Only your phone rings.'])),
      h('div', { class: 'cardw flush', style: 'margin-top:10px' }, data.always.length ? data.always.map((c) => row(c, true)) : h('div', { class: 'crow' }, h('div', { class: 's' }, t(['अभी कोई नंबर नहीं', 'No numbers yet'])))),
      h('div', { style: 'margin-top:26px;font-size:16px;font-weight:700' }, t(['ग्राहक', 'Customers'])),
      h('div', { class: 'cardw flush', style: 'margin-top:10px' }, data.customers.length ? data.customers.map((c) => row(c, false)) : h('div', { class: 'crow' }, h('div', { class: 's' }, t(['जिन्होंने कॉल की है वे यहाँ दिखेंगे', 'People who call will show here'])))));
  }
  async function importLines(lines, always) {
    let added = 0; let skipped = 0;
    try {
      for (let i = 0; i < lines.length; i += 150) { const r = await A('/contacts/import', { method: 'POST', body: { text: lines.slice(i, i + 150).join('\n'), always_ring: always } }); added += r.added; skipped += r.skipped.length; }
      toast(t([`${added} जुड़े${skipped ? `, ${skipped} छोड़े (पहले से हैं या नंबर सही नहीं)` : ''}`, `${added} added${skipped ? `, ${skipped} skipped (already saved or not a valid number)` : ''}`])); await reload();
    } catch (e) { toast(e.message, { bad: true }); if (added) await reload(); }
  }
  function confirmImport(lines) {
    if (!lines.length) return toast(t(['कोई फ़ोन नंबर नहीं मिला।', 'No phone numbers found.']), { bad: true });
    sheet(t([`${lines.length} संपर्क मिले`, `${lines.length} contacts found`]), (close) => [
      h('p', {}, [...new Set(lines.map((l) => l.split(',')[0].trim() || l.split(',')[1].trim()))].slice(0, 4).join(', ') + (lines.length > 4 ? '…' : '')),
      h('button', { class: 'primary', onclick: () => { close(); importLines(lines, false); } }, t(['ग्राहक की तरह जोड़ें', 'Add as customers'])),
      h('p', {}, t(['नाम सेव होंगे, ताकि कॉल पर पहचान हो। Munshi इनकी कॉल उठाएगा।', 'Names are saved so callers are recognised. Munshi still answers them.'])),
      h('button', { class: 'outline main', onclick: () => { close(); importLines(lines, true); } }, t(['हमेशा मेरा फ़ोन बजे', 'Always ring me'])),
      h('p', {}, t(['इन नंबरों की कॉल Munshi कभी नहीं उठाएगा।', 'Munshi will never answer these numbers.'])),
      h('button', { class: 'outline', onclick: close }, t(['रद्द', 'Cancel']))]);
  }
  function fromFile() {
    const input = h('input', { type: 'file', accept: '.vcf,.csv,.txt,text/vcard,text/x-vcard,text/csv,text/plain', hidden: true }); document.body.append(input);
    input.addEventListener('change', async () => { const f = input.files[0]; input.remove(); if (f) confirmImport(parseContacts(await f.text())); });
    input.click();
  }
  async function fromPhoneBook() {
    if (!canPick) return fromFile();
    try {
      const picked = await navigator.contacts.select(['name', 'tel'], { multiple: true });
      const lines = []; const seen = new Set();
      for (const c of picked) for (const tel of c.tel || []) { const d = digits(tel).slice(-10); if (d.length >= 8 && !seen.has(d)) { seen.add(d); lines.push(`${cleanName(c.name && c.name[0])}, ${tel}`); } }
      confirmImport(lines.slice(0, MAX_IMPORT));
    } catch (e) { if (e.name !== 'AbortError') { toast(t(['फ़ोन बुक नहीं खुली। फ़ाइल से जोड़ें।', 'Could not open the phone book. Add from a file instead.']), { bad: true }); } }
  }
  function add() {
    sheet(t(['हमेशा रिंग वाला नंबर', 'Always-ring number']), (close) => { const n = h('input', { placeholder: t(['नाम (जैसे: बड़े भैया)', 'Name (e.g. elder brother)']) }); const p = h('input', { placeholder: t(['फ़ोन नंबर', 'Phone number']), inputmode: 'tel' });
      return [h('p', {}, t(['Munshi इस नंबर की कॉल कभी नहीं उठाएगा।', 'Munshi will never answer this number.'])), n, p, h('button', { class: 'primary', onclick: async () => {
        if (!n.value.trim()) return toast(t(['नाम लिखें', 'Enter a name']), { bad: true });
        try { await A('/contacts', { method: 'POST', body: { name: n.value.trim(), phone: p.value.trim(), always_ring: true } }); close(); toast(t(['जुड़ गया। Munshi इनकी कॉल नहीं उठाएगा।', 'Added. Munshi will not answer this number.'])); await reload(); }
        catch (e) { toast(e.message, { bad: true }); } } }, t(['जोड़ें', 'Add']))]; });
  }
  mount(root, body, h('button', { class: 'fab', onclick: add }, icon('plus', 26), t(['नंबर जोड़ें', 'Add number'])));
  draw();
}
