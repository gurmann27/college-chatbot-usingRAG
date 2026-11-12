"""Small multilingual domain lexicon.

Used for (a) the keyword intent classifier fallback, (b) Hinglish detection, and
(c) the MOCK_AZURE providers (fake translation / fake cross-lingual embeddings).
Production cross-lingual quality comes from the LLM query-understanding step and the
multilingual embedding model, NOT from this table.
"""
from __future__ import annotations

# token (any language / romanisation) -> English term
LEXICON: dict[str, str] = {
    # ---------------- Hindi (Devanagari)
    "बेनेट": "bennett", "यूनिवर्सिटी": "university", "विश्वविद्यालय": "university", "कॉलेज": "college",
    "टाइम्स": "times", "ग्रुप": "group", "समूह": "group", "विनीत": "vineet", "जैन": "jain",
    "राज": "raj", "सिंह": "singh", "ग्रेटर": "greater", "नोएडा": "noida",
    "छात्रावास": "hostel", "हॉस्टल": "hostel", "होस्टल": "hostel",
    "शुल्क": "fee", "फीस": "fee", "फ़ीस": "fee", "ट्यूशन": "tuition",
    "परीक्षा": "exam", "इम्तिहान": "exam", "प्रवेश": "admission", "दाखिला": "admission", "एडमिशन": "admission",
    "छात्रवृत्ति": "scholarship", "स्कॉलरशिप": "scholarship", "परिपत्र": "circular", "सर्कुलर": "circular",
    "नियम": "rule", "नियमों": "rule", "दिशानिर्देश": "guideline", "समय": "time", "रात": "night",
    "वापस": "return", "लौटने": "return", "लौटना": "return", "आने": "return", "गेट": "gate", "बंद": "close",
    "उपस्थिति": "attendance", "हाजिरी": "attendance", "न्यूनतम": "minimum", "कितनी": "how", "कितना": "how", "कितने": "how",
    "वार्षिक": "annual", "सालाना": "annual", "अंतिम": "last", "तिथि": "date", "तारीख": "date",
    "विलंब": "late", "लेट": "late", "देर": "late", "जुर्माना": "fine", "पात्र": "eligible", "पात्रता": "eligibility",
    "योग्यता": "eligibility", "मेरिट": "merit", "अंक": "marks", "प्रतिशत": "percent", "आगंतुक": "visitor",
    "मेहमान": "visitor", "रैगिंग": "ragging", "फॉर्म": "form", "पुनर्मूल्यांकन": "revaluation", "दस्तावेज़": "document",
    "दस्तावेज": "document", "बी.टेक": "b.tech", "बीटेक": "b.tech", "एमटेक": "m.tech", "एम.टेक": "m.tech",
    "बीबीए": "bba", "एमबीए": "mba", "बीसीए": "bca", "एमसीए": "mca", "बीएससी": "b.sc", "एमएससी": "m.sc",
    "पीएचडी": "ph.d", "एलएलबी": "ll.b", "एलएलएम": "ll.m", "बीकॉम": "b.com", "बीडेस": "b.des",
    "आवेदन": "application", "भुगतान": "payment", "प्रक्रिया": "process", "तरीका": "process",
    "कैंपस": "campus", "परिसर": "campus", "एकड़": "acres", "आकार": "acres", "क्षेत्रफल": "acres",
    "क्षमता": "capacity", "सीट": "capacity", "सीटें": "capacity", "छात्र": "students", "बच्चे": "students",
    "स्टार्टअप": "startups", "स्टार्टअप्स": "startups", "हैचरी": "hatchery", "इनक्यूबेशन": "incubation",
    "लॉन्च": "launched", "फंडिंग": "funding", "फंड": "funds",
    "स्थापना": "founded", "संस्थापक": "founded", "किसने": "founded",
    "चांसलर": "chancellor", "कुलाधिपति": "chancellor", "कुलपति": "vice chancellor", "वाइस": "vice",
    "डीन": "deans", "डीन्स": "deans", "फैकल्टी": "faculty", "शिक्षक": "faculty", "प्रोफेसर": "prof",
    "रिसर्च": "research", "शोध": "research", "पेटेंट": "patents", "पब्लिकेशन": "publications",
    "प्रकाशन": "publications", "साइटेशन": "citations", "लैब": "labs", "प्रयोगशाला": "labs",
    "स्पोर्ट्स": "sports", "खेल": "sports", "क्रिकेट": "cricket", "फुटबॉल": "football",
    "बैडमिंटन": "badminton", "पिकलबॉल": "pickleball", "स्विमिंग": "swimming", "जिम": "fitness", "कोर्ट": "courts",
    "लाइब्रेरी": "library", "पुस्तकालय": "library", "किताबें": "books", "किताब": "books",
    "क्लब": "clubs", "क्लब्स": "clubs", "सोसाइटी": "clubs", "इवेंट": "events", "इवेंट्स": "events",
    "फेस्ट": "fests", "उत्सव": "fests", "यूफोरिया": "uphoria", "जेनेविया": "zenevia",
    "ब्लूमून": "bluemoon", "स्पोर्टिकॉन": "sportikon", "कन्वर्ज": "converge",
    "प्लेसमेंट": "placements", "नौकरी": "placements", "जॉब": "placements",
    "कंपनी": "recruiters", "कंपनियां": "recruiters", "रिक्रूटर्स": "recruiters",
    "कोर्स": "programs", "कोर्सेज": "programs", "प्रोग्राम": "programs", "प्रोग्राम्स": "programs",
    "डिग्री": "programs", "पढ़ाई": "programs", "ब्रांच": "programs", "स्पेशलाइजेशन": "specializations",
    "स्कूल": "school", "विभाग": "school",
    "आर्टिफिशियल": "artificial", "इंटेलिजेंस": "intelligence", "एआई": "ai",
    "कंप्यूटर": "computer", "साइंस": "science", "इंजीनियरिंग": "engineering",
    "डिजाइन": "design", "डिज़ाइन": "design", "लॉ": "law", "कानून": "law",
    "मैनेजमेंट": "management", "प्रबंधन": "management", "मीडिया": "media", "पत्रकारिता": "journalism",
    "लिबरल": "liberal", "आर्ट्स": "arts", "बायोटेक": "biotech", "मैकेनिकल": "mechanical", "इलेक्ट्रॉनिक्स": "electronics",
    "खाना": "hangout", "खाने": "hangout", "भोजन": "dining", "मेस": "mess",
    "कैंटीन": "cafeteria", "कैफेटेरिया": "cafeteria", "रेस्टोरेंट": "hangout", "हैंगआउट": "hangout",
    "कमरा": "rooms", "कमरे": "rooms", "क्लासरूम": "classrooms", "लाउंज": "lounge",
    "ग्लोबल": "global", "अंतरराष्ट्रीय": "international", "विदेश": "abroad", "पार्टनर": "partner",
    "मान्यता": "accreditation", "रैंकिंग": "rankings", "ग्रेड": "grade", "अवार्ड": "awards", "पुरस्कार": "awards",
    "संपर्क": "contact", "फोन": "contact", "नंबर": "contact", "हेल्पलाइन": "contact", "ईमेल": "email", "वेबसाइट": "website",
    # ---------------- Marathi
    "वसतिगृह": "hostel", "परीक्षेचे": "exam", "शिष्यवृत्ती": "scholarship", "किती": "how", "आहे": "is",
    # ---------------- Hinglish / romanised
    "shulk": "fee", "pariksha": "exam", "imtihan": "exam", "pravesh": "admission", "dakhila": "admission",
    "chhatravritti": "scholarship", "niyam": "rule", "samay": "time",
    "raat": "night", "rat": "night", "wapas": "return", "vapas": "return", "kitni": "how", "kitna": "how",
    "kitne": "how", "saalana": "annual", "salana": "annual",
    "jurmana": "fine", "hazri": "attendance", "haziri": "attendance",
    "tarikh": "date", "taarikh": "date", "aakhri": "last", "akhri": "last",
    "kisne": "founded", "banaya": "founded", "sthapna": "founded", "shuru": "founded",
    "kshamta": "capacity", "jagah": "capacity", "ekad": "acres",
    "khel": "sports", "khana": "hangout", "khane": "hangout",
    "naukri": "placements", "padhai": "programs",
    "kulpati": "vice chancellor", "vibhag": "school", "pustakalaya": "library", "kitab": "books",
    "suvidha": "facilities", "suvidhayen": "facilities", "vyavastha": "facilities",
    "prakriya": "process", "tarika": "process", "sampark": "contact", "jaankari": "information", "jankari": "information",
    # ---------------- Tamil
    "விடுதி": "hostel", "கட்டணம்": "fee", "தேர்வு": "exam", "சேர்க்கை": "admission", "உதவித்தொகை": "scholarship",
    "விதிகள்": "rule", "நேரம்": "time", "இரவு": "night", "எவ்வளவு": "how", "வருகைப்பதிவு": "attendance",
    # ---------------- Telugu
    "హాస్టల్": "hostel", "వసతిగృహం": "hostel", "ఫీజు": "fee", "రుసుము": "fee", "పరీక్ష": "exam",
    "ప్రవేశం": "admission", "స్కాలర్‌షిప్": "scholarship", "ఎంత": "how", "నియమాలు": "rule",
    # ---------------- Bengali
    "ছাত্রাবাস": "hostel", "হোস্টেল": "hostel", "ফি": "fee", "পরীক্ষা": "exam", "ভর্তি": "admission",
    "বৃত্তি": "scholarship", "কত": "how", "নিয়ম": "rule",
    # ---------------- Kannada
    "ವಸತಿನಿಲಯ": "hostel", "ಹಾಸ್ಟೆಲ್": "hostel", "ಶುಲ್ಕ": "fee", "ಪರೀಕ್ಷೆ": "exam", "ಪ್ರವೇಶ": "admission",
    "ವಿದ್ಯಾರ್ಥಿವೇತನ": "scholarship", "ಎಷ್ಟು": "how",
}

# Function words that strongly indicate Romanised Hindi (Hinglish).
HINGLISH_MARKERS = frozenset(
    """hai hain kya kaise kaisa kaisi kitni kitna kitne kab kahan kaha kaun kaunsa kaunse konsa konse kyun kyu
    mein me mai main nahi nahin ka ki ke ko se par aur ya bhi hota hoti hote chahiye batao bataye bataiye
    karna karte kare karwaye kiya kiye milta milegi milega milti milte wala wali wale lagta lagti lagegi sakte sakta sakti
    tha thi the hua hue hui gaya gaye gayi abhi agar toh to jaate jata lene dena diya saare sare sabhi kuch baare bare
    hostel_ke""".split()
)
# Words that are both English and Hinglish markers; ignore them when counting.
AMBIGUOUS_MARKERS = frozenset({"to", "me", "main", "par", "the", "mai"})

# Native-script function words that should not be kept in a fake translation.
NATIVE_STOPWORDS = frozenset(
    """क्या है हैं था थी थे का की के को में से पर और या भी कैसे कब कहाँ कौन कौनसा कौनसे किस किसके किसका
    होता होती होते होना हुए हुआ हुई गए गया गई जाते जाता जाती कराए कराया कीजिये करें करने करना
    चाहिए बताइए बताओ बताएं लिए एक यह वह इस उस मुझे हमें आप तक कुल सभी सारे कुछ बारे जानकारी सुविधा सुविधाएं व्यवस्था
    काय आहे आहेत ची चा चे मध्ये என்ன உள்ள ఏమిటి కి কী কি ಏನು""".split()
)

CATEGORY_KEYWORDS: dict[str, tuple[str, ...]] = {
    "hostel": ("hostel", "mess", "warden", "room", "curfew", "gate", "visitor", "ragging", "night"),
    "fees": ("fee", "tuition", "payment", "refund", "installment", "fine", "₹", "rupee", "amount", "cost"),
    "exams": ("exam", "examination", "attendance", "revaluation", "marks", "grade", "malpractice", "hall ticket", "result"),
    "admissions": ("admission", "apply", "application", "eligibility", "counselling", "entrance", "seat", "document"),
    "scholarships": ("scholarship", "waiver", "merit", "stipend", "financial aid", "concession"),
    "circulars": ("circular", "notice", "notification", "revised", "announcement"),
}


def translate_tokens(tokens: list[str]) -> list[str]:
    out: list[str] = []
    for t in tokens:
        if t in LEXICON:
            out.append(LEXICON[t])
        elif t in NATIVE_STOPWORDS or t in HINGLISH_MARKERS:
            continue
        else:
            out.append(t)
    return out

