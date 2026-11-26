# Dataset Reference — Multilingual College RAG Knowledge Base

This document provides a comprehensive specification of the institutional dataset, ingestion corpus, metadata schemas, and the evaluation golden dataset used by the **College Multilingual RAG Assistant**.

---

## 1. Document Corpus Overview

The primary knowledge base consists of official regulatory, academic, residential, and administrative circulars from **Bennett University (Times of India Group)**.

### Active Primary Documents in Corpus:

| Document Identifier | Category | Pages | Format | Content Summary |
| :--- | :--- | :---: | :---: | :--- |
| `Bennett-Brochure__2026-11-12__v1.pdf` | `admissions` | 32 | PDF | Complete institutional brochure: School of Artificial Intelligence programs (B.Tech, BCA, MCA, M.Tech, Ph.D.), School of Engineering, School of Management, School of Law, faculty leadership (Vice Chancellor, Deans), 1200+ placement recruiters, campus incubation (Bennett Hatchery, 70+ startups, ₹5.5 Cr seed fund), food outlets, sports, and hostels. |
| `Hostel-Guidelines-2026.pdf` | `hostel` | 4 | PDF | Resident student guidelines: 10:00 PM curfew timing, biometric attendance, night-out pass procedures, cafeteria timings, prohibited appliances, laundry services, and disciplinary penalties. |
| `Fee-Structure-2026-27.pdf` | `fees` | 3 | PDF | Academic program tuition schedules, annual hostel fees, one-time security deposit terms, installment schedules, and UGC refund policies. |
| `Examination-Rules-2026.pdf` | `exams` | 5 | PDF | Academic regulations: 75% minimum mandatory attendance criterion, grading scale (Letter grades A+ to F), CGPA calculation, debarment policy, and re-evaluation guidelines. |
| `Exam-Form-Circular-2026.pdf` | `circulars` | 2 | PDF | Semester exam registration: online portal deadlines, late submission penalty schedule (₹500 to ₹2000), and admit card issuance prerequisites. |
| `Scholarship-Policy-2026.pdf` | `scholarships` | 3 | PDF | Academic merit scholarships (10% to 100% tuition waiver), minimum CGPA renewal thresholds (8.5+ CGPA), sports scholarships, and sibling concessions. |

---

## 2. Ingestion Pipeline & Azure Blob Storage Hierarchy

Documents in Azure Blob Storage (`collegedocsdemo` container `college-docs`) follow a standardized naming convention:

```text
<category>/<title>__<YYYY-MM-DD>__v<version>.<ext>
```

### Examples:
- `admissions/Bennett-Brochure__2026-11-12__v1.pdf`
- `circulars/Exam-Form-Circular__2026-08-15__v2.pdf`
- `hostel/Hostel-Guidelines__2026-07-01__v1.pdf`

### Supported Categories:
- `admissions`
- `fees`
- `exams`
- `hostel`
- `scholarships`
- `circulars`
- `other`

### Accompanying Metadata Schema (`*.meta.json`):
Each document can have an optional companion `.meta.json` file providing structured override metadata:
```json
{
  "category": "admissions",
  "effective_date": "2026-11-12",
  "version": "1",
  "language": "en",
  "title": "Bennett University Admissions Brochure 2026"
}
```

---

## 3. Chunking & Text Representation Strategy

To ensure zero hallucination and preserve table structures:
1. **Window Size**: 512 tokens with a **64-token sliding overlap** to prevent loss of sentence context across split boundaries.
2. **Structural Header Prefix**: Each chunk is dynamically injected with an authoritative header during ingestion:
   ```text
   [Document: Bennett-Brochure.pdf | Category: admissions | Page: 13 | Version: 1]
   ```
3. **Dual Embedding Representation**:
   - **Dense Embeddings**: Generated using OpenAI `text-embedding-3-small` (1536 dimensions) or hashed cross-lingual character n-grams in local mock mode.
   - **Sparse Lexical Inverted Index**: BM25 index built over normalized tokens with punctuation and case normalization.

---

## 4. Evaluation Golden Benchmark Dataset (`golden_set.jsonl`)

The golden dataset is used by `python -m eval.run_eval` to compute automated accuracy, citation, and abstention scores.

```jsonl
{"question": "हॉस्टल में रात को वापस आने का समय क्या है?", "language": "hi", "expected_doc": "Hostel-Guidelines-2026.pdf", "expected_page": 2, "should_abstain": false}
{"question": "B.Tech ki annual tuition fee kitni hai?", "language": "hi-Latn", "expected_doc": "Fee-Structure-2026-27.pdf", "expected_page": 1, "should_abstain": false}
{"question": "What is the minimum attendance required to appear in end-semester exams?", "language": "en", "expected_doc": "Examination-Rules-2026.pdf", "expected_page": 1, "should_abstain": false}
{"question": "What is the last date and late fine for the odd-semester examination form?", "language": "en", "expected_doc": "Exam-Form-Circular-2026.pdf", "expected_page": 1, "should_abstain": false}
{"question": "What is the CGPA required for the Institute Merit Scholarship?", "language": "en", "expected_doc": "Scholarship-Policy-2026.pdf", "expected_page": 1, "should_abstain": false}
{"question": "विदेशी भाषा फ्रेंच डिप्लोमा की फीस कितनी है?", "language": "hi", "expected_doc": null, "expected_page": null, "should_abstain": true}
{"question": "What are the swimming pool membership charges?", "language": "en", "expected_doc": null, "expected_page": null, "should_abstain": true}
{"question": "விடுதி இரவு நேரம் என்ன?", "language": "ta", "expected_doc": "Hostel-Guidelines-2026.pdf", "expected_page": 2, "should_abstain": false}
```

### Breakdown of Golden Test Queries:
1. **Multilingual Factual Queries**: Evaluates cross-lingual transfer (answering Hindi or Tamil queries using English documents).
2. **Code-Mixed Hinglish Queries**: Evaluates colloquial student terminology (`"B.Tech ki annual tuition fee kitni hai?"`).
3. **Adversarial / Out-of-Domain Queries**: Intentionally asks questions absent from the corpus (e.g., French diploma fee, swimming pool charges) to verify that the system returns 100% abstention (`"Official documents do not contain this information."`) rather than hallucinating answers.

---

## 5. How to Ingest New Documents

### Option A: Local CLI Ingestion
Place your PDF into `college-rag-backend/data/college-docs/<category>/` and run:
```powershell
cd college-rag-backend
C:\Users\gdsin\AppData\Local\Programs\Python\Python313\python.exe -m scripts.ingest --all
```

### Option B: Cloud Azure Blob Upload
Upload the PDF directly into your Azure Storage container `college-docs` under the folder prefix `<category>/`. The backend automatically indexes new blobs on startup or via the Azure Function trigger in `functions/blob_trigger/`.
