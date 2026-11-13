// The product's API, plus the shared helpers from the lab (same server, same access token).
import { api } from '/lab/api.js';
import { svg } from '/lab/ui.js';

export { apiForm, apiBlob, getConfig } from '/lab/api.js';
export const A = (path, options) => api(`/api/assistant${path}`, options);
export const lab = api;  // the lab's own endpoints: provider keys, voices, speech to text

export const durationText = (s) => (!s ? '' : s < 60 ? `${s}s` : `${Math.floor(s / 60)}m ${String(s % 60).padStart(2, '0')}s`);
export const who = (c) => c.caller_name || c.caller_number || 'Unknown caller';
export const rupees = (v) => (v === undefined || v === null ? '' : `Rs ${v < 1 ? v.toFixed(2) : v.toFixed(1)}`);
export const initials = (name = '') => (name.replace(/[^\p{L}\s]/gu, '').trim().split(/\s+/).slice(0, 2).map((w) => w[0]).join('').toUpperCase() || '?');
export const avatarClass = (key = '') => `a${[...key].reduce((n, ch) => n + ch.charCodeAt(0), 0) % 5}`;

/** Stroke icon. Pass SVG path strings and optional [cx, cy, r] circles. */
export function ic(paths, circles = [], small = false) {
  const el = svg('svg', { viewBox: '0 0 24 24', 'aria-hidden': 'true' }, ...paths.map((d) => svg('path', { d })), ...circles.map(([cx, cy, r]) => svg('circle', { cx, cy, r })));
  el.setAttribute('class', 'i' + (small ? ' s' : ''));
  return el;
}
export const ICONS = {
  phone: ['M5 4h4l2 5-2.5 1.5a11 11 0 0 0 5 5L15 13l5 2v4a2 2 0 0 1-2 2A16 16 0 0 1 3 6a2 2 0 0 1 2-2z'],
  mic: ['M12 3a3 3 0 0 0-3 3v6a3 3 0 0 0 6 0V6a3 3 0 0 0-3-3z', 'M5 11a7 7 0 0 0 14 0', 'M12 18v3'],
  users: ['M16 21v-2a4 4 0 0 0-4-4H7a4 4 0 0 0-4 4v2', 'M20 8v6', 'M23 11h-6'],
  sliders: ['M4 8h8', 'M16 8h4', 'M4 16h4', 'M12 16h8'],
  back: ['M15 6l-6 6 6 6'], next: ['M9 6l6 6-6 6'], check: ['M5 12l5 5L20 7'], x: ['M6 6l12 12', 'M18 6L6 18'], send: ['M5 12h14', 'M13 6l6 6-6 6'],
  pencil: ['M4 20l4-1 11-11a2.1 2.1 0 0 0-3-3L5 16l-1 4z'], search: ['M20 20l-4-4'], board: ['M5 5h14v14H5z', 'M5 10h14', 'M10 10v9'], chat: ['M4 5h16v11H9l-5 4z'], info: ['M12 11v5', 'M12 8h.01'], camera: ['M4 8h3l2-3h6l2 3h3v11H4z'],
};
