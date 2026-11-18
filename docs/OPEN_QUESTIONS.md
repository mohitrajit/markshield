# Open Questions, Assumptions, and Metrics Register

This register catalogs all items requiring engineer or management verification (`[VERIFY]`) and unmeasured production metrics (`[ADD METRIC]`) across the Md_Validator documentation record.

---

## 1. Metric Placeholders ([ADD METRIC])

| Item # | Document Location | Missing Metric | Why It Matters | Owner / Action |
|:---:|:---|:---|:---|:---|
| **M1** | Chapter 9, Section 9.3 | Estimated engineering triage time saved per document (`[ADD METRIC]`) | Quantifies developer productivity ROI of catching errors pre-ingestion versus debugging corrupted vector chunks. | Enterprise AI Lead to provide baseline manual review hours. |
| **M2** | Chapter 9, Section 9.3 | Reduction in RAG retrieval hallucination rate (`[ADD METRIC]`) | Proves business impact on end-user response quality after eliminating broken tables and bad chunks. | RAG Platform Lead to measure evaluation benchmark delta. |
| **M3** | Chapter 9, Section 9.3 | Total production Markdown document volume processed to date (`[ADD METRIC]`) | Demonstrates platform adoption scale across Radiant Global Tech knowledge bases. | Knowledge Base Admin to query batch report logs. |

---

## 2. Verification Items ([VERIFY])

| Item # | Document Location | Assumption / Uncertainty | Specific Question for Engineer | Resolution Status |
|:---:|:---|:---|:---|:---|
| **V1** | Chapter 5 & 8, Environment Config | Microsoft 365 Tenant Admin Approval Timeline (`[VERIFY]`) | When will the Radiant Global Tech M365 tenant administrator enable modern SMTP AUTH or OAuth2 client credentials to transition off the personal Gmail relay? | **Resolved** -- Dual-engine email dispatcher implemented in `agent.py` supporting native Microsoft Graph REST API (OAuth 2.0 Client Credentials) alongside legacy SMTP. Admin creates Entra ID App with `Mail.Send` permission; no SMTP subscription required. |
| **V2** | Chapter 8, Section 8.4 | Production Ingestion Trigger (`[VERIFY]`) | Will `agent.py` run as a Windows Task Scheduler service, a continuous background daemon on an ingestion VM, or a pre-commit CI hook? | Pending architectural decision on deployment topology. |
| **V3** | Chapter 11, Section 11.1 | RAGFlow API Ingestion Endpoint (`[VERIFY]`) | What are the exact RAGFlow REST API dataset IDs and authentication tokens for the Phase 2 direct upload hook? | To be provided upon RAGFlow cluster provisioning. |

---

## 3. Notes & Unconfirmed Folder Items

1. **Git Repository Status:**
   - The current workspace `c:\RAG\md_validator` is not initialized as a git repository (`fatal: not a git repository`).
   - *Recommendation:* Initialize git tracking (`git init`) to track revision history, tags, and commit messages.

2. **Backup Storage Location:**
   - Reports and documentation were also mirrored to `C:\projects\Project Reports\Md_Validator\` per user request. Ensure any future documentation builds refresh both locations.
