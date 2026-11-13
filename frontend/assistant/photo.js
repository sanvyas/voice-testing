// Photos: shrink on the phone first (a 12 MP photo is slow to upload and costs more to read), then ask the server to read it.
import { h, mount, toast, dialog } from '/lab/ui.js';
import { A, apiForm } from './net.js';

export async function shrink(file, max = 1400, quality = 0.82) {
  let bitmap;
  try { bitmap = await createImageBitmap(file, { imageOrientation: 'from-image' }); }
  catch { bitmap = await new Promise((resolve, reject) => { const img = new Image(); img.onload = () => resolve(img); img.onerror = () => reject(new Error('That file is not a photo this browser can open.')); img.src = URL.createObjectURL(file); }); }
  const scale = Math.min(1, max / Math.max(bitmap.width, bitmap.height));
  const canvas = document.createElement('canvas'); canvas.width = Math.round(bitmap.width * scale); canvas.height = Math.round(bitmap.height * scale);
  canvas.getContext('2d').drawImage(bitmap, 0, 0, canvas.width, canvas.height);
  const blob = await new Promise((resolve) => canvas.toBlob(resolve, 'image/jpeg', quality));
  if (!blob) throw new Error('Could not prepare the photo.');
  return blob;
}

/** Pick or take a photo, let the server read it, show what it found, and apply only what the owner ticks. */
export async function updateFromPhoto(file, onDone) {
  const note = h('div', { class: 'small muted' }, 'Reading your photo…');
  const wait = dialog('Reading your photo', h('div', { class: 'stack' }, note, h('div', { class: 'progress', style: 'background:var(--line)' }, h('i', { style: 'width:60%;background:var(--primary);animation:breathe 1.4s ease-in-out infinite' }))), { locked: true });
  let found;
  try {
    const blob = await shrink(file);
    const form = new FormData(); form.append('file', blob, 'photo.jpg');
    found = await apiForm('/api/assistant/board/photo', form);
  } catch (e) { wait(); toast(e.message, true); return; }
  wait();
  review(found.items, found.model, onDone);
}

function review(items, model, onDone) {
  const rows = items.map((it) => ({ ...it, on: !it.same }));
  const list = h('div', {});
  const apply = h('button', { class: 'btn' }, '');
  const draw = () => {
    mount(list, ...rows.map((r) => h('div', { class: 'item' },
      h('label', { class: 'row', style: 'gap:10px;flex-wrap:nowrap' }, h('input', { type: 'checkbox', class: 'ck', checked: r.on, 'aria-label': `Use ${r.name}`, onchange: (e) => { r.on = e.target.checked; draw(); } }),
        h('div', { class: 'grow' }, h('input', { type: 'text', value: r.name, 'aria-label': 'Item name', oninput: (e) => { r.name = e.target.value; }, style: 'min-height:40px' })),
        h('input', { type: 'text', value: r.price.replace(/^Rs /, ''), 'aria-label': `Price of ${r.name}`, inputmode: 'decimal', placeholder: 'price', style: 'width:92px;min-height:40px', oninput: (e) => { r.price = e.target.value; } })),
      h('div', { class: 'row', style: 'gap:6px;padding-left:34px' }, h('span', { class: 'badge ' + (r.action === 'new' ? 'ok' : r.same ? '' : 'act') }, r.same ? 'No change' : r.action === 'new' ? 'New' : `Update${r.old_price && r.old_price !== r.price ? `: ${r.old_price} → ${r.price}` : ''}`),
        r.status === 'sold_out' ? h('span', { class: 'badge act' }, 'Sold out') : null))));
    const n = rows.filter((r) => r.on).length;
    apply.textContent = n ? `Apply ${n} change${n > 1 ? 's' : ''}` : 'Nothing selected'; apply.disabled = !n;
  };
  draw();
  const close = dialog('Is this right?', h('div', { class: 'stack' }, h('div', { class: 'small muted' }, `Read from your photo by ${model}. Check the names and prices, untick anything wrong. Nothing changes until you apply.`), h('div', { style: 'max-height:48vh;overflow:auto' }, list), apply,
    h('button', { class: 'link', onclick: () => close() }, 'Cancel')));
  apply.addEventListener('click', async () => {
    apply.disabled = true;
    try { const r = await A('/board/apply', { method: 'POST', body: { items: rows.filter((x) => x.on).map(({ name, price, status }) => ({ name, price, status })) } }); close(); toast(`${r.added} added, ${r.updated} updated`); window.dispatchEvent(new Event('munshi-changed')); onDone?.(r.board); }
    catch (e) { toast(e.message, true); apply.disabled = false; }
  });
}
