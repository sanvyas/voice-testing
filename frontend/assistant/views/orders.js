// Today's orders: a dedicated screen showing orders extracted from calls.
import { h, mount } from '/lab/ui.js';
import { A } from '../net.js';
import { t, getLang, clock } from '../i18n.js';
import { icon, toast, telLink } from '../kit.js';
import { go } from '../shell.js';

export async function render(root) {
  let calls = [];
  const body = h('div', { class: 'scroll' });

  async function fetchOrders() {
    try {
      const data = await A(`/calls?category=order&range=today&lang=${getLang()}`);
      calls = (data.calls || data.rows || []).filter((c) => c.category === 'order' || (c.order && c.order.items && c.order.items.length));
    } catch {
      try {
        const data = await A(`/people?tab=all&range=today&lang=${getLang()}`);
        calls = (data.rows || []).filter((r) => r.summary && /order|ऑर्डर|आटा|चीनी|चावल|kg|किलो|packet/i.test(r.summary));
      } catch (e) { toast(e.message, { bad: true }); }
    }
    draw();
  }

  function draw() {
    mount(body,
      h('div', { style: 'margin:8px 0 12px;font-size:14px;color:var(--muted)' },
        calls.length ? t([`${calls.length} ऑर्डर मिले`, `${calls.length} orders found`]) : ''),
      calls.length === 0
        ? h('div', { class: 'empty' },
            h('div', { class: 'ring' }, icon('check', 32)),
            h('b', {}, t(['कोई ऑर्डर नहीं', 'No orders today'])),
            h('p', {}, t(['जब कोई ऑर्डर की कॉल आएगी, यहाँ दिखेगा।', 'When someone calls to order, it will show here.'])))
        : h('div', { class: 'list' }, ...calls.map((r) => {
            const name = r.caller_name || r.name || r.caller_number || t(['अनजान', 'Unknown']);
            const phone = r.caller_number || (r.key && /^\d/.test(r.key) ? r.key : null);
            const key = r.key || phone || `call:${r.id}`;
            const items = r.order && r.order.items ? r.order.items.map((i) => [i.name, i.qty_n, i.unit].filter(Boolean).join(' ')).join(', ') : '';
            return h('button', { class: 'person', onclick: () => go(`#/thread/${encodeURIComponent(key)}`) },
              h('div', { class: 'av' }, (name || '?')[0]),
              h('div', { class: 'pmain' },
                h('div', { class: 'prow' },
                  h('div', { class: 'pname' }, name),
                  h('span', { class: 'ptime' }, clock(r.at || r.started_at))),
                h('div', { class: 'pask' }, items || r.summary)),
              phone ? h('a', { class: 'mini-call', href: telLink(phone), onclick: (e) => e.stopPropagation(), 'aria-label': t(['कॉल', 'Call']) }, icon('phone', 20)) : null);
          }))
    );
  }

  mount(root, h('div', { class: 'col' },
    h('div', { class: 'sub-top' },
      h('button', { class: 'btn-ic', 'aria-label': t(['वापस', 'Back']), onclick: () => go('#/calls') }, icon('back', 28)),
      h('h1', {}, t(['आज के ऑर्डर', "Today's orders"]))),
    body));
  await fetchOrders();
}
