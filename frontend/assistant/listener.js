// Records one thing the caller says: starts on the first words, stops after a pause. Works on phones (MediaRecorder).
const pickMime = () => ['audio/webm;codecs=opus', 'audio/webm', 'audio/mp4', 'audio/ogg;codecs=opus'].find((m) => window.MediaRecorder && MediaRecorder.isTypeSupported(m)) || '';
export const canRecord = !!(navigator.mediaDevices && navigator.mediaDevices.getUserMedia && window.MediaRecorder);

export function makeListener() {
  let stream = null; let ctx = null; let rec = null; let cancelled = false;
  return {
    /** Resolves {blob, seconds}, or null if nothing was said or it was cancelled. */
    async listen({ onLevel = () => {}, silenceMs = 1300, waitMs = 9000, maxMs = 30000 } = {}) {
      stream ||= await navigator.mediaDevices.getUserMedia({ audio: { echoCancellation: true, noiseSuppression: true } });
      ctx ||= new (window.AudioContext || window.webkitAudioContext)();
      if (ctx.state === 'suspended') await ctx.resume();
      cancelled = false;
      return new Promise((resolve) => {
        const an = ctx.createAnalyser(); an.fftSize = 1024; const src = ctx.createMediaStreamSource(stream); src.connect(an);
        const mime = pickMime(); const chunks = []; rec = new MediaRecorder(stream, mime ? { mimeType: mime } : undefined);
        const buf = new Float32Array(an.fftSize); const t0 = performance.now(); let heard = false; let last = t0; let floor = 0.01;  // floor: how loud the room is when nobody speaks
        rec.ondataavailable = (e) => e.data?.size && chunks.push(e.data);
        rec.onstop = () => { clearInterval(timer); src.disconnect(); onLevel(0); resolve(!cancelled && heard ? { blob: new Blob(chunks, { type: rec.mimeType || mime || 'audio/webm' }), seconds: (last - t0) / 1000 + 1 } : null); };
        const timer = setInterval(() => {
          an.getFloatTimeDomainData(buf); let sum = 0; for (let i = 0; i < buf.length; i++) sum += buf[i] * buf[i];
          const now = performance.now(); const rms = Math.sqrt(sum / buf.length); onLevel(rms * 7);
          if (rms < floor * 2 + 0.01) floor = 0.9 * floor + 0.1 * rms;  // learn the background hum (never from speech), so a noisy shop still ends turns
          if (rms > Math.max(0.02, floor * 2.5 + 0.008)) { heard = true; last = now; }
          if ((heard && now - last > silenceMs) || (!heard && now - t0 > waitMs) || now - t0 > maxMs) { if (rec.state === 'recording') rec.stop(); }
        }, 100);
        rec.start();
      });
    },
    cancel() { cancelled = true; if (rec && rec.state === 'recording') { try { rec.stop(); } catch { /* ignore */ } } },
    close() { this.cancel(); stream?.getTracks().forEach((t) => t.stop()); ctx?.close().catch(() => {}); stream = null; ctx = null; },
  };
}
