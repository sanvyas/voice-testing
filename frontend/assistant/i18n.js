// Hindi first, English on a tap. t(['हिन्दी', 'English']) picks one. The choice is kept on the phone.
const KEY = 'munshi.lang';
let lang = 'hi';
try { lang = localStorage.getItem(KEY) === 'en' ? 'en' : 'hi'; } catch { /* storage blocked */ }
export const isHi = () => lang === 'hi';
export const t = (pair) => (lang === 'hi' ? pair[0] : pair[1]);
export const getLang = () => lang;
export function setLang(next) {
  lang = next === 'en' ? 'en' : 'hi';
  try { localStorage.setItem(KEY, lang); } catch { /* storage blocked */ }
  document.documentElement.lang = lang;
  window.dispatchEvent(new Event('munshi-lang'));
}
document.documentElement.lang = lang;

export const initial = (name) => { const s = (name || '').trim(); return /^[+0-9]/.test(s) ? '#' : (s.charAt(0).toUpperCase() || '?'); };
export const dayLabel = (d) => (d === 0 ? t(['आज', 'Today']) : d === 1 ? t(['कल', 'Yesterday']) : isHi() ? `${d} दिन पहले` : `${d} days ago`);
export const waitingFor = (d) => (isHi() ? `${d} दिन से बाकी` : `Pending for ${d} day${d === 1 ? '' : 's'}`);

const IST = 'Asia/Kolkata';
export function clock(iso) {
  const parts = new Intl.DateTimeFormat('en-GB', { timeZone: IST, hour: 'numeric', minute: '2-digit', hour12: false }).formatToParts(new Date(iso));
  const hh = +parts.find((p) => p.type === 'hour').value % 24; const mm = parts.find((p) => p.type === 'minute').value;
  const h12 = hh % 12 || 12;
  if (!isHi()) return `${h12}:${mm} ${hh < 12 ? 'am' : 'pm'}`;
  return `${h12}:${mm} ${hh < 4 ? 'रात' : hh < 12 ? 'सुबह' : hh < 16 ? 'दोपहर' : hh < 20 ? 'शाम' : 'रात'}`;
}
export function duration(s) {
  s = Math.max(0, Math.round(s || 0));
  if (s < 60) return isHi() ? `${s} सेकंड` : `${s} sec`;
  const m = Math.floor(s / 60); const r = s % 60;
  return isHi() ? `${m} मिनट${r ? ` ${r} सेकंड` : ''}` : `${m} min${r ? ` ${r} sec` : ''}`;
}
/** "Rs 42/kg" -> "₹42/kg" (or ₹42/किलो in Hindi). */
export function money(price) {
  let p = String(price || '').trim().replace(/^(?:rs\.?|₹|inr)\s*/i, '');
  if (!p) return '';
  if (/^\d/.test(p)) p = '₹' + p;
  if (isHi()) p = p.replace(/\/\s*(kg|kilo)\b/i, '/किलो').replace(/\/\s*(litre|liter|ltr|l)\b/i, '/लीटर');
  return p;
}
export function freshness(hours) {
  if (hours >= 10 ** 5) return t(['पक्का नहीं किया', 'Not confirmed yet']);
  if (hours === 0) return t(['अभी पक्का किया', 'Just confirmed']);
  if (hours < 24) return isHi() ? `${hours} घंटे पहले पक्का` : `Confirmed ${hours} hours ago`;
  const d = Math.round(hours / 24);
  return isHi() ? `${d} दिन पुराना` : `${d} days old`;
}
