import { h, mount, toast, ask, ago } from '/lab/ui.js';
import { A } from '/assistant/net.js';
import { businessList, selectedId } from '../ctx.js';

const VAR = /\{\{\s*([A-Za-z_][A-Za-z0-9_]*)\s*\}\}/g;
const usedIn = (t) => [...new Set([...t.matchAll(VAR)].map((m) => m[1]))];

export async function render(page) {
  const list = await businessList();
  const sel = list.find((b) => b.id === selectedId());
  let scope = sel ? 'business' : 'platform'; let kind = 'assistant'; let previewBiz = sel ? sel.id : (list[0] ? list[0].id : '');
  let data = null; let timer = null;
  const body = h('div', { class: 'stack', style: 'gap:16px' });
  mount(page, h('div', {}, h('h1', { class: 'title' }, 'Prompts'), h('div', { class: 'sub' }, 'Write what the AI is told. Put a {{variable}} where a detail should go, and it is filled in from each business’s own information: its name, hours, address, prices and more. Saved changes apply to the very next call.')), body);
  await load();

  async function load() { data = await A(`/prompts?scope=${scope}`); draw(); }

  function draw() {
    const tpl = data.templates[kind];
    const original = tpl.value;
    const ta = h('textarea', { class: 'editor', spellcheck: 'false', 'aria-label': tpl.label }, original);
    const status = h('div', { class: 'small' }); const preview = h('pre', { class: 'prompt' }); const lockedBox = h('div', { class: 'locked' }); const values = h('div', { class: 'stack', style: 'gap:6px' }); const meta = h('div', { class: 'small muted' });
    const save = h('button', { class: 'btn', style: 'width:auto' }, 'Save changes');
    const chips = h('div', { style: 'display:flex;flex-wrap:wrap;gap:8px' });

    const dirty = () => ta.value.trim() !== original.trim();
    const refreshChips = () => { const used = new Set(usedIn(ta.value)); mount(chips, ...tpl.variables.map((v) => h('button', { type: 'button', class: 'varchip' + (used.has(v.name) ? ' used' : ''), title: v.description, onclick: () => { ta.focus(); ta.setRangeText(`{{${v.name}}}`, ta.selectionStart, ta.selectionEnd, 'end'); ta.dispatchEvent(new Event('input')); } }, `{{${v.name}}}`))); };
    const refreshStatus = (unknown = []) => {
      save.disabled = !dirty() || unknown.length > 0;
      status.style.color = unknown.length ? 'var(--danger)' : '';
      status.textContent = unknown.length ? `Not a variable: ${unknown.map((u) => `{{${u}}}`).join(', ')}. Pick from the list above.` : (dirty() ? 'Unsaved changes. The preview on the right shows exactly what the AI would read.' : (tpl.own ? (scope === 'business' ? 'This business has its own version.' : 'The platform has its own version.') : (scope === 'business' ? 'Following the platform text.' : 'Showing the built-in text.')));
    };
    async function refreshPreview() {
      try {
        const r = await A('/prompts/preview', { method: 'POST', body: { kind, text: ta.value, business_id: previewBiz } });
        preview.textContent = r.text; lockedBox.textContent = r.locked; lockedBox.parentElement.hidden = !r.locked;
        meta.textContent = `${r.words} words${r.business ? ` · filled in for ${r.business}` : ''}`;
        mount(values, ...Object.entries(r.values).map(([k, v]) => h('div', { class: 'small' }, h('code', {}, `{{${k}}}`), ' → ', h('span', { class: 'muted' }, v ? (v.length > 90 ? `${v.slice(0, 90).replace(/\n/g, ' ')}…` : v.replace(/\n/g, ' ')) : '(empty for this business)'))));
        refreshStatus(r.unknown);
      } catch (e) { preview.textContent = e.message; }
    }
    ta.addEventListener('input', () => { refreshChips(); refreshStatus(unknownLocal()); clearTimeout(timer); timer = setTimeout(refreshPreview, 350); });
    const unknownLocal = () => usedIn(ta.value).filter((u) => !tpl.variables.some((v) => v.name === u));

    save.addEventListener('click', async () => {
      save.disabled = true;
      try { data = await A('/prompts', { method: 'PUT', body: { scope, templates: { [kind]: ta.value } } }); toast('Saved. The next call uses it.'); window.dispatchEvent(new Event('munshi-changed')); draw(); }
      catch (e) { toast(e.message, true); refreshStatus(); }
    });
    const back = h('button', { class: 'plain', onclick: () => { ta.value = scope === 'business' ? tpl.inherited : tpl.default; ta.dispatchEvent(new Event('input')); } }, scope === 'business' ? 'Use the platform text' : 'Use the built-in text');

    const scopeTabs = sel ? h('div', { class: 'tabs2', role: 'tablist', 'aria-label': 'Who this applies to' },
      h('button', { class: scope === 'business' ? 'on' : '', onclick: () => { scope = 'business'; load(); } }, `Only ${sel.name}`), h('button', { class: scope === 'platform' ? 'on' : '', onclick: () => { scope = 'platform'; load(); } }, 'Platform default (everyone)')) : null;
    const kinds = h('div', { class: 'tabs2', role: 'tablist', 'aria-label': 'Which prompt' }, ...Object.entries(data.templates).map(([id, t]) => h('button', { class: kind === id ? 'on' : '', onclick: () => { kind = id; draw(); } }, t.label, t.own ? ' •' : '')));
    const previewPick = h('select', { 'aria-label': 'Preview with business', style: 'width:auto;max-width:260px', onchange: (e) => { previewBiz = e.target.value; refreshPreview(); } }, ...list.map((b) => h('option', { value: b.id, selected: b.id === previewBiz }, b.name)));

    mount(body, scopeTabs,
      scope === 'platform' ? h('div', { class: 'notice' }, 'You are editing the platform default. It applies to every business that has not set its own version.') : h('div', { class: 'notice ok' }, `You are editing the version for ${sel.name} only. Other businesses are not affected.`),
      kinds,
      h('div', { class: 'grid2', style: 'align-items:start' },
        h('div', { class: 'card stack' },
          h('div', {}, h('h2', { class: 'sec' }, tpl.label), h('div', { class: 'small muted' }, tpl.help)),
          ta,
          h('div', { class: 'stack', style: 'gap:8px' }, h('div', { class: 'small', style: 'font-weight:700' }, 'Click a variable to put it where your cursor is'), chips),
          status,
          h('div', { class: 'row' }, save, back),
          tpl.locked ? h('div', { class: 'stack', style: 'gap:6px' }, h('div', { class: 'small', style: 'font-weight:700' }, 'Always added after your text (cannot be changed)'), h('div', { class: 'locked' }, tpl.locked)) : null),
        h('div', { class: 'stack' },
          h('div', { class: 'card stack' }, h('div', { class: 'row between' }, h('h2', { class: 'sec' }, 'What the AI reads'), previewPick), preview,
            h('div', { hidden: true }, h('div', { class: 'small', style: 'font-weight:700;margin:6px 0' }, 'Then, always'), lockedBox), meta),
          h('details', { class: 'card stack' }, h('summary', { style: 'cursor:pointer;font-weight:700' }, 'What each variable is filled with'), h('div', { style: 'margin-top:10px' }, values)),
          h('div', { class: 'card stack' }, h('h2', { class: 'sec' }, 'Versions'),
            data.history.length ? h('div', {}, ...data.history.map((v) => h('div', { class: 'hist' }, h('div', {}, h('b', {}, `Version ${v.version}`), h('div', { class: 'small muted' }, `${ago(v.at)}${v.kinds.length ? ' · ' + v.kinds.join(', ') : ' · built-in text'}`)),
              h('button', { class: 'plain', onclick: async () => { if (await ask(`Go back to version ${v.version}? Your current text is kept in the history.`, { yes: 'Restore' })) { data = await A('/prompts/restore', { method: 'POST', body: { scope, version: v.version } }); toast(`Restored version ${v.version}`); draw(); } } }, 'Restore'))))
              : h('div', { class: 'muted' }, data.version ? 'No earlier versions kept.' : 'No changes saved yet. Each save keeps the one before it, up to 20.')))));
    body.append(lexiconCard());
    refreshChips(); refreshStatus(); refreshPreview();
  }

  /* Local words and how to say them: used by the voice, the listener and the AI prompt. */
  function lexiconCard() {
    const box = h('div', { class: 'card stack', id: 'lexicon' }); let st = null; let rows = []; let saved = '[]';
    const who = scope === 'business' && sel ? `for ${sel.name}` : 'for every business';
    const keep = () => JSON.stringify(rows.filter((r) => r.word.trim() && r.say.trim()));
    async function load() { st = await A(`/lexicon?scope=${scope}`); rows = st.entries.map((e) => ({ word: e.word, say: e.say, meaning: e.meaning || '' })); saved = keep(); paint(); }
    function paint() {
      const save = h('button', { class: 'btn', style: 'width:auto', disabled: keep() === saved }, 'Save words');
      const grid = h('div', { class: 'stack', style: 'gap:8px' });
      const drawRows = () => mount(grid, h('div', { class: 'small muted', style: 'display:grid;grid-template-columns:1.1fr 1.1fr 1.2fr 40px;gap:8px;font-weight:700' }, h('span', {}, 'Word, as written (add other spellings with commas)'), h('span', {}, 'Say it as'), h('span', {}, 'Meaning for the AI (optional)'), h('span', {})),
        ...rows.map((r, i) => h('div', { style: 'display:grid;grid-template-columns:1.1fr 1.1fr 1.2fr 40px;gap:8px;align-items:center' },
          h('input', { value: r.word, placeholder: 'kaju katli, kaju kathli', 'aria-label': 'Word', oninput: (e) => { r.word = e.target.value; save.disabled = keep() === saved; } }),
          h('input', { value: r.say, placeholder: 'काजू कतली', 'aria-label': 'Say it as', oninput: (e) => { r.say = e.target.value; save.disabled = keep() === saved; } }),
          h('input', { value: r.meaning, placeholder: 'cashew fudge sweet', 'aria-label': 'Meaning', oninput: (e) => { r.meaning = e.target.value; save.disabled = keep() === saved; } }),
          h('button', { class: 'plain', 'aria-label': 'Remove this word', onclick: () => { rows.splice(i, 1); drawRows(); save.disabled = keep() === saved; } }, '✕'))));
      drawRows();
      const add = h('button', { class: 'plain', onclick: () => { rows.push({ word: '', say: '', meaning: '' }); drawRows(); } }, '+ Add a word');
      const names = scope === 'business' && sel ? h('button', { class: 'plain', onclick: () => { for (const w of [sel.name, sel.owner_name].filter(Boolean)) if (!rows.some((r) => r.word.toLowerCase() === w.toLowerCase())) rows.push({ word: w, say: '', meaning: '' }); drawRows(); save.disabled = keep() === saved; } }, '+ Add the business and owner name') : null;
      save.addEventListener('click', async () => {
        save.disabled = true;
        try { st = await A('/lexicon', { method: 'PUT', body: { scope, entries: JSON.parse(keep()) } }); rows = st.entries.map((e) => ({ word: e.word, say: e.say, meaning: e.meaning || '' })); saved = keep(); toast('Saved. The next call uses these words.'); paint(); }
        catch (e) { toast(e.message, true); save.disabled = false; }
      });
      const test = h('input', { placeholder: 'Try: babuji sweets में काजू कतली ₹480 किलो है, शाम 5 बजे आइए', style: 'flex:1', 'aria-label': 'Sentence to try' }); const out = h('div', { class: 'locked', style: 'min-height:40px' }, 'The spoken form shows here.');
      const run = h('button', { class: 'plain', onclick: async () => { try { const r = await A('/lexicon/test', { method: 'POST', body: { text: test.value, scope } }); out.textContent = r.spoken || ''; } catch (e) { out.textContent = e.message; } } }, 'Show how it will be said');
      const table = (items) => h('div', { class: 'small', style: 'display:grid;grid-template-columns:1fr 1fr 1.2fr;gap:4px 12px;max-height:260px;overflow:auto' }, ...items.flatMap((e) => [h('span', {}, e.word), h('span', { style: 'font-weight:700' }, e.say), h('span', { class: 'muted' }, e.meaning || '')]));
      mount(box,
        h('div', {}, h('h2', { class: 'sec' }, `Local words and how to say them (${who})`),
          h('div', { class: 'small muted' }, 'List the words your callers use, and how each one should sound. The voice says them your way, the listener expects them, and the AI learns what they mean. Write “Say it as” in Devanagari for Hindi. A common starter list is already built in; yours wins when a word is on both.')),
        grid, h('div', { class: 'row' }, add, names), h('div', { class: 'row' }, save),
        h('div', { class: 'stack', style: 'gap:8px' }, h('div', { class: 'small', style: 'font-weight:700' }, 'Test a sentence (uses the words as last saved)'), h('div', { class: 'row' }, test, run), out),
        st.inherited && st.inherited.length ? h('details', {}, h('summary', { style: 'cursor:pointer;font-weight:700' }, `Platform words that also apply (${st.inherited.length})`), h('div', { style: 'margin-top:8px' }, table(st.inherited))) : null,
        h('details', {}, h('summary', { style: 'cursor:pointer;font-weight:700' }, `Built-in starter words (${st.builtin.length})`), h('div', { style: 'margin-top:8px' }, table(st.builtin))));
    }
    load().catch((e) => { box.textContent = e.message; });
    return box;
  }
}
