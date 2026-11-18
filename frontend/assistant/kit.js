// Shared pieces of the owner app: icons, the logo, toast, bottom sheet, online state.
import { h, svg } from '/lab/ui.js';

const P = {
  phone: 'M6.6 10.8a15.1 15.1 0 006.6 6.6l2.2-2.2a1 1 0 011-.25 11.4 11.4 0 003.6.6 1 1 0 011 1V20a1 1 0 01-1 1A17 17 0 013 4a1 1 0 011-1h3.5a1 1 0 011 1c0 1.25.2 2.45.57 3.57a1 1 0 01-.25 1z',
  check: 'M9 16.2L4.8 12l-1.4 1.4L9 19 21 7l-1.4-1.4z',
  search: 'M15.5 14h-.79l-.28-.27A6.47 6.47 0 0016 9.5 6.5 6.5 0 109.5 16c1.61 0 3.09-.59 4.23-1.57l.27.28v.79l5 4.99L20.49 19l-4.99-5zm-6 0C7.01 14 5 11.99 5 9.5S7.01 5 9.5 5 14 7.01 14 9.5 11.99 14 9.5 14z',
  camera: 'M12 15.2a3.2 3.2 0 100-6.4 3.2 3.2 0 000 6.4zM9 2L7.17 4H4a2 2 0 00-2 2v12a2 2 0 002 2h16a2 2 0 002-2V6a2 2 0 00-2-2h-3.17L15 2H9zm3 15a5 5 0 110-10 5 5 0 010 10z',
  image: 'M21 19V5a2 2 0 00-2-2H5a2 2 0 00-2 2v14a2 2 0 002 2h14a2 2 0 002-2zM8.5 13.5l2.5 3.01L14.5 12l4.5 6H5l3.5-4.5z',
  file: 'M14 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V8l-6-6zm-1 7V3.5L18.5 9H13z',
  mic: 'M12 14a3 3 0 003-3V5a3 3 0 00-6 0v6a3 3 0 003 3zm5-3a5 5 0 01-10 0H5a7 7 0 006 6.92V21h2v-3.08A7 7 0 0019 11h-2z',
  pencil: 'M3 17.25V21h3.75L17.81 9.94l-3.75-3.75L3 17.25zM20.71 7.04a1 1 0 000-1.41l-2.34-2.34a1 1 0 00-1.41 0l-1.83 1.83 3.75 3.75 1.83-1.83z',
  back: 'M15.41 7.41L14 6l-6 6 6 6 1.41-1.41L10.83 12z', next: 'M8.59 16.59L13.17 12 8.59 7.41 10 6l6 6-6 6z', plus: 'M19 13h-6v6h-2v-6H5v-2h6V5h2v6h6z',
  book: 'M18 2H6a2 2 0 00-2 2v16a2 2 0 002 2h12a2 2 0 002-2V4a2 2 0 00-2-2zM6 4h5v8l-2.5-1.5L6 12V4z',
  people: 'M16 11c1.66 0 2.99-1.34 2.99-3S17.66 5 16 5s-3 1.34-3 3 1.34 3 3 3zm-8 0c1.66 0 2.99-1.34 2.99-3S9.66 5 8 5 5 6.34 5 8s1.34 3 3 3zm0 2c-2.33 0-7 1.17-7 3.5V19h14v-2.5c0-2.33-4.67-3.5-7-3.5zm8 0c-.29 0-.62.02-.97.05 1.16.84 1.97 1.97 1.97 3.45V19h6v-2.5c0-2.33-4.67-3.5-7-3.5z',
  more: 'M6 10a2 2 0 100 4 2 2 0 000-4zm12 0a2 2 0 100 4 2 2 0 000-4zm-6 0a2 2 0 100 4 2 2 0 000-4z',
  chat: 'M20 2H4a2 2 0 00-2 2v18l4-4h14a2 2 0 002-2V4a2 2 0 00-2-2z',
  todo: 'M19 3h-4.18C14.4 1.84 13.3 1 12 1s-2.4.84-2.82 2H5a2 2 0 00-2 2v14a2 2 0 002 2h14a2 2 0 002-2V5a2 2 0 00-2-2zm-7 0a1 1 0 110 2 1 1 0 010-2zm-2 14l-4-4 1.41-1.41L10 14.17l6.59-6.59L18 9l-8 8z',
  play: 'M8 5v14l11-7z', pause: 'M6 19h4V5H6v14zm8-14v14h4V5h-4z', alert: 'M1 21h22L12 2 1 21zm12-3h-2v-2h2v2zm0-4h-2v-4h2v4z',
  close: 'M19 6.41L17.59 5 12 10.59 6.41 5 5 6.41 10.59 12 5 17.59 6.41 19 12 13.41 17.59 19 19 17.59 13.41 12z',
  sound: 'M3 9v6h4l5 5V4L7 9H3zm13.5 3A4.5 4.5 0 0014 7.97v8.05A4.5 4.5 0 0016.5 12z', send: 'M2 21l21-9L2 3v7l15 2-15 2z',
};
export const icon = (name, size = 24) => svg('svg', { viewBox: '0 0 24 24', width: size, height: size, class: 'ic', 'aria-hidden': 'true' }, svg('path', { d: P[name] || P.check }));

export const Logo = (size = 34) => h('div', { style: `width:${size}px;height:${size}px;position:relative;flex:none` },
  h('div', { style: `position:absolute;left:0;top:0;width:40px;height:40px;border-radius:50%;background:#0B7A5B;transform:scale(${size / 40});transform-origin:0 0` },
    h('div', { style: "position:absolute;left:7px;top:8px;width:26px;height:22px;border-radius:8px;background:#fff;display:flex;align-items:center;justify-content:center;font:700 16px/1 'Noto Sans Devanagari',sans-serif;color:#0B7A5B;padding-top:2px;box-sizing:border-box" }, 'म'),
    h('div', { style: 'position:absolute;left:11px;top:25px;width:8px;height:8px;background:#fff;transform:rotate(45deg);border-radius:1px' })));

const app = () => document.getElementById('app');
let toastTimer = null;
export function toast(message, { bad = false, high = false } = {}) {
  app().querySelector('.toast')?.remove();
  app().append(h('div', { class: 'toast' + (bad ? ' bad' : '') + (high ? ' high' : ''), role: 'status' }, message));
  clearTimeout(toastTimer);
  toastTimer = setTimeout(() => app().querySelector('.toast')?.remove(), bad ? 5000 : 2400);
}

/** A bottom sheet. build(close) returns the content; tapping the dark area closes it. Returns close(). */
export function sheet(title, build) {
  const close = () => { scrim.remove(); };
  const body = h('div', { class: 'sheet', onclick: (e) => e.stopPropagation() }, h('div', { class: 'grab' }), h('h2', {}, title), build(close));
  const scrim = h('div', { class: 'scrim', onclick: close }, body);
  app().append(scrim);
  return close;
}

// Online state: shown as a banner. A failed request marks us offline until the next one works.
let online = navigator.onLine;
export const isOnline = () => online;
export function setOnline(v) { if (v !== online) { online = v; window.dispatchEvent(new Event('munshi-online')); } }
window.addEventListener('online', () => setOnline(true));
window.addEventListener('offline', () => setOnline(false));

/** Phone numbers as a tel: link (the # of a dial code must be encoded). */
export const telLink = (number) => `tel:${String(number || '').replace(/[^\d+*#]/g, '').replace(/#/g, '%23')}`;
