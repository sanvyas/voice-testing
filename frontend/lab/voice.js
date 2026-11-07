// Server voices (Google, Chatterbox): language list, sample sentences and a player that works on phones.
import { api, apiBlob } from './api.js';

export const LANGS = [['en-IN', 'English (India)'], ['en-US', 'English (US)'], ['en-GB', 'English (UK)'], ['hi-IN', 'Hindi'], ['ta-IN', 'Tamil'], ['te-IN', 'Telugu'],
  ['bn-IN', 'Bengali'], ['mr-IN', 'Marathi'], ['gu-IN', 'Gujarati'], ['kn-IN', 'Kannada'], ['ml-IN', 'Malayalam'], ['pa-IN', 'Punjabi']];
export const SAMPLES = {
  en: 'Hello, I am here. Tell me what is on your mind.', hi: 'नमस्ते, मैं यहाँ हूँ। आप क्या महसूस कर रहे हैं?', ta: 'வணக்கம், நான் இங்கே இருக்கிறேன். உங்கள் மனதில் என்ன இருக்கிறது?',
  te: 'నమస్కారం, నేను ఇక్కడ ఉన్నాను. మీ మనసులో ఏముంది?', bn: 'নমস্কার, আমি এখানে আছি। আপনার মনে কী আছে?', mr: 'नमस्कार, मी इथे आहे. तुमच्या मनात काय आहे?',
  gu: 'નમસ્તે, હું અહીં છું. તમારા મનમાં શું છે?', kn: 'ನಮಸ್ಕಾರ, ನಾನು ಇಲ್ಲಿದ್ದೇನೆ. ನಿಮ್ಮ ಮನಸ್ಸಿನಲ್ಲಿ ಏನಿದೆ?', ml: 'നമസ്കാരം, ഞാൻ ഇവിടെയുണ്ട്. നിങ്ങളുടെ മനസ്സിൽ എന്താണ്?', pa: 'ਸਤ ਸ੍ਰੀ ਅਕਾਲ, ਮੈਂ ਇੱਥੇ ਹਾਂ। ਤੁਹਾਡੇ ਮਨ ਵਿੱਚ ਕੀ ਹੈ?' };
export const sampleFor = (lang) => SAMPLES[lang.split('-')[0]] || SAMPLES.en;
export const ENGINE_NAMES = { device: 'Device voice', google: 'Google', chatterbox: 'Chatterbox' };
export const voiceSettings = () => api('/settings/tts');

const SILENT = 'data:audio/wav;base64,UklGRiQAAABXQVZFZm10IBAAAAABAAEAQB8AAIA+AAACABAAZGF0YQAAAAA=';

/** One <audio> element reused for every reply: phones only allow playback on an element a tap has already started. */
export function makePlayer() {
  const el = new Audio(); let url = null;
  const free = () => { if (url) { URL.revokeObjectURL(url); url = null; } };
  return {
    unlock() { try { el.src = SILENT; el.play().catch(() => {}); } catch { /* not supported */ } },
    play(blob) { return new Promise((resolve, reject) => { free(); url = URL.createObjectURL(blob); el.onended = resolve; el.onerror = () => reject(new Error('The browser could not play this audio.')); el.src = url; el.play().catch(reject); }); },
    stop() { try { el.pause(); } catch { /* ignore */ } el.onended = null; free(); },
    say(text, language, engine) { return apiBlob('/speak', { text, language, ...(engine ? { engine } : {}) }); },
  };
}
