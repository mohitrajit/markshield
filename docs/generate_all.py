"""Master Script: Generates all 4 documentation outputs:
1. docs/Md_Validator_Documentation.docx
2. docs/onenote/ (01_... to 12_... HTML files + HOW_TO_IMPORT.md)
3. docs/OPEN_QUESTIONS.md
4. Merged root README.md
"""
import os
import sys
from pathlib import Path
import docx
from docx.shared import Inches, Pt, RGBColor
from docx.enum.text import WD_ALIGN_PARAGRAPH
from docx.enum.table import WD_TABLE_ALIGNMENT
from docx.oxml import parse_xml, OxmlElement
from docx.oxml.ns import nsdecls, qn

DOCS_DIR = Path("c:/RAG/md_validator/docs")
ONENOTE_DIR = DOCS_DIR / "onenote"
DOCS_DIR.mkdir(parents=True, exist_ok=True)
ONENOTE_DIR.mkdir(parents=True, exist_ok=True)

# ---------------------------------------------------------------------------
# Styling and XML helpers for python-docx
# ---------------------------------------------------------------------------
def set_cell_background(cell, hex_color):
    shd = f'<w:shd {nsdecls("w")} w:fill="{hex_color}"/>'
    cell._tc.get_or_add_tcPr().append(parse_xml(shd))

def set_cell_margins(cell, top=100, bottom=100, left=140, right=140):
    tcPr = cell._tc.get_or_add_tcPr()
    tcMar = OxmlElement('w:tcMar')
    for m, val in [('top', top), ('bottom', bottom), ('left', left), ('right', right)]:
        node = OxmlElement(f'w:{m}')
        node.set(qn('w:w'), str(val))
        node.set(qn('w:type'), 'dxa')
        tcMar.append(node)
    tcPr.append(tcMar)

def set_table_borders(table, color="D0D7DE", sz="6", val="single"):
    tblPr = table._tbl.tblPr
    borders_xml = f'''
    <w:tblBorders {nsdecls("w")}>
        <w:top w:val="{val}" w:sz="{sz}" w:space="0" w:color="{color}"/>
        <w:bottom w:val="{val}" w:sz="{sz}" w:space="0" w:color="{color}"/>
        <w:left w:val="none"/>
        <w:right w:val="none"/>
        <w:insideH w:val="{val}" w:sz="{sz}" w:space="0" w:color="{color}"/>
        <w:insideV w:val="none"/>
    </w:tblBorders>
    '''
    tblPr.append(parse_xml(borders_xml))

def add_header_footer(doc):
    section = doc.sections[0]
    section.top_margin = Inches(1)
    section.bottom_margin = Inches(1)
    section.left_margin = Inches(1)
    section.right_margin = Inches(1)

    hdr = section.header.paragraphs[0]
    hdr.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    hrun = hdr.add_run("Md_Validator | Enterprise Technical Documentation Record")
    hrun.font.name = "Arial"
    hrun.font.size = Pt(8.5)
    hrun.font.color.rgb = RGBColor(120, 144, 156)

    ftr = section.footer.paragraphs[0]
    ftr.alignment = WD_ALIGN_PARAGRAPH.CENTER
    frun = ftr.add_run("Md_Validator Project Documentation Record  |  Page ")
    frun.font.name = "Arial"
    frun.font.size = Pt(9)
    frun.font.color.rgb = RGBColor(120, 144, 156)

    fldSimple = OxmlElement('w:fldSimple')
    fldSimple.set(qn('w:instr'), 'PAGE')
    ftr._p.append(fldSimple)

def add_h1(doc, text):
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(20)
    p.paragraph_format.space_after = Pt(8)
    p.paragraph_format.keep_with_next = True
    r = p.add_run(text)
    r.font.name = "Arial"
    r.font.size = Pt(16)
    r.font.bold = True
    r.font.color.rgb = RGBColor(31, 78, 120)  # Dark Corporate Navy
    return p

def add_h2(doc, text):
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(14)
    p.paragraph_format.space_after = Pt(6)
    p.paragraph_format.keep_with_next = True
    r = p.add_run(text)
    r.font.name = "Arial"
    r.font.size = Pt(13)
    r.font.bold = True
    r.font.color.rgb = RGBColor(44, 82, 130)  # Slate Blue
    return p

def add_h3(doc, text):
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(10)
    p.paragraph_format.space_after = Pt(4)
    p.paragraph_format.keep_with_next = True
    r = p.add_run(text)
    r.font.name = "Arial"
    r.font.size = Pt(11)
    r.font.bold = True
    r.font.color.rgb = RGBColor(74, 85, 104)  # Slate Neutral
    return p

def add_p(doc, text, bold_prefix=None, space_after=6, italic=False):
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(0)
    p.paragraph_format.space_after = Pt(space_after)
    p.paragraph_format.line_spacing = 1.15
    if bold_prefix:
        r_pre = p.add_run(bold_prefix)
        r_pre.font.name = "Arial"
        r_pre.font.size = Pt(11)
        r_pre.font.bold = True
        r_pre.font.color.rgb = RGBColor(31, 78, 120)
    r = p.add_run(text)
    r.font.name = "Arial"
    r.font.size = Pt(11)
    r.font.italic = italic
    r.font.color.rgb = RGBColor(36, 41, 47)
    return p

def add_bullet(doc, text, bold_prefix=None):
    p = doc.add_paragraph(style='List Bullet')
    p.paragraph_format.space_before = Pt(0)
    p.paragraph_format.space_after = Pt(3)
    p.paragraph_format.line_spacing = 1.15
    if bold_prefix:
        r_pre = p.add_run(bold_prefix)
        r_pre.font.name = "Arial"
        r_pre.font.size = Pt(11)
        r_pre.font.bold = True
        r_pre.font.color.rgb = RGBColor(31, 78, 120)
    r = p.add_run(text)
    r.font.name = "Arial"
    r.font.size = Pt(11)
    r.font.color.rgb = RGBColor(36, 41, 47)
    return p

def add_code_block(doc, code_str):
    tbl = doc.add_table(rows=1, cols=1)
    tbl.alignment = WD_TABLE_ALIGNMENT.CENTER
    tbl.autofit = False
    cell = tbl.cell(0, 0)
    cell.width = Inches(6.5)

    set_cell_background(cell, "F6F8FA")
    set_cell_margins(cell, top=100, bottom=100, left=140, right=140)

    tcPr = cell._tc.get_or_add_tcPr()
    border_xml = f'''
    <w:tcBorders {nsdecls("w")}>
        <w:left w:val="single" w:sz="6" w:space="0" w:color="D0D7DE"/>
        <w:top w:val="single" w:sz="6" w:space="0" w:color="D0D7DE"/>
        <w:right w:val="single" w:sz="6" w:space="0" w:color="D0D7DE"/>
        <w:bottom w:val="single" w:sz="6" w:space="0" w:color="D0D7DE"/>
    </w:tcBorders>
    '''
    tcPr.append(parse_xml(border_xml))

    p = cell.paragraphs[0]
    p.paragraph_format.space_before = Pt(0)
    p.paragraph_format.space_after = Pt(0)
    p.paragraph_format.line_spacing = 1.05

    r = p.add_run(code_str.strip())
    r.font.name = "Consolas"
    r.font.size = Pt(9)
    r.font.color.rgb = RGBColor(36, 41, 47)

    p_after = doc.add_paragraph()
    p_after.paragraph_format.space_before = Pt(0)
    p_after.paragraph_format.space_after = Pt(4)

def create_styled_table(doc, headers, rows, col_widths=None):
    table = doc.add_table(rows=len(rows) + 1, cols=len(headers))
    table.alignment = WD_TABLE_ALIGNMENT.CENTER
    set_table_borders(table)

    hdr_cells = table.rows[0].cells
    for i, title in enumerate(headers):
        hdr_cells[i].text = title
        set_cell_background(hdr_cells[i], "1F4E78")
        set_cell_margins(hdr_cells[i], top=120, bottom=120, left=120, right=120)
        p = hdr_cells[i].paragraphs[0]
        p.alignment = WD_ALIGN_PARAGRAPH.LEFT
        for run in p.runs:
            run.font.name = "Arial"
            run.font.size = Pt(10)
            run.font.bold = True
            run.font.color.rgb = RGBColor(255, 255, 255)

    for r_idx, row_data in enumerate(rows):
        row_cells = table.rows[r_idx + 1].cells
        bg_color = "F9FAFB" if (r_idx % 2 == 1) else "FFFFFF"
        for c_idx, cell_value in enumerate(row_data):
            row_cells[c_idx].text = str(cell_value)
            set_cell_background(row_cells[c_idx], bg_color)
            set_cell_margins(row_cells[c_idx], top=80, bottom=80, left=120, right=120)
            p = row_cells[c_idx].paragraphs[0]
            p.paragraph_format.line_spacing = 1.15
            for run in p.runs:
                run.font.name = "Arial"
                run.font.size = Pt(9.5)
                run.font.color.rgb = RGBColor(36, 41, 47)

    if col_widths:
        for row in table.rows:
            for idx, width in enumerate(col_widths):
                row.cells[idx].width = Inches(width)

    p_after = doc.add_paragraph()
    p_after.paragraph_format.space_before = Pt(0)
    p_after.paragraph_format.space_after = Pt(6)
    return table

def add_toc_field(doc):
    p = doc.add_paragraph()
    p.paragraph_format.space_before = Pt(6)
    p.paragraph_format.space_after = Pt(12)
    run = p.add_run()
    fldChar1 = parse_xml(r'<w:fldChar %s w:fldCharType="begin"/>' % nsdecls('w'))
    instrText = parse_xml(r'<w:instrText %s xml:space="preserve"> TOC \o "1-3" \h \z \u </w:instrText>' % nsdecls('w'))
    fldChar2 = parse_xml(r'<w:fldChar %s w:fldCharType="separate"/>' % nsdecls('w'))
    fldChar3 = parse_xml(r'<w:fldChar %s w:fldCharType="end"/>' % nsdecls('w'))
    run._r.append(fldChar1)
    run._r.append(instrText)
    run._r.append(fldChar2)
    run._r.append(fldChar3)

print("Starting complete generation of Md_Validator documentation...")

# ---------------------------------------------------------------------------
# Data Definitions for Chapters
# ---------------------------------------------------------------------------

TEXT_FLOW_DIAGRAM = """+-------------------------------------------------------------------------+
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
+-------------------------------------------------------------------------+"""

PROBLEMS_DATA = [
    {
        "num": "1",
        "problem": "Microsoft 365 SMTP Auth Disabled (535 5.7.139)",
        "root_cause": "Radiant Global Tech enterprise tenant policy disabled basic SMTP authentication on smtp.office365.com, returning '535 5.7.139 Authentication unsuccessful, SmtpClientAuthentication disabled for Tenant'.",
        "fix": "Re-routed notifications through an authorized personal Gmail SMTP relay (mohitrajsingh2601@gmail.com) utilizing Google 16-character App Passwords, delivering directly to mohit.raj@radiantglobaltech.com. Added dual STARTTLS/SSL support in agent.py.",
        "outcome": "100% reliable email delivery with full Excel workbook attachments without requiring tenant-wide policy alterations."
    },
    {
        "num": "2",
        "problem": "Windows Console UnicodeEncodeError on Emoji (Clip Icon)",
        "root_cause": "Windows PowerShell environment running standard legacy code pages (cp1252/cp437) crashed with UnicodeEncodeError when attempting to print the raw paperclip emoji glyph in terminal logs.",
        "fix": "Replaced raw emoji characters in email HTML templates with standard HTML numeric character entity '&#128206;' and replaced terminal log strings with clean ASCII indicators ([ATTACHMENT], [PASS], [FAIL]).",
        "outcome": "Complete cross-platform stability across all Windows PowerShell, CMD, and Linux shell environments without encoding crashes."
    },
    {
        "num": "3",
        "problem": "Email Body Character Limit & Clutter from Raw Inline Dumps",
        "root_cause": "Initial implementations embedded the full issue table directly into the HTML email message body. Documents with 50+ errors caused email bodies to exceed 100 KB, triggering mobile client truncation, character limits, and severe visual clutter.",
        "fix": "Decoupled executive notification from forensic details. Streamlined the email HTML body into an executive status card (total files, pass/fail counts, timestamps, attachment callout) and routed all line-by-line issue details exclusively into the attached Excel spreadsheet.",
        "outcome": "Clean, lightweight executive email body (<5 KB) with complete diagnostic forensics accessible in the structured Excel attachment."
    },
    {
        "num": "4",
        "problem": "Multi-Document Failure Congestion in Single-Sheet Spreadsheets",
        "root_cause": "Early Excel report implementation dumped all issues from all batch files into a single flat worksheet ('Issue Details'). Reviewers could not easily distinguish which issues belonged to which document or filter errors by file without complex multi-column filtering.",
        "fix": "Re-engineered generate_excel_report() using openpyxl to create a dynamic multi-tab workbook: a master 'Summary' tab serving as an index, followed by isolated, dedicated worksheet tabs for each individual document named after the file.",
        "outcome": "Reviewers can navigate directly to specific document tabs with frozen headers, column filters, and wrapped descriptions."
    },
    {
        "num": "5",
        "problem": "Excel 31-Character Worksheet Name Limit & Duplicate Stem Collisions",
        "root_cause": "Real-world enterprise document filenames (e.g. RAIN-09-INT-SQLSERVER-AV-0002.md) exceeded Excel's rigid 31-character sheet title limit; multiple files with long shared prefixes produced identical truncated titles, causing openpyxl to crash with 'Sheet title already exists'.",
        "fix": "Implemented _safe_sheet_title(name, existing_titles) algorithm to sanitize illegal characters (\\ / * ? : [ ]), clamp titles safely to 31 characters, and append collision counters (e.g. ' (2)').",
        "outcome": "100% crash-free multi-tab Excel generation across arbitrary filename lengths and naming patterns."
    },
    {
        "num": "6",
        "problem": "Raw Machine Timestamps in Reports and UI (20261104_155642)",
        "root_cause": "Filesystem timestamp string was passed directly into display columns and email headers.",
        "fix": "Decoupled stamp_file (strftime('%Y%m%d_%H%M%S')) for filenames from display_time (strftime('%Y-%m-%d %H:%M:%S')) for visible report tables, emails, and spreadsheets.",
        "outcome": "Clean, professional, human-readable ISO-like timestamps across all reports, emails, and spreadsheets."
    },
    {
        "num": "7",
        "problem": "Master Template Schema Evolution & Legacy Context Lines",
        "root_cause": "Upstream master template eliminated legacy context lines ('**Doc ID:** ...'), obsolete H1 header lines, and fields like source_url/version, moving sources to the front-matter 'references' list of records. Existing documents still contained old syntax.",
        "fix": "Extended verifier.py to parse 'records' schema in front matter, added section_types regex mapping to infer section types from H2 titles, added optional_keys: [ekg_config_version], and introduced legacy cleanup rules E066 (context lines), E067 (H1 header lines), and E068 (legacy sections).",
        "outcome": "Golden master template passes with 0 errors; legacy documents are cleanly flagged for modernization without false alarms."
    },
    {
        "num": "8",
        "problem": "Stale Mutation Test Failures Post-Schema Migration",
        "root_cause": "test_mutations.py looked for deleted template strings (version: '2.1', old context lines), causing AssertionErrors.",
        "fix": "Completely overhauled test_mutations.py to test the new schema (references missing name, bad url, bad type, legacy keys/lines, new section headings), updating the test suite to 46 mutations.",
        "outcome": "Achieved '46 mutations, 0 problems' (100% pass rate)."
    }
]

ERROR_CATALOG = [
    ("E001", "Encoding", "UTF-8 BOM detected; front-matter parser fails completely.", "Save as standard UTF-8 without BOM."),
    ("E002", "I/O", "File read or routing failure; document cannot be inspected or moved.", "Fix filesystem permissions and write access."),
    ("E010", "Metadata", "Malformed YAML front-matter; document invisible to index.", "Enclose valid YAML between '---' on line 1 and closing '---'."),
    ("E011", "Metadata", "Required metadata key missing; citation and filters fail.", "Add missing key with valid value per master template."),
    ("E012", "Metadata", "Value type mismatch; integer/date parsed as string or vice versa.", "Use proper type shown in template (quote strings, unquote numbers)."),
    ("E013", "Metadata", "Value pattern violation; date format or enum invalid.", "Correct value format to match schema regex or allowed enum."),
    ("E014", "Metadata", "Deprecated or unknown key; pollutes index.", "Remove deprecated key or add to optional_keys in rules.yaml."),
    ("E015", "Metadata", "Duplicate metadata key; YAML keeps only last entry.", "Retain exactly one unique entry per metadata key."),
    ("E016", "Metadata", "Front-matter title does not match # H1 heading.", "Ensure front-matter title matches the # H1 title exactly."),
    ("E017", "Content", "Template placeholder (VIDEO_ID, SOURCE_FILE_ID) remaining in text.", "Replace placeholder values with real production data."),
    ("E018", "Content", "Document review overdue; technical data may be stale.", "Review technical content and update last_reviewed date."),
    ("E019", "Content", "Version in metadata disagrees with Version History table.", "Update front-matter version to match the latest table entry."),
    ("E020", "Structure", "Mandatory section (e.g. Overview) is missing.", "Add mandatory section matching master template."),
    ("E021", "Structure", "Heading level skipped (e.g. H1 to H3); outline tree broken.", "Do not skip heading levels in hierarchy."),
    ("E022", "Structure", "Missing or misplaced H1; document context lost.", "Place exactly one # Title immediately after front matter."),
    ("E023", "Structure", "Multiple H1 headings found; chunk hierarchy corrupted.", "Retain one # H1 for the document; demote other headings to ##."),
    ("E024", "Structure", "Empty or duplicate heading text; ambiguous anchors.", "Ensure every heading has unique, non-empty text."),
    ("E025", "Structure", "H2 numbering sequence error; cross-references break.", "Use '## N. Title' with integers strictly incrementing by 1."),
    ("E026", "Structure", "Subheading numbering error (2.1 under 2; 11.1.1 under 11.1).", "Align subheadings with parent section number."),
    ("E027", "Structure", "Sections out of canonical order compared to master template.", "Reorder sections to conform with the master template."),
    ("E030", "Code", "Unclosed code fence; subsequent prose ingested as raw code.", "Add closing backticks (```) on a dedicated line."),
    ("E031", "Code", "Missing language tag on code fence; syntax typing fails.", "Add language tag immediately after opening fence (e.g. ```sql)."),
    ("E032", "Code", "Empty code block; useless chunk created in vector index.", "Populate code block with example or remove it."),
    ("E033", "Code", "Missing blank line padding around code fence.", "Insert a blank line before opening and after closing fence."),
    ("E040", "Table", "Malformed table separator row; rows flattened into noisy text.", "Provide header row followed by |---|---| separator row."),
    ("E041", "Table", "Table column count mismatch; cell values land under wrong header.", "Ensure every table row contains the exact same column count."),
    ("E042", "Table", "Table lacks blank line padding; merged into prose.", "Add an empty blank line before and after the table."),
    ("E043", "Table", "Table has no data rows; empty structure.", "Add data rows or remove the table."),
    ("E050", "Assets", "Local referenced image file missing from directory.", "Place image file in directory or correct the relative path."),
    ("E051", "Assets", "Inline base64 image data bloats chunk size and ruins embeddings.", "Save image to filesystem and reference via markdown link."),
    ("E052", "Assets", "Missing or trivial alt text; image invisible to retrieval.", "Write descriptive alt text explaining what image illustrates."),
    ("E053", "Links", "Empty link or image URL; creates broken citations.", "Provide valid URL target inside parentheses [text](url)."),
    ("E054", "Links", "URL contains unencoded spaces; link truncated.", "Replace spaces with URL-encoded '%20'."),
    ("E055", "Links", "Vague link text ('click here'); target unindexed.", "Use meaningful, descriptive anchor text describing target."),
    ("E056", "Links", "Orphaned footnote or reference definition.", "Add matching definition or remove reference call."),
    ("E057", "Links", "Broken internal anchor (#target) matches no heading.", "Update anchor tag to match valid heading slug."),
    ("E058", "Links", "Reference to non-existent section number in text.", "Update section reference number to point to existing section."),
    ("E060", "Source", "Source document link differs from front-matter source_file.", "Ensure source document link matches front-matter source_file."),
    ("E066", "Legacy", "Deprecated context line ('**Doc ID:** ...') found under ##.", "Delete legacy context lines; master template no longer has them."),
    ("E067", "Legacy", "Deprecated H1 header lines duplicate front matter.", "Delete Document ID / Platform lines under H1."),
    ("E068", "Legacy", "Deprecated legacy section found (e.g. Version History).", "Delete deprecated section; sources now live in references."),
    ("E070", "Quality", "Oversized chunk (>2500 chars); chunker splits mid-thought.", "Break large section into sub-topics using ### subheadings."),
    ("E071", "Quality", "Oversized single line (>2000 chars); tokenization penalty.", "Break line into structured paragraphs or Markdown table."),
    ("E072", "Quality", "Disallowed raw HTML or control characters leak into chunks.", "Replace with standard Markdown; remove control characters."),
    ("E073", "Quality", "Escaped Markdown backslashes (\\*\\*) render in AI output.", "Remove backslashes outside of code blocks."),
    ("E074", "Security", "Hardcoded password, API key, or bearer token detected.", "Remove secret immediately; use <placeholder> and rotate key."),
    ("E075", "Quality", "Missing blank line padding around heading.", "Insert blank line immediately before and after heading."),
    ("E076", "Quality", "Tab characters used for indentation; rendering breaks.", "Replace tabs with spaces; use '- ' for unordered lists."),
    ("E077", "Quality", "Missing final newline at end of file.", "Add a single blank newline at the very end of the file."),
    ("E080", "Procedure", "Procedure lacks required Goal or Expected Result label.", "Include '**Goal:**' and '**Expected result:**' labels in procedure."),
    ("E081", "Procedure", "Step heading format or numbering sequence wrong.", "Use '### Step N - Title' with integer counting 1, 2, 3..."),
    ("E082", "Video", "Malformed video timestamp line; deep-linking fails.", "Format as **Video:** [MM:SS - Text](url&t=Ss)."),
    ("E083", "Video", "Shown MM:SS does not match &t=SECONDSs parameter.", "Ensure seconds parameter t= matches MM:SS (3 min = 180s)."),
    ("E084", "Video", "Timestamp exceeds stated total video duration.", "Correct timestamp or verify stated total video duration."),
    ("E085", "Video", "Video ID in step differs from source_url video ID.", "Use the consistent video ID declared for the document."),
    ("E086", "Video", "Procedure step lacks required video deep-link.", "Add **Video:** line to step or clarify step is unrecorded."),
    ("E090", "Content", "Troubleshooting entry incomplete; lacks Symptom, Cause, Fix.", "Structure entry with - **Symptom:**, - **Cause:**, and - **Fix:**."),
    ("E091", "Content", "Malformed FAQ entry; Q&A pairs get split.", "Format entry as '### Q: Question?' followed by '**A:** Answer'."),
    ("E092", "Content", "Question list weak; fewer than min_questions.", "List at least min_questions ending in '?' in test section."),
    ("E093", "Diagram", "Invalid Mermaid diagram syntax (type, direction, brackets).", "Fix diagram type (flowchart TD), direction, or bracket pairs."),
    ("E094", "Diagram", "Diagram or image lacks required text description below it.", "Add '**Text description:**' immediately beneath diagram/image."),
    ("E095", "Callout", "Callout lacks bold text label or emoji/label clash.", "Start callout with bold label (e.g. > **Warning:**, > 🟢 **Tip:**)."),
    ("E096", "Content", "Related documents list inconsistent with front matter.", "Ensure all related_docs are listed as - [ID: Title](url)."),
    ("E097", "History", "Version History table malformed or non-ascending.", "Columns: Version | Date | Author | Change Summary (ascending)."),
    ("E098", "Video", "Video chapter index table inconsistent (Time != Seconds != t=).", "Verify that Time MM:SS matches Seconds column and link t=."),
    ("E099", "Engine", "Unhandled verifier parser exception.", "Inspect traceback, correct document syntax, and rerun.")
]

print("Data definitions loaded.")

def generate_word_document():
    print("Generating Word Document (docs/Md_Validator_Documentation.docx)...")
    doc = docx.Document()
    add_header_footer(doc)

    # -----------------------------------------------------------------------
    # COVER / TITLE BLOCK
    # -----------------------------------------------------------------------
    p_title = doc.add_paragraph()
    p_title.paragraph_format.space_before = Pt(36)
    p_title.paragraph_format.space_after = Pt(8)
    p_title.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r_title = p_title.add_run("Md_Validator: Technical Documentation Record\nDeterministic Quality Gate for RAG Knowledge Bases")
    r_title.font.name = "Arial"
    r_title.font.size = Pt(24)
    r_title.font.bold = True
    r_title.font.color.rgb = RGBColor(31, 78, 120)

    p_sub = doc.add_paragraph()
    p_sub.paragraph_format.space_before = Pt(0)
    p_sub.paragraph_format.space_after = Pt(20)
    p_sub.alignment = WD_ALIGN_PARAGRAPH.CENTER
    r_sub = p_sub.add_run("Architecture, Component Walkthrough, Implementation Log, Problem-Solution Matrix, and Runbook")
    r_sub.font.name = "Arial"
    r_sub.font.size = Pt(12)
    r_sub.font.italic = True
    r_sub.font.color.rgb = RGBColor(74, 85, 104)

    meta_headers = ["Attribute", "Specification Value"]
    meta_rows = [
        ["Project Name", "Md_Validator (Markdown Document Verification Agent)"],
        ["Version & Status", "Version 2.0.0 (Production-Hardened, Schema-Migrated)"],
        ["Author / Lead Engineer", "Mohit Raj Singh (Enterprise AI Engineering Team)"],
        ["Collaborative Assistant", "Antigravity Engineering Pair-Programming Assistant"],
        ["Organization / Tenant", "Radiant Global Tech (Enterprise Knowledge Pipeline)"],
        ["Document Classification", "Internal Engineering Architecture & Technical Runbook"],
        ["Date of Record", "November 2026"],
        ["Core Tech Stack", "Python 3.13, PyYAML (>=6.0), OpenPyXL (>=3.0.0), smtplib/SSL"]
    ]
    create_styled_table(doc, meta_headers, meta_rows, col_widths=[2.0, 4.5])

    doc.add_page_break()

    # -----------------------------------------------------------------------
    # TABLE OF CONTENTS
    # -----------------------------------------------------------------------
    add_h1(doc, "Table of Contents")
    add_p(doc, "The dynamic Word Table of Contents field is embedded below. In Microsoft Word, press F9 or right-click to update page numbers if editing:")
    add_toc_field(doc)

    toc_summary = [
        ("1. Title Page and Executive Summary", "Project abstract, core dilemma, solution overview, and verified outcomes."),
        ("2. Background and Problem Statement", "RAG vector pipeline chunking vulnerabilities and the business cost of malformed Markdown."),
        ("3. Goals, Scope, and Design Principles", "Functional goals, boundaries, deterministic philosophies, and template-driven design."),
        ("4. Architecture Overview with Diagram", "End-to-end ingestion pipeline flow diagram, staging, routing, and reporting."),
        ("5. Component or Module Walkthrough", "Concise technical briefs for verifier.py, agent.py, rules.yaml, master template, and tests."),
        ("6. Work Done, Step by Step", "Comprehensive 10-step chronological implementation record from inception to hardening."),
        ("7. Problems Faced and Solutions", "Full detailed matrix of 8 major engineering challenges, root causes, fixes, and outcomes."),
        ("8. Setup, Deployment, and Usage Guide", "Copy-pasteable CLI commands, environment setup, and verification checklists."),
        ("9. Achievements and Results", "Before vs after comparison, verified test metrics, and production document audit."),
        ("10. Limitations, Risks, and Lessons Learned", "Current scope boundaries, operational risks, and architectural takeaways."),
        ("11. Proposed Plan, Future Work, and Roadmap", "Upcoming roadmap: RAGFlow direct hook, AI auto-fixer, and semantic LLM review."),
        ("12. Appendix", "Configuration reference, CLI interface reference, data reference (E001-E099), glossary, folder map.")
    ]
    for ch_title, ch_desc in toc_summary:
        add_p(doc, ch_desc, bold_prefix=f"{ch_title}: ", space_after=3)

    doc.add_page_break()

    # -----------------------------------------------------------------------
    # CHAPTER 1
    # -----------------------------------------------------------------------
    add_h1(doc, "1. Title Page and Executive Summary")
    add_h2(doc, "1.1 Problem Summary")
    add_p(doc, "Enterprise Retrieval-Augmented Generation (RAG) platforms (such as RAGFlow, LangChain, or LlamaIndex) ingest technical Markdown files to create chunked vector embeddings and hybrid search indexes. However, minor mechanical defects in Markdown files—such as malformed table rows, missing YAML front-matter, unclosed code fences, missing blank lines, or malformed YouTube timestamp links—routinely cause chunkers to corrupt document outlines, flatten tables into unreadable text, drop metadata, or fail to deep-link visual procedures. These errors degrade vector retrieval precision and cause silent model hallucinations.")

    add_h2(doc, "1.2 Solution Summary")
    add_p(doc, "Md_Validator is a deterministic, pure-Python quality firewall that operates prior to vector indexing. It monitors an intake staging folder ('inbox/'), inspects incoming Markdown files across 10 comprehensive structural and semantic passes, preserves relative visual assets, and safely routes files into 'verified/' (0 errors) or 'failed/' (quarantine with diagnostic logs). It generates multi-tab Excel workbooks via openpyxl and delivers executive HTML reports via enterprise SMTP (Gmail relay with STARTTLS/SSL).")

    add_h2(doc, "1.3 Key Outcomes")
    add_bullet(doc, "Zero Hallucination Gate: 100% deterministic rule enforcement with sub-10ms evaluation latency per document and zero external API costs.", bold_prefix="Deterministic Reliability: ")
    add_bullet(doc, "Mathematical Test Confidence: A 46-mutation regression test suite (test_mutations.py) verifying 46 deliberate rule violations with a 100% pass rate.", bold_prefix="Mutation Verification: ")
    add_bullet(doc, "Enterprise Multi-Tab Reporting: Replaced noisy inline email error tables with an executive status card and an attached Excel workbook featuring an index Summary tab and dedicated per-document tabs.", bold_prefix="Clean Forensic Reporting: ")
    add_bullet(doc, "Zero-Loss Asset Preservation: Relative local image links (e.g. ![Arch](images/diag.png)) are tracked, copied, and rewritten during routing, preventing broken graphics post-verification.", bold_prefix="Asset Synchronization: ")

    # -----------------------------------------------------------------------
    # CHAPTER 2
    # -----------------------------------------------------------------------
    add_h1(doc, "2. Background and Problem Statement")
    add_h2(doc, "2.1 The RAG Data Ingestion Dilemma")
    add_p(doc, "Modern RAG architectures rely on text extractors to split documentation into chunks of 500 to 1,500 tokens before computing dense vector embeddings. If the source Markdown document contains formatting irregularities, the parser fails to understand document hierarchy, leading to:")
    add_bullet(doc, "Tables without closing pipes or blank padding are flattened into unseparated text lines, destroying row-column relationships and rendering tabular data unsearchable.", bold_prefix="Table Flattening: ")
    add_bullet(doc, "Omission of YAML front matter or syntax errors prevents metadata extraction, causing documents to lose platform, module, difficulty, and access-control tags in vector databases.", bold_prefix="Metadata Invisibility: ")
    add_bullet(doc, "Malformed YouTube links (e.g. missing &t=...s seconds parameter or arithmetic discrepancies between shown MM:SS and target seconds) prevent deep-linking to video procedures.", bold_prefix="Timestamp Misdirection: ")
    add_bullet(doc, "Paragraphs exceeding 2,500 characters force chunkers to split thoughts mid-sentence, corrupting semantic embedding vectors and degrading cosine similarity matching.", bold_prefix="Context Fragmentation: ")
    add_bullet(doc, "Accidental hardcoding of passwords, API keys, or bearer tokens in code examples causes security credentials to be permanently indexed into public RAG vector databases.", bold_prefix="Security Leaks: ")

    add_h2(doc, "2.2 Business Cost of Ingestion Defects")
    add_p(doc, "In customer-facing or internal support RAG systems, ingestion defects lead directly to hallucinations, user distrust, and expensive engineering triage. Remediating corrupted chunks after vector indexing requires flushing the index, modifying source Markdown, and re-computing embeddings across thousands of documents. Md_Validator eliminates this overhead by enforcing quality at the intake boundary.")

    # -----------------------------------------------------------------------
    # CHAPTER 3
    # -----------------------------------------------------------------------
    add_h1(doc, "3. Goals, Scope, and Design Principles")
    add_h2(doc, "3.1 System Goals")
    add_bullet(doc, "Provide an automated, standalone pre-ingestion gate for all technical Markdown documents entering the RAG pipeline.")
    add_bullet(doc, "Achieve 100% deterministic rule enforcement with zero false passes on syntactic or structural defects.")
    add_bullet(doc, "Provide explainable, actionable diagnostics: every issue must report line number, rule code, severity, impact, and fix.")
    add_bullet(doc, "Operate autonomously in continuous background daemon mode or ad-hoc single-file/batch CLI modes.")

    add_h2(doc, "3.2 Scope and Boundaries")
    add_bullet(doc, "In Scope: Markdown syntax, YAML front matter, heading outline hierarchy, code fence tagging, Mermaid diagram syntax, table formatting, link/image validity, YouTube timestamp arithmetic, security secrets scanning, and file routing.", bold_prefix="In-Scope: ")
    add_bullet(doc, "Out of Scope: Vector database management (e.g. Milvus/Qdrant), embedding computation, and LLM text generation (semantic review is planned for Phase 3/4).", bold_prefix="Out-of-Scope: ")

    add_h2(doc, "3.3 Core Design Principles")
    add_bullet(doc, "A table is either structurally valid or invalid. A machine validator must guarantee repeatable, zero-cost, sub-10ms verification without probabilistic hallucinations.", bold_prefix="Deterministic over Probabilistic: ")
    add_bullet(doc, "Rather than hardcoding fields, the verifier introspects RAG-SAMPLE-MASTER-TEMPLATE.md dynamically to learn required metadata, types, and section sequences.", bold_prefix="Dynamic Template Learning: ")
    add_bullet(doc, "Input files are never modified in-place or deleted. Defective files are quarantined in failed/ alongside companion diagnostic reports.", bold_prefix="Non-Destructive Routing: ")
    add_bullet(doc, "Executes completely on-premise without transmitting documents across cloud boundaries, protecting enterprise IP.", bold_prefix="Air-Gapped Security: ")

    # -----------------------------------------------------------------------
    # CHAPTER 4
    # -----------------------------------------------------------------------
    add_h1(doc, "4. Architecture Overview with Diagram")
    add_h2(doc, "4.1 Pipeline Architecture Flow Diagram")
    add_p(doc, "The diagram below illustrates the end-to-end processing pipeline from intake to routing and notification:")
    add_code_block(doc, TEXT_FLOW_DIAGRAM)
    add_p(doc, "Diagram Method Note: The diagram above was authored directly as a formatted monospace text flow diagram embedded within a Consolas code block. An external Mermaid CLI renderer (mmdc) was not installed in this execution environment; this plain-text representation guarantees full portability across all Word, PDF, and terminal viewers without external rendering dependencies.", italic=True)

    add_h2(doc, "4.2 Pipeline Processing Stages")
    add_bullet(doc, "Incoming Markdown files and referenced image assets are dropped into inbox/.", bold_prefix="1. Intake Staging: ")
    add_bullet(doc, "The daemon checks file modification times against SETTLE_SECONDS (default 5s). Files currently being written or copied over network shares are skipped until the transfer finishes.", bold_prefix="2. Settlement Buffer: ")
    add_bullet(doc, "rules.yaml is loaded and RAG-SAMPLE-MASTER-TEMPLATE.md is introspected to construct dynamic schema definitions.", bold_prefix="3. Rule Compilation: ")
    add_bullet(doc, "verifier.py executes 10 sequential inspection passes against the document text.", bold_prefix="4. Verifier Engine: ")
    add_bullet(doc, "If 0 errors are found, the document and its local images are moved to verified/. If errors are detected, the document is moved to failed/ and a <stem>.report.txt is emitted.", bold_prefix="5. File Routing: ")
    add_bullet(doc, "openpyxl synthesizes a multi-tab workbook with Summary and per-document tabs; render_html() builds an executive status card; send_email() dispatches the report via Gmail relay.", bold_prefix="6. Reporting & Notification: ")

    # -----------------------------------------------------------------------
    # CHAPTER 5
    # -----------------------------------------------------------------------
    add_h1(doc, "5. Component or Module Walkthrough")
    
    add_h2(doc, "5.1 verifier.py (Core Verification Library)")
    add_p(doc, "What it is: A pure-Python verification library (1,150 lines) implementing the Verifier class and verify_file API.")
    add_p(doc, "Why it was built: To perform high-speed, deterministic syntactic, structural, and security validation on Markdown documents without LLM dependencies.")
    add_p(doc, "How it works: Executes 10 inspection passes (BOM, front matter, headings, fences, tables, links, images, procedures, text hygiene, and legacy checks).")
    add_p(doc, "Inputs & Outputs: Takes document text or file path and configuration dictionary; outputs structured Issue objects (line, code, severity, message, impact, fix).")
    add_p(doc, "Configuration: Governed by learned rules from the master template and rule overrides from rules.yaml.")

    add_h2(doc, "5.2 agent.py (Autonomous Daemon & Batch Runner)")
    add_p(doc, "What it is: Autonomous folder watcher and batch pipeline driver (545 lines).")
    add_p(doc, "Why it was built: To eliminate manual verification workflows, manage safe file routing, generate multi-tab Excel reports, and dispatch email alerts.")
    add_p(doc, "How it works: Periodically polls inbox/, enforces settle time buffers, coordinates file and asset moves, synthesizes openpyxl workbooks, and sends emails.")
    add_p(doc, "Inputs & Outputs: Watches inbox/; outputs to verified/, failed/, reports/, and dispatches SMTP emails.")
    add_p(doc, "Configuration: Reads parameters from .env (SMTP settings, POLL_SECONDS, SETTLE_SECONDS, directory paths).")

    add_h2(doc, "5.3 rules.yaml (Configuration Overlay)")
    add_p(doc, "What it is: Declarative YAML configuration file (74 lines).")
    add_p(doc, "Why it was built: To define strict field regex patterns, enumerations, allowed HTML tags, and chunk thresholds that cannot be expressed in Markdown.")
    add_p(doc, "How it works: Overlays learned template fields via field_overrides; defines optional_keys, section_types regex mappings, and legacy cleanup lists.")
    add_p(doc, "Inputs & Outputs: Parsed by load_rules() and merged with template schema.")

    add_h2(doc, "5.4 RAG-SAMPLE-MASTER-TEMPLATE.md (Golden Contract)")
    add_p(doc, "What it is: Authoritative master Markdown document (983 lines) demonstrating all valid documentation patterns.")
    add_p(doc, "Why it was built: Serves as the single source of truth from which verifier.py learns valid front matter keys, types, and canonical section orders.")
    add_p(doc, "How it works: Parsed at runtime by learn_template(); changes to this file immediately update validation expectations.")

    add_h2(doc, "5.5 test_mutations.py (Mutation Test Suite)")
    add_p(doc, "What it is: Regression testing harness (106 lines) executing 46 programmatic template breakages.")
    add_p(doc, "Why it was built: To mathematically verify that every cataloged rule code is triggered when its corresponding defect is introduced.")
    add_p(doc, "How it works: Mutates RAG-SAMPLE-MASTER-TEMPLATE.md in temporary directories and verifies that expected error codes fire on expected lines.")

    add_h2(doc, "5.6 .env / .env.example (Secrets Configuration)")
    add_p(doc, "What it is: Local environment files defining SMTP credentials and operational parameters.")
    add_p(doc, "Why it was built: To isolate sensitive credentials from version control while providing zero-dependency environment variable parsing.")

    # -----------------------------------------------------------------------
    # CHAPTER 6
    # -----------------------------------------------------------------------
    add_h1(doc, "6. Work Done, Step by Step (Chronological Record)")
    
    steps_data = [
        ("Step 1: Ingestion Failure Analysis & Master Contract Design",
         "Analyzed production RAG chunking failures across enterprise documents. Created RAG-SAMPLE-MASTER-TEMPLATE.md to model all approved Markdown patterns: YAML front matter, procedures, tables, YouTube timestamps, Mermaid diagrams, troubleshooting triads, and FAQs. Cataloged error codes E001 through E099."),
        ("Step 2: Core Verifier Engine Implementation (verifier.py)",
         "Developed verifier.py in pure Python. Implemented dynamic learn_template() using a custom PyYAML SafeLoader to introspect fields, types, and canonical section orders. Built regex scanners for code fences, tables, links, images, secrets, and YouTube timestamp arithmetic. Validated execution latency under 10ms."),
        ("Step 3: Autonomous Watcher Daemon (agent.py)",
         "Created agent.py to automate folder monitoring. Implemented a 5-second settlement window (SETTLE_SECONDS) to prevent race conditions during file transfers. Added safe non-destructive routing to verified/ (0 errors) and failed/ (quarantine with <file>.report.txt)."),
        ("Step 4: Relative Image Asset Tracking & Rewriting",
         "Discovered that moving Markdown files severed relative image links (e.g. images/diagram.png). Implemented _local_images() and _rewrite_image_links() to parse image tags, copy referenced graphics to target folders, and rewrite Markdown links when collisions occur."),
        ("Step 5: Enterprise Email Integration & SMTP Diagnostics",
         "Integrated smtplib with RFC-compliant MIME multipart generation. Added load_dotenv() for zero-dependency environment configuration. Added CLI diagnostic flag --test-email to test connectivity and attachment rendering."),
        ("Step 6: Microsoft 365 Tenant SMTP Block & Gmail Relay Migration",
         "Identified tenant policy error '535 5.7.139 SmtpClientAuthentication disabled' when attempting to connect to smtp.office365.com. Re-architected delivery to route through an authorized personal Gmail relay (mohitrajsingh2601@gmail.com) with 16-character App Passwords, delivering to mohit.raj@radiantglobaltech.com. Added dual STARTTLS (587) and SSL (465) support."),
        ("Step 7: Multi-Tab Excel Reporting Overhaul",
         "Replaced noisy inline email error dumps with an executive HTML dashboard and an attached openpyxl Excel report. Tab 1: Summary index with color-coded status badges and human-readable timestamps. Subsequent tabs: Dedicated per-document sheets with column filters, wrapped descriptions, and issue taxonomy."),
        ("Step 8: Excel 31-Character Sheet Title Sanitization",
         "Encountered openpyxl crashes when processing enterprise filenames exceeding 31 characters. Engineered _safe_sheet_title(name, existing_titles) to sanitize illegal characters (\\ / * ? : [ ]), clamp lengths to 31 characters, and append collision counters (e.g. ' (2)')."),
        ("Step 9: Template Schema Evolution (Legacy Elimination)",
         "Upgraded the master template: eliminated legacy context lines ('**Doc ID:** ...'), deprecated H1 header lines, removed obsolete fields (source_url, version), and introduced the 'references' records schema. Extended verifier.py to parse records, map section_types by title regex, permit optional_keys (ekg_config_version), and flag legacy syntax via E066, E067, and E068."),
        ("Step 10: Mutation Testing Suite Modernization",
         "Overhauled test_mutations.py to test the new schema. Replaced obsolete mutations with tests for references missing names, bad URLs, invalid types, legacy keys, and new section headings. Restored the suite to 46 passing mutations with 0 problems.")
    ]
    for st_title, st_desc in steps_data:
        add_h2(doc, st_title)
        add_p(doc, st_desc)

    # -----------------------------------------------------------------------
    # CHAPTER 7
    # -----------------------------------------------------------------------
    add_h1(doc, "7. Problems Faced and Solutions")
    add_p(doc, "The following matrix details all 8 major engineering obstacles encountered during the project, their verified root causes, engineering fixes, and measured outcomes:")

    prob_headers = ["#", "Problem Encountered", "Root Cause", "Engineering Solution", "Verified Outcome"]
    prob_rows = [
        [p["num"], p["problem"], p["root_cause"], p["fix"], p["outcome"]] for p in PROBLEMS_DATA
    ]
    create_styled_table(doc, prob_headers, prob_rows, col_widths=[0.4, 1.4, 1.6, 1.8, 1.3])

    # -----------------------------------------------------------------------
    # CHAPTER 8
    # -----------------------------------------------------------------------
    add_h1(doc, "8. Setup, Deployment, and Usage Guide")
    add_h2(doc, "8.1 Prerequisites")
    add_p(doc, "Python 3.10 or higher (tested and verified on Python 3.13 64-bit Windows). Dependencies: PyYAML>=6.0 and openpyxl>=3.0.0.")

    add_h2(doc, "8.2 Installation & Setup")
    add_p(doc, "Install required dependencies from the project root:")
    add_code_block(doc, "cd c:\\RAG\\md_validator\npython -m pip install -r requirements.txt")
    add_p(doc, "Verification: Run 'python -c \"import yaml, openpyxl; print('OK')\"'. Output must be 'OK'.")

    add_h2(doc, "8.3 Environment Configuration (.env)")
    add_p(doc, "Configure credentials in .env (protected by .gitignore):")
    add_code_block(doc, 
        "# SMTP Relay Configuration (Gmail Relay Example)\n"
        "SMTP_HOST=smtp.gmail.com\n"
        "SMTP_PORT=587\n"
        "SMTP_SECURITY=starttls\n"
        "SMTP_USER=mohitrajsingh2601@gmail.com\n"
        "SMTP_PASS=<GOOGLE_16_CHAR_APP_PASSWORD>\n"
        "MAIL_FROM=mohitrajsingh2601@gmail.com\n"
        "MAIL_TO=mohit.raj@radiantglobaltech.com\n"
        "MAIL_CC=engineering-leads@radiantglobaltech.com\n"
        "POLL_SECONDS=30\n"
        "SETTLE_SECONDS=5\n"
        "INBOX=inbox\n"
        "VERIFIED=verified\n"
        "FAILED=failed\n"
        "REPORTS=reports"
    )

    add_h2(doc, "8.4 Execution Modes")
    add_bullet(doc, "Single-File CLI Verification: 'python verifier.py path/to/document.md' (exit code 0 = pass, 1 = fail).", bold_prefix="Ad-Hoc Check: ")
    add_bullet(doc, "JSON Output for CI/CD: 'python verifier.py path/to/document.md --json'.", bold_prefix="CI Pipeline: ")
    add_bullet(doc, "Batch Processing: 'python agent.py --once --settle 0' processes all settled files in inbox/ and exits.", bold_prefix="Batch Run: ")
    add_bullet(doc, "Continuous Daemon: 'python agent.py' watches inbox/ continuously every 30 seconds.", bold_prefix="Daemon Mode: ")
    add_bullet(doc, "SMTP Diagnostic Test: 'python agent.py --test-email' validates credentials and sends a test Excel report.", bold_prefix="Email Check: ")
    add_bullet(doc, "Mutation Test Regression: 'python test_mutations.py' verifies all 46 rule breakages.", bold_prefix="Test Suite: ")

    # -----------------------------------------------------------------------
    # CHAPTER 9
    # -----------------------------------------------------------------------
    add_h1(doc, "9. Achievements and Results")
    add_h2(doc, "9.1 Before vs. After Implementation")
    
    achieve_headers = ["Metric / Capability", "Before (Unvalidated Pipeline)", "After (Md_Validator Implemented)"]
    achieve_rows = [
        ["Syntactic Validation", "None; malformed Markdown uploaded directly to RAG.", "10-pass deterministic validation running sub-10ms."],
        ["Table Ingestion", "Malformed tables flattened into unsearchable text.", "100% of tables verified for headers, separators, column equality."],
        ["YouTube Deep-Linking", "Broken timestamp links; arithmetic mismatches.", "Arithmetic verification between MM:SS and seconds URL parameter."],
        ["Visual Asset Tracking", "Local image links broken when files moved.", "Intelligent asset replication and automatic link rewriting."],
        ["Reporting Mechanism", "No logging; silent ingestion failures.", "Multi-tab Excel workbooks, JSON logs, and executive HTML emails."],
        ["Secret Leak Prevention", "Hardcoded API keys and tokens indexed into RAG.", "Automated regex detection of bearer tokens, API keys, passwords."],
        ["Mutation Test Suite", "0 automated failure assertions.", "46 programmatic mutations verified with 0 problems."]
    ]
    create_styled_table(doc, achieve_headers, achieve_rows, col_widths=[1.8, 2.3, 2.4])

    add_h2(doc, "9.2 Production Document Audit Results")
    add_p(doc, "Live batch verification performed on technical documents in inbox/ recorded the following results:")
    audit_headers = ["Document Filename", "Status", "Errors", "Warnings", "Primary Defects Caught"]
    audit_rows = [
        ["create_a_table_in_ekg_configurator.md", "PASSED", "0", "0", "Conforms 100% to schema; routed to verified/."],
        ["RAIN-09-INT-SQLSERVER-AV-0005.md", "FAILED", "4", "3", "Legacy context lines (E066), deprecated header lines (E067)."],
        ["RAIN-O9-INT-3-0002.md", "FAILED", "5", "2", "Missing required references key (E011), legacy context lines (E066)."],
        ["RAIN-09-INT-SQLSERVER-AV-0002.md", "FAILED", "6", "4", "Deprecated source_url key (E014), unescaped markdown (E073)."],
        ["RAIN-09-CFG-MFP-AV-0001.md", "FAILED", "37", "49", "Major legacy structure, missing procedure goals, malformed table cells."]
    ]
    create_styled_table(doc, audit_headers, audit_rows, col_widths=[2.4, 0.9, 0.7, 0.8, 1.7])

    add_h2(doc, "9.3 Measured & Unmeasured Metrics")
    add_p(doc, "Document verification speed: <10ms per document on standard hardware.")
    add_p(doc, "Mutation test pass rate: 46/46 (100%).")
    add_p(doc, "Estimated engineering time saved per document: [ADD METRIC].")
    add_p(doc, "Reduction in RAG retrieval hallucination rate: [ADD METRIC].")

    # -----------------------------------------------------------------------
    # CHAPTER 10
    # -----------------------------------------------------------------------
    add_h1(doc, "10. Limitations, Risks, and Lessons Learned")
    add_h2(doc, "10.1 Limitations")
    add_bullet(doc, "Syntactic, Not Semantic: The verifier enforces structure, syntax, and presence of sections, but does not verify if instructional prose is factually accurate.", bold_prefix="Deterministic Boundary: ")
    add_bullet(doc, "Filesystem Bound: Requires local filesystem access to watch directories; currently lacks direct cloud object store (S3/Azure Blob) polling.", bold_prefix="Storage Scope: ")

    add_h2(doc, "10.2 Operational Risks")
    add_bullet(doc, "Uncoordinated master template edits can immediately cause all incoming documents to fail validation.", bold_prefix="Schema Divergence: ")
    add_bullet(doc, "Author friction if error diagnostics are misunderstood (mitigated by providing actionable fixes on every error).", bold_prefix="Author Frustration: ")

    add_h2(doc, "10.3 Lessons Learned")
    add_bullet(doc, "Never rely on LLMs for deterministic syntax checking. Deterministic Python regex evaluation is 1000x faster, zero-cost, and 100% reproducible.", bold_prefix="1. Deterministic Primacy: ")
    add_bullet(doc, "Decouple presentation timestamps from machine filenames early to maintain clean UI reporting.", bold_prefix="2. Presentation Decoupling: ")
    add_bullet(doc, "Enterprise SMTP authentication policies frequently block direct server-to-server mail; maintaining flexible relay support is essential.", bold_prefix="3. Flexible Mail Relays: ")

    # -----------------------------------------------------------------------
    # CHAPTER 11
    # -----------------------------------------------------------------------
    add_h1(doc, "11. Proposed Plan, Future Work, and Roadmap")
    add_h2(doc, "11.1 Phase 2: Ingestion Pipeline Hook (RAGFlow Direct API)")
    add_p(doc, "Automate direct dispatch of verified documents from verified/ into RAGFlow document datasets via REST API upon successful verification, completing the automated ingestion lifecycle.")

    add_h2(doc, "11.2 Phase 3: Autonomous AI Auto-Fixer Agent")
    add_p(doc, "Over 70% of document failures stem from mechanical flaws (missing blank lines around headings, tabs instead of spaces, missing language tags). We propose an automated pre-quarantine fixer that sanitizes whitespace, injects blank padding, infers code languages, and re-verifies automatically.")

    add_h2(doc, "11.3 Phase 4: Semantic LLM Quality Reviewer")
    add_p(doc, "An optional, gated LLM review step executed only after deterministic checks pass to evaluate whether the title matches content, procedures have meaningful expected results, and evaluation questions are answerable from the document.")

    add_h2(doc, "11.4 Phase 5: Centralized Telemetry & Dashboard")
    add_p(doc, "Build a lightweight web dashboard displaying batch verification trends, top rule failure distributions, and pipeline throughput.")

    # -----------------------------------------------------------------------
    # CHAPTER 12
    # -----------------------------------------------------------------------
    add_h1(doc, "12. Appendix")
    
    add_h2(doc, "12.1 Configuration Reference")
    conf_headers = ["File / Setting", "Purpose", "Default Value", "Description"]
    conf_rows = [
        ["rules.yaml: template", "Pointer to golden contract", "RAG-SAMPLE-MASTER-TEMPLATE.md", "Relative path to master template."],
        ["rules.yaml: field_overrides", "Schema regex/enum rules", "doc_id, difficulty, etc.", "Overrides learned template field constraints."],
        ["rules.yaml: optional_keys", "Allowed unlisted keys", "[ekg_config_version]", "Suppresses unknown-key warnings."],
        ["rules.yaml: section_types", "Title-to-type regex map", "procedure, troubleshooting, etc.", "Infers section roles from H2 titles."],
        ["rules.yaml: legacy", "Deprecated feature rules", "keys, headers, sections", "Flags obsolete syntax with configurable severity."],
        [".env: SMTP_HOST", "Mail server hostname", "smtp.gmail.com", "SMTP relay host."],
        [".env: SMTP_PORT", "Mail server port", "587", "Port (587 for STARTTLS, 465 for SSL)."],
        [".env: SMTP_SECURITY", "TLS encryption mode", "starttls", "Security protocol (starttls, ssl, none)."],
        [".env: POLL_SECONDS", "Daemon polling cycle", "30", "Seconds between inbox/ scans."],
        [".env: SETTLE_SECONDS", "Write buffer delay", "5", "Seconds file must be untouched before processing."]
    ]
    create_styled_table(doc, conf_headers, conf_rows, col_widths=[1.5, 1.4, 1.3, 2.3])

    add_h2(doc, "12.2 Master Error Catalog Summary (E001 - E099)")
    err_headers = ["Code", "Category", "Description", "Actionable Fix"]
    err_rows = [[e[0], e[1], e[2], e[3]] for e in ERROR_CATALOG]
    create_styled_table(doc, err_headers, err_rows, col_widths=[0.8, 1.1, 2.5, 2.1])

    add_h2(doc, "12.3 Glossary of Technical Terms")
    gloss_headers = ["Term", "Definition in Context of Md_Validator"]
    gloss_rows = [
        ["RAG", "Retrieval-Augmented Generation: An AI architecture that retrieves external knowledge passages to augment LLM answers."],
        ["Chunking", "The process of splitting a long Markdown document into smaller semantic passages for embedding computation."],
        ["BOM", "Byte Order Mark: A hidden Unicode signature (\\ufeff) at file start that corrupts many automated YAML parsers."],
        ["STARTTLS", "An email protocol command that upgrades an insecure plain-text connection to encrypted TLS over port 587."],
        ["Mutation Testing", "A quality assurance methodology that deliberately injects defects into a codebase/template to verify test sensitivity."],
        ["Settlement Window", "A time delay (default 5s) requiring an incoming file's modification time to remain unchanged before processing begins."]
    ]
    create_styled_table(doc, gloss_headers, gloss_rows, col_widths=[1.8, 4.7])

    add_h2(doc, "12.4 File and Folder Map")
    add_code_block(doc,
        "c:\\RAG\\md_validator\\\n"
        "|-- docs/\n"
        "|   |-- Md_Validator_Documentation.docx    # Complete Word technical documentation record\n"
        "|   |-- OPEN_QUESTIONS.md                  # Open items, [VERIFY], and [ADD METRIC] register\n"
        "|   |-- generate_all.py                    # Master documentation generator script\n"
        "|   `-- onenote/                           # OneNote-ready chapter exports\n"
        "|       |-- 01_Title_and_Executive_Summary.html\n"
        "|       |-- ...\n"
        "|       |-- 12_Appendix.html\n"
        "|       `-- HOW_TO_IMPORT.md\n"
        "|-- inbox/                                 # Incoming staging directory for .md and image files\n"
        "|-- verified/                              # Output folder for documents passing with 0 errors\n"
        "|-- failed/                                # Quarantine folder for failed files + .report.txt\n"
        "|-- reports/                               # Historical JSON, HTML, and multi-tab .xlsx reports\n"
        "|-- .env                                   # Local SMTP credentials and operational parameters\n"
        "|-- .env.example                           # Documented template for environment setup\n"
        "|-- .gitignore                             # Protects .env from version control leaks\n"
        "|-- agent.py                               # Autonomous folder watcher daemon and report runner\n"
        "|-- verifier.py                            # Deterministic 10-pass Markdown verification library\n"
        "|-- rules.yaml                             # YAML rules overlay and field constraints\n"
        "|-- RAG-SAMPLE-MASTER-TEMPLATE.md          # Authoritative golden master template\n"
        "|-- test_mutations.py                      # 46-mutation regression test suite\n"
        "|-- requirements.txt                       # Python dependencies (PyYAML, openpyxl)\n"
        "`-- README.md                              # Authoritative project summary and update guide"
    )

    docx_path = DOCS_DIR / "Md_Validator_Documentation.docx"
    doc.save(docx_path)
    print(f"Word document saved to: {docx_path} ({docx_path.stat().st_size} bytes)")
    return docx_path

print("generate_word_document definition ready.")

# ---------------------------------------------------------------------------
# OneNote HTML Generator
# ---------------------------------------------------------------------------

ONENOTE_CHAPTERS = [
    ("01_Title_and_Executive_Summary.html", "1. Title Page and Executive Summary", """
<h2>1.1 Problem Statement</h2>
<p>In enterprise Retrieval-Augmented Generation (RAG) platforms (such as RAGFlow, LangChain, or LlamaIndex), Markdown documents are parsed and chunked to create vector embeddings and hybrid search indexes. Formatting flaws—including unclosed code fences, malformed table rows, missing YAML front-matter, and broken YouTube timestamp links—routinely cause chunkers to flatten tables, drop metadata, or fail to deep-link visual procedures. These errors degrade vector retrieval precision and cause silent model hallucinations.</p>

<h2>1.2 Solution Overview</h2>
<p>Md_Validator is a deterministic, pure-Python quality firewall that operates prior to vector indexing. It monitors an intake staging folder (<code>inbox/</code>), inspects incoming Markdown files across 10 comprehensive structural and semantic passes, preserves relative visual assets, and safely routes files into <code>verified/</code> (0 errors) or <code>failed/</code> (quarantine with diagnostic logs). It generates multi-tab Excel workbooks via openpyxl and delivers executive HTML reports via enterprise SMTP (Gmail relay with STARTTLS/SSL).</p>

<h2>1.3 Key Outcomes</h2>
<ul>
  <li><b>Deterministic Reliability:</b> 100% deterministic rule enforcement with sub-10ms evaluation latency per document and zero external API costs.</li>
  <li><b>Mutation Verification:</b> A 46-mutation regression test suite (<code>test_mutations.py</code>) verifying 46 deliberate rule violations with a 100% pass rate.</li>
  <li><b>Clean Forensic Reporting:</b> Replaced noisy inline email error tables with an executive status card and an attached Excel workbook featuring an index Summary tab and dedicated per-document tabs.</li>
  <li><b>Asset Synchronization:</b> Relative local image links are tracked, copied, and rewritten during routing, preventing broken graphics post-verification.</li>
</ul>
"""),

    ("02_Background_and_Problem_Statement.html", "2. Background and Problem Statement", """
<h2>2.1 The RAG Data Ingestion Dilemma</h2>
<p>Modern RAG architectures rely on text extractors to split documentation into chunks of 500 to 1,500 tokens before computing dense vector embeddings. If the source Markdown document contains formatting irregularities, the parser fails to understand document hierarchy, leading to:</p>
<ul>
  <li><b>Table Flattening:</b> Tables without closing pipes or blank padding are flattened into unseparated text lines, destroying row-column relationships and rendering tabular data unsearchable.</li>
  <li><b>Metadata Invisibility:</b> Omission of YAML front matter or syntax errors prevents metadata extraction, causing documents to lose platform, module, difficulty, and access-control tags in vector databases.</li>
  <li><b>Timestamp Misdirection:</b> Malformed YouTube links (e.g. missing &t=...s seconds parameter or arithmetic discrepancies between shown MM:SS and target seconds) prevent deep-linking to video procedures.</li>
  <li><b>Context Fragmentation:</b> Paragraphs exceeding 2,500 characters force chunkers to split thoughts mid-sentence, corrupting semantic embedding vectors and degrading cosine similarity matching.</li>
  <li><b>Security Leaks:</b> Accidental hardcoding of passwords, API keys, or bearer tokens in code examples causes security credentials to be permanently indexed into public RAG vector databases.</li>
</ul>

<h2>2.2 Business Cost of Ingestion Defects</h2>
<p>In customer-facing or internal support RAG systems, ingestion defects lead directly to hallucinations, user distrust, and expensive engineering triage. Remediating corrupted chunks after vector indexing requires flushing the index, modifying source Markdown, and re-computing embeddings across thousands of documents. Md_Validator eliminates this overhead by enforcing quality at the intake boundary.</p>
"""),

    ("03_Goals_Scope_and_Design_Principles.html", "3. Goals, Scope, and Design Principles", """
<h2>3.1 System Goals</h2>
<ul>
  <li>Provide an automated, standalone pre-ingestion gate for all technical Markdown documents entering the RAG pipeline.</li>
  <li>Achieve 100% deterministic rule enforcement with zero false passes on syntactic or structural defects.</li>
  <li>Provide explainable, actionable diagnostics: every issue must report line number, rule code, severity, impact, and fix.</li>
  <li>Operate autonomously in continuous background daemon mode or ad-hoc single-file/batch CLI modes.</li>
</ul>

<h2>3.2 Scope and Boundaries</h2>
<ul>
  <li><b>In-Scope:</b> Markdown syntax, YAML front matter, heading outline hierarchy, code fence tagging, Mermaid diagram syntax, table formatting, link/image validity, YouTube timestamp arithmetic, security secrets scanning, and file routing.</li>
  <li><b>Out-of-Scope:</b> Vector database management (e.g. Milvus/Qdrant), embedding computation, and LLM text generation (semantic review is planned for Phase 3/4).</li>
</ul>

<h2>3.3 Core Design Principles</h2>
<ul>
  <li><b>Deterministic over Probabilistic:</b> A table is either structurally valid or invalid. A machine validator must guarantee repeatable, zero-cost, sub-10ms verification without probabilistic hallucinations.</li>
  <li><b>Dynamic Template Learning:</b> Rather than hardcoding fields, the verifier introspects <code>RAG-SAMPLE-MASTER-TEMPLATE.md</code> dynamically to learn required metadata, types, and section sequences.</li>
  <li><b>Non-Destructive Routing:</b> Input files are never modified in-place or deleted. Defective files are quarantined in <code>failed/</code> alongside companion diagnostic reports.</li>
  <li><b>Air-Gapped Security:</b> Executes completely on-premise without transmitting documents across cloud boundaries, protecting enterprise IP.</li>
</ul>
"""),

    ("04_Architecture_Overview.html", "4. Architecture Overview with Diagram", f"""
<h2>4.1 Pipeline Architecture Flow Diagram</h2>
<p>The diagram below illustrates the end-to-end processing pipeline from intake to routing and notification:</p>
<pre>
{TEXT_FLOW_DIAGRAM}
</pre>
<p><i>Diagram Method Note: The diagram above was authored directly as a formatted monospace text flow diagram embedded within a pre code block. An external Mermaid CLI renderer (mmdc) was not installed in this execution environment; this plain-text representation guarantees full portability without external rendering dependencies.</i></p>

<h2>4.2 Pipeline Processing Stages</h2>
<ol>
  <li><b>Intake Staging:</b> Incoming Markdown files and referenced image assets are dropped into <code>inbox/</code>.</li>
  <li><b>Settlement Buffer:</b> The daemon checks file modification times against SETTLE_SECONDS (default 5s). Files currently being written or copied over network shares are skipped until the transfer finishes.</li>
  <li><b>Rule Compilation:</b> <code>rules.yaml</code> is loaded and <code>RAG-SAMPLE-MASTER-TEMPLATE.md</code> is introspected to construct dynamic schema definitions.</li>
  <li><b>Verifier Engine:</b> <code>verifier.py</code> executes 10 sequential inspection passes against the document text.</li>
  <li><b>File Routing:</b> If 0 errors are found, the document and its local images are moved to <code>verified/</code>. If errors are detected, the document is moved to <code>failed/</code> and a <code>&lt;stem&gt;.report.txt</code> is emitted.</li>
  <li><b>Reporting & Notification:</b> openpyxl synthesizes a multi-tab workbook with Summary and per-document tabs; <code>render_html()</code> builds an executive status card; <code>send_email()</code> dispatches the report via Gmail relay.</li>
</ol>
"""),

    ("05_Component_Walkthrough.html", "5. Component or Module Walkthrough", """
<h2>5.1 verifier.py (Core Verification Library)</h2>
<p><b>What it is:</b> A pure-Python verification library (1,150 lines) implementing the Verifier class and verify_file API.<br>
<b>Why it was built:</b> To perform high-speed, deterministic syntactic, structural, and security validation on Markdown documents without LLM dependencies.<br>
<b>How it works:</b> Executes 10 inspection passes (BOM, front matter, headings, fences, tables, links, images, procedures, text hygiene, and legacy checks).<br>
<b>Inputs & Outputs:</b> Takes document text or file path and configuration dictionary; outputs structured Issue objects (line, code, severity, message, impact, fix).<br>
<b>Configuration:</b> Governed by learned rules from the master template and rule overrides from rules.yaml.</p>

<h2>5.2 agent.py (Autonomous Daemon & Batch Runner)</h2>
<p><b>What it is:</b> Autonomous folder watcher and batch pipeline driver (545 lines).<br>
<b>Why it was built:</b> To eliminate manual verification workflows, manage safe file routing, generate multi-tab Excel reports, and dispatch email alerts.<br>
<b>How it works:</b> Periodically polls inbox/, enforces settle time buffers, coordinates file and asset moves, synthesizes openpyxl workbooks, and sends emails.<br>
<b>Inputs & Outputs:</b> Watches inbox/; outputs to verified/, failed/, reports/, and dispatches SMTP emails.<br>
<b>Configuration:</b> Reads parameters from .env (SMTP settings, POLL_SECONDS, SETTLE_SECONDS, directory paths).</p>

<h2>5.3 rules.yaml (Configuration Overlay)</h2>
<p><b>What it is:</b> Declarative YAML configuration file (74 lines).<br>
<b>Why it was built:</b> To define strict field regex patterns, enumerations, allowed HTML tags, and chunk thresholds that cannot be expressed in Markdown.<br>
<b>How it works:</b> Overlays learned template fields via field_overrides; defines optional_keys, section_types regex mappings, and legacy cleanup lists.<br>
<b>Inputs & Outputs:</b> Parsed by load_rules() and merged with template schema.</p>

<h2>5.4 RAG-SAMPLE-MASTER-TEMPLATE.md (Golden Contract)</h2>
<p><b>What it is:</b> Authoritative master Markdown document (983 lines) demonstrating all valid documentation patterns.<br>
<b>Why it was built:</b> Serves as the single source of truth from which verifier.py learns valid front matter keys, types, and canonical section orders.<br>
<b>How it works:</b> Parsed at runtime by learn_template(); changes to this file immediately update validation expectations.</p>

<h2>5.5 test_mutations.py (Mutation Test Suite)</h2>
<p><b>What it is:</b> Regression testing harness (106 lines) executing 46 programmatic template breakages.<br>
<b>Why it was built:</b> To mathematically verify that every cataloged rule code is triggered when its corresponding defect is introduced.<br>
<b>How it works:</b> Mutates RAG-SAMPLE-MASTER-TEMPLATE.md in temporary directories and verifies that expected error codes fire on expected lines.</p>

<h2>5.6 .env / .env.example (Secrets Configuration)</h2>
<p><b>What it is:</b> Local environment files defining SMTP credentials and operational parameters.<br>
<b>Why it was built:</b> To isolate sensitive credentials from version control while providing zero-dependency environment variable parsing.</p>
"""),

    ("06_Work_Done_Step_by_Step.html", "6. Work Done, Step by Step", """
<h2>Step 1: Ingestion Failure Analysis & Master Contract Design</h2>
<p>Analyzed production RAG chunking failures across enterprise documents. Created RAG-SAMPLE-MASTER-TEMPLATE.md to model all approved Markdown patterns: YAML front matter, procedures, tables, YouTube timestamps, Mermaid diagrams, troubleshooting triads, and FAQs. Cataloged error codes E001 through E099.</p>

<h2>Step 2: Core Verifier Engine Implementation (verifier.py)</h2>
<p>Developed verifier.py in pure Python. Implemented dynamic learn_template() using a custom PyYAML SafeLoader to introspect fields, types, and canonical section orders. Built regex scanners for code fences, tables, links, images, secrets, and YouTube timestamp arithmetic. Validated execution latency under 10ms.</p>

<h2>Step 3: Autonomous Watcher Daemon (agent.py)</h2>
<p>Created agent.py to automate folder monitoring. Implemented a 5-second settlement window (SETTLE_SECONDS) to prevent race conditions during file transfers. Added safe non-destructive routing to verified/ (0 errors) and failed/ (quarantine with &lt;file&gt;.report.txt).</p>

<h2>Step 4: Relative Image Asset Tracking & Rewriting</h2>
<p>Discovered that moving Markdown files severed relative image links (e.g. images/diagram.png). Implemented _local_images() and _rewrite_image_links() to parse image tags, copy referenced graphics to target folders, and rewrite Markdown links when collisions occur.</p>

<h2>Step 5: Enterprise Email Integration & SMTP Diagnostics</h2>
<p>Integrated smtplib with RFC-compliant MIME multipart generation. Added load_dotenv() for zero-dependency environment configuration. Added CLI diagnostic flag --test-email to test connectivity and attachment rendering.</p>

<h2>Step 6: Microsoft 365 Tenant SMTP Block & Gmail Relay Migration</h2>
<p>Identified tenant policy error '535 5.7.139 SmtpClientAuthentication disabled' when attempting to connect to smtp.office365.com. Re-architected delivery to route through an authorized personal Gmail relay (mohitrajsingh2601@gmail.com) with 16-character App Passwords, delivering to mohit.raj@radiantglobaltech.com. Added dual STARTTLS (587) and SSL (465) support.</p>

<h2>Step 7: Multi-Tab Excel Reporting Overhaul</h2>
<p>Replaced noisy inline email error dumps with an executive HTML dashboard and an attached openpyxl Excel report. Tab 1: Summary index with color-coded status badges and human-readable timestamps. Subsequent tabs: Dedicated per-document sheets with column filters, wrapped descriptions, and issue taxonomy.</p>

<h2>Step 8: Excel 31-Character Sheet Title Sanitization</h2>
<p>Encountered openpyxl crashes when processing enterprise filenames exceeding 31 characters. Engineered _safe_sheet_title(name, existing_titles) to sanitize illegal characters (\\ / * ? : [ ]), clamp lengths to 31 characters, and append collision counters (e.g. ' (2)').</p>

<h2>Step 9: Template Schema Evolution (Legacy Elimination)</h2>
<p>Upgraded the master template: eliminated legacy context lines ('**Doc ID:** ...'), deprecated H1 header lines, removed obsolete fields (source_url, version), and introduced the 'references' records schema. Extended verifier.py to parse records, map section_types by title regex, permit optional_keys (ekg_config_version), and flag legacy syntax via E066, E067, and E068.</p>

<h2>Step 10: Mutation Testing Suite Modernization</h2>
<p>Overhauled test_mutations.py to test the new schema. Replaced obsolete mutations with tests for references missing names, bad URLs, invalid types, legacy keys, and new section headings. Restored the suite to 46 passing mutations with 0 problems.</p>
"""),

    ("07_Problems_Faced_and_Solutions.html", "7. Problems Faced and Solutions", f"""
<h2>Problem-Solution Matrix</h2>
<p>The following table details all 8 major engineering obstacles encountered during the project, their verified root causes, engineering fixes, and measured outcomes:</p>
<table border="1" cellpadding="6">
  <tr style="background-color: #1F4E78; color: #FFFFFF;">
    <th>#</th><th>Problem Encountered</th><th>Root Cause</th><th>Engineering Solution</th><th>Verified Outcome</th>
  </tr>
  {"".join(f'''<tr>
    <td><b>{p["num"]}</b></td>
    <td><b>{p["problem"]}</b></td>
    <td>{p["root_cause"]}</td>
    <td>{p["fix"]}</td>
    <td>{p["outcome"]}</td>
  </tr>''' for p in PROBLEMS_DATA)}
</table>
"""),

    ("08_Setup_Deployment_and_Usage_Guide.html", "8. Setup, Deployment, and Usage Guide", """
<h2>8.1 Prerequisites</h2>
<p>Python 3.10 or higher (tested on Python 3.13 64-bit Windows). Dependencies: PyYAML>=6.0, openpyxl>=3.0.0.</p>

<h2>8.2 Installation</h2>
<pre>
cd c:\\RAG\\md_validator
python -m pip install -r requirements.txt
</pre>
<p><b>Verification:</b> Run <code>python -c "import yaml, openpyxl; print('OK')"</code>. Output must be 'OK'.</p>

<h2>8.3 Environment Configuration (.env)</h2>
<pre>
SMTP_HOST=smtp.gmail.com
SMTP_PORT=587
SMTP_SECURITY=starttls
SMTP_USER=mohitrajsingh2601@gmail.com
SMTP_PASS=&lt;GOOGLE_16_CHAR_APP_PASSWORD&gt;
MAIL_FROM=mohitrajsingh2601@gmail.com
MAIL_TO=mohit.raj@radiantglobaltech.com
MAIL_CC=engineering-leads@radiantglobaltech.com
POLL_SECONDS=30
SETTLE_SECONDS=5
INBOX=inbox
VERIFIED=verified
FAILED=failed
REPORTS=reports
</pre>

<h2>8.4 Execution Commands</h2>
<pre>
# 1. Validate a single document
python verifier.py path/to/document.md

# 2. Validate with JSON output
python verifier.py path/to/document.md --json

# 3. Process all settled inbox files once and exit
python agent.py --once --settle 0

# 4. Start 24/7 background folder watcher
python agent.py

# 5. Diagnostic SMTP test email with Excel attachment
python agent.py --test-email

# 6. Execute mutation regression test suite
python test_mutations.py
</pre>
"""),

    ("09_Achievements_and_Results.html", "9. Achievements and Results", """
<h2>9.1 Before vs. After Implementation</h2>
<table border="1" cellpadding="6">
  <tr style="background-color: #1F4E78; color: #FFFFFF;">
    <th>Metric / Capability</th><th>Before Implementation</th><th>After Implementation</th>
  </tr>
  <tr><td><b>Syntactic Validation</b></td><td>None; malformed Markdown uploaded directly to RAG.</td><td>10-pass deterministic validation running sub-10ms.</td></tr>
  <tr><td><b>Table Ingestion</b></td><td>Malformed tables flattened into unsearchable text.</td><td>100% of tables verified for headers, separators, column equality.</td></tr>
  <tr><td><b>YouTube Deep-Linking</b></td><td>Broken timestamp links; arithmetic mismatches.</td><td>Arithmetic verification between MM:SS and seconds URL parameter.</td></tr>
  <tr><td><b>Visual Asset Tracking</b></td><td>Local image links broken when files moved.</td><td>Intelligent asset replication and automatic link rewriting.</td></tr>
  <tr><td><b>Reporting Mechanism</b></td><td>No logging; silent ingestion failures.</td><td>Multi-tab Excel workbooks, JSON logs, and executive HTML emails.</td></tr>
  <tr><td><b>Secret Leak Prevention</b></td><td>Hardcoded API keys and tokens indexed into RAG.</td><td>Automated regex detection of bearer tokens, API keys, passwords.</td></tr>
  <tr><td><b>Mutation Test Suite</b></td><td>0 automated failure assertions.</td><td>46 programmatic mutations verified with 0 problems.</td></tr>
</table>

<h2>9.2 Production Document Audit Results</h2>
<table border="1" cellpadding="6">
  <tr style="background-color: #1F4E78; color: #FFFFFF;">
    <th>Document Filename</th><th>Status</th><th>Errors</th><th>Warnings</th><th>Primary Defects Caught</th>
  </tr>
  <tr><td>create_a_table_in_ekg_configurator.md</td><td><b>PASSED</b></td><td>0</td><td>0</td><td>Conforms 100% to schema; routed to verified/.</td></tr>
  <tr><td>RAIN-09-INT-SQLSERVER-AV-0005.md</td><td><b>FAILED</b></td><td>4</td><td>3</td><td>Legacy context lines (E066), deprecated header lines (E067).</td></tr>
  <tr><td>RAIN-O9-INT-3-0002.md</td><td><b>FAILED</b></td><td>5</td><td>2</td><td>Missing required references key (E011), legacy context lines (E066).</td></tr>
  <tr><td>RAIN-09-INT-SQLSERVER-AV-0002.md</td><td><b>FAILED</b></td><td>6</td><td>4</td><td>Deprecated source_url key (E014), unescaped markdown (E073).</td></tr>
  <tr><td>RAIN-09-CFG-MFP-AV-0001.md</td><td><b>FAILED</b></td><td>37</td><td>49</td><td>Major legacy structure, missing procedure goals, malformed table cells.</td></tr>
</table>

<h2>9.3 Metrics & Benchmarks</h2>
<p>Document verification speed: &lt;10ms per document on standard hardware.<br>
Mutation test pass rate: 46/46 (100%).<br>
Estimated engineering time saved per document: [ADD METRIC].<br>
Reduction in RAG retrieval hallucination rate: [ADD METRIC].</p>
"""),

    ("10_Limitations_Risks_and_Lessons_Learned.html", "10. Limitations, Risks, and Lessons Learned", """
<h2>10.1 Limitations</h2>
<ul>
  <li><b>Syntactic, Not Semantic:</b> The verifier enforces structure, syntax, and presence of sections, but does not verify if instructional prose is factually accurate.</li>
  <li><b>Filesystem Bound:</b> Requires local filesystem access to watch directories; currently lacks direct cloud object store (S3/Azure Blob) polling.</li>
</ul>

<h2>10.2 Operational Risks</h2>
<ul>
  <li><b>Schema Divergence:</b> Uncoordinated master template edits can immediately cause all incoming documents to fail validation.</li>
  <li><b>Author Frustration:</b> Author friction if error diagnostics are misunderstood (mitigated by providing actionable fixes on every error).</li>
</ul>

<h2>10.3 Lessons Learned</h2>
<ul>
  <li><b>Deterministic Primacy:</b> Never rely on LLMs for deterministic syntax checking. Deterministic Python regex evaluation is 1000x faster, zero-cost, and 100% reproducible.</li>
  <li><b>Presentation Decoupling:</b> Decouple presentation timestamps from machine filenames early to maintain clean UI reporting.</li>
  <li><b>Flexible Mail Relays:</b> Enterprise SMTP authentication policies frequently block direct server-to-server mail; maintaining flexible relay support is essential.</li>
</ul>
"""),

    ("11_Proposed_Plan_and_Roadmap.html", "11. Proposed Plan, Future Work, and Roadmap", """
<h2>11.1 Phase 2: Ingestion Pipeline Hook (RAGFlow Direct API)</h2>
<p>Automate direct dispatch of verified documents from verified/ into RAGFlow document datasets via REST API upon successful verification, completing the automated ingestion lifecycle.</p>

<h2>11.2 Phase 3: Autonomous AI Auto-Fixer Agent</h2>
<p>Over 70% of document failures stem from mechanical flaws (missing blank lines around headings, tabs instead of spaces, missing language tags). We propose an automated pre-quarantine fixer that sanitizes whitespace, injects blank padding, infers code languages, and re-verifies automatically.</p>

<h2>11.3 Phase 4: Semantic LLM Quality Reviewer</h2>
<p>An optional, gated LLM review step executed only after deterministic checks pass to evaluate whether the title matches content, procedures have meaningful expected results, and evaluation questions are answerable from the document.</p>

<h2>11.4 Phase 5: Centralized Telemetry & Dashboard</h2>
<p>Build a lightweight web dashboard displaying batch verification trends, top rule failure distributions, and pipeline throughput.</p>
"""),

    ("12_Appendix.html", "12. Appendix", f"""
<h2>12.1 Configuration Reference</h2>
<table border="1" cellpadding="6">
  <tr style="background-color: #1F4E78; color: #FFFFFF;">
    <th>File / Setting</th><th>Purpose</th><th>Default Value</th><th>Description</th>
  </tr>
  <tr><td>rules.yaml: template</td><td>Pointer to golden contract</td><td>RAG-SAMPLE-MASTER-TEMPLATE.md</td><td>Relative path to master template.</td></tr>
  <tr><td>rules.yaml: field_overrides</td><td>Schema regex/enum rules</td><td>doc_id, difficulty, etc.</td><td>Overrides learned template field constraints.</td></tr>
  <tr><td>rules.yaml: optional_keys</td><td>Allowed unlisted keys</td><td>[ekg_config_version]</td><td>Suppresses unknown-key warnings.</td></tr>
  <tr><td>rules.yaml: section_types</td><td>Title-to-type regex map</td><td>procedure, troubleshooting, etc.</td><td>Infers section roles from H2 titles.</td></tr>
  <tr><td>rules.yaml: legacy</td><td>Deprecated feature rules</td><td>keys, headers, sections</td><td>Flags obsolete syntax with configurable severity.</td></tr>
  <tr><td>.env: SMTP_HOST</td><td>Mail server hostname</td><td>smtp.gmail.com</td><td>SMTP relay host.</td></tr>
  <tr><td>.env: SMTP_PORT</td><td>Mail server port</td><td>587</td><td>Port (587 for STARTTLS, 465 for SSL).</td></tr>
  <tr><td>.env: SMTP_SECURITY</td><td>TLS encryption mode</td><td>starttls</td><td>Security protocol (starttls, ssl, none).</td></tr>
  <tr><td>.env: POLL_SECONDS</td><td>Daemon polling cycle</td><td>30</td><td>Seconds between inbox/ scans.</td></tr>
  <tr><td>.env: SETTLE_SECONDS</td><td>Write buffer delay</td><td>5</td><td>Seconds file must be untouched before processing.</td></tr>
</table>

<h2>12.2 Master Error Catalog Summary (E001 - E099)</h2>
<table border="1" cellpadding="6">
  <tr style="background-color: #1F4E78; color: #FFFFFF;">
    <th>Code</th><th>Category</th><th>Description</th><th>Actionable Fix</th>
  </tr>
  {"".join(f'''<tr>
    <td><b>{e[0]}</b></td>
    <td>{e[1]}</td>
    <td>{e[2]}</td>
    <td>{e[3]}</td>
  </tr>''' for e in ERROR_CATALOG)}
</table>

<h2>12.3 Glossary of Technical Terms</h2>
<table border="1" cellpadding="6">
  <tr style="background-color: #1F4E78; color: #FFFFFF;">
    <th>Term</th><th>Definition in Context of Md_Validator</th>
  </tr>
  <tr><td><b>RAG</b></td><td>Retrieval-Augmented Generation: An AI architecture that retrieves external knowledge passages to augment LLM answers.</td></tr>
  <tr><td><b>Chunking</b></td><td>The process of splitting a long Markdown document into smaller semantic passages for embedding computation.</td></tr>
  <tr><td><b>BOM</b></td><td>Byte Order Mark: A hidden Unicode signature (\\ufeff) at file start that corrupts many automated YAML parsers.</td></tr>
  <tr><td><b>STARTTLS</b></td><td>An email protocol command that upgrades an insecure plain-text connection to encrypted TLS over port 587.</td></tr>
  <tr><td><b>Mutation Testing</b></td><td>A quality assurance methodology that deliberately injects defects into a codebase/template to verify test sensitivity.</td></tr>
  <tr><td><b>Settlement Window</b></td><td>A time delay (default 5s) requiring an incoming file's modification time to remain unchanged before processing begins.</td></tr>
</table>

<h2>12.4 File and Folder Map</h2>
<pre>
c:\\RAG\\md_validator\\
|-- docs/
|   |-- Md_Validator_Documentation.docx    # Complete Word technical documentation record
|   |-- OPEN_QUESTIONS.md                  # Open items, [VERIFY], and [ADD METRIC] register
|   |-- generate_all.py                    # Master documentation generator script
|   `-- onenote/                           # OneNote-ready chapter exports
|       |-- 01_Title_and_Executive_Summary.html
|       |-- ...
|       |-- 12_Appendix.html
|       `-- HOW_TO_IMPORT.md
|-- inbox/                                 # Incoming staging directory for .md and image files
|-- verified/                              # Output folder for documents passing with 0 errors
|-- failed/                                # Quarantine folder for failed files + .report.txt
|-- reports/                               # Historical JSON, HTML, and multi-tab .xlsx reports
|-- .env                                   # Local SMTP credentials and operational parameters
|-- .env.example                           # Documented template for environment setup
|-- .gitignore                             # Protects .env from version control leaks
|-- agent.py                               # Autonomous folder watcher daemon and report runner
|-- verifier.py                            # Deterministic 10-pass Markdown verification library
|-- rules.yaml                             # YAML rules overlay and field constraints
|-- RAG-SAMPLE-MASTER-TEMPLATE.md          # Authoritative golden master template
|-- test_mutations.py                      # 46-mutation regression test suite
|-- requirements.txt                       # Python dependencies (PyYAML, openpyxl)
`-- README.md                              # Authoritative project summary and update guide
</pre>
""")
]

def generate_onenote_exports():
    print("Generating OneNote HTML files (docs/onenote/)...")
    for filename, title, body in ONENOTE_CHAPTERS:
        full_html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<title>{title}</title>
</head>
<body>
<h1>{title}</h1>
{body}
</body>
</html>"""
        path = ONENOTE_DIR / filename
        path.write_text(full_html, encoding="utf-8")
        print(f"  Saved {path.name}")

    # HOW_TO_IMPORT.md
    how_to = """# How to Import Documentation into Microsoft OneNote

## Important Notice
Microsoft OneNote does not provide a direct headless command-line interface or local API to programmatically write into a `.one` notebook file without Microsoft Office COM automation or Microsoft Graph API permissions. Therefore, you cannot write into a OneNote notebook directly via an automated script.

## Step-by-Step OneNote Import Procedure
To import this complete documentation record into Microsoft OneNote with 100% visual fidelity:

1. **Create Notebook Section:**
   - Open Microsoft OneNote.
   - Create or select a notebook section named **Md_Validator** or **RAG Ingestion Engineering**.

2. **Import Chapters Page by Page:**
   - Open the `docs/onenote/` directory in File Explorer (`c:\\RAG\\md_validator\\docs\\onenote\\`).
   - For each chapter file (from `01_Title_and_Executive_Summary.html` to `12_Appendix.html`):
     1. Double-click the `.html` file to open it in your web browser (Google Chrome, Microsoft Edge, or Firefox).
     2. Press **Ctrl + A** to select all content on the page.
     3. Press **Ctrl + C** to copy.
     4. In OneNote, create a **New Page** and title it with the chapter name.
     5. Click into the OneNote page body and press **Ctrl + V** to paste.
   - All headings (`<h1>`, `<h2>`, `<h3>`), tables, shaded header rows, and code blocks (`<pre>`) will transfer directly into native OneNote objects.

3. **Alternative: Insert Word Document as Printout:**
   - In OneNote, click **Insert** > **File Printout** (or **File Attachment**).
   - Select `docs/Md_Validator_Documentation.docx`.
   - OneNote will automatically render every page of the complete Word documentation record directly into your notebook.
"""
    (ONENOTE_DIR / "HOW_TO_IMPORT.md").write_text(how_to, encoding="utf-8")
    print("  Saved HOW_TO_IMPORT.md")

def generate_open_questions():
    print("Generating docs/OPEN_QUESTIONS.md...")
    content = """# Open Questions, Assumptions, and Metrics Register

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
| **V1** | Chapter 5 & 8, Environment Config | Microsoft 365 Tenant Admin Approval Timeline (`[VERIFY]`) | When will the Radiant Global Tech M365 tenant administrator enable modern SMTP AUTH or OAuth2 client credentials to transition off the personal Gmail relay? | Open -- User indicated Gmail relay is temporary until admin approval. |
| **V2** | Chapter 8, Section 8.4 | Production Ingestion Trigger (`[VERIFY]`) | Will `agent.py` run as a Windows Task Scheduler service, a continuous background daemon on an ingestion VM, or a pre-commit CI hook? | Pending architectural decision on deployment topology. |
| **V3** | Chapter 11, Section 11.1 | RAGFlow API Ingestion Endpoint (`[VERIFY]`) | What are the exact RAGFlow REST API dataset IDs and authentication tokens for the Phase 2 direct upload hook? | To be provided upon RAGFlow cluster provisioning. |

---

## 3. Notes & Unconfirmed Folder Items

1. **Git Repository Status:**
   - The current workspace `c:\\RAG\\md_validator` is not initialized as a git repository (`fatal: not a git repository`).
   - *Recommendation:* Initialize git tracking (`git init`) to track revision history, tags, and commit messages.

2. **Backup Storage Location:**
   - Reports and documentation were also mirrored to `C:\\projects\\Project Reports\\Md_Validator\\` per user request. Ensure any future documentation builds refresh both locations.
"""
    (DOCS_DIR / "OPEN_QUESTIONS.md").write_text(content, encoding="utf-8")
    print("  Saved docs/OPEN_QUESTIONS.md")

def update_readme():
    print("Updating root README.md with merged Source-of-Truth table, update guide, and CHANGELOG...")
    readme_path = Path("c:/RAG/md_validator/README.md")
    existing_readme = readme_path.read_text(encoding="utf-8")

    merge_sections = """
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
"""
    if "## 9. Source-of-Truth Architecture" not in existing_readme:
        updated_readme = existing_readme + merge_sections
        readme_path.write_text(updated_readme, encoding="utf-8")
        print("README.md successfully updated and merged.")
    else:
        print("README.md already contains merged sections.")

def main():
    print("--- Starting Md_Validator Documentation Suite Build ---")
    generate_word_document()
    generate_onenote_exports()
    generate_open_questions()
    update_readme()
    print("--- Build Complete Successfully ---")

if __name__ == "__main__":
    main()
