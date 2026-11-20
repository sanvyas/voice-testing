import React from 'react';
import { AbsoluteFill, Sequence, interpolate, spring, useCurrentFrame, useVideoConfig } from 'remotion';
import { AppTop, Badge, Bed, Bg, Bubble, C, EndCard, Hi, Phone, Pop, Sfx } from './ui';
import { BODY, FONT } from './fonts';
import { Card, Col, Foot, Handset, KW, Light, Tag } from './reels5';

/* Set I: built from the buyer panel (founder/panel/results.md). Each reel answers one reason people said no:
   I1 trust ("a machine may say a wrong price")        -> Munshi's firm rules, struck-through wrong answers
   I2 habit ("I pick up every call myself")             -> your phone rings first, Munshi only after 20 seconds
   I3 relationship-driven owners (0 of 4 bought)       -> your own people stay yours (phone book, always ring)
   I4 noise and language fear                          -> Hindi, Hinglish or English, and "say it again" when unclear
   Every name, time, shop and number on screen is an example (उदाहरण). */

const Ex: React.FC<{ dark?: boolean }> = ({ dark = false }) => <Tag dark={dark}>उदाहरण</Tag>;
const Head: React.FC<{ children: React.ReactNode; top?: number; size?: number; dark?: boolean }> = ({ children, top = 170, size = 80, dark = true }) => (
  <Pop style={{ position: 'absolute', left: 80, right: 80, top }}><div style={{ fontFamily: FONT, fontSize: size, fontWeight: 800, color: dark ? '#fff' : C.ink, lineHeight: 1.2 }}>{children}</div></Pop>
);
const Label: React.FC<{ children: React.ReactNode; color?: string; top: number; delay?: number }> = ({ children, color = C.muted, top, delay = 0 }) => (
  <Pop delay={delay} style={{ position: 'absolute', left: 80, top }}><div style={{ fontFamily: BODY, fontSize: 36, fontWeight: 700, color, letterSpacing: 0.2 }}>{children}</div></Pop>
);

/** A chat bubble sized for a full-screen reel (the phone-screen Bubble is too small there). */
const Big: React.FC<{ who: 'me' | 'them'; children: React.ReactNode; delay: number; maxWidth?: number }> = ({ who, children, delay, maxWidth = 800 }) => (
  <Pop delay={delay} from="scale" style={{ alignSelf: who === 'me' ? 'flex-end' : 'flex-start', transformOrigin: who === 'me' ? 'right bottom' : 'left bottom' }}>
    <div style={{ maxWidth, padding: '30px 38px', borderRadius: 44, borderBottomRightRadius: who === 'me' ? 10 : 44, borderBottomLeftRadius: who === 'them' ? 10 : 44, background: who === 'me' ? C.green : '#fff', color: who === 'me' ? '#fff' : C.ink, fontFamily: BODY, fontSize: 54, lineHeight: 1.35, fontWeight: 700, boxShadow: '0 8px 28px rgba(15,31,27,.16)' }}>{children}</div>
  </Pop>
);

/* ================= I1: Munshi's firm rules ================= */
const RULES = [
  { n: 1, title: 'अंदाज़ा नहीं', q: 'आटा कितने का है?', wrong: 'शायद ₹40 का होगा।', right: 'आपके board के हिसाब से ₹42 किलो।' },
  { n: 2, title: 'वादा नहीं', q: 'थोड़ा discount दे दो।', wrong: 'हाँ-हाँ, मिल जाएगा।', right: 'छूट का फ़ैसला रमेश जी करते हैं। वो आपको call करेंगे।' },
  { n: 3, title: 'नाटक नहीं', q: 'आप कौन बोल रहे हैं?', wrong: 'जी, मैं रमेश बोल रहा हूँ।', right: 'मैं रमेश जी का AI सहायक हूँ।' },
  { n: 4, title: 'OTP नहीं', q: 'कार्ड से पेमेंट कर दूँ? नंबर बताऊँ?', wrong: 'हाँ, नंबर बताइए।', right: 'कार्ड नंबर या OTP फ़ोन पर मत बताइए।' },
];
const RuleBeat: React.FC<(typeof RULES)[number]> = ({ n, title, q, wrong, right }) => {
  const f = useCurrentFrame();
  const strike = interpolate(f, [44, 62], [0, 100], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
  return <AbsoluteFill>
    <Light />
    <Pop style={{ position: 'absolute', left: 80, top: 150 }}><div style={{ display: 'inline-block', background: C.green, color: '#fff', fontFamily: FONT, fontWeight: 800, fontSize: 40, padding: '10px 30px', borderRadius: 999 }}>नियम {n}</div></Pop>
    <Pop delay={4} style={{ position: 'absolute', left: 80, right: 80, top: 250 }}><div style={{ fontFamily: FONT, fontWeight: 800, fontSize: 112, color: C.ink, lineHeight: 1.1 }}>{title}</div></Pop>
    <Label top={520} delay={10}>ग्राहक पूछता है</Label>
    <Pop delay={12} style={{ position: 'absolute', left: 80, right: 80, top: 580 }}><Card style={{ borderRadius: 36, padding: '30px 38px' }}><div style={{ fontFamily: BODY, fontSize: 54, fontWeight: 700, color: C.ink, lineHeight: 1.3 }}>“{q}”</div></Card></Pop>
    <Label top={830} color={C.red} delay={30}>✗ ये नहीं बोलेगा</Label>
    <Pop delay={32} style={{ position: 'absolute', left: 80, right: 80, top: 890 }}>
      <div style={{ position: 'relative', background: '#FDECEC', border: `2px solid #F3C2C2`, borderRadius: 36, padding: '30px 38px' }}>
        <div style={{ fontFamily: BODY, fontSize: 54, fontWeight: 700, color: '#8a4a4a', lineHeight: 1.3 }}>“{wrong}”</div>
        <div style={{ position: 'absolute', left: 30, top: '50%', height: 9, borderRadius: 5, background: C.red, width: `calc(${strike}% - 60px)` }} />
      </div></Pop>
    <Label top={1190} color={C.green} delay={64}>✓ Munshi ये बोलता है</Label>
    <Pop delay={66} from="scale" style={{ position: 'absolute', left: 80, right: 80, top: 1250, transformOrigin: 'left top' }}>
      <div style={{ background: C.green, borderRadius: 36, padding: '34px 40px', boxShadow: '0 22px 60px rgba(11,122,91,.38)' }}><div style={{ fontFamily: BODY, fontSize: 54, fontWeight: 700, color: '#fff', lineHeight: 1.32 }}>“{right}”</div></div></Pop>
    <Ex />
    <Sfx at={4} file="pop.wav" /><Sfx at={44} file="whoosh.wav" volume={0.5} /><Sfx at={66} file="ding.wav" volume={0.55} />
  </AbsoluteFill>;
};
export const I1: React.FC = () => (
  <AbsoluteFill>
    <Sequence from={0} durationInFrames={120}><Bg />
      <KW dark top={500} size={118} step={9} words={[['एक', false], ['ग़लत', true], ['रेट।', false], ['एक', false], ['झूठा', true], ['वादा।', false], ['ग्राहक', false], ['गया।', true]]} />
      <Foot top={1500}>इसीलिए Munshi के कुछ नियम पक्के हैं।</Foot></Sequence>
    {RULES.map((r, i) => <Sequence key={r.n} from={120 + i * 150} durationInFrames={150}><RuleBeat {...r} /></Sequence>)}
    <Sequence from={720} durationInFrames={120}><Bg />
      <KW dark top={470} size={104} step={7} words={[['आपने', false], ['जो', false], ['बताया,', false], ['सिर्फ़', false], ['वही।', true], ['बाक़ी', false], ['सब', false], ['पर:', false], ['“मालिक', true], ['call', true], ['करेंगे।”', true]]} />
      <Foot top={1500}>Munshi AI है और कॉलर को बताता है।</Foot></Sequence>
    <Sequence from={840}><Bg /><EndCard line="भरोसा पहले।" /></Sequence>
    <Bed /><Sfx at={0} file="pop.wav" /><Sfx at={60} file="pop.wav" /><Sfx at={720} file="pop.wav" /><Sfx at={840} file="pop.wav" />
  </AbsoluteFill>
);

/* ================= I2: your phone rings first ================= */
const RingTimer: React.FC<{ seconds: number; frames: number; hold?: boolean }> = ({ seconds, frames, hold }) => {
  const f = useCurrentFrame();
  const sec = interpolate(f, [0, frames], [0, seconds], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
  const R = 230, circ = 2 * Math.PI * R; const shake = hold ? 0 : Math.sin(f * 1.7) * 6;
  return <div style={{ position: 'absolute', left: 0, right: 0, top: 330, height: 640, display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
    <svg width={560} height={560} viewBox="0 0 560 560" style={{ position: 'absolute' }}>
      <circle cx={280} cy={280} r={R} fill="none" stroke="#DDD8C6" strokeWidth={22} />
      <circle cx={280} cy={280} r={R} fill="none" stroke={C.green2} strokeWidth={22} strokeLinecap="round" strokeDasharray={circ} strokeDashoffset={circ * (1 - sec / 20)} transform="rotate(-90 280 280)" />
    </svg>
    <div style={{ width: 250, height: 250, borderRadius: 125, background: C.green, display: 'grid', placeItems: 'center', transform: `rotate(${shake}deg)`, boxShadow: '0 24px 70px rgba(11,122,91,.45)' }}><Handset size={140} /></div>
    <div style={{ position: 'absolute', top: 540, fontFamily: FONT, fontSize: 96, fontWeight: 800, color: C.ink }}>{Math.floor(sec)}<span style={{ fontSize: 46, color: C.muted, fontWeight: 700 }}> सेकंड</span></div>
  </div>;
};
const Plain: React.FC<{ children: React.ReactNode; top: number; size?: number; color?: string; delay?: number; align?: 'left' | 'center' }> = ({ children, top, size = 62, color = C.ink, delay = 0, align = 'left' }) => (
  <Pop delay={delay} style={{ position: 'absolute', left: 80, right: 80, top, textAlign: align }}><div style={{ fontFamily: FONT, fontSize: size, fontWeight: 800, color, lineHeight: 1.25 }}>{children}</div></Pop>
);
export const I2: React.FC = () => (
  <AbsoluteFill>
    <Sequence from={0} durationInFrames={120}><Bg />
      <KW dark top={470} size={112} step={7} words={[['आप', false], ['हर', false], ['call', true], ['ख़ुद', false], ['उठाते', false], ['हैं?', false]]} />
      <Pop delay={62} style={{ position: 'absolute', left: 80, right: 80, top: 1100 }}><div style={{ fontFamily: FONT, fontSize: 64, fontWeight: 800, color: '#E3EFEA', lineHeight: 1.3 }}>बहुत अच्छा।<br /><Hi color="#FFD27A">Munshi आपकी जगह नहीं लेता।</Hi></div></Pop></Sequence>
    <Sequence from={120} durationInFrames={90}><Light />
      <Head dark={false} top={170} size={78}>पहले <span style={{ color: C.green }}>आपका</span> फ़ोन बजता है</Head>
      <RingTimer seconds={6} frames={60} hold />
      <Pop delay={62} from="scale" style={{ position: 'absolute', left: 80, right: 80, top: 1160 }}><div style={{ background: C.green, color: '#fff', borderRadius: 34, padding: '30px 38px', fontFamily: FONT, fontWeight: 800, fontSize: 56, lineHeight: 1.25 }}>✓ आपने उठाया।<br /><span style={{ fontSize: 44, fontFamily: BODY, fontWeight: 600, color: '#D9F5EA' }}>बात आप करेंगे। Munshi बीच में नहीं आता।</span></div></Pop>
      <Sfx at={0} file="ring.wav" volume={0.6} /><Sfx at={62} file="ding.wav" /></Sequence>
    <Sequence from={210} durationInFrames={300}><Light />
      <Head dark={false} top={170} size={78}>इस बार आप <span style={{ color: C.green }}>ग्राहक के साथ</span> हैं…</Head>
      <Sequence from={0} durationInFrames={170} layout="none"><RingTimer seconds={20} frames={150} /></Sequence>
      <Sequence from={0} durationInFrames={170} layout="none"><Plain top={1230} size={52} color={C.muted} delay={40}>20 सेकंड तक कोई नहीं उठाता…</Plain></Sequence>
      <Sequence from={170} durationInFrames={130} layout="none"><AbsoluteFill><Light />
        <Head dark={false} top={170} size={78}>तब <span style={{ color: C.green }}>Munshi</span> उठाता है</Head>
        <div style={{ position: 'absolute', left: 60, right: 60, top: 470, display: 'flex', flexDirection: 'column', gap: 36 }}>
          <Big who="me" delay={6} maxWidth={900}>नमस्ते, मैं Munshi हूँ, रमेश जी का AI सहायक। बताइए?</Big>
          <Big who="them" delay={42} maxWidth={820}>आज दुकान कितने बजे तक खुली है?</Big>
          <Big who="me" delay={78} maxWidth={860}>रात 9 बजे तक। और कुछ पूछना है?</Big>
        </div><Ex />
        <Sfx at={6} file="pop.wav" /><Sfx at={42} file="pop.wav" /><Sfx at={78} file="pop.wav" /></AbsoluteFill></Sequence>
      <Sfx at={0} file="ring.wav" volume={0.6} /><Sfx at={40} file="ring.wav" volume={0.5} /><Sfx at={150} file="ding.wav" /></Sequence>
    <Sequence from={510} durationInFrames={150}><Bg />
      <Head top={170} size={80}>आपके पास आई <Hi>एक लाइन।</Hi></Head>
      <Phone top={470}><AppTop title="अभी की calls" sub="Munshi" /><Col top={190}>
        <Pop delay={8}><Card><div style={{ display: 'flex', gap: 10 }}><Badge>Good to know</Badge><Badge>Phone call</Badge></div>
          <div style={{ fontSize: 34, fontWeight: 700, color: C.ink, marginTop: 16, lineHeight: 1.32 }}>नए ग्राहक ने दुकान का समय पूछा। बता दिया गया।</div></Card></Pop></Col></Phone>
      <Ex dark /></Sequence>
    <Sequence from={660}><Bg /><EndCard line="पहले आपका फ़ोन। फिर Munshi।" /></Sequence>
    <Bed /><Sfx at={0} file="pop.wav" /><Sfx at={520} file="ding.wav" /><Sfx at={660} file="pop.wav" />
  </AbsoluteFill>
);


/* ================= I3: your own people stay yours ================= */
const PEOPLE = [['माँ', 'M'], ['बड़े भैया', 'B'], ['विकास (पार्टनर)', 'V'], ['पुराना सप्लायर', 'S']] as const;
const Toggle: React.FC<{ on: boolean }> = ({ on }) => <div style={{ width: 150, height: 54, borderRadius: 27, background: on ? C.green : '#E3E9E6', color: on ? '#fff' : C.muted, fontFamily: BODY, fontWeight: 700, fontSize: 24, display: 'grid', placeItems: 'center', whiteSpace: 'nowrap' }}>{on ? '✓ हमेशा रिंग' : 'हमेशा रिंग'}</div>;
const PhoneBook: React.FC = () => {
  const f = useCurrentFrame();
  return <Phone top={470} bg={C.ground}>
    <AppTop title="संपर्क" sub="Munshi" />
    <div style={{ padding: '0 30px', display: 'flex', flexDirection: 'column', gap: 16 }}>
      <Pop delay={6}><div style={{ border: `3px solid ${C.green}`, background: '#F1F9F5', borderRadius: 24, padding: '20px 26px', fontFamily: BODY, fontSize: 32, fontWeight: 700, color: C.green, display: 'flex', alignItems: 'center', gap: 14 }}>
        <span style={{ fontSize: 40 }}>👥</span> फ़ोन बुक से जोड़ें</div></Pop>
      <Pop delay={30}><div style={{ fontFamily: BODY, fontSize: 26, fontWeight: 700, color: C.muted, marginTop: 8 }}>चुनें, कौन हमेशा आपके फ़ोन पर बजे</div></Pop>
      {PEOPLE.map(([name, ini], i) => <Pop key={name} delay={40 + i * 14}><Card style={{ borderRadius: 24, padding: '18px 22px', display: 'flex', alignItems: 'center', gap: 16 }}>
        <div style={{ width: 62, height: 62, borderRadius: 31, background: C.ink, color: C.mint, fontFamily: FONT, fontWeight: 800, fontSize: 30, display: 'grid', placeItems: 'center' }}>{ini}</div>
        <div style={{ flex: 1, fontFamily: BODY, fontSize: 32, fontWeight: 700, color: C.ink }}>{name}</div>
        <Toggle on={f > 120 + i * 22} /></Card></Pop>)}
    </div></Phone>;
};
const CallCard: React.FC<{ who: string; sub: string; verdict: string; good?: boolean; delay: number }> = ({ who, sub, verdict, good, delay }) => (
  <Pop delay={delay} from="left"><div style={{ background: '#fff', border: `3px solid ${good ? C.green : C.line}`, borderRadius: 38, padding: '34px 40px', boxShadow: good ? '0 20px 60px rgba(11,122,91,.25)' : '0 6px 24px rgba(15,31,27,.10)' }}>
    <div style={{ display: 'flex', alignItems: 'center', gap: 22 }}><div style={{ width: 96, height: 96, borderRadius: 48, background: C.ink, display: 'grid', placeItems: 'center' }}><Handset size={52} color={C.mint} /></div>
      <div><div style={{ fontFamily: FONT, fontSize: 54, fontWeight: 800, color: C.ink }}>{who}</div><div style={{ fontFamily: BODY, fontSize: 32, color: C.muted, fontWeight: 600 }}>{sub}</div></div></div>
    <div style={{ marginTop: 22, background: good ? C.green : '#EEF4F1', color: good ? '#fff' : C.ink, borderRadius: 22, padding: '20px 26px', fontFamily: BODY, fontSize: 40, fontWeight: 700, lineHeight: 1.3 }}>{verdict}</div></div></Pop>
);
export const I3: React.FC = () => (
  <AbsoluteFill>
    <Sequence from={0} durationInFrames={120}><Bg />
      <KW dark top={470} size={112} step={6} words={[['माँ', true], ['की', false], ['call।', false], ['अनजान', true], ['नंबर', false], ['की', false], ['call।', false], ['एक', false], ['जैसी', false], ['नहीं।', true]]} /></Sequence>
    <Sequence from={120} durationInFrames={300}><Bg />
      <Head top={215} size={70}>फ़ोन बुक से चुनिए <Hi>अपने खास लोग</Hi></Head>
      <PhoneBook /><Ex dark />
      <Sfx at={6} file="pop.wav" />{PEOPLE.map((_, i) => <Sfx key={i} at={120 + i * 22} file="tick.wav" volume={0.5} />)}</Sequence>
    <Sequence from={420} durationInFrames={230}><Light />
      <Head dark={false} top={215} size={72}>फिर जब call आती है…</Head>
      <div style={{ position: 'absolute', left: 60, right: 60, top: 400, display: 'flex', flexDirection: 'column', gap: 44 }}>
        <CallCard who="माँ" sub="आपके खास लोग" verdict="सिर्फ़ आपका फ़ोन बजा। Munshi बात नहीं करेगा।" delay={14} />
        <CallCard who="नया नंबर" sub="+91 98xxxxx712" verdict="आप न उठा पाएँ, तो Munshi उठाएगा।" good delay={80} />
      </div><Ex />
      <Sfx at={14} file="ring.wav" volume={0.5} /><Sfx at={80} file="pop.wav" /><Sfx at={100} file="ding.wav" /></Sequence>
    <Sequence from={650} durationInFrames={160}><Bg />
      <KW dark top={470} size={110} step={7} words={[['आपके', false], ['अपने', false], ['लोग:', false], ['आप।', true], ['नए', false], ['ग्राहक:', false], ['Munshi।', true]]} />
      <Foot top={1500}>Munshi AI असिस्टेंट है, और कॉलर को बताता है।</Foot></Sequence>
    <Sequence from={810}><Bg /><EndCard line="आपके अपने, सिर्फ़ आपके।" /></Sequence>
    <Bed /><Sfx at={0} file="pop.wav" /><Sfx at={650} file="pop.wav" /><Sfx at={810} file="pop.wav" />
  </AbsoluteFill>
);

/* ================= I4: Hindi, Hinglish or English ================= */
const Wave: React.FC<{ noisy?: boolean }> = ({ noisy }) => {
  const f = useCurrentFrame();
  return <div style={{ display: 'flex', alignItems: 'center', gap: 8, height: 90 }}>{Array.from({ length: 22 }).map((_, i) => {
    const h = noisy ? 20 + Math.abs(Math.sin(f / 3 + i * 1.9) * 60) + (i % 3 === 0 ? 10 : 0) : 18 + Math.abs(Math.sin(f / 6 + i * 0.7)) * 40;
    return <div key={i} style={{ width: 10, height: h, borderRadius: 5, background: noisy ? C.warn : C.green2, opacity: noisy ? 0.85 : 0.7 }} />; })}</div>;
};
const LangRound: React.FC<{ chip: string; q: string; a: string; noisy?: boolean; dark?: boolean }> = ({ chip, q, a, noisy, dark }) => (
  <AbsoluteFill>
    {dark ? <Bg /> : <Light />}
    <Pop style={{ position: 'absolute', left: 80, top: 190 }}><div style={{ display: 'inline-block', background: noisy ? C.warnSoft : '#DDF3EA', color: noisy ? C.warn : '#07573F', fontFamily: FONT, fontWeight: 800, fontSize: 56, padding: '14px 42px', borderRadius: 999 }}>{chip}</div></Pop>
    <Pop delay={6} style={{ position: 'absolute', left: 80, top: 380 }}><Wave noisy={noisy} /></Pop>
    <Label top={520} color={dark ? '#9DB3AC' : C.muted} delay={10}>ग्राहक</Label>
    <div style={{ position: 'absolute', left: 60, right: 80, top: 580, display: 'flex' }}><Big who="them" delay={12} maxWidth={900}>{q}</Big></div>
    <Label top={930} color={dark ? C.mint : C.green} delay={50}>Munshi</Label>
    <div style={{ position: 'absolute', left: 80, right: 60, top: 1010, display: 'flex', justifyContent: 'flex-end' }}><Big who="me" delay={52} maxWidth={900}>{a}</Big></div>
    <Ex dark={!!dark} />
    <Sfx at={12} file={noisy ? 'tick.wav' : 'pop.wav'} /><Sfx at={52} file="ding.wav" volume={0.5} />
  </AbsoluteFill>
);
export const I4: React.FC = () => (
  <AbsoluteFill>
    <Sequence from={0} durationInFrames={100}><Bg />
      <Pop style={{ position: 'absolute', left: 80, right: 80, top: 430 }}><div style={{ fontFamily: FONT, fontWeight: 800, fontSize: 150, color: C.mint, lineHeight: 1.1 }}>हिंदी।</div></Pop>
      <Pop delay={14} style={{ position: 'absolute', left: 80, right: 80, top: 640 }}><div style={{ fontFamily: FONT, fontWeight: 800, fontSize: 150, color: '#FFD27A', lineHeight: 1.1 }}>Hinglish।</div></Pop>
      <Pop delay={28} style={{ position: 'absolute', left: 80, right: 80, top: 850 }}><div style={{ fontFamily: FONT, fontWeight: 800, fontSize: 150, color: '#fff', lineHeight: 1.1 }}>English।</div></Pop>
      <Pop delay={52} style={{ position: 'absolute', left: 80, right: 80, top: 1190 }}><div style={{ fontFamily: FONT, fontWeight: 800, fontSize: 78, color: '#E3EFEA', lineHeight: 1.25 }}>ग्राहक जैसे बोले,<br />Munshi समझकर जवाब देता है।</div></Pop></Sequence>
    <Sequence from={100} durationInFrames={140}><LangRound chip="हिंदी" q="भैया, आज दुकान कब तक खुली है?" a="जी, रात 9 बजे तक। और कुछ पूछना है?" /></Sequence>
    <Sequence from={240} durationInFrames={140}><LangRound dark chip="Hinglish" q="bhaiya, kal delivery ho jayegi kya?" a="डिलीवरी रमेश जी बताएँगे। आपका नाम बताइए?" /></Sequence>
    <Sequence from={380} durationInFrames={140}><LangRound chip="English" q="Do you have home delivery?" a="Yes, within 3 km. Free above ₹500." /></Sequence>
    <Sequence from={520} durationInFrames={170}><LangRound dark noisy chip="शोर वाली line" q="[शोर]… 5 किलो… चीनी… [शोर]" a="आवाज़ साफ़ नहीं आई। क्या आप दोबारा बोल सकते हैं?" /></Sequence>
    <Sequence from={690} durationInFrames={120}><Bg />
      <KW dark top={470} size={110} step={6} words={[['समझ', false], ['न', false], ['आए,', false], ['तो', false], ['अंदाज़ा', true], ['नहीं।', true], ['दोबारा', true], ['पूछता', true], ['है।', true]]} />
      <Foot top={1500}>हिंदी, Hinglish और English में।</Foot></Sequence>
    <Sequence from={810}><Bg /><EndCard line="जैसे बोलें, वैसे सुने।" /></Sequence>
    <Bed /><Sfx at={0} file="pop.wav" /><Sfx at={14} file="pop.wav" /><Sfx at={28} file="pop.wav" /><Sfx at={690} file="pop.wav" /><Sfx at={810} file="pop.wav" />
  </AbsoluteFill>
);

export const iDur = { I1: 990, I2: 810, I3: 960, I4: 960 };
