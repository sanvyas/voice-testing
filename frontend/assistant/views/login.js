// Sign in with a phone number: a six-digit code by SMS. A demo number is shown when the server has one switched on.
import { h, mount } from '/lab/ui.js';
import { setBusinessKey } from '/lab/api.js';
import { t, getLang, setLang } from '../i18n.js';
import { Logo, toast } from '../kit.js';

const API = '/api/assistant/auth';
// The server explains problems in English; the people using this are Hindi-first, so the common ones are shown in Hindi too.
const HI = [['not right', 'कोड सही नहीं है। SMS देखकर फिर कोशिश करें।'], ['expired', 'कोड की मियाद खत्म हो गई। नया कोड मँगाएँ।'], ['Too many wrong tries', 'बहुत गलत कोशिशें हुईं। नया कोड मँगाएँ।'], ['wait', 'थोड़ा रुकें, फिर नया कोड मँगाएँ।'],
  ['Too many codes', 'इस नंबर पर बहुत कोड माँगे गए। कुछ देर बाद कोशिश करें।'], ['not switched on', 'SMS से साइन इन अभी चालू नहीं है। बाद में कोशिश करें।'], ['could not be sent', 'कोड अभी नहीं भेजा जा सका। फिर कोशिश करें।']];
const say = (msg) => (getLang() === 'hi' ? (HI.find(([k]) => msg.includes(k)) || [])[1] || msg : msg);
async function post(path, body, key) {
  let res;
  try { res = await fetch(API + path, { method: 'POST', headers: { 'Content-Type': 'application/json', ...(key ? { 'X-Business-Key': key } : {}) }, body: body === undefined ? undefined : JSON.stringify(body) }); }
  catch { throw new Error(t(['इंटरनेट नहीं है। जाँचकर फिर कोशिश करें।', 'No internet. Check and try again.'])); }
  if (res.status === 204) return {};
  let data = {}; try { data = await res.json(); } catch { /* no body */ }
  if (!res.ok) throw new Error(typeof data.detail === 'string' ? say(data.detail) : (Array.isArray(data.detail) ? t(['नंबर सही नहीं है', 'That number does not look right']) : t(['कुछ गड़बड़ हुई', 'Something went wrong'])));
  return data;
}
export async function signOut() {
  try { const { getBusinessKey } = await import('/lab/api.js'); await post('/logout', undefined, getBusinessKey()); } catch { /* signing out on this phone is what matters */ }
  setBusinessKey('');
}

/** Shows the sign-in screen over the app. Resolves with {is_new} once the person is in. */
export function showLogin() {
  return new Promise(async (resolve) => {
    let cfg = { demo: null }; try { cfg = await (await fetch(API + '/config')).json(); } catch { /* no demo hint */ }
    const state = { step: 'phone', phone: '', masked: '', error: '', busy: false, wait: 0, agree: false, code: '', shake: false };
    const root = h('div', { class: 'login', role: 'dialog', 'aria-modal': 'true', 'aria-label': t(['साइन इन', 'Sign in']) });
    document.body.append(root);
    let timer = null;
    const digits = (v) => v.replace(/\D/g, '').slice(-10);
    let resendBtn = null;
    const resendLabel = () => (state.wait > 0 ? t([`दोबारा कोड (${state.wait}s)`, `Resend code (${state.wait}s)`]) : t(['दोबारा कोड भेजें', 'Resend code']));
    const paintResend = () => { if (resendBtn) { resendBtn.textContent = resendLabel(); resendBtn.disabled = state.wait > 0 || state.busy; } };  // only this button changes each second: a redraw would erase the digits being typed
    const startWait = (s) => { state.wait = s; clearInterval(timer); timer = setInterval(() => { state.wait = Math.max(0, state.wait - 1); if (state.wait === 0) clearInterval(timer); paintResend(); }, 1000); };

    async function sendCode() {
      const n = digits(state.phone);
      if (n.length !== 10) { state.error = t(['10 अंकों का मोबाइल नंबर लिखें', 'Enter a 10-digit mobile number']); return draw(); }
      if (!state.agree) { state.error = t(['आगे बढ़ने के लिए शर्तों और प्राइवेसी नीति से सहमत हों', 'Please agree to the Terms and Privacy Policy to continue']); return draw(); }
      state.busy = true; state.error = ''; draw();
      try { const r = await post('/request', { phone: '+91' + n }); state.step = 'code'; state.masked = r.phone; state.demo = r.demo; startWait(r.cooldown_s || 45); }
      catch (e) { state.error = e.message; }
      state.busy = false; draw();
    }
    async function verify(code) {
      state.busy = true; state.error = ''; draw();
      try {
        const r = await post('/verify', { phone: '+91' + digits(state.phone), code, accept: state.agree, device: navigator.userAgent.slice(0, 100) });
        setBusinessKey(r.token); clearInterval(timer); root.remove(); resolve(r);
        if (r.is_new) location.hash = '#/start';
        return;
      } catch (e) { state.error = e.message; state.code = ''; state.shake = true; }
      state.busy = false; draw(); state.shake = false;
    }

    function draw() {
      const lang = h('button', { class: 'login-lang', onclick: () => { setLang(getLang() === 'hi' ? 'en' : 'hi'); draw(); }, 'aria-label': 'Language' }, getLang() === 'hi' ? 'English' : 'हिन्दी');
      const err = state.error ? h('div', { class: 'login-err', role: 'alert' }, state.error) : null;
      let body;
      if (state.step === 'phone') {
        const phone = h('input', { type: 'tel', inputmode: 'numeric', autocomplete: 'tel-national', maxlength: 14, value: state.phone, placeholder: '98765 43210', 'aria-label': t(['मोबाइल नंबर', 'Mobile number']), oninput: (e) => { state.phone = e.target.value; }, onkeydown: (e) => { if (e.key === 'Enter') sendCode(); } });
        const agree = h('input', { type: 'checkbox', checked: state.agree, id: 'agree', onchange: (e) => { state.agree = e.target.checked; } });
        body = [h('h1', {}, t(['अपना नंबर डालें', 'Enter your number'])), h('p', {}, t(['हम आपको SMS से 6 अंकों का कोड भेजेंगे।', 'We will send you a 6-digit code by SMS.'])),
          h('label', { class: 'phone' }, h('span', {}, '+91'), phone), err,
          h('label', { class: 'agree', for: 'agree' }, agree, h('span', {}, t(['मैं ', 'I agree to the ']), h('a', { href: '/legal/terms', target: '_blank', rel: 'noopener' }, t(['शर्तों', 'Terms'])), t([' और ', ' and ']), h('a', { href: '/legal/privacy', target: '_blank', rel: 'noopener' }, t(['प्राइवेसी नीति', 'Privacy Policy'])), t([' से सहमत हूँ', '']))),
          h('button', { class: 'big', disabled: state.busy, onclick: sendCode }, state.busy ? t(['भेज रहे हैं…', 'Sending…']) : t(['कोड भेजें', 'Send code'])),
          cfg.demo ? h('button', { class: 'link demo', onclick: () => { state.phone = cfg.demo.phone.slice(-10); state.agree = true; draw(); } }, t(['डेमो दुकान आज़माएँ (सैंपल नंबर)', 'Try the demo shop (sample number)'])) : null];
        queueMicrotask(() => phone.focus());
      } else {
        // Six boxes drawn from one real (invisible) field on top: SMS autofill, paste, backspace and the number keyboard all keep working.
        const boxes = Array.from({ length: 6 }, () => h('div', { class: 'otp-box' }));
        const field = h('input', { type: 'text', inputmode: 'numeric', autocomplete: 'one-time-code', maxlength: 6, pattern: '[0-9]*', class: 'otp-input', value: state.code, 'aria-label': t(['6 अंकों का कोड', '6-digit code']),
          oninput: (e) => { e.target.value = e.target.value.replace(/\D/g, '').slice(0, 6); state.code = e.target.value; state.error = ''; paintBoxes(); if (state.code.length === 6 && !state.busy) verify(state.code); },
          onfocus: () => { focused = true; paintBoxes(); }, onblur: () => { focused = false; paintBoxes(); }, onkeydown: (e) => { if (e.key === 'Enter' && state.code.length >= 4) verify(state.code); } });
        let focused = true;
        const paintBoxes = () => boxes.forEach((b, i) => { b.textContent = state.code[i] || ''; b.className = 'otp-box' + (state.code[i] ? ' full' : '') + (focused && i === Math.min(state.code.length, 5) && !state.busy ? ' on' : '') + (state.error ? ' bad' : ''); });
        const code = field;
        const wrap = h('div', { class: 'otp-wrap' + (state.shake ? ' shake' : ''), onclick: () => field.focus() }, h('div', { class: 'otp-row' }, ...boxes), field);
        paintBoxes();
        const demoFill = state.demo && cfg.demo ? h('button', { class: 'link', onclick: () => { state.code = cfg.demo.code; field.value = state.code; paintBoxes(); verify(state.code); } }, t([`डेमो कोड भरें (${cfg.demo.code})`, `Fill the demo code (${cfg.demo.code})`])) : null;
        body = [h('h1', {}, t(['कोड डालें', 'Enter the code'])), h('p', {}, state.demo ? t(['डेमो नंबर है, इसलिए SMS नहीं जाएगा।', 'This is the demo number, so no SMS is sent.']) : t([`${state.masked} पर 6 अंकों का कोड भेजा गया`, `A 6-digit code was sent to ${state.masked}`])),
          wrap, err, demoFill, h('button', { class: 'big', disabled: state.busy || state.code.length < 4, onclick: () => state.code.length >= 4 && verify(state.code) }, state.busy ? t(['जाँच रहे हैं…', 'Checking…']) : t(['साइन इन', 'Sign in'])),
          h('div', { class: 'login-row' }, h('button', { class: 'link', onclick: () => { state.step = 'phone'; state.error = ''; state.code = ''; clearInterval(timer); draw(); } }, t(['नंबर बदलें', 'Change number'])),
            (resendBtn = h('button', { class: 'link', disabled: state.wait > 0 || state.busy, onclick: () => { state.code = ''; sendCode(); } }, resendLabel())))];
        queueMicrotask(() => { field.focus(); });
      }
      mount(root, h('div', { class: 'login-card' }, h('div', { class: 'login-top' }, h('div', { class: 'login-brand' }, Logo(40), h('b', {}, 'Munshi')), lang),
        h('div', { class: 'login-body' }, ...body), h('div', { class: 'login-foot' }, t(['आपका AI सहायक, जब आप कॉल न उठा पाएँ', 'Your AI assistant for the calls you cannot take']))));
    }
    draw();
  });
}
