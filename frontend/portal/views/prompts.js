import { h, mount, toast, ask, ago } from '/lab/ui.js';
import { A } from '/assistant/net.js';

const words = (t) => (t.trim() ? t.trim().split(/\s+/).length : 0);

export async function render(page) {
  const body = h('div', { class: 'stack', style: 'gap:18px' });
  mount(page, h('div', { class: 'pagehead' }, h('div', {}, h('h1', { class: 'title' }, 'Prompts'), h('div', { class: 'sub' }, 'Shape how the assistant greets, what extra it should do, and how call notes are written. Saved changes apply to the very next call.')),
    h('a', { class: 'btn', style: 'width:auto', href: '/assistant/#/try', target: '_blank', rel: 'noopener' }, 'Try it with a practice call')), body);
  await load();

  async function load() {
    const d = await A('/prompts');
    const greeting = h('input', { type: 'text', value: d.greeting, maxlength: 300, placeholder: d.defaults.greeting, 'aria-label': 'Greeting' });
    const extra = h('textarea', { rows: 6, maxlength: 1500, placeholder: 'e.g. Always ask which shop the caller owns. Offer to send the price list on WhatsApp.', 'aria-label': 'Extra instructions' }, d.extra);
    const rules = h('textarea', { rows: 4, maxlength: 800, placeholder: 'e.g. Write quantities as numbers. Put the caller’s shop name first.', 'aria-label': 'Call note rules' }, d.summary_rules);
    const save = h('button', { class: 'btn', style: 'width:auto' }, 'Save changes');
    save.addEventListener('click', async () => { save.disabled = true; try { await A('/prompts', { method: 'PUT', body: { greeting: greeting.value, extra: extra.value, summary_rules: rules.value } }); toast('Saved. The next call uses it.'); load(); } catch (e) { toast(e.message, true); save.disabled = false; } });
    mount(body,
      h('div', { class: 'grid2' },
        h('div', { class: 'card stack' }, h('div', { class: 'row between' }, h('h2', { class: 'sec' }, 'Your changes'), h('span', { class: 'badge ' + (d.version ? 'ok' : '') }, d.version ? `Live: version ${d.version}` : 'Built-in text')),
          h('label', { class: 'f' }, 'Greeting', greeting, h('small', {}, `Leave empty to use the built-in greeting. Use {business} and {owner} for the names. ${d.defaults.greeting_hint}`)),
          h('label', { class: 'f' }, 'Extra instructions for the phone assistant', extra, h('small', {}, `${words(d.extra)} words. These are added after the built-in rules and can never override the hard rules (no promises, no guessing prices, no card numbers).`)),
          h('label', { class: 'f' }, 'Rules for the call notes', rules, h('small', {}, 'Added to how summaries and to-dos are written. The notes stay short.')),
          h('div', { class: 'row' }, save, h('button', { class: 'plain', onclick: async () => { if (await ask('Go back to the built-in prompts? Your current text is kept in the history.', { yes: 'Reset' })) { await A('/prompts/reset', { method: 'POST' }); toast('Back to the built-in text'); load(); } } }, 'Reset to built-in'))),
        h('div', { class: 'card stack' }, h('h2', { class: 'sec' }, 'History'), d.history.length ? h('div', {}, ...d.history.map((v) => h('div', { class: 'hist' }, h('div', {}, h('b', {}, `Version ${v.version}`), h('div', { class: 'small muted' }, `${ago(v.at)} · ${[v.greeting && 'greeting', v.extra && 'extra instructions', v.summary_rules && 'note rules'].filter(Boolean).join(', ') || 'built-in text'}`)),
          h('button', { class: 'plain', onclick: async () => { await A('/prompts/restore', { method: 'POST', body: { version: v.version } }); toast(`Restored version ${v.version}`); load(); } }, 'Restore')))) : h('div', { class: 'muted' }, 'No earlier versions yet. Each save keeps the one before it, up to 20.'))),
      h('details', { class: 'card stack' }, h('summary', { style: 'cursor:pointer;font-weight:700;font-size:17px' }, `What the phone assistant is told, right now (${words(d.preview.assistant)} words)`), h('div', { class: 'small muted', style: 'margin:8px 0' }, 'This is exactly what the model reads on every call, including the business details and today’s board. Read-only.'), h('pre', { class: 'prompt' }, d.preview.assistant)),
      h('details', { class: 'card stack' }, h('summary', { style: 'cursor:pointer;font-weight:700;font-size:17px' }, `How call notes are written (${words(d.preview.summary)} words)`), h('pre', { class: 'prompt', style: 'margin-top:10px' }, d.preview.summary)));
  }
}
