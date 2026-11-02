import { h, mount, toast, ask, field, ago } from '../ui.js';
import { api, getConfig, setToken, hasToken } from '../api.js';
import { styleControls } from '../style.js';

const RULES = {  // plain-language switches that map onto the engine's exact checks
  spoken_length: ['Short replies (5 sentences max)', { rule: 'max_sentences_per_reply', max: 5, allow_violations: 1 }],
  one_question: ['One question at a time', { rule: 'max_questions_per_reply', max: 1, allow_violations: 1 }],
  no_markup: ['No lists or markdown (they sound wrong aloud)', { rule: 'no_formatting' }],
  latency: ['Replies arrive within 6 seconds', { rule: 'max_latency_ms', max_ms: 6000, stat: 'p95' }],
  asks_followup: ['Keeps the conversation going', { rule: 'min_question_ratio', min_ratio: 0.5 }],
};

export async function render(root) {
  const box = h('div', { class: 'stack', style: 'gap:18px' });
  mount(root, h('h1', {}, 'Settings'), box);
  await load();

  async function load() {
    const [cfg, providers, evalsets, active, keys, app, probe] = await Promise.all([getConfig(true), api('/settings/providers'), api('/eval-sets'), api('/deployments/active'), api('/api-keys'), api('/settings/app'),
      api('/settings/providers/groq/test', { method: 'POST' }).catch((e) => ({ ok: false, message: e.message, models: {} }))]);
    const groq = providers.find((p) => p.id === 'groq');
    const style = await styleControls();
    mount(box, statusCard(cfg, groq, probe, active), groqCard(groq, probe), h('div', { class: 'card stack' }, h('h2', { style: 'margin:0' }, 'How it talks'), h('div', { class: 'small muted' }, 'Saved as you change it. Applies to every new test and talk, and to what you publish next. Already-published prompts keep their saved values until you publish again.'), style), checksCard(evalsets[0]), appCard(cfg, active, keys, app, evalsets[0]), cfg.auth_required ? signOut() : null);
    window.dispatchEvent(new Event('lab-config'));
  }

  function statusCard(cfg, groq, probe, active) {
    const row = (state, title, detail) => h('div', { class: 'statusrow' }, h('span', { class: 'dot ' + state }, state === 'pass' ? '✓' : state === 'fail' ? '✕' : '!'), h('div', { class: 'grow' }, h('div', { class: 't' }, title), h('div', { class: 'd' }, detail)));
    const live = active.production;
    return h('div', { class: 'card' }, h('h2', {}, 'Status'),
      row(probe.ok ? 'pass' : 'fail', 'AI model (Groq)', probe.ok ? `${probe.message}${groq.source === 'env' ? ' Key is set on the server.' : ''}` : (groq.configured ? `Could not reach Groq: ${probe.message}` : 'Not connected. Add your key below.')),
      row(cfg.stt_ready ? 'pass' : 'fail', 'Voice (speech to text)', cfg.stt_ready ? 'Ready. Whisper on Groq understands what people say, on any phone.' : 'Needs Groq connected.'),
      row(cfg.storage === 'temporary' ? 'warn' : 'pass', 'Database', cfg.storage === 'temporary' ? 'Temporary: everything is lost when the server restarts. Set DATABASE_URL.' : cfg.database === 'postgres' ? 'Postgres. Everything you save is kept.' : 'Local database file.'),
      row(live ? 'pass' : 'warn', 'Your app', live ? `Live prompt: ${live.prompt_label}` : 'Nothing published yet. Run a test, then press Publish.'));
  }

  function groqCard(p, probe) {
    const key = h('input', { type: 'password', autocomplete: 'off', placeholder: p.has_stored_key ? `Saved ${p.key_hint}. Paste a new key to replace it` : 'gsk_…', id: 'groq-key' });
    const model = h('select', { id: 'groq-model', 'aria-label': 'Model' }, h('option', { value: p.model }, p.model));
    const msg = h('div', { class: 'small', role: 'status' });
    const fill = (models) => { if (models?.chat?.length) mount(model, ...models.chat.map((m) => h('option', { value: m, selected: m === p.model }, m))); };
    fill(probe.models);
    const btn = h('button', { class: 'go' }, p.configured ? 'Save' : 'Connect');
    btn.addEventListener('click', async () => {
      btn.disabled = true; msg.textContent = 'Connecting…'; msg.style.color = '';
      try {
        const body = {}; if (key.value.trim()) body.api_key = key.value; if (model.value !== p.model) body.model = model.value;
        if (Object.keys(body).length) { const r = await api('/settings/providers/groq', { method: 'PUT', body }); if (r.warning) toast(r.warning); }
        const t = await api('/settings/providers/groq/test', { method: 'POST' }); fill(t.models); msg.textContent = t.message; msg.style.color = t.ok ? 'var(--pass)' : 'var(--fail)';
        if (t.ok) { toast('Groq connected'); setTimeout(load, 700); }
      } catch (e) { msg.textContent = e.message; msg.style.color = 'var(--fail)'; }
      btn.disabled = false;
    });
    const form = h('div', { class: 'stack' },
      p.configured ? null : h('div', { class: 'small muted' }, 'Get a key at console.groq.com/keys and paste it here. It is stored encrypted.'),
      !p.can_store && !p.configured ? h('div', { class: 'notice' }, 'This server needs LAB_SECRET_KEY set before it can store keys.') : null,
      p.stored_key_unreadable ? h('div', { class: 'notice' }, 'The saved key can no longer be read. Paste it again.') : null,
      field('API key', key), p.configured ? field('Model', model, 'The model that talks to your callers and scores the conversations.') : null, btn, msg);
    return h('div', { class: 'card stack' }, h('h2', { style: 'margin:0' }, p.configured ? 'Groq key and model' : 'Connect Groq'),
      p.configured ? h('details', { class: 'more' }, h('summary', {}, 'Change key or model'), h('div', { style: 'margin-top:12px' }, form)) : form);
  }

  function checksCard(set) {
    const params = set.params.map((x) => ({ ...x }));
    const ai = params.filter((x) => x.kind === 'llm_judge').map((x) => ({ ...x, _k: true }));  // keep keys of existing checks stable
    const others = params.filter((x) => x.kind === 'rule' && !(x.key in RULES));
    const on = Object.fromEntries(Object.keys(RULES).map((k) => [k, params.some((x) => x.key === k)]));
    const pass = h('input', { type: 'range', min: 50, max: 100, step: 5, value: set.pass_threshold, 'aria-label': 'Pass mark' });
    const passOut = h('b', {}, `${set.pass_threshold}%`); pass.addEventListener('input', () => { passOut.textContent = `${pass.value}%`; });
    const aiBox = h('div', { class: 'stack', style: 'gap:10px' });
    const drawAi = () => mount(aiBox, ...ai.map((x, i) => h('div', { class: 'stack', style: 'gap:6px;padding-top:10px;border-top:1px solid var(--line)' },
      h('div', { class: 'row' }, h('input', { value: x.name, 'aria-label': 'Check name', placeholder: 'Name', oninput: (e) => { x.name = e.target.value; if (!x._k) x.key = e.target.value.toLowerCase().replace(/[^a-z0-9]+/g, '_').replace(/^_|_$/g, '').slice(0, 50); }, style: 'flex:1' }),
        h('button', { class: 'link danger', onclick: () => { ai.splice(i, 1); drawAi(); } }, 'Remove')),
      h('textarea', { rows: 2, style: 'min-height:60px', 'aria-label': 'What the AI should look for', placeholder: 'What should it look for? e.g. The reply acknowledges the caller’s feeling before offering anything.', oninput: (e) => { x.config.criteria = e.target.value; } }, x.config.criteria),
      h('div', { class: 'row between' }, h('label', { class: 'row', style: 'gap:8px' }, h('input', { type: 'checkbox', checked: x.required, onchange: (e) => { x.required = e.target.checked; } }), h('span', { class: 'small' }, 'Must pass, whatever the score')),
        x.applies_to_moods?.length ? h('span', { class: 'small muted' }, `only for: ${x.applies_to_moods.join(', ')}`) : null))));
    drawAi();
    const save = h('button', { class: 'go' }, 'Save checks');
    save.addEventListener('click', async () => {
      save.disabled = true;
      try {
        const out = [...ai.map((x) => ({ key: x.key || `check_${Math.random().toString(36).slice(2, 7)}`, name: x.name, description: '', kind: 'llm_judge', config: { criteria: x.config.criteria, scale_max: 5, min_score: x.config.min_score ?? 4, guidance: x.config.guidance || '' }, weight: x.weight ?? 1, required: !!x.required, applies_to_moods: x.applies_to_moods || [] })),
          ...Object.entries(RULES).filter(([k]) => on[k]).map(([k, [name, config]]) => { const old = params.find((x) => x.key === k); return { key: k, name, description: '', kind: 'rule', config: old?.config || config, weight: old?.weight ?? 1, required: false, applies_to_moods: [] }; }),
          ...others.map((x) => ({ key: x.key, name: x.name, description: x.description || '', kind: 'rule', config: x.config, weight: x.weight, required: x.required, applies_to_moods: x.applies_to_moods }))];
        await api(`/eval-sets/${set.id}`, { method: 'PUT', body: { name: set.name, description: set.description || '', pass_threshold: +pass.value, params: out } });
        toast('Checks saved'); load();
      } catch (e) { toast(e.message, true); save.disabled = false; }
    });
    return h('div', { class: 'card stack' }, h('h2', { style: 'margin:0' }, 'What counts as a pass'),
      h('div', { class: 'stack', style: 'gap:8px' }, h('div', { class: 'small muted' }, 'Rules'), ...Object.entries(RULES).map(([k, [name]]) => h('label', { class: 'row', style: 'gap:10px;font-weight:500' }, h('input', { type: 'checkbox', checked: on[k], onchange: (e) => { on[k] = e.target.checked; } }), name))),
      h('div', { class: 'stack', style: 'gap:2px' }, h('div', { class: 'small muted' }, 'AI checks (scored 1 to 5, a pass needs 4)'), aiBox,
        h('div', {}, h('button', { class: 'link', onclick: () => { ai.push({ key: '', name: '', kind: 'llm_judge', config: { criteria: '', scale_max: 5, min_score: 4 }, weight: 1, required: false, applies_to_moods: [] }); drawAi(); } }, '+ Add an AI check'))),
      h('div', { class: 'stack', style: 'gap:4px' }, h('div', { class: 'row between' }, h('span', { class: 'small muted' }, 'Pass mark'), passOut), pass), save);
  }

  function appCard(cfg, active, keys, app, set) {
    const live = active.production, test = active.staging;
    const name = h('input', { placeholder: 'App name, e.g. iPhone app', id: 'key-name' });
    const env = h('select', { id: 'key-env', 'aria-label': 'Key for' }, h('option', { value: 'production' }, 'Live app'), h('option', { value: 'staging' }, 'Test app'));
    const shown = h('div', {});
    const url = `${location.origin}/api/v1`;
    const copy = (t) => navigator.clipboard?.writeText(t).then(() => toast('Copied')).catch(() => toast('Select and copy it manually', true));
    const line = (label, d) => h('div', { class: 'row between' }, h('span', { class: 'muted' }, label), d ? h('span', {}, h('strong', {}, d.prompt_label), h('span', { class: 'small muted' }, `  ${d.evidence?.tested ? Math.round(d.evidence.latest_pass_rate) + '% tested' : 'untested'} · ${ago(d.created_at)}`)) : h('span', { class: 'small muted' }, 'nothing published yet'));
    return h('div', { class: 'card stack' }, h('h2', { style: 'margin:0' }, 'Your app'),
      h('div', { class: 'stack', style: 'gap:6px' }, line('Live', live), line('Test', test), h('div', { class: 'small muted' }, 'Publish from the Test tab once a prompt passes. Every app follows what is published.')),
      h('div', { class: 'row' }, h('span', { class: 'small muted' }, 'API address'), h('code', { class: 'grow', style: 'word-break:break-all' }, url), h('button', { class: 'link', onclick: () => copy(url) }, 'Copy')),
      h('div', { class: 'row', style: 'flex-wrap:nowrap' }, h('div', { class: 'grow' }, name), env, h('button', { onclick: async () => {
        try { const k = await api('/api-keys', { method: 'POST', body: { name: name.value.trim() || 'My app', environment: env.value } });
          mount(shown, h('div', { class: 'notice ok stack' }, h('strong', {}, 'Copy this key now. It will not be shown again.'), h('code', { style: 'word-break:break-all;user-select:all' }, k.key), h('button', { onclick: () => copy(k.key) }, 'Copy key')));
          name.value = ''; } catch (e) { toast(e.message, true); } } }, 'Create key')), shown,
      ...keys.filter((k) => !k.revoked).map((k) => h('div', { class: 'row between' }, h('span', {}, k.name, h('span', { class: 'small muted' }, `  ${k.environment === 'production' ? 'live' : 'test'} · ${k.prefix}… · ${k.last_used_at ? 'used ' + ago(k.last_used_at) : 'never used'}`)),
        h('button', { class: 'link danger', onclick: async () => { if (await ask(`Revoke “${k.name}”? Apps using it stop working.`, { yes: 'Revoke', danger: true })) { await api(`/api-keys/${k.id}`, { method: 'DELETE' }); load(); } } }, 'Revoke'))),
      h('label', { class: 'row', style: 'gap:10px;font-weight:500' }, h('input', { type: 'checkbox', checked: !!app.eval_set_id, onchange: async (e) => { try { await api('/settings/app', { method: 'PUT', body: { eval_set_id: e.target.checked ? set.id : null } }); toast(e.target.checked ? 'Real conversations will be scored' : 'Scoring off'); } catch (err) { toast(err.message, true); } } }), 'Score real conversations from my app automatically'),
      h('div', { class: 'small muted' }, 'Developer guide: docs/MOBILE_API.md'));
  }

  function signOut() { return h('div', { style: 'text-align:center' }, h('button', { class: 'link', onclick: () => { setToken(''); toast('Signed out'); location.reload(); } }, hasToken() ? 'Sign out' : 'Sign in')); }
}
