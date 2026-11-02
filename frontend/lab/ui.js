// Tiny DOM helpers. All dynamic content is set via text nodes, never parsed as markup.
const nativeAppend = Element.prototype.append;
Element.prototype.append = function (...nodes) {  // ignore null/false children, like h() does
  return nativeAppend.apply(this, nodes.flat(Infinity).filter((n) => n !== null && n !== undefined && n !== false));
};

export function h(tag, props, ...children) {
  const el = document.createElement(tag);
  for (const [k, v] of Object.entries(props || {})) {
    if (v === null || v === undefined || v === false) continue;
    if (k === 'class') el.className = v;
    else if (k.startsWith('on') && typeof v === 'function') el.addEventListener(k.slice(2), v);
    else if (k === 'value') el.value = v;
    else if (k in el && k !== 'list' && k !== 'form' && typeof v !== 'object') el[k] = v;
    else el.setAttribute(k, v === true ? '' : v);
  }
  el.append(...children);
  return el;
}
export const clear = (el) => { el.replaceChildren(); return el; };
export const mount = (el, ...children) => { el.replaceChildren(); el.append(...children); return el; };

export function toast(message, bad = false) {
  const t = h('div', { class: 'toast' + (bad ? ' bad' : '') }, message);
  document.getElementById('toasts').append(t);
  setTimeout(() => t.remove(), bad ? 7000 : 3000);
}

export function dialog(title, body, { locked = false } = {}) {
  const close = () => { back.remove(); document.removeEventListener('keydown', onKey); };
  const onKey = (e) => { if (e.key === 'Escape' && !locked) close(); };
  const back = h('div', { class: 'overlay', onmousedown: (e) => { if (e.target === back && !locked) close(); } },
    h('div', { class: 'dialog', role: 'dialog', 'aria-modal': 'true', 'aria-label': title }, h('h2', { style: 'margin:0' }, title), body));
  document.getElementById('modal-root').append(back);
  document.addEventListener('keydown', onKey);
  back.querySelector('input, textarea, select')?.focus();
  return close;
}

export function ask(message, { yes = 'OK', danger = false } = {}) {
  return new Promise((resolve) => {
    const close = dialog('Please confirm', h('div', { class: 'stack' }, h('p', { style: 'white-space:pre-line;margin:0' }, message),
      h('div', { class: 'row', style: 'justify-content:flex-end' },
        h('button', { onclick: () => { close(); resolve(false); } }, 'Cancel'),
        h('button', { class: danger ? 'go danger' : 'go', style: 'width:auto', onclick: () => { close(); resolve(true); } }, yes))));
  });
}

export const field = (label, control, hint) => h('label', { class: 'f' }, label, control, hint ? h('small', {}, hint) : null);

export function ago(iso) {
  if (!iso) return '';
  const s = Math.round((Date.now() - new Date(iso).getTime()) / 1000);
  if (s < 45) return 'just now';
  if (s < 3600) return `${Math.round(s / 60)} min ago`;
  if (s < 86400) return `${Math.round(s / 3600)} h ago`;
  if (s < 86400 * 14) return `${Math.round(s / 86400)} d ago`;
  return new Date(iso).toLocaleDateString();
}

export const VAR_RE = /\{\{\s*([A-Za-z_][A-Za-z0-9_]*)\s*\}\}/g;
export const detectVariables = (text) => [...new Set([...text.matchAll(VAR_RE)].map((m) => m[1]))];
export const pct = (v) => (v === null || v === undefined ? '–' : `${Math.round(v)}%`);
export const slug = (s) => s.trim().toLowerCase().replace(/[^a-z0-9]+/g, '_').replace(/^_|_$/g, '').slice(0, 40);

// ---- delight: icons, colours, count-up, gauge, sparkline, confetti ------------------------------------------
const NS = 'http://www.w3.org/2000/svg';
const reduced = () => window.matchMedia && window.matchMedia('(prefers-reduced-motion: reduce)').matches;
export function svg(tag, attrs = {}, ...kids) {
  const el = document.createElementNS(NS, tag);
  for (const [k, v] of Object.entries(attrs)) el.setAttribute(k, v);
  el.append(...kids);
  return el;
}
export const icon = (paths, circles = []) => svg('svg', { viewBox: '0 0 24 24', 'aria-hidden': 'true' }, ...paths.map((d) => svg('path', { d })), ...circles.map(([cx, cy, r]) => svg('circle', { cx, cy, r })));

export function moodColor(name = '') {
  let hue = 0;
  for (const ch of name) hue = (hue * 31 + ch.charCodeAt(0)) % 360;
  return `hsl(${hue} 68% 55%)`;
}

export function countUp(el, to, { ms = 900, suffix = '' } = {}) {
  if (reduced() || !Number.isFinite(to)) { el.textContent = `${Math.round(to)}${suffix}`; return; }
  const t0 = performance.now();
  const step = (t) => { const k = Math.min(1, (t - t0) / ms); el.textContent = `${Math.round(to * (1 - Math.pow(1 - k, 3)))}${suffix}`; if (k < 1) requestAnimationFrame(step); };
  requestAnimationFrame(step);
}

/** Circular score gauge that fills smoothly and counts up. */
export function gauge(value, kind) {
  const C = 2 * Math.PI * 54;
  const bar = svg('circle', { class: 'bar', cx: 66, cy: 66, r: 54, 'stroke-dasharray': C.toFixed(1) });
  bar.style.strokeDashoffset = C;
  const num = h('div', { class: 'num' }, '0%');
  const el = h('div', { class: `gauge ${kind || ''}`, role: 'img', 'aria-label': `Score ${Math.round(value)} percent` },
    svg('svg', { viewBox: '0 0 132 132' }, svg('circle', { class: 'track', cx: 66, cy: 66, r: 54 }), bar), num);
  requestAnimationFrame(() => requestAnimationFrame(() => { bar.style.strokeDashoffset = C * (1 - Math.max(0, Math.min(100, value)) / 100); countUp(num, value, { suffix: '%' }); }));
  return el;
}

/** Small trend line for a series of 0..100 values (oldest first). */
export function sparkline(values) {
  const W = 300, H = 56, pad = 6;
  if (values.length < 2) return h('div', { class: 'small muted' }, 'Run a few tests to see your trend.');
  const x = (i) => pad + (i * (W - 2 * pad)) / (values.length - 1);
  const y = (v) => pad + ((100 - v) / 100) * (H - 2 * pad);
  const pts = values.map((v, i) => `${x(i).toFixed(1)},${y(v).toFixed(1)}`);
  return svg('svg', { class: 'spark', viewBox: `0 0 ${W} ${H}`, preserveAspectRatio: 'none', role: 'img', 'aria-label': `Pass rate trend, latest ${Math.round(values.at(-1))} percent` },
    svg('defs', {}, svg('linearGradient', { id: 'sparkfill', x1: 0, y1: 0, x2: 0, y2: 1 }, svg('stop', { offset: '0%', 'stop-color': '#7c5cf0', 'stop-opacity': '.35' }), svg('stop', { offset: '100%', 'stop-color': '#7c5cf0', 'stop-opacity': '0' }))),
    svg('polygon', { class: 'ar', points: `${x(0)},${H} ${pts.join(' ')} ${x(values.length - 1)},${H}` }),
    svg('polyline', { class: 'ln', points: pts.join(' ') }), svg('circle', { cx: x(values.length - 1), cy: y(values.at(-1)), r: 4 }));
}

export function confetti() {
  if (reduced()) return;
  const colors = ['#7c5cf0', '#b25cf0', '#4fd49b', '#ffcf5a', '#5cc8ff', '#ff7d93'];
  const box = h('div', { class: 'confetti', 'aria-hidden': 'true' });
  for (let i = 0; i < 36; i++) {
    const p = h('i', {});
    p.style.setProperty('--c', colors[i % colors.length]);
    p.style.setProperty('--dx', `${(Math.random() - 0.5) * 520}px`);
    p.style.setProperty('--dy', `${Math.random() * 360 - 120}px`);
    p.style.setProperty('--r', `${Math.random() * 720 - 360}deg`);
    p.style.animationDelay = `${Math.random() * 120}ms`;
    box.append(p);
  }
  document.body.append(box);
  setTimeout(() => box.remove(), 1900);
}
