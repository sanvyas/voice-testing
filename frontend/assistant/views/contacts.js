// Contacts: numbers Munshi never answers ("always ring me") and customers.
import { h, mount } from '/lab/ui.js';
import { A } from '../net.js';
import { t, initial } from '../i18n.js';
import { icon, sheet, toast } from '../kit.js';

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
      h('div', { style: 'margin-top:8px;font-size:16px;font-weight:700' }, t(['हमेशा मेरा फ़ोन बजे', 'Always ring me'])),
      h('div', { class: 'lead', style: 'margin-top:2px' }, t(['इन नंबरों की कॉल Munshi कभी नहीं उठाएगा। सिर्फ़ आपका फ़ोन बजेगा।', 'Munshi never answers these numbers. Only your phone rings.'])),
      h('div', { class: 'cardw flush', style: 'margin-top:10px' }, data.always.length ? data.always.map((c) => row(c, true)) : h('div', { class: 'crow' }, h('div', { class: 's' }, t(['अभी कोई नंबर नहीं', 'No numbers yet'])))),
      h('div', { style: 'margin-top:26px;font-size:16px;font-weight:700' }, t(['ग्राहक', 'Customers'])),
      h('div', { class: 'cardw flush', style: 'margin-top:10px' }, data.customers.length ? data.customers.map((c) => row(c, false)) : h('div', { class: 'crow' }, h('div', { class: 's' }, t(['जिन्होंने कॉल की है वे यहाँ दिखेंगे', 'People who call will show here'])))));
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
