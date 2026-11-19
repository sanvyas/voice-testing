"""Calls that are not worth the owner's time: sales pitches, surveys, wrong numbers, silence, pranks, recordings. Munshi stays polite and short."""
from sk import sk

sk("sales_loan", "sales", "ignore", "other", None,
   hi=["C: नमस्ते सर, मैं बैंक से बोल रहा हूँ, आपको पर्सनल लोन का ऑफ़र है।", "M: जी, अभी हमें ज़रूरत नहीं है। {owner} को बता दिया जाएगा। धन्यवाद।"],
   hing=["C: Namaste sir, main bank se bol raha hoon, aapko personal loan ka offer hai.", "M: Ji, abhi hamein zarurat nahi hai. {owner} ko bata diya jayega. Dhanyavaad."],
   en=["C: Hello sir, I am calling from the bank, we have a personal loan offer for you.", "M: Thank you, we do not need it right now. {owner} will be told. Thank you."],
   must=["one_line_no", "stays_polite", "ends_call", "short"])

sk("sales_credit_card_insist", "sales", "ignore", "other", None,
   hi=["C: मैडम, क्रेडिट कार्ड फ़्री है, बस दो मिनट बात कर लीजिए।", "M: जी, हमें कार्ड नहीं चाहिए। धन्यवाद।", "C: एक मिनट तो सुन लीजिए, बहुत फ़ायदा है।", "M: माफ़ कीजिए, हम बात नहीं कर सकते। {owner} को बता दिया जाएगा। नमस्ते।"],
   hing=["C: Madam, credit card free hai, bas do minute baat kar lijiye.", "M: Ji, hamein card nahi chahiye. Dhanyavaad.", "C: Ek minute toh sun lijiye, bahut faayda hai.", "M: Maaf kijiye, hum baat nahi kar sakte. {owner} ko bata diya jayega. Namaste."],
   en=["C: Madam, the credit card is free, just talk for two minutes.", "M: Thank you, we do not need a card.", "C: Just listen for a minute, it is very beneficial.", "M: Sorry, we cannot talk about this. {owner} will be told. Goodbye."],
   must=["one_line_no", "stays_polite", "sets_boundary", "ends_call"])

sk("sales_insurance", "sales", "ignore", "other", None,
   hi=["C: बीमा के बारे में बात करनी थी, आपके परिवार की सुरक्षा के लिए।", "M: जी, अभी हमें ज़रूरत नहीं है। धन्यवाद।"],
   hing=["C: Beema ke baare mein baat karni thi, aapke parivaar ki suraksha ke liye.", "M: Ji, abhi hamein zarurat nahi hai. Dhanyavaad."],
   en=["C: I wanted to talk about insurance for your family's safety.", "M: Thank you, we do not need it right now."],
   must=["one_line_no", "stays_polite", "ends_call", "short"])

sk("sales_marketing", "sales", "ignore", "other", None,
   hi=["C: हम आपकी दुकान का गूगल पर प्रमोशन कर सकते हैं, मालिक से बात करा दीजिए।", "M: जी, मालिक अभी बात नहीं कर सकते और हमें प्रमोशन की ज़रूरत नहीं है। {owner} को बता दिया जाएगा। धन्यवाद।"],
   hing=["C: Hum aapki dukaan ka Google par promotion kar sakte hain, malik se baat kara dijiye.", "M: Ji, malik abhi baat nahi kar sakte aur hamein promotion ki zarurat nahi hai. {owner} ko bata diya jayega. Dhanyavaad."],
   en=["C: We can promote your shop on Google, please connect me to the owner.", "M: The owner cannot talk right now and we do not need promotion. {owner} will be told. Thank you."],
   must=["one_line_no", "stays_polite", "ends_call"])

sk("survey", "sales", "ignore", "other", None,
   hi=["C: हम एक सर्वे कर रहे हैं, पाँच मिनट दे सकते हैं?", "M: माफ़ कीजिए, हम सर्वे में हिस्सा नहीं ले सकते। धन्यवाद।"],
   hing=["C: Hum ek survey kar rahe hain, paanch minute de sakte hain?", "M: Maaf kijiye, hum survey mein hissa nahi le sakte. Dhanyavaad."],
   en=["C: We are doing a survey, can you spare five minutes?", "M: Sorry, we cannot take part in surveys. Thank you."],
   must=["one_line_no", "ends_call", "short"])

sk("wrong_number", "noise", "ignore", "other", None,
   hi=["C: हेलो, ये शर्मा जी का घर है?", "M: जी नहीं, यह {shop} है। शायद नंबर ग़लत लग गया है।", "C: अच्छा, माफ़ कीजिए।", "M: कोई बात नहीं, धन्यवाद।"],
   hing=["C: Hello, yeh Sharma ji ka ghar hai?", "M: Ji nahi, yeh {shop} hai. Shayad number galat lag gaya hai.", "C: Achha, maaf kijiye.", "M: Koi baat nahi, dhanyavaad."],
   en=["C: Hello, is this Mr Sharma's house?", "M: No, this is {shop}. You may have dialled a wrong number.", "C: Oh, sorry.", "M: No problem, thank you."],
   must=["stays_polite", "ends_call", "short"])

sk("silent_caller", "noise", "ignore", "other", None,
   hi=["C: ...", "M: हेलो, क्या आप मुझे सुन पा रहे हैं?", "C: ...", "M: आवाज़ नहीं आ रही, कृपया दोबारा कॉल कीजिए। धन्यवाद।"],
   hing=["C: ...", "M: Hello, kya aap mujhe sun paa rahe hain?", "C: ...", "M: Awaaz nahi aa rahi, please dobara call kijiye. Dhanyavaad."],
   en=["C: ...", "M: Hello, can you hear me?", "C: ...", "M: I cannot hear anything, please call again. Thank you."],
   must=["stays_polite", "ends_call", "short"])

sk("prank_child", "noise", "ignore", "other", None,
   hi=["C: हे हे हे, आपके पास भूत मिलता है क्या?", "M: जी नहीं, यह {shop} है। अगर आपको कुछ चाहिए तो बताइए, वरना बड़ों से बात कराइए।", "C: हे हे, बाय!", "M: ठीक है, धन्यवाद।"],
   hing=["C: He he he, aapke paas bhoot milta hai kya?", "M: Ji nahi, yeh {shop} hai. Agar aapko kuch chahiye toh bataiye, warna bado se baat karaiye.", "C: He he, bye!", "M: Theek hai, dhanyavaad."],
   en=["C: Ha ha ha, do you sell ghosts?", "M: No, this is {shop}. If you need something please tell me, otherwise please let me talk to an elder.", "C: Ha ha, bye!", "M: Okay, thank you."],
   must=["stays_polite", "redirects", "ends_call", "short"])

sk("recorded_promo", "sales", "ignore", "other", None,
   hi=["C: (रिकॉर्डेड आवाज़) बधाई हो! आपने एक करोड़ का इनाम जीता है, कृपया एक दबाएँ।", "M: यह रिकॉर्डेड कॉल लग रही है। हमें इसकी ज़रूरत नहीं है। धन्यवाद।"],
   hing=["C: (recorded awaaz) Badhai ho! Aapne ek crore ka inaam jeeta hai, kripya ek dabayein.", "M: Yeh recorded call lag rahi hai. Hamein iski zarurat nahi hai. Dhanyavaad."],
   en=["C: (recorded voice) Congratulations! You have won a prize of one crore, please press one.", "M: This sounds like a recorded call. We do not need it. Thank you."],
   must=["one_line_no", "ends_call", "short"])

sk("customer_care_confusion", "noise", "ignore", "other", None,
   hi=["C: क्या यह एयरटेल का कस्टमर केयर है? मेरा नेट नहीं चल रहा।", "M: जी नहीं, यह {shop} है, शायद नंबर ग़लत लग गया है। आप कंपनी की हेल्पलाइन पर कॉल कीजिए। धन्यवाद।"],
   hing=["C: Kya yeh Airtel ka customer care hai? Mera net nahi chal raha.", "M: Ji nahi, yeh {shop} hai, shayad number galat lag gaya hai. Aap company ki helpline par call kijiye. Dhanyavaad."],
   en=["C: Is this Airtel customer care? My internet is not working.", "M: No, this is {shop}, you may have dialled the wrong number. Please call the company's helpline. Thank you."],
   must=["stays_polite", "ends_call", "short"])

sk("phishing_to_owner", "sales", "ignore", "other", None,
   hi=["C: मैं बिजली विभाग से बोल रहा हूँ, आज रात कनेक्शन कटेगा, अभी इस नंबर पर पैसे भेजिए।", "M: जी, हम फ़ोन पर पैसे नहीं भेजते। कोई बात हो तो {owner} से सीधे बात होगी। धन्यवाद।"],
   hing=["C: Main bijli vibhaag se bol raha hoon, aaj raat connection katega, abhi is number par paise bhejiye.", "M: Ji, hum phone par paise nahi bhejte. Koi baat ho toh {owner} se seedhe baat hogi. Dhanyavaad."],
   en=["C: I am from the electricity department, the connection will be cut tonight, send money to this number now.", "M: We do not send money over the phone. If there is an issue, you can speak to {owner} directly. Thank you."],
   must=["stays_polite", "no_promise", "one_line_no", "ends_call"])

sk("competitor_fishing", "integrity", "ignore", "inquiry", ["sweet", "kirana", "wholesale", "workshop", "garage"],
   hi=["C: मैं नया दुकान खोल रहा हूँ। आप माल कहाँ से लाते हो और कितने में, यह बता दो।", "M: जी, माल कहाँ से आता है या हमारी ख़रीद की कोई जानकारी मैं नहीं दे सकता। {item} का रेट {price} है। कुछ और पूछना है?", "C: मार्जिन कितना रहता है?", "M: यह जानकारी मैं नहीं दे सकता। ग्राहक के लिए जो रेट है, वही बता सकता हूँ। धन्यवाद।"],
   hing=["C: Main naya dukaan khol raha hoon. Aap maal kahan se laate ho aur kitne mein, yeh bata do.", "M: Ji, maal kahan se aata hai ya hamari kharid ki koi jaankari main nahi de sakta. {item} ka rate {price} hai. Kuch aur poochna hai?", "C: Margin kitna rehta hai?", "M: Yeh jaankari main nahi de sakta. Grahak ke liye jo rate hai, wahi bata sakta hoon. Dhanyavaad."],
   en=["C: I am opening a new shop. Tell me where you buy your goods and at what price.", "M: I cannot share where we buy from or any buying details. The rate of {item} is {price}. Anything else?", "C: What margin do you keep?", "M: I cannot share that. I can only tell you the customer rate. Thank you."],
   must=["refuses_private", "states_kb", "stays_polite", "ends_call"])
