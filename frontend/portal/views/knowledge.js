import { h, mount, toast, ask, ago, dialog } from '/lab/ui.js';
import { A, apiForm, ic, ICONS } from '/assistant/net.js';
import { updateFromPhoto } from '/assistant/photo.js';
import { makeListener, canRecord } from '/assistant/listener.js';

const STATES = [['in_stock', 'In stock', ''], ['sold_out', 'Sold out', 'out'], ['ask', 'Ask me', 'ask']];
const WINDOWS = [[0, 'Never'], [1, '1 day'], [2, '2 days'], [3, '3 days'], [7, '1 week'], [14, '2 weeks']];

export async function render(page) {
  const listener = makeListener();
  const body = h('div', { class: 'stack', style: 'gap:18px' });
  mount(page, h('div', {}, h('h1', { class: 'title' }, 'Knowledge'), h('div', { class: 'sub' }, 'What the assistant may say about prices and stock. Keep it fresh with a photo, a few words, or one tap.')), body);
  await load();

  async function load() {
    const [data, asked] = await Promise.all([A('/board'), A('/board/asked')]);
    const say = h('input', { type: 'text', placeholder: 'kaju katli khatam, toor dal 170 ho gayi', 'aria-label': 'Update by typing', onkeydown: (e) => { if (e.key === 'Enter') doSay(say.value); } });
    const doSay = async (text) => {
      if (!text.trim()) return;
      try { const r = await A('/board/say', { method: 'POST', body: { text } }); if (r.changed.length) toast(r.changed.map((c) => `${c.name}: ${c.status.replace('_', ' ')}${c.price ? ' · ' + c.price : ''}`).join('  |  ')); if (r.unmatched.length) toast(`Could not place: ${r.unmatched.join(', ')}`, true); say.value = ''; await load(); } catch (e) { toast(e.message, true); }
    };
    const fileInput = h('input', { type: 'file', accept: 'image/*', hidden: true, onchange: (e) => { const f = e.target.files[0]; e.target.value = ''; if (f) updateFromPhoto(f, () => load()); } });
    const zone = h('div', { class: 'dropzone', role: 'button', tabindex: '0', 'aria-label': 'Choose or drop a photo', onclick: () => fileInput.click(), onkeydown: (e) => { if (e.key === 'Enter' || e.key === ' ') fileInput.click(); } },
      ic(ICONS.camera), h('div', { style: 'font-weight:700;margin-top:6px' }, 'Drop a photo here, or click to choose one'), h('div', { class: 'small muted' }, 'A price list, a shelf with price tags, a handwritten rate board, or a purchase bill. You review before anything changes.'), fileInput);
    zone.addEventListener('dragover', (e) => { e.preventDefault(); zone.classList.add('over'); }); zone.addEventListener('dragleave', () => zone.classList.remove('over'));
    zone.addEventListener('drop', (e) => { e.preventDefault(); zone.classList.remove('over'); const f = e.dataTransfer.files[0]; if (f) updateFromPhoto(f, () => load()); });
    const mic = h('button', { class: 'plain' }, 'Say it'); mic.disabled = !canRecord;
    mic.addEventListener('click', async () => {
      if (mic.dataset.on) return listener.cancel();
      mic.dataset.on = '1'; mic.textContent = 'Listening… click to stop';
      try { const got = await listener.listen({ silenceMs: 1500, waitMs: 8000 }); if (!got) toast('Did not hear anything'); else { mic.textContent = 'Understanding…'; const form = new FormData(); form.append('file', got.blob, 'speech.webm'); form.append('language', 'hi'); const { text } = await apiForm('/transcribe', form); if (!text) toast('Did not catch that', true); else { toast(`Heard: “${text}”`); await doSay(text); } } }
      catch (e) { toast(e.name === 'NotAllowedError' ? 'Allow the microphone to use this.' : e.message, true); }
      delete mic.dataset.on; mic.textContent = 'Say it';
    });
    const stale = h('select', { 'aria-label': 'Treat prices as out of date after', style: 'width:auto;min-height:40px', onchange: async (e) => { try { await A('/knowledge', { method: 'PUT', body: { stale_days: parseInt(e.target.value, 10) } }); toast('Saved'); load(); } catch (err) { toast(err.message, true); } } }, ...WINDOWS.map(([v, l]) => h('option', { value: v, selected: v === data.stale_days }, l)));
    mount(body,
      h('div', { class: 'grid2' },
        h('div', { class: 'stack' }, zone, h('div', { class: 'card stack' }, h('div', { style: 'font-weight:700' }, 'Say or type it'), h('div', { class: 'row', style: 'flex-wrap:nowrap' }, h('div', { class: 'grow' }, say), h('button', { class: 'plain', onclick: () => doSay(say.value) }, 'Update'), mic), h('button', { class: 'link', style: 'align-self:flex-start', onclick: importList }, 'Or paste a price list'))),
        h('div', { class: 'stack' },
          h('div', { class: 'card stack' }, h('h2', { class: 'sec' }, 'Keeping it fresh'), h('div', { class: data.stale ? 'notice' : 'notice ok' }, data.items.length ? (data.stale ? `${data.stale} price${data.stale > 1 ? 's are' : ' is'} out of date. The assistant treats ${data.stale > 1 ? 'them' : 'it'} as “ask me”.` : `Everything is up to date. Last checked ${ago(data.updated_at)}.`) : 'The board is empty.'),
            h('button', { class: 'btn', disabled: !data.items.length, onclick: async () => { const r = await A('/board/confirm', { method: 'POST' }); toast(`${r.confirmed} items confirmed for today`); load(); window.dispatchEvent(new Event('munshi-changed')); } }, ic(ICONS.check, [], true), 'Everything is the same as before'),
            h('label', { class: 'row between', style: 'font-weight:600;font-size:14px' }, h('span', {}, 'Treat a price as out of date after', h('div', { class: 'small muted', style: 'font-weight:400' }, 'Out-of-date items are never quoted to callers.')), stale)),
          asked.length ? h('div', { class: 'card stack' }, h('h2', { class: 'sec' }, 'Callers asked about these'), h('div', { class: 'small muted' }, 'The assistant could not answer. Add a price once and it will answer next time.'),
            ...asked.slice(0, 6).map((q) => h('div', { class: 'row between', style: 'flex-wrap:nowrap;border-top:1px solid var(--line);padding-top:10px' }, h('div', {}, h('div', { style: 'font-weight:600' }, q.term), h('div', { class: 'small muted' }, `${q.count} call${q.count > 1 ? 's' : ''}, last ${ago(q.last_at)}`)),
              h('div', { class: 'row', style: 'flex-wrap:nowrap' }, h('button', { class: 'plain', onclick: () => edit(null, q.term) }, 'Add'), h('button', { class: 'link', onclick: async () => { await A('/board/asked/dismiss', { method: 'POST', body: { term: q.term } }); load(); } }, 'Skip'))))) : null)),
      h('div', { class: 'card stack' }, h('div', { class: 'row between' }, h('h2', { class: 'sec' }, `Items (${data.items.length})`), h('button', { class: 'plain', onclick: () => edit(null) }, 'Add an item')),
        data.items.length ? h('table', { class: 'tbl' }, h('thead', {}, h('tr', {}, h('th', {}, 'Item'), h('th', { style: 'width:130px' }, 'Price'), h('th', { style: 'width:290px' }, 'Status'), h('th', { style: 'width:150px' }, 'Checked'), h('th', { style: 'width:60px' }, ''))),
          h('tbody', {}, ...data.items.map((i) => h('tr', {},
            h('td', {}, h('input', { type: 'text', value: i.name, 'aria-label': 'Item name', onchange: (e) => patch(i, { name: e.target.value }) })),
            h('td', {}, h('input', { type: 'text', value: i.price.replace(/^Rs /, ''), 'aria-label': `Price of ${i.name}`, inputmode: 'decimal', placeholder: 'price', onchange: (e) => patch(i, { price: e.target.value }) })),
            h('td', {}, h('div', { class: 'seg mini', role: 'group', 'aria-label': `Status of ${i.name}` }, ...STATES.map(([id, label, cls]) => h('button', { class: i.status === id ? `on ${cls}` : '', 'aria-pressed': String(i.status === id), onclick: () => patch(i, { status: id }) }, label)))),
            h('td', {}, h('span', { class: 'badge ' + (i.stale ? 'act' : '') }, i.stale ? `Old · ${ago(i.confirmed_at)}` : ago(i.confirmed_at))),
            h('td', {}, h('button', { class: 'link danger', 'aria-label': `Remove ${i.name}`, onclick: async () => { if (await ask(`Remove ${i.name}?`, { yes: 'Remove', danger: true })) { await A(`/board/${i.id}`, { method: 'DELETE' }); load(); } } }, ic(ICONS.x, [], true))))))) : h('div', { class: 'empty' }, 'Nothing here yet. Drop a photo of your price list above, or add an item.')));
  }

  async function patch(item, body) { try { await A(`/board/${item.id}`, { method: 'PUT', body }); await load(); window.dispatchEvent(new Event('munshi-changed')); } catch (e) { toast(e.message, true); load(); } }

  function edit(item, prefill = '') {
    const name = h('input', { type: 'text', placeholder: 'e.g. Basmati rice, 5 kg', 'aria-label': 'Item name', value: item?.name || prefill });
    const price = h('input', { type: 'text', placeholder: 'e.g. 450', 'aria-label': 'Price', inputmode: 'decimal' });
    const save = h('button', { class: 'btn' }, 'Add to board');
    const close = dialog('Add an item', h('div', { class: 'stack' }, name, price, save));
    save.addEventListener('click', async () => { save.disabled = true; try { await A('/board', { method: 'POST', body: { name: name.value, price: price.value } }); close(); load(); window.dispatchEvent(new Event('munshi-changed')); } catch (e) { toast(e.message, true); save.disabled = false; } });
  }

  function importList() {
    const text = h('textarea', { rows: 8, placeholder: 'One item per line:\nBasmati rice 5 kg - 450\nToor dal 1 kg - 160', 'aria-label': 'Price list' });
    const go = h('button', { class: 'btn' }, 'Add all');
    const close = dialog('Paste your price list', h('div', { class: 'stack' }, text, go));
    go.addEventListener('click', async () => { if (!text.value.trim()) return toast('Paste your list first', true); go.disabled = true; try { const r = await A('/board/import', { method: 'POST', body: { text: text.value } }); close(); toast(`${r.added} added${r.skipped.length ? `, ${r.skipped.length} skipped` : ''}`, r.added === 0); load(); } catch (e) { toast(e.message, true); go.disabled = false; } });
  }
}
