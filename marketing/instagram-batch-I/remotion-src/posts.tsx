import React from 'react';
import { AbsoluteFill } from 'remotion';
import { C, Logo } from './ui';
import { BODY, FONT } from './fonts';

/* Instagram posts (1080 x 1350, the 4:5 feed size). Same brand as the reels: green and ink, the म bubble, Hindi first.
   Every name, number and shop on a post is an example (उदाहरण). Munshi says it is an AI. */
export const PW = 1080, PH = 1350;
const CREAM = '#F4EFE3';

const Frame: React.FC<{ dark?: boolean; n?: number; total?: number; children: React.ReactNode; bare?: boolean }> = ({ dark, n, total, children, bare }) => (
  <AbsoluteFill style={{ background: dark ? `radial-gradient(1000px 800px at 12% -6%, #17503F 0%, ${C.ink} 62%)` : CREAM, fontFamily: BODY }}>
    <AbsoluteFill style={{ background: dark ? 'radial-gradient(640px 520px at 100% 100%, rgba(31,163,122,.30), transparent 70%)' : 'radial-gradient(760px 560px at 100% 0%, rgba(31,163,122,.20), transparent 70%)' }} />
    {bare ? null : <div style={{ position: 'absolute', left: 70, right: 70, top: 56, display: 'flex', alignItems: 'center', justifyContent: 'space-between' }}>
      <div style={{ display: 'flex', alignItems: 'center', gap: 16 }}><Logo size={62} /><span style={{ fontFamily: FONT, fontWeight: 700, fontSize: 46, color: dark ? '#fff' : C.ink, letterSpacing: -0.5 }}>Munshi</span></div>
      {n && total ? <span style={{ fontFamily: BODY, fontWeight: 700, fontSize: 30, color: dark ? '#9DB3AC' : C.muted }}>{n} / {total}</span> : null}
    </div>}
    {children}
    {n && total && n < total ? <div style={{ position: 'absolute', right: 70, bottom: 56, fontFamily: BODY, fontWeight: 700, fontSize: 32, color: dark ? C.mint : C.green }}>स्वाइप करें →</div> : null}
  </AbsoluteFill>
);
const Body: React.FC<{ children: React.ReactNode; top?: number; center?: boolean }> = ({ children, top = 210, center }) => (
  <div style={{ position: 'absolute', left: 80, right: 80, top, bottom: 150, display: 'flex', flexDirection: 'column', justifyContent: center ? 'center' : 'flex-start', gap: 34 }}>{children}</div>
);
const H: React.FC<{ children: React.ReactNode; size?: number; dark?: boolean }> = ({ children, size = 96, dark }) => <div style={{ fontFamily: FONT, fontWeight: 800, fontSize: size, lineHeight: 1.16, color: dark ? '#fff' : C.ink, letterSpacing: -1 }}>{children}</div>;
const G: React.FC<{ children: React.ReactNode; dark?: boolean }> = ({ children, dark }) => <span style={{ color: dark ? C.mint : C.green }}>{children}</span>;
const P: React.FC<{ children: React.ReactNode; dark?: boolean; size?: number }> = ({ children, dark, size = 46 }) => <div style={{ fontFamily: BODY, fontWeight: 600, fontSize: size, lineHeight: 1.42, color: dark ? '#D5E4DE' : '#2B3B36' }}>{children}</div>;
const Ex: React.FC<{ dark?: boolean }> = ({ dark }) => <div style={{ position: 'absolute', right: 70, top: 130, background: 'rgba(255,176,32,.18)', border: '2px solid #FFB020', color: dark ? '#FFD27A' : '#8A5A00', fontFamily: BODY, fontWeight: 700, fontSize: 30, padding: '8px 24px', borderRadius: 999 }}>उदाहरण</div>;
const Chip: React.FC<{ children: React.ReactNode; tone?: 'green' | 'amber' | 'gray' | 'solid' }> = ({ children, tone = 'green' }) => {
  const m = { green: ['#DDF3EA', '#07573F'], amber: [C.warnSoft, C.warn], gray: ['#E8ECEA', C.muted], solid: [C.green, '#fff'] }[tone];
  return <span style={{ background: m[0], color: m[1], borderRadius: 999, padding: '10px 26px', fontSize: 34, fontWeight: 700, fontFamily: BODY, whiteSpace: 'nowrap' }}>{children}</span>;
};
const Card: React.FC<{ children: React.ReactNode; accent?: string }> = ({ children, accent }) => <div style={{ background: '#fff', borderRadius: 36, border: `3px solid ${accent || C.line}`, padding: '34px 38px', boxShadow: '0 14px 40px rgba(15,31,27,.10)' }}>{children}</div>;
const Bub: React.FC<{ who: 'me' | 'them'; children: React.ReactNode }> = ({ who, children }) => (
  <div style={{ alignSelf: who === 'me' ? 'flex-end' : 'flex-start', maxWidth: 820, padding: '26px 34px', borderRadius: 40, borderBottomRightRadius: who === 'me' ? 8 : 40, borderBottomLeftRadius: who === 'them' ? 8 : 40, background: who === 'me' ? C.green : '#fff', color: who === 'me' ? '#fff' : C.ink, fontSize: 44, fontWeight: 700, lineHeight: 1.35, boxShadow: '0 6px 22px rgba(15,31,27,.14)' }}>{children}</div>
);
const Step: React.FC<{ n: number; title: React.ReactNode; body: React.ReactNode; extra?: React.ReactNode; of: number; total: number; ex?: boolean }> = ({ n, title, body, extra, of, total, ex }) => (
  <Frame n={of} total={total}>{ex ? <Ex /> : null}<Body top={170} center>
    <div style={{ fontFamily: FONT, fontWeight: 800, fontSize: 250, lineHeight: 0.9, color: C.green, opacity: 0.9 }}>{n}</div>
    <H size={86}>{title}</H><P>{body}</P>{extra}
  </Body></Frame>
);
const CTA: React.FC<{ line: React.ReactNode; sub: string; n: number; total: number }> = ({ line, sub, n, total }) => (
  <Frame dark n={n} total={total}><Body center>
    <div style={{ display: 'flex', justifyContent: 'center' }}><Logo size={170} /></div>
    <div style={{ textAlign: 'center' }}><H size={88} dark>{line}</H></div>
    <div style={{ display: 'flex', justifyContent: 'center' }}><div style={{ background: C.green2, color: '#fff', fontFamily: FONT, fontWeight: 800, fontSize: 56, padding: '26px 54px', borderRadius: 999, boxShadow: '0 12px 40px rgba(31,163,122,.45)' }}>Comment करें: <span style={{ color: '#FFF3C4' }}>MUNSHI</span></div></div>
    <div style={{ textAlign: 'center' }}><P dark>{sub}</P></div>
    <div style={{ textAlign: 'center', fontFamily: BODY, fontWeight: 600, fontSize: 30, color: '#9DB3AC' }}>Munshi AI असिस्टेंट है, और कॉलर को बताता है।</div>
  </Body></Frame>
);

/* ---------- P1: carousel, how it works in 4 steps ---------- */
const T1 = 6;
export const P1_1: React.FC = () => <Frame dark n={1} total={T1}><Body center>
  <H size={112} dark>ग्राहक की call <G dark>छूटी।</G></H>
  <H size={112} dark>आगे क्या होता है?</H>
  <P dark size={50}>4 कदम में देखिए, एक उदाहरण के साथ।</P></Body></Frame>;
export const P1_2: React.FC = () => <Step of={2} total={T1} n={1} title={<>पहले <G>आपका</G> फ़ोन बजता है</>} body="20 सेकंड तक उठाने का मौका आपके पास है। आपने उठा लिया, तो बात आप ही करते हैं।" extra={<Card accent={C.green}><div style={{ fontFamily: FONT, fontSize: 52, fontWeight: 800, color: C.ink }}>✓ आपने उठाया</div><P size={38}>Munshi बीच में नहीं आता।</P></Card>} />;
export const P1_3: React.FC = () => <Step ex of={3} total={T1} n={2} title={<>नहीं उठा? <G>Munshi</G> उठाता है</>} body="ग्राहक को शुरू में ही बता देता है कि वह AI सहायक है।" extra={<div style={{ display: 'flex', flexDirection: 'column', gap: 22 }}><Bub who="me">नमस्ते, मैं Munshi हूँ, रमेश जी का AI सहायक। बताइए?</Bub><Bub who="them">आज दुकान कब तक खुली है?</Bub></div>} />;
export const P1_4: React.FC = () => <Step of={4} total={T1} n={3} title={<>सिर्फ़ वही, जो <G>आपने बताया</G></>} body="आपके board का रेट, समय और पता। बाक़ी हर सवाल पर: “रमेश जी call करेंगे।”" extra={<div style={{ display: 'flex', gap: 14, flexWrap: 'wrap' }}><Chip>रेट</Chip><Chip>समय</Chip><Chip>पता</Chip><Chip tone="gray">बाक़ी: मालिक call करेंगे</Chip></div>} />;
export const P1_5: React.FC = () => <Step ex of={5} total={T1} n={4} title={<>आपको मिलती है <G>एक लाइन</G></>} body="कौन था, क्या चाहिए, आगे क्या करना है। एक टैप में call back या WhatsApp।" extra={<Card><div style={{ display: 'flex', gap: 12 }}><Chip tone="amber">Needs you</Chip><Chip tone="gray">Phone call</Chip></div><div style={{ fontSize: 42, fontWeight: 700, color: C.ink, margin: '18px 0 20px', lineHeight: 1.3 }}>सुनील को कल सुबह 10 kg आटा चाहिए।</div><div style={{ display: 'flex', gap: 12 }}><Chip tone="solid">Call back</Chip><Chip>WhatsApp</Chip></div></Card>} />;
export const P1_6: React.FC = () => <CTA n={6} total={T1} line={<>14 दिन <G dark>मुफ़्त</G> आज़माएँ</>} sub="कमेंट करें, हम आपसे संपर्क करेंगे।" />;

/* ---------- P2: brand poster ---------- */
export const P2: React.FC = () => <Frame dark bare>
  <AbsoluteFill style={{ alignItems: 'center', justifyContent: 'center' }}>
    {[0, 1, 2].map((i) => <div key={i} style={{ position: 'absolute', top: 120 + i * 0, width: 360 + i * 230, height: 360 + i * 230, borderRadius: '50%', border: `5px solid rgba(142,240,198,${0.34 - i * 0.1})`, transform: 'translateY(-130px)' }} />)}
    <div style={{ position: 'absolute', top: 190 }}><Logo size={300} /></div>
    <div style={{ position: 'absolute', top: 620, left: 70, right: 70, textAlign: 'center' }}>
      <div style={{ fontFamily: FONT, fontWeight: 800, fontSize: 150, color: '#fff', lineHeight: 1.1, letterSpacing: -2 }}>आप busy हैं?</div>
      <div style={{ fontFamily: FONT, fontWeight: 800, fontSize: 150, color: C.mint, lineHeight: 1.1, letterSpacing: -2 }}>Munshi है ना।</div>
    </div>
    <div style={{ position: 'absolute', bottom: 150, left: 70, right: 70, textAlign: 'center' }}><P dark size={54}>पहले आपका फ़ोन। फिर Munshi।</P></div>
    <div style={{ position: 'absolute', bottom: 70, left: 70, right: 70, textAlign: 'center', fontFamily: BODY, fontWeight: 600, fontSize: 30, color: '#9DB3AC' }}>Munshi AI असिस्टेंट है, और कॉलर को बताता है।</div>
  </AbsoluteFill></Frame>;

/* ---------- P3: carousel, which call is worth your time ---------- */
const T3 = 5;
export const P3_1: React.FC = () => <Frame n={1} total={T3}><Body center>
  <H size={108}>आज <G>6 call</G> आईं।</H><H size={108}>कौन सी आपके काम की?</H>
  <P size={50}>Munshi हर call को तीन में बाँटता है। एक उदाहरण देखिए।</P></Body></Frame>;
const Kind: React.FC<{ n: number; tag: string; tone: 'amber' | 'green' | 'gray'; title: React.ReactNode; line: string; chips?: string[]; note: string }> = ({ n, tag, tone, title, line, chips = [], note }) => (
  <Frame n={n} total={T3}><Ex /><Body top={190} center>
    <div><Chip tone={tone}>{tag}</Chip></div><H size={92}>{title}</H>
    <Card accent={tone === 'amber' ? C.warn : tone === 'green' ? C.green : undefined}><div style={{ fontSize: 46, fontWeight: 700, color: C.ink, lineHeight: 1.32 }}>{line}</div>
      {chips.length ? <div style={{ display: 'flex', gap: 14, marginTop: 24 }}>{chips.map((c, i) => <Chip key={c} tone={i === 0 ? 'solid' : 'green'}>{c}</Chip>)}</div> : null}</Card>
    <P>{note}</P></Body></Frame>
);
export const P3_2: React.FC = () => <Kind n={2} tag="Needs you" tone="amber" title={<>जिसे आपका <G>जवाब</G> चाहिए</>} line="सुनील: 10 kg आटा, कल सुबह घर पर डिलीवरी।" chips={['Call back', 'WhatsApp']} note="ऑर्डर, सवाल जिसका जवाब सिर्फ़ आप दे सकते हैं, शिकायत: ये सबसे ऊपर दिखती हैं।" />;
export const P3_3: React.FC = () => <Kind n={3} tag="Good to know" tone="green" title={<>जिसका जवाब <G>मिल चुका</G></>} line="नए ग्राहक ने दुकान का समय पूछा। बता दिया गया।" note="आपके करने के लिए कुछ नहीं। बस पता रहे कि क्या हुआ।" />;
export const P3_4: React.FC = () => <Kind n={4} tag="Not worth it" tone="gray" title={<>जो आपका <G>समय</G> नहीं लेगी</>} line="Loan का ऑफ़र। अलग रख दिया गया।" note="Sales, ग़लत नंबर, खाली call: ये आपका ध्यान नहीं माँगतीं। चाहें तो पढ़ सकते हैं।" />;
export const P3_5: React.FC = () => <CTA n={5} total={T3} line={<>सिर्फ़ <G dark>काम की</G> call पर ध्यान दीजिए</>} sub="कमेंट करें, हम आपसे संपर्क करेंगे।" />;

/* ---------- P4: carousel, four honest questions ---------- */
const T4 = 6;
export const P4_1: React.FC = () => <Frame dark n={1} total={T4}><Body center>
  <H size={104} dark>4 सवाल, जो हर <G dark>दुकानदार</G> पूछता है</H>
  <P dark size={50}>सीधे जवाब, बिना बढ़ा-चढ़ाकर।</P></Body></Frame>;
const QA: React.FC<{ n: number; q: string; a: React.ReactNode; tag?: string }> = ({ n, q, a }) => (
  <Frame n={n} total={T4}><Body top={170} center>
    <div style={{ fontFamily: FONT, fontWeight: 800, fontSize: 52, color: C.green }}>सवाल {n - 1}</div>
    <H size={90}>{q}</H>
    <div style={{ height: 6, background: C.green, width: 120, borderRadius: 3 }} />
    <div style={{ fontFamily: BODY, fontWeight: 700, fontSize: 52, lineHeight: 1.42, color: C.ink }}>{a}</div></Body></Frame>
);
export const P4_2: React.FC = () => <QA n={2} q="क्या ग्राहक को पता चलेगा कि ये AI है?" a={<><G>हाँ।</G> Munshi हर call की शुरुआत में बताता है: “मैं आपकी दुकान का AI सहायक हूँ।”</>} />;
export const P4_3: React.FC = () => <QA n={3} q="ग़लत रेट बोल दिया तो?" a={<>Munshi सिर्फ़ वही रेट बोलता है जो आपने <G>board में डाला</G>। जो नहीं पता, वहाँ: “रमेश जी call करेंगे।” रेट पुराना हो जाए तो वो उसे नहीं बोलता।</>} />;
export const P4_4: React.FC = () => <QA n={4} q="शोर वाली दुकान में समझेगा?" a={<>कोशिश करता है। समझ न आए, तो <G>अंदाज़ा नहीं लगाता</G>, दोबारा पूछता है। हिंदी, Hinglish और English में।</>} />;
export const P4_5: React.FC = () => <QA n={5} q="मेरे खास लोगों का क्या?" a={<>जिन नंबरों को आप <G>“हमेशा रिंग”</G> में रखें, उनसे Munshi बात नहीं करता। फ़ोन बुक से एक साथ जोड़ सकते हैं।</>} />;
export const P4_6: React.FC = () => <CTA n={6} total={T4} line={<>और कोई सवाल? <G dark>पूछिए।</G></>} sub="कमेंट करें, हम आपसे संपर्क करेंगे।" />;

/* ---------- P5: photo to rates ---------- */
export const P5: React.FC = () => <Frame><Ex />
  <Body top={200}>
    <H size={104}>फ़ोटो खींचिए। <G>रेट तैयार।</G></H>
    <div style={{ display: 'flex', alignItems: 'center', gap: 26 }}>
      <div style={{ flex: 1, background: '#FFFDF4', border: '3px solid #E3DCC2', borderRadius: 20, padding: '30px 30px 34px', transform: 'rotate(-3deg)', boxShadow: '0 16px 40px rgba(60,50,20,.18)' }}>
        <div style={{ fontFamily: BODY, fontWeight: 700, fontSize: 28, color: '#8C8466', marginBottom: 14 }}>📷 रेट लिस्ट की फ़ोटो</div>
        {[['आटा', '42'], ['चीनी', '46'], ['तूर दाल', '165'], ['सरसों तेल', '150']].map(([a, b]) => <div key={a} style={{ display: 'flex', justifyContent: 'space-between', fontFamily: "'Noto Sans Devanagari', sans-serif", fontWeight: 600, fontSize: 40, color: '#4B4630', lineHeight: 1.65, borderBottom: '2px dashed #C9C1A3' }}><span>{a}</span><span>{b}</span></div>)}
      </div>
      <div style={{ fontFamily: FONT, fontWeight: 800, fontSize: 90, color: C.green }}>→</div>
      <div style={{ flex: 1, background: '#fff', border: `3px solid ${C.green}`, borderRadius: 28, padding: '30px 30px 26px', boxShadow: '0 16px 40px rgba(11,122,91,.2)' }}>
        <div style={{ fontFamily: BODY, fontWeight: 700, fontSize: 28, color: C.green, marginBottom: 14 }}>✓ Munshi का board</div>
        {[['आटा', '₹42/kg'], ['चीनी', '₹46/kg'], ['तूर दाल', '₹165/kg'], ['सरसों तेल', '₹150/ltr']].map(([a, b]) => <div key={a} style={{ display: 'flex', justifyContent: 'space-between', fontFamily: BODY, fontWeight: 700, fontSize: 36, color: C.ink, lineHeight: 1.7, borderBottom: `2px solid ${C.line}` }}><span>{a}</span><span style={{ color: C.green }}>{b}</span></div>)}
      </div>
    </div>
    <P>आप एक बार देख लें, फिर सेव। उसके बाद Munshi सिर्फ़ यही रेट बताता है। रेट बदला? बोल दीजिए: “तूर दाल 170 हो गई।”</P>
  </Body></Frame>;

export const POSTS: [string, React.FC][] = [
  ['P1-1', P1_1], ['P1-2', P1_2], ['P1-3', P1_3], ['P1-4', P1_4], ['P1-5', P1_5], ['P1-6', P1_6],
  ['P2', P2],
  ['P3-1', P3_1], ['P3-2', P3_2], ['P3-3', P3_3], ['P3-4', P3_4], ['P3-5', P3_5],
  ['P4-1', P4_1], ['P4-2', P4_2], ['P4-3', P4_3], ['P4-4', P4_4], ['P4-5', P4_5], ['P4-6', P4_6],
  ['P5', P5],
];
