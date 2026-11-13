import { h, mount, toast, ask, dialog } from '/lab/ui.js';
import { A, ic, ICONS, initials, avatarClass } from '../net.js';

export async function render(root) {
  const box = h('div', { class: 'stack', style: 'gap:14px' });
  mount(root, h('div', {}, h('h1', { class: 'title' }, 'Contacts'), h('div', { class: 'sub' }, 'People you always want to talk to yourself')), box);
  await load();

  async function load(q = '') {
    const all = await A('/contacts');
    const shown = all.filter((c) => !q || (c.name + c.phone).toLowerCase().includes(q.toLowerCase()));
    const search = h('label', { class: 'search' }, ic(ICONS.search, [[11, 11, 7]], true), h('input', { type: 'search', placeholder: 'Search name or number', 'aria-label': 'Search contacts', value: q, oninput: (e) => { clearTimeout(search.t); search.t = setTimeout(() => { load(e.target.value).then(() => document.querySelector('.search input')?.focus()); }, 200); } }));
    mount(box, search,
      h('div', { class: 'notice ok' }, h('b', {}, 'Your phone always rings first. '), 'If you miss someone on this list, they hear that you are unavailable and you get a missed call. Everyone else is answered by Munshi.'),
      h('div', { class: 'card tight' }, shown.length ? h('div', {}, ...shown.map((c) => h('div', { class: 'contact' },
        h('span', { class: `avatar sm ${avatarClass(c.name)}` }, initials(c.name)),
        h('div', { class: 'grow' }, h('div', { class: 'nm' }, c.name), h('div', { class: 'ph' }, c.phone)),
        h('input', { class: 'sw', type: 'checkbox', role: 'switch', checked: c.always_ring, 'aria-label': `Always ring me for ${c.name}`, onchange: async (e) => { try { await A(`/contacts/${c.id}`, { method: 'PUT', body: { always_ring: e.target.checked } }); toast(e.target.checked ? `${c.name} will always ring you` : `${c.name} can be answered by the assistant`); } catch (err) { toast(err.message, true); e.target.checked = !e.target.checked; } } }),
        h('button', { class: 'link danger', 'aria-label': `Remove ${c.name}`, onclick: async () => { if (await ask(`Remove ${c.name}?`, { yes: 'Remove', danger: true })) { await A(`/contacts/${c.id}`, { method: 'DELETE' }); load(q); } } }, ic(ICONS.x, [], true)))))
        : h('div', { class: 'empty' }, all.length ? 'No match.' : 'No contacts yet. Everyone is answered by the assistant when you miss a call.')),
      h('div', { class: 'row', style: 'flex-wrap:nowrap' }, h('button', { class: 'btn', onclick: addOne }, 'Add contact'), h('button', { class: 'btn ghost', onclick: addMany }, 'Paste many')));
  }

  function addOne() {
    const name = h('input', { type: 'text', placeholder: 'Name, e.g. Mummy', 'aria-label': 'Name' });
    const phone = h('input', { type: 'tel', placeholder: 'Phone, e.g. 98765 43210', 'aria-label': 'Phone number', inputmode: 'tel' });
    const go = h('button', { class: 'btn' }, 'Add contact');
    const close = dialog('Add a contact', h('div', { class: 'stack' }, name, phone, go));
    go.addEventListener('click', async () => { go.disabled = true; try { await A('/contacts', { method: 'POST', body: { name: name.value, phone: phone.value, always_ring: true } }); close(); toast('Added'); load(); } catch (e) { toast(e.message, true); go.disabled = false; } });
  }

  function addMany() {
    const bulk = h('textarea', { rows: 6, placeholder: 'One per line:\nRavi, 9876543210\nSunita, 98765 43211', 'aria-label': 'Paste many contacts' });
    const go = h('button', { class: 'btn' }, 'Add all');
    const close = dialog('Paste many contacts', h('div', { class: 'stack' }, bulk, go));
    go.addEventListener('click', async () => {
      if (!bulk.value.trim()) return toast('Paste some contacts first', true);
      go.disabled = true;
      try { const r = await A('/contacts/import', { method: 'POST', body: { text: bulk.value } }); close(); toast(`${r.added} added${r.skipped.length ? `, ${r.skipped.length} skipped` : ''}`, r.added === 0); load(); }
      catch (e) { toast(e.message, true); go.disabled = false; }
    });
  }
}
