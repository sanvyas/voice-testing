import { h, mount, toast, ask, ago, dialog } from '/lab/ui.js';
import { A, apiForm, ic, ICONS } from '../net.js';
import { updateFromPhoto } from '../photo.js';
import { makeListener, canRecord } from '../listener.js';

const STATES = [['in_stock', 'In stock', ''], ['sold_out', 'Sold out', 'out'], ['ask', 'Ask me', 'ask']];
const changed = () => window.dispatchEvent(new Event('munshi-changed'));

export async function render(root) {
  const box = h('div', { class: 'stack', style: 'gap:14px' });
  const listener = makeListener();
  mount(root, h('a', { href: '#/setup', class: 'back' }, ic(ICONS.back), 'Setup'), box);
  await load();

  async function load() {
    const [data, status, asked] = await Promise.all([A('/board'), A('/status'), A('/board/asked')]);
    const say = h('input', { type: 'text', placeholder: 'kaju katli khatam, toor dal 170 ho gayi', 'aria-label': 'Update the board by typing', onkeydown: (e) => { if (e.key === 'Enter') doSay(say.value); } });
    const doSay = async (text) => {
      if (!text.trim()) return;
      try { const r = await A('/board/say', { method: 'POST', body: { text } });
        if (r.changed.length) toast(r.changed.map((c) => `${c.name}: ${c.status.replace('_', ' ')}${c.price ? ' · ' + c.price : ''}`).join('  |  ')); if (r.unmatched.length) toast(`Could not place: ${r.unmatched.join(', ')}`, true);
        say.value = ''; await load(); changed(); }
      catch (e) { toast(e.message, true); }
    };
    const photoInput = h('input', { type: 'file', accept: 'image/*', hidden: true, onchange: (e) => { const f = e.target.files[0]; e.target.value = ''; if (f) updateFromPhoto(f, () => load()); } });
    const mic = h('button', { class: 'btn ghost', style: 'flex:1' }, ic(ICONS.mic, [], true), 'Say it');
    mic.disabled = !canRecord;
    mic.addEventListener('click', async () => {
      if (mic.dataset.on) { listener.cancel(); return; }
      mic.dataset.on = '1'; mic.textContent = 'Listening… tap to stop';
      try {
        const got = await listener.listen({ silenceMs: 1500, waitMs: 8000 });
        if (!got) { toast('Did not hear anything'); } else {
          mic.textContent = 'Understanding…';
          const form = new FormData(); form.append('file', got.blob, 'speech.webm'); form.append('language', 'hi');
          const { text } = await apiForm('/transcribe', form);
          if (!text) toast('Did not catch that', true); else { toast(`Heard: “${text}”`); await doSay(text); }
        }
      } catch (e) { toast(e.name === 'NotAllowedError' ? 'Allow the microphone to use this.' : e.message, true); }
      delete mic.dataset.on; mic.textContent = ''; mic.append(ic(ICONS.mic, [], true), 'Say it');
    });
    const confirm = async () => { try { const r = await A('/board/confirm', { method: 'POST' }); toast(`${r.confirmed} items confirmed for today`); await load(); changed(); } catch (e) { toast(e.message, true); } };
    const stale = data.stale;
    mount(box,
      h('div', {}, h('h1', { class: 'title' }, "Today's board"), h('div', { class: 'sub' }, data.items.length ? `Munshi only says what is on this board. Last checked ${ago(data.updated_at)}.` : 'Add what you sell. In “Answer from Today’s board” mode, Munshi will only state prices and stock from here.')),
      data.items.length ? h('div', { class: 'notice ' + (stale ? '' : 'ok') }, h('div', { style: 'font-weight:700;margin-bottom:6px' }, stale ? `${stale} price${stale > 1 ? 's are' : ' is'} older than ${data.stale_days} day${data.stale_days > 1 ? 's' : ''}` : 'Everything is up to date'),
        h('div', { class: 'small', style: 'margin-bottom:10px' }, stale ? 'Munshi treats these as “ask me” until you check them, so it never quotes an old price.' : 'You do not need to update it daily. If nothing changed, one tap keeps it fresh.'),
        h('button', { class: 'btn', onclick: confirm }, ic(ICONS.check, [], true), 'Everything is the same as before')) : null,
      h('div', { class: 'tip' }, h('div', { style: 'font-weight:700;color:var(--primary-ink)' }, 'Update it the easy way'),
        h('div', { class: 'row', style: 'flex-wrap:nowrap' }, h('button', { class: 'btn', style: 'flex:1', onclick: () => photoInput.click() }, ic(ICONS.camera, [], true), 'Photo'), mic, photoInput),
        h('div', { class: 'small', style: 'color:var(--primary-ink)' }, 'Photo of your price list, shelf, rate board or a purchase bill. Or say or type it, like “toor dal 170 ho gayi”.'),
        h('div', { class: 'row', style: 'flex-wrap:nowrap' }, h('div', { class: 'grow' }, say), h('button', { class: 'plain', onclick: () => doSay(say.value) }, 'Update')),
        h('button', { class: 'link', style: 'align-self:flex-start', onclick: importList }, 'Or paste a price list')),
      asked.length ? h('div', { class: 'card stack' }, h('h2', { class: 'sec' }, 'Callers asked about these'), h('div', { class: 'small muted' }, 'The assistant could not answer. Add a price once and it will answer next time.'),
        ...asked.slice(0, 5).map((q) => h('div', { class: 'row between', style: 'flex-wrap:nowrap;border-top:1px solid var(--line);padding-top:10px' }, h('div', {}, h('div', { style: 'font-weight:600' }, q.term), h('div', { class: 'small muted' }, `${q.count} call${q.count > 1 ? 's' : ''}`)),
          h('div', { class: 'row', style: 'flex-wrap:nowrap' }, h('button', { class: 'plain', onclick: () => edit(null, q.term) }, 'Add'), h('button', { class: 'link', onclick: async () => { await A('/board/asked/dismiss', { method: 'POST', body: { term: q.term } }); load(); } }, 'Skip'))))) : null,
      data.items.length ? h('div', { class: 'card tight' }, ...data.items.map((i) => h('div', { class: 'item' },
        h('div', { class: 'row between', style: 'flex-wrap:nowrap' }, h('button', { class: 'link', style: 'color:var(--ink);padding:0;text-align:left;font-size:16px', onclick: () => edit(i) }, i.name), h('span', { class: 'pr' }, i.price || 'no price')),
        h('div', { class: 'seg', role: 'group', 'aria-label': `Status of ${i.name}` }, ...STATES.map(([id, label, cls]) => h('button', { class: (i.status === id ? `on ${cls}` : ''), 'aria-pressed': String(i.status === id), onclick: async () => { try { await A(`/board/${i.id}`, { method: 'PUT', body: { status: id } }); await load(); changed(); } catch (e) { toast(e.message, true); } } }, label))),
        i.stale ? h('div', { class: 'small', style: 'color:var(--warn);font-weight:600' }, `Not checked since ${ago(i.confirmed_at)}. Treated as “ask me”.`) : null))) : h('div', { class: 'card empty' }, 'The board is empty.'),
      h('button', { class: 'btn', onclick: () => edit(null) }, 'Add an item'),
      h('div', { class: 'small muted', style: 'line-height:1.5' }, [h('b', { style: 'color:var(--ink)' }, 'Ask me'), ' means Munshi takes a message and you call back with the right answer. It never guesses stock or price.']),
      status.mode !== 'board' ? h('div', { class: 'notice' }, ['The assistant is not using this board yet. ', h('a', { href: '#/setup', style: 'font-weight:700;text-decoration:underline' }, 'Choose “Answer from Today’s board” in Setup')]) : null);
  }

  function edit(item, prefill = '') {
    const name = h('input', { type: 'text', placeholder: 'e.g. Basmati rice, 5 kg', 'aria-label': 'Item name', value: item?.name || prefill });
    const price = h('input', { type: 'text', placeholder: 'e.g. 450 (leave empty if it varies)', 'aria-label': 'Price', value: (item?.price || '').replace(/^Rs /, ''), inputmode: 'decimal' });
    const save = h('button', { class: 'btn' }, item ? 'Save' : 'Add to board');
    const close = dialog(item ? 'Edit item' : 'Add an item', h('div', { class: 'stack' }, name, price, save, item ? h('button', { class: 'link danger', onclick: async () => { if (await ask(`Remove ${item.name} from the board?`, { yes: 'Remove', danger: true })) { await A(`/board/${item.id}`, { method: 'DELETE' }); close(); load(); } } }, 'Remove this item') : null));
    save.addEventListener('click', async () => {
      save.disabled = true;
      try { if (item) await A(`/board/${item.id}`, { method: 'PUT', body: { name: name.value, price: price.value } }); else await A('/board', { method: 'POST', body: { name: name.value, price: price.value } }); close(); load(); changed(); }
      catch (e) { toast(e.message, true); save.disabled = false; }
    });
  }

  function importList() {
    const text = h('textarea', { rows: 8, placeholder: 'One item per line:\nBasmati rice 5 kg - 450\nToor dal 1 kg - 160\nSugar', 'aria-label': 'Price list' });
    const go = h('button', { class: 'btn' }, 'Add all');
    const close = dialog('Paste your price list', h('div', { class: 'stack' }, h('div', { class: 'small muted' }, 'Copy it from a WhatsApp message or a note. Prices are optional.'), text, go));
    go.addEventListener('click', async () => {
      if (!text.value.trim()) return toast('Paste your list first', true);
      go.disabled = true;
      try { const r = await A('/board/import', { method: 'POST', body: { text: text.value } }); close(); toast(`${r.added} added${r.skipped.length ? `, ${r.skipped.length} skipped` : ''}`, r.added === 0); load(); }
      catch (e) { toast(e.message, true); go.disabled = false; }
    });
  }
  return () => listener.close();
}
