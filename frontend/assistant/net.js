// The product's API, plus the shared helpers from the lab (same server, same access token).
import { api } from '/lab/api.js';

export { apiForm, apiBlob, getConfig } from '/lab/api.js';
export const A = (path, options) => api(`/api/assistant${path}`, options);
export const lab = api;  // the lab's own endpoints: provider keys, voices, speech to text

export const durationText = (s) => (!s ? '' : s < 60 ? `${s}s` : `${Math.floor(s / 60)}m ${String(s % 60).padStart(2, '0')}s`);
export const who = (c) => c.caller_name || c.caller_number || 'Unknown caller';
export const rupees = (v) => (v === undefined || v === null ? '' : `₹${v < 1 ? v.toFixed(2) : v.toFixed(1)}`);
export const IMPORTANCE = { action: ['Needs you', 'act', '!'], fyi: ['Good to know', 'fyi', 'i'], ignore: ['Not worth your time', 'skip', '–'] };
