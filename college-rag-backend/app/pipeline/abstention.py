"""Step (g): localised abstention (and 'service busy') messages."""
from __future__ import annotations

# Exact token the generator must output when the context does not answer the question.
ABSTAIN_TOKEN = "<<NOT_FOUND>>"

ABSTENTION_MESSAGES: dict[str, str] = {
    "en": "Information not found in official college documents.",
    "hi": "आधिकारिक कॉलेज दस्तावेज़ों में यह जानकारी नहीं मिली।",
    "hi-Latn": "Yeh jaankari official college documents mein nahi mili.",
    "ta": "அதிகாரப்பூர்வ கல்லூரி ஆவணங்களில் இந்தத் தகவல் கிடைக்கவில்லை.",
    "te": "అధికారిక కళాశాల పత్రాలలో ఈ సమాచారం లభించలేదు.",
    "mr": "अधिकृत महाविद्यालयीन कागदपत्रांमध्ये ही माहिती आढळली नाही.",
    "bn": "সরকারি কলেজ নথিতে এই তথ্য পাওয়া যায়নি।",
    "kn": "ಅಧಿಕೃತ ಕಾಲೇಜು ದಾಖಲೆಗಳಲ್ಲಿ ಈ ಮಾಹಿತಿ ಕಂಡುಬಂದಿಲ್ಲ.",
    "gu": "સત્તાવાર કોલેજ દસ્તાવેજોમાં આ માહિતી મળી નથી.",
    "pa": "ਅਧਿਕਾਰਤ ਕਾਲਜ ਦਸਤਾਵੇਜ਼ਾਂ ਵਿੱਚ ਇਹ ਜਾਣਕਾਰੀ ਨਹੀਂ ਮਿਲੀ।",
    "ml": "ഔദ്യോഗിക കോളേജ് രേഖകളിൽ ഈ വിവരം കണ്ടെത്താനായില്ല.",
}

BUSY_MESSAGES: dict[str, str] = {
    "en": "The service is busy right now. Please try again later.",
    "hi": "सेवा अभी व्यस्त है। कृपया बाद में पुनः प्रयास करें।",
    "hi-Latn": "Service abhi busy hai. Kripya thodi der baad try karein.",
}


def _lookup(table: dict[str, str], language: str | None) -> str:
    if not language:
        return table["en"]
    if language in table:
        return table[language]
    # e.g. "hi-IN" -> "hi"; but romanised variants of other languages ("ta-Latn")
    # fall back to English, since a native-script message would not be readable.
    base, _, rest = language.partition("-")
    if rest.lower() == "latn":
        return table.get(f"{base}-Latn", table["en"])
    return table.get(base.lower(), table["en"])


def abstention_message(language: str | None) -> str:
    return _lookup(ABSTENTION_MESSAGES, language)


def busy_message(language: str | None) -> str:
    return _lookup(BUSY_MESSAGES, language)


def is_abstention(text: str) -> bool:
    t = (text or "").strip()
    return not t or ABSTAIN_TOKEN in t or "NOT_FOUND" in t

