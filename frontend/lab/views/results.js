import { h, mount, toast, ask, ago, pct, sparkline } from '../ui.js';
import { api } from '../api.js';
import { kind, dotChar, why, isPending, checkList, transcript } from '../components.js';

export async function render(root, { params }) {
  return params[0] ? detail(root, params[0]) : list(root);
}

async function list(root) {
  const [runs, talks, apps] = await Promise.all([api('/runs?limit=20'), api('/conversations?source=live&limit=20'), api('/conversations?source=app&limit=20')]);
  const rows = [
    ...runs.items.map((r) => ({ type: 'test', id: r.id, at: r.created_at, title: r.name, sub: r.prompt_label, href: `#/test/${r.id}`,
      k: r.status !== 'completed' ? 'wait' : r.pass_rate === null ? 'warn' : r.pass_rate >= 80 ? 'pass' : 'fail', result: r.status !== 'completed' ? 'Running…' : `${r.counts.passed}/${r.counts.total} passed` })),
    ...talks.items.map((c) => ({ type: 'talk', id: c.id, at: c.created_at, title: c.title, sub: c.prompt_label, href: `#/results/${c.id}`, k: kind(c), result: why(c) })),
    ...apps.items.map((c) => ({ type: 'app', id: c.id, at: c.created_at, title: `${c.client || 'App'} user`, sub: `${c.environment} · ${c.prompt_label}`, href: `#/results/${c.id}`, k: kind(c), result: why(c) })),
  ].sort((a, b) => (a.at < b.at ? 1 : -1));
  let tab = 'all';
  const box = h('div', { class: 'stack', style: 'gap:10px' });
  const chips = h('div', { class: 'chips' });
  const draw = () => {
    mount(chips, ...[['all', 'All'], ['test', 'Tests'], ['talk', 'Talks'], ['app', 'App users']].map(([id, l]) => h('span', { class: 'chip' + (tab === id ? ' on' : ''), role: 'button', onclick: () => { tab = id; draw(); } }, l)));
    const shown = rows.filter((r) => tab === 'all' || r.type === tab);
    mount(box, ...(shown.length ? shown.map((r) => h('a', { href: r.href, class: 'item', style: 'color:inherit' }, h('div', { style: 'display:flex;gap:12px;align-items:center;padding:14px 16px' },
      h('span', { class: `dot ${r.k}${r.k === 'wait' ? ' spin' : ''}` }, dotChar[r.k]), h('div', { class: 'grow' }, h('div', { style: 'font-weight:600' }, r.title), h('div', { class: 'why' }, `${r.sub} · ${ago(r.at)}`)), h('span', { class: 'small muted' }, r.result)))) : [h('div', { class: 'empty card' }, 'Nothing here yet.')]));
  };
  const scores = runs.items.filter((r) => r.status === 'completed' && r.pass_rate !== null).slice(0, 12).reverse().map((r) => r.pass_rate);
  const last = scores.at(-1), best = scores.length ? Math.max(...scores) : null;
  mount(root, h('div', {}, h('h1', {}, 'Results'), h('div', { class: 'muted' }, 'Everything you have tested, talked or received from your app.')),
    scores.length ? h('div', { class: 'card stack' }, h('div', { class: 'row between' }, h('strong', {}, 'Your pass rate over time'), h('span', { class: 'small muted' }, `Latest ${Math.round(last)}% · Best ${Math.round(best)}%`)), sparkline(scores)) : null,
    chips, box);
  draw();
}

async function detail(root, id) {
  let timer = null; let gone = false;
  const box = h('div', { class: 'stack', style: 'gap:18px' });
  mount(root, h('a', { href: '#/results', class: 'small' }, '← Results'), box);
  async function load() {
    let c;
    try { c = await api(`/conversations/${id}`); } catch (e) { mount(box, h('div', { class: 'card empty' }, e.message)); return; }
    if (gone) return;
    const k = kind(c), live = c.status === 'live', unscored = c.status === 'completed' && !c.verdict;
    const evalId = async () => (await api('/eval-sets'))[0].id;
    mount(box,
      h('div', {}, h('h1', {}, c.title || 'Conversation'), h('div', { class: 'muted small' }, [c.source === 'app' ? `${c.client || 'App'} · ${c.environment}` : c.source === 'live' ? 'Talk' : c.source, c.prompt_label, ago(c.created_at)].filter(Boolean).join(' · '))),
      h('div', { class: 'card stack' }, live ? h('div', {}, h('strong', {}, 'This conversation is still open.'))
        : unscored ? h('strong', {}, 'Not scored yet') : h('div', { class: 'score ' + (k === 'wait' ? '' : k) }, h('b', {}, isPending(c) ? '…' : k === 'pass' ? 'PASS' : k === 'fail' ? 'FAIL' : '!'), c.score !== null ? h('span', { class: 'muted' }, `score ${Math.round(c.score)}`) : null),
        h('div', { class: 'muted' }, live ? 'Finish it to get a result.' : why(c)),
        live ? h('button', { class: 'go', onclick: async () => { try { await api(`/live/${id}/finish`, { method: 'POST', body: { eval_set_id: await evalId() } }); load(); } catch (e) { toast(e.message, true); } } }, 'Finish and get result')
          : unscored || c.verdict === 'error' || c.status === 'error' ? h('button', { class: 'go', onclick: async () => { try { await api(`/conversations/${id}/reevaluate`, { method: 'POST', body: { eval_set_id: await evalId() } }); load(); } catch (e) { toast(e.message, true); } } }, unscored ? 'Score it now' : 'Try scoring again') : null),
      c.results.length ? h('div', { class: 'card' }, h('h2', {}, 'Checks'), checkList(c.results)) : null,
      h('div', { class: 'card' }, h('h2', {}, 'Conversation'), c.turns.length ? transcript(c.turns) : h('div', { class: 'muted' }, 'No messages.')),
      !isPending(c) ? h('div', { style: 'text-align:center' }, h('button', { class: 'link danger', onclick: async () => { if (await ask('Delete this conversation?', { yes: 'Delete', danger: true })) { await api(`/conversations/${id}`, { method: 'DELETE' }); location.hash = '#/results'; } } }, 'Delete')) : null);
    if (isPending(c)) timer = setTimeout(load, 1500);
  }
  await load();
  return () => { gone = true; clearTimeout(timer); };
}
