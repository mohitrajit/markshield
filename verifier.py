"""Strict verifier: checks a Markdown file against RAG-SAMPLE-MASTER-TEMPLATE.md.

Deterministic (no LLM). Learns keys/sections from the template, adds the extra
rules from rules.yaml. Every issue carries line, code, reason, impact, fix.
"""
import datetime as dt
import json
import re
import sys
from dataclasses import asdict, dataclass
from pathlib import Path
from urllib.parse import unquote, urlsplit

import yaml

# code -> (what goes wrong if uploaded, how to fix)
CATALOG = {
    "E001": ("Parser can misread or drop the whole front matter.", "Save as UTF-8 without BOM."),
    "E002": ("The document could not be read, so it was not validated.", "Check that the file exists and is readable, then run the verifier again."),
    "E010": ("Front matter is ignored; no metadata reaches the index.", "Open with '---' on line 1, valid YAML, close with '---'."),
    "E011": ("Missing metadata: filtering, citation and source links break.", "Add the key with a value, as in the master template."),
    "E012": ("Wrong value type; metadata is mis-indexed or rejected.", "Use the type shown in the master template (quote text values)."),
    "E013": ("Invalid value; dedup, filters or date logic misbehave.", "Fix the value to match the allowed format."),
    "E014": ("Key not in the master template; ignored or pollutes the index.", "Remove it or add it to the master template first."),
    "E015": ("Duplicate key; YAML silently keeps only the last one.", "Keep one entry per key."),
    "E016": ("Metadata and visible content disagree; answers cite conflicting info.", "Make the title/ID identical everywhere."),
    "E017": ("Template placeholder shipped; answers show fake links/names.", "Replace with the real value (never invent one)."),
    "E018": ("Document is past its review date; answers may be stale.", "Review the content and update last_reviewed."),
    "E019": ("Version in metadata differs from the Version History table.", "Make front-matter version equal the last table row."),
    "E020": ("A mandatory section is missing; retrieval has nothing to match.", "Add the section exactly as in the master template."),
    "E021": ("Heading hierarchy broken; chunk parents/titles come out wrong.", "Do not skip heading levels."),
    "E022": ("Missing or wrong H1; chunks lose the document context.", "Put one '# Title' (equal to front-matter title) right after the front matter."),
    "E023": ("Multiple H1s confuse chunk hierarchy.", "Keep one H1; demote the rest."),
    "E024": ("Empty or duplicate heading; ambiguous chunk titles and anchors.", "Give every heading unique, non-empty text."),
    "E025": ("Section numbering is off; cross-references like 'See Section 12' point to the wrong place.", "Use '## N. Title' with N increasing by 1."),
    "E026": ("Sub-heading numbers do not follow the parent heading.", "Number as 2.1, 2.2 under section 2; 11.1.1 under 11.1."),
    "E027": ("Section order differs from the template; people and prompts expect a fixed order.", "Reorder sections as in the master template."),
    "E028": ("Unknown or wrong Section type; chunk is mis-labelled for retrieval.", "Use the Section type the template uses for that section."),
    "E029": ("A required sub-heading is missing; questions on it cannot be answered.", "Add the sub-heading as in the template."),
    "E030": ("Everything after the fence is read as code; chunks are corrupted.", "Add the closing fence."),
    "E031": ("Code has no language label; rendering and chunk typing unreliable.", "Add one, e.g. ```sql."),
    "E032": ("Empty block makes a useless chunk.", "Fill it or remove it."),
    "E033": ("No blank line around fence; some parsers merge it into the paragraph.", "Add a blank line before and after the fence."),
    "E040": ("Table does not parse; rows are flattened into noisy text.", "Header row, then |---|---| separator, rows starting and ending with '|'."),
    "E041": ("Column count differs; values land under the wrong header.", "Make every row have the header's column count."),
    "E042": ("Table glued to nearby text; it renders as plain text or swallows the next line.", "Add a blank line before and after the table."),
    "E043": ("Table has no data rows.", "Add rows or remove the table."),
    "E050": ("Image link is broken; the picture never shows.", "Fix the path or place the file next to the .md."),
    "E051": ("Inline base64 image bloats the chunk and ruins embeddings.", "Save as a file and link it."),
    "E052": ("No/weak alt text; the image is invisible to retrieval.", "Write alt text explaining what the image shows."),
    "E053": ("Link has an empty or malformed URL.", "Fix the (url) part."),
    "E054": ("URL has spaces; the link breaks.", "Use %20 for spaces."),
    "E055": ("Vague link text gives retrieval nothing to match.", "Use descriptive link text."),
    "E056": ("Reference link / footnote has no definition (or the reverse).", "Add the matching definition or remove the reference."),
    "E057": ("Internal anchor points nowhere.", "Fix the #anchor to match a heading."),
    "E058": ("Text refers to a section number that does not exist.", "Fix the section number."),
    "E060": ("Original-document link missing; answers cannot link back to the PDF.", "Add the Source document / Official references link equal to source_file."),
    "E061": ("Source link differs between places; answers cite inconsistent sources.", "Use the same original link (source_file or source_url) everywhere."),
    "E062": ("Section has no context line; its chunk has no Doc ID or source.", "Add the context line right under the heading."),
    "E063": ("Context line malformed; parsers cannot read ID/type/source.", "Use: **Doc ID:** X | **Section type:** T | **Source:** [name](url)"),
    "E064": ("Context Doc ID differs from the document ID; chunk attributed to the wrong doc.", "Use the front-matter doc_id."),
    "E065": ("Header block missing/different from front matter.", "Add the labelled lines under the H1, matching the front matter."),
    "E066": ("Old context lines repeat the Doc ID and source in every chunk; the master template no longer has them.", "Delete every '**Doc ID:** ... | **Section type:** ... | **Source:** ...' line."),
    "E067": ("Old header lines under the H1 duplicate the front matter; the master template no longer has them.", "Delete the Document ID / Platform / Difficulty / Estimated time / Video duration / Last reviewed lines."),
    "E068": ("Old section duplicates metadata; the master template no longer has it.", "Delete the section (sources now live in 'references' in the front matter)."),
    "E070": ("Text under one heading is too big; the chunker splits it mid-thought.", "Split it with sub-headings."),
    "E071": ("Very long line; chunk quality drops.", "Break it into paragraphs or a table."),
    "E072": ("Raw HTML/control characters leak into chunk text.", "Replace with plain Markdown."),
    "E073": ("Escaped Markdown characters show up literally in chunks.", "Remove the backslashes (outside code)."),
    "E074": ("A secret would be indexed and shown in answers.", "Remove it; use a <placeholder>."),
    "E075": ("No blank line around heading; some parsers mis-split chunks.", "Add a blank line before and after headings."),
    "E076": ("List style differs from the template; nesting can break.", "Use '- ' bullets and '- [ ]' / '- [x]' task items; no tabs."),
    "E077": ("File does not end with a newline.", "Add a final newline."),
    "E080": ("Procedure lacks a required part (goal / steps / expected result).", "Add the missing part."),
    "E081": ("Step heading format/sequence wrong; steps cannot be located.", "Use '### Step N - Title' counting 1, 2, 3..."),
    "E082": ("Video line malformed; timestamp link will not open at the right moment.", "Use: **Video:** [MM:SS - text](https://www.youtube.com/watch?v=ID&t=SECONDSs)"),
    "E083": ("Shown time and the URL seconds differ; link opens at the wrong moment.", "Seconds = minutes x 60 + seconds (01:05:30 = 3930)."),
    "E084": ("Timestamp is beyond the stated video duration.", "Correct the timestamp or the duration."),
    "E085": ("YouTube link points to a different video than source_url.", "Use the document's video ID."),
    "E086": ("Step has no own video link; answers cannot deep-link it.", "Add a **Video:** line to the step."),
    "E090": ("Troubleshooting entry incomplete; answer lacks symptom/cause/fix.", "Give Symptom, Cause and Fix for each entry."),
    "E091": ("FAQ entry malformed; question/answer pairs get split.", "Use '### Q: ...?' followed by '**A:** ...'."),
    "E092": ("Question list weak; fewer retrievable questions.", "List at least the minimum number of real questions ending in '?'."),
    "E093": ("Mermaid diagram invalid; it will not render.", "Fix the diagram type/direction/brackets."),
    "E094": ("Diagram/image has no text description; retriever cannot read it.", "Add '**Text description:**' (or '**Image note:**') right below."),
    "E095": ("Callout lacks a text label or its emoji/label disagree.", "Start with '**Label:**' (Tip, Warning, Important, Info...)."),
    "E096": ("Related Resources section incomplete or inconsistent with related_docs.", "List each related doc as '- [ID: Title](url)' and the Official references."),
    "E097": ("Version History table malformed.", "Columns: Version | Date | Author | Change Summary, ascending."),
    "E098": ("Video chapter index inconsistent.", "Time, Seconds and link t= must agree."),
    "E099": ("The verifier stopped while processing the document; its format is unconfirmed.", "Inspect the reported exception, correct the document or rule that triggered it, and run the verifier again."),
}

FENCE = re.compile(r"^(\s{0,3})(`{3,}|~{3,})(.*)$")
HEAD = re.compile(r"^(#{1,6})(?:\s+(.*?))?\s*$")
IMG = re.compile(r"!\[([^\]]*)\]\(([^)]*)\)")
LINK = re.compile(r"(?<!!)\[([^\]]*)\]\(([^)]*)\)")
SEP = re.compile(r"^\s*\|?\s*:?-{3,}:?\s*(\|\s*:?-{3,}:?\s*)*\|?\s*$")
CTX = re.compile(r"^\*\*Doc ID:\*\* (?P<id>[^\s|]+) \| \*\*Section type:\*\* (?P<type>[a-z][a-z-]*) \| "
                 r"\*\*Source:\*\* \[(?P<name>[^\]]+)\]\((?P<url>[^)\s]+)\)\s*$")
VIDEO = re.compile(r"^\*\*Video:\*\* \[((?:\d{2}:)?\d{2}:\d{2}) - (.+?)\]\((https://www\.youtube\.com/watch\?v=([\w-]+)"
                   r"(?:&list=[\w-]+)?(?:&index=\d+)?&t=(\d+)s)\)\s*$")
LABEL = re.compile(r"^\s*(?:[-*]\s+|\d+\.\s+)?\*\*([^*]+?):\*\*\s*(.*)$")
HTML = re.compile(r"<(/?)([A-Za-z][\w-]*)(?![\w+.-]*:)[^<>@]*>")
CTRL = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")
ESC = re.compile(r"\\[*_#\[\]()<>~`!+.{}-]")
URLRE = re.compile(r"https?://[^\s)>\]]+")
SECRETS = [
    re.compile(r"(?i)(?<![A-Za-z0-9])(password|passwd|pwd|secret|api[_-]?key|access[_-]?key|token)(?![A-Za-z0-9])[\"']?\s*[:=]\s*[\"']?(?!<)[^\s\"'<>]{4,}"),
    re.compile(r"AKIA[0-9A-Z]{16}"),
    re.compile(r"Bearer\s+(?!<)[A-Za-z0-9._~+/=-]{20,}"),
    re.compile(r"\bsk-[A-Za-z0-9]{20,}"),
    re.compile(r"\bghp_[A-Za-z0-9]{20,}"),
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
]
MERMAID_TYPES = ("flowchart", "graph", "sequenceDiagram", "erDiagram", "stateDiagram-v2", "stateDiagram",
                 "gantt", "classDiagram", "pie", "journey", "mindmap", "timeline", "gitGraph")


@dataclass
class Issue:
    line: int
    code: str
    severity: str
    message: str
    impact: str
    fix: str


def _isodate(s):
    try:
        return dt.date.fromisoformat(s)
    except Exception:
        return None


def _secs(t):
    try:
        p = [int(x) for x in t.split(":")]
    except (AttributeError, ValueError):
        return None
    if len(p) == 2:
        minutes, seconds = p
        if seconds >= 60:
            return None
        return minutes * 60 + seconds
    if len(p) == 3:
        hours, minutes, seconds = p
        if minutes >= 60 or seconds >= 60:
            return None
        return hours * 3600 + minutes * 60 + seconds
    return None


def _slug(t):
    t = re.sub(r"[^\w\s-]", "", t.lower().strip())
    return re.sub(r"\s", "-", t)


def _cells(row):
    r = row.strip()
    if r.startswith("|"):
        r = r[1:]
    if r.endswith("|") and not r.endswith("\\|"):
        r = r[:-1]
    return [c.strip() for c in re.split(r"(?<!\\)\|", r)]


def _image_target(raw):
    """Extract an image destination, including destinations wrapped in <>."""
    raw = raw.strip()
    if raw.startswith("<") and ">" in raw:
        return raw[1:raw.index(">")].strip()
    return raw.split(None, 1)[0] if raw else ""


def _strip_inline(s):
    return re.sub(r"(`+)(.+?)\1", lambda m: " " * len(m.group()), s)


def _strip_num(t):
    return re.sub(r"^\d+(\.\d+)*\.?\s+", "", t).strip()


class _UniqueLoader(yaml.SafeLoader):
    dups = []


def _construct(loader, node, deep=False):
    seen = set()
    for k, _ in node.value:
        key = loader.construct_object(k, deep=deep)
        if key in seen:
            _UniqueLoader.dups.append(key)
        seen.add(key)
    return yaml.SafeLoader.construct_mapping(loader, node, deep)


_UniqueLoader.add_constructor(yaml.resolver.BaseResolver.DEFAULT_MAPPING_TAG, _construct)


def read_front(lines):
    """-> (meta|None, end_idx|None, error|None, {key: line_no}, [dup keys])
    Front matter is optional in general RAG documents. If absent, returns (None, None, None, {}, []).
    If opened with '---' on line 1, it must be properly closed and valid YAML.
    """
    if not lines or lines[0].strip() != "---":
        return None, None, None, {}, []
    end = next((i for i in range(1, len(lines)) if lines[i].strip() == "---"), None)
    if end is None:
        return None, None, "Front matter opened with '---' but never closed.", {}, []
    keyline = {}
    for i in range(1, end):
        m = re.match(r"^([A-Za-z_][\w-]*)\s*:", lines[i])
        if m and m.group(1) not in keyline:
            keyline[m.group(1)] = i + 1
    _UniqueLoader.dups = []
    try:
        meta = yaml.load("\n".join(lines[1:end]), Loader=_UniqueLoader) or {}
        if not isinstance(meta, dict):
            raise ValueError("not key: value pairs")
    except Exception as e:
        return None, end, f"Front matter is not valid YAML: {str(e).splitlines()[0]}", keyline, []
    return meta, end, None, keyline, list(_UniqueLoader.dups)


def scan_fences(lines, start=0):
    code = [False] * len(lines)
    fences, cur = [], None
    for i in range(start, len(lines)):
        m = FENCE.match(lines[i])
        if cur:
            code[i] = True
            if m and m.group(2)[0] == cur["char"] and len(m.group(2)) >= cur["len"] and not m.group(3).strip():
                cur["end"] = i
                fences.append(cur)
                cur = None
            elif m and m.group(2)[0] == cur["char"] and m.group(3).strip() and cur.get("suspect") is None:
                cur["suspect"] = i
        elif m:
            code[i] = True
            info = m.group(3).strip()
            cur = {"start": i, "end": None, "char": m.group(2)[0], "len": len(m.group(2)),
                   "lang": info.split()[0] if info else "", "indent": len(m.group(1))}
    if cur:
        fences.append(cur)
    return code, fences


# ---------------------------------------------------------------- learn from template
def learn_template(path):
    lines = Path(path).read_text(encoding="utf-8").splitlines()
    meta, end, err, _, _ = read_front(lines)
    if err or meta is None:
        raise ValueError(f"Template front matter problem: {err or 'Template must have YAML front matter'}")
    fields = {}
    for k, v in meta.items():
        if isinstance(v, list) and v and all(isinstance(x, dict) for x in v):
            t = "records"
        elif isinstance(v, list):
            t = "list"
        elif isinstance(v, int) and not isinstance(v, bool):
            t = "int"
        elif isinstance(v, dt.date) or (isinstance(v, str) and _isodate(v)):
            t = "date"
        else:
            t = "str"
        fields[k] = {"type": t, "required": True}
        if t == "records":
            fields[k]["item_keys"] = list(v[0].keys())
    code, _ = scan_fences(lines, end + 1)
    canon, exempt, types = [], set(), set()
    for i, ln in enumerate(lines):
        if code[i]:
            continue
        m = re.match(r"^##\s+\d+\.\s+(.+?)\s*$", ln)
        if not m:
            continue
        title = m.group(1).strip().lower()
        j = i + 1
        while j < len(lines) and not lines[j].strip():
            j += 1
        c = CTX.match(lines[j]) if j < len(lines) else None
        if c:
            canon.append((title, c.group("type")))
            types.add(c.group("type"))
        else:
            exempt.add(title)
            canon.append((title, None))
    return {"fields": fields, "canon": canon, "exempt": exempt, "types": types}


def load_rules(path):
    path = Path(path).expanduser()
    cfg = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    template = Path(cfg["template"]).expanduser()
    if not template.is_absolute():
        template = path.parent / template
    learned = learn_template(template)
    fields = learned["fields"]
    for k, o in (cfg.get("field_overrides") or {}).items():
        if k not in fields:
            raise ValueError(f"field_overrides has '{k}' which is not in the master template")
        fields[k].update(o)
    cfg["fields"], cfg["learned"] = fields, learned
    return cfg


# ---------------------------------------------------------------- the checker
class Verifier:
    def __init__(self, cfg, md_dir, today=None):
        self.cfg, self.md_dir = cfg, Path(md_dir)
        self.today = today or dt.date.today()
        self.issues, self._seen = [], set()

    def add(self, idx, code, sev, msg):
        key = (idx, code, msg)
        if key in self._seen:
            return
        self._seen.add(key)
        impact, fix = CATALOG[code]
        self.issues.append(Issue(idx + 1, code, sev, msg, impact, fix))

    def err(self, idx, code, msg):
        self.add(idx, code, "error", msg)

    def warn(self, idx, code, msg):
        self.add(idx, code, "warning", msg)

    def m(self, key):
        v = self.meta.get(key, "")
        return v.isoformat() if isinstance(v, dt.date) else v

    # ---- driver
    def run(self, text):
        self.issues.clear()
        self._seen.clear()
        self._steps = []
        self.duration = None
        if text.startswith("\ufeff"):
            self.err(0, "E001", "File starts with a BOM; front matter will not be detected.")
            text = text.lstrip("\ufeff")
        if not text.endswith("\n"):
            self.warn(max(len(text.splitlines()) - 1, 0), "E077", "File does not end with a newline.")
        self.lines = text.splitlines()
        self.front_matter()
        start = (self.fm_end + 1) if self.fm_end is not None else 0
        self.start = start
        self.code, self.fences = scan_fences(self.lines, start)
        self.clean = ["" if self.code[i] else _strip_inline(l) for i, l in enumerate(self.lines)]
        self.collect_headings()
        self.tables()
        self.sections()
        self.legacy_checks()
        # Fence validation needs section metadata so diagram blocks written as
        # text/ascii can be checked for their required text description.
        self.fence_checks()
        self.header_block()
        self.text_checks()
        self.link_checks()
        self.callouts()
        self.video_checks()
        self.specials()
        self.issues.sort(key=lambda x: (x.line, x.code))
        return self.issues

    # ---- front matter
    def front_matter(self):
        meta, end, err, kl, dups = read_front(self.lines)
        self.meta, self.fm_end, self.keyline = meta or {}, end, kl
        if end is None and err is None:
            if self.cfg.get("front_matter_required", False):
                self.err(0, "E010", "File lacks required YAML front matter (must start with '---' on line 1).")
            return
        if err:
            self.err(0, "E010", err)
            return
        for d in dups:
            self.err(kl.get(d, 1) - 1, "E015", f"Key '{d}' appears more than once.")
        fields = self.cfg["fields"]
        legacy = self.cfg.get("legacy") or {}
        optional = set(self.cfg.get("optional_keys") or [])
        require_all = self.cfg.get("require_all_template_keys", False)
        for key in self.meta:
            if key in fields or key in optional:
                continue
            if key in (legacy.get("keys") or []):
                self.add(kl.get(key, 1) - 1, "E014", legacy.get("severity", "error"),
                         f"Key '{key}' was removed from the master template; delete it.")
            else:
                self.warn(kl.get(key, 1) - 1, "E014", f"Key '{key}' is not in the master template.")
        for key, spec in fields.items():
            ln = kl.get(key, 1) - 1
            if key not in self.meta:
                if require_all and spec.get("required", True):
                    self.err(0, "E011", f"Required key '{key}' is missing.")
                continue
            v, t = self.meta[key], spec["type"]
            if v is None or v == "" or v == []:
                if not spec.get("allow_empty"):
                    self.err(ln, "E011", f"'{key}' is empty.")
                continue
            hint = None
            if t == "str" and not isinstance(v, str):
                hint = "must be a quoted text value"
            elif t == "int" and (not isinstance(v, int) or isinstance(v, bool)):
                hint = "must be a whole number"
            elif t == "records" and not (isinstance(v, list) and all(isinstance(x, dict) for x in v)):
                hint = "must be a list of entries with the same keys as in the master template"
            elif t == "list" and not (isinstance(v, list) and all(isinstance(x, str) and x.strip() for x in v)):
                hint = "must be a list of non-empty quoted strings"
            elif t == "date":
                if isinstance(v, str) and not _isodate(v):
                    self.err(ln, "E013", f"'{key}' = '{v}' is not a valid date (YYYY-MM-DD).")
                    continue
                if not isinstance(v, (str, dt.date)):
                    hint = "must be a date written YYYY-MM-DD"
            if hint:
                self.err(ln, "E012", f"'{key}' {hint} (got {type(v).__name__}).")
                continue
            if t == "str":
                if spec.get("pattern") and not re.fullmatch(spec["pattern"], v):
                    self.err(ln, "E013", f"'{key}' = '{v}' does not match {spec['pattern']}")
                if spec.get("enum") and v not in spec["enum"]:
                    self.err(ln, "E013", f"'{key}' = '{v}' must be one of {spec['enum']}")
            if t == "int" and spec.get("min") is not None and v < spec["min"]:
                self.err(ln, "E013", f"'{key}' must be >= {spec['min']}.")
            if t == "list":
                if spec.get("min_items") and len(v) < spec["min_items"]:
                    self.err(ln, "E013", f"'{key}' needs at least {spec['min_items']} items (has {len(v)}).")
                for item in v:
                    if spec.get("item_pattern") and not re.fullmatch(spec["item_pattern"], item):
                        self.err(ln, "E013", f"'{key}' item '{item}' does not match {spec['item_pattern']}")
            if t == "records":
                if spec.get("min_items") and len(v) < spec["min_items"]:
                    self.err(ln, "E013", f"'{key}' needs at least {spec['min_items']} entries (has {len(v)}).")
                for n_, item in enumerate(v, 1):
                    for k_ in spec.get("item_keys", []):
                        if not (isinstance(item.get(k_), str) and item[k_].strip()):
                            self.err(ln, "E011", f"'{key}' entry {n_} lacks a text value for '{k_}'.")
                    for k_ in item:
                        if k_ not in spec.get("item_keys", []):
                            self.warn(ln, "E014", f"'{key}' entry {n_} has key '{k_}' which is not in the master template.")
                    for k_, pat in (spec.get("item_patterns") or {}).items():
                        val = item.get(k_)
                        if isinstance(val, str) and val.strip() and not re.fullmatch(pat, val):
                            self.err(ln, "E013", f"'{key}' entry {n_}: {k_} '{val}' does not match {pat}")
                    for k_, allowed in (spec.get("item_enums") or {}).items():
                        val = item.get(k_)
                        if isinstance(val, str) and val.strip() and val not in allowed:
                            self.err(ln, "E013", f"'{key}' entry {n_}: {k_} '{val}' must be one of {allowed}")
        # review overdue
        d, n = _isodate(str(self.m("last_reviewed"))), self.meta.get("review_cycle_days")
        if d and isinstance(n, int) and d + dt.timedelta(days=n) < self.today:
            self.warn(kl.get("last_reviewed", 1) - 1, "E018",
                      f"Review overdue: last reviewed {d}, cycle {n} days.")

    # ---- headings
    def collect_headings(self):
        self.headings = []
        for i in range(self.start, len(self.lines)):
            if self.code[i] or self.lines[i].startswith("    "):
                continue
            line = self.lines[i]
            m_broken = re.match(r"^(#{1,6})([^#\s].*)$", line)
            if m_broken:
                self.err(i, "E024", f"ATX heading missing space after '#': '{line.strip()}'. Use '{m_broken.group(1)} {m_broken.group(2)}'.")
            m = HEAD.match(line)
            if m:
                text = re.sub(r"\s+#+\s*$", "", m.group(2) or "").strip()
                self.headings.append((len(m.group(1)), text, i))
        h1 = [h for h in self.headings if h[0] == 1]
        first_body = next((i for i in range(self.start, len(self.lines)) if self.lines[i].strip()), None)
        if not h1:
            self.err(first_body if first_body is not None else 0, "E022",
                     "Document must contain a top-level '# Title' (H1).")
        elif h1[0][2] != first_body:
            self.err(first_body if first_body is not None else 0, "E022",
                     "The first thing after the front matter must be the '# Title' (H1).")
        for lvl, t, i in h1[1:]:
            self.err(i, "E023", f"Extra H1 '{t}'. Only one H1 is allowed.")
        if h1 and self.meta.get("title") and h1[0][1] != self.meta["title"]:
            self.err(h1[0][2], "E016", f"H1 '{h1[0][1]}' differs from front-matter title '{self.meta['title']}'.")
        prev, seen = 0, {}
        for lvl, t, i in self.headings:
            if not t:
                self.err(i, "E024", "Heading has no text.")
            elif t.lower() in seen:
                self.warn(i, "E024", f"Duplicate heading '{t}' (first on line {seen[t.lower()] + 1}).")
            else:
                seen[t.lower()] = i
            if prev and lvl > prev + 1:
                self.err(i, "E021", f"Heading jumps from H{prev} to H{lvl}.")
            prev = lvl
            if i > self.start and self.lines[i - 1].strip():
                self.warn(i, "E075", "No blank line before this heading.")
            if i + 1 < len(self.lines) and self.lines[i + 1].strip():
                self.warn(i, "E075", "No blank line after this heading.")
        # sub-numbering 2.1 / 11.1.1
        stack, last = {}, {}
        for lvl, t, i in self.headings:
            m = re.match(r"^(\d+(?:\.\d+)+)\s", t + " ")
            if lvl == 2:
                m2 = re.match(r"^(\d+)\.\s", t + " ")
                stack = {2: m2.group(1)} if m2 else {}
                continue
            if lvl < 3:
                continue
            if m:
                parts = m.group(1).split(".")
                parent = stack.get(lvl - 1)
                if len(parts) != lvl - 1 or (parent and ".".join(parts[:-1]) != parent):
                    self.err(i, "E026", f"Number '{m.group(1)}' does not fit under parent '{parent}'.")
                else:
                    pk = ".".join(parts[:-1])
                    exp = last.get(pk, 0) + 1
                    if int(parts[-1]) != exp:
                        self.err(i, "E026", f"Expected number {pk}.{exp}, found {m.group(1)}.")
                    last[pk] = int(parts[-1])
                stack[lvl] = m.group(1)
            else:
                stack[lvl] = None
            for k in [k for k in stack if k > lvl]:
                del stack[k]

    # ---- fences
    def fence_checks(self):
        for f in self.fences:
            s, e = f["start"], f["end"]
            if e is None:
                self.err(s, "E030", f"Code fence ({f['char'] * f['len']}) opened here is never closed.")
                continue
            if not f["lang"]:
                self.err(s, "E031", "Code fence has no language label.")
            if f.get("suspect") is not None:
                self.err(s, "E030", f"This fence looks unclosed: a new fence opens on line {f['suspect'] + 1} before it was closed.")
            body = [l for l in self.lines[s + 1:e] if l.strip()]
            if not body:
                self.err(s, "E032", "Code block is empty.")
            if f["indent"] == 0:
                if s > 0 and self.lines[s - 1].strip():
                    self.warn(s, "E033", "No blank line before the code fence.")
                if e + 1 < len(self.lines) and self.lines[e + 1].strip():
                    self.warn(e, "E033", "No blank line after the code fence.")
            if f["lang"] == "mermaid" and body:
                self.mermaid(f, body)
            sec_type = self.type_at(s)
            if f["lang"] == "mermaid" or (f["lang"] in ("text", "ascii") and (sec_type == "diagrams" or any("-->" in l or "+---" in l for l in body))):
                j = e + 1
                while j < len(self.lines) and not self.lines[j].strip():
                    j += 1
                has_desc = False
                if j < len(self.lines):
                    next_line = self.lines[j].strip()
                    if re.match(r"^\*\*(Text description|Description|Image note|Diagram note)[^*]*:\*\*", next_line) or \
                       re.match(r"^\*\*(Text description|Description|Image note|Diagram note)[^*]*\*\*", next_line):
                        has_desc = True
                    elif next_line.startswith("> **Why every diagram needs a text version:") or next_line.startswith(">"):
                        has_desc = True
                if not has_desc:
                    self.err(e, "E094", "Diagram has no '**Text description:**' directly below it.")

    def mermaid(self, f, body):
        first = body[0].strip()
        kind = next((t for t in MERMAID_TYPES if first == t or first.startswith(t + " ") or first.startswith(t + "\t")), None)
        if not kind:
            self.err(f["start"], "E093", f"Unknown Mermaid diagram type '{first.split()[0]}'.")
            return
        if kind in ("flowchart", "graph") and not re.fullmatch(rf"{kind}\s+(TD|TB|BT|RL|LR)", first):
            self.err(f["start"] + 1, "E093", f"'{kind}' needs a direction: TD, TB, BT, RL or LR.")
        if kind in ("flowchart", "graph"):
            for k, l in enumerate(self.lines[f["start"] + 1:f["end"]], f["start"] + 1):
                raw = l.strip()
                if not raw or raw.startswith("%%"):
                    continue
                for a, b in (("[", "]"), ("{", "}"), ("(", ")")):
                    if l.count(a) != l.count(b):
                        self.err(k, "E093", f"Unbalanced '{a}' '{b}' in diagram line.")
                if re.search(r"(?<!-)->(?!>)", l) and not re.search(r"-[.\w\s]+->", l):
                    self.err(k, "E093", "Invalid arrow syntax '->' in flowchart. Use '-->' or '-->|label|'.")

    def type_at(self, idx):
        for s in getattr(self, "secs", []):
            if s["idx"] <= idx < s["end"]:
                return s["type"]
        return None

    # ---- tables
    def tables(self):
        self.tbls = []
        L, i = self.lines, self.start
        while i < len(L):
            if not self.code[i] and L[i].lstrip().startswith("|") and not L[i].startswith("    "):
                j = i
                while j < len(L) and not self.code[j] and L[j].lstrip().startswith("|"):
                    j += 1
                self.table(i, j)
                i = j
            else:
                i += 1

    def table(self, i, j):
        L = self.lines
        if i > self.start and L[i - 1].strip():
            self.err(i, "E042", "No blank line before the table.")
        if j < len(L) and L[j].strip():
            self.err(j - 1, "E042", "No blank line after the table (next line becomes a table row).")
        if j - i < 2 or not SEP.match(L[i + 1]):
            self.err(i, "E040", "Table needs a header row followed by a separator row (|---|---|).")
            return
        header = _cells(L[i])
        sep = _cells(L[i + 1])
        if not all(re.fullmatch(r":?-{3,}:?", c) for c in sep):
            self.err(i + 1, "E040", "Separator row cells must look like --- , :--- , ---: or :---:.")
        if len(sep) != len(header):
            self.err(i + 1, "E041", f"Separator has {len(sep)} columns, header has {len(header)}.")
        rows = []
        for k in range(i, j):
            s = L[k].rstrip()
            if not s.endswith("|") or s.endswith("\\|"):
                self.err(k, "E040", "Table row must end with '|'.")
            if k >= i + 2:
                c = _cells(L[k])
                rows.append((k, c))
                if len(c) != len(header):
                    self.err(k, "E041", f"Row has {len(c)} columns, header has {len(header)}.")
        if not rows:
            self.warn(i, "E043", "Table has no data rows.")
        self.tbls.append({"start": i, "end": j, "header": header, "rows": rows})

    # ---- sections
    def sections(self):
        L, cfg = self.lines, self.cfg
        learned = cfg.get("learned", {})
        canon_titles = [t for t, _ in learned.get("canon", [])] if learned else []
        enforce_order = cfg.get("enforce_section_order", False)
        h2 = [h for h in self.headings if h[0] == 2]
        self.secs, prev, last_canon, ctx_urls, legacy_ctx = [], 0, -1, {}, []
        for k, (lvl, text, idx) in enumerate(h2):
            end = h2[k + 1][2] if k + 1 < len(h2) else len(L)
            m = re.match(r"^(\d+)\.\s+(\S.*)$", text)
            sec = {"idx": idx, "end": end, "num": None, "title": text, "key": text.lower(), "type": None}
            self.secs.append(sec)
            if m:
                sec["num"], sec["title"], sec["key"] = int(m.group(1)), m.group(2), m.group(2).lower()
                if sec["num"] <= prev:
                    self.err(idx, "E025", f"Section number {sec['num']} must be greater than the previous ({prev}).")
                elif sec["num"] != prev + 1:
                    self.warn(idx, "E025", f"Section numbering skips from {prev} to {sec['num']}.")
                prev = sec["num"]
            elif self.cfg.get("require_section_numbering", False):
                self.err(idx, "E025", f"H2 must look like '## N. Title' (found '{text}').")
            if enforce_order and canon_titles:
                ci = canon_titles.index(sec["key"]) if sec["key"] in canon_titles else None
                if ci is not None:
                    if ci < last_canon:
                        self.err(idx, "E027", f"'{sec['title']}' is out of order compared with the master template.")
                    last_canon = max(last_canon, ci)
            # old context line (no longer in the template) and section type taken from the title
            j = idx + 1
            while j < end and not L[j].strip():
                j += 1
            if j < end and L[j].startswith("**Doc ID:**"):
                legacy_ctx.append(j)
            sec["type"] = self._type_by_title(sec["title"])
        if legacy_ctx:
            lines_txt = ", ".join(str(n + 1) for n in legacy_ctx[:15]) + (" and more" if len(legacy_ctx) > 15 else "")
            self.add(legacy_ctx[0], "E066", (self.cfg.get("legacy") or {}).get("severity", "error"),
                     f"{len(legacy_ctx)} old context line(s) found (lines {lines_txt}).")
        # required sections
        have_types = {s["type"] for s in self.secs if s["type"]}
        for t in self.cfg.get("required_section_types", []):
            if t not in have_types:
                self.err(0, "E020", f"No section with Section type '{t}'.")
        keys = {s["key"] for s in self.secs}
        for t in self.cfg.get("required_section_titles", []):
            if not any(k == t.lower() or k.startswith(t.lower() + ":") for k in keys):
                self.err(0, "E020", f"Required section '{t}' is missing.")
        first = next((s for s in self.secs), None)
        ft = self.cfg.get("first_section_type")
        if first and ft and first["type"] != ft and ft in have_types:
            self.err(first["idx"], "E027", f"The first section must be the '{ft}' section.")
        # required sub-headings
        for title, need in (self.cfg.get("required_subheadings") or {}).items():
            sec = next((s for s in self.secs if s["key"] == title.lower()), None)
            if not sec:
                continue
            subs = {_strip_num(t).lower() for l, t, i in self.headings if l == 3 and sec["idx"] < i < sec["end"]}
            for n in need:
                if n.lower() not in subs:
                    self.err(sec["idx"], "E029", f"Section '{sec['title']}' lacks the sub-heading '{n}'.")
        for sec in self.secs:
            fn = {"procedure": self.procedure, "sources": self.sources, "troubleshooting": self.troubleshooting,
                  "faq": self.faq, "meta": self.related}.get(sec["type"])
            if fn:
                fn(sec)

    def _type_by_title(self, title):
        for typ, pats in (self.cfg.get("section_types") or {}).items():
            if any(re.search(p, title, re.I) for p in pats):
                return typ
        return None

    def legacy_checks(self):
        legacy = self.cfg.get("legacy") or {}
        old = {x.lower() for x in (legacy.get("sections") or [])}
        for lvl, t, i in self.headings:
            if lvl in (2, 3) and _strip_num(t).lower() in old:
                self.add(i, "E068", legacy.get("severity", "error"), f"'{t}' was removed from the master template.")

    def sec_labels(self, sec):
        out = {}
        for i in range(sec["idx"] + 1, sec["end"]):
            m = LABEL.match(self.clean[i]) if self.clean[i] else None
            if m:
                out.setdefault(m.group(1).strip(), (i, m.group(2)))
        return out

    def procedure(self, sec):
        labels = {k.lower() for k in self.sec_labels(sec)}
        for need in self.cfg.get("procedure_required_labels", []):
            if need.lower() not in labels:
                self.err(sec["idx"], "E080", f"Procedure '{sec['title']}' lacks '**{need}:**'.")
        for group in self.cfg.get("procedure_one_of_labels", []):
            if not any(g.lower() in labels for g in group):
                self.err(sec["idx"], "E080", f"Procedure '{sec['title']}' needs one of: {', '.join('**' + g + ':**' for g in group)}.")
        steps = [(l, t, i) for l, t, i in self.headings if sec["idx"] < i < sec["end"] and t.startswith("Step")]
        has_list = any(re.match(r"^\s*\d+\.\s", self.clean[i]) for i in range(sec["idx"], sec["end"]))
        if not steps and not has_list:
            self.err(sec["idx"], "E080", f"Procedure '{sec['title']}' has no steps (### Step N - ... or a numbered list).")
        exp = 1
        for l, t, i in steps:
            m = re.match(r"^Step (\d+) - \S.*$", t)
            if not m:
                self.err(i, "E081", f"Step heading must be 'Step N - Title' (found '{t}').")
                continue
            if int(m.group(1)) != exp:
                self.err(i, "E081", f"Expected 'Step {exp}', found 'Step {m.group(1)}'.")
            exp = int(m.group(1)) + 1
        self._steps = getattr(self, "_steps", []) + [(sec, steps)]

    def sources(self, sec):
        src_file, src_url = self.meta.get("source_file"), self.meta.get("source_url")
        found_pdf = found_vid = False
        for i in range(sec["idx"] + 1, sec["end"]):
            m = re.match(r"^\*\*(Source document[^*]*?|Watch the full tutorial on YouTube):\*\*\s*\[([^\]]+)\]\(([^)\s]+)\)", self.clean[i])
            if not m:
                continue
            if m.group(1).startswith("Source document"):
                found_pdf = True
                if src_file and m.group(3) != src_file:
                    self.err(i, "E060", "Source document link differs from front-matter source_file.")
            else:
                found_vid = True
                if src_url and m.group(3) != src_url:
                    self.err(i, "E060", "Video link differs from front-matter source_url.")
        if src_file and not found_pdf:
            self.err(sec["idx"], "E060", "Section lacks '**Source document ...:** [name](url)' with the source_file link.")
        if src_url and not found_vid:
            self.err(sec["idx"], "E060", "Section lacks '**Watch the full tutorial on YouTube:** [..](source_url)'.")

    def troubleshooting(self, sec):
        hs = [(l, t, i) for l, t, i in self.headings if sec["idx"] < i < sec["end"]]
        for k, (l, t, i) in enumerate(hs):
            if l != 3:
                continue
            nxt = hs[k + 1][2] if k + 1 < len(hs) else sec["end"]
            if any(i < tb["start"] < nxt for tb in self.tbls):
                continue
            got = {m.group(1) for ln in self.clean[i:nxt] for m in [re.match(r"^\s*[-*]\s+\*\*(Symptom|Cause|Fix):\*\*", ln)] if m}
            miss = [x for x in ("Symptom", "Cause", "Fix") if x not in got]
            if miss:
                self.err(i, "E090", f"Entry '{t}' lacks: {', '.join(miss)} (use '- **Symptom:** ...').")

    def faq(self, sec):
        hs = [(l, t, i) for l, t, i in self.headings if sec["idx"] < i < sec["end"]]
        for k, (l, t, i) in enumerate(hs):
            if l != 3:
                continue
            nxt = hs[k + 1][2] if k + 1 < len(hs) else sec["end"]
            if not t.startswith("Q: ") or not t.rstrip().endswith("?"):
                self.err(i, "E091", f"FAQ heading must be 'Q: question?' (found '{t}').")
            if not any(ln.startswith("**A:**") and len(ln) > 8 for ln in self.lines[i + 1:nxt]):
                self.err(i, "E091", "FAQ entry has no '**A:** answer' line.")

    def related(self, sec):
        L, rel = self.lines, [str(x) for x in self.meta.get("related_docs", []) or []]
        lab = {i: self.clean[i].strip() for i in range(sec["idx"] + 1, sec["end"])}
        def block(name):
            st = next((i for i, t in lab.items() if t == f"**{name}**"), None)
            if st is None:
                return None
            out = []
            for i in range(st + 1, sec["end"]):
                if re.match(r"^\*\*[^*]+\*\*\s*$", lab[i]):
                    break
                if lab[i]:
                    out.append((i, L[i]))
            return st, out
        rd, ofr = block("Related documents"), block("Official references")
        if rel and rd is None:
            self.err(sec["idx"], "E096", "related_docs is set but '**Related documents**' list is missing.")
        if rd:
            ids = set()
            for i, ln in rd[1]:
                m = re.match(r"^- \[([^\]:]+): (.+?)\]\((https://[^)\s]+)\)(?: - .+)?$", ln)
                if not m:
                    self.err(i, "E096", "Related document must be '- [ID: Title](https://url) - description'.")
                else:
                    ids.add(m.group(1))
            for r in rel:
                if r not in ids:
                    self.err(rd[0], "E096", f"related_docs lists {r} but no matching link is in this list.")
            for r in ids - set(rel):
                self.err(rd[0], "E096", f"{r} is linked here but missing from front-matter related_docs.")
        if ofr is None:
            self.err(sec["idx"], "E096", "'**Official references**' list is missing.")
        else:
            sf = self.meta.get("source_file")
            if sf and not any(sf in ln for _, ln in ofr[1]):
                self.err(ofr[0], "E060", "Official references must include the original document (source_file) link.")

    # ---- header block
    def header_block(self):
        h1 = next((h for h in self.headings if h[0] == 1), None)
        if not h1:
            return
        h2s = [h[2] for h in self.headings if h[0] == 2]
        stop = h2s[0] if h2s else len(self.lines)
        lab = {}
        for i in range(h1[2] + 1, stop):
            m = re.match(r"^\*\*([^*:]+):\*\*\s*(.*?)\s*$", self.clean[i]) if self.clean[i] else None
            if m:
                lab[m.group(1)] = (i, m.group(2))
        legacy = self.cfg.get("legacy") or {}
        old = [n for n in (legacy.get("header_labels") or []) if n in lab]
        if old:
            self.add(lab[old[0]][0], "E067", legacy.get("severity", "error"),
                     f"Old header lines under the H1 ({', '.join(old)}).")
        need = list(self.cfg.get("header_required", []))
        fm_map = {"Document ID": "doc_id", "Platform": "platform", "Difficulty": "difficulty", "Last reviewed": "last_reviewed"}
        for n in need:
            if n not in lab:
                self.err(h1[2], "E065", f"Header line '**{n}:**' is missing under the H1.")
                continue
            i, v = lab[n]
            if n in fm_map and v != str(self.m(fm_map[n])):
                self.err(i, "E065", f"'{n}' is '{v}' but front matter says '{self.m(fm_map[n])}'.")
            if n == "Estimated time" and not re.fullmatch(r"\d+ (minutes?|hours?)", v):
                self.err(i, "E065", "Estimated time must look like '15 minutes'.")
            if n == "Video duration" and not re.fullmatch(r"(\d{2}:)?\d{2}:\d{2}", v):
                self.err(i, "E065", "Video duration must look like 09:35 or 01:05:30.")
        if "Video duration" in lab:
            duration_text = lab["Video duration"][1]
            if re.fullmatch(r"(\d{2}:)?\d{2}:\d{2}", duration_text):
                self.duration = _secs(duration_text)
                if self.duration is None:
                    self.err(lab["Video duration"][0], "E065", "Video duration has invalid minutes or seconds.")

    # ---- text-level checks
    def text_checks(self):
        cfg, lim = self.cfg, self.cfg.get("limits", {})
        ok_status = self.meta.get("status") in cfg.get("placeholder_ok_status", [])
        allowed_html = set(cfg.get("allowed_html", []))
        for i, raw in enumerate(self.lines):
            n = i
            for p in SECRETS:
                if p.search(raw):
                    self.err(n, "E074", "Possible password/token/secret in the text.")
                    break
            if CTRL.search(raw):
                self.warn(n, "E072", "Control character found.")
            if raw.startswith("\t") or re.match(r"^ *\t", raw):
                self.warn(n, "E076", "Tab used for indentation; use spaces.")
            if lim.get("max_line_chars") and len(raw) > lim["max_line_chars"]:
                self.warn(n, "E071", f"Line is {len(raw)} characters long.")
            if self.code[i]:
                continue
            c = self.clean[i]
            if not ok_status:
                for ph in cfg.get("placeholders", []):
                    if ph in raw:
                        self.err(n, "E017", f"Placeholder '{ph}' is still present.")
                        break
            for m in HTML.finditer(c):
                if m.group(2).lower() not in allowed_html:
                    self.err(n, "E072", f"Raw HTML tag <{m.group(2)}> is not allowed.")
            if ESC.search(c):
                self.err(n, "E073", "Escaped Markdown character (backslash) found outside code.")
            if c.rstrip().endswith("\\"):
                self.err(n, "E073", "Line ends with a trailing backslash.")
            if re.match(r"^\s*[*+]\s", c):
                self.warn(n, "E076", "Use '- ' for bullets.")
            m = re.match(r"^\s*[-*]\s*\[(.?)\](.?)", c)
            if m and (m.group(1) not in (" ", "x") or m.group(2) != " "):
                self.err(n, "E076", "Task item must be '- [ ] text' or '- [x] text'.")
        # chunk size per heading
        hs = [h[2] for h in self.headings] + [len(self.lines)]
        for k, (l, t, i) in enumerate(self.headings):
            size = sum(len(x) for x in self.lines[i + 1:hs[k + 1]])
            if lim.get("max_chunk_chars") and size > lim["max_chunk_chars"]:
                self.warn(i, "E070", f"'{t}' has {size} characters before the next heading (limit {lim['max_chunk_chars']}).")

    # ---- links, images, references
    def link_checks(self):
        L, c = self.lines, self.clean
        slugs, seen = set(), {}
        for l, t, i in self.headings:
            s = _slug(t)
            if s in seen:
                seen[s] += 1
                s = f"{s}-{seen[s] - 1}"
            else:
                seen[s] = 1
            slugs.add(s)
        refs_def = {m.group(1).lower() for ln in c for m in [re.match(r"^\[([^\]^]+)\]:\s*\S+", ln)] if m}
        fn_def = {m.group(1) for ln in c for m in [re.match(r"^\[\^([^\]]+)\]:", ln)] if m}
        sec_nums = {s["num"] for s in self.secs if s["num"]}
        vague = {v.lower() for v in self.cfg.get("vague_link_text", [])}
        fn_used, ref_used = set(), set()
        for i, ln in enumerate(c):
            if not ln:
                continue
            for alt, src in IMG.findall(ln):
                s = _image_target(src)
                if not alt.strip():
                    self.err(i, "E052", "Image has empty alt text.")
                elif len(alt.strip()) < 10:
                    self.warn(i, "E052", f"Alt text '{alt}' is too short to describe the image.")
                if s.startswith("data:"):
                    self.err(i, "E051", "Inline base64 image.")
                elif not s:
                    self.err(i, "E053", "Image has an empty path.")
                else:
                    parsed = urlsplit(s)
                    if not parsed.scheme and not s.startswith("//"):
                        local = self.md_dir / unquote(parsed.path)
                        if not local.exists():
                            self.err(i, "E050", f"Image file not found: {s}")
            if self.cfg.get("require_image_notes", False) and re.match(r"^!\[[^\]]*\]\([^)]*\)\s*$", ln.strip()):
                j = i + 1
                while j < len(L) and not L[j].strip():
                    j += 1
                if j >= len(L) or not re.match(r"^\*\*(Image note|Text description)[^*]*:\*\*", L[j]):
                    self.err(i, "E094", "Image has no '**Image note:**' / '**Text description:**' below it.")
            for text, url in LINK.findall(ln):
                u = url.strip()
                if not u:
                    self.err(i, "E053", "Link has an empty URL.")
                    continue
                if " " in u and not re.match(r'^\S+\s+"[^"]*"$', u):
                    self.err(i, "E054", f"Link URL contains spaces: {u}")
                if text.strip().lower() in vague:
                    self.err(i, "E055", f"Link text '{text}' is not descriptive.")
                if re.match(r"^\s*$", text) and not u.startswith("#"):
                    self.err(i, "E055", "Link has empty text.")
            for a in re.findall(r"\]\(#([^)\s]+)\)", ln):
                if a not in slugs:
                    self.err(i, "E057", f"Anchor '#{a}' matches no heading.")
            for r in re.findall(r"\[[^\]]+\]\[([^\]]+)\]", ln):
                ref_used.add((r.lower(), i))
            for f in re.findall(r"\[\^([^\]]+)\](?!:)", ln):
                fn_used.add((f, i))
            for num in re.findall(r"\bSection (\d+)\b", ln):
                if int(num) not in sec_nums:
                    self.warn(i, "E058", f"Refers to Section {num}, which does not exist.")
            for t_, u in re.findall(r"\[([^\]]*)\]\((https://www\.youtube\.com/watch[^)\s]*)\)", ln):
                tm = re.match(r"^(?:Open at )?((?:\d{1,2}:)?\d{1,2}:\d{2})\b", t_)
                tv = re.search(r"[&?]t=(\d+)s?\b", u)
                shown_seconds = _secs(tm.group(1)) if tm else None
                if tm and shown_seconds is None:
                    self.err(i, "E082", f"Timestamp '{tm.group(1)}' has invalid minutes or seconds.")
                elif tm and tv and shown_seconds != int(tv.group(1)):
                    self.err(i, "E083", f"Link says {tm.group(1)} ({shown_seconds}s) but URL has t={tv.group(1)}s.")
                if tv and not re.search(r"&t=\d+s(?:&|$)", u):
                    self.err(i, "E082", "YouTube timestamp must be written '&t=SECONDSs' (e.g. &t=180s).")
        for r, i in ref_used:
            if r not in refs_def:
                self.err(i, "E056", f"Reference link [{r}] has no definition line.")
        for f, i in fn_used:
            if f not in fn_def:
                self.err(i, "E056", f"Footnote [^{f}] has no definition.")
        for f in fn_def:
            if f not in {x for x, _ in fn_used}:
                self.err(next(k for k, ln in enumerate(c) if ln.startswith(f"[^{f}]:")), "E056", f"Footnote [^{f}] is defined but never used.")

    # ---- callouts
    def callouts(self):
        labels = {x.lower() for x in self.cfg.get("callout_labels", [])}
        emap = self.cfg.get("callout_emoji", {})
        i, L = self.start, self.lines
        while i < len(L):
            if not self.code[i] and L[i].lstrip().startswith(">"):
                j = i
                while j < len(L) and not self.code[j] and L[j].lstrip().startswith(">"):
                    j += 1
                first = re.sub(r"^(\s*>\s?)+", "", L[i]).strip()
                m = re.match(r"^(?P<e>[^\w\s*>]+)?\s*\*\*(?P<l>[^*]+?):\*\*", first)
                if not m:
                    self.err(i, "E095", "Callout must start with a bold text label like '**Note:**'.")
                else:
                    lab, e = m.group("l").strip(), m.group("e")
                    if lab.lower() not in labels:
                        self.warn(i, "E095", f"Callout label '{lab}' is not in the standard list.")
                    if e and e in emap and lab not in emap[e]:
                        self.err(i, "E095", f"Emoji {e} must go with {emap[e]}, not '{lab}'.")
                i = j
            else:
                i += 1

    # ---- video
    def video_checks(self):
        src_url = self.meta.get("source_url") or ""
        vid = (re.search(r"[?&]v=([\w-]+)", src_url) or [None, None])[1]
        n_video = 0
        for i, l in enumerate(self.lines):
            if self.code[i]:
                continue
            if l.startswith("**Video:**"):
                n_video += 1
                m = VIDEO.match(l)
                if not m:
                    if not URLRE.search(l):
                        why = "no link"
                    elif not re.search(r"[&?]t=", l):
                        why = "link has no &t= timestamp"
                    elif not re.search(r"&t=\d+s\)", l):
                        why = "&t= must be seconds ending in 's'"
                    else:
                        why = "text must be '[MM:SS - description](url)'"
                    self.err(i, "E082", f"Video line malformed: {why}.")
                    continue
                timestamp_seconds = _secs(m.group(1))
                if timestamp_seconds is None:
                    self.err(i, "E082", f"Timestamp '{m.group(1)}' has invalid minutes or seconds.")
                elif getattr(self, "duration", None) is not None and int(m.group(5)) > self.duration:
                    self.err(i, "E084", "Timestamp is later than the Video duration.")
                if vid and m.group(4) != vid:
                    self.warn(i, "E085", f"Video ID '{m.group(4)}' differs from source_url video '{vid}'.")
        if n_video:
            for sec, steps in getattr(self, "_steps", []):
                hs = [h for h in self.headings if sec["idx"] < h[2] < sec["end"]]
                for l, t, i in steps:
                    nxt = next((h[2] for h in hs if h[2] > i and h[0] <= l), sec["end"])
                    if not any(x.startswith("**Video:**") for x in self.lines[i:nxt]):
                        self.warn(i, "E086", f"'{t}' has no **Video:** line.")
        # chapter index
        for tb in self.tbls:
            if [h.lower() for h in tb["header"]] == ["time", "seconds", "topic", "link"]:
                for i, c in tb["rows"]:
                    if len(c) != 4:
                        continue
                    if not re.fullmatch(r"(\d{2}:)?\d{2}:\d{2}", c[0]) or not c[1].isdigit():
                        self.err(i, "E098", "Time must be MM:SS and Seconds a whole number.")
                        continue
                    table_seconds = _secs(c[0])
                    if table_seconds is None:
                        self.err(i, "E098", f"Time '{c[0]}' has invalid minutes or seconds.")
                        continue
                    if table_seconds != int(c[1]):
                        self.err(i, "E098", f"Time {c[0]} is {_secs(c[0])}s but Seconds column says {c[1]}.")
                    m = re.match(r"^\[Open at ([^\]]+)\]\((https://www\.youtube\.com/watch\?v=[\w-]+[^)\s]*&t=(\d+)s)\)$", c[3])
                    if not m:
                        self.err(i, "E098", "Link must be '[Open at MM:SS](https://www.youtube.com/watch?v=ID&t=SECONDSs)'.")
                    else:
                        if m.group(1) != c[0]:
                            self.err(i, "E098", f"Link text says {m.group(1)} but Time column says {c[0]}.")
                        if int(m.group(3)) != int(c[1]):
                            self.err(i, "E098", f"Link has t={m.group(3)}s but Seconds column says {c[1]}.")

    # ---- version history, questions list
    def specials(self):
        sec = next((s for s in self.secs if s["key"] == "version history"), None)
        if sec:
            tb = next((t for t in self.tbls if sec["idx"] < t["start"] < sec["end"]), None)
            if not tb:
                self.err(sec["idx"], "E097", "Version History has no table.")
            else:
                if [h.lower() for h in tb["header"]] != ["version", "date", "author", "change summary"]:
                    self.err(tb["start"], "E097", "Header must be: Version | Date | Author | Change Summary.")
                last, lastd = (0, 0), None
                for i, c in tb["rows"]:
                    if len(c) != 4:
                        continue
                    if not re.fullmatch(r"\d+\.\d+", c[0]):
                        self.err(i, "E097", f"Version '{c[0]}' must look like 2.1.")
                        continue
                    v = tuple(int(x) for x in c[0].split("."))
                    d = _isodate(c[1])
                    if not d:
                        self.err(i, "E097", f"Date '{c[1]}' must be YYYY-MM-DD.")
                    if v <= last:
                        self.err(i, "E097", f"Version {c[0]} must be higher than the row above.")
                    if d and lastd and d < lastd:
                        self.err(i, "E097", "Date is earlier than the row above.")
                    if not c[2] or not c[3]:
                        self.err(i, "E097", "Author and Change Summary cannot be empty.")
                    last, lastd = v, d or lastd
                if tb["rows"] and last != (0, 0):
                    fmv = str(self.meta.get("version", ""))
                    if fmv and fmv != ".".join(map(str, last)):
                        self.err(self.keyline.get("version", 1) - 1, "E019",
                                 f"Front-matter version '{fmv}' but Version History ends at {'.'.join(map(str, last))}.")
        h = next(((l, t, i) for l, t, i in self.headings if _strip_num(t).lower() == "questions this document answers"), None)
        if h:
            nxt = next((x[2] for x in self.headings if x[2] > h[2]), len(self.lines))
            qs = [(i, self.lines[i]) for i in range(h[2] + 1, nxt) if self.lines[i].startswith("- ")]
            if len(qs) < self.cfg.get("min_questions", 1):
                self.err(h[2], "E092", f"Needs at least {self.cfg.get('min_questions')} questions (found {len(qs)}).")
            for i, q in qs:
                if not q.rstrip().endswith("?"):
                    self.err(i, "E092", "Each question must end with '?'.")


# ---------------------------------------------------------------- public API
def verify_file(path, cfg, today=None):
    path = Path(path)
    try:
        text = path.read_bytes().decode("utf-8")
    except UnicodeDecodeError as e:
        v = Verifier(cfg, path.parent)
        v.err(0, "E001", f"Not valid UTF-8: {e}")
        issues = v.issues
    except OSError as e:
        v = Verifier(cfg, path.parent)
        v.err(0, "E002", f"Could not read '{path}': {e}")
        issues = v.issues
    else:
        v = Verifier(cfg, path.parent, today)
        try:
            issues = v.run(text)
        except Exception as e:
            v.err(0, "E099", f"Verifier exception: {type(e).__name__}: {e}")
            issues = v.issues
    errors = [i for i in issues if i.severity == "error"]
    warns = [i for i in issues if i.severity == "warning"]
    passed = not errors and not (cfg.get("fail_on_warnings") and warns)
    return {"file": path.name, "passed": passed, "errors": len(errors), "warnings": len(warns),
            "issues": [asdict(i) for i in issues]}


def to_text(r):
    out = [f"{'PASSED' if r['passed'] else 'FAILED'}  {r['file']}  ({r['errors']} errors, {r['warnings']} warnings)"]
    for i in r["issues"]:
        out += [f"  line {i['line']:>4}  [{i['severity'].upper()} {i['code']}] {i['message']}",
                f"             impact: {i['impact']}", f"             fix:    {i['fix']}"]
    return "\n".join(out)


def main(argv=None):
    import argparse

    ap = argparse.ArgumentParser(description="Validate Markdown files against the configured RAG template.")
    ap.add_argument("files", nargs="+", help="Markdown files to validate")
    ap.add_argument("--rules", default=str(Path(__file__).with_name("rules.yaml")),
                    help="Path to the YAML rules file (default: rules.yaml)")
    ap.add_argument("--json", action="store_true", help="Print machine-readable JSON")
    ap.add_argument("--today", help="Override today's date for review-cycle checks (YYYY-MM-DD)")
    args = ap.parse_args(argv)

    try:
        cfg = load_rules(args.rules)
        today = _isodate(args.today) if args.today else None
        if args.today and today is None:
            ap.error("--today must be a valid YYYY-MM-DD date")
    except (OSError, KeyError, ValueError, yaml.YAMLError) as e:
        ap.error(str(e))

    results = [verify_file(f, cfg, today) for f in args.files]
    if args.json:
        print(json.dumps(results, indent=2))
    else:
        print("\n\n".join(to_text(r) for r in results))
    return 0 if all(r["passed"] for r in results) else 1


if __name__ == "__main__":
    sys.exit(main())
