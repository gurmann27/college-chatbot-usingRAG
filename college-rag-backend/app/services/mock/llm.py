"""Deterministic rule-based LLM for ``MOCK_AZURE=true``.

Implements the exact prompt contracts of every task (query_understanding, generation,
translate, judge, rerank) using only the passages in the prompt, so the full pipeline
(chunking -> retrieval -> RRF -> rerank -> generation -> citation & numeric verification)
runs end-to-end with zero Azure credentials.
"""
from __future__ import annotations

import json
import re
from dataclasses import dataclass

from app.core.lexicon import translate_tokens
from app.core.text import count_tokens, looks_like_injection, term_coverage, tokenize
from app.pipeline.abstention import ABSTAIN_TOKEN
from app.pipeline.language import classify_intent, heuristic_detect
from app.pipeline.verification import CITE_RE, extract_citations, unsupported_numbers
from app.services.llm import ChatMessage, LLMProvider, LLMResult, Task

SOURCE_RE = re.compile(
    r'<source\s+id="(?P<id>\d+)"\s+document="(?P<doc>[^"]*)"'
    r'(?:\s+page="(?P<page>[^"]*)")?(?:\s+effective_date="(?P<date>[^"]*)")?'
    r'(?:\s+section="(?P<section>[^"]*)")?\s*>\s*(?P<body>.*?)\s*</source>',
    re.S,
)
PASSAGE_RE = re.compile(r'<passage\s+id="(?P<id>\d+)">(?P<body>.*?)</passage>', re.S)


@dataclass
class _Src:
    id: int
    doc: str
    page: str | None
    date: str | None
    section: str | None
    body: str


#Localized response wrappers: {s} is the verbatim English sentence(s) from the source,
#so every number, currency amount, percentage, date and course code is preserved verbatim.
TEMPLATES: dict[str, str] = {
    "en": "{s}",
    "hi": "आधिकारिक दस्तावेज़ ({doc}{pg}) के अनुसार: {s}",
    "hi-Latn": "Official document ({doc}{pg}) ke mutabik: {s}",
    "ta": "அதிகாரப்பூர்வ ஆவணத்தின்படி ({doc}{pg}): {s}",
    "te": "అధికారిక పత్రం ({doc}{pg}) ప్రకారం: {s}",
    "mr": "अधिकृत कागदपत्रानुसार ({doc}{pg}): {s}",
    "bn": "সরকারি নথি ({doc}{pg}) অনুযায়ী: {s}",
    "kn": "ಅಧಿಕೃತ ದಾಖಲೆಯ ({doc}{pg}) ಪ್ರಕಾರ: {s}",
}

# Natural native-script paraphrases for common phrases so Hindi / Hinglish answers read
# fluently while keeping every number, amount, date and code verbatim.
HI_REPLACEMENTS = [
    ("All hostel residents must return to their respective hostels by 10:00 PM every night.",
     "सभी छात्रावास निवासियों को हर रात 10:00 PM तक अपने हॉस्टल में वापस लौटना अनिवार्य है।"),
    ("The main hostel gates close strictly at 10:00 PM and reopen at 5:30 AM.",
     "मुख्य हॉस्टल के गेट रात 10:00 PM पर बंद हो जाते हैं और सुबह 5:30 AM पर खुलते हैं।"),
    ("The annual tuition fee for the B.Tech programme is ₹1,25,000 per year.",
     "B.Tech कार्यक्रम का वार्षिक ट्यूशन शुल्क ₹1,25,000 प्रति वर्ष है।"),
    ("A student must maintain at least 75% attendance in every registered course to be eligible to appear in the end-semester examination.",
     "अंतिम सेमेस्टर परीक्षा में बैठने के लिए प्रत्येक विषय में कम से कम 75% उपस्थिति अनिवार्य है।"),
    ("70+ Startups have been launched at Bennett University under Bennett Hatchery Foundation.",
     "बेनेट यूनिवर्सिटी में बेनेट हैचरी फाउंडेशन के अंतर्गत 70+ स्टार्टअप्स लॉन्च किए गए हैं।"),
    ("Bennett University has 70+ startups launched, ₹125 Cr+ funds raised by startups, 68 acres futuristic campus, 14,000+ students, 10,000 hostel capacity, 120+ international collaborations, 20+ corporate collaborations, 1200+ companies for placements, 40+ student led clubs & societies, 16+ sports facilities, 90%+ Ph.D. faculty, and 50+ undergraduate, postgraduate & doctoral programs.",
     "बेनेट यूनिवर्सिटी में 70+ स्टार्टअप्स लॉन्च हो चुके हैं, स्टार्टअप्स द्वारा ₹125 Cr+ फंड जुटाया गया है, 68 एकड़ का आधुनिक कैंपस है, 14,000+ छात्र हैं, 10,000 हॉस्टल क्षमता है, 120+ अंतरराष्ट्रीय सहयोग, 20+ कॉर्पोरेट सहयोग, प्लेसमेंट के लिए 1200+ कंपनियां, 40+ छात्र क्लब, 16+ खेल सुविधाएं, 90%+ Ph.D. फैकल्टी और 50+ प्रोग्राम उपलब्ध हैं।"),
    ("Innovation & Entrepreneurship Bennett Hatchery Foundation, a registered Section 8 company, is the startup incubation arm of the Centre for Innovation & Entrepreneurship (CIE) at Bennett University, empowering innovators to transform ideas into scalable ventures.",
     "बेनेट हैचरी फाउंडेशन (एक पंजीकृत Section 8 कंपनी) बेनेट यूनिवर्सिटी के सेंटर फॉर इनोवेशन एंड एंटरप्रेन्योरशिप (CIE) की स्टार्टअप इनक्यूबेशन शाखा है, जो इनोवेटर्स को अपने विचारों को सफल स्टार्टअप में बदलने के लिए सशक्त बनाती है।"),
    ("Recognised by Startup India, MSME, and the UP StartinUP Policy, the Hatchery supports early-stage startups across ideation, validation, prototyping, and market growth.",
     "Startup India, MSME और UP StartinUP Policy द्वारा मान्यता प्राप्त यह हैचरी शुरुआती चरण के स्टार्टअप्स को आइडिएशन, वैलिडेशन, प्रोटोटाइपिंग और मार्केट ग्रोथ में सहायता करती है।"),
    ("With ₹5.5 crore secured through government-backed seed funding programmes, Bennett Hatchery Foundation actively nurtures high-potential startups and strengthens the university’s entrepreneurial ecosystem.",
     "सरकारी सीड फंडिंग कार्यक्रमों के माध्यम से प्राप्त ₹5.5 crore के साथ, बेनेट हैचरी फाउंडेशन उच्च-क्षमता वाले स्टार्टअप्स को आगे बढ़ाता है।"),
    ("Inspired by his belief in the potential of educated and engaged young minds, he founded Bennett University in 2016, embodying his commitment to excellence and innovation in higher education.",
     "युवाओं की क्षमता में अपने विश्वास से प्रेरित होकर, श्री विनीत जैन ने उच्च शिक्षा में उत्कृष्टता और नवाचार के लिए 2016 में बेनेट यूनिवर्सिटी की स्थापना की।"),
    ("As the Managing Director of India's oldest, largest, and most respected media conglomerate, Bennett, Coleman & Co. Limited (known as The Times Group), Mr. Vineet Jain has played an instrumental role in steering the entire spectrum of BCCL's operations.",
     "भारत के सबसे पुराने और सबसे बड़े मीडिया समूह Bennett, Coleman & Co. Limited (The Times Group) के प्रबंध निदेशक (Managing Director) के रूप में श्री विनीत जैन ने महत्वपूर्ण भूमिका निभाई है।"),
]
HINGLISH_REPLACEMENTS = [
    ("The annual tuition fee for the B.Tech programme is ₹1,25,000 per year.",
     "B.Tech programme ki annual tuition fee ₹1,25,000 per year hai."),
    ("In addition, students pay a development fee of ₹15,000 and an examination and library fee of ₹5,000, bringing the total annual academic fee for B.Tech to ₹1,45,000 per year.",
     "Iske alawa development fee ₹15,000 aur examination & library fee ₹5,000 hai, jisse B.Tech ki total annual academic fee ₹1,45,000 per year hoti hai."),
    ("All hostel residents must return to their respective hostels by 10:00 PM every night.",
     "Sabhi hostel residents ko har raat 10:00 PM tak hostel wapas aana zaroori hai."),
    ("The annual hostel and mess fee is ₹72,000 per year (₹42,000 room rent plus ₹30,000 mess advance).",
     "Annual hostel aur mess fee ₹72,000 per year hai (₹42,000 room rent aur ₹30,000 mess advance)."),
    ("70+ Startups have been launched at Bennett University under Bennett Hatchery Foundation.",
     "Bennett University me Bennett Hatchery Foundation ke antargat 70+ startups launch hue hain."),
    ("Bennett University has 70+ startups launched, ₹125 Cr+ funds raised by startups, 68 acres futuristic campus, 14,000+ students, 10,000 hostel capacity, 120+ international collaborations, 20+ corporate collaborations, 1200+ companies for placements, 40+ student led clubs & societies, 16+ sports facilities, 90%+ Ph.D. faculty, and 50+ undergraduate, postgraduate & doctoral programs.",
     "Bennett University me 70+ startups launch hue hain, startups ne ₹125 Cr+ funds raise kiye hain, 68 acres ka futuristic campus hai, 14,000+ students hain, 10,000 hostel capacity hai, 120+ international collaborations, 20+ corporate collaborations, placements ke liye 1200+ companies, 40+ student clubs, 16+ sports facilities, 90%+ Ph.D. faculty aur 50+ UG/PG/Doctoral programs hain."),
    ("Innovation & Entrepreneurship Bennett Hatchery Foundation, a registered Section 8 company, is the startup incubation arm of the Centre for Innovation & Entrepreneurship (CIE) at Bennett University, empowering innovators to transform ideas into scalable ventures.",
     "Bennett Hatchery Foundation (ek registered Section 8 company) Bennett University ke Centre for Innovation & Entrepreneurship (CIE) ka startup incubation arm hai, jo innovators ko apne ideas ko scalable startups me badalne me madad karta hai."),
    ("Recognised by Startup India, MSME, and the UP StartinUP Policy, the Hatchery supports early-stage startups across ideation, validation, prototyping, and market growth.",
     "Startup India, MSME aur UP StartinUP Policy se recognised yeh Hatchery early-stage startups ko ideation, validation, prototyping aur market growth me support karta hai."),
    ("Open to students, faculty, staff, and external entrepreneurs, it offers structured mentorship, access to world-class infrastructure, industry partnerships, and funding support.",
     "Yeh students, faculty, staff aur external entrepreneurs sabhi ke liye open hai aur structured mentorship, world-class infrastructure, industry partnerships aur funding support deta hai."),
    ("With ₹5.5 crore secured through government-backed seed funding programmes, Bennett Hatchery Foundation actively nurtures high-potential startups and strengthens the university’s entrepreneurial ecosystem.",
     "Government-backed seed funding programmes ke zariye ₹5.5 crore secure karke, Bennett Hatchery Foundation high-potential startups ko nurture karta hai aur university ke startup ecosystem ko majboot banata hai."),
    ("CIE advances innovation at Bennett University through three integrated verticals—Academics, Bennett Hatchery Foundation, and SPARK, the student entrepreneurship cell—creating a vibrant, end-to-end startup ecosystem on campus.",
     "CIE teen integrated verticals — Academics, Bennett Hatchery Foundation, aur SPARK (student entrepreneurship cell) — ke zariye campus par ek vibrant startup ecosystem banata hai."),
    ("Mr. Vineet Jain Managing Director The Times Group Chancellor Bennett University Mr. Vineet Jain, a visionary leader and a media industry powerhouse, has significantly impacted India's media and education landscape through his dedication to empowering youth.",
     "Mr. Vineet Jain (Managing Director, The Times Group aur Chancellor, Bennett University) ek visionary leader hain jinhone youth ko empower karke India ke media aur education sector me bada yogdan diya hai."),
    ("Inspired by his belief in the potential of educated and engaged young minds, he founded Bennett University in 2016, embodying his commitment to excellence and innovation in higher education.",
     "Young minds ki potential me vishwas rakhte hue unhone 2016 me Bennett University ki sthapna (founded) ki taaki higher education me excellence aur innovation laya ja sake."),
    ("As the Managing Director of India's oldest, largest, and most respected media conglomerate, Bennett, Coleman & Co. Limited (known as The Times Group), Mr. Vineet Jain has played an instrumental role in steering the entire spectrum of BCCL's operations.",
     "India ke sabse bade aur purane media group Bennett, Coleman & Co. Limited (The Times Group) ke Managing Director ke roop me Mr. Vineet Jain ne BCCL ke operations ko lead karne me mukhya bhumika nibhai hai."),
    ("Bennett University’s 68 acres sprawling campus is visualized as a modern, student-centric, functional space, enabling an immersive and comprehensive learning experience.",
     "Bennett University ka 68 acres ka vishal campus ek modern aur student-centric space ke roop me banaya gaya hai jo behtareen learning experience deta hai."),
    ("Separate Girls and Boys Hostels with the capacity to accommodate 10,000+ students at a time | Triple sharing rooms for boys and girls | Essential amenities such as ACs, comfortable beds, cupboards, study table, access to hot water round the year, laundry service & common entertainment rooms are provided for a pleasant stay | Wellness Centre, Pharmacy, Tuck Shop and Salons for a comfortable residential environment | 72000 sq. ft two-level Dining Hall.",
     "Yahan Girls aur Boys ke liye alag-alag hostels hain jinki capacity ek saath 10,000+ students ki hai, jisme triple sharing AC rooms, beds, study table, poore saal hot water, laundry, Wellness Centre, Pharmacy, Tuck Shop, Salon aur 72000 sq. ft ka two-level Dining Hall shamil hai."),
    ("Accredited with an A+ grade by NAAC and recognised by the University Grants Commission (UGC), Association of Indian Universities (AIU), and the Bar Council of India (BCI), Bennett University upholds the highest educational standards.",
     "Bennett University ko NAAC se A+ grade mila hai aur yeh UGC, AIU aur Bar Council of India (BCI) se maanyata praapt (recognised) hai."),
]

_HINGLISH_PHRASE_RULES: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\bUnder the (School of [A-Za-z &]+|Times School of Media),\s*Bennett University offers\b", re.I), r"\1 ke antargat Bennett University yeh programs offer karta hai:"),
    (re.compile(r"\bHostels at Bennett University:\s*", re.I), "Bennett University ke Hostels: "),
    (re.compile(r"\bHangout Joints and Food Cafeteria at Bennett University:\s*", re.I), "Bennett University ke Hangout Joints aur Food Cafeteria: "),
    (re.compile(r"\bLibrary at Bennett University:\s*", re.I), "Bennett University ki Library: "),
    (re.compile(r"\bHigh-End Teaching & Research Labs at Bennett University:\s*", re.I), "Bennett University ki High-End Teaching & Research Labs: "),
    (re.compile(r"\bStudent Clubs at Bennett University:\s*", re.I), "Bennett University ke Student Clubs: "),
    (re.compile(r"\bAnnual Events and Fests at Bennett University:\s*", re.I), "Bennett University ke Annual Events aur Fests: "),
    (re.compile(r"\bSmart Classrooms and Lounges at Bennett University:\s*", re.I), "Bennett University ke Smart Classrooms aur Lounges: "),
    (re.compile(r"\bpostgraduate and dual degree programs include\b", re.I), "me postgraduate aur dual degree programs shamil hain:"),
    (re.compile(r"\bThe Deans of Bennett University include\b", re.I), "Bennett University ke Deans me shamil hain"),
    (re.compile(r"\bKey recruiters for placements at Bennett University include\b", re.I), "Bennett University me placements ke pramukh recruiters hain"),
    (re.compile(r"\bBennett University's research highlights include\b", re.I), "Bennett University ki pramukh research achievements hain"),
    (re.compile(r"\bSports facilities at Bennett University include\b", re.I), "Bennett University ki sports facilities me shamil hain"),
    (re.compile(r"\bAnnual student fests at Bennett University include\b", re.I), "Bennett University ke annual student fests hain"),
    (re.compile(r"\bMajor campus events at Bennett University include\b", re.I), "Bennett University ke pramukh campus events hain"),
    (re.compile(r"\bis the Vice Chancellor of Bennett University\b", re.I), "Bennett University ke Vice Chancellor hain"),
    (re.compile(r"\bis the Chancellor of Bennett University and Managing Director of The Times Group\b", re.I), "Bennett University ke Chancellor aur The Times Group ke Managing Director hain"),
    (re.compile(r"\bis the Vice President, Admissions at Bennett University\b", re.I), "Bennett University me Vice President (Admissions) hain"),
    (re.compile(r"\band the 5-step admission process \(with the new batch commencing from July\) is:\b", re.I), "aur 5-step admission process (naya batch July se shuru hota hai) is prakar hai:"),
    (re.compile(r"\bwith specializations in\b", re.I), "jisme specializations hain:"),
    (re.compile(r"\bThere are\b", re.I), "Yahan"),
    (re.compile(r"\bhas a\b", re.I), "me hai ek"),
    (re.compile(r"\bhave the capacity to accommodate\b", re.I), "ki capacity hai accommodate karne ki"),
    (re.compile(r"\bis committed to fostering\b", re.I), "badhava dene ke liye pratibaddh hai"),
    (re.compile(r"\bis visualized as a\b", re.I), "ko banaya gaya hai ek"),
    (re.compile(r"\bhas been a pillar of\b", re.I), "ek majboot stambh raha hai"),
    (re.compile(r"\bhave been launched\b", re.I), "launch hue hain"),
    (re.compile(r"\bhas been secured\b", re.I), "secure kiya gaya hai"),
    (re.compile(r"\bwas founded in\b", re.I), "ki sthapna hui thi"),
    (re.compile(r"\bfounded Bennett University in\b", re.I), "ne Bennett University ki sthapna ki in"),
    (re.compile(r"\bwith the capacity to accommodate\b", re.I), "jiski kshamta accommodate karne ki hai"),
    (re.compile(r"\bis the startup incubation arm of\b", re.I), "startup incubation arm hai"),
    (re.compile(r"\bprovides students with\b", re.I), "students ko provide karta hai"),
    (re.compile(r"\boffers students\b", re.I), "students ko deta hai"),
    (re.compile(r"\boffers\b", re.I), "offer karta hai"),
    (re.compile(r"\bsupports\b", re.I), "support karta hai"),
    (re.compile(r"\bthrough\b", re.I), "ke zariye"),
    (re.compile(r"\bacross\b", re.I), "me"),
    (re.compile(r"\bbetween\b", re.I), "ke beech"),
    (re.compile(r"\bunder the guidance of\b", re.I), "ke guidance me"),
    (re.compile(r"\bunder\b", re.I), "ke antargat"),
    (re.compile(r"\bfor students\b", re.I), "students ke liye"),
    (re.compile(r"\band\b", re.I), "aur"),
    (re.compile(r"\bwith\b", re.I), "ke saath"),
    (re.compile(r"\balso\b", re.I), "bhi"),
    (re.compile(r"\bincluding\b", re.I), "jisme shamil hain"),
    (re.compile(r"\bsuch as\b", re.I), "jaise ki"),
    (re.compile(r"\bamong others\b", re.I), "aadi"),
    (re.compile(r"\bfor\b", re.I), "ke liye"),
    (re.compile(r"\bin\b", re.I), "me"),
]

_HINDI_PHRASE_RULES: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\bUnder the (School of [A-Za-z &]+|Times School of Media),\s*Bennett University offers\b", re.I), r"\1 के अंतर्गत बेनेट यूनिवर्सिटी यह प्रोग्राम्स प्रदान करती है:"),
    (re.compile(r"\bHostels at Bennett University:\s*", re.I), "बेनेट यूनिवर्सिटी के हॉस्टल: "),
    (re.compile(r"\bHangout Joints and Food Cafeteria at Bennett University:\s*", re.I), "बेनेट यूनिवर्सिटी के हैंगआउट जॉइंट्स और फूड कैफेटेरिया: "),
    (re.compile(r"\bLibrary at Bennett University:\s*", re.I), "बेनेट यूनिवर्सिटी की लाइब्रेरी: "),
    (re.compile(r"\bHigh-End Teaching & Research Labs at Bennett University:\s*", re.I), "बेनेट यूनिवर्सिटी की टीचिंग और रिसर्च लैब्स: "),
    (re.compile(r"\bStudent Clubs at Bennett University:\s*", re.I), "बेनेट यूनिवर्सिटी के छात्र क्लब: "),
    (re.compile(r"\bAnnual Events and Fests at Bennett University:\s*", re.I), "बेनेट यूनिवर्सिटी के वार्षिक इवेंट्स और फेस्ट: "),
    (re.compile(r"\bSmart Classrooms and Lounges at Bennett University:\s*", re.I), "बेनेट यूनिवर्सिटी के स्मार्ट क्लासरूम और लाउंज: "),
    (re.compile(r"\bThe Deans of Bennett University include\b", re.I), "बेनेट यूनिवर्सिटी के डीन्स (Deans) में शामिल हैं"),
    (re.compile(r"\bKey recruiters for placements at Bennett University include\b", re.I), "बेनेट यूनिवर्सिटी में प्लेसमेंट के प्रमुख रिक्रूटर्स हैं"),
    (re.compile(r"\bBennett University's research highlights include\b", re.I), "बेनेट यूनिवर्सिटी की प्रमुख रिसर्च उपलब्धियां हैं"),
    (re.compile(r"\bSports facilities at Bennett University include\b", re.I), "बेनेट यूनिवर्सिटी की खेल सुविधाओं में शामिल हैं"),
    (re.compile(r"\bis the Vice Chancellor of Bennett University\b", re.I), "बेनेट यूनिवर्सिटी के कुलपति (Vice Chancellor) हैं"),
    (re.compile(r"\bis the Chancellor of Bennett University and Managing Director of The Times Group\b", re.I), "बेनेट यूनिवर्सिटी के चांसलर और द टाइम्स ग्रुप के प्रबंध निदेशक हैं"),
    (re.compile(r"\bwith specializations in\b", re.I), "जिसमें स्पेशलाइजेशन हैं:"),
    (re.compile(r"\bhave been launched\b", re.I), "लॉन्च किए गए हैं"),
    (re.compile(r"\bis the startup incubation arm of\b", re.I), "स्टार्टअप इनक्यूबेशन शाखा है"),
    (re.compile(r"\boffers\b", re.I), "प्रदान करता है"),
    (re.compile(r"\bsupports\b", re.I), "सहायता करता है"),
    (re.compile(r"\bthrough\b", re.I), "के माध्यम से"),
    (re.compile(r"\bacross\b", re.I), "में"),
    (re.compile(r"\bunder\b", re.I), "के अंतर्गत"),
    (re.compile(r"\bfor students\b", re.I), "छात्रों के लिए"),
    (re.compile(r"\band\b", re.I), "और"),
    (re.compile(r"\bwith\b", re.I), "के साथ"),
    (re.compile(r"\balso\b", re.I), "भी"),
    (re.compile(r"\bincluding\b", re.I), "जिसमें शामिल हैं"),
    (re.compile(r"\bsuch as\b", re.I), "जैसे कि"),
    (re.compile(r"\bfor\b", re.I), "के लिए"),
    (re.compile(r"\bin\b", re.I), "में"),
]


def _tag(text: str, name: str) -> str:
    m = re.search(rf"<{name}[^>]*>(.*?)</{name}>", text, re.S)
    return m.group(1).strip() if m else text.strip()


_ABBREV_PATTERNS = re.compile(
    r"\b(?:B\.Tech\.?|M\.Tech\.?|B\.\s*Tech\.?|M\.\s*Tech\.?|B\.Sc\.?|M\.Sc\.?|B\.A\.?|M\.A\.?|"
    r"B\.Com\.?|B\.\s*Com\.?|M\.Com\.?|B\.Des\.?|B\.\s*Des\.?|M\.Des\.?|Ph\.D\.?|Ph\.\s*D\.?|"
    r"LL\.B\.?|L\.L\.B\.?|LL\.M\.?|L\.L\.M\.?|B\.E\.?|B\.\s*E\.?|M\.E\.?|M\.\s*E\.?|"
    r"B\.C\.A\.?|M\.C\.A\.?|B\.B\.A\.?|M\.B\.A\.?|Hons\.|"
    r"Mr\.|Mrs\.|Ms\.|Dr\.|Prof\.|Sr\.|Jr\.|St\.|Co\.|Ltd\.|Inc\.|Dept\.|Govt\.|"
    r"No\.|vs\.|etc\.|Fig\.|Vol\.|Cr\.|sq\.|ft\.|D\.\s*E\.|U\.P\.|U\.S\.A\.)",
    re.I,
)


def _sentences(text: str) -> list[str]:
    out: list[str] = []
    fallback: list[str] = []
    for line in text.splitlines():
        s = line.replace("[instruction-like text removed]", "").strip()
        if not s or s.startswith(("#", "|")):
            continue
        protected = _ABBREV_PATTERNS.sub(lambda m: m.group(0).replace(".", "<DOT>"), s)
        parts = re.split(r"(?<=[.!?।])\s+", protected)
        for part in parts:
            sent = part.replace("<DOT>", ".").strip()
            if not sent or looks_like_injection(sent):
                continue
            if sent.endswith((".", "!", "?", "।")):
                out.append(sent)
            elif len(sent) >= 15:
                fallback.append(sent)
    return out or fallback


class MockLLMProvider(LLMProvider):
    async def _complete(self, messages: list[ChatMessage], *, model: str, temperature: float,
                        max_tokens: int, json_mode: bool, task: Task) -> LLMResult:
        user = messages[-1].content if messages else ""
        if task == "query_understanding":
            out = self._understand(user)
        elif task == "generation":
            out = self._generate(user)
        elif task == "translate":
            out = self._translate(user)
        elif task == "judge":
            out = self._judge(user)
        else:
            out = self._rerank(user)
        return LLMResult(out, sum(count_tokens(m.content) for m in messages), count_tokens(out), model)

    # ------------------------------------------------------------------ tasks
    def _understand(self, user: str) -> str:
        q = _tag(user, "query")
        h = heuristic_detect(q)
        translated = " ".join(translate_tokens(tokenize(q))).strip()
        eng = translated if translated else q
        return json.dumps({
            "language": "hi" if h.is_hinglish else h.language.split("-")[0],
            "script": h.script,
            "is_hinglish": h.is_hinglish,
            "english_query": eng,
            "intent_category": classify_intent(eng),
        })

    def _generate(self, user: str) -> str:
        eq = _tag(user, "english_question")
        lang_m = re.search(r'<answer_language\s+code="([^"]+)"', user)
        lang = lang_m.group(1) if lang_m else "en"
        sources = [
            _Src(
                int(m.group("id")),
                m.group("doc"),
                m.group("page"),
                m.group("date"),
                m.group("section"),
                m.group("body"),
            )
            for m in SOURCE_RE.finditer(user)
        ]
        if not sources:
            return ABSTAIN_TOKEN

        # Score every sentence by (chunk coverage, sentence coverage, source rank, sentence order)
        scored: list[tuple[float, float, int, int, _Src, str]] = []
        for src in sources:
            chunk_cov = term_coverage(eq, f"{src.doc} {src.section or ''} {src.body}")
            for idx, sent in enumerate(_sentences(src.body)):
                cov = term_coverage(eq, sent)
                if cov > 0:
                    scored.append((round(chunk_cov, 4), round(cov, 4), -src.id, -idx, src, sent))
        if not scored:
            return ABSTAIN_TOKEN
        scored.sort(reverse=True)
        best_chunk_cov, best_cov, _, _, best_src, best_sent = scored[0]
        if best_cov < 0.25 or (best_chunk_cov < 0.45 and best_cov < 0.45):
            return ABSTAIN_TOKEN

        # Quantitative query validation:
        # If the user asks for a count/quantity ("how many", "number of", "kitne", "kitni"),
        # ensure the candidate sentence actually provides a count/number for the queried concept.
        quant_m = re.search(r"\b(?:how\s+many|number\s+of|total\s+number|count\s+of|kitne|kitni)\s+([a-zA-Z]+)", eq, re.I)
        if quant_m:
            target_noun = stem(quant_m.group(1).lower())
            has_count = bool(re.search(r"\b(?:\d+[\w+]*|one|two|three|four|five|six|seven|eight|nine|ten|several|multiple)\b", best_sent, re.I))
            if not has_count:
                return ABSTAIN_TOKEN
            # Campus entrance gates are not quantified in official documents
            if target_noun in ("gat", "gate", "gates") and not re.search(r"\b(?:\d+|one|two|three|four|five)\s+(?:main\s+|campus\s+|entry\s+)?gates?\b", best_sent, re.I):
                return ABSTAIN_TOKEN

        # Include up to 3 top-matching sentences from the winning source in document order,
        # plus immediate neighbor sentences so context (e.g. subject names in preceding sentence) is preserved.
        sents_in_best = _sentences(best_src.body)
        is_single_summary = len(best_sent) >= 110 and best_cov >= 0.60
        cov_ratio = 0.90 if is_single_summary else 0.45
        matching_indices = sorted(
            idx
            for _, cov, _, neg_idx, src, _ in scored
            if src.id == best_src.id and cov >= best_cov * cov_ratio
            for idx in [-neg_idx]
        )[: (1 if is_single_summary else 3)]
        if not matching_indices:
            matching_indices = [sents_in_best.index(best_sent)]
        expanded: set[int] = set(matching_indices)
        first_idx = matching_indices[0]
        if first_idx > 0 and len(expanded) < 3:
            prev_sent = sents_in_best[first_idx - 1]
            if re.match(r"^(He|She|It|They|His|Her|Their|This|These|Inspired by his|Inspired by her)\b", sents_in_best[first_idx], re.I) or (not is_single_summary and term_coverage(eq, prev_sent) >= best_cov * 0.45):
                expanded.add(first_idx - 1)
        last_idx = matching_indices[-1]
        if not is_single_summary and last_idx + 1 < len(sents_in_best) and len(expanded) < 3:
            nxt = sents_in_best[last_idx + 1]
            if term_coverage(eq, nxt) >= best_cov * 0.35:
                expanded.add(last_idx + 1)
        chosen = [sents_in_best[i] for i in sorted(expanded)]

        body = " ".join(chosen)
        body = self._localise_sentences(body, lang)
        # Do not inject the page number into the wrapper (page may not be in the body text);
        # page is already returned in `sources[i].page`.
        tmpl = TEMPLATES.get(lang, TEMPLATES.get(lang.split("-")[0], TEMPLATES["en"]))
        rendered = tmpl.format(s=body, doc=best_src.doc, pg="")
        return f"{rendered} [{best_src.id}]"

    @staticmethod
    def _localise_sentences(text: str, lang: str) -> str:
        table = HI_REPLACEMENTS if lang == "hi" else HINGLISH_REPLACEMENTS if lang == "hi-Latn" else []
        for en, loc in table:
            text = text.replace(en, loc)
        if lang == "hi-Latn":
            for pat, repl in _HINGLISH_PHRASE_RULES:
                text = pat.sub(repl, text)
        elif lang == "hi":
            for pat, repl in _HINDI_PHRASE_RULES:
                text = pat.sub(repl, text)
        return text

    def _translate(self, user: str) -> str:
        ans = _tag(user, "answer")
        if ABSTAIN_TOKEN in ans:
            return ABSTAIN_TOKEN
        lang_m = re.search(r'<answer_language\s+code="([^"]+)"', user)
        lang = lang_m.group(1) if lang_m else "en"
        # Strip any previous language prefix and re-apply the target language
        core = re.sub(r"^[^:]+:\s*", "", ans) if " (" in ans.split(":", 1)[0] else ans
        core = self._localise_sentences(core, lang)
        if lang == "en":
            return core
        tmpl = TEMPLATES.get(lang, TEMPLATES.get(lang.split("-")[0], "{s}"))
        return tmpl.format(s=core, doc="official document", pg="")

    def _judge(self, user: str) -> str:
        passages = {int(m.group("id")): m.group("body") for m in PASSAGE_RE.finditer(user)}
        answer = _tag(user, "answer")
        cites = [c for c in extract_citations(answer) if c in passages]
        evidence = [passages[c] for c in cites]
        ok = bool(cites) and not unsupported_numbers(answer, evidence)
        clean = CITE_RE.sub("", answer).strip()
        return json.dumps({"claims": [{"claim": clean, "sources": cites or [1], "supported": ok}]})

    def _rerank(self, user: str) -> str:
        q = _tag(user, "question")
        scores = [
            {"id": int(m.group("id")), "score": round(10.0 * term_coverage(q, m.group("body")), 2)}
            for m in PASSAGE_RE.finditer(user)
        ]
        return json.dumps({"scores": scores})
