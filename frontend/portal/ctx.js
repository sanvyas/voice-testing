// Which business the portal is working on. "All businesses" is the platform view (nothing selected).
import { h, mount } from '/lab/ui.js';
import { getBusiness, setBusiness } from '/lab/api.js';
import { A } from '/assistant/net.js';

export const selectedId = () => getBusiness();
export const businessList = async () => (await A('/admin/businesses')).items;

export function choose(id) {
  setBusiness(id || '');
  window.dispatchEvent(new Event('business-changed'));
}

/** For pages that only make sense inside one business: returns that business, or shows a picker and returns null. */
export async function needBusiness(page, title, sub) {
  const list = await businessList();
  const mine = list.find((b) => b.id === selectedId());
  if (mine) return mine;
  if (selectedId()) setBusiness('');
  mount(page, h('div', {}, h('h1', { class: 'title' }, title), h('div', { class: 'sub' }, sub)),
    list.length ? h('div', { class: 'card stack' }, h('h2', { class: 'sec' }, 'Choose a business'), h('div', { class: 'small muted' }, 'This page works on one business at a time. You can also switch from the list at the top left.'),
      ...list.map((b) => h('button', { class: 'plain', style: 'justify-content:space-between;text-align:left', onclick: () => choose(b.id) }, h('span', {}, h('b', {}, b.name), b.owner_name ? ` · ${b.owner_name}` : ''), h('span', { class: 'small muted' }, `${b.calls} calls · ${b.needs_action} need action`))))
      : h('div', { class: 'card empty' }, h('p', {}, 'There are no businesses yet.'), h('a', { class: 'btn', style: 'width:auto', href: '#/businesses' }, 'Add the first business')));
  return null;
}

export const fmtDate = (iso) => (iso ? new Date(iso).toLocaleDateString(undefined, { day: 'numeric', month: 'short' }) : '—');
