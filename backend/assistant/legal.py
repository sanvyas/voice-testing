"""The policy pages (/legal/...) and what they say about the operator.

The wording describes what this system actually does with data. Details that only the operator can know (company name, address,
grievance officer, support email) come from environment variables; until they are set the pages show a visible "to be filled" marker and
``missing()`` lists them, so the portal can warn. This is not legal advice: have a lawyer read these pages before launch.
"""
from __future__ import annotations

import html
import os

VERSION = "2026-11-19"
RETENTION_DAYS_DEFAULT = 365

FIELDS = {
    "LEGAL_ENTITY": "Company or proprietor name",
    "LEGAL_ADDRESS": "Registered address",
    "GRIEVANCE_NAME": "Grievance officer's name",
    "GRIEVANCE_EMAIL": "Grievance officer's email",
    "SUPPORT_EMAIL": "Support email",
    "LEGAL_JURISDICTION": "City whose courts have jurisdiction",
}


def retention_days() -> int:
    try:
        return max(30, int(os.getenv("MUNSHI_RETENTION_DAYS", RETENTION_DAYS_DEFAULT)))
    except ValueError:
        return RETENTION_DAYS_DEFAULT


def value(name: str) -> str:
    return os.getenv(name, "").strip()


def missing() -> list[str]:
    return [label for name, label in FIELDS.items() if not value(name)]


def ph(name: str) -> str:
    v = value(name)
    return html.escape(v) if v else f'<mark title="Set {name} on the server">[{html.escape(FIELDS[name])}: to be filled before launch]</mark>'


CSS = """:root{color-scheme:light dark;--bg:#F5F7F6;--fg:#14211c;--mut:#51635d;--card:#fff;--g:#0B7A59;--ring:#d3ddd9}
@media (prefers-color-scheme:dark){:root{--bg:#0f1714;--fg:#e8f0ec;--mut:#9db0a9;--card:#17221e;--g:#4fd0a3;--ring:#2c3b36}}
*{box-sizing:border-box}body{margin:0;background:var(--bg);color:var(--fg);font:16px/1.65 Inter,system-ui,'Noto Sans Devanagari',sans-serif}
main{max-width:760px;margin:0 auto;padding:20px 18px 64px}h1{font:700 30px/1.25 'Space Grotesk',Inter,sans-serif;margin:8px 0 4px}h2{font-size:20px;margin:30px 0 6px}
p,li{color:var(--fg)}.mut{color:var(--mut);font-size:14px}a{color:var(--g)}nav{display:flex;gap:14px;flex-wrap:wrap;font-weight:600;font-size:14px;margin-bottom:6px}
.hi{background:var(--card);border:1.5px solid var(--g);border-radius:16px;padding:14px 18px;margin:16px 0}.hi b{color:var(--g)}table{border-collapse:collapse;width:100%;font-size:14.5px}
td,th{border-bottom:1px solid var(--ring);padding:8px 6px;text-align:left;vertical-align:top}mark{background:#ffe9a8;color:#3a2a00;padding:1px 5px;border-radius:5px}ul{padding-left:22px}"""


def page(title: str, body: str, summary_hi: str = "") -> str:
    nav = '<nav><a href="/legal/privacy">Privacy Policy</a><a href="/legal/terms">Terms of Service</a><a href="/legal/delete-account">Delete your account</a><a href="/assistant/">Open the app</a></nav>'
    box = f'<div class="hi" lang="hi"><b>हिन्दी में संक्षेप:</b> {summary_hi}</div>' if summary_hi else ""
    return (f'<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><title>{html.escape(title)} · Munshi</title>'
            f'<meta name="robots" content="index,follow"><style>{CSS}</style></head><body><main>{nav}<h1>{html.escape(title)}</h1><p class="mut">Version {VERSION}</p>{box}{body}'
            f'<p class="mut" style="margin-top:40px">Munshi is operated by {ph("LEGAL_ENTITY")}, {ph("LEGAL_ADDRESS")}.</p></main></body></html>')


def privacy() -> str:
    days = retention_days()
    body = f"""
<p>Munshi is an AI assistant that answers a shop's phone calls when the owner cannot, takes a message, and tells the owner what happened. This policy explains what information Munshi handles, why, who else touches it, how long we keep it, and what you can do about it. It follows India's Digital Personal Data Protection Act, 2023.</p>

<h2>1. Who is who</h2>
<ul><li><b>You, the shop owner</b>, are our customer. We hold your information to run your account.</li>
<li><b>Your callers</b> are people who phone your shop. You decide to use Munshi to answer them, so you are responsible for them being told; Munshi handles their information on your behalf and, at the start of every call, tells them it is an AI assistant and that the conversation is noted.</li>
<li><b>We</b> are {ph("LEGAL_ENTITY")}. Questions and complaints go to our grievance officer (section 9).</li></ul>

<h2>2. What we collect</h2>
<table><tr><th>Whose</th><th>What</th><th>Why</th></tr>
<tr><td>Owner</td><td>Mobile number (to sign in), name, shop name, address, hours, rates and other shop information you add, contacts you choose to import, your choice of voice and language, the version of these terms you accepted and when, the device type of each signed-in phone.</td><td>To sign you in, answer calls as your shop, and show you your calls.</td></tr>
<tr><td>Caller</td><td>The number they called from, their name if they say it, what was said (a written transcript), the AI's short notes and to-do list, call time and length, language.</td><td>To take their message, tell the owner, and let the owner call or message them back.</td></tr>
<tr><td>Usage</td><td>Counts of AI and voice usage per call, costs, error logs, an activity log of changes in your account.</td><td>To bill correctly, find faults, and keep the service safe.</td></tr></table>
<p><b>Call audio.</b> While a call is going on, short pieces of audio are sent to a speech-to-text service to be turned into text. We do not keep the audio. We also ask our phone provider to delete its copy of each recording once it has been turned into text; it may take that provider a short while to do so.</p>
<p>We do not sell your information, and we do not use it for advertising. We do not collect payment card details.</p>

<h2>3. Who else handles it (our service providers)</h2>
<p>We use these companies to run Munshi. Each receives only what it needs, for the purpose shown. Some of them handle data on servers outside India.</p>
<table><tr><th>Provider</th><th>For</th></tr>
<tr><td>Render</td><td>Hosting the app</td></tr><tr><td>Supabase</td><td>The database where your account and calls are stored</td></tr>
<tr><td>Groq</td><td>Speech-to-text and the AI that writes replies and notes</td></tr><tr><td>Sarvam AI (only if switched on)</td><td>A second AI provider for replies and notes</td></tr>
<tr><td>Google Cloud Text-to-Speech</td><td>Turning Munshi's replies into voice</td></tr><tr><td>DeepInfra (only if switched on)</td><td>An alternative voice</td></tr>
<tr><td>Plivo</td><td>Phone calls, and the SMS that carries your sign-in code</td></tr>
<tr><td>Meta (WhatsApp) (only if you connect it)</td><td>Sending a message to a caller from your shop</td></tr></table>
<p>We may also share information when the law requires it, for example a lawful order from a court or authority.</p>

<h2>4. Why we may use it, and your consent</h2>
<p>We use your information to provide the service you signed up for. By ticking the box when you sign in you consent to this policy and the Terms. You can withdraw consent at any time by deleting your account (section 7); Munshi then stops working for you.</p>

<h2>5. How long we keep it</h2>
<ul><li>Calls (transcripts, notes, messages): {days} days after the call, then deleted automatically. You can delete your whole account sooner.</li>
<li>Sign-in codes: deleted within a day. Signed-in sessions: end after 90 days without use, or when you sign out.</li>
<li>When you delete your account, your shop, contacts, rates, calls and messages are deleted at once from the live service. Backups, if any, are overwritten within 35 days.</li>
<li>Records we must keep by law (for example billing records, once billing starts) are kept for the period the law requires.</li></ul>

<h2>6. Security</h2>
<p>Connections are encrypted. Keys for outside services are stored encrypted. Each owner can see only their own business. Sign-in needs a code sent to your phone. No system is perfectly safe; if a breach affects you we will tell you and the authorities as the law requires.</p>

<h2>7. Your rights</h2>
<ul><li><b>See and download</b> your information: Settings, "Download my data" in the app.</li>
<li><b>Correct</b> it: change your details and shop information in the app.</li>
<li><b>Delete</b> it: Settings, "Delete my account and data", or see <a href="/legal/delete-account">how to delete your account</a>.</li>
<li><b>Withdraw consent, complain, or nominate</b> someone to act for you if you cannot: write to the grievance officer below.</li></ul>
<p>If you are a caller and want your call removed, tell the shop owner or write to us with your number and the date; we will pass it on to the owner and remove it where we can.</p>

<h2>8. Children</h2>
<p>Munshi is for businesses. It is not meant for people under 18. If a child's information reaches us, tell us and we will delete it.</p>

<h2>9. Grievance officer and contact</h2>
<p>{ph("GRIEVANCE_NAME")}, {ph("GRIEVANCE_EMAIL")}. We reply within 30 days. Support: {ph("SUPPORT_EMAIL")}. If you are not satisfied you may complain to the Data Protection Board of India once it is operating.</p>

<h2>10. Changes</h2>
<p>If we change this policy in a way that matters, we will tell you in the app before it applies and ask you to agree again.</p>"""
    hi = f"Munshi आपकी दुकान की कॉल उठाता है और संदेश लिखकर आपको देता है। हम आपका मोबाइल नंबर, दुकान की जानकारी और कॉल की बातचीत (लिखित) रखते हैं। कॉल की आवाज़ हम सहेजते नहीं। जानकारी बेची नहीं जाती। कॉल की जानकारी {days} दिन बाद अपने आप मिट जाती है। आप सेटिंग में अपना डेटा डाउनलोड कर सकते हैं या खाता मिटा सकते हैं। शिकायत नीचे दिए अधिकारी को भेजें।"
    return page("Privacy Policy", body, hi)


def terms() -> str:
    body = f"""
<p>These terms are between you (the business or shop owner using Munshi) and {ph("LEGAL_ENTITY")}. By signing in and ticking the box you agree to them and to the <a href="/legal/privacy">Privacy Policy</a>.</p>

<h2>1. What Munshi does</h2>
<p>Munshi answers calls to your shop with an AI voice when you cannot, tells callers it is an AI, takes a message, answers from the shop information you give it, and sends you notes. It is a helper, not a person, and it can make mistakes: mishear, misunderstand, or say something imperfectly. Read your notes and call people back.</p>

<h2>2. What Munshi will not do</h2>
<p>It does not agree prices, discounts, credit, refunds, deadlines or appointments for you, does not take card numbers, OTPs or passwords, and does not give medical, legal or financial advice. If someone needs urgent help it tells them to call 112. Do not rely on Munshi for emergencies.</p>

<h2>3. Your responsibilities</h2>
<ul><li>Keep your shop information, rates and hours correct. Munshi repeats only what you give it.</li>
<li>Use Munshi only for lawful purposes. It answers incoming calls; it is not for unsolicited or marketing calls, and you must follow telecom and consumer rules.</li>
<li>You are responsible for telling your callers that calls are answered by an AI and noted. Munshi says so at the start of every call; do not switch that off.</li>
<li>Only import contacts you are allowed to hold, and keep your sign-in number and phone secure.</li></ul>

<h2>4. Plans and payment</h2>
<p>New accounts start with a free trial. If we start charging we will show the price in the app and ask for your agreement first; nothing is charged without it. You can cancel any time in the app.</p>

<h2>5. Availability</h2>
<p>We work to keep Munshi running, but phone networks, AI and voice providers can fail, and a call may sometimes not be answered or may be answered badly. We do not promise uninterrupted service. Keep your phone able to ring so that a call is never lost.</p>

<h2>6. Our content and your content</h2>
<p>You keep ownership of your shop information and call records. You allow us to process them to run the service as described in the Privacy Policy. Munshi's software, name and design belong to us.</p>

<h2>7. Ending</h2>
<p>You can delete your account at any time. We may suspend an account that breaks these terms, is used to harm others, or is not paid for once payment starts.</p>

<h2>8. Liability</h2>
<p>To the fullest extent the law allows, we are not liable for lost business, lost calls or indirect losses, and our total liability for anything arising from the service is limited to the amount you paid us in the three months before the claim. Nothing here limits liability that cannot be limited by law.</p>

<h2>9. Law and disputes</h2>
<p>These terms follow the laws of India. Courts at {ph("LEGAL_JURISDICTION")} have jurisdiction.</p>

<h2>10. Contact</h2>
<p>{ph("SUPPORT_EMAIL")}. Complaints about your data: see the grievance officer in the <a href="/legal/privacy#9">Privacy Policy</a>.</p>"""
    hi = "Munshi एक AI सहायक है और उससे गलती हो सकती है, इसलिए नोट पढ़कर ग्राहकों को कॉल करें। वह आपकी तरफ़ से छूट, उधार, समय या पैसे का वादा नहीं करता। दुकान की जानकारी सही रखना आपकी ज़िम्मेदारी है, और ग्राहकों को बताना कि कॉल AI उठाता है (Munshi हर कॉल की शुरुआत में बताता है)। खाता आप कभी भी मिटा सकते हैं।"
    return page("Terms of Service", body, hi)


def delete_account() -> str:
    body = f"""
<h2 id="delete">Delete your account and data</h2>
<p><b>In the app (fastest):</b> open Munshi, go to <b>Settings</b>, tap <b>Delete my account and data</b>, and confirm. Your shop, contacts, rates, calls and messages are deleted at once, and you are signed out. It cannot be undone, so use <b>Download my data</b> first if you want a copy.</p>
<p><b>If you cannot open the app:</b> email {ph("SUPPORT_EMAIL")} from any address with the subject "Delete my Munshi account" and the mobile number you sign in with. We will check it is you by sending a code to that number, then delete the account within 30 days (usually much sooner).</p>
<h2>What is deleted</h2>
<ul><li>Your profile, shop information, rates and imported contacts.</li><li>All call transcripts, notes, to-do lists and messages.</li><li>Your signed-in sessions and sign-in codes.</li></ul>
<h2>What may remain</h2>
<ul><li>Backups, if any, are overwritten within 35 days.</li><li>Records the law requires us to keep (for example billing records once billing starts).</li><li>A plain note that an account was deleted, with no personal details, in our activity log.</li></ul>
<h2>If you are a caller</h2>
<p>To have a call about you removed, tell the shop owner, or email {ph("SUPPORT_EMAIL")} with the number you called from and the date. See the <a href="/legal/privacy">Privacy Policy</a>."""
    hi = "ऐप खोलें, सेटिंग में जाएँ और “खाता और डेटा मिटाएँ” दबाएँ। आपकी दुकान, संपर्क, रेट और सारी कॉल तुरंत मिट जाती हैं। ऐप न खुले तो ईमेल से मोबाइल नंबर बताकर खाता मिटवाएँ।"
    return page("Delete your account", body, hi)


def index() -> str:
    return page("Legal", '<ul><li><a href="/legal/privacy">Privacy Policy</a></li><li><a href="/legal/terms">Terms of Service</a></li><li><a href="/legal/delete-account">Delete your account</a></li></ul>')
