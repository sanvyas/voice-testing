import { h, mount, toast, ask, ago, dialog } from '/lab/ui.js';
import { A, ic, ICONS } from '../net.js';

const STATES = [['in_stock', 'In stock', ''], ['sold_out', 'Sold out', 'out'], ['ask', 'Ask me', 'ask']];

export async function render(root) {
  const box = h('div', { class: 'stack', style: 'gap:14px' });
  mount(root, h('a', { href: '#/setup', class: 'back' }, ic(ICONS.back), 'Setup'), box);
  await load();

  async function load() {
    const [data, status] = await Promise.all([A('/board'), A('/status')]);
    const say = h('input', { type: 'text', placeholder: 'e.g. kaju katli khatam, toor dal aa gayi', 'aria-label': 'Update the board by typing', onkeydown: (e) => { if (e.key === 'Enter') doSay(); } });
    const doSay = async () => {
      if (!say.value.trim()) return;
      try { const r = await A('/board/say', { method: 'POST', body: { text: say.value } });
        if (r.changed.length) toast(r.changed.map((c) => `${c.name}: ${c.status.replace('_', ' ')}`).join(' · ')); if (r.unmatched.length) toast(`Could not place: ${r.unmatched.join(', ')}`, true); say.value = ''; await load(); window.dispatchEvent(new Event('munshi-changed')); }
      catch (e) { toast(e.message, true); }
    };
    mount(box,
      h('div', {}, h('h1', { class: 'title' }, "Today's board"), h('div', { class: 'sub' }, data.items.length ? `Munshi only says what is on this board. Updated ${ago(data.updated_at)}.` : 'Add what you sell. In “Answer from Today’s board” mode, Munshi will only state prices and stock from here.')),
      h('div', { class: 'tip' }, h('div', { style: 'font-weight:700;color:var(--primary-ink)' }, 'Update it in 5 seconds'),
        h('div', { class: 'row', style: 'flex-wrap:nowrap' }, h('div', { class: 'grow' }, say), h('button', { class: 'plain', onclick: doSay }, 'Update')),
        h('div', { class: 'small', style: 'color:var(--primary-ink)' }, 'Type it the way you would say it, tap a status below, or paste your whole price list.'),
        h('button', { class: 'btn ghost', onclick: importList }, ic(ICONS.board, [], true), 'Paste your price list')),
      data.items.length ? h('div', { class: 'card tight' }, ...data.items.map((i) => h('div', { class: 'item' },
        h('div', { class: 'row between', style: 'flex-wrap:nowrap' }, h('button', { class: 'link', style: 'color:var(--ink);padding:0;text-align:left;font-size:16px', onclick: () => edit(i) }, i.name), h('span', { class: 'pr' }, i.price || 'no price')),
        h('div', { class: 'seg', role: 'group', 'aria-label': `Status of ${i.name}` }, ...STATES.map(([id, label, cls]) => h('button', { class: (i.status === id ? `on ${cls}` : ''), 'aria-pressed': String(i.status === id), onclick: async () => { try { await A(`/board/${i.id}`, { method: 'PUT', body: { status: id } }); await load(); window.dispatchEvent(new Event('munshi-changed')); } catch (e) { toast(e.message, true); } } }, label)))))) : h('div', { class: 'card empty' }, 'The board is empty.'),
      h('button', { class: 'btn', onclick: () => edit(null) }, 'Add an item'),
      h('div', { class: 'small muted', style: 'line-height:1.5' }, [h('b', { style: 'color:var(--ink)' }, 'Ask me'), ' means Munshi takes a message and you call back with the right answer. It never guesses stock or price.']),
      status.mode !== 'board' ? h('div', { class: 'notice' }, ['The assistant is not using this board yet. ', h('a', { href: '#/setup', style: 'font-weight:700;text-decoration:underline' }, 'Choose “Answer from Today’s board” in Setup')]) : null);
  }

  function edit(item) {
    const name = h('input', { type: 'text', placeholder: 'e.g. Basmati rice, 5 kg', 'aria-label': 'Item name', value: item?.name || '' });
    const price = h('input', { type: 'text', placeholder: 'e.g. 450 (leave empty if it varies)', 'aria-label': 'Price', value: (item?.price || '').replace(/^Rs /, ''), inputmode: 'decimal' });
    const save = h('button', { class: 'btn' }, item ? 'Save' : 'Add to board');
    const close = dialog(item ? 'Edit item' : 'Add an item', h('div', { class: 'stack' }, name, price, save, item ? h('button', { class: 'link danger', onclick: async () => { if (await ask(`Remove ${item.name} from the board?`, { yes: 'Remove', danger: true })) { await A(`/board/${item.id}`, { method: 'DELETE' }); close(); load(); } } }, 'Remove this item') : null));
    save.addEventListener('click', async () => {
      save.disabled = true;
      try { if (item) await A(`/board/${item.id}`, { method: 'PUT', body: { name: name.value, price: price.value } }); else await A('/board', { method: 'POST', body: { name: name.value, price: price.value } }); close(); load(); }
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
}
