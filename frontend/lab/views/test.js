import { h, mount, toast, ask, dialog, field, detectVariables, pct, slug, moodColor, gauge, confetti } from '../ui.js';
import { api, getConfig } from '../api.js';
import { conversationRow, isPending } from '../components.js';
import { saved, remember } from '../workspace.js';
import { styleControls } from '../style.js';

export async function render(root, { params }) {
  const [cfg, prompts, scenarios, evalsets, active] = await Promise.all([getConfig(), api('/prompts'), api('/scenarios'), api('/eval-sets'), api('/deployments/active')]);
  const ws = saved();
  const styleBox = await styleControls();
  let timer = null; let gone = false;
  const st = { prompt: null, version: null, values: {}, selected: new Set(ws.moods || scenarios.map((s) => s.id)), evalId: evalsets[0]?.id };
  if (!prompts.length) { root.append(h('div', { class: 'card empty' }, h('p', {}, 'Create your first prompt to start.'), h('button', { class: 'go', style: 'width:auto', onclick: () => newPrompt() }, 'New prompt'))); return; }

  const sel = h('select', { 'aria-label': 'Prompt', style: 'flex:1' }, ...prompts.map((p) => h('option', { value: p.id }, p.name)));
  const verSel = h('select', { 'aria-label': 'Version' });
  const stateChip = h('span', { class: 'state' });
  const saveBtn = h('button', {}, 'Save prompt');
  const text = h('textarea', { class: 'code', spellcheck: false, 'aria-label': 'Prompt text', style: 'min-height:220px' });
  const varsBox = h('div', { class: 'stack' });
  const moodsBox = h('div', { class: 'chips' });
  const runBtn = h('button', { class: 'go' }, 'Run test');
  const out = h('div', { class: 'stack' });
  const hint = h('div', { class: 'small muted' });

  const varsOf = () => Object.fromEntries(detectVariables(text.value).map((n) => [n, String(st.values[n] ?? '')]));
  const dirty = () => text.value !== st.version.content || JSON.stringify(varsOf()) !== JSON.stringify(Object.fromEntries(detectVariables(st.version.content).map((n) => [n, String(st.version.variable_defaults[n] ?? '')])));
  function drawState() {
    const latest = st.prompt.versions[0];
    const d = dirty();
    stateChip.className = 'state ' + (d ? 'dirty' : 'clean');
    stateChip.textContent = d ? '● Unsaved changes' : st.version.id === latest.id ? '✓ Saved' : `Viewing v${st.version.version}, not the latest`;
    saveBtn.disabled = !d && st.version.id === latest.id;
    saveBtn.textContent = !d && st.version.id !== latest.id ? `Make v${st.version.version} the latest` : 'Save prompt';
  }
  const keep = () => remember({ promptId: st.prompt.id, text: text.value, values: st.values, moods: [...st.selected] });

  async function loadPrompt(id, versionId) {
    st.prompt = await api(`/prompts/${id}`); sel.value = id;
    st.version = st.prompt.versions.find((v) => v.id === versionId) || st.prompt.versions[0];
    mount(verSel, ...st.prompt.versions.map((v, i) => h('option', { value: v.id }, `Version ${v.version}${i === 0 ? ' (latest)' : ''}${v.note ? ' · ' + v.note : ''}`)));
    verSel.value = st.version.id;
    const same = !versionId && ws.promptId === id && ws.text;
    text.value = same ? ws.text : st.version.content;
    st.values = { ...st.version.variable_defaults, ...(same ? ws.values : {}) };
    drawVars();
  }
  function drawVars() {
    const names = detectVariables(text.value);
    mount(varsBox, names.length ? h('div', { class: 'small muted' }, 'Variables: change a value to test a variation without rewriting the prompt.') : null,
      ...names.map((n) => field(n, h('input', { value: st.values[n] ?? '', oninput: (e) => { st.values[n] = e.target.value; keep(); drawState(); } }))));
    hint.textContent = names.length ? '' : 'Tip: write {{tone}} anywhere in the prompt to create a variable you can change per test.';
    keep(); drawState();
  }
  text.addEventListener('input', drawVars);
  text.addEventListener('keydown', (e) => { if ((e.ctrlKey || e.metaKey) && e.key === 'Enter' && !runBtn.disabled) runBtn.click(); });
  verSel.addEventListener('change', () => { ws.text = ''; loadPrompt(st.prompt.id, verSel.value); });
  sel.addEventListener('change', () => { remember({ promptId: sel.value, text: '' }); ws.promptId = null; loadPrompt(sel.value); });

  saveBtn.addEventListener('click', async () => {
    saveBtn.disabled = true;
    try {
      const v = await api(`/prompts/${st.prompt.id}/versions`, { method: 'POST', body: { content: text.value, variable_defaults: varsOf(), note: 'Saved from editor' } });
      remember({ text: '' }); ws.text = ''; toast(`Saved as version ${v.version}`); await loadPrompt(st.prompt.id);
    } catch (e) { toast(e.message, true); drawState(); }
  });

  function drawMoods() {
    const all = (on) => { scenarios.forEach((s) => (on ? st.selected.add(s.id) : st.selected.delete(s.id))); drawMoods(); keep(); };
    mount(moodsBox, ...scenarios.map((s) => {
      const chip = h('span', { class: 'chip' + (st.selected.has(s.id) ? ' on' : ''), role: 'button', tabindex: 0, title: s.persona,
        onclick: () => { st.selected.has(s.id) ? st.selected.delete(s.id) : st.selected.add(s.id); drawMoods(); keep(); },
        onkeydown: (e) => { if (e.key === 'Enter' || e.key === ' ') { e.preventDefault(); chip.click(); } } }, s.name,
        h('button', { class: 'link', title: 'Edit this mood', style: 'padding:0 2px', onclick: (e) => { e.stopPropagation(); moodDialog(s); } }, '✎'));
      chip.style.setProperty('--dot', moodColor(s.mood));
      return chip;
    }), h('button', { class: 'chip plain', onclick: () => moodDialog(null) }, '+ Add mood'));
    mount(moodTools, h('span', { class: 'small muted' }, `${st.selected.size} of ${scenarios.length} selected`), h('button', { class: 'link', onclick: () => all(true) }, 'All'), h('button', { class: 'link', onclick: () => all(false) }, 'None'));
    runBtn.disabled = !st.selected.size; runBtn.textContent = st.selected.size ? `Run test on ${st.selected.size} mood${st.selected.size === 1 ? '' : 's'}` : 'Pick at least one mood';
  }
  const moodTools = h('div', { class: 'row' });

  function moodDialog(s) {
    const name = h('input', { value: s?.name || '', placeholder: 'e.g. Impatient' });
    const who = h('textarea', { rows: 3, value: s?.persona || '', placeholder: 'Who is calling, what is going on, and how do they talk?' });
    const first = h('input', { value: s?.opening_message || '', placeholder: 'What they say first' });
    const close = dialog(s ? 'Edit mood' : 'Add a mood', h('form', { class: 'stack', onsubmit: async (e) => {
      e.preventDefault();
      try {
        const body = { name: name.value, mood: s?.mood || slug(name.value) || 'custom', persona: who.value, behavior: s?.behavior || '', opening_message: first.value, intensity: s?.intensity ?? 3, max_turns: s?.max_turns ?? 6, scripted_turns: s?.scripted_turns || [], variables: s?.variables || {}, tags: s?.tags || [] };
        const r = await api(s ? `/scenarios/${s.id}` : '/scenarios', { method: s ? 'PUT' : 'POST', body });
        if (s) Object.assign(s, r); else { scenarios.push(r); st.selected.add(r.id); }
        close(); drawMoods(); keep();
      } catch (err) { toast(err.message, true); }
    } }, field('Mood', name), field('The caller', who), field('First line', first), h('button', { class: 'go', type: 'submit' }, 'Save'),
      s ? h('button', { type: 'button', class: 'link danger', onclick: async () => { if (await ask(`Remove “${s.name}”? Past results are kept.`, { yes: 'Remove', danger: true })) { await api(`/scenarios/${s.id}`, { method: 'DELETE' }); scenarios.splice(scenarios.indexOf(s), 1); st.selected.delete(s.id); close(); drawMoods(); } } }, 'Remove this mood') : null));
  }

  function newPrompt() {
    const name = h('input', { placeholder: 'e.g. Calm coach' });
    const close = dialog('New prompt', h('form', { class: 'stack', onsubmit: async (e) => {
      e.preventDefault();
      try { const p = await api('/prompts', { method: 'POST', body: { name: name.value, content: 'You are a calm, caring voice assistant. Keep replies to 2-4 short spoken sentences and ask one question at a time.' } }); remember({ promptId: p.id, text: '' }); close(); location.hash = '#/test'; location.reload(); }
      catch (err) { toast(err.message, true); }
    } }, field('Name', name), h('button', { class: 'go', type: 'submit' }, 'Create')));
  }

  runBtn.addEventListener('click', async () => {
    if (!cfg.llm_ready) { location.hash = '#/settings'; return; }
    runBtn.disabled = true; runBtn.textContent = 'Starting…';
    try {
      let versionId = st.version.id;
      if (dirty()) { const v = await api(`/prompts/${st.prompt.id}/versions`, { method: 'POST', body: { content: text.value, variable_defaults: varsOf(), note: 'Saved when run' } }); versionId = v.id; }
      const run = await api('/runs', { method: 'POST', body: { name: '', prompt_version_id: versionId, eval_set_id: st.evalId, scenario_ids: [...st.selected], variables: varsOf() } });
      remember({ text: '', promptId: st.prompt.id }); ws.text = '';
      location.hash = `#/test/${run.id}`;
    } catch (e) { toast(e.message, true); drawMoods(); }
  });

  // ---- results of a run: live tiles while it runs, an animated gauge when it is done
  const openIds = new Set();
  const tiles = new Map();
  const tilesBox = h('div', { class: 'tiles' });
  const progress = h('i', { style: 'width:0%' });
  const progressText = h('strong', {});
  const summary = h('div', { class: 'card stack' });
  const rowsBox = h('div', { class: 'stack', style: 'gap:10px' });
  let celebrated = false; let sawRunning = false;
  function tileFor(c) {
    let t = tiles.get(c.id);
    if (!t) { t = { el: h('div', { class: 'tile' }), nm: h('div', { class: 'nm' }), st: h('div', { class: 'st' }) }; t.el.append(t.nm, t.st); tiles.set(c.id, t); tilesBox.append(t.el); }
    const k = c.status === 'completed' ? (c.verdict === 'pass' ? 'pass' : c.verdict === 'fail' ? 'fail' : 'wait') : 'wait';
    const wanted = 'tile ' + k;
    if (t.el.className !== wanted) t.el.className = wanted;
    t.nm.textContent = c.title;
    t.st.textContent = k === 'pass' ? `✓ Passed · ${Math.round(c.score)}` : k === 'fail' ? '✕ Needs work' : c.status === 'evaluating' ? 'Scoring…' : c.status === 'queued' ? 'Waiting…' : 'Simulating the call…';
  }
  async function showRun(id) {
    let run;
    try { run = await api(`/runs/${id}`); } catch (e) { mount(out, h('div', { class: 'notice bad' }, e.message)); return; }
    if (gone) return;
    const c = run.counts, done = c.total - c.pending, running = run.status === 'queued' || run.status === 'running';
    if (!out.firstChild) mount(out, h('div', { class: 'step' }, h('i', {}, '3'), 'Results'), summary, tilesBox, rowsBox);
    run.conversations.forEach(tileFor);
    if (running) {
      sawRunning = true;
      progress.style.width = `${(100 * done) / c.total}%`; progressText.textContent = `Testing… ${done} of ${c.total} moods done`;
      if (!summary.firstChild) mount(summary, progressText, h('div', { class: 'progress' }, progress), h('div', { class: 'small muted' }, 'Each mood is a simulated caller. Tiles flip when a mood is scored.'));
      timer = setTimeout(() => showRun(id), 1500);
      return;
    }
    const decided = c.passed + c.failed;
    const kindOf = run.pass_rate === null ? '' : run.pass_rate >= 80 ? 'pass' : run.pass_rate >= 50 ? 'warn' : 'fail';
    const order = { fail: 0, error: 1, pass: 2 };
    const rows = [...run.conversations].sort((a, b) => (order[a.verdict] ?? 3) - (order[b.verdict] ?? 3));
    let previous = null;
    try { previous = (await api('/runs?limit=15')).items.find((r) => r.id !== run.id && r.status === 'completed' && r.pass_rate !== null && r.created_at < run.created_at); } catch { /* optional */ }
    const diff = previous && run.pass_rate !== null ? Math.round(run.pass_rate - previous.pass_rate) : null;
    mount(summary, h('div', { class: 'result' }, run.pass_rate === null ? h('div', { class: 'notice' }, 'No mood could be scored.') : gauge(run.pass_rate, kindOf),
      h('div', { class: 'stack', style: 'gap:6px' }, h('strong', { style: 'font-size:20px' }, run.pass_rate === null ? 'Could not score' : run.pass_rate >= 80 ? 'Looking good' : run.pass_rate >= 50 ? 'Getting there' : 'Needs work'),
        h('div', { class: 'muted' }, `${c.passed} of ${decided || c.total} moods passed`),
        diff === null ? null : h('div', { class: 'row' }, h('span', { class: 'delta ' + (diff > 0 ? 'up' : diff < 0 ? 'down' : 'same') }, diff > 0 ? `▲ +${diff}` : diff < 0 ? `▼ ${diff}` : '＝ same'), h('span', { class: 'small muted' }, `vs your previous test (${Math.round(previous.pass_rate)}%)`)),
        h('div', { class: 'small muted' }, [run.prompt_label, ...Object.entries(run.config.variables || {}).slice(0, 3).map(([k, v]) => `${k}: ${v}`)].join(' · ')))),
      publishRow(run));
    tilesBox.hidden = true;
    mount(rowsBox, ...rows.map((r) => conversationRow(r, { open: openIds.has(r.id), onToggle: (o) => (o ? openIds.add(r.id) : openIds.delete(r.id)) })));
    if (kindOf === 'pass' && sawRunning && !celebrated) { celebrated = true; confetti(); }
    out.scrollIntoView({ behavior: 'smooth', block: 'start' });
  }
  function publishRow(run) {
    const go = async (env, confirm = false) => {
      try {
        const g = run.config;
        await api('/deployments', { method: 'POST', body: { environment: env, prompt_version_id: run.prompt_version_id, variables: g.variables || {}, temperature: g.temperature ?? 0.7, max_tokens: g.max_tokens ?? 350, provider: g.provider || null, model: g.model || null, note: run.name, confirm } });
        toast(env === 'production' ? 'Live in your app' : 'Published to your test app');
      } catch (e) {
        if (e.status === 409 && await ask(`${e.message}\n\nPublish anyway?`, { yes: 'Publish anyway' })) return go(env, true);
        if (e.status !== 409) toast(e.message, true);
      }
    };
    return h('div', { class: 'stack', style: 'gap:6px' }, h('button', { class: 'go', onclick: () => go('production') }, 'Publish to my app'),
      h('div', { class: 'row', style: 'justify-content:center' }, h('button', { class: 'link', onclick: () => go('staging') }, 'Publish to test app only')));
  }

  const live = active.production;
  mount(root,
    h('div', { class: 'hero' }, h('h1', {}, 'Test a prompt'), h('div', { class: 'muted' }, 'Write it, pick the moods, and see what passes.'),
      h('div', { class: 'pills' },
        cfg.llm_ready ? h('span', { class: 'pill ok' }, '● Groq connected') : h('a', { class: 'pill bad', href: '#/settings' }, '○ Connect Groq →'),
        cfg.storage === 'temporary' ? h('a', { class: 'pill warn', href: '#/settings' }, '⚠ Temporary storage') : h('span', { class: 'pill ok' }, `● ${cfg.database === 'postgres' ? 'Database saved' : 'Local database'}`),
        live ? h('span', { class: 'pill ok' }, `Live in app: ${live.prompt_label}`) : h('span', { class: 'pill' }, 'Nothing published to your app yet'))),
    h('div', { class: 'card stack' }, h('div', { class: 'step', style: 'margin:0' }, h('i', {}, '1'), 'Your prompt'),
      h('div', { class: 'row', style: 'flex-wrap:nowrap' }, sel, h('button', { onclick: newPrompt }, '+ New')),
      h('div', { class: 'savebar' }, verSel, stateChip, h('span', { class: 'grow' }), saveBtn), text, varsBox, hint,
      h('details', { class: 'more' }, h('summary', {}, 'Creativity and reply length'), h('div', { style: 'margin-top:12px' }, styleBox))),
    h('div', { class: 'card stack' }, h('div', { class: 'step', style: 'margin:0' }, h('i', {}, '2'), 'Moods to test'), h('div', { class: 'small muted' }, 'Each mood is a simulated caller. Hover a mood to read who it plays.'), moodsBox, moodTools),
    h('div', { class: 'runbar' }, runBtn), out);
  await loadPrompt(prompts.some((p) => p.id === ws.promptId) ? ws.promptId : prompts[0].id);
  drawMoods();
  if (params[0]) await showRun(params[0]);
  return () => { gone = true; clearTimeout(timer); };
}
