// Plan and payment. Billing is not switched on yet: the screen says so plainly.
import { h, mount } from '/lab/ui.js';
import { A } from '../net.js';
import { t, isHi } from '../i18n.js';
import { icon, sheet, toast } from '../kit.js';
import { go } from '../shell.js';

export async function render(root) {
  let p = await A('/plan'); const body = h('div', { class: 'scroll', style: 'padding-top:8px;display:flex;flex-direction:column;gap:12px' });
  const endText = () => new Date(p.ends_on).toLocaleDateString(isHi() ? 'hi-IN' : 'en-IN', { day: 'numeric', month: 'long', timeZone: 'Asia/Kolkata' });
  async function update(change, message) { try { p = await A('/plan', { method: 'PUT', body: change }); toast(message); draw(); window.dispatchEvent(new Event('munshi-changed')); } catch (e) { toast(e.message, { bad: true }); } }
  function upiSheet() {
    sheet(t(['UPI जोड़ें', 'Add UPI']), (close) => { const inp = h('input', { placeholder: 'name@upi', value: p.upi }); return [h('p', {}, t(['ट्रायल में कुछ नहीं कटेगा। पहला भुगतान ट्रायल ख़त्म होने के बाद होगा।', 'Nothing is charged during the trial. The first payment is after it ends.'])), inp,
      h('button', { class: 'primary', onclick: async () => { close(); await update({ upi: inp.value.trim() }, t(['UPI जुड़ गया', 'UPI added'])); } }, t(['सेव करें', 'Save']))]; });
  }
  function cancelSheet() {
    sheet(t(['प्लान रद्द करें?', 'Cancel your plan?']), (close) => [h('p', {}, t([`रद्द करने पर ${endText()} के बाद Munshi बंद हो जाएगा। तब तक सब चालू रहेगा, और आपका डेटा सुरक्षित रहेगा।`, `If you cancel, Munshi switches off after ${endText()}. Everything works until then, and your data stays saved.`])),
      h('div', { class: 'two-btn' }, h('button', { class: 'outline danger', onclick: async () => { close(); await update({ cancelled: true }, t(['प्लान रद्द हुआ', 'Plan cancelled'])); } }, t(['हाँ, रद्द करें', 'Yes, cancel'])), h('button', { class: 'primary', onclick: close }, t(['नहीं, चालू रखें', 'No, keep it'])))]);
  }
  function draw() {
    const cancelled = p.status === 'cancelled'; const used = Math.min(100, Math.round((p.calls_used / p.call_limit) * 100));
    mount(body,
      h('div', { class: 'planhero' }, h('span', { class: 'c' }, cancelled ? t(['रद्द किया', 'Cancelled']) : p.status === 'trial' ? t(['मुफ़्त ट्रायल', 'Free trial']) : t(['ट्रायल पूरा', 'Trial over'])),
        h('div', { class: 'hd', style: 'font:700 30px/1.3 \'Space Grotesk\',\'Noto Sans Devanagari\';margin-top:10px' }, cancelled ? t([`${endText()} तक चालू`, `Active till ${endText()}`]) : t([`${p.days_left} दिन बाकी`, `${p.days_left} days left`])),
        h('div', { class: 'meter' }, h('i', { style: `width:${cancelled ? 100 : Math.round(((p.trial_days - p.days_left) / p.trial_days) * 100)}%` })),
        h('div', { style: 'font-size:14.5px;line-height:1.55;color:#cfe8de;margin-top:12px' }, cancelled ? t(['इसके बाद Munshi बंद हो जाएगा। कॉल सिर्फ़ आपके फ़ोन पर आएँगी।', 'After that Munshi switches off. Calls will ring only your phone.']) : t(['14 दिन मुफ़्त, फिर लगभग ₹499 / महीना। ट्रायल में कुछ नहीं कटेगा।', '14 days free, then about ₹499 / month. Nothing is charged during the trial.'])),
        h('div', { style: 'font-size:12.5px;color:var(--gold);margin-top:8px' }, t(['क़ीमत और सीमा अभी तय नहीं हैं। भुगतान अभी चालू नहीं है, कुछ नहीं कटेगा।', 'Price and limits are not final. Payments are not switched on yet, nothing is charged.']))),
      h('div', { class: 'cardw' }, h('div', { style: 'display:flex;justify-content:space-between;align-items:baseline' }, h('b', { style: 'font-size:16px' }, t(['इस महीने की कॉल', 'Calls this month'])), h('span', { style: 'font-size:14px;font-weight:700' }, t([`${p.calls_used} / ${p.call_limit} कॉल`, `${p.calls_used} of ${p.call_limit} calls`]))),
        h('div', { class: 'meter light' }, h('i', { style: `width:${used}%` })), h('div', { style: 'font-size:13px;color:var(--muted);margin-top:8px' }, t([`${p.call_limit} कॉल की सीमा उदाहरण है।`, `The ${p.call_limit}-call limit is an example.`]))),
      h('div', { class: 'cardw', style: 'display:flex;flex-direction:column;gap:10px' }, h('b', { style: 'font-size:16px' }, t(['भुगतान का तरीक़ा', 'Payment method'])),
        p.upi ? h('div', { style: 'display:flex;align-items:center;justify-content:space-between;gap:10px;min-height:56px' }, h('div', {}, h('div', { style: 'font-size:13px;color:var(--muted)' }, t(['UPI से भुगतान', 'Pay by UPI'])), h('div', { style: 'font-size:17px;font-weight:600' }, p.upi)), h('button', { class: 'pill-btn', onclick: upiSheet }, t(['बदलें', 'Change'])))
          : [h('div', { style: 'font-size:14.5px;line-height:1.5;color:var(--muted)' }, t(['अभी कोई भुगतान तरीक़ा नहीं जुड़ा। ट्रायल के बाद ज़रूरत पड़ेगी।', 'No payment method added. You will need one after the trial.'])), h('button', { class: 'big', style: 'min-height:56px;border-radius:14px;font-size:16px', onclick: upiSheet }, '+ ' + t(['UPI जोड़ें', 'Add UPI']))]),
      h('div', { class: 'cardw' }, h('b', { style: 'font-size:16px' }, t(['रसीदें', 'Receipts'])), h('div', { style: 'font-size:14.5px;line-height:1.5;color:var(--muted);margin-top:6px' }, t(['अभी कोई रसीद नहीं। ट्रायल के बाद यहाँ दिखेंगी।', 'No receipts yet. They will show here after the trial.']))),
      h('div', { style: 'text-align:center;padding-top:6px' }, h('button', { class: 'link', style: 'margin:0 auto;color:var(--warn-d);font-size:16px', onclick: cancelled ? () => update({ cancelled: false }, t(['प्लान चालू है', 'Plan is active'])) : cancelSheet }, cancelled ? t(['प्लान फिर से चालू करें', 'Restart plan']) : t(['प्लान रद्द करें', 'Cancel plan'])),
        h('div', { style: 'font-size:13px;color:var(--muted)' }, t(['कभी भी रद्द कर सकते हैं। कोई सवाल नहीं पूछा जाएगा।', 'Cancel any time. No questions asked.']))));
  }
  mount(root, h('div', { class: 'col' }, h('div', { class: 'sub-top' }, h('button', { class: 'btn-ic', 'aria-label': t(['वापस', 'Back']), onclick: () => go('#/more') }, icon('back', 28)), h('h1', {}, t(['प्लान और भुगतान', 'Plan and payment']))), body));
  draw();
}
