import { h, mount, toast, ago } from '/lab/ui.js';
import { A, lab, ic, ICONS } from '/assistant/net.js';

const copy = (t) => navigator.clipboard?.writeText(t).then(() => toast('Copied')).catch(() => toast('Select and copy it manually', true));
const copyRow = (text) => h('div', { class: 'copyrow' }, h('code', {}, text), h('button', { class: 'plain', onclick: () => copy(text) }, 'Copy'));
const field = (label, control, hint) => h('label', { class: 'f' }, label, control, hint ? h('small', {}, hint) : null);
const pw = (label, ph) => h('input', { type: 'password', autocomplete: 'off', placeholder: ph, 'aria-label': label });
const txt = (label, value = '', ph = '') => h('input', { type: 'text', autocomplete: 'off', value, placeholder: ph, 'aria-label': label });
const changed = () => window.dispatchEvent(new Event('munshi-changed'));

export async function render(page) {
  const body = h('div', { class: 'stack', style: 'gap:14px' });
  mount(page, h('div', {}, h('h1', { class: 'title' }, 'Integrations'), h('div', { class: 'sub' }, 'Everything the assistant is connected to. Test any of them with one click. Keys are stored encrypted and never shown again.')), body);
  const open = new Set();
  await load();

  async function load() {
    const [list, status, vision, tts, providers] = await Promise.all([A('/integrations'), A('/status'), A('/vision'), lab('/settings/tts'), lab('/settings/providers')]);
    const custom = providers.find((p) => p.id === 'custom') || {};
    const forms = {
      ai: () => aiForm(providers.find((p) => p.id === 'groq') || {}),
      vision: () => visionForm(vision, custom),
      voice_google: () => voiceForm('google', 'google_key', tts),
      voice_chatterbox: () => voiceForm('chatterbox', 'deepinfra_key', tts),
      whatsapp: () => whatsappForm(status),
      phone: () => phoneForm(status),
    };
    mount(body, ...list.map((it) => card(it, forms[it.id])));
  }

  function card(it, form) {
    const msg = h('div', { class: 'small', role: 'status' });
    const last = it.last_check;
    if (last) { msg.textContent = `${last.ok ? 'Passed' : 'Failed'} ${ago(last.at)}: ${last.message}`; msg.style.color = last.ok ? 'var(--primary)' : 'var(--danger)'; }
    const test = h('button', { class: 'plain', disabled: !it.can_test }, 'Test');
    test.addEventListener('click', async () => {
      test.disabled = true; msg.style.color = ''; msg.textContent = 'Testing…';
      try { const r = await A(`/integrations/${it.id}/test`, { method: 'POST' }); msg.textContent = `${r.ok ? 'Passed' : 'Failed'}: ${r.message}`; msg.style.color = r.ok ? 'var(--primary)' : 'var(--danger)'; }
      catch (e) { msg.textContent = e.message; msg.style.color = 'var(--danger)'; }
      test.disabled = false;
    });
    const el = form ? h('details', { class: 'card stack', open: open.has(it.id) }) : h('div', { class: 'card stack' });
    const head = h('div', { class: 'row between', style: 'flex-wrap:nowrap;gap:12px' },
      h('div', { class: 'row', style: 'flex-wrap:nowrap;gap:12px' }, h('span', { class: 'ico' + (it.connected ? '' : ' warn') }, ic(it.connected ? ICONS.check : ICONS.sliders)),
        h('div', {}, h('div', { style: 'font-weight:700' }, it.name), h('div', { class: 'small muted' }, it.what), h('div', { class: 'small', style: it.connected ? '' : 'color:var(--warn);font-weight:600' }, it.detail))),
      h('div', { class: 'row', style: 'flex-wrap:nowrap' }, it.can_test ? test : null, form ? h('span', { class: 'small', style: 'color:var(--primary);font-weight:600' }, it.connected ? 'Change' : 'Set up') : null));
    if (form) {
      const summary = h('summary', { style: 'cursor:pointer;list-style:none' }, head);
      el.addEventListener('toggle', () => { el.open ? open.add(it.id) : open.delete(it.id); });
      test.addEventListener('click', (e) => e.stopPropagation());
      el.append(summary, h('div', { class: 'stack', style: 'margin-top:12px;border-top:1px solid var(--line);padding-top:12px' }, ...form()), msg);
    } else el.append(head, msg);
    return el;
  }

  function save(fn, ok) { return async (e) => { const b = e.currentTarget; b.disabled = true; try { await fn(); toast(ok); changed(); await load(); } catch (err) { toast(err.message, true); b.disabled = false; } }; }

  function aiForm(groq) {
    const key = pw('Groq API key', groq.configured ? 'Paste a new key to replace it' : 'gsk_…');
    const model = txt('Model', groq.model || '', 'openai/gpt-oss-20b');
    return [h('div', { class: 'small muted' }, 'Get a free key at console.groq.com/keys. The same key is used for speech and for thinking.'), field('Groq API key', key), field('Model', model, 'Leave as it is unless you know you need another.'),
      h('button', { class: 'btn', style: 'width:auto;align-self:flex-start', onclick: save(async () => { if (!key.value.trim() && model.value === groq.model) throw new Error('Nothing to save'); await lab('/settings/providers/groq', { method: 'PUT', body: { ...(key.value.trim() ? { api_key: key.value } : {}), model: model.value } }); }, 'Saved') }, 'Save')];
  }

  function visionForm(v, custom) {
    const provider = h('select', { 'aria-label': 'Photo reader service' }, ...v.provider_options.map(([id, l]) => h('option', { value: id, selected: id === v.provider }, l)));
    const model = txt('Photo reader model', v.model, 'e.g. meta-llama/llama-4-scout-17b-16e-instruct');
    const base = txt('Service address', custom.base_url || '', 'https://openrouter.ai/api/v1');
    const key = pw('Service API key', custom.configured ? 'Saved. Paste a new key to replace it' : 'sk-or-…');
    const extra = h('div', { class: 'stack' }, h('div', { class: 'small muted' }, 'Any OpenAI-compatible service works, such as OpenRouter. This key is also used by nothing else.'), field('Service address', base), field('API key', key));
    const sync = () => { extra.hidden = provider.value !== 'custom'; }; provider.addEventListener('change', sync); sync();
    return [h('div', { class: 'small muted' }, 'The photo reader needs a model that can look at pictures. If a test says the model cannot read images, pick a vision model here.'), field('Service', provider), field('Model', model), extra,
      h('button', { class: 'btn', style: 'width:auto;align-self:flex-start', onclick: save(async () => {
        if (provider.value === 'custom' && (key.value.trim() || base.value.trim())) await lab('/settings/providers/custom', { method: 'PUT', body: { ...(key.value.trim() ? { api_key: key.value } : {}), ...(base.value.trim() ? { base_url: base.value } : {}), model: model.value } });
        await A('/vision', { method: 'PUT', body: { provider: provider.value, model: model.value } });
      }, 'Photo reader saved') }, 'Save')];
  }

  function voiceForm(id, field_, tts) {
    const e = (tts.engines || []).find((x) => x.id === id) || {};
    const key = pw('API key', e.configured ? 'Saved. Paste a new key to replace it' : 'Paste API key');
    return [h('div', { class: 'small muted' }, id === 'google' ? 'Google Cloud Text-to-Speech key. All major Indian languages.' : 'DeepInfra key for Chatterbox. Cheaper, Hindi and English only.'), field('API key', key),
      h('div', { class: 'row' }, h('button', { class: 'btn', style: 'width:auto', onclick: save(async () => { if (!key.value.trim()) throw new Error('Paste the key first'); await lab('/settings/tts', { method: 'PUT', body: { [field_]: key.value } }); }, 'Saved') }, 'Save key'),
        tts.active !== id && e.configured ? h('button', { class: 'plain', onclick: save(() => lab('/settings/tts', { method: 'PUT', body: { active: id } }), 'Now speaking with this voice') }, 'Use this voice') : null,
        tts.active === id ? h('span', { class: 'badge ok' }, 'In use') : null)];
  }

  function whatsappForm(s) {
    const w = s.whatsapp;
    const pid = txt('Phone number ID', w.phone_number_id, 'Phone number ID from Meta'); const tok = pw('Access token', w.token_saved ? 'Saved. Paste a new token to replace it' : 'Access token'); const tpl = txt('Template name', w.template);
    return [h('div', { class: 'small muted' }, `In Meta Business Manager, create a Utility template named ${w.template}, language English, with this text. Meta must approve it first. Not yet tested with a live Meta account.`), copyRow(w.template_body),
      field('Phone number ID', pid), field('Access token', tok), field('Template name', tpl),
      h('div', { class: 'row' }, h('button', { class: 'btn', style: 'width:auto', onclick: save(() => A('/whatsapp', { method: 'PUT', body: { phone_number_id: pid.value, access_token: tok.value, template: tpl.value, language: w.language } }), 'WhatsApp saved') }, 'Save'),
        w.connected ? h('button', { class: 'plain', onclick: async (ev) => { ev.currentTarget.disabled = true; try { const r = await A('/whatsapp/test', { method: 'POST' }); toast(`Sent to ${r.to}`); } catch (err) { toast(err.message, true); } ev.currentTarget.disabled = false; } }, 'Send a test to my number') : null,
        w.connected ? h('button', { class: 'link danger', onclick: save(() => A('/whatsapp', { method: 'DELETE' }), 'Disconnected') }, 'Disconnect') : null)];
  }

  function phoneForm(s) {
    const p = s.phone;
    const id = txt('Plivo Auth ID', p.auth_id, 'Plivo Auth ID'); const tok = pw('Plivo Auth Token', p.token_saved ? 'Saved. Paste a new token to replace it' : 'Plivo Auth Token'); const num = txt('Plivo number', p.number, '+91 80 4711 2233');
    return [h('div', { class: 'small', style: 'font-weight:700' }, 'In Plivo (India), make an Application with these, method POST'), h('div', { class: 'small muted' }, 'Answer URL'), copyRow(s.webhooks.answer), h('div', { class: 'small muted' }, 'Hangup URL'), copyRow(s.webhooks.hangup),
      s.webhooks.https ? null : h('div', { class: 'notice' }, 'This page is not on https, so Plivo may not reach it.'),
      field('Auth ID', id), field('Auth Token', tok), field('Your Plivo number', num),
      h('div', { class: 'row' }, h('button', { class: 'btn', style: 'width:auto', onclick: save(() => A('/phone', { method: 'PUT', body: { auth_id: id.value, auth_token: tok.value, number: num.value } }), 'Phone line saved') }, 'Save'),
        p.connected ? h('button', { class: 'link danger', onclick: save(() => A('/phone', { method: 'DELETE' }), 'Disconnected') }, 'Disconnect') : null),
      h('div', { class: 'small', style: 'font-weight:700' }, 'Then forward missed calls (dial on your phone, once)'), ...s.forwarding.map((c) => h('div', { class: 'stack', style: 'gap:4px' }, h('div', { class: 'small muted' }, c.when), copyRow(c.dial)))];
  }
}
