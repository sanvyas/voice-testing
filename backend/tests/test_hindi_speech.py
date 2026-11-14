import hindi_speech as h


def test_number_words_indian_grouping():
    assert h.number_words(480) == "चार सौ अस्सी"
    assert h.number_words(2480) == "दो हज़ार चार सौ अस्सी"
    assert h.number_words(150000) == "एक लाख पचास हज़ार"
    assert h.number_words(99) == "निन्यानवे"
    assert h.number_words(0) == "शून्य"


def test_money_and_units():
    assert h.normalize("बर्फ़ी ₹480 किलो है।") == "बर्फ़ी चार सौ अस्सी रुपये किलो है।"
    assert "एक रुपया" in h.normalize("₹1")
    assert h.normalize("Rs. 1,250") == "एक हज़ार दो सौ पचास रुपये"
    assert h.normalize("5 kg चावल") == "पाँच किलो चावल"
    assert h.normalize("20 पैकेट") == "बीस पैकेट"
    assert h.normalize("10% छूट") == "दस प्रतिशत छूट"


def test_times():
    assert h.normalize("शाम 5 बजे") == "शाम पाँच बजे"
    assert h.normalize("9 am to 8 pm") == "सुबह नौ बजे to रात आठ बजे"
    assert h.normalize("5:30 pm") == "शाम साढ़े पाँच बजे"
    assert h.normalize("1:15") == "सवा एक बजे"
    assert h.normalize("17:30") == "शाम साढ़े पाँच बजे"
    assert h.normalize("12 pm") == "दोपहर बारह बजे"
    assert h.normalize("12 am") == "रात बारह बजे"


def test_phone_numbers_are_read_digit_by_digit():
    assert h.normalize("98765 43210") == "नौ आठ सात छह पाँच चार तीन दो एक शून्य"
    assert h.normalize("+91 98765 43210").startswith("नौ आठ सात")


def test_loanwords_become_devanagari():
    assert h.normalize("आपका order confirm हो गया") == "आपका ऑर्डर कन्फ़र्म हो गया"
    assert h.normalize("मैं AI assistant हूँ") == "मैं ए आई असिस्टेंट हूँ"
    assert h.normalize("WhatsApp पर भेजें") == "व्हाट्सऐप पर भेजें"


def test_names_and_plain_hindi_are_untouched():
    assert h.normalize("रमेश जी call करेंगे।") == "रमेश जी कॉल करेंगे।"
    assert h.normalize("Ramesh ji आएँगे") == "Ramesh ji आएँगे"
    assert h.normalize("ai") == "ai"  # not the abbreviation


def test_danda_for_pause_and_empty():
    assert h.normalize("ठीक है. अगला") == "ठीक है। अगला"
    assert h.normalize("") == ""


def test_script_detection():
    assert h.has_devanagari("नमस्ते Munshi") and not h.has_devanagari("Hello there")


def test_voice_follows_the_script_of_the_reply():
    from assistant import phone
    assert phone._voice_language("जी, आपका ऑर्डर नोट हो गया।", "en-IN") == "hi-IN"
    assert phone._voice_language("Sure, I will tell Ramesh.", "hi-IN") == "en-IN"


def test_record_wait_is_configurable_and_short(monkeypatch):
    from assistant import phone
    assert 1 <= phone.RECORD_SILENCE_S <= 5
    assert f'timeout="{phone.RECORD_SILENCE_S}"' in phone.record_xml(type("R", (), {"base_url": "x", "url": type("U", (), {"scheme": "https", "netloc": "h"})(), "headers": {}})(), "c1")
