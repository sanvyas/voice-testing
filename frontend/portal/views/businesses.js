import { h, mount, toast, ask, dialog, ago } from '/lab/ui.js';
import { A, rupees } from '/assistant/net.js';
import { choose, selectedId } from '../ctx.js';

const MODES = { reply: 'WhatsApp reply', message: 'Takes messages', board: 'Answers from board' };
const copy = (t) => navigator.clipboard?.writeText(t).then(() => toast('Copied')).catch(() => toast('Select and copy it manually', true));
const field = (label, control, hint) => h('label', { class: 'f' }, label, control, hint ? h('small', {}, hint) : null);
const text = (label, value = '', ph = '', type = 'text') => h('input', { type, autocomplete: 'off', value, placeholder: ph, 'aria-label': label });

function showLink(title, link) {
  const shareText = `Open this link on your phone to use Munshi for your business. Keep it private, it is your login: ${link}`;
  const close = dialog(title, h('div', { class: 'stack' },
    h('p', { class: 'muted', style: 'margin:0' }, 'This is the owner’s private link. Anyone who has it can see and change that business, so send it only to the owner. Making a new link stops the old one.'),
    h('div', { class: 'copyrow' }, h('code', { style: 'word-break:break-all' }, link), h('button', { class: 'plain', onclick: () => copy(link) }, 'Copy')),
    h('div', { class: 'row' }, h('a', { class: 'btn', style: 'width:auto', href: `https://wa.me/?text=${encodeURIComponent(shareText)}`, target: '_blank', rel: 'noopener' }, 'Send on WhatsApp'), h('button', { class: 'plain', onclick: () => close() }, 'Done'))));
}

export async function render(page) {
  const body = h('div', { class: 'card' });
  const search = h('input', { type: 'search', placeholder: 'Search by name, owner or number', 'aria-label': 'Search businesses', style: 'max-width:340px', oninput: () => draw() });
  mount(page, h('div', { class: 'pagehead' }, h('div', {}, h('h1', { class: 'title' }, 'Businesses'), h('div', { class: 'sub' }, 'Everyone on the platform. Each business has its own private data and its own app link.')), h('button', { class: 'btn', style: 'width:auto', onclick: addDialog }, 'Add a business')), search, body);
  let rows = [];
  await load();

  async function load() { rows = (await A('/admin/businesses')).items; draw(); window.dispatchEvent(new Event('munshi-changed')); }

  function draw() {
    const q = search.value.trim().toLowerCase();
    const shown = rows.filter((r) => !q || [r.name, r.owner_name, r.phone_number].some((v) => (v || '').toLowerCase().includes(q)));
    if (!rows.length) return mount(body, h('div', { class: 'empty' }, h('p', {}, 'No businesses yet.'), h('button', { class: 'btn', style: 'width:auto', onclick: addDialog }, 'Add the first one')));
    mount(body, h('div', { class: 'brow head' }, h('div', {}, 'Business'), h('div', {}, 'Phone number and mode'), h('div', {}, 'Calls'), h('div', {}, 'Need owner'), h('div', {}, 'Cost'), h('div', {})),
      ...shown.map((r) => h('div', { class: 'brow' },
        h('div', {}, h('div', { class: 'nm' }, r.name, r.active ? null : h('span', { class: 'badge', style: 'margin-left:8px' }, 'Paused'), r.id === selectedId() ? h('span', { class: 'badge ok', style: 'margin-left:8px' }, 'Selected') : null), h('div', { class: 'sm' }, [r.owner_name || 'No owner name yet', r.last_call_at ? `last call ${ago(r.last_call_at)}` : 'no calls yet'].join(' · '))),
        h('div', {}, h('div', {}, r.phone_number || h('span', { style: 'color:var(--warn);font-weight:600' }, 'No number')), h('div', { class: 'sm' }, r.assistant_on ? MODES[r.mode] : 'Assistant off')),
        h('div', {}, String(r.calls)), h('div', { style: r.needs_action ? 'color:var(--warn);font-weight:700' : '' }, String(r.needs_action)), h('div', {}, rupees(r.cost) || 'Rs 0'),
        h('div', { class: 'row', style: 'justify-content:flex-end;flex-wrap:nowrap' }, h('button', { class: 'plain', onclick: () => choose(r.id) }, 'Open'), h('button', { class: 'plain', onclick: () => manage(r) }, 'Manage')))));
  }

  function addDialog() {
    const name = text('Business name', '', 'e.g. Sharma Traders'); const owner = text('Owner name', '', 'e.g. Ramesh'); const mobile = text('Owner mobile', '', '98xxxxxxxx', 'tel'); const number = text('Munshi phone number', '', '+91 80 4711 2233', 'tel');
    const go = h('button', { class: 'btn' }, 'Add business');
    const close = dialog('Add a business', h('div', { class: 'stack' }, field('Business name', name), field('Owner name', owner), field('Owner’s mobile', mobile, 'Used for “Call back” and test messages.'), field('Munshi phone number', number, 'The Plivo number that forwards to this business. Leave empty and add it later.'), go));
    go.addEventListener('click', async () => {
      if (!name.value.trim()) return toast('Add the business name', true);
      go.disabled = true;
      try { const r = await A('/admin/businesses', { method: 'POST', body: { name: name.value, owner_name: owner.value, owner_phone: mobile.value, phone_number: number.value } }); close(); await load(); showLink(`Link for ${r.name}`, r.link); }
      catch (e) { toast(e.message, true); go.disabled = false; }
    });
  }

  function manage(r) {
    const name = text('Business name', r.name); const number = text('Munshi phone number', r.phone_number, '+91 80 4711 2233', 'tel');
    const save = h('button', { class: 'btn' }, 'Save');
    const paused = h('input', { type: 'checkbox', class: 'sw', role: 'switch', checked: !r.active, 'aria-label': 'Paused' });
    const close = dialog(r.name, h('div', { class: 'stack' },
      field('Business name', name), field('Munshi phone number', number, 'Calls forwarded to this number are answered for this business.'),
      h('label', { class: 'row between', style: 'font-weight:600;flex-wrap:nowrap' }, h('span', {}, 'Pause this business', h('div', { class: 'small muted', style: 'font-weight:400' }, 'The AI stops answering its calls. Its data is kept.')), paused),
      save,
      h('div', { class: 'card tight stack' }, h('div', { style: 'font-weight:700' }, 'Owner link'), h('div', { class: 'small muted' }, 'The private link the owner opens on their phone.'),
        h('div', { class: 'row' }, h('button', { class: 'plain', onclick: async () => { try { const d = await A(`/admin/businesses/${r.id}/link`); d.link ? showLink(`Link for ${r.name}`, d.link) : toast('No link yet or it cannot be shown. Make a new one.', true); } catch (e) { toast(e.message, true); } } }, 'Show link'),
          h('button', { class: 'plain', onclick: async () => { if (await ask('Make a new link? The old link stops working at once.', { yes: 'Make new link' })) { try { const d = await A(`/admin/businesses/${r.id}/link`, { method: 'POST' }); await load(); showLink(`New link for ${r.name}`, d.link); } catch (e) { toast(e.message, true); } } } }, 'New link'))),
      h('button', { class: 'link danger', style: 'align-self:flex-start', onclick: () => { close(); remove(r); } }, 'Delete this business')));
    save.addEventListener('click', async () => {
      save.disabled = true;
      try { await A(`/admin/businesses/${r.id}`, { method: 'PUT', body: { name: name.value, phone_number: number.value, active: !paused.checked } }); toast('Saved'); close(); load(); }
      catch (e) { toast(e.message, true); save.disabled = false; }
    });
  }

  function remove(r) {
    const confirm = text('Type the business name to confirm', '', r.name);
    const go = h('button', { class: 'btn danger' }, 'Delete for good');
    const close = dialog(`Delete ${r.name}?`, h('div', { class: 'stack' }, h('p', { style: 'margin:0' }, 'This deletes the business and all its calls, contacts, board and settings. It cannot be undone.'), field('Type the business name to confirm', confirm), go));
    go.addEventListener('click', async () => {
      go.disabled = true;
      try { await A(`/admin/businesses/${r.id}/delete`, { method: 'POST', body: { confirm_name: confirm.value } }); toast('Deleted'); close(); if (selectedId() === r.id) choose(''); load(); }
      catch (e) { toast(e.message, true); go.disabled = false; }
    });
  }
}
