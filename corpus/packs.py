"""Ten kinds of small business, each with the shop information ("KB") Munshi may state. Names, prices and hours are invented.

Every price and number Munshi says in a generated conversation must come from here or from what the caller just said.
item = (hindi name, english name, price, unit hindi, unit english, a usual quantity hindi, a usual quantity english)
"""

PACKS = [
    dict(id="sweet", kind="sweet shop", shop=("बाबूजी स्वीट्स", "Babuji Sweets"), owner=("रमेश जी", "Ramesh ji"), addr=("सेक्टर 14 मार्केट, गेट के सामने", "Sector 14 Market, opposite the gate"),
         hours=("रोज़ सुबह 9 से रात 11 बजे तक", "every day, 9 am to 11 pm"), delivery=("3 किमी तक होम डिलीवरी, ₹500 से ऊपर मुफ़्त", "home delivery within 3 km, free above ₹500"), kb_numbers={3, 500, 9, 11},
         items=[("काजू कतली", "kaju katli", 900, "किलो", "kg", "1 किलो", "1 kg"), ("बर्फी", "barfi", 480, "किलो", "kg", "2 किलो", "2 kg"), ("गुलाब जामुन", "gulab jamun", 360, "किलो", "kg", "1 किलो", "1 kg"), ("समोसा", "samosa", 20, "पीस", "piece", "10 पीस", "10 pieces")],
         unlisted=("रसमलाई", "rasmalai"), rule=("उधार नहीं दिया जाता", "no credit is given"), extra=("त्योहार पर ऑर्डर एक दिन पहले लेते हैं", "festival orders are taken a day ahead")),
    dict(id="kitchen", kind="cloud kitchen", shop=("स्वाद रसोई", "Swad Rasoi"), owner=("अनीता जी", "Anita ji"), addr=("गांधी रोड, नेहरू नगर", "Gandhi Road, Nehru Nagar"),
         hours=("रोज़ दोपहर 12 से रात 10 बजे तक", "every day, 12 noon to 10 pm"), delivery=("5 किमी तक डिलीवरी, ₹40 चार्ज", "delivery within 5 km, ₹40 charge"), kb_numbers={5, 40, 12, 10},
         items=[("बिरयानी", "biryani", 220, "प्लेट", "plate", "2 प्लेट", "2 plates"), ("पनीर बटर मसाला", "paneer butter masala", 260, "प्लेट", "plate", "1 प्लेट", "1 plate"), ("रोटी", "roti", 15, "पीस", "piece", "8 पीस", "8 pieces"), ("दाल तड़का", "dal tadka", 160, "प्लेट", "plate", "1 प्लेट", "1 plate")],
         unlisted=("चिकन टिक्का", "chicken tikka"), rule=("ऑर्डर का पैसा डिलीवरी पर या UPI से", "pay on delivery or by UPI"), extra=("बड़े ऑर्डर के लिए 2 घंटे पहले बताएँ", "tell us 2 hours ahead for large orders")),
    dict(id="salon", kind="salon", shop=("ग्लैम सैलून", "Glam Salon"), owner=("नेहा जी", "Neha ji"), addr=("मेन मार्केट, पहली मंज़िल", "Main Market, first floor"),
         hours=("मंगल से रविवार, सुबह 10 से रात 8 बजे तक, सोमवार बंद", "Tuesday to Sunday, 10 am to 8 pm, closed on Monday"), delivery=("", ""), kb_numbers={10, 8},
         items=[("हेयरकट", "haircut", 250, "", "", "", ""), ("फेशियल", "facial", 800, "", "", "", ""), ("हेयर कलर", "hair colour", 1500, "से शुरू", "onwards", "", ""), ("मेहंदी", "mehendi", 500, "से शुरू", "onwards", "", "")],
         unlisted=("बॉडी स्पा", "body spa"), rule=("अपॉइंटमेंट पक्का नेहा जी करती हैं", "Neha ji confirms every appointment"), extra=("दुल्हन के मेकअप के लिए 15 दिन पहले बुक करें", "book bridal makeup 15 days ahead")),
    dict(id="kirana", kind="grocery store", shop=("शर्मा किराना", "Sharma Kirana"), owner=("रमेश जी", "Ramesh ji"), addr=("21, मेन बाज़ार, नेहरू नगर", "21, Main Bazaar, Nehru Nagar"),
         hours=("रोज़ सुबह 8 से रात 9 बजे तक", "every day, 8 am to 9 pm"), delivery=("3 किमी तक होम डिलीवरी, ₹500 से ऊपर मुफ़्त", "home delivery within 3 km, free above ₹500"), kb_numbers={3, 500, 8, 9},
         items=[("आटा", "atta", 42, "किलो", "kg", "10 किलो", "10 kg"), ("चीनी", "sugar", 46, "किलो", "kg", "5 किलो", "5 kg"), ("तूर दाल", "toor dal", 165, "किलो", "kg", "2 किलो", "2 kg"), ("सरसों तेल", "mustard oil", 150, "लीटर", "litre", "2 लीटर", "2 litres")],
         unlisted=("बासमती चावल", "basmati rice"), rule=("उधार नहीं दिया जाता", "no credit is given"), extra=("₹500 से ऊपर के ऑर्डर पर डिलीवरी मुफ़्त", "delivery is free on orders above ₹500")),
    dict(id="wholesale", kind="wholesale trader", shop=("गुप्ता ट्रेडर्स", "Gupta Traders"), owner=("अनिल जी", "Anil ji"), addr=("अनाज मंडी, दुकान 14", "Anaj Mandi, shop 14"),
         hours=("सोमवार से शनिवार, सुबह 7 से शाम 7 बजे तक", "Monday to Saturday, 7 am to 7 pm"), delivery=("शहर में 10 बोरी से ऊपर पर डिलीवरी", "city delivery above 10 bags"), kb_numbers={10, 7},
         items=[("मूंग दाल", "moong dal", 110, "किलो", "kg", "50 किलो", "50 kg"), ("चावल", "rice", 58, "किलो", "kg", "25 किलो", "25 kg"), ("गेहूँ", "wheat", 31, "किलो", "kg", "100 किलो", "100 kg"), ("बेसन", "besan", 82, "किलो", "kg", "20 किलो", "20 kg")],
         unlisted=("चना दाल", "chana dal"), rule=("थोक का रेट मात्रा देखकर अनिल जी बताते हैं", "Anil ji gives bulk rates after seeing the quantity"), extra=("पेमेंट डिलीवरी से पहले", "payment before delivery")),
    dict(id="clinic", kind="dental clinic", shop=("स्माइल डेंटल क्लिनिक", "Smile Dental Clinic"), owner=("डॉक्टर मेहता", "Dr. Mehta"), addr=("रेल रोड, सिटी हॉस्पिटल के पास", "Rail Road, near City Hospital"),
         hours=("सोमवार से शनिवार, शाम 5 से रात 8 बजे तक", "Monday to Saturday, 5 pm to 8 pm"), delivery=("", ""), kb_numbers={5, 8},
         items=[("चेकअप", "check-up", 300, "", "", "", ""), ("दाँत की सफ़ाई", "teeth cleaning", 800, "", "", "", ""), ("एक्स-रे", "X-ray", 200, "", "", "", "")],
         unlisted=("रूट कैनाल", "root canal"), rule=("इलाज की सलाह फ़ोन पर नहीं दी जाती, डॉक्टर मिलकर बताते हैं", "treatment advice is not given on the phone, the doctor advises in person"), extra=("पहली बार आने पर नाम और उम्र बताएँ", "first-time patients should share name and age")),
    dict(id="workshop", kind="small factory", shop=("शक्ति इंजीनियरिंग", "Shakti Engineering"), owner=("सुरेश जी", "Suresh ji"), addr=("प्लॉट 22, इंडस्ट्रियल एरिया फ़ेज़ 2", "Plot 22, Industrial Area Phase 2"),
         hours=("सोमवार से शनिवार, सुबह 9 से शाम 6 बजे तक", "Monday to Saturday, 9 am to 6 pm"), delivery=("", ""), kb_numbers={22, 2, 9, 6},
         items=[("लेथ का जॉब वर्क", "lathe job work", 0, "", "", "", ""), ("फ़ैब्रिकेशन", "fabrication", 0, "", "", "", ""), ("वेल्डिंग का काम", "welding work", 0, "", "", "", "")],
         unlisted=("पाउडर कोटिंग", "powder coating"), rule=("कोटेशन के लिए ड्रॉइंग या नाप और मात्रा चाहिए, रेट सुरेश जी देखकर बताते हैं", "for a quotation we need the drawing or size and quantity, Suresh ji gives the rate after seeing it"), extra=("छोटे और बड़े दोनों ऑर्डर लेते हैं", "we take small and large orders")),
    dict(id="tailor", kind="tailor", shop=("रॉयल टेलर्स", "Royal Tailors"), owner=("फ़ारूक जी", "Farooq ji"), addr=("चौक बाज़ार, मस्जिद के पास", "Chowk Bazaar, near the masjid"),
         hours=("रोज़ सुबह 10 से रात 8 बजे तक, शुक्रवार बंद", "every day, 10 am to 8 pm, closed on Friday"), delivery=("", ""), kb_numbers={10, 8, 7},
         items=[("शर्ट की सिलाई", "shirt stitching", 450, "", "", "", ""), ("ब्लाउज़ की सिलाई", "blouse stitching", 350, "", "", "", ""), ("पैंट की सिलाई", "trouser stitching", 500, "", "", "", "")],
         unlisted=("शेरवानी", "sherwani"), rule=("सिलाई में सामान्य तौर पर 7 दिन लगते हैं, तारीख फ़ारूक जी तय करते हैं", "stitching usually takes 7 days, Farooq ji fixes the date"), extra=("त्योहार पर पहले से बताएँ", "tell us ahead before festivals")),
    dict(id="garage", kind="garage", shop=("ऑटो केयर गैराज", "Auto Care Garage"), owner=("जावेद जी", "Javed ji"), addr=("बाइपास रोड, पेट्रोल पंप के पीछे", "Bypass Road, behind the petrol pump"),
         hours=("सोमवार से शनिवार, सुबह 9 से शाम 7 बजे तक", "Monday to Saturday, 9 am to 7 pm"), delivery=("", ""), kb_numbers={9, 7},
         items=[("सर्विसिंग", "servicing", 1800, "से शुरू", "onwards", "", ""), ("ऑयल चेंज", "oil change", 600, "से शुरू", "onwards", "", ""), ("व्हील अलाइनमेंट", "wheel alignment", 700, "", "", "", "")],
         unlisted=("इंजन ओवरहॉल", "engine overhaul"), rule=("गाड़ी देखे बिना पक्का रेट नहीं बताते", "no firm rate without seeing the vehicle"), extra=("गाड़ी लाने से पहले समय ले लें", "book a time before bringing the vehicle")),
    dict(id="coaching", kind="coaching class", shop=("ज्ञान ट्यूशन", "Gyan Tuition"), owner=("मीना जी", "Meena ji"), addr=("शिव कॉलोनी, पार्क के पास", "Shiv Colony, near the park"),
         hours=("सोमवार से शनिवार, शाम 4 से रात 8 बजे तक", "Monday to Saturday, 4 pm to 8 pm"), delivery=("", ""), kb_numbers={4, 8, 10, 12},
         items=[("10वीं का बैच", "class 10 batch", 1500, "महीना", "month", "", ""), ("12वीं का बैच", "class 12 batch", 2000, "महीना", "month", "", ""), ("डेमो क्लास", "demo class", 0, "", "", "", "")],
         unlisted=("ऑनलाइन क्लास", "online class"), rule=("एडमिशन से पहले एक डेमो क्लास मुफ़्त है", "one demo class is free before admission"), extra=("बैच सीमित हैं", "batches are limited")),
]
PACK_BY_ID = {p["id"]: p for p in PACKS}

# Callers: (hindi, roman). Mixed ages and genders; some use a title.
CALLERS = [("सुनील", "Sunil"), ("अनीता", "Anita"), ("राजेश", "Rajesh"), ("पूजा", "Pooja"), ("अमित", "Amit"), ("सीमा", "Seema"), ("विकास", "Vikas"), ("मीना", "Meena"), ("इरफ़ान", "Irfan"), ("कविता", "Kavita"), ("दीपक", "Deepak"), ("नीलम", "Neelam"), ("हरप्रीत", "Harpreet"), ("सुरेंद्र", "Surendra")]
