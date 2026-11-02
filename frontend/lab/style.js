// Creativity (temperature) and reply length (max tokens): one saved setting for tests, Talk and releases.
import { h, toast } from './ui.js';
import { api } from './api.js';

export const LENGTHS = [[200, 'Short'], [350, 'Medium'], [600, 'Long'], [1000, 'Very long']];
export const creativityWord = (t) => (t < 0.4 ? 'Precise' : t < 0.9 ? 'Balanced' : 'Creative');
export const lengthLabel = (tokens) => (LENGTHS.find(([n]) => n === tokens) || [tokens, `${tokens} tokens`])[1];
const approxWords = (tokens) => Math.round((tokens * 0.75) / 10) * 10;

export async function styleControls() {
  const cur = await api('/settings/generation');
  const temp = h('input', { type: 'range', min: 0, max: 1.2, step: 0.1, value: cur.temperature, 'aria-label': 'Creativity', id: 'gen-temp' });
  const tempOut = h('b', {});
  const len = h('select', { 'aria-label': 'Reply length', id: 'gen-len' },
    ...(LENGTHS.some(([n]) => n === cur.max_tokens) ? [] : [h('option', { value: cur.max_tokens }, `Custom (${cur.max_tokens} tokens)`)]),
    ...LENGTHS.map(([n, label]) => h('option', { value: n }, `${label} · about ${approxWords(n)} words`)));
  len.value = String(cur.max_tokens);
  const show = () => { tempOut.textContent = `${creativityWord(+temp.value)} (${(+temp.value).toFixed(1)})`; };
  let timer = null;
  const save = () => {
    show(); clearTimeout(timer);
    timer = setTimeout(async () => {
      try { await api('/settings/generation', { method: 'PUT', body: { temperature: +temp.value, max_tokens: +len.value } }); toast('Saved: applies to your next test or talk'); }
      catch (e) { toast(e.message, true); }
    }, 350);
  };
  temp.addEventListener('input', save); len.addEventListener('change', save); show();
  return h('div', { class: 'stack' },
    h('label', { class: 'f' }, h('span', { class: 'row between' }, h('span', {}, 'Creativity'), tempOut), temp,
      h('small', {}, 'Low: steady, predictable answers. High: more varied and spontaneous.')),
    h('label', { class: 'f' }, 'Reply length', len, h('small', {}, 'The longest a single reply can be. For spoken conversation, Short or Medium usually sounds most natural.')));
}
