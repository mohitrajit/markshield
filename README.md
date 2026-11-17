# MarkShield: Markdown Quality Gate & RAG Verification Agent

An autonomous, deterministic quality gate for technical Markdown files destined for enterprise Retrieval-Augmented Generation (RAG) knowledge bases (e.g., RAGFlow, LangChain, LlamaIndex).

It validates structure, optional YAML front matter, heading outlines, code fences, Mermaid diagrams and flowcharts, tables, multimedia links, YouTube timestamps, and secret hygiene before documents are uploaded to vector indices.

> **Full Use Case Catalog:** For the complete register of all 65 implemented validation rules and chunking patterns, see [`docs/RAG_VALIDATION_USE_CASES.md`](docs/RAG_VALIDATION_USE_CASES.md).

---

## 1. System Architecture & Ingestion Flow

```text
+-------------------------------------------------------------------------+
|                             INBOX DIRECTORY                             |
|          (Incoming .md files and local referenced images/diagrams)      |
+------------------------------------+------------------------------------+
                                     |
                                     v
+------------------------------------+------------------------------------+
|                    AUTONOMOUS DAEMON (agent.py)                         |
|  1. Settle Buffer Check (Wait 5s post-write to prevent race conditions) |
|  2. Dynamic Template Learning & Rules Ingestion (rules.yaml)            |
+------------------------------------+------------------------------------+
                                     |
                                     v
+------------------------------------+------------------------------------+
|                  VERIFIER CORE ENGINE (verifier.py)                     |
|  - 10-Pass Structural, Syntactic & Security Inspection                 |
|  - Front-matter schema, heading trees, tables, code, links, YouTube     |
+------------------------------------+------------------------------------+
                                     |
                  +------------------+------------------+
                  |                                     |
         [ALL CHECKS PASSED]                   [ERRORS DETECTED]
                  |                                     |
                  v                                     v
+-----------------+---------------+   +-----------------+-----------------+
|        VERIFIED/ STORAGE        |   |         FAILED/ STORAGE         |
|  - Markdown file moved          |   |  - Markdown file quarantined      |
|  - Local image assets copied    |   |  - Local assets copied            |
|  - Ready for RAGFlow Ingestion  |   |  - Standalone .report.txt emitted |
+-----------------+---------------+   +-----------------+-----------------+
                  |                                     |
                  +------------------+------------------+
                                     |
                                     v
+------------------------------------+------------------------------------+
|                       REPORTING & NOTIFICATION                          |
|  - OpenPyXL Multi-Tab Excel (.xlsx): Master Summary + Document Tabs     |
|  - Clean HTML Executive Dashboard (No messy inline error dumps)          |
|  - SMTP Enterprise Email Dispatch (Gmail Relay, STARTTLS/SSL, CC/BCC)   |
+-------------------------------------------------------------------------+
```

### Directory Topology
- **`inbox/`**: Staging directory for incoming Markdown documents and their local image assets.
- **`verified/`**: Production storage. Contains only documents that passed validation with **0 errors**.
- **`failed/`**: Quarantine folder. Holds failed documents alongside a companion `<filename>.report.txt` error log.
- **`reports/`**: Audit archive containing JSON batch reports, HTML dashboards, and multi-tab `.xlsx` spreadsheets.

---

## 2. Quick Start

### Installation
Requires Python 3.10+ (tested on Python 3.13 Windows 64-bit).

```powershell
python -m pip install -r requirements.txt
```

*Required packages: `PyYAML>=6.0`, `openpyxl>=3.0.0`.*

### Core Execution Commands

```powershell
# 1. Validate a single document via CLI (exit code 0 = pass, 1 = fail)
python verifier.py path/to/document.md

# 2. Validate with JSON machine output
python verifier.py path/to/document.md --json

# 3. Process all settled inbox files once and exit
python agent.py --once --settle 0

# 4. Start 24/7 background folder watcher (polls every 30s)
python agent.py

# 5. Diagnostic SMTP test: verify credentials, send email, and attach test Excel
python agent.py --test-email

# 6. Execute mutation regression test suite (verifies 46 rule breakages)
python test_mutations.py
```

---

## 3. Dynamic Template Learning & Rules Architecture

The verifier does not hardcode document structures. Instead, it **dynamically learns** the expected schema from the golden master template (`RAG-SAMPLE-MASTER-TEMPLATE.md`):

1. **Front-Matter Introspection**: Discovers required keys and classifies their types:
   - `str`, `int`, `date`, `list`, or `records` (list of dictionaries with consistent keys).
2. **Canonical Section Sequencing**: Records the exact sequence of Level 2 (`##`) headings.
3. **YAML Configuration Overlay (`rules.yaml`)**:
   - `field_overrides`: Adds regex patterns, enumerations, min/max item limits.
   - `optional_keys`: Declares permitted extra keys (e.g. `ekg_config_version`) to prevent false alarms.
   - `section_types`: Maps titles to section roles via case-insensitive regexes (`procedure`, `troubleshooting`, `faq`, `diagrams`).
   - `legacy`: Flags deprecated structures for cleanup (`E066`, `E067`, `E068`, `E014`).

---

## 4. Master Error Codes Catalog (E001 - E099)

Every reported issue includes the exact source line number, severity (`ERROR` or `WARNING`), description, RAG pipeline impact, and actionable fix:

| Code Range | Category | Key Inspection Areas |
|:---|:---|:---|
| **E001 - E002** | Encoding & I/O | UTF-8 Byte Order Mark (BOM) detection; file read/route permissions. |
| **E010 - E019** | Metadata | YAML syntax, missing/duplicate keys, data types, date formatting, title mismatch (`title` vs `# H1`), and unreplaced template placeholders (`VIDEO_ID`). |
| **E020 - E029** | Structure | Missing mandatory sections (Overview), heading hierarchy (H1-H5), strict numbering (`## N. Title`), subheadings (`2.1`, `11.1.1`), and canonical section ordering. |
| **E030 - E033** | Code Fences | Unclosed fences, mandatory language tags (` ```sql `), empty blocks, and blank line padding. |
| **E040 - E043** | Tables | Malformed separator rows (`|---|`), mismatched column counts across rows, and missing blank line margins. |
| **E050 - E058** | Links & Images | Missing local images, base64 bloat, missing alt text, empty URLs, unencoded spaces, vague text (`click here`), and broken internal anchors. |
| **E060 - E068** | Source & Context | Source file consistency, legacy context lines (`**Doc ID:**`), and obsolete H1 header blocks. |
| **E070 - E077** | Quality & Security | Hardcoded secrets/API keys (`E074`), raw HTML tags, escaped markdown backslashes, tabs, oversized chunks (>2500 chars), and final newline. |
| **E080 - E086** | Procedures & Video | Missing procedure goals/results, step sequences (`Step N - Title`), YouTube timestamp syntax, MM:SS to seconds arithmetic (`E083`), and video ID consistency. |
| **E090 - E098** | Semantic Features | Troubleshooting triads (`Symptom`/`Cause`/`Fix`), FAQ syntax (`Q: ...?` / `A:`), Mermaid diagram syntax, diagram text descriptions (`E094`), callout labels (`E095`), and chapter index tables (`E098`). |
| **E099** | Engine | Unhandled verifier parser exceptions. |

*Errors fail a document and route it to `failed/`. Warnings highlight quality improvements and do not fail the document unless `fail_on_warnings: true` is configured in `rules.yaml`.*

---

## 5. Enterprise Reporting & Email Configuration

### Multi-Tab Excel Workbook (`openpyxl`)
Every batch run generates a formatted `.xlsx` workbook in `reports/` and attaches it to the notification email:
- **`Summary` Tab**: Executive dashboard with document names, color-coded status badges, error/warning tallies, pointers to document sheet tabs, and human-readable timestamps (`YYYY-MM-DD HH:MM:SS`).
- **Dedicated Document Tabs**: Each processed document receives an isolated worksheet tab named safely via `_safe_sheet_title()` (clamped to 31 chars, illegal characters sanitized, duplicate stems resolved). Contains frozen headers, autofilters, wrapped text, and exact line-by-line issue details.

### Clean HTML Email Dashboard
The email body displays a clean status card and attachment callout. Forensic issue dumps are excluded from the HTML body, keeping emails lightweight and readable on all mobile and desktop email clients.

### Email Configuration (`.env`)
The agent natively parses `.env` without third-party dependencies:

```ini
# SMTP Relay Configuration (Gmail Relay Example)
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_SECURITY=starttls
SMTP_USER=mohitrajsingh2601@gmail.com
SMTP_PASS=xxxx xxxx xxxx xxxx          # 16-character Google App Password

# Recipient Addresses
MAIL_FROM=mohitrajsingh2601@gmail.com
MAIL_TO=mohit.raj@radiantglobaltech.com
MAIL_CC=engineering-leads@radiantglobaltech.com
MAIL_BCC=rag-audit-archive@radiantglobaltech.com

# Operational Parameters
POLL_SECONDS=30
SETTLE_SECONDS=5
INBOX=inbox
VERIFIED=verified
FAILED=failed
REPORTS=reports
```

*Note: Microsoft 365 tenants with disabled SMTP client authentication (`535 5.7.139`) should route through an authorized Gmail relay or internal corporate relay as shown above.*

---

## 6. Testing & Quality Assurance

### Mutation Testing (`test_mutations.py`)
Rather than relying on basic happy-path assertions, the verification suite uses **Mutation Testing**:
- It loads `RAG-SAMPLE-MASTER-TEMPLATE.md` and programmatically introduces 46 deliberate syntactic, structural, and metadata defects.
- It verifies that the verifier catches **every single defect** with the exact expected error code and line number.

Run the test suite anytime code or rules are modified:
```powershell
python test_mutations.py
# Expected output: 46 mutations, 0 problems [VERDICT: PASS]
```

---

## 7. Operational Maintenance Guide

### How to Update Rules or Template
1. **To change the document contract**: Edit `RAG-SAMPLE-MASTER-TEMPLATE.md`. The verifier automatically updates its learned expectations on the next run.
2. **To adjust strictness or patterns**: Edit `rules.yaml` (e.g. adjust `doc_id` regex, add `optional_keys`, or modify allowed HTML tags).
3. **To verify changes**: Run `python test_mutations.py`. If you altered golden template structures, update `test_mutations.py` to match the new baseline strings.
4. **To update documentation**: Run `python build_full_suite.py` to regenerate `RAG_Markdown_Document_Verification_Agent_Booklet.docx` and `python build_onenote_docs.py` to regenerate the OneNote exports.

---

## 8. Strategic Roadmap

- **Phase 2 (Ingestion Hook)**: Direct API hook to upload verified documents into RAGFlow datasets immediately upon passing.
- **Phase 3 (AI Auto-Fixer)**: Autonomous self-healing module to automatically fix whitespace, missing blank lines around headings/tables, and code language tags before quarantine.
- **Phase 4 (Semantic Quality Reviewer)**: Optional LLM evaluation stage to verify title-content coherence, procedure expected results, and QA answerability.
- **Phase 5 (Centralized Telemetry)**: Web dashboard displaying batch trends, common failure codes, and ingestion health metrics.

---

## 9. Source-of-Truth Architecture

The following matrix defines which files serve as the authoritative source of truth for each subsystem, and which documentation chapters depend on them:

| Authoritative File | Subsystem / Responsibility | Dependent Documentation Chapters |
|:---|:---|:---|
| **`verifier.py`** | 10-Pass Deterministic Verification Engine, Error Catalog (E001-E099), Regex Scanners | Chapter 1, Chapter 3, Chapter 5, Chapter 12 (Appendix) |
| **`agent.py`** | Autonomous Daemon, File Routing (`verified/`/`failed/`), Multi-Tab Excel Generator, SMTP Relay | Chapter 2, Chapter 4, Chapter 5, Chapter 8 |
| **`rules.yaml`** | Declarative Schema Constraints (`field_overrides`, `optional_keys`, `section_types`, `legacy`) | Chapter 3, Chapter 5, Chapter 12 (Appendix) |
| **`RAG-SAMPLE-MASTER-TEMPLATE.md`** | Golden Master Contract; Authoritative Markdown Patterns Learned at Runtime | Chapter 1, Chapter 3, Chapter 5 |
| **`test_mutations.py`** | 46-Mutation Regression Test Suite; Proof of Validator Sensitivity | Chapter 6, Chapter 7, Chapter 9 |
| **`.env` / `.env.example`** | Environment Variables & Secrets Configuration (SMTP Relay, Polling Frequencies) | Chapter 8, Chapter 12 (Appendix) |
| **`docs/`** | Generated Technical Documentation Record (Word Booklet, OneNote, Open Questions) | Complete Project Documentation Package |

---

## 10. Maintenance Guide: How to Update Documentation

When changes occur in the project, follow this exact procedure to update the codebase and synchronize the documentation records:

| Change Type | Primary Files to Edit | Documentation Sections to Refresh | Verification Step |
|:---|:---|:---|:---|
| **Dependency Added or Upgraded** | `requirements.txt` | README.md Section 2, Chapter 8 Section 8.1 | Run `python -m pip install -r requirements.txt` and verify imports. |
| **New Verification Rule or Code Added** | `verifier.py`, `rules.yaml` | README.md Section 4, Chapter 4 & Chapter 12 | Add corresponding mutation in `test_mutations.py` and run test suite. |
| **Master Template Structure Changed** | `RAG-SAMPLE-MASTER-TEMPLATE.md` | README.md Section 3, Chapter 3 & Chapter 5 | Re-align baseline strings in `test_mutations.py` and run `python test_mutations.py`. |
| **Config or Environment Variable Added** | `rules.yaml`, `.env.example`, `agent.py` | README.md Section 5, Chapter 8 & Chapter 12 | Test with `python agent.py --once --settle 0`. |
| **Deployment Mode or CLI Flags Changed** | `agent.py` | README.md Section 2, Chapter 8 Section 8.4 | Execute CLI commands with new flags and inspect output. |
| **Problem Solved / Bug Fixed** | `verifier.py` or `agent.py` | README.md CHANGELOG, Chapter 7 Problem-Solution Matrix | Record root cause, fix, and outcome in Chapter 7 and CHANGELOG. |
| **Production Metrics Measured** | `docs/OPEN_QUESTIONS.md` | Chapter 9 Section 9.3, `docs/OPEN_QUESTIONS.md` | Replace `[ADD METRIC]` with measured values in Word and OneNote docs. |

To regenerate all Word and OneNote documentation records after making changes:
```powershell
python docs/generate_all.py
```

---

## 11. Project Changelog

### [2.1.0] - 2026-11-17
- **Branding & Repository Creation:** Established GitHub repository as **MarkShield** (`mohitrajit/markshield`).
- **Shift to RAG Syntax & Pattern Quality Gate:**
  - Front matter (page properties) is now optional by default (`front_matter_required: false`), while retaining strict syntax, enum, and typing checks whenever present.
  - Documents are no longer restricted to rigid master-template section names or fixed section sequences, enabling general technical Markdown documentation to be verified for RAG ingestion.
- **Enhanced Flowchart & Diagram Checks:**
  - Strict Mermaid syntax validation (type declaration, direction requirement for flowcharts/graphs, bracket balancing, and valid arrow connectors).
  - Enforced `**Text description:**` below Mermaid and ASCII diagram blocks so vector retrieval engines can index visual architectures.
- **Added Comprehensive Use Case Catalog:**
  - Created [`docs/RAG_VALIDATION_USE_CASES.md`](docs/RAG_VALIDATION_USE_CASES.md) cataloging all 65 implemented structural, syntactic, and security rules across 11 functional categories.
- **Cleaned Runtime Memory:**
  - Emptied `verified/`, `failed/`, and `reports/` directories for a clean operational state.

### [2.0.0] - 2026-11-13
- **Added:** Full technical documentation suite under `docs/`:
  - `docs/Md_Validator_Documentation.docx` (12 chapters, Arial 11pt, real TOC field, styled tables).
  - `docs/onenote/` (Chapters 01 through 12 in standalone HTML format + `HOW_TO_IMPORT.md`).
  - `docs/OPEN_QUESTIONS.md` (Register of all `[VERIFY]` and `[ADD METRIC]` items).
- **Added:** Merged Source-of-Truth architecture table and Maintenance Update Guide into `README.md`.
- **Verified:** 46/46 mutation regression tests passing (`test_mutations.py`).
- **Cleaned:** Removed loose temporary document files from repository root.

### [1.2.0] - 2026-11-05
- **Added:** Multi-tab Excel workbook generation (`openpyxl`) with Master Summary tab + dedicated per-document tabs.
- **Added:** Safe 31-character worksheet title sanitizer (`_safe_sheet_title`) with duplicate collision handling.
- **Added:** `MAIL_CC` and `MAIL_BCC` support in `agent.py`.
- **Fixed:** Decoupled `stamp_file` from human-readable `display_time` (`YYYY-MM-DD HH:MM:SS`).

### [1.1.0] - 2026-11-04
- **Added:** Personal Gmail SMTP relay configuration with Google App Passwords to bypass M365 tenant auth block (`535 5.7.139`).
- **Added:** Dual STARTTLS (port 587) and SSL (port 465) security modes in `agent.py`.
- **Fixed:** UnicodeEncodeError on Windows terminals by replacing raw paperclip emojis with `&#128206;`.
- **Fixed:** Removed cluttered top-10 inline issue table from HTML email bodies.

### [1.0.0] - 2026-11-04
- **Added:** Initial deterministic verification engine (`verifier.py`) with 10 inspection passes.
- **Added:** Autonomous folder watcher daemon (`agent.py`) with 5-second write settlement buffer.
- **Added:** Relative image asset tracking and link rewriting (`_local_images`, `_rewrite_image_links`).
- **Added:** Golden master contract (`RAG-SAMPLE-MASTER-TEMPLATE.md`) and YAML rules overlay (`rules.yaml`).
