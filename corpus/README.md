# Conversation corpus for the Munshi call agent

Generated, labelled call transcripts used to design and test the voice-agent prompt. These are written examples, **not recordings of real calls**; names, shops and prices are invented.

    python3 build.py          # rebuilds conversations.jsonl, SAMPLE.md, STATS.md; fails if any conversation breaks a rule
    python3 validate.py       # checks conversations.jsonl on its own

## What is in it
- **64 situations** (`skeletons_a/b/c.py`), each written in Hindi (Devanagari), Hinglish (roman) and English, played in up to six of **ten kinds of business** (`packs.py`: sweet shop, cloud kitchen, salon, kirana, wholesale, dental clinic, small factory, tailor, garage, coaching class).
- **Required calls** (owner must act): orders, price or stock questions that need the owner, appointments, quotes, complaints, refunds, messages, suppliers, job seekers.
- **Not required**: sales and loan calls, surveys, wrong numbers, silence, prank, recorded promos, phishing.
- **Integrity and safety**: discount pressure, "the owner promised me", prompt injection, private-information requests, card/OTP sharing, abuse, legal threats, flirting, "are you human?", emergencies (tell the caller to call 112), unclear audio, other languages.
- Every conversation carries a label (`action` = Needs you, `fyi` = Good to know, `ignore` = Not worth it), a category, the shop information it may use (`kb`), and the behaviours a good reply must show (`must`).

## Rules enforced by `validate.py` (and `backend/tests/test_corpus.py`)
- Munshi greets first; turns alternate; an ending call ends on Munshi with a polite closing.
- Munshi turns are at most 34 words.
- No promises, guarantees, admissions of fault, compensation, or model/vendor names.
- Munshi never asks for the caller's phone number (the call already has it).
- Every number Munshi says comes from the shop information or from what the caller already said (112 is allowed).
- Hindi is Devanagari only (plus AI, OTP, UPI, GST, WhatsApp, Munshi); Hinglish and English contain no Devanagari.
- Each `must` tag is checked where it can be (asks the name, says it is an AI, says 112, names the owner, and so on).

## Notes
- Munshi's Hindi lines use the masculine form (मैं कर सकता हूँ). If the owner picks a female voice, the prompt should tell the model to use the feminine form; the corpus does not cover that yet.
- This is a design and regression set, not training data for fine-tuning. It is used to write the prompt's rules and its few examples, and to replay hard cases against the live agent.
