import { h, mount, toast, ask, field } from '/lab/ui.js';
import { A } from '../net.js';

export async function render(root) {
  const box = h('div', { class: 'stack', style: 'gap:18px' });
  mount(root, h('div', {}, h('h1', {}, 'Contacts'), h('div', { class: 'muted' }, 'People you always want to talk to yourself. The assistant never answers them: your phone rings first, and if you miss them they just see you are unavailable.')), box);
  await load();

  async function load() {
    const contacts = await A('/contacts');
    const name = h('input', { placeholder: 'Name, e.g. Mummy', 'aria-label': 'Name' });
    const phone = h('input', { placeholder: 'Phone, e.g. 98765 43210', 'aria-label': 'Phone number', inputmode: 'tel' });
    const add = h('button', { class: 'go' }, 'Add contact');
    add.addEventListener('click', async () => {
      add.disabled = true;
      try { await A('/contacts', { method: 'POST', body: { name: name.value, phone: phone.value, always_ring: true } }); toast('Added'); await load(); }
      catch (e) { toast(e.message, true); add.disabled = false; }
    });
    const bulk = h('textarea', { rows: 4, placeholder: 'One per line:\nRavi, 9876543210\nSunita, 98765 43211', 'aria-label': 'Paste many contacts', style: 'min-height:96px' });
    const imp = h('button', {}, 'Add all');
    imp.addEventListener('click', async () => {
      if (!bulk.value.trim()) return toast('Paste some contacts first', true);
      imp.disabled = true;
      try { const r = await A('/contacts/import', { method: 'POST', body: { text: bulk.value } }); toast(`${r.added} added${r.skipped.length ? `, ${r.skipped.length} skipped` : ''}`, r.added === 0); if (r.skipped.length) console.info(r.skipped); await load(); }
      catch (e) { toast(e.message, true); imp.disabled = false; }
    });
    mount(box,
      h('div', { class: 'card stack' }, h('h2', { style: 'margin:0' }, 'Add someone'), h('div', { class: 'row', style: 'flex-wrap:nowrap' }, h('div', { class: 'grow' }, name), h('div', { class: 'grow' }, phone)), add,
        h('details', { class: 'more' }, h('summary', {}, 'Paste many at once'), h('div', { class: 'stack', style: 'margin-top:12px' }, bulk, imp))),
      h('div', { class: 'card' }, h('h2', {}, `Your contacts (${contacts.length})`),
        contacts.length ? h('div', {}, ...contacts.map((c) => h('div', { class: 'contact' },
          h('div', { class: 'grow' }, h('div', { class: 't' }, c.name), h('div', { class: 'd' }, c.phone)),
          h('label', { class: 'row', style: 'gap:8px;font-size:13px;font-weight:600' }, 'Always ring me', h('span', { class: 'switch' }, h('input', { type: 'checkbox', checked: c.always_ring, 'aria-label': `Always ring me for ${c.name}`, onchange: async (e) => { try { await A(`/contacts/${c.id}`, { method: 'PUT', body: { always_ring: e.target.checked } }); toast(e.target.checked ? `${c.name} will always ring you` : `${c.name} can be answered by the assistant`); } catch (err) { toast(err.message, true); e.target.checked = !e.target.checked; } } }), h('i', {}))),
          h('button', { class: 'link danger', onclick: async () => { if (await ask(`Remove ${c.name}?`, { yes: 'Remove', danger: true })) { await A(`/contacts/${c.id}`, { method: 'DELETE' }); load(); } } }, 'Remove'))))
          : h('div', { class: 'empty' }, 'No contacts yet. Everyone is answered by the assistant when you miss a call.')));
  }
}
