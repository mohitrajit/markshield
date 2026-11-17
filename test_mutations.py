"""Breaks the master template in many ways; every break must be caught with the right code.
Run:  python test_mutations.py
"""
import sys, tempfile, datetime as dt
from pathlib import Path
sys.path.insert(0, str(Path(__file__).parent))
from verifier import load_rules, verify_file

ROOT = Path(__file__).parent
cfg = load_rules(ROOT / "rules.yaml")
# Enable strict template checks for template mutation suite
cfg["require_all_template_keys"] = True
cfg["required_section_titles"] = ["Overview"]
cfg["enforce_section_order"] = True
cfg["require_section_numbering"] = True
TODAY = dt.date(2026, 11, 4)
# Keep the mutation baseline valid; the template metadata matches its history.
BASE = (ROOT / "RAG-SAMPLE-MASTER-TEMPLATE.md").read_text(encoding="utf-8")

M = [  # (name, old, new, expected code)
 # --- Front matter: required keys and types ---
 ("missing key owner",        'owner: "Integration Team"\n',       "",                              "E011"),
 ("bad doc_id",               'doc_id: "RAG-SAMPLE-MASTER-0001"',  'doc_id: "rag 1"',               "E013"),
 ("title != H1",              'title: "Master Template - Connecting', 'title: "Other Template - Connecting', "E016"),
 ("bad difficulty",           'difficulty: "Beginner"',             'difficulty: "Expert"',          "E013"),
 ("bad date",                 'last_reviewed: "2026-10-27"',        'last_reviewed: "2026-13-45"',   "E013"),
 ("tags not list",            'tags: ["database", "client tool", "connection", "authentication", "flowchart", "SQL", "troubleshooting", "sample"]',
                              'tags: "database"',                                                     "E012"),
 ("duplicate key",            'language: "en"\n',                   'language: "en"\nlanguage: "en"\n', "E015"),
 ("unknown key",              'language: "en"\n',                   'language: "en"\nfoo: "bar"\n',  "E014"),
 # --- references field (new 'records' type) ---
 ("references missing name",
      '  - name: "Connecting to a Database - Source Guide.pdf"\n    url: "https://example.sharepoint.com/:b:/s/Team/SOURCE_FILE_ID"\n    type: "pdf"',
      '  - name: ""\n    url: "https://example.sharepoint.com/:b:/s/Team/SOURCE_FILE_ID"\n    type: "pdf"',
      "E011"),
 ("references bad url",
      '    url: "https://example.sharepoint.com/:b:/s/Team/SOURCE_FILE_ID"\n    type: "pdf"\n  - name: "Add Table From Ref Model.pdf"',
      '    url: "not-a-url"\n    type: "pdf"\n  - name: "Add Table From Ref Model.pdf"',
      "E013"),
 ("references bad type",
      '    type: "pdf"\n  - name: "Add Table From Ref Model.pdf"',
      '    type: "unknown_type"\n  - name: "Add Table From Ref Model.pdf"',
      "E013"),
 # --- Legacy key detection ---
 ("legacy key source_url",
      'source_file: "RAG-SAMPLE-MASTER-0001.md"\n',
      'source_file: "RAG-SAMPLE-MASTER-0001.md"\nsource_url: "https://example.com/video"\n',
      "E014"),
 ("legacy key version",
      'source_file: "RAG-SAMPLE-MASTER-0001.md"\n',
      'source_file: "RAG-SAMPLE-MASTER-0001.md"\nversion: "2.1"\n',
      "E014"),
 # --- Legacy context line detection (E066) ---
 ("legacy context line",
      "## 2. Prerequisites\n\nBefore you start",
      '## 2. Prerequisites\n\n**Doc ID:** RAG-SAMPLE-MASTER-0001 | **Section type:** prerequisites | **Source:** [Guide.pdf](https://example.com/guide)\n\nBefore you start',
      "E066"),
 # --- Fences ---
 ("unclosed fence",          "SELECT 1;\n",   "SELECT 1;\n",  None),  # replaced below
 ("fence language removed",  "```sql\nSELECT TOP 10",  "```\nSELECT TOP 10",    "E031"),
 # --- Tables ---
 ("table separator removed",
      "| Time | Seconds | Topic | Link |\n|---|---:|---|---|\n",
      "| Time | Seconds | Topic | Link |\n",
      "E040"),
 ("extra table cell",
      "| Example batch size | 500 | records |",
      "| Example batch size | 500 | records | x |",
      "E041"),
 ("no blank before table",   "**Text description:** The user enters", "**Text description:** The user enters", None),
 # --- Video / timestamps ---
 ("seconds wrong in step",
      "[03:00 - Select Database Engine](https://www.youtube.com/watch?v=VIDEO_ID&t=180s)",
      "[03:00 - Select Database Engine](https://www.youtube.com/watch?v=VIDEO_ID&t=181s)",
      "E083"),
 ("t= without s",
      "[00:32 - Click Start](https://www.youtube.com/watch?v=VIDEO_ID&t=32s)",
      "[00:32 - Click Start](https://www.youtube.com/watch?v=VIDEO_ID&t=32)",
      "E082"),
 ("video line not a link",
      "**Video:** [00:35 - Select All Programs](https://www.youtube.com/watch?v=VIDEO_ID&t=35s)",
      "**Video:** 00:35 Select All Programs",
      "E082"),
 ("chapter seconds wrong",   "| 03:00 | 180 | Select server type |", "| 03:00 | 181 | Select server type |", "E098"),
 # E084 requires a parsed Video duration header which the new template no longer has;
 # instead verify that an impossible timestamp at least trips E083 (shown/url mismatch)
 ("timestamp mismatch large", "&t=470s)\n\nAfter connecting", "&t=9999s)\n\nAfter connecting", "E083"),
 # --- Diagrams ---
 ("flowchart description removed",  "**Text description of the flowchart:**\n",    "",            "E094"),
 ("mermaid bad type",        "flowchart TD\n    A[Start]",   "flowchar TD\n    A[Start]",    "E093"),
 ("mermaid bad bracket",     "A[Start] --> B[Open client tool]", "A[Start --> B[Open client tool]", "E093"),
 # --- Headings ---
 ("heading level skip",      "### 6.1 Flowchart",   "#### 6.1 Flowchart",     "E021"),
 ("second H1",               "## 2. Prerequisites", "# 2. Prerequisites",      "E023"),
 ("section number reused",   "## 2. Prerequisites", "## 1. Prerequisites",     "E025"),
 # --- Troubleshooting ---
 ("missing symptom",
      '- **Symptom:** "Login failed for user".\n',
      "",
      "E090"),
 # --- FAQ ---
 ("faq answer removed",
      "**A:** No. The client tool is only an interface.",
      "No. The client tool is only an interface.",
      "E091"),
 # --- Secrets / text ---
 ("secret",          "DB_PORT=1433",   "DB_PORT=1433\nDB_PASSWORD=Sup3rSecret!",  "E074"),
 ("raw html",        "## 2. Prerequisites\n",  "## 2. Prerequisites\n\n<div>hi</div>\n",  "E072"),
 ("empty alt",
      "![Architecture diagram: a user sends",
      "![](https://example.com/images/a.png)\n![Architecture diagram: a user sends",
      "E052"),
 ("broken anchor",   "(#6-flowcharts-and-diagrams)",     "(#6-flowcharts)",     "E057"),
 ("escaped markdown", "Use headings to reflect the topic structure.", "Use \\*\\*headings\\*\\* to reflect the topic structure.", "E073"),
 # --- Callouts ---
 ('callout without label',   '> 🟢 **Tip:** Save the server',  '> 🟢 Save the server',   "E095"),
 ('callout emoji/label clash', '> 🟢 **Tip:**',                '> 🟢 **Warning:**',       "E095"),
 # --- Links ---
 ("vague link",      "[connection tutorial](https://www.youtube.com/watch?v=VIDEO_ID)", "[click here](https://www.youtube.com/watch?v=VIDEO_ID)", "E055"),
 ("footnote undefined", "[^legacy]: Legacy", "[^legacyX]: Legacy",  "E056"),
 # --- Procedure ---
 ("step sequence",   "### Step 3 - Select the installed", "### Step 4 - Select the installed",  "E081"),
 ("procedure goal removed",  "**Goal:** Connect to the database server using the client tool and open a query editor.\n\n",  "",  "E080"),
 # --- Sections ---
 ("section out of order",    None,   None,  "E027"),
 # --- Required sections ---
 ("overview missing",        "## 1. Overview\n",  "",  "E020"),
 # --- Questions ---
 # The FAQ section uses H3 Q: headings; check that they must end with ?
 ("faq question no ?",   "### Q: Is the client tool the same as the database server?", "### Q: Is the client tool the same as the database server", "E091"),
]

def run(name, text):
    with tempfile.TemporaryDirectory() as d:
        p = Path(d) / "t.md"
        p.write_text(text, encoding="utf-8")
        (Path(d) / "x").mkdir()
        return verify_file(p, cfg, TODAY)

bad = 0
base = run("base", BASE)
print(f"baseline template: {'PASS' if base['passed'] else 'FAIL'} ({base['errors']} errors)")
if not base["passed"]:
    print([ (i['line'], i['code'], i['message']) for i in base['issues'] if i['severity']=='error']); bad += 1

def mutate(name, old, new):
    if name == "unclosed fence":
        t = BASE.replace("```sql\nSELECT TOP 10\n    customer_id,\n    customer_name,\n    status\nFROM dbo.sample_customers\nWHERE status = 'ACTIVE'\nORDER BY customer_name;\n```", "```sql\nSELECT TOP 10")
        return t
    if name == "no blank before table":
        return BASE.replace("\n| Question | If yes | If no |", "\n\n| Question | If yes | If no |".replace("\n\n", "\n", 1)).replace("### 6.2 Decision tree as a table\n\n", "### 6.2 Decision tree as a table\n\nIntro line\n", 1)
    if name == "section out of order":
        a, b = BASE.index("## 2. Prerequisites"), BASE.index("## 3. Step-by-Step")
        pre = BASE[a:b]
        return BASE.replace(pre, "").replace("## 4. Video Chapters", pre.replace("2. Prerequisites", "4. Prerequisites") + "## 5. Video Chapters", 1)
    if name == "broken anchor":
        return BASE.replace("(#6-flowcharts-and-diagrams)", "(#6-flowcharts)", 1)
    if name == "overview missing":
        # Remove just the Overview H2 line to trigger E020
        lines = BASE.splitlines(keepends=True)
        out = [l for l in lines if l.strip() != "## 1. Overview"]
        return "".join(out)
    assert BASE.count(old) >= 1, f"mutation text not found: {name}"
    return BASE.replace(old, new, 1)

codes = {"unclosed fence": "E030", "no blank before table": "E042", "section out of order": "E027"}
for name, old, new, code in M:
    code = code or codes[name]
    r = run(name, mutate(name, old, new))
    hit = [i for i in r["issues"] if i["code"] == code]
    ok = bool(hit)
    bad += (not ok)
    print(f"{'ok  ' if ok else 'MISS'} {name:38s} -> {code}" + (f"  (line {hit[0]['line']})" if ok else f"  got {sorted({i['code'] for i in r['issues']})}"))
print(f"\n{len(M)} mutations, {bad} problems")
sys.exit(1 if bad else 0)
