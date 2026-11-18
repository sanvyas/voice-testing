// What every screen shares: the business's status and profile, the number of people waiting, and simple navigation.
import { A } from './net.js';
import { setOnline } from './kit.js';

export const shell = { status: null, profile: null, badge: 0 };

export async function load() {
  const [status, profile] = await Promise.all([A('/status'), A('/profile')]);
  shell.status = status; shell.profile = profile;
  setOnline(true);
}
export async function saveProfile(changes) {
  shell.profile = await A('/profile', { method: 'PUT', body: { ...shell.profile, ...changes } });
  window.dispatchEvent(new Event('munshi-changed'));
  return shell.profile;
}
export function setBadge(n) { if (n !== shell.badge) { shell.badge = n; window.dispatchEvent(new Event('munshi-badge')); } }
export async function refreshBadge() { try { setBadge((await A('/people?tab=need')).pending_calls); } catch { /* offline or signed out */ } }
export const go = (hash) => { location.hash = hash; };
/** Is the business ready to answer calls? The profile is filled in and the forwarding code has been dialled. */
export const setupDone = () => !!(shell.profile && shell.profile.business_name && shell.profile.owner_name && shell.profile.forwarding_done);
