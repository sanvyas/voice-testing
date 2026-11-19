// Settings.
import { h, mount } from '/lab/ui.js';
import { A } from '../net.js';
import { t, isHi, setLang } from '../i18n.js';
import { icon, sheet, toast } from '../kit.js';
import { setBusinessKey } from '/lab/api.js';
import { signOut } from './login.js';
import { go } from '../shell.js';

export async function render(root) {
  const [plan, voices, me] = await Promise.all([A('/plan'), A('/voices'), A('/me')]);
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
    account(me),
    h('div', { style: 'margin-top:16px;font-size:13px;color:var(--muted);line-height:1.55' }, t(['Munshi आपकी जगह रेट, छूट या समय का वादा नहीं करेगा। जो नहीं पता, कहेगा कि मालिक कॉल करेंगे।', 'Munshi will not promise a price, discount or deadline for you. If it does not know, it says the owner will call back.']))));
}

const link = (href, label) => h('a', { href, target: '_blank', rel: 'noopener', class: 'mrow' }, h('div', { style: 'flex:1' }, h('div', { class: 'l' }, label)), h('span', { style: 'color:#8a9a95' }, icon('next')));

/** Who is signed in, the way out, the owner's copy of their data, and deleting the account. */
function account(me) {
  const signedIn = me.role === 'owner';
  async function download() {
    try {
      const blob = new Blob([JSON.stringify(await A('/account/export'), null, 2)], { type: 'application/json' });
      const a = h('a', { href: URL.createObjectURL(blob), download: 'munshi-my-data.json' }); document.body.append(a); a.click(); a.remove();
      toast(t(['आपका डेटा डाउनलोड हो गया', 'Your data was downloaded']));
    } catch (e) { toast(e.message, { bad: true }); }
  }
  function remove() {
    sheet(t(['खाता और डेटा मिटाएँ?', 'Delete your account and data?']), (close) => {
      const word = h('input', { placeholder: t(['DELETE लिखें', 'Type DELETE']), autocapitalize: 'characters', 'aria-label': t(['पक्का करने के लिए DELETE लिखें', 'Type DELETE to confirm']) });
      return [h('p', {}, t(['आपकी दुकान, रेट, संपर्क और सारी कॉल तुरंत मिट जाएँगी। यह वापस नहीं हो सकता। पहले “डेटा डाउनलोड करें” से कॉपी रख लें।', 'Your shop, rates, contacts and every call are deleted at once. This cannot be undone. Use “Download my data” first if you want a copy.'])), word,
        h('button', { class: 'outline danger', onclick: async () => {
          if (word.value.trim().toUpperCase() !== 'DELETE') return toast(t(['पक्का करने के लिए DELETE लिखें', 'Type DELETE to confirm']), { bad: true });
          try { await A('/account/delete', { method: 'POST', body: { confirm: 'DELETE' } }); setBusinessKey(''); close(); location.hash = ''; location.reload(); } catch (e) { toast(e.message, { bad: true }); }
        } }, t(['हाँ, सब मिटा दें', 'Yes, delete everything'])), h('button', { class: 'outline', onclick: close }, t(['रद्द', 'Cancel']))];
    });
  }
  const rows = [];
  if (signedIn) rows.push(h('div', { class: 'mrow', style: 'cursor:default' }, h('div', { style: 'flex:1' }, h('div', { class: 'l' }, me.demo ? t(['डेमो दुकान', 'Demo shop']) : t(['साइन इन है', 'Signed in'])), h('div', { class: 's' }, me.phone))),
    h('button', { class: 'mrow', onclick: download }, h('div', { style: 'flex:1' }, h('div', { class: 'l' }, t(['मेरा डेटा डाउनलोड करें', 'Download my data']))), h('span', { style: 'color:#8a9a95' }, icon('next'))),
    h('button', { class: 'mrow', onclick: async () => { await signOut(); location.hash = ''; location.reload(); } }, h('div', { style: 'flex:1' }, h('div', { class: 'l' }, t(['साइन आउट', 'Sign out']))), h('span', { style: 'color:#8a9a95' }, icon('next'))));
  rows.push(link('/legal/privacy', t(['प्राइवेसी नीति', 'Privacy Policy'])), link('/legal/terms', t(['शर्तें', 'Terms of Service'])));
  if (signedIn && !me.demo) rows.push(h('button', { class: 'mrow', onclick: remove }, h('div', { style: 'flex:1' }, h('div', { class: 'l', style: 'color:var(--warn-d)' }, t(['खाता और डेटा मिटाएँ', 'Delete my account and data']))), h('span', { style: 'color:#8a9a95' }, icon('next'))));
  return h('div', { class: 'cardw flush', style: 'margin-top:14px' }, ...rows);
}
