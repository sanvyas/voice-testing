// Munshi's voice: four to choose from, each with a short sample to listen to.
import { h, mount } from '/lab/ui.js';
import { A } from '../net.js';
import { apiBlob } from '/lab/api.js';
import { t, isHi, getLang } from '../i18n.js';
import { icon, toast } from '../kit.js';
import { shell, saveProfile, go } from '../shell.js';

const SAMPLE = { 'hi-IN': 'नमस्ते, मैं मुंशी हूँ, एक ए आई सहायक। बताइए, क्या चाहिए?', 'en-IN': 'Namaste, this is Munshi, an AI assistant. How can I help?' };

export async function render(root, { query }) {
  const data = await A('/voices'); let pick = data.current; const from = query.get('from') === 'setup' ? '#/setup' : query.get('from') === 'start' ? '#/start/4' : '#/more'; const list = h('div', { class: 'scroll', style: 'padding-top:8px;display:flex;flex-direction:column;gap:10px' });
  let audio = null;
  async function listen(v, e) {
    e.stopPropagation(); pick = v.id; draw(); const language = getLang() === 'hi' ? 'hi-IN' : 'en-IN';
    try { const r = await apiBlob('/api/assistant/voices/sample', { voice: v.id, language }); audio?.pause(); audio = new Audio(URL.createObjectURL(r.blob)); await audio.play(); toast(t(['नमूना चल रहा है: ', 'Playing sample: ']) + (isHi() ? v.name_hi : v.name)); }
    catch (err) {
      if (err.status === 409 && 'speechSynthesis' in window) { const u = new SpeechSynthesisUtterance(SAMPLE[language]); u.lang = language; window.speechSynthesis.cancel(); window.speechSynthesis.speak(u); toast(t(['फ़ोन की अपनी आवाज़ में नमूना। असली आवाज़ अलग होगी।', "Sample in your phone's own voice. The real voice will differ."])); }
      else toast(err.message, { bad: true });
    }
  }
  function draw() {
    mount(list, ...data.voices.map((v) => h('div', { class: 'vrow' + (pick === v.id ? ' on' : ''), role: 'radio', 'aria-checked': pick === v.id, tabindex: 0, onclick: () => { pick = v.id; draw(); }, onkeydown: (e) => { if (e.key === 'Enter') { pick = v.id; draw(); } } },
      h('span', { class: 'rad' }), h('div', { style: 'flex:1' }, h('div', { style: 'font-size:18px;font-weight:700' }, isHi() ? v.name_hi : v.name), h('div', { style: 'font-size:14px;color:var(--muted)' }, isHi() ? v.desc_hi : v.desc)),
      h('button', { class: 'pill-btn', style: 'border-radius:24px;padding:0 14px 0 10px;gap:4px;font-size:14px', onclick: (e) => listen(v, e) }, icon('play', 22), t(['सुनें', 'Listen'])))),
      h('div', { style: 'margin-top:6px;font-size:13px;color:var(--muted);line-height:1.5' }, t(['Munshi हर कॉल में बताता है कि वह AI है। आवाज़ बदलने पर कॉल की भाषा के क्रियारूप (रही/रहा) भी बदल जाते हैं।', 'Munshi tells every caller it is an AI. Changing the voice also changes the Hindi verb forms (रही / रहा) it uses.'])));
  }
  async function keep() { try { await saveProfile({ voice: pick }); toast(t(['आवाज़ सेव हुई', 'Voice saved'])); go(from); } catch (e) { toast(e.message, { bad: true }); } }
  mount(root, h('div', { class: 'col' }, h('div', { class: 'sub-top' }, h('button', { class: 'btn-ic', 'aria-label': t(['वापस', 'Back']), onclick: () => go(from) }, icon('back', 28)), h('h1', {}, t(['Munshi की आवाज़', "Munshi's voice"]))), list,
    h('div', { class: 'bar' }, h('button', { class: 'big', onclick: keep }, t(['यही आवाज़ रखें', 'Keep this voice'])))));
  draw();
  return () => { audio?.pause(); window.speechSynthesis?.cancel(); };
}
