// Settings.
import { h, mount } from '/lab/ui.js';
import { A } from '../net.js';
import { t, isHi, setLang } from '../i18n.js';
import { icon } from '../kit.js';
import { go } from '../shell.js';

export async function render(root) {
  const [plan, voices] = await Promise.all([A('/plan'), A('/voices')]);
  const v = voices.voices.find((x) => x.id === voices.current) || voices.voices[0];
  const planSub = plan.status === 'cancelled' ? t(['रद्द किया', 'Cancelled']) : plan.status === 'trial' ? t([`14 दिन मुफ़्त · ${plan.days_left} दिन बाकी`, `14-day free trial · ${plan.days_left} days left`]) : t(['ट्रायल पूरा हुआ', 'Trial is over']);
  const items = [
    [t(['प्लान और भुगतान', 'Plan and payment']), planSub, () => go('#/plan')],
    [t(['Munshi की आवाज़', "Munshi's voice"]), `${isHi() ? v.name_hi : v.name} · ${isHi() ? v.desc_hi : v.desc}`, () => go('#/voice?from=more')],
    [t(['दुकान का सेटअप', 'Shop setup']), t(['नाम, पता, समय, भाषा, कोड', 'Name, address, hours, languages, code']), () => go('#/setup')],
    [t(['ऐप की भाषा', 'App language']), t(['हिन्दी · बदलने के लिए छुएँ', 'English · tap to change']), () => setLang(isHi() ? 'en' : 'hi')],
  ];
  mount(root, h('div', { class: 'scroll' }, h('h1', { class: 'page-title' }, t(['सेटिंग', 'Settings'])),
    h('button', { class: 'try-card', onclick: () => go('#/try') }, h('div', { class: 'o' }, icon('phone', 26)), h('div', { style: 'flex:1' }, h('div', { style: 'font-size:18px;font-weight:700' }, t(['Munshi को आज़माएँ', 'Test your Munshi'])),
      h('div', { style: 'font-size:14px;line-height:1.45;color:#D9F5E8;margin-top:2px' }, t(['अपने फ़ोन से अपने Munshi को कॉल करें और सुनें।', 'Call your own Munshi and listen.']))), icon('next', 26)),
    h('div', { class: 'cardw flush', style: 'margin-top:14px' }, ...items.map(([l, s, fn]) => h('button', { class: 'mrow', onclick: fn }, h('div', { style: 'flex:1' }, h('div', { class: 'l' }, l), h('div', { class: 's' }, s)), h('span', { style: 'color:#8a9a95' }, icon('next'))))),
    h('div', { style: 'margin-top:16px;font-size:13px;color:var(--muted);line-height:1.55' }, t(['Munshi आपकी जगह रेट, छूट या समय का वादा नहीं करेगा। जो नहीं पता, कहेगा कि मालिक कॉल करेंगे।', 'Munshi will not promise a price, discount or deadline for you. If it does not know, it says the owner will call back.']))));
}
