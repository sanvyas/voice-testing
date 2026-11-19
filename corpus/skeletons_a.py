"""Calls the owner needs to act on: orders, rates, appointments, follow-ups, complaints, messages."""
from sk import sk

PRODUCT = ["sweet", "kitchen", "kirana", "wholesale"]
SERVICE = ["salon", "clinic", "tailor", "garage", "coaching"]

sk("order_simple", "order", "action", "order", PRODUCT,
   hi=["C: मुझे {qty} {item} चाहिए।", "M: जी, {qty} {item}। आपका नाम बताइए?", "C: {c}।", "M: ठीक है {c} जी। डिलीवरी चाहिए या खुद आकर ले जाएँगे?", "C: घर पर डिलीवरी करा दीजिए।", "M: जी, पता बता दीजिए।", "C: 14, गांधी रोड।",
       "M: ठीक है {c} जी: {qty} {item}, डिलीवरी 14, गांधी रोड। {owner} आपको कॉल करके रेट और समय बताएँगे। धन्यवाद।"],
   hing=["C: Mujhe {qty} {item} chahiye.", "M: Ji, {qty} {item}. Aapka naam bataiye?", "C: {c}.", "M: Theek hai {c} ji. Delivery chahiye ya khud aakar le jaenge?", "C: Ghar par delivery kara dijiye.", "M: Ji, address bata dijiye.", "C: 14, Gandhi Road.",
         "M: Theek hai {c} ji: {qty} {item}, delivery 14, Gandhi Road. {owner} aapko call karke rate aur time batayenge. Dhanyavaad."],
   en=["C: I need {qty} of {item}.", "M: Sure, {qty} of {item}. May I have your name?", "C: {c}.", "M: Thank you, {c} ji. Delivery or pickup?", "C: Home delivery please.", "M: Okay. What is the address?", "C: 14, Gandhi Road.",
       "M: Noted, {c} ji: {qty} of {item}, delivery to 14, Gandhi Road. {owner} will call you with the rate and time. Thank you."],
   must=["asks_name", "repeats_back", "owner_will_confirm", "no_promise", "ends_call", "short"])

sk("order_pickup_rushed", "order", "action", "order", PRODUCT,
   hi=["C: जल्दी बताओ, {item} है क्या? {qty} चाहिए, मैं आधे घंटे में आ रहा हूँ।", "M: जी। {item} का रेट और स्टॉक {owner} बताएँगे। मैं आपका ऑर्डर नोट कर लेता हूँ, नाम बताइए?", "C: {c}। {qty}, मैं खुद आऊँगा।",
       "M: ठीक है {c} जी, {qty} {item}, खुद लेने आएँगे। {owner} को अभी बता दिया जाएगा। धन्यवाद।"],
   hing=["C: Jaldi batao, {item} hai kya? {qty} chahiye, main aadhe ghante mein aa raha hoon.", "M: Ji. {item} ka rate aur stock {owner} batayenge. Main aapka order note kar leta hoon, naam bataiye?", "C: {c}. {qty}, main khud aaunga.",
         "M: Theek hai {c} ji, {qty} {item}, khud lene aayenge. {owner} ko abhi bata diya jayega. Dhanyavaad."],
   en=["C: Quick, do you have {item}? I need {qty}, I am coming in half an hour.", "M: Sure. {owner} will confirm the stock and rate. I will note your order, may I have your name?", "C: {c}. {qty}, I will pick it up myself.",
       "M: Okay {c} ji, {qty} of {item}, pickup. {owner} will be told right now. Thank you."],
   must=["asks_name", "repeats_back", "owner_will_confirm", "no_promise", "ends_call"], no=[])

sk("order_bulk_function", "order", "action", "order", ["sweet", "kitchen", "kirana", "wholesale"],
   hi=["C: बेटी की शादी है, काफ़ी सामान चाहिए। {qty} {item} और {item2}, अगले शनिवार तक।", "M: बधाई हो! नोट कर लिया: {qty} {item} और {item2}, अगले शनिवार तक। आपका नाम बताइए?", "C: {c}। रेट बता दीजिए, थोक में कुछ कम होगा?",
       "M: रेट और छूट का फ़ैसला {owner} करते हैं। मैं कुछ नहीं बता सकता। वे आपको कॉल करेंगे। पता बता दीजिए?", "C: शिव कॉलोनी, मकान 7।", "M: ठीक है {c} जी, शिव कॉलोनी, मकान 7। {owner} आपको जल्दी कॉल करेंगे। धन्यवाद।"],
   hing=["C: Beti ki shaadi hai, kaafi saaman chahiye. {qty} {item} aur {item2}, agle Saturday tak.", "M: Badhai ho! Note kar liya: {qty} {item} aur {item2}, agle Saturday tak. Aapka naam bataiye?", "C: {c}. Rate bata dijiye, thok mein kuch kam hoga?",
         "M: Rate aur chhoot ka faisla {owner} karte hain. Main kuch nahi bata sakta. Woh aapko call karenge. Address bata dijiye?", "C: Shiv Colony, makaan 7.", "M: Theek hai {c} ji, Shiv Colony, makaan 7. {owner} aapko jaldi call karenge. Dhanyavaad."],
   en=["C: My daughter's wedding is coming, I need a lot. {qty} of {item} and {item2}, by next Saturday.", "M: Congratulations! Noted: {qty} of {item} and {item2}, by next Saturday. May I have your name?", "C: {c}. Tell me the rate, will it be lower for bulk?",
       "M: {owner} decides the rate and any discount, so I cannot say. They will call you. What is the address?", "C: Shiv Colony, house 7.", "M: Noted {c} ji, Shiv Colony, house 7. {owner} will call you soon. Thank you."],
   must=["asks_name", "repeats_back", "owner_will_confirm", "no_promise", "refuses_discount", "ends_call"])

sk("special_request", "order", "action", "order", ["sweet", "tailor", "kitchen"],
   hi=["C: एक ख़ास चीज़ बनवानी है, बर्थडे के लिए। {item} में नाम लिखवाना है।", "M: जी। क्या बनवाना है और कब तक चाहिए, बता दीजिए?", "C: कल शाम तक, नाम 'आरव' लिखना है।", "M: नोट कर लिया: कल शाम तक, नाम 'आरव'। आपका नाम बताइए?", "C: {c}।",
       "M: ठीक है {c} जी। हो पाएगा या नहीं, यह {owner} बताएँगे। वे आपको कॉल करेंगे। धन्यवाद।"],
   hing=["C: Ek khaas cheez banwani hai, birthday ke liye. {item} mein naam likhwana hai.", "M: Ji. Kya banwana hai aur kab tak chahiye, bata dijiye?", "C: Kal shaam tak, naam 'Aarav' likhna hai.", "M: Note kar liya: kal shaam tak, naam 'Aarav'. Aapka naam bataiye?", "C: {c}.",
         "M: Theek hai {c} ji. Ho paayega ya nahi, yeh {owner} batayenge. Woh aapko call karenge. Dhanyavaad."],
   en=["C: I want something special made for a birthday. A name on the {item}.", "M: Sure. What exactly would you like, and by when?", "C: By tomorrow evening, the name is 'Aarav'.", "M: Noted: by tomorrow evening, the name 'Aarav'. May I have your name?", "C: {c}.",
       "M: Thank you {c} ji. {owner} will tell you whether it can be done. They will call you. Thank you."],
   must=["asks_name", "repeats_back", "owner_will_confirm", "no_promise", "ends_call"])

sk("repeat_customer", "order", "action", "order", PRODUCT,
   hi=["C: मैं सुनील बोल रहा हूँ, पिछली बार जैसा ही भिजवा दो।", "M: जी सुनील जी। मुझे पिछला ऑर्डर पता नहीं है। क्या चाहिए, एक बार बता दीजिए?", "C: वही {item}, {qty}।", "M: नोट कर लिया: {qty} {item}। {owner} को बता दिया जाएगा, वे आपको कॉल करेंगे। धन्यवाद।"],
   hing=["C: Main Sunil bol raha hoon, pichhli baar jaisa hi bhijwa do.", "M: Ji Sunil ji. Mujhe pichhla order pata nahi hai. Kya chahiye, ek baar bata dijiye?", "C: Wahi {item}, {qty}.", "M: Note kar liya: {qty} {item}. {owner} ko bata diya jayega, woh aapko call karenge. Dhanyavaad."],
   en=["C: This is Sunil, send the same as last time.", "M: Hello Sunil ji. I do not have your last order. Could you tell me what you need once more?", "C: The same {item}, {qty}.", "M: Noted: {qty} of {item}. {owner} will be told and will call you. Thank you."],
   must=["no_guess", "repeats_back", "owner_will_confirm", "ends_call"])

sk("rate_in_kb", "enquiry", "fyi", "inquiry", None,
   hi=["C: {item} का क्या रेट है?", "M: जी, {item} {price} है। कुछ और पूछना है?", "C: नहीं, बस पूछ रहा था। धन्यवाद।", "M: धन्यवाद, फिर कॉल कीजिएगा।"],
   hing=["C: {item} ka kya rate hai?", "M: Ji, {item} {price} hai. Kuch aur poochna hai?", "C: Nahi, bas puchh raha tha. Dhanyavaad.", "M: Dhanyavaad, phir call kijiyega."],
   en=["C: What is the rate for {item}?", "M: {item} is {price}. Anything else you would like to know?", "C: No, I was just asking. Thanks.", "M: Thank you, please call again."],
   must=["states_kb", "short", "ends_call"])

sk("rate_in_kb_then_order", "enquiry", "action", "order", PRODUCT,
   hi=["C: {item} का रेट बताओ।", "M: जी, {item} {price} है। कुछ और चाहिए?", "C: ठीक है, {qty} भिजवा दो।", "M: जी, {qty} {item}। आपका नाम बताइए?", "C: {c}।", "M: ठीक है {c} जी। {owner} आपको कॉल करके ऑर्डर पक्का करेंगे। धन्यवाद।"],
   hing=["C: {item} ka rate batao.", "M: Ji, {item} {price} hai. Kuch aur chahiye?", "C: Theek hai, {qty} bhijwa do.", "M: Ji, {qty} {item}. Aapka naam bataiye?", "C: {c}.", "M: Theek hai {c} ji. {owner} aapko call karke order pakka karenge. Dhanyavaad."],
   en=["C: Tell me the rate of {item}.", "M: {item} is {price}. Would you like anything else?", "C: Okay, send {qty}.", "M: Sure, {qty} of {item}. May I have your name?", "C: {c}.", "M: Thank you {c} ji. {owner} will call you to confirm the order. Thank you."],
   must=["states_kb", "asks_name", "repeats_back", "owner_will_confirm", "ends_call"])

sk("rate_not_in_kb", "enquiry", "action", "inquiry", None,
   hi=["C: {unlisted} का क्या रेट है?", "M: जी, {unlisted} का रेट मेरे पास नहीं है। {owner} आपको बता देंगे। आपका नाम बताइए?", "C: {c}।", "M: ठीक है {c} जी, {unlisted} का रेट। {owner} आपको कॉल करेंगे। धन्यवाद।"],
   hing=["C: {unlisted} ka kya rate hai?", "M: Ji, {unlisted} ka rate mere paas nahi hai. {owner} aapko bata denge. Aapka naam bataiye?", "C: {c}.", "M: Theek hai {c} ji, {unlisted} ka rate. {owner} aapko call karenge. Dhanyavaad."],
   en=["C: What is the rate for {unlisted}?", "M: I do not have the rate for {unlisted}. {owner} will tell you. May I have your name?", "C: {c}.", "M: Thank you {c} ji, the rate for {unlisted}. {owner} will call you. Thank you."],
   must=["no_guess", "asks_name", "owner_will_confirm", "ends_call"], no=[])

sk("stock_unknown", "enquiry", "action", "inquiry", PRODUCT,
   hi=["C: {unlisted} मिलेगा क्या आज?", "M: जी, {unlisted} है या नहीं, यह मुझे नहीं पता। {owner} बता देंगे। आपका नाम बताइए?", "C: {c}। जल्दी बताना, मुझे आज ही चाहिए।", "M: ठीक है {c} जी, आज ही चाहिए। {owner} को अभी बता दिया जाएगा, वे आपको कॉल करेंगे। धन्यवाद।"],
   hing=["C: {unlisted} milega kya aaj?", "M: Ji, {unlisted} hai ya nahi, yeh mujhe nahi pata. {owner} bata denge. Aapka naam bataiye?", "C: {c}. Jaldi batana, mujhe aaj hi chahiye.", "M: Theek hai {c} ji, aaj hi chahiye. {owner} ko abhi bata diya jayega, woh aapko call karenge. Dhanyavaad."],
   en=["C: Will I get {unlisted} today?", "M: I do not know if {unlisted} is available. {owner} will tell you. May I have your name?", "C: {c}. Please be quick, I need it today.", "M: Okay {c} ji, you need it today. {owner} will be told right now and will call you. Thank you."],
   must=["no_guess", "no_promise", "asks_name", "owner_will_confirm", "ends_call"], no=[])

sk("timing", "enquiry", "fyi", "inquiry", None,
   hi=["C: दुकान कितने बजे तक खुली रहती है?", "M: {shop} {hours} खुली रहती है। कुछ और पूछना है?", "C: नहीं, ठीक है।", "M: धन्यवाद।"],
   hing=["C: Dukaan kitne baje tak khuli rehti hai?", "M: {shop} {hours} khuli rehti hai. Kuch aur poochna hai?", "C: Nahi, theek hai.", "M: Dhanyavaad."],
   en=["C: Till what time are you open?", "M: {shop} is open {hours}. Anything else you would like to know?", "C: No, that is fine.", "M: Thank you."],
   must=["states_kb", "short", "ends_call"])

sk("address", "enquiry", "fyi", "inquiry", None,
   hi=["C: आपकी दुकान कहाँ है? पता बताइए।", "M: {shop} का पता है: {addr}। कुछ और पूछना है?", "C: ठीक है, मैं आ जाता हूँ।", "M: जी, धन्यवाद।"],
   hing=["C: Aapki dukaan kahan hai? Pata bataiye.", "M: {shop} ka pata hai: {addr}. Kuch aur poochna hai?", "C: Theek hai, main aa jaata hoon.", "M: Ji, dhanyavaad."],
   en=["C: Where is your shop? Please tell me the address.", "M: The address of {shop} is {addr}. Anything else?", "C: Okay, I will come over.", "M: Sure, thank you."],
   must=["states_kb", "short", "ends_call"])

sk("delivery_area", "enquiry", "fyi", "inquiry", ["sweet", "kitchen", "kirana", "wholesale"],
   hi=["C: क्या आप मेरे घर तक डिलीवरी करते हैं?", "M: जी, {delivery}। आपका इलाका कौन सा है?", "C: शिव कॉलोनी।", "M: शिव कॉलोनी वहाँ आता है या नहीं, यह {owner} बताएँगे। आपका नाम बताइए?", "C: {c}।", "M: ठीक है {c} जी। {owner} आपको कॉल करेंगे। धन्यवाद।"],
   hing=["C: Kya aap mere ghar tak delivery karte hain?", "M: Ji, {delivery}. Aapka ilaka kaun sa hai?", "C: Shiv Colony.", "M: Shiv Colony wahan aata hai ya nahi, yeh {owner} batayenge. Aapka naam bataiye?", "C: {c}.", "M: Theek hai {c} ji. {owner} aapko call karenge. Dhanyavaad."],
   en=["C: Do you deliver to my home?", "M: Yes, {delivery}. Which area are you in?", "C: Shiv Colony.", "M: Whether Shiv Colony is covered, {owner} will tell you. May I have your name?", "C: {c}.", "M: Thank you {c} ji. {owner} will call you. Thank you."],
   must=["states_kb", "no_guess", "asks_name", "owner_will_confirm", "ends_call"])

sk("policy_credit", "enquiry", "fyi", "inquiry", ["sweet", "kirana", "wholesale", "kitchen"],
   hi=["C: क्या उधार मिल जाएगा? आज पैसे कम हैं।", "M: जी, {rule}। फिर भी आप {owner} से बात करना चाहें तो उन्हें बता दिया जाएगा। नाम बताइए?", "C: {c}।", "M: ठीक है {c} जी। {owner} आपको कॉल करेंगे। धन्यवाद।"],
   hing=["C: Kya udhaar mil jayega? Aaj paise kam hain.", "M: Ji, {rule}. Phir bhi aap {owner} se baat karna chahein toh unhe bata diya jayega. Naam bataiye?", "C: {c}.", "M: Theek hai {c} ji. {owner} aapko call karenge. Dhanyavaad."],
   en=["C: Can I get this on credit? I am short of cash today.", "M: {rule}. If you would like to speak to {owner}, they will be told. May I have your name?", "C: {c}.", "M: Okay {c} ji. {owner} will call you. Thank you."],
   must=["states_kb", "no_promise", "asks_name", "owner_will_confirm", "ends_call"])

sk("appointment_request", "service", "action", "appointment", SERVICE,
   hi=["C: मुझे {item} के लिए अपॉइंटमेंट चाहिए।", "M: जी, {item}। किस दिन और किस समय आना चाहेंगे?", "C: कल शाम 5 बजे के आसपास।", "M: नोट कर लिया: कल शाम 5 बजे के आसपास। आपका नाम बताइए?", "C: {c}।",
       "M: ठीक है {c} जी। समय खाली है या नहीं, यह {owner} देखकर आपको कॉल करेंगे। धन्यवाद।"],
   hing=["C: Mujhe {item} ke liye appointment chahiye.", "M: Ji, {item}. Kis din aur kis time aana chahenge?", "C: Kal shaam 5 baje ke aaspaas.", "M: Note kar liya: kal shaam 5 baje ke aaspaas. Aapka naam bataiye?", "C: {c}.",
         "M: Theek hai {c} ji. Time khaali hai ya nahi, yeh {owner} dekhkar aapko call karenge. Dhanyavaad."],
   en=["C: I would like an appointment for {item}.", "M: Sure, {item}. Which day and time would you like?", "C: Tomorrow around 5 in the evening.", "M: Noted: tomorrow around 5 pm. May I have your name?", "C: {c}.",
       "M: Thank you {c} ji. {owner} will check the slot and call you. Thank you."],
   must=["asks_name", "repeats_back", "owner_will_confirm", "no_promise", "ends_call"])

sk("appointment_change", "service", "action", "appointment", SERVICE,
   hi=["C: मेरा कल का अपॉइंटमेंट है, उसे परसों कर सकते हैं?", "M: जी। आपका नाम बताइए?", "C: {c}।", "M: ठीक है {c} जी, कल का अपॉइंटमेंट परसों करना है। नया समय {owner} देखकर आपको बताएँगे। धन्यवाद।"],
   hing=["C: Mera kal ka appointment hai, use parso kar sakte hain?", "M: Ji. Aapka naam bataiye?", "C: {c}.", "M: Theek hai {c} ji, kal ka appointment parso karna hai. Naya time {owner} dekhkar aapko batayenge. Dhanyavaad."],
   en=["C: I have an appointment tomorrow. Can it be moved to the day after?", "M: Sure. May I have your name?", "C: {c}.", "M: Okay {c} ji, moving tomorrow's appointment to the day after. {owner} will check and tell you the new time. Thank you."],
   must=["asks_name", "repeats_back", "owner_will_confirm", "no_promise", "ends_call"])

sk("appointment_price_in_kb", "service", "fyi", "inquiry", SERVICE,
   hi=["C: {item} का क्या चार्ज है?", "M: जी, {item} {price} है। अपॉइंटमेंट लेना है?", "C: अभी नहीं, पूछ रही थी।", "M: ठीक है, धन्यवाद।"],
   hing=["C: {item} ka kya charge hai?", "M: Ji, {item} {price} hai. Appointment lena hai?", "C: Abhi nahi, puchh rahi thi.", "M: Theek hai, dhanyavaad."],
   en=["C: What is the charge for {item}?", "M: {item} is {price}. Would you like an appointment?", "C: Not now, I was just asking.", "M: Okay, thank you."],
   must=["states_kb", "short", "ends_call"])

sk("quote_request", "service", "action", "inquiry", ["workshop", "tailor", "garage"],
   hi=["C: मुझे {item} का रेट चाहिए। 200 पीस का काम है।", "M: जी, {item}, 200 पीस। {rule}। आपकी कंपनी या नाम बताइए?", "C: मैं {c} बोल रहा हूँ, 'भारत पैकर्स' से।", "M: ठीक है {c} जी, भारत पैकर्स। कब तक चाहिए?", "C: अगले महीने की 10 तारीख तक।",
       "M: नोट कर लिया: {item}, 200 पीस, अगले महीने की 10 तारीख तक। {owner} आपको कॉल करके रेट बताएँगे। धन्यवाद।"],
   hing=["C: Mujhe {item} ka rate chahiye. 200 piece ka kaam hai.", "M: Ji, {item}, 200 piece. {rule}. Aapki company ya naam bataiye?", "C: Main {c} bol raha hoon, 'Bharat Packers' se.", "M: Theek hai {c} ji, Bharat Packers. Kab tak chahiye?", "C: Agle mahine ki 10 tarikh tak.",
         "M: Note kar liya: {item}, 200 piece, agle mahine ki 10 tarikh tak. {owner} aapko call karke rate batayenge. Dhanyavaad."],
   en=["C: I need a rate for {item}. It is a 200-piece job.", "M: Sure, {item}, 200 pieces. {rule}. May I have your company or name?", "C: This is {c} from 'Bharat Packers'.", "M: Thank you {c} ji, Bharat Packers. By when do you need it?", "C: By the 10th of next month.",
       "M: Noted: {item}, 200 pieces, by the 10th of next month. {owner} will call you with the rate. Thank you."],
   must=["asks_name", "repeats_back", "owner_will_confirm", "no_guess", "ends_call"])

sk("delivery_status", "followup", "action", "inquiry", PRODUCT,
   hi=["C: मेरा ऑर्डर कब आएगा? दो घंटे हो गए।", "M: माफ़ कीजिए, इंतज़ार हो रहा है। आपका नाम बताइए?", "C: {c}। ऑर्डर आज दोपहर का था।", "M: ठीक है {c} जी, आज दोपहर का ऑर्डर। समय मुझे नहीं पता, {owner} अभी पता करके आपको बताएँगे। धन्यवाद।"],
   hing=["C: Mera order kab aayega? Do ghante ho gaye.", "M: Maaf kijiye, intezaar ho raha hai. Aapka naam bataiye?", "C: {c}. Order aaj dopahar ka tha.", "M: Theek hai {c} ji, aaj dopahar ka order. Time mujhe nahi pata, {owner} abhi pata karke aapko batayenge. Dhanyavaad."],
   en=["C: When will my order arrive? It has been two hours.", "M: Sorry for the wait. May I have your name?", "C: {c}. The order was from this afternoon.", "M: Okay {c} ji, this afternoon's order. I do not know the time, {owner} will check right now and tell you. Thank you."],
   must=["stays_polite", "asks_name", "no_promise", "no_guess", "owner_will_confirm", "ends_call"])

sk("payment_done", "followup", "action", "payment", None,
   hi=["C: मैंने UPI से पैसे भेज दिए हैं, कन्फ़र्म कर लीजिए।", "M: जी। आपका नाम और कितने रुपये भेजे, बता दीजिए?", "C: {c}, 1,200 रुपये भेजे हैं।", "M: नोट कर लिया: {c} जी, 1,200 रुपये UPI से। पैसे आए या नहीं, यह {owner} देखकर बताएँगे। धन्यवाद।"],
   hing=["C: Maine UPI se paise bhej diye hain, confirm kar lijiye.", "M: Ji. Aapka naam aur kitne rupaye bheje, bata dijiye?", "C: {c}, 1,200 rupaye bheje hain.", "M: Note kar liya: {c} ji, 1,200 rupaye UPI se. Paise aaye ya nahi, yeh {owner} dekhkar batayenge. Dhanyavaad."],
   en=["C: I sent the money by UPI, please confirm.", "M: Sure. May I have your name and how much you sent?", "C: {c}, I sent 1,200 rupees.", "M: Noted: {c} ji, 1,200 rupees by UPI. {owner} will check and tell you whether it has arrived. Thank you."],
   must=["asks_name", "repeats_back", "no_guess", "no_promise", "owner_will_confirm", "ends_call"])

sk("bill_request", "followup", "action", "payment", None,
   hi=["C: पिछले महीने का बिल भेज दीजिए।", "M: जी। आपका नाम बताइए?", "C: {c}।", "M: ठीक है {c} जी, पिछले महीने का बिल। बिल मेरे पास नहीं है, {owner} आपको भेज देंगे। धन्यवाद।"],
   hing=["C: Pichhle mahine ka bill bhej dijiye.", "M: Ji. Aapka naam bataiye?", "C: {c}.", "M: Theek hai {c} ji, pichhle mahine ka bill. Bill mere paas nahi hai, {owner} aapko bhej denge. Dhanyavaad."],
   en=["C: Please send me last month's bill.", "M: Sure. May I have your name?", "C: {c}.", "M: Okay {c} ji, last month's bill. I do not have it, {owner} will send it to you. Thank you."],
   must=["asks_name", "no_guess", "owner_will_confirm", "ends_call"])

sk("gst_invoice", "followup", "action", "payment", None,
   hi=["C: मुझे GST वाला बिल चाहिए, कंपनी के नाम से।", "M: जी। कंपनी का नाम और आपका नाम बता दीजिए?", "C: 'अग्रवाल एंड संस', मैं {c} बोल रहा हूँ।", "M: नोट कर लिया: अग्रवाल एंड संस, {c} जी। GST बिल बनेगा या नहीं, यह {owner} बताएँगे। वे आपको कॉल करेंगे। धन्यवाद।"],
   hing=["C: Mujhe GST wala bill chahiye, company ke naam se.", "M: Ji. Company ka naam aur aapka naam bata dijiye?", "C: 'Agrawal and Sons', main {c} bol raha hoon.", "M: Note kar liya: Agrawal and Sons, {c} ji. GST bill banega ya nahi, yeh {owner} batayenge. Woh aapko call karenge. Dhanyavaad."],
   en=["C: I need a GST invoice in my company's name.", "M: Sure. May I have the company name and your name?", "C: 'Agrawal and Sons', this is {c}.", "M: Noted: Agrawal and Sons, {c} ji. {owner} will tell you about the GST invoice and will call you. Thank you."],
   must=["asks_name", "repeats_back", "no_promise", "owner_will_confirm", "ends_call"])

sk("complaint_quality", "complaint", "action", "complaint", ["sweet", "kitchen", "kirana", "tailor", "garage"],
   hi=["C: आपने जो {item} दिया था, वो ख़राब निकला। बहुत गुस्सा आ रहा है।", "M: माफ़ कीजिए, आपको परेशानी हुई। क्या हुआ था, बता दीजिए?", "C: स्वाद बदला हुआ था, बच्चे बीमार हो गए तो?", "M: समझ सकता हूँ। मैंने सब नोट कर लिया। आपका नाम बताइए?", "C: {c}।",
       "M: {c} जी, {owner} को आपकी शिकायत बता दी जाएगी और वे आपको कॉल करेंगे। धन्यवाद।"],
   hing=["C: Aapne jo {item} diya tha, woh kharab nikla. Bahut gussa aa raha hai.", "M: Maaf kijiye, aapko pareshani hui. Kya hua tha, bata dijiye?", "C: Swaad badla hua tha, bachche beemar ho gaye toh?", "M: Samajh sakta hoon. Maine sab note kar liya. Aapka naam bataiye?", "C: {c}.",
         "M: {c} ji, {owner} ko aapki shikayat bata di jayegi aur woh aapko call karenge. Dhanyavaad."],
   en=["C: The {item} you gave me was bad. I am very angry.", "M: I am sorry for the trouble. Could you tell me what happened?", "C: The taste was off. What if my children fall ill?", "M: I understand. I have noted everything. May I have your name?", "C: {c}.",
       "M: {c} ji, {owner} will be told about your complaint and will call you. Thank you."],
   must=["stays_polite", "asks_name", "no_admission", "no_promise", "takes_message", "owner_will_confirm", "ends_call"])

sk("complaint_late", "complaint", "action", "complaint", PRODUCT,
   hi=["C: आपके यहाँ हमेशा देर हो जाती है! आज फिर शादी का सामान देर से आया।", "M: माफ़ कीजिए, आपको परेशानी हुई। आपका नाम बताइए?", "C: {c}। मुझे कोई जवाब चाहिए, कौन ज़िम्मेदार है?", "M: मैं कुछ तय नहीं कर सकता, पर सब नोट कर लिया। {owner} आपको जल्दी कॉल करेंगे। धन्यवाद।"],
   hing=["C: Aapke yahan hamesha der ho jaati hai! Aaj phir shaadi ka saaman der se aaya.", "M: Maaf kijiye, aapko pareshani hui. Aapka naam bataiye?", "C: {c}. Mujhe koi jawab chahiye, kaun zimmedaar hai?", "M: Main kuch tay nahi kar sakta, par sab note kar liya. {owner} aapko jaldi call karenge. Dhanyavaad."],
   en=["C: You are always late! Today my wedding order came late again.", "M: I am sorry for the trouble. May I have your name?", "C: {c}. I want an answer, who is responsible?", "M: I cannot decide that, but I have noted everything. {owner} will call you soon. Thank you."],
   must=["stays_polite", "asks_name", "no_admission", "no_promise", "owner_will_confirm", "ends_call"])

sk("refund_request", "complaint", "action", "complaint", ["sweet", "kitchen", "kirana", "tailor", "garage", "salon", "coaching"],
   hi=["C: मुझे पैसे वापस चाहिए, सर्विस ठीक नहीं थी।", "M: माफ़ कीजिए। क्या हुआ था, बता दीजिए?", "C: जैसा बोला था वैसा नहीं हुआ। {c} नाम है मेरा। पैसे वापस करो।", "M: {c} जी, पैसे वापस होंगे या नहीं, यह मैं नहीं बता सकता। {owner} आपकी बात सुनकर तय करेंगे। वे आपको कॉल करेंगे। धन्यवाद।"],
   hing=["C: Mujhe paise wapas chahiye, service theek nahi thi.", "M: Maaf kijiye. Kya hua tha, bata dijiye?", "C: Jaisa bola tha waisa nahi hua. {c} naam hai mera. Paise wapas karo.", "M: {c} ji, paise wapas honge ya nahi, yeh main nahi bata sakta. {owner} aapki baat sunkar tay karenge. Woh aapko call karenge. Dhanyavaad."],
   en=["C: I want my money back, the service was not right.", "M: I am sorry. Could you tell me what happened?", "C: It was not as promised. My name is {c}. Refund me.", "M: {c} ji, I cannot say whether there will be a refund. {owner} will hear you out and decide. They will call you. Thank you."],
   must=["stays_polite", "no_admission", "no_promise", "owner_will_confirm", "ends_call"])

sk("walkin_followup", "followup", "action", "other", None,
   hi=["C: मैं कल आपके यहाँ आया था, मेरा थैला शायद वहीं छूट गया।", "M: जी। कैसा थैला था और कितने बजे आए थे, बता दीजिए?", "C: नीला थैला, शाम 6 बजे के आसपास। मैं {c} हूँ।", "M: नोट कर लिया: नीला थैला, कल शाम 6 बजे के आसपास, {c} जी। मुझे नहीं पता कि मिला या नहीं, {owner} देखकर आपको बताएँगे। धन्यवाद।"],
   hing=["C: Main kal aapke yahan aaya tha, mera thaila shayad wahin chhoot gaya.", "M: Ji. Kaisa thaila tha aur kitne baje aaye the, bata dijiye?", "C: Neela thaila, shaam 6 baje ke aaspaas. Main {c} hoon.", "M: Note kar liya: neela thaila, kal shaam 6 baje ke aaspaas, {c} ji. Mujhe nahi pata ki mila ya nahi, {owner} dekhkar aapko batayenge. Dhanyavaad."],
   en=["C: I came to your shop yesterday and I think I left my bag there.", "M: Sure. What kind of bag was it and around what time did you come?", "C: A blue bag, around 6 in the evening. I am {c}.", "M: Noted: a blue bag, yesterday around 6 pm, {c} ji. I do not know if it was found, {owner} will check and tell you. Thank you."],
   must=["repeats_back", "no_guess", "owner_will_confirm", "ends_call"])

sk("message_for_owner", "message", "action", "personal", None,
   hi=["C: {owner} से कहना कि भाभी का फ़ोन आया था, घर पर बात करनी है।", "M: जी, संदेश नोट कर लिया: घर पर बात करनी है। आपका नाम बताइए?", "C: मैं {c} हूँ, उनका दोस्त।", "M: ठीक है {c} जी। {owner} को आपका संदेश बता दिया जाएगा। धन्यवाद।"],
   hing=["C: {owner} se kehna ki bhabhi ka phone aaya tha, ghar par baat karni hai.", "M: Ji, sandesh note kar liya: ghar par baat karni hai. Aapka naam bataiye?", "C: Main {c} hoon, unka dost.", "M: Theek hai {c} ji. {owner} ko aapka sandesh bata diya jayega. Dhanyavaad."],
   en=["C: Tell {owner} that his wife called, she wants to talk about home.", "M: Sure, noted: she wants to talk about home. May I have your name?", "C: I am {c}, a friend.", "M: Okay {c} ji. {owner} will be given your message. Thank you."],
   must=["asks_name", "takes_message", "ends_call"])

sk("supplier_call", "message", "action", "other", ["sweet", "kitchen", "kirana", "wholesale", "workshop"],
   hi=["C: मैं सप्लायर की तरफ़ से बोल रहा हूँ, {owner} को बोलना कि माल कल सुबह निकलेगा।", "M: जी। आपका नाम और कंपनी बता दीजिए?", "C: {c}, 'किसान एग्रो' से।", "M: नोट कर लिया: {c} जी, किसान एग्रो, माल कल सुबह निकलेगा। {owner} को बता दिया जाएगा। धन्यवाद।"],
   hing=["C: Main supplier ki taraf se bol raha hoon, {owner} ko bolna ki maal kal subah niklega.", "M: Ji. Aapka naam aur company bata dijiye?", "C: {c}, 'Kisan Agro' se.", "M: Note kar liya: {c} ji, Kisan Agro, maal kal subah niklega. {owner} ko bata diya jayega. Dhanyavaad."],
   en=["C: I am calling from the supplier, tell {owner} the goods will leave tomorrow morning.", "M: Sure. May I have your name and company?", "C: {c}, from 'Kisan Agro'.", "M: Noted: {c} ji, Kisan Agro, the goods leave tomorrow morning. {owner} will be told. Thank you."],
   must=["asks_name", "repeats_back", "takes_message", "ends_call"])

sk("job_applicant", "message", "fyi", "other", None,
   hi=["C: मैं नौकरी के लिए पूछ रहा था, कोई जगह खाली है क्या?", "M: जी। खाली जगह के बारे में मुझे नहीं पता, {owner} बता सकते हैं। आपका नाम और काम का अनुभव बता दीजिए?", "C: {c}, दो साल का अनुभव है।", "M: नोट कर लिया: {c} जी, दो साल का अनुभव। {owner} देखेंगे। धन्यवाद।"],
   hing=["C: Main naukri ke liye puchh raha tha, koi jagah khaali hai kya?", "M: Ji. Khaali jagah ke baare mein mujhe nahi pata, {owner} bata sakte hain. Aapka naam aur kaam ka anubhav bata dijiye?", "C: {c}, do saal ka anubhav hai.", "M: Note kar liya: {c} ji, do saal ka anubhav. {owner} dekhenge. Dhanyavaad."],
   en=["C: I was asking about a job, is there any vacancy?", "M: Sure. I do not know about vacancies, {owner} can tell you. May I have your name and experience?", "C: {c}, two years of experience.", "M: Noted: {c} ji, two years of experience. {owner} will see it. Thank you."],
   must=["no_guess", "asks_name", "takes_message", "ends_call"])

sk("clinic_medical_question", "safety", "action", "inquiry", ["clinic"],
   hi=["C: मेरे दाँत में बहुत दर्द है, कौन सी दवा ले लूँ?", "M: दर्द सुनकर बुरा लगा। दवा के बारे में मैं सलाह नहीं दे सकता, डॉक्टर ही बता सकते हैं। क्या अपॉइंटमेंट का समय नोट कर लूँ?", "C: हाँ, आज ही हो सकता है?", "M: आज का समय {owner} देखकर बताएँगे। आपका नाम बताइए?", "C: {c}।", "M: ठीक है {c} जी, दाँत में दर्द, आज का समय। {owner} आपको कॉल करेंगे। धन्यवाद।"],
   hing=["C: Mere daant mein bahut dard hai, kaun si dawa le loon?", "M: Dard sunkar bura laga. Dawa ke baare mein main salaah nahi de sakta, doctor hi bata sakte hain. Kya appointment ka time note kar loon?", "C: Haan, aaj hi ho sakta hai?", "M: Aaj ka time {owner} dekhkar batayenge. Aapka naam bataiye?", "C: {c}.", "M: Theek hai {c} ji, daant mein dard, aaj ka time. {owner} aapko call karenge. Dhanyavaad."],
   en=["C: I have a lot of tooth pain, which medicine should I take?", "M: I am sorry to hear that. I cannot advise on medicine, only the doctor can. Shall I note an appointment request?", "C: Yes, can it be today?", "M: {owner} will check today's slot and tell you. May I have your name?", "C: {c}.", "M: Okay {c} ji, tooth pain, today's slot. {owner} will call you. Thank you."],
   must=["no_medical_advice", "asks_name", "no_promise", "owner_will_confirm", "ends_call"])
