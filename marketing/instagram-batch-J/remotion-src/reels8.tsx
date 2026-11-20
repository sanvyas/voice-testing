import React from 'react';
import { AbsoluteFill, Sequence, interpolate, spring, useCurrentFrame, useVideoConfig } from 'remotion';
import { AppTop, Badge, Bed, Bg, C, EndCard, Hi, Phone, Pop, Sfx } from './ui';
import { BODY, FONT } from './fonts';
import { Card, Col, Foot, Handset, KW, Light, Num, Tag } from './reels5';

/* Set J: value-led stories. Each reel (1) shows a moment the owner recognises, with the rupees it costs,
   (2) shows what normally happens, (3) shows what Munshi and WhatsApp do about it on the real screens,
   (4) shows what improves. Every shop, name, time and number is an example (उदाहरण); the owner's numbers will differ. */

const Ex: React.FC<{ dark?: boolean }> = ({ dark = false }) => <Tag dark={dark}>उदाहरण</Tag>;
const Head: React.FC<{ children: React.ReactNode; top?: number; size?: number; dark?: boolean }> = ({ children, top = 200, size = 74, dark = true }) => (
  <Pop style={{ position: 'absolute', left: 80, right: 130, top }}><div style={{ fontFamily: FONT, fontSize: size, fontWeight: 800, color: dark ? '#fff' : C.ink, lineHeight: 1.2 }}>{children}</div></Pop>
);
const Sub: React.FC<{ children: React.ReactNode; top: number; size?: number; color?: string; delay?: number }> = ({ children, top, size = 46, color = '#D5E4DE', delay = 0 }) => (
  <Pop delay={delay} style={{ position: 'absolute', left: 80, right: 80, top }}><div style={{ fontFamily: BODY, fontSize: size, fontWeight: 600, color, lineHeight: 1.4 }}>{children}</div></Pop>
);

/** A row of a timeline: a time, what happened. */
const Row: React.FC<{ time: string; children: React.ReactNode; tone?: 'gray' | 'amber' | 'red' | 'green'; delay: number }> = ({ time, children, tone = 'gray', delay }) => {
  const m = { gray: ['#fff', C.line, C.ink], amber: [C.warnSoft, '#F2C79E', C.warn], red: ['#FDECEC', '#F3C2C2', '#9B1C1C'], green: ['#E6F6EE', '#9AD6B8', '#07573F'] }[tone];
  return <Pop delay={delay} from="left"><div style={{ display: 'flex', alignItems: 'center', gap: 22, background: m[0], border: `3px solid ${m[1]}`, borderRadius: 30, padding: '26px 30px' }}>
    <div style={{ fontFamily: FONT, fontWeight: 800, fontSize: 40, color: m[2], minWidth: 150 }}>{time}</div>
    <div style={{ fontFamily: BODY, fontWeight: 700, fontSize: 40, color: m[2], lineHeight: 1.3 }}>{children}</div></div></Pop>;
};

/** A WhatsApp-style chat screen (generic, no logo). */
const WA: React.FC<{ name: string; children: React.ReactNode; top?: number }> = ({ name, children, top = 430 }) => (
  <Phone top={top} bg="#ECE5DD">
    <div style={{ background: '#075E54', padding: '70px 26px 18px', display: 'flex', alignItems: 'center', gap: 16 }}>
      <div style={{ width: 62, height: 62, borderRadius: 31, background: '#DCF8C6', color: '#075E54', fontFamily: FONT, fontWeight: 800, fontSize: 32, display: 'grid', placeItems: 'center' }}>{name.charAt(0)}</div>
      <div><div style={{ fontFamily: BODY, fontWeight: 700, fontSize: 31, color: '#fff' }}>{name}</div><div style={{ fontFamily: BODY, fontSize: 21, color: '#B5D9D2' }}>WhatsApp · business</div></div></div>
    <div style={{ padding: '22px 20px', display: 'flex', flexDirection: 'column', gap: 14 }}>{children}</div>
  </Phone>
);
const Msg: React.FC<{ out?: boolean; time: string; delay: number; children: React.ReactNode; ticks?: boolean }> = ({ out, time, delay, children, ticks }) => (
  <Pop delay={delay} from="scale" style={{ alignSelf: out ? 'flex-end' : 'flex-start', transformOrigin: out ? 'right top' : 'left top' }}>
    <div style={{ maxWidth: 470, background: out ? '#DCF8C6' : '#fff', color: '#111', borderRadius: 22, borderTopRightRadius: out ? 6 : 22, borderTopLeftRadius: out ? 22 : 6, padding: '16px 20px 10px', fontFamily: BODY, fontSize: 26, lineHeight: 1.38, fontWeight: 500, boxShadow: '0 1px 3px rgba(0,0,0,.18)' }}>
      {children}<div style={{ textAlign: 'right', fontSize: 19, color: '#6b7a76', marginTop: 4 }}>{time}{ticks ? <span style={{ color: '#34B7F1', marginLeft: 6 }}>✓✓</span> : null}</div></div></Pop>
);
/** The one message every caller gets after a call (what the product really sends). */
const WA_MESSAGE = 'Hi, this is the AI assistant of Sharma Kirana. Your call is noted. Address: 21, Main Bazaar, Nehru Nagar. Hours: every day, 8 am to 9 pm. Reply here if you want to add anything and the owner will get back to you.';

/** The owner's call card, as in the app. */
const OwnerCard: React.FC<{ badge: string; tone?: 'warn' | 'ok' | 'gray'; text: string; chips?: string[]; pressed?: number; pressAt?: number; extra?: React.ReactNode }> = ({ badge, tone = 'warn', text, chips = [], pressed = -1, pressAt = 70, extra }) => {
  const f = useCurrentFrame();
  return <Card><div style={{ display: 'flex', gap: 10, flexWrap: 'wrap' }}><Badge tone={tone}>{badge}</Badge><Badge>Phone call</Badge>{extra}</div>
    <div style={{ fontSize: 33, fontWeight: 700, color: C.ink, marginTop: 14, lineHeight: 1.34 }}>{text}</div>
    <div style={{ display: 'flex', gap: 12, marginTop: 18, flexWrap: 'wrap' }}>{chips.map((c, i) => { const on = i === pressed && f >= pressAt;
      return <div key={c} style={{ background: on ? '#07573F' : i === 0 ? C.green : '#fff', color: i === 0 || on ? '#fff' : C.green, border: `2px solid ${C.green}`, borderRadius: 999, padding: '14px 26px', fontSize: 27, fontWeight: 700, transform: on ? 'scale(.94)' : 'none' }}>{c}</div>; })}</div></Card>;
};
/** A finger tap. */
const Tap: React.FC<{ x: number; y: number; at: number }> = ({ x, y, at }) => {
  const f = useCurrentFrame(); const p = interpolate(f, [at, at + 18], [0, 1], { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' });
  if (f < at) return null;
  return <div style={{ position: 'absolute', left: x - 50, top: y - 50, width: 100, height: 100, borderRadius: 50, border: '6px solid rgba(255,176,32,.9)', transform: `scale(${0.4 + p * 0.9})`, opacity: 1 - p * 0.6, zIndex: 20 }} />;
};
const Money: React.FC<{ value: number; color?: string; size?: number; prefix?: string }> = ({ value, color = C.red, size = 170, prefix = '₹' }) => (
  <div style={{ fontFamily: FONT, fontWeight: 800, fontSize: size, color, letterSpacing: -3, lineHeight: 1 }}><Num to={value} prefix={prefix} dur={26} /></div>
);
const Chips: React.FC<{ items: string[]; top: number; start?: number; step?: number; dark?: boolean }> = ({ items, top, start = 0, step = 22, dark = true }) => (
  <div style={{ position: 'absolute', left: 70, right: 70, top, display: 'flex', flexDirection: 'column', gap: 24 }}>
    {items.map((t, i) => <Pop key={t} delay={start + i * step} from="left"><div style={{ background: dark ? 'rgba(142,240,198,.12)' : '#fff', border: `3px solid ${dark ? 'rgba(142,240,198,.45)' : C.green}`, color: dark ? C.mint : '#07573F', borderRadius: 34, padding: '26px 36px', fontFamily: FONT, fontWeight: 800, fontSize: 48, lineHeight: 1.25 }}>✓ {t}</div></Pop>)}
  </div>
);
const More: React.FC<{ items: string[] }> = ({ items }) => <AbsoluteFill><Bg /><Head top={190} size={70}>और क्या कर सकते हैं?</Head><Chips items={items} top={430} start={14} /></AbsoluteFill>;

/* ================= J1: the story of one order ================= */
export const J1: React.FC = () => (
  <AbsoluteFill>
    <Sequence from={0} durationInFrames={120}><Bg />
      <Pop from="scale" style={{ position: 'absolute', left: 0, right: 0, top: 330, textAlign: 'center' }}><div style={{ fontFamily: FONT, fontWeight: 800, fontSize: 260, color: C.mint, letterSpacing: -6 }}>7:42</div><div style={{ fontFamily: FONT, fontWeight: 700, fontSize: 70, color: '#fff', marginTop: -6 }}>शाम · दुकान में भीड़</div></Pop>
      <Pop delay={26} style={{ position: 'absolute', left: 80, right: 80, top: 900, textAlign: 'center' }}><div style={{ fontFamily: FONT, fontWeight: 800, fontSize: 84, color: '#fff', lineHeight: 1.25 }}>फ़ोन बजा।<br />ऑर्डर था <Hi color="#FFD27A">₹2,350</Hi> का।</div></Pop><Ex dark />
      <Sfx at={0} file="ring.wav" volume={0.6} /><Sfx at={40} file="ring.wav" volume={0.5} /></Sequence>
    <Sequence from={120} durationInFrames={210}><Light /><Ex />
      <Head dark={false} top={200} size={80}>बिना Munshi, <span style={{ color: C.red }}>ऐसा होता है</span></Head>
      <div style={{ position: 'absolute', left: 60, right: 60, top: 470, display: 'flex', flexDirection: 'column', gap: 30 }}>
        <Row time="7:42" delay={10}>हाथ में सामान। फ़ोन किसी ने नहीं उठाया।</Row>
        <Row time="7:43" tone="amber" delay={48}>ग्राहक ने अगली दुकान को call किया।</Row>
        <Row time="7:50" tone="red" delay={86}>₹2,350 का ऑर्डर वहाँ चला गया।</Row></div>
      <Pop delay={128} from="scale" style={{ position: 'absolute', left: 0, right: 0, top: 1250, textAlign: 'center' }}><Money value={2350} /><div style={{ fontFamily: BODY, fontWeight: 700, fontSize: 44, color: '#9B1C1C', marginTop: 6 }}>की बिक्री गई</div></Pop>
      <Sfx at={10} file="pop.wav" /><Sfx at={86} file="whoosh.wav" volume={0.5} /></Sequence>
    <Sequence from={330} durationInFrames={110}><Bg /><Ex dark />
      <Head top={180} size={70}>Munshi के साथ: <Hi>7:42 पर</Hi></Head>
      <div style={{ position: 'absolute', left: 60, right: 60, top: 440, display: 'flex', flexDirection: 'column', gap: 34 }}>
        <Pop delay={8} from="scale" style={{ alignSelf: 'flex-start' }}><div style={{ maxWidth: 860, background: '#fff', borderRadius: 44, borderBottomLeftRadius: 10, padding: '30px 38px', fontFamily: BODY, fontSize: 50, fontWeight: 700, color: C.ink, lineHeight: 1.35 }}>10 kg आटा, 5 kg चीनी, 2 लीटर तेल। आज रात पहुँचा दीजिए।</div></Pop>
        <Pop delay={46} from="scale" style={{ alignSelf: 'flex-end' }}><div style={{ maxWidth: 880, background: C.green, borderRadius: 44, borderBottomRightRadius: 10, padding: '30px 38px', fontFamily: BODY, fontSize: 50, fontWeight: 700, color: '#fff', lineHeight: 1.35 }}>जी, मैं दुकान का AI सहायक हूँ। आपका नाम और पता बताइए।</div></Pop></div>
      <Sub top={1250} color="#9DB3AC" size={40} delay={70}>Munshi ने उठाया और ऑर्डर नोट किया।</Sub>
      <Sfx at={8} file="pop.wav" /><Sfx at={46} file="pop.wav" /></Sequence>
    <Sequence from={440} durationInFrames={110}><Bg /><Ex dark />
      <Head top={170} size={66}>ग्राहक को <Hi>WhatsApp</Hi> पर तुरंत संदेश</Head>
      <WA name="Sharma Kirana" top={400}><Msg time="7:44 pm" delay={14}>{WA_MESSAGE}</Msg></WA>
      <Sfx at={14} file="ding.wav" /></Sequence>
    <Sequence from={550} durationInFrames={130}><Bg /><Ex dark />
      <Head top={170} size={66}>8:05 पर आपके पास: <Hi>एक लाइन</Hi></Head>
      <Phone top={430}><AppTop title="अभी की calls" sub="Munshi" /><Col top={190}>
        <Pop delay={8}><OwnerCard badge="Needs you" text="सुनील: 10 kg आटा, 5 kg चीनी, 2 लीटर तेल। आज रात डिलीवरी।" chips={['Call back', 'WhatsApp']} pressed={0} pressAt={64} /></Pop>
        <Pop delay={86} from="scale"><Card style={{ background: '#E6F6EE', borderColor: '#9AD6B8' }}><div style={{ fontSize: 36, fontWeight: 800, color: '#07573F' }}>✓ बात हुई। ऑर्डर पक्का।</div></Card></Pop></Col></Phone>
      <Tap x={285} y={840} at={64} /><Sfx at={64} file="tick.wav" /><Sfx at={88} file="ding.wav" /></Sequence>
    <Sequence from={680} durationInFrames={180}><Light /><Ex />
      <Head dark={false} top={190} size={72}>एक छोटा <span style={{ color: C.green }}>हिसाब</span></Head>
      <div style={{ position: 'absolute', left: 70, right: 70, top: 440, display: 'flex', flexDirection: 'column', gap: 28 }}>
        <Row time="रोज़" delay={8}>2 call छूटती हैं</Row>
        <Row time="हफ़्ता" delay={34}>इनमें 4 ऑर्डर वाली</Row>
        <Row time="महीना" tone="green" delay={60}>सिर्फ़ 2 ऑर्डर बचे (हर ₹2,350)</Row></div>
      <Pop delay={92} from="scale" style={{ position: 'absolute', left: 70, right: 70, top: 1010 }}><Card style={{ borderRadius: 36, borderColor: C.green, padding: '30px 36px' }}>
        <div style={{ fontFamily: BODY, fontSize: 38, fontWeight: 700, color: C.muted }}>बिक्री ₹4,700 · मुनाफ़ा (15% मानें)</div>
        <div style={{ fontFamily: FONT, fontSize: 120, fontWeight: 800, color: C.green, letterSpacing: -2 }}><Num to={705} prefix="≈ ₹" from={96} dur={30} /></div></Card></Pop>
      <Foot dark={false} top={1420}>आपके आँकड़े अलग होंगे। यह सिर्फ़ एक उदाहरण है।</Foot></Sequence>
    <Sequence from={860} durationInFrames={120}><More items={['WhatsApp पर एक टैप में जवाब', 'हर ग्राहक का एक thread', 'ऑर्डर एक जगह, गुम नहीं']} /></Sequence>
    <Sequence from={980}><Bg /><EndCard line="एक भी ऑर्डर क्यों जाए?" word="ORDER" /></Sequence>
    <Bed />
  </AbsoluteFill>
);

/* ================= J2: the same five questions every day ================= */
const Q = [['दुकान कब तक खुली है?', 3], ['पता कहाँ है?', 2], ['होम डिलीवरी होती है?', 2], ['रविवार को खुले हैं?', 1], ['आटे का रेट?', 1]] as const;
export const J2: React.FC = () => (
  <AbsoluteFill>
    <Sequence from={0} durationInFrames={110}><Bg /><Ex dark />
      <KW dark top={480} size={116} step={8} words={[['आज', false], ['14', true], ['call', false], ['आईं।', false]]} />
      <Pop delay={46} style={{ position: 'absolute', left: 80, right: 80, top: 1000 }}><div style={{ fontFamily: FONT, fontWeight: 800, fontSize: 96, color: '#fff', lineHeight: 1.2 }}><Hi color="#FFD27A">9</Hi> में सवाल<br />एक ही था।</div></Pop></Sequence>
    <Sequence from={110} durationInFrames={290}><Light /><Ex />
      <Head dark={false} top={190} size={74}>वही <span style={{ color: C.green }}>5 सवाल</span>, रोज़</Head>
      <div style={{ position: 'absolute', left: 60, right: 60, top: 440, display: 'flex', flexDirection: 'column', gap: 22 }}>
        {Q.map(([q, n], i) => <Pop key={q} delay={10 + i * 30} from="left"><div style={{ display: 'flex', alignItems: 'center', gap: 20, background: '#fff', border: `3px solid ${C.line}`, borderRadius: 28, padding: '24px 30px' }}>
          <div style={{ flex: 1, fontFamily: BODY, fontWeight: 700, fontSize: 42, color: C.ink }}>{q}</div>
          <div style={{ fontFamily: FONT, fontWeight: 800, fontSize: 56, color: C.warn }}>× {n}</div></div></Pop>)}
      </div>
      <Pop delay={170} from="scale" style={{ position: 'absolute', left: 70, right: 70, top: 1260 }}><div style={{ background: C.warnSoft, border: '3px solid #F2C79E', borderRadius: 34, padding: '30px 36px', fontFamily: FONT, fontWeight: 800, fontSize: 52, color: C.warn, lineHeight: 1.3 }}>9 बार आप बिल बनाते-बनाते रुके।</div></Pop>
      <Sfx at={10} file="pop.wav" /><Sfx at={170} file="whoosh.wav" volume={0.5} /></Sequence>
    <Sequence from={400} durationInFrames={110}><Bg /><Ex dark />
      <Head top={170} size={66}>आप <Hi>एक बार</Hi> बताइए</Head>
      <Phone top={400}><AppTop title="दुकान की जानकारी" sub="Munshi" /><Col top={190} gap={12}>
        {[['समय', 'रोज़ सुबह 8 से रात 9 बजे तक'], ['पता', '21, मेन बाज़ार, नेहरू नगर'], ['होम डिलीवरी', '3 किमी तक, ₹500 से ऊपर मुफ़्त'], ['आटा', '₹42/kg']].map(([a, b], i) => <Pop key={a} delay={8 + i * 12}><Card style={{ padding: '16px 22px', borderRadius: 24 }}><div style={{ fontSize: 24, fontWeight: 700, color: C.muted }}>{a}</div><div style={{ fontSize: 31, fontWeight: 700, color: C.ink, lineHeight: 1.3 }}>{b}</div><div style={{ fontSize: 21, color: C.green, fontWeight: 700, marginTop: 4 }}>अभी पक्का किया</div></Card></Pop>)}</Col></Phone></Sequence>
    <Sequence from={510} durationInFrames={110}><Bg /><Ex dark />
      <Head top={190} size={66}>फिर हर call पर <Hi>Munshi जवाब देता है</Hi></Head>
      <div style={{ position: 'absolute', left: 60, right: 60, top: 480, display: 'flex', flexDirection: 'column', gap: 34 }}>
        <Pop delay={8} from="scale" style={{ alignSelf: 'flex-start' }}><div style={{ maxWidth: 860, background: '#fff', borderRadius: 44, borderBottomLeftRadius: 10, padding: '30px 38px', fontFamily: BODY, fontSize: 52, fontWeight: 700, color: C.ink }}>आज दुकान कितने बजे तक खुली है?</div></Pop>
        <Pop delay={44} from="scale" style={{ alignSelf: 'flex-end' }}><div style={{ maxWidth: 860, background: C.green, borderRadius: 44, borderBottomRightRadius: 10, padding: '30px 38px', fontFamily: BODY, fontSize: 52, fontWeight: 700, color: '#fff' }}>रात 9 बजे तक। और कुछ पूछना है?</div></Pop></div>
      <Sub top={1180} color="#9DB3AC" size={42} delay={70}>जवाब वही, जो आपने बताया।</Sub></Sequence>
    <Sequence from={620} durationInFrames={100}><Bg /><Ex dark />
      <Head top={170} size={64}>साथ में <Hi>WhatsApp</Hi> पर पता और समय, लिखा हुआ</Head>
      <WA name="Sharma Kirana" top={420}><Msg time="1:24 pm" delay={12}>{WA_MESSAGE}</Msg></WA><Sfx at={12} file="ding.wav" /></Sequence>
    <Sequence from={720} durationInFrames={170}><Light /><Ex />
      <Head dark={false} top={190} size={70}>अब आपके पास सिर्फ़ <span style={{ color: C.green }}>ज़रूरी call</span></Head>
      <div style={{ position: 'absolute', left: 60, right: 60, top: 470, display: 'flex', flexDirection: 'column', gap: 28 }}>
        <Pop delay={8} from="left"><div style={{ background: '#EEF4F1', border: `3px solid ${C.line}`, borderRadius: 30, padding: '28px 34px', fontFamily: BODY, fontWeight: 700, fontSize: 42, color: C.muted }}><Badge>Good to know</Badge> &nbsp; 9 सवालों के जवाब मिल गए</div></Pop>
        <Pop delay={34} from="left"><div style={{ background: '#fff', border: `3px solid ${C.warn}`, borderRadius: 30, padding: '28px 34px' }}><Badge tone="warn">Needs you</Badge><div style={{ fontFamily: BODY, fontWeight: 700, fontSize: 42, color: C.ink, marginTop: 12 }}>5 call जिन पर आपका जवाब चाहिए</div></div></Pop></div>
      <Pop delay={80} style={{ position: 'absolute', left: 80, right: 80, top: 1050 }}><div style={{ fontFamily: FONT, fontWeight: 800, fontSize: 70, color: C.ink, lineHeight: 1.25 }}>फ़ोन बजे तो आप तय करें:<br /><span style={{ color: C.green }}>उठाएँ, या Munshi को सँभालने दें।</span></div></Pop></Sequence>
    <Sequence from={890} durationInFrames={110}><More items={['पता और समय ग्राहक को लिखकर मिलता है', 'ग्राहक का नाम और बात ऐप में', 'spam अलग (Not worth it)']} /></Sequence>
    <Sequence from={1000}><Bg /><EndCard line="सवाल वही, जवाब Munshi का।" word="SAWAAL" /></Sequence>
    <Bed />
  </AbsoluteFill>
);

/* ================= J3: diary against an order card ================= */
const Diary: React.FC = () => (
  <div style={{ position: 'absolute', left: 90, right: 90, top: 440, background: '#FFFDF4', border: '3px solid #E3DCC2', borderRadius: 18, padding: '34px 40px 40px', transform: 'rotate(-2deg)', boxShadow: '0 20px 50px rgba(60,50,20,.22)' }}>
    {[['सुनील – आटा 10?  चीनी ??', true], ['नंबर: ........', true], ['कल सुबह (कहाँ?)', false], ['गुप्ता – तेल 2 ltr', false]].map(([t, bad], i) => <Pop key={String(t)} delay={8 + i * 14}><div style={{ fontFamily: "'Noto Sans Devanagari', sans-serif", fontWeight: 600, fontSize: 52, fontStyle: 'italic', color: bad ? '#9B1C1C' : '#4B4630', lineHeight: 1.7, borderBottom: '3px dashed #C9C1A3' }}>{t as string}</div></Pop>)}
  </div>
);
export const J3: React.FC = () => (
  <AbsoluteFill>
    <Sequence from={0} durationInFrames={100}><Bg /><Ex dark />
      <KW dark top={470} size={116} step={7} words={[['10', true], ['kg', false], ['था', false], ['या', false], ['5', true], ['kg?', false]]} />
      <Pop delay={44} style={{ position: 'absolute', left: 80, right: 80, top: 1000 }}><div style={{ fontFamily: FONT, fontWeight: 700, fontSize: 64, color: '#E3EFEA', lineHeight: 1.3 }}>diary में लिखा था…<br /><Hi color="#FFD27A">पर साफ़ नहीं।</Hi></div></Pop></Sequence>
    <Sequence from={100} durationInFrames={240}><Light /><Ex />
      <Head dark={false} top={190} size={72}>फ़ोन का ऑर्डर, <span style={{ color: C.red }}>diary में</span></Head>
      <Diary />
      <div style={{ position: 'absolute', left: 70, right: 70, top: 1130, display: 'flex', flexDirection: 'column', gap: 20 }}>
        <Pop delay={70} from="left"><div style={{ background: '#FDECEC', border: '3px solid #F3C2C2', borderRadius: 28, padding: '20px 30px', fontFamily: BODY, fontWeight: 700, fontSize: 40, color: '#9B1C1C' }}>✗ नंबर नहीं लिखा, पर्ची खो गई</div></Pop>
        <Pop delay={100} from="left"><div style={{ alignSelf: 'flex-end', maxWidth: 800, background: '#fff', border: `3px solid ${C.line}`, borderRadius: 34, borderBottomRightRadius: 8, padding: '22px 32px', fontFamily: BODY, fontWeight: 700, fontSize: 42, color: C.ink }}>“भैया, मैंने तो 10 kg बोला था!”</div></Pop></div>
      <Sfx at={70} file="whoosh.wav" volume={0.5} /></Sequence>
    <Sequence from={340} durationInFrames={130}><Bg /><Ex dark />
      <Head top={170} size={68}>Munshi का <Hi>order card</Hi></Head>
      <Phone top={420}><AppTop title="अभी की calls" sub="Munshi" /><Col top={190}>
        <Pop delay={8}><Card><div style={{ display: 'flex', gap: 10 }}><Badge tone="warn">Needs you</Badge><Badge>Phone call</Badge></div>
          <div style={{ fontSize: 34, fontWeight: 800, color: C.ink, marginTop: 14 }}>सुनील · +91 98xxx xx210</div>
          {[['आटा', '10 kg'], ['चीनी', '5 kg']].map(([a, b], i) => <Pop key={a} delay={22 + i * 12}><div style={{ display: 'flex', justifyContent: 'space-between', fontSize: 32, fontWeight: 700, color: C.ink, borderBottom: `2px solid ${C.line}`, padding: '10px 0' }}><span>{a}</span><span style={{ color: C.green }}>{b}</span></div></Pop>)}
          <div style={{ fontSize: 27, color: C.muted, fontWeight: 600, marginTop: 12 }}>डिलीवरी · कल सुबह · 14, गांधी रोड</div>
          <div style={{ display: 'flex', gap: 12, marginTop: 16 }}><div style={{ background: C.green, color: '#fff', borderRadius: 999, padding: '12px 24px', fontSize: 26, fontWeight: 700 }}>Call back</div><div style={{ border: `2px solid ${C.green}`, color: C.green, borderRadius: 999, padding: '12px 24px', fontSize: 26, fontWeight: 700 }}>WhatsApp</div></div></Card></Pop></Col></Phone>
      <Sfx at={8} file="pop.wav" /><Sfx at={24} file="tick.wav" /><Sfx at={36} file="tick.wav" /></Sequence>
    <Sequence from={470} durationInFrames={130}><Bg /><Ex dark />
      <Head top={170} size={64}>एक टैप में <Hi>WhatsApp पर जवाब</Hi></Head>
      <WA name="सुनील" top={420}>
        <Msg time="4:02 pm" delay={10} out ticks>नमस्ते सुनील जी, आपकी बात नोट हो गई है। मैं थोड़ी देर में call करता हूँ।</Msg>
        <Msg time="4:03 pm" delay={50}>ठीक है, धन्यवाद 🙏</Msg></WA>
      <Sfx at={10} file="ding.wav" /><Sfx at={50} file="pop.wav" /></Sequence>
    <Sequence from={600} durationInFrames={190}><Light /><Ex />
      <Head dark={false} top={190} size={72}>diary बनाम <span style={{ color: C.green }}>Munshi</span></Head>
      <div style={{ position: 'absolute', left: 50, right: 50, top: 420, display: 'flex', flexDirection: 'column', gap: 18 }}>
        {[['ग्राहक का नंबर', 'कभी-कभी', 'हर बार, अपने आप'], ['क्या मँगवाया', 'याद से', 'सुनकर लिखा गया'], ['बाद में विवाद', '“मैंने तो…”', 'पूरी बातचीत देख सकते हैं'], ['पर्ची खोना', 'हो जाता है', 'सब ऐप में']].map(([a, b, c], i) => <Pop key={a} delay={8 + i * 26} from="left"><div style={{ background: '#fff', border: `3px solid ${C.line}`, borderRadius: 26, padding: '20px 26px' }}>
          <div style={{ fontFamily: BODY, fontWeight: 700, fontSize: 32, color: C.muted, marginBottom: 8 }}>{a}</div>
          <div style={{ display: 'flex', gap: 14 }}><div style={{ flex: 1, background: '#FDECEC', color: '#9B1C1C', borderRadius: 18, padding: '14px 18px', fontFamily: BODY, fontWeight: 700, fontSize: 34 }}>diary: {b}</div><div style={{ flex: 1, background: '#E6F6EE', color: '#07573F', borderRadius: 18, padding: '14px 18px', fontFamily: BODY, fontWeight: 700, fontSize: 34 }}>Munshi: {c}</div></div></div></Pop>)}</div></Sequence>
    <Sequence from={790} durationInFrames={110}><More items={['ग्राहक का पुराना हिसाब एक thread में', 'रेट की फ़ोटो से board', 'हिंदी और English notes']} /></Sequence>
    <Sequence from={900}><Bg /><EndCard line="ऑर्डर साफ़। झगड़ा बंद।" word="DIARY" /></Sequence>
    <Bed />
  </AbsoluteFill>
);

/* ================= J4: Sunday lunch ================= */
const Table: React.FC = () => {
  const f = useCurrentFrame(); const buzz = f % 50 < 8 ? Math.sin(f * 2.6) * 7 : 0;
  return <div style={{ position: 'absolute', left: 90, right: 90, top: 430, height: 560, background: '#F0E4CC', border: '4px solid #D7C49A', borderRadius: 48, boxShadow: '0 20px 50px rgba(60,50,20,.2)' }}>
    {[[110, 90], [400, 90], [690, 90], [255, 330], [545, 330]].map(([x, y], i) => <div key={i} style={{ position: 'absolute', left: x, top: y, width: 150, height: 150, borderRadius: 75, background: '#fff', border: '6px solid #E5D8B8', display: 'grid', placeItems: 'center', fontSize: 64 }}>{['🍛', '🍚', '🥗', '🍛', '🫓'][i]}</div>)}
    <div style={{ position: 'absolute', right: 40, bottom: 30, width: 130, height: 220, borderRadius: 26, background: '#0F1F1B', border: '5px solid #243B34', transform: `rotate(${buzz}deg)`, display: 'grid', placeItems: 'center' }}><Handset size={64} color={C.mint} /></div>
  </div>;
};
export const J4: React.FC = () => (
  <AbsoluteFill>
    <Sequence from={0} durationInFrames={110}><Bg /><Ex dark />
      <Pop from="scale" style={{ position: 'absolute', left: 80, right: 80, top: 360 }}><div style={{ fontFamily: FONT, fontWeight: 800, fontSize: 108, color: C.mint, lineHeight: 1.1 }}>रविवार<br />दोपहर 1:20</div></Pop>
      <Pop delay={26} style={{ position: 'absolute', left: 80, right: 80, top: 880 }}><div style={{ fontFamily: FONT, fontWeight: 800, fontSize: 86, color: '#fff', lineHeight: 1.25 }}>परिवार के साथ खाना।<br /><Hi color="#FFD27A">दुकान का फ़ोन फिर बजा।</Hi></div></Pop>
      <Sfx at={4} file="ring.wav" volume={0.6} /><Sfx at={60} file="ring.wav" volume={0.5} /></Sequence>
    <Sequence from={110} durationInFrames={230}><Light /><Ex />
      <Head dark={false} top={190} size={72}>खाना चलता रहा, <span style={{ color: C.green }}>call सँभली</span></Head>
      <Table />
      <div style={{ position: 'absolute', left: 60, right: 60, top: 1060, display: 'flex', flexDirection: 'column', gap: 20 }}>
        {['1:22', '1:41', '2:05'].map((t, i) => <Pop key={t} delay={30 + i * 50} from="left"><div style={{ display: 'flex', gap: 20, alignItems: 'center', background: '#E6F6EE', border: '3px solid #9AD6B8', borderRadius: 28, padding: '20px 30px' }}><span style={{ fontFamily: FONT, fontWeight: 800, fontSize: 42, color: '#07573F' }}>{t}</span><span style={{ fontFamily: BODY, fontWeight: 700, fontSize: 40, color: '#07573F' }}>call आई · Munshi ने उठाया ✓</span></div></Pop>)}</div>
      <Sfx at={30} file="ding.wav" /><Sfx at={80} file="ding.wav" /><Sfx at={130} file="ding.wav" /></Sequence>
    <Sequence from={340} durationInFrames={260}><Bg /><Ex dark />
      <Head top={170} size={68}>शाम 4 बजे, चाय के साथ</Head>
      <Phone top={400}><AppTop title="अभी की calls" sub="Munshi" /><Col top={190} gap={14}>
        <Pop delay={8}><OwnerCard badge="Needs you" text="गुप्ता जी: शादी के लिए 5 kg मिठाई, शनिवार।" chips={['Call back', 'WhatsApp']} pressed={0} pressAt={120} /></Pop>
        <Pop delay={24}><Card style={{ padding: '16px 22px' }}><div style={{ display: 'flex', gap: 10 }}><Badge>Good to know</Badge></div><div style={{ fontSize: 28, fontWeight: 700, color: C.ink, marginTop: 8 }}>नए ग्राहक ने दुकान का समय पूछा। बता दिया।</div></Card></Pop>
        <Pop delay={40}><Card style={{ padding: '16px 22px', background: '#F4F6F5' }}><div style={{ display: 'flex', gap: 10 }}><Badge>Not worth it</Badge></div><div style={{ fontSize: 28, fontWeight: 700, color: C.muted, marginTop: 8 }}>Loan का ऑफ़र। अलग रखा।</div></Card></Pop>
        <Pop delay={150} from="scale"><Card style={{ background: '#E6F6EE', borderColor: '#9AD6B8', padding: '16px 22px' }}><div style={{ fontSize: 30, fontWeight: 800, color: '#07573F' }}>✓ बात हुई। ऑर्डर पक्का।</div></Card></Pop></Col></Phone>
      <Tap x={285} y={760} at={120} /><Sfx at={120} file="tick.wav" /><Sfx at={152} file="ding.wav" /></Sequence>
    <Sequence from={600} durationInFrames={190}><Light /><Ex />
      <Head dark={false} top={190} size={72}>रविवार का <span style={{ color: C.green }}>फ़र्क़</span></Head>
      <div style={{ position: 'absolute', left: 50, right: 50, top: 440, display: 'flex', gap: 22 }}>
        {[['पहले', ['खाना अधूरा', 'बार-बार फ़ोन', 'या call छूटी'], '#FDECEC', '#9B1C1C'], ['अब', ['खाना पूरा', '4 बजे एक नज़र', 'ज़रूरी call पर बात'], '#E6F6EE', '#07573F']].map(([t, xs, bg, fg], c) => <div key={String(t)} style={{ flex: 1, background: bg as string, borderRadius: 34, padding: '30px 26px' }}>
          <Pop delay={8 + c * 40}><div style={{ fontFamily: FONT, fontWeight: 800, fontSize: 56, color: fg as string, marginBottom: 20 }}>{t as string}</div></Pop>
          {(xs as string[]).map((x, i) => <Pop key={x} delay={20 + c * 40 + i * 14}><div style={{ fontFamily: BODY, fontWeight: 700, fontSize: 40, color: fg as string, lineHeight: 1.35, marginBottom: 18 }}>{c ? '✓' : '✗'} {x}</div></Pop>)}</div>)}</div>
      <Sub top={1180} size={50} color={C.ink} delay={110}>छुट्टी मिली। ग्राहक भी नहीं गया।</Sub></Sequence>
    <Sequence from={790} durationInFrames={110}><More items={['रात और छुट्टी के दिन भी जवाब', 'दिन भर के spam से छुटकारा', 'माँ और परिवार की call सिर्फ़ आपको']} /></Sequence>
    <Sequence from={900}><Bg /><EndCard line="रविवार आपका। दुकान Munshi की।" word="FAMILY" /></Sequence>
    <Bed />
  </AbsoluteFill>
);

/* ================= J5: the follow-up you forget ================= */
export const J5: React.FC = () => (
  <AbsoluteFill>
    <Sequence from={0} durationInFrames={130}><Bg /><Ex dark />
      <div style={{ position: 'absolute', left: 80, right: 80, top: 330, display: 'flex', flexDirection: 'column', gap: 34 }}>
        <Pop><div style={{ fontFamily: FONT, fontWeight: 800, fontSize: 78, color: '#fff', lineHeight: 1.2 }}><Hi>मंगलवार:</Hi> शादी की मिठाई का enquiry आया।</div></Pop>
        <Pop delay={34}><div style={{ fontFamily: FONT, fontWeight: 800, fontSize: 78, color: '#fff', lineHeight: 1.2 }}><Hi color="#FFD27A">शुक्रवार:</Hi> ग्राहक ने कहीं और ऑर्डर दे दिया।</div></Pop>
        <Pop delay={70} from="scale"><div style={{ fontFamily: FONT, fontWeight: 800, fontSize: 130, color: '#FF8A80', letterSpacing: -3 }}>₹18,000</div></Pop></div></Sequence>
    <Sequence from={130} durationInFrames={210}><Light /><Ex />
      <Head dark={false} top={190} size={74}>भूलना <span style={{ color: C.red }}>इंसानी है</span></Head>
      <div style={{ position: 'absolute', left: 60, right: 60, top: 440, display: 'flex', gap: 16 }}>
        {[['मंगल', 'enquiry'], ['बुध', 'कल call करूँगा'], ['गुरु', '30 काम…'], ['शुक्र', 'ग्राहक गया']].map(([d, t], i) => <Pop key={d} delay={8 + i * 30} from="up" style={{ flex: 1 }}><div style={{ background: i === 3 ? '#FDECEC' : '#fff', border: `3px solid ${i === 3 ? '#F3C2C2' : C.line}`, borderRadius: 26, padding: '22px 12px', minHeight: 300, textAlign: 'center' }}>
          <div style={{ fontFamily: FONT, fontWeight: 800, fontSize: 44, color: i === 3 ? '#9B1C1C' : C.ink }}>{d}</div>
          <div style={{ fontFamily: BODY, fontWeight: 700, fontSize: 30, color: i === 3 ? '#9B1C1C' : C.muted, marginTop: 16, lineHeight: 1.3 }}>{t}</div></div></Pop>)}</div>
      <Pop delay={140} style={{ position: 'absolute', left: 80, right: 80, top: 920 }}><div style={{ fontFamily: BODY, fontWeight: 700, fontSize: 52, color: C.ink, lineHeight: 1.4 }}>दिन भर के 30 काम में, call back <span style={{ color: C.red }}>खिसक जाती है।</span></div></Pop>
      <Sfx at={8} file="pop.wav" /><Sfx at={98} file="pop.wav" /><Sfx at={140} file="whoosh.wav" volume={0.5} /></Sequence>
    <Sequence from={340} durationInFrames={290}><Bg /><Ex dark />
      <Head top={170} size={66}>Munshi के साथ, वो enquiry <Hi>ऊपर रहती है</Hi></Head>
      <Phone top={420}><AppTop title="अभी की calls" sub="Munshi" /><Col top={190} gap={14}>
        <Pop delay={8}><OwnerCard badge="Needs you" extra={<Badge tone="red">3 दिन से बाकी</Badge>} text="गुप्ता जी: शादी के लिए मिठाई, मात्रा और तारीख बतानी है।" chips={['WhatsApp', 'Call back']} pressed={0} pressAt={90} /></Pop>
        <Pop delay={110} from="scale"><div style={{ alignSelf: 'flex-end', background: '#DCF8C6', borderRadius: 24, borderTopRightRadius: 6, padding: '16px 22px', fontSize: 26, fontWeight: 500, color: '#111', lineHeight: 1.38, boxShadow: '0 1px 3px rgba(0,0,0,.18)' }}>नमस्ते, आपकी मिठाई की enquiry नोट है। तारीख और मात्रा बता दीजिए, मैं आज शाम call करता हूँ। <span style={{ color: '#34B7F1' }}>✓✓</span></div></Pop>
        <Pop delay={190} from="scale"><Card style={{ background: '#E6F6EE', borderColor: '#9AD6B8', padding: '16px 22px' }}><div style={{ fontSize: 30, fontWeight: 800, color: '#07573F' }}>✓ हो गया · बाकी: 0</div></Card></Pop></Col></Phone>
      <Tap x={285} y={820} at={90} /><Sfx at={90} file="tick.wav" /><Sfx at={112} file="ding.wav" /><Sfx at={190} file="ding.wav" /></Sequence>
    <Sequence from={630} durationInFrames={190}><Light /><Ex />
      <Head dark={false} top={190} size={72}>जो आपके <span style={{ color: C.green }}>हाथ में</span> आता है</Head>
      <div style={{ position: 'absolute', left: 70, right: 70, top: 450, display: 'flex', flexDirection: 'column', gap: 26 }}>
        {['कोई enquiry गुम नहीं, जब तक आप “हो गया” न दबाएँ', 'कितने दिन से बाकी है, साफ़ दिखता है', 'एक टैप में WhatsApp पर जवाब', 'ग्राहक का पूरा इतिहास एक जगह'].map((t, i) => <Pop key={t} delay={10 + i * 30} from="left"><div style={{ background: '#fff', border: `3px solid ${C.green}`, borderRadius: 30, padding: '26px 32px', fontFamily: BODY, fontWeight: 700, fontSize: 42, color: C.ink, lineHeight: 1.3 }}><span style={{ color: C.green }}>✓</span> {t}</div></Pop>)}</div></Sequence>
    <Sequence from={820} durationInFrames={110}><More items={['ऑर्डर की सूची एक जगह', 'हिंदी या English में notes', 'आपके खास लोग हमेशा आपके फ़ोन पर']} /></Sequence>
    <Sequence from={930}><Bg /><EndCard line="कोई ग्राहक छूटे नहीं।" word="FOLLOWUP" /></Sequence>
    <Bed />
  </AbsoluteFill>
);

export const jDur = { J1: 1130, J2: 1150, J3: 1050, J4: 1050, J5: 1080 };
