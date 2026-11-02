// The prompt you are working on, shared by Test and Talk. Edits are saved as a new version only when you run or talk.
import { api } from './api.js';
import { detectVariables } from './ui.js';

const KEY = 'lab.workspace';
const read = () => { try { return JSON.parse(localStorage.getItem(KEY)) || {}; } catch { return {}; } };
export const saved = () => read();
export function remember(patch) { try { localStorage.setItem(KEY, JSON.stringify({ ...read(), ...patch })); } catch { /* storage blocked */ } }

/** Make sure the text on screen exists as a prompt version; returns {versionId, values, label}. */
export async function ensureVersion({ promptId, text, values, version }) {
  const names = detectVariables(text);
  const vars = Object.fromEntries(names.map((n) => [n, String(values[n] ?? '')]));
  if (text === version.content) return { versionId: version.id, variables: vars, label: `v${version.version}`, created: false };
  const v = await api(`/prompts/${promptId}/versions`, { method: 'POST', body: { content: text, variable_defaults: vars, note: 'Edited' } });
  return { versionId: v.id, variables: vars, label: `v${v.version}`, created: true, version: v };
}
