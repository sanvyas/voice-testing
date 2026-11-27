// Calls: one row per person. People who are waiting come first, in orange.
import { h, mount } from '/lab/ui.js';
import { A } from '../net.js';
import { t, getLang, dayLabel, waitingFor, clock, initial } from '../i18n.js';
import { icon, Logo, sheet, isOnline, setOnline, toast, telLink } from '../kit.js';
import { shell, setBadge, saveProfile, go, setupDone } from '../shell.js';

const TABS = [['need', ['आपकी ज़रूरत', 'Needs you']], ['good', ['जानने लायक', 'Good to know']], ['spam', ['काम की नहीं', 'Not worth it']], ['all', ['सब', 'All']]];
const RANGES = [['any', ['सब दिन', 'All time']], ['today', ['आज', 'Today']], ['7d', ['7 दिन', '7 days']], ['30d', ['30 दिन', '30 days']]];
const cacheKey = (tab) => `munshi.people.${getLang()}.${tab}`;
const readCache = (tab) => { try { return JSON.parse(localStorage.getItem(cacheKey(tab)) || 'null'); } catch { return null; } };
const writeCache = (tab, data) => { try { localStorage.setItem(cacheKey(tab), JSON.stringify(data)); } catch { /* storage blocked */ } };

export async function render(root, { query }) {
  let tab = TABS.some(([k]) => k === query.get('tab')) ? query.get('tab') : 'need';
  let q = ''; let range = 'any'; let open = false; let data = null; let timer = null; let alive = true;
  const head = h('div', { class: 'top' }); const tabs = h('div', { class: 'tabs', role: 'tablist' }); const body = h('div', { class: 'scroll' }); const panel = h('div'); const list = h('div'); const sum = h('div', { class: 'sumrow' });

  function drawHead() {
    const state = !setupDone() ? 'setup' : shell.profile.assistant_on ? 'on' : 'off';
    const label = { on: t(['Munshi चालू', 'Munshi ON']), off: t(['Munshi बंद', 'Munshi OFF']), setup: t(['सेटअप बाकी', 'Finish setup']) }[state];
    mount(head, h('div', { class: 'brand' }, Logo(34), 'Munshi'), h('button', { class: `chip ${state}`, onclick: () => statusSheet(state) }, h('i'), label));
  }
  function statusSheet(state) {
    const on = shell.profile.assistant_on;
    sheet(state === 'setup' ? t(['सेटअप पूरा करें', 'Finish setup']) : on ? t(['Munshi चालू है', 'Munshi is ON']) : t(['Munshi बंद है', 'Munshi is OFF']), (close) => [
      h('p', {}, state === 'setup' ? t(['फ़ोन में कोड डायल करना बाकी है। तब तक Munshi कॉल नहीं उठाएगा।', 'You still need to dial the code on your phone. Until then Munshi will not pick up.'])
        : on ? t(['फ़ोन पहले आपका बजेगा। लगभग 20 सेकंड में न उठाएँ तो Munshi उठाएगा। बंद करने पर सारी कॉल सिर्फ़ आपके फ़ोन पर आएँगी।', 'Your phone rings first. If you do not pick up in about 20 seconds, Munshi does. If you switch it off, all calls ring only your phone.'])
          : t(['अभी सारी कॉल सिर्फ़ आपके फ़ोन पर आ रही हैं। Munshi कोई कॉल नहीं उठा रहा।', 'All calls ring only your phone now. Munshi is not answering any call.'])),
      h('button', { class: state === 'setup' || !on ? 'primary' : 'outline', style: 'width:100%', onclick: async () => {
        close();
        if (state === 'setup') return go('#/setup');
        try { await saveProfile({ assistant_on: !on }); drawHead(); window.dispatchEvent(new Event('munshi-toast')); } catch (e) { alert(e.message); }
      } }, state === 'setup' ? t(['सेटअप खोलें', 'Open setup']) : on ? t(['Munshi बंद करें', 'Switch Munshi off']) : t(['Munshi चालू करें', 'Switch Munshi on']))]);
  }
  function drawTabs() {
    mount(tabs, ...TABS.map(([k, l]) => h('button', { class: `tab ${k}${tab === k ? ' on' : ''}`, role: 'tab', 'aria-selected': tab === k, onclick: () => { tab = k; history.replaceState(null, '', `#/calls?tab=${k}`); drawTabs(); fetchList(); } },
      t(l), k === 'need' && data && data.pending_calls ? h('b', {}, String(data.pending_calls)) : null)));
  }
  const filterActive = () => range !== 'any' || !!q.trim();
  function drawPanel() {
    const input = h('input', { value: q, placeholder: t(['नाम या बात खोजें', 'Search name or topic']), 'aria-label': t(['खोजें', 'Search']), oninput: (e) => { q = e.target.value; clearTimeout(timer); timer = setTimeout(fetchList, 250); } });
    mount(panel, open ? h('div', { class: 'filters' }, input, h('div', { class: 'ranges' }, ...RANGES.map(([k, l]) => h('button', { class: 'range' + (range === k ? ' on' : ''), onclick: () => { range = k; drawPanel(); fetchList(); } }, t(l))))) : null);
  }
  function showActions(r) {
    const phone = r.key && /^\d/.test(r.key) ? r.key : null;
    sheet(r.name, (close) => [
      phone ? h('button', { class: 'opt', onclick: () => { close(); location.href = telLink(phone); } }, h('i', {}, icon('phone')), t(['कॉल करें', 'Call back'])) : null,
      h('button', { class: 'opt', onclick: () => { close(); go(`#/thread/${encodeURIComponent(r.key)}`); } }, h('i', {}, icon('chat')), t(['बातचीत देखें', 'View messages'])),
      r.pending > 0 ? h('button', { class: 'opt', onclick: async () => { try { await A(`/people/${encodeURIComponent(r.key)}/done`, { method: 'POST' }); close(); await fetchList(); toast(t(['हो गया', 'Marked done'])); } catch (e) { toast(e.message, { bad: true }); } } }, h('i', {}, icon('check')), t(['सब हो गया', 'Mark all done'])) : null,
    ].filter(Boolean));
  }
  function drawList() {
    const rows = data ? data.rows : [];
    const sumText = !data ? '' : tab === 'need' ? (data.pending_calls ? t([`आज के ${data.pending_today} · पुराने ${data.pending_older}`, `${data.pending_today} today · ${data.pending_older} older`]) : '')
      : filterActive() ? '' : t([`${rows.length} लोग`, `${rows.length} people`]);
    mount(sum, h('span', {}, sumText), h('button', { class: 'iconbtn' + (open || filterActive() ? ' on' : ''), 'aria-label': t(['खोजें', 'Search']), onclick: () => { open = !open; drawPanel(); drawList(); } }, icon('search')));
    const empty = rows.length === 0;
    const none = tab === 'need' && !filterActive() ? [t(['कुछ बाकी नहीं', 'Nothing pending']), t(['सारे कॉल-बैक हो चुके हैं। पुरानी कॉल “सब” में देखें।', 'All call-backs are done. See older calls under All.'])]
      : data && data.people === 0 && !filterActive() ? [t(['अभी कोई कॉल नहीं', 'No calls yet']), t(['जब आप कॉल नहीं उठाएँगे, Munshi यहाँ लिख देगा।', 'When you miss a call, Munshi will write it here.'])]
        : [t(['कोई कॉल नहीं मिली', 'No calls found']), t(['खोज या तारीख बदलकर देखें।', 'Try changing the search or dates.'])];
    mount(list, empty ? h('div', { class: 'empty' }, h('div', { class: 'ring' }, icon('check', 32)), h('b', {}, none[0]), h('p', {}, none[1]))
      : h('div', { class: 'list' }, ...rows.map((r) => {
        const wait = r.pending > 0;
        let pt = null;
        return h('button', { class: 'person' + (wait ? ' wait' : ''),
          onclick: () => go(`#/thread/${encodeURIComponent(r.key)}`),
          oncontextmenu: (e) => { e.preventDefault(); showActions(r); },
          ontouchstart: () => { pt = setTimeout(() => { pt = null; showActions(r); }, 500); },
          ontouchend: () => { if (pt) clearTimeout(pt); },
          ontouchmove: () => { if (pt) { clearTimeout(pt); pt = null; } } },
          h('div', { class: 'av' + (wait ? ' wait' : r.kind === 'good' ? ' good' : '') }, initial(r.name)),
          h('div', { class: 'pmain' }, h('div', { class: 'prow' }, h('div', { class: 'pname' }, r.name, r.calls > 1 ? h('span', { class: 'ncalls' }, t([`${r.calls} कॉल`, `${r.calls} calls`])) : null),
            h('span', { class: 'ptime' }, r.days_ago > 0 ? dayLabel(r.days_ago) : clock(r.at))),
          h('div', { class: 'pask' }, r.summary), r.oldest_pending_days > 0 ? h('div', { class: 'page' }, waitingFor(r.oldest_pending_days)) : null),
          wait ? h('span', { class: 'badge' }, String(r.pending)) : null);
      })));
  }
  const foot = h('div', { class: 'foot' });
  function drawFoot() { const d = data && data.today; mount(foot, d && d.handled ? h('button', { class: 'link', style: 'font-size:13px;font-weight:500;color:var(--muted);min-height:auto;justify-content:center;width:100%', onclick: () => go('#/orders') }, t([`आज Munshi ने ${d.handled} कॉल संभालीं, ${d.orders} ऑर्डर नोट किए`, `Today Munshi handled ${d.handled} calls and noted ${d.orders} orders`])) : ''); }

  async function fetchList() {
    try {
      data = await A(`/people?tab=${tab}&q=${encodeURIComponent(q.trim())}&range=${range}&lang=${getLang()}`);
      setOnline(true); if (!q.trim() && range === 'any') writeCache(tab, data);
    } catch (e) {
      if (e.status !== 0) throw e;
      setOnline(false); data = readCache(tab) || { rows: [], people: 0, pending_calls: shell.badge, pending_today: 0, pending_older: 0, today: { handled: 0, orders: 0 } };
    }
    if (!alive) return;
    setBadge(data.pending_calls); drawTabs(); drawList(); drawFoot();
  }
  mount(root, head, tabs, h('div', { class: 'scroll', style: 'padding-top:0' }, sum, panel, list, foot));
  drawHead(); drawTabs(); drawPanel(); drawList();
  await fetchList();
  // SSE: live-refresh when a new call comes in
  let sse = null;
  try { sse = new EventSource('/api/assistant/events'); sse.onmessage = () => { if (alive) fetchList(); }; sse.onerror = () => { sse?.close(); sse = null; }; } catch { /* SSE not available */ }
  return () => { alive = false; clearTimeout(timer); sse?.close(); };
}
