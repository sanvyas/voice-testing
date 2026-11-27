// Shop setup: five things, once. The last is a code you dial so missed calls reach Munshi.
import { h, mount } from '/lab/ui.js';
import { A } from '../net.js';
import { t, isHi } from '../i18n.js';
import { icon, toast, telLink } from '../kit.js';
import { shell, saveProfile, go } from '../shell.js';

const LANGS = [['hi', ['हिन्दी', 'Hindi']], ['en', ['English', 'English']], ['hing', ['Hinglish', 'Hinglish']]];
const ORDER = ['hi', 'en', 'hing'];

export async function render(root) {
  const p = shell.profile; const voices = await A('/voices');
  const f = { biz: p.business_name, owner: p.owner_name, addr: p.address, open: p.open || '', close: p.close || '', langs: new Set(p.languages.filter((c) => ORDER.includes(c))) };
  const number = shell.status.phone && shell.status.phone.number; const code = number ? `**61*${number}**20#` : '';
  const count = h('b', { style: 'font-size:14px;color:var(--green)' }); const body = h('div', { class: 'scroll', style: 'padding-top:8px;display:flex;flex-direction:column;gap:14px' });
  const v = voices.voices.find((x) => x.id === (p.voice || 'v1')) || voices.voices[0];
  const field = (label, key, extra = {}) => h('label', { class: 'f' }, label, h('input', { value: f[key], ...extra, oninput: (e) => { f[key] = e.target.value; paint(); } }));
  const ok = () => [!!(f.biz.trim() && f.owner.trim()), !!f.addr.trim(), !!(f.open && f.close), f.langs.size > 0, !!p.forwarding_done];
  const paint = () => { const n = ok().filter(Boolean).length; count.textContent = t([`${n} / 5 पूरे`, `${n} of 5 done`]); };
  const changes = () => ({ business_name: f.biz.trim(), owner_name: f.owner.trim(), address: f.addr.trim(), open: f.open, close: f.close, languages: ORDER.filter((c) => f.langs.has(c)) });
  async function save(to) {
    if (!f.langs.size) return toast(t(['कम से कम एक भाषा चुनें', 'Pick at least one language']), { bad: true });
    if (!f.biz.trim() || !f.owner.trim()) return toast(t(['दुकान और अपना नाम लिखें', 'Enter the shop name and your name']), { bad: true });
    try { await saveProfile(changes()); go(to); } catch (e) { toast(e.message, { bad: true }); }
  }
  const langRow = h('div', { class: 'langs' });
  const drawLangs = () => mount(langRow, ...LANGS.map(([k, l]) => h('button', { class: 'lg' + (f.langs.has(k) ? ' on' : ''), onclick: () => { f.langs.has(k) ? f.langs.delete(k) : f.langs.add(k); drawLangs(); paint(); } }, (f.langs.has(k) ? '✓ ' : '') + t(l))));
  mount(body,
    h('div', { class: 'cardw form' }, field(t(['दुकान का नाम', 'Shop name']), 'biz'), field(t(['आपका नाम', 'Your name']), 'owner'), field(t(['पता', 'Address']), 'addr'),
      h('div', { class: 'two' }, field(t(['दुकान खुलती है', 'Opens at']), 'open', { type: 'time' }), field(t(['दुकान बंद होती है', 'Closes at']), 'close', { type: 'time' }))),
    h('div', { class: 'cardw', style: 'display:flex;flex-direction:column;gap:10px' }, h('div', { class: 'f' }, t(['Munshi किन भाषाओं में बात करे', 'Languages Munshi speaks'])), langRow),
    h('button', { class: 'pick', onclick: () => save(`#/voice?from=setup`) }, h('div', { class: 'o' }, icon('sound')), h('div', { style: 'flex:1' }, h('div', { class: 'f' }, t(['Munshi की आवाज़', "Munshi's voice"])), h('div', { style: 'font-size:16px;font-weight:600' }, `${isHi() ? v.name_hi : v.name} · ${isHi() ? v.desc_hi : v.desc}`)), h('span', { style: 'color:#8a9a95' }, icon('next'))),
    h('div', { class: 'codebox' }, h('b', { style: 'font-size:16px' }, t(['कॉल Munshi तक पहुँचाने वाला कोड', 'Code that sends missed calls to Munshi'])),
      h('div', { style: 'font-size:14px;line-height:1.5;color:#cfe8de;margin-top:4px' }, t(['इससे आपका फ़ोन पहले बजेगा। 20 सेकंड में न उठाएँ तो कॉल Munshi के पास जाएगी।', 'Your phone rings first. If you do not pick up in 20 seconds, the call goes to Munshi.'])),
      h('div', { class: 'code' }, code || t(['आपका Munshi नंबर अभी तय नहीं है', 'Your Munshi number is not set yet'])),
      h('div', { style: 'font-size:12px;color:#9db5ac;margin-top:6px' }, number ? t(['यह कोड आपके Munshi नंबर से बना है।', 'This code is made from your Munshi number.']) : t(['Munshi टीम से नंबर लेकर यह कोड दिखेगा।', 'The code shows once the Munshi team sets your number.'])),
      h('div', { class: 'row' }, h('a', { class: 'go', href: code ? telLink(code) : '#', 'aria-disabled': code ? null : 'true', onclick: async (e) => { if (!code) return e.preventDefault(); try { await saveProfile({ forwarding_done: true }); paint(); } catch { /* the dialer still opens */ } } }, t(['डायल करें', 'Dial now'])),
        h('button', { class: 'cp', onclick: async () => { if (!code) return; try { await navigator.clipboard.writeText(code); toast(t(['कोड कॉपी हुआ', 'Code copied'])); } catch { toast(code); } } }, t(['कॉपी', 'Copy']))),
      h('div', { style: 'margin-top:12px;font-size:13px;color:#cfe8de;line-height:1.5' }, t(['Munshi बंद करना हो तो डायल करें:', 'To switch Munshi off, dial:']) + ' ', h('b', { style: 'font-family:ui-monospace,monospace;color:var(--mint)' }, '##61#'))));
  mount(root, h('div', { class: 'col' }, h('div', { class: 'sub-top' }, h('button', { class: 'btn-ic', 'aria-label': t(['वापस', 'Back']), onclick: () => go('#/more') }, icon('back', 28)), h('h1', {}, t(['दुकान का सेटअप', 'Shop setup'])), count),
    body, h('div', { class: 'bar' }, h('button', { class: 'big', onclick: () => save('#/try') }, t(['सेव करें और आज़माएँ', 'Save and try it'])))));
  drawLangs(); paint();
}
