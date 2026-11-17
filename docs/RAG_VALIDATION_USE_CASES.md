# RAG Markdown Validation Use Cases

Authoritative catalog of all Markdown structural, syntactic, and RAG chunking validation use cases implemented in **MarkShield** (`verifier.py` & `rules.yaml`).

---

## 1. Document & File Hygiene
* `UC-DOC-01`: **UTF-8 Encoding & BOM Detection** (`E001`) — Rejects non-UTF-8 bytes and UTF-8 Byte Order Marks (`\ufeff`) that corrupt chunk splitters. `[IMPLEMENTED]`
* `UC-DOC-02`: **File Readability & Path Resolution** (`E002`) — Gracefully flags missing or unreadable files. `[IMPLEMENTED]`
* `UC-DOC-03`: **Trailing Newline Enforcement** (`E077`) — Ensures documents terminate with a standard newline. `[IMPLEMENTED]`
* `UC-DOC-04`: **Control Character Detection** (`E072`) — Flags non-printable control characters `[\x00-\x08\x0b\x0c\x0e-\x1f]`. `[IMPLEMENTED]`
* `UC-DOC-05`: **Raw Disallowed HTML Tag Restriction** (`E072`) — Flags unescaped raw HTML like `<script>`, `<iframe>`, `<div>`, etc., that corrupts downstream tokenizers. `[IMPLEMENTED]`
* `UC-DOC-06`: **Line Length Threshold** (`E071`) — Warns on excessively long lines (>2000 chars) indicating minified blobs. `[IMPLEMENTED]`

---

## 2. Page Properties / YAML Front Matter (Optional, Validated When Present)
* `UC-FM-01`: **Optional Front Matter Compatibility** — Documents without front matter pass cleanly without requiring empty metadata. `[IMPLEMENTED]`
* `UC-FM-02`: **Front Matter Delimiter Integrity** (`E010`) — Enforces matching opening and closing `---` delimiters on line 1. `[IMPLEMENTED]`
* `UC-FM-03`: **Valid YAML Key-Value Mapping** (`E010`) — Verifies front matter parses into a valid key-value dictionary. `[IMPLEMENTED]`
* `UC-FM-04`: **Duplicate YAML Key Detection** (`E015`) — Catches duplicate keys that cause silent parser value overwriting. `[IMPLEMENTED]`
* `UC-FM-05`: **Title Consistency Matching** (`E016`) — Verifies that if front-matter `title` is present, it matches the document's H1 title. `[IMPLEMENTED]`
* `UC-FM-06`: **Front Matter Type Validation** (`E012`) — Enforces string, integer, date, list, and records structures. `[IMPLEMENTED]`
* `UC-FM-07`: **Date Format Compliance** (`E013`) — Validates `YYYY-MM-DD` ISO dates on fields like `last_reviewed`. `[IMPLEMENTED]`
* `UC-FM-08`: **Enum & Pattern Validation** (`E013`) — Enforces regex patterns (e.g., `doc_id`) and enum values (e.g., `difficulty`) when present. `[IMPLEMENTED]`
* `UC-FM-09`: **References Records Validation** (`E011` / `E013`) — Enforces structured references (`name`, valid `url`, media `type`). `[IMPLEMENTED]`
* `UC-FM-10`: **Overdue Review Warning** (`E018`) — Warns when `last_reviewed` + `review_cycle_days` has expired. `[IMPLEMENTED]`

---

## 3. Headings & Hierarchy (RAG Chunking & Breadcrumbs)
* `UC-HEAD-01`: **ATX Heading Space Enforcement** (`E024`) — Flags broken headings like `##Heading` or `#Title` missing a space after `#`. `[IMPLEMENTED]`
* `UC-HEAD-02`: **Single Primary Document Title (H1)** (`E022`) — Requires exactly one primary `# Title` as the main chunk breadcrumb. `[IMPLEMENTED]`
* `UC-HEAD-03`: **H1 Top-of-Document Placement** (`E022`) — Ensures the H1 is the first content element after front matter. `[IMPLEMENTED]`
* `UC-HEAD-04`: **Multiple H1 Prohibition** (`E023`) — Prevents multiple top-level `# Title` headings that confuse chunk hierarchy. `[IMPLEMENTED]`
* `UC-HEAD-05`: **No Skipped Heading Levels** (`E021`) — Flags invalid level jumps (e.g., H1 $\to$ H3 or H2 $\to$ H4) that break hierarchy trees. `[IMPLEMENTED]`
* `UC-HEAD-06`: **Non-Empty Heading Validation** (`E024`) — Flags empty headings like `## ` or `### `. `[IMPLEMENTED]`
* `UC-HEAD-07`: **Duplicate Sibling Heading Warning** (`E024`) — Warns on duplicate headings creating ambiguous vector chunk anchors. `[IMPLEMENTED]`
* `UC-HEAD-08`: **Heading Blank Line Padding** (`E075`) — Enforces blank lines before and after headings to prevent paragraph concatenation. `[IMPLEMENTED]`
* `UC-HEAD-09`: **Hierarchical Section Numbering Consistency** (`E025` / `E026`) — If numbered headings are used (`## 1. `, `### 1.1 `), enforces ascending order and parent-child fit. `[IMPLEMENTED]`

---

## 4. Code Fences & Syntax (Code Chunkers & Parsers)
* `UC-CODE-01`: **Matching Fence Delimiters** (`E030`) — Requires closing fence delimiter length to match or exceed opening fence. `[IMPLEMENTED]`
* `UC-CODE-02`: **Unclosed Code Fence Detection** (`E030`) — Flags unclosed fences that swallow remaining document text into code. `[IMPLEMENTED]`
* `UC-CODE-03`: **Mandatory Language Identifier** (`E031`) — Enforces language tag on code fences (`python`, `sql`, `json`, `bash`, `yaml`, `mermaid`, `text`, etc.). `[IMPLEMENTED]`
* `UC-CODE-04`: **Non-Empty Code Block Validation** (`E032`) — Flags empty code fences that create useless chunks. `[IMPLEMENTED]`
* `UC-CODE-05`: **Code Fence Blank Line Padding** (`E033`) — Enforces blank lines before opening fence and after closing fence. `[IMPLEMENTED]`
* `UC-CODE-06`: **Suspect Unclosed Inner Fence Detection** (`E030`) — Detects newly opened fences before prior fences were closed. `[IMPLEMENTED]`

---

## 5. Flowcharts & Diagrams (Mermaid & Visual Knowledge)
* `UC-DIAG-01`: **Valid Mermaid Diagram Declaration** (`E093`) — Validates diagram type (`flowchart`, `graph`, `sequenceDiagram`, `stateDiagram-v2`, `erDiagram`, `classDiagram`, `gantt`, etc.). `[IMPLEMENTED]`
* `UC-DIAG-02`: **Flowchart Direction Requirement** (`E093`) — Enforces direction declarations (`TD`, `TB`, `LR`, `RL`, `BT`) on flowcharts and graphs. `[IMPLEMENTED]`
* `UC-DIAG-03`: **Diagram Node Bracket Balance** (`E093`) — Validates balanced `[]`, `{}`, `()`, `(())`, `[[]]` in flowchart node definitions. `[IMPLEMENTED]`
* `UC-DIAG-04`: **Flowchart Connection Arrow Syntax** (`E093`) — Flags invalid arrows (e.g., bare `->`) and enforces standard Mermaid connectors (`-->`, `---`, `-.->`, `==>`, `-->|label|`). `[IMPLEMENTED]`
* `UC-DIAG-05`: **Diagram Text Description Requirement** (`E094`) — Enforces an accompanying `**Text description:**` directly below diagrams so vector models can index graphic knowledge. `[IMPLEMENTED]`
* `UC-DIAG-06`: **ASCII / Text Architecture Diagram Validation** (`E094`) — Validates plain-text diagram blocks and ensures accompanying text explanations. `[IMPLEMENTED]`

---

## 6. GFM Markdown Tables (Table Chunker Compatibility)
* `UC-TBL-01`: **Table Header & Separator Delimiter Row** (`E040`) — Enforces header row followed immediately by `|---|---|` delimiter row. `[IMPLEMENTED]`
* `UC-TBL-02`: **Delimiter Cell Syntax Compliance** (`E040`) — Validates delimiter cells conform to `:?-{3,}:?`. `[IMPLEMENTED]`
* `UC-TBL-03`: **Column Count Consistency** (`E041`) — Validates every data row matches the exact column count of the header. `[IMPLEMENTED]`
* `UC-TBL-04`: **Outer Pipe Enclosure** (`E040`) — Enforces rows starting and ending with pipe `|`. `[IMPLEMENTED]`
* `UC-TBL-05`: **Table Blank Line Padding** (`E042`) — Enforces blank lines before and after tables to prevent chunk boundary distortion. `[IMPLEMENTED]`
* `UC-TBL-06`: **Non-Empty Table Data Validation** (`E043`) — Flags tables containing only headers without any data rows. `[IMPLEMENTED]`

---

## 7. Lists, Checklists & Indentation
* `UC-LIST-01`: **Standard Unordered List Formatting** (`E076`) — Enforces `- ` or `* ` bullet markers. `[IMPLEMENTED]`
* `UC-LIST-02`: **Standard Ordered List Formatting** — Enforces sequential `1. `, `2. ` step numbering. `[IMPLEMENTED]`
* `UC-LIST-03`: **GFM Task List Syntax** (`E076`) — Validates `- [ ] ` and `- [x] ` task items; flags malformed checkboxes. `[IMPLEMENTED]`
* `UC-LIST-04`: **Space-Only Indentation** (`E076`) — Flags tab characters used for indentation to ensure consistent parser rendering. `[IMPLEMENTED]`

---

## 8. Blockquotes & Callouts / Alerts
* `UC-CALL-01`: **Continuous Blockquote Prefix** (`E095`) — Enforces `>` prefix across all lines of blockquote blocks. `[IMPLEMENTED]`
* `UC-CALL-02`: **GFM Alert Syntax Support** — Supports standard alerts (`> [!NOTE]`, `> [!TIP]`, `> [!IMPORTANT]`, `> [!WARNING]`, `> [!CAUTION]`). `[IMPLEMENTED]`
* `UC-CALL-03`: **Bold Label Callout Support** (`E095`) — Supports bold labels (`> **Note:**`, `> **Warning:**`, `> **Tip:**`, `> **Important:**`, `> **Purpose:**`, `> **Rule:**`). `[IMPLEMENTED]`
* `UC-CALL-04`: **Callout Emoji/Label Agreement** (`E095`) — Validates emoji/label consistency (🟢 Tip, 🟡 Warning, 🔴 Important, 🔵 Info). `[IMPLEMENTED]`

---

## 9. Links, Images & Multimedia
* `UC-LINK-01`: **Markdown Link Syntax** (`E053`) — Validates `[text](url)` format; flags empty URLs or link text. `[IMPLEMENTED]`
* `UC-LINK-02`: **URL Space Sanitation** (`E054`) — Flags unencoded spaces in link URLs. `[IMPLEMENTED]`
* `UC-LINK-03`: **Non-Vague Link Anchor Text** (`E055`) — Flags low-information text like "click here", "here", "link" for better citation context. `[IMPLEMENTED]`
* `UC-LINK-04`: **Internal Heading Anchor Validity** (`E057`) — Verifies `#anchor` internal links resolve to an actual heading slug. `[IMPLEMENTED]`
* `UC-LINK-05`: **Reference Links & Footnotes Resolution** (`E056`) — Ensures every reference link `[ref][id]` and footnote `[^1]` has a matching definition. `[IMPLEMENTED]`
* `UC-IMG-01`: **Mandatory Image Alt Text** (`E052`) — Flags `![](url)` with missing alt text. `[IMPLEMENTED]`
* `UC-IMG-02`: **Alt Text Quality Warning** (`E052`) — Warns when alt text is < 10 characters to ensure adequate RAG visual context. `[IMPLEMENTED]`
* `UC-IMG-03`: **Disallow Inline Base64 Images** (`E051`) — Flags inline base64 blobs that bloat vector chunk embeddings. `[IMPLEMENTED]`
* `UC-IMG-04`: **Local Image File Existence** (`E050`) — Verifies referenced relative image files actually exist on disk beside the document. `[IMPLEMENTED]`
* `UC-MEDIA-01`: **YouTube Timestamp Syntax** (`E082`) — Enforces `&t=SECONDSs` format in video timestamp URLs. `[IMPLEMENTED]`
* `UC-MEDIA-02`: **Video Timestamp Time/URL Synchronization** (`E083`) — Validates displayed `MM:SS` matches `t=SECONDSs` in the URL. `[IMPLEMENTED]`

---

## 10. Secrets, Security & Text Hygiene
* `UC-SEC-01`: **API Key & Token Leak Detection** (`E074`) — Detects OpenAI (`sk-...`), GitHub (`ghp_...`), AWS (`AKIA...`), and Bearer tokens. `[IMPLEMENTED]`
* `UC-SEC-02`: **Password & Credential Detection** (`E074`) — Detects plaintext password assignments (`password=...`). `[IMPLEMENTED]`
* `UC-SEC-03`: **Private Key Certificate Detection** (`E074`) — Flags `-----BEGIN ... PRIVATE KEY-----` blocks. `[IMPLEMENTED]`
* `UC-SEC-04`: **Escaped Markdown Outside Code** (`E073`) — Flags backslash escapes (`\*\*text\*\*`) that show up literally in chunk embeddings. `[IMPLEMENTED]`
* `UC-SEC-05`: **Trailing Backslash Line Breaks** (`E073`) — Flags trailing backslashes that cause unexpected CommonMark line joins. `[IMPLEMENTED]`
* `UC-SEC-06`: **Template Placeholder Detection** (`E017`) — Flags unreplaced placeholders (`DOC_ID_`, `VIDEO_ID`, `example.com`). `[IMPLEMENTED]`

---

## 11. Chunk Boundaries & RAG Splitting Limits
* `UC-CHUNK-01`: **Maximum Heading Chunk Size Warning** (`E070`) — Warns when text under a single heading exceeds 2,500 characters without subheadings, preventing arbitrary mid-thought sentence splitting. `[IMPLEMENTED]`
* `UC-CHUNK-02`: **Sequential Procedure Steps** (`E080` / `E081`) — Validates step sequence (`Step 1 - ...`, `Step 2 - ...`) and procedural completeness. `[IMPLEMENTED]`
* `UC-CHUNK-03`: **Structured Troubleshooting Entries** (`E090`) — Validates Symptom, Cause, and Fix triplets. `[IMPLEMENTED]`
* `UC-CHUNK-04`: **FAQ Q&A Formatting** (`E091`) — Enforces `### Q: ...?` ending with `?` and accompanied by `**A:** ...`. `[IMPLEMENTED]`
