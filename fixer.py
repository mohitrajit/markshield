"""Autonomous Markdown Auto-Fixer for MarkShield RAG Quality Gate.

Repairs common mechanical syntax and formatting flaws in Markdown documents
intended for RAG pipelines, including:
- Converting raw HTML <u> tags to bold Markdown
- Normalizing FAQ questions (### Q: ...) and answers (**A:** ...)
- Normalizing step headings (em-dashes/colons -> hyphen)
- Normalizing video timestamp links (em-dashes -> hyphen, &t=...s)
- Trimming extraneous H1 prefixes (e.g. 'Topic - ') to match front-matter title
- Removing obsolete legacy metadata lines under H1
- Adding language tags to bare code fences (inferring sql, python, json, or text)
- Converting front-matter string fields to lists (e.g. audience) and deduplicating keys
- Ensuring space after '#' in ATX headings (e.g. ##Heading -> ## Heading)
- Promoting H3 to H2 when a document has no H2s (e.g. Glossary lists)
- Ensuring blank line padding around headings, tables, and code fences
"""
import re
from dataclasses import asdict, dataclass
from pathlib import Path


@dataclass
class FixRecord:
    line: int
    code: str
    rule: str
    original: str
    fixed: str
    description: str


def _scan_fences(lines):
    code = [False] * len(lines)
    cur = None
    for i, line in enumerate(lines):
        m = re.match(r"^(\s{0,3})(`{3,}|~{3,})(.*)$", line)
        if cur:
            code[i] = True
            if m and m.group(2)[0] == cur["char"] and len(m.group(2)) >= cur["len"] and not m.group(3).strip():
                cur = None
        elif m:
            code[i] = True
            cur = {"char": m.group(2)[0], "len": len(m.group(2))}
    return code


class MarkdownFixer:
    def __init__(self, text, filename=""):
        self.raw = text
        self.filename = filename
        self.fixes = []

    def fix(self):
        text = self.raw
        self.fixes.clear()

        # Step 1: Normalize newlines and whitespace
        text = self._fix_newlines_and_tabs(text)

        # Step 2: Front matter normalization (duplicate keys, string-to-list)
        text = self._fix_front_matter(text)

        # Step 3: Raw HTML tags (<u> -> **)
        text = self._fix_html_tags(text)

        # Step 4: ATX heading space enforcement (##Heading -> ## Heading)
        text = self._fix_atx_spacing(text)

        # Step 5: Heading promotion if document skips H2 entirely (e.g. Glossary.md)
        text = self._fix_heading_promotion(text)

        # Step 6: Step headings (Step N — Title -> Step N - Title)
        text = self._fix_step_headings(text)

        # Step 7: Video timestamp link dashes and URL &t= parameters
        text = self._fix_video_links(text)

        # Step 8: H1 title prefix alignment (Topic - ... -> ...)
        text = self._fix_title_prefix(text)

        # Step 9: Remove obsolete legacy lines under H1
        text = self._fix_legacy_headers(text)

        # Step 10: Bare code fences (tag with inferred language or text)
        text = self._fix_bare_code_fences(text)

        # Step 11: FAQ Q&A structure (### Q: ... and **A:** ...)
        text = self._fix_faq_structure(text)

        # Step 12: Ensure blank lines around headings, tables, fences
        text = self._fix_blank_line_padding(text)

        return text, self.fixes

    # ---- 1. Newlines & Tabs
    def _fix_newlines_and_tabs(self, text):
        lines = text.splitlines()
        code_mask = _scan_fences(lines)
        for i, l in enumerate(lines):
            if not code_mask[i] and ("\t" in l):
                fixed = l.replace("\t", "    ")
                self.fixes.append(FixRecord(
                    line=i + 1, code="E076", rule="TabsToSpaces",
                    original=l, fixed=fixed,
                    description="Converted tab indentation to 4 spaces."
                ))
                lines[i] = fixed
        res = "\n".join(lines)
        if not res.endswith("\n"):
            self.fixes.append(FixRecord(
                line=len(lines), code="E077", rule="TrailingNewline",
                original="", fixed="\\n",
                description="Added missing trailing newline at end of file."
            ))
            res += "\n"
        return res

    # ---- 2. Front matter normalization
    def _fix_front_matter(self, text):
        lines = text.splitlines(keepends=True)
        if not lines or lines[0].strip() != "---":
            return text
        end = next((i for i in range(1, len(lines)) if lines[i].strip() == "---"), None)
        if not end:
            return text

        fm_lines = lines[1:end]
        seen_keys = {}
        new_fm = []
        modified = False

        for idx, line in enumerate(fm_lines):
            m = re.match(r"^([A-Za-z_][\w-]*)\s*:\s*(.*)$", line)
            if not m:
                new_fm.append(line)
                continue
            key, val = m.group(1), m.group(2).strip()
            # Deduplicate duplicate keys
            if key in seen_keys:
                self.fixes.append(FixRecord(
                    line=idx + 2, code="E015", rule="DeduplicateKey",
                    original=line.strip(), fixed="",
                    description=f"Removed duplicate front-matter key '{key}'."
                ))
                modified = True
                continue
            seen_keys[key] = idx

            # Convert single string to list for known list fields
            if key in ("audience", "roles_required", "tags"):
                # e.g. audience: "Architect" or audience: Architect
                if val and not val.startswith("[") and not val.startswith("-"):
                    clean_val = val.strip("\"'")
                    fixed_line = f"{key}: [\"{clean_val}\"]\n"
                    self.fixes.append(FixRecord(
                        line=idx + 2, code="E012", rule="StringToList",
                        original=line.strip(), fixed=fixed_line.strip(),
                        description=f"Converted '{key}' string value to a YAML list [\"{clean_val}\"]."
                    ))
                    new_fm.append(fixed_line)
                    modified = True
                    continue

            new_fm.append(line)

        if modified:
            return "".join([lines[0]] + new_fm + lines[end:])
        return text

    # ---- 3. HTML tags (<u> -> **)
    def _fix_html_tags(self, text):
        lines = text.splitlines()
        code_mask = _scan_fences(lines)
        for i, l in enumerate(lines):
            if code_mask[i]:
                continue
            if "<u>" in l.lower() or "</u>" in l.lower():
                fixed = re.sub(r"<\s*u\s*>(.*?)<\s*/\s*u\s*>", r"**\1**", l, flags=re.IGNORECASE)
                fixed = re.sub(r"<\s*/?\s*u\s*>", "", fixed, flags=re.IGNORECASE)
                if fixed != l:
                    self.fixes.append(FixRecord(
                        line=i + 1, code="E072", rule="ConvertHtmlUToBold",
                        original=l, fixed=fixed,
                        description="Converted raw HTML <u> underline tag to Markdown bold (**text**)."
                    ))
                    lines[i] = fixed
        joined = "\n".join(lines)
        # Catch any multiline <u>...</u> outside code blocks
        if "<u>" in joined.lower():
            def repl_u(m):
                content = m.group(1).replace("\n", " ").strip()
                return f"**{content}**"
            fixed_joined = re.sub(r"<\s*u\s*>(.*?)<\s*/\s*u\s*>", repl_u, joined, flags=re.IGNORECASE | re.DOTALL)
            if fixed_joined != joined:
                self.fixes.append(FixRecord(
                    line=1, code="E072", rule="ConvertMultilineHtmlUToBold",
                    original="<u>...</u>", fixed="**...**",
                    description="Converted multiline HTML <u> underline tags to Markdown bold (**text**)."
                ))
                joined = fixed_joined
        return joined + ("\n" if text.endswith("\n") else "")

    # ---- 4. ATX heading space (##Heading -> ## Heading)
    def _fix_atx_spacing(self, text):
        lines = text.splitlines()
        code_mask = _scan_fences(lines)
        for i, l in enumerate(lines):
            if code_mask[i]:
                continue
            m = re.match(r"^(#{1,6})([^#\s].*)$", l)
            if m:
                fixed = f"{m.group(1)} {m.group(2)}"
                self.fixes.append(FixRecord(
                    line=i + 1, code="E024", rule="AtxHeadingSpacing",
                    original=l, fixed=fixed,
                    description=f"Inserted missing space after '{m.group(1)}' in ATX heading."
                ))
                lines[i] = fixed
        return "\n".join(lines) + ("\n" if text.endswith("\n") else "")

    # ---- 5. Heading promotion when document skips H2 entirely (e.g. Glossary.md)
    def _fix_heading_promotion(self, text):
        lines = text.splitlines()
        code_mask = _scan_fences(lines)
        # Check if file has # H1 and ### H3, but completely lacks ## H2
        has_h2 = any(re.match(r"^##\s+\S", l) for i, l in enumerate(lines) if not code_mask[i])
        h3_indices = [i for i, l in enumerate(lines) if not code_mask[i] and re.match(r"^###\s+\S", l)]

        if not has_h2 and len(h3_indices) > 0:
            for i in h3_indices:
                orig = lines[i]
                fixed = re.sub(r"^###\s+", "## ", orig)
                lines[i] = fixed
                self.fixes.append(FixRecord(
                    line=i + 1, code="E021", rule="PromoteH3ToH2",
                    original=orig, fixed=fixed,
                    description="Promoted top-level '###' subheading to '##' section heading (document lacked H2 levels)."
                ))
        return "\n".join(lines) + ("\n" if text.endswith("\n") else "")

    # ---- 6. Step headings (Step N — Title -> Step N - Title)
    def _fix_step_headings(self, text):
        lines = text.splitlines()
        code_mask = _scan_fences(lines)
        for i, l in enumerate(lines):
            if code_mask[i]:
                continue
            m = re.match(r"^(#{1,6}\s*Step\s+\d+)\s*[—–:.]\s*(\S.*)$", l)
            if m:
                fixed = f"{m.group(1)} - {m.group(2)}"
                self.fixes.append(FixRecord(
                    line=i + 1, code="E081", rule="NormalizeStepHeadingDash",
                    original=l, fixed=fixed,
                    description="Normalized step heading delimiter to standard hyphen ('Step N - Title')."
                ))
                lines[i] = fixed
        return "\n".join(lines) + ("\n" if text.endswith("\n") else "")

    # ---- 7. Video timestamp links (em-dashes, 1-digit minutes, and missing 's' in URL)
    def _fix_video_links(self, text):
        lines = text.splitlines()
        code_mask = _scan_fences(lines)
        vid_pat = re.compile(r"(\[((?:\d{1,2}:)?\d{1,2}:\d{2}))\s*[—–:]\s*([^\]]+\]\(https?://(?:www\.)?youtube\.com/[^)]+\))")
        single_min_pat = re.compile(r"\[(\d:\d{2})\s*-\s*([^\]]+\]\(https?://(?:www\.)?youtube\.com/[^)]+\))")

        for i, l in enumerate(lines):
            if code_mask[i]:
                continue
            cur = l
            if vid_pat.search(cur):
                fixed = vid_pat.sub(r"\1 - \3", cur)
                if fixed != cur:
                    self.fixes.append(FixRecord(
                        line=i + 1, code="E082", rule="NormalizeVideoLinkDash",
                        original=cur, fixed=fixed,
                        description="Normalized em-dash or colon in video timestamp link text to hyphen."
                    ))
                    cur = fixed
            if single_min_pat.search(cur):
                fixed = single_min_pat.sub(r"[0\1 - \2", cur)
                if fixed != cur:
                    self.fixes.append(FixRecord(
                        line=i + 1, code="E082", rule="PadVideoTimestampMinutes",
                        original=cur, fixed=fixed,
                        description="Padded single-digit minutes in video timestamp to 2 digits (e.g. 4:56 -> 04:56)."
                    ))
                    cur = fixed
            t_pat = re.compile(r"([?&]t=\d+)(?![s\w])")
            if t_pat.search(cur) and "youtube.com" in cur:
                fixed = t_pat.sub(r"\1s", cur)
                if fixed != cur:
                    self.fixes.append(FixRecord(
                        line=i + 1, code="E082", rule="AddSecondsSuffixToVideoUrl",
                        original=cur, fixed=fixed,
                        description="Appended 's' unit to YouTube URL timestamp (&t=SECONDSs)."
                    ))
                    cur = fixed
            lines[i] = cur
        return "\n".join(lines) + ("\n" if text.endswith("\n") else "")

    # ---- 8. H1 title prefix alignment
    def _fix_title_prefix(self, text):
        lines = text.splitlines()
        code_mask = _scan_fences(lines)
        # Extract front-matter title if present
        fm_title = None
        if lines and lines[0].strip() == "---":
            end = next((i for i in range(1, len(lines)) if lines[i].strip() == "---"), None)
            if end:
                for l in lines[1:end]:
                    m = re.match(r"^title\s*:\s*[\"']?(.*?)[\"']?\s*$", l)
                    if m:
                        fm_title = m.group(1).strip()
                        break

        for i, l in enumerate(lines):
            if code_mask[i]:
                continue
            if l.startswith("# "):
                h1_text = l[2:].strip()
                # Check for "Topic - " or "Topic: "
                m = re.match(r"^Topic\s*[-—:]\s*(.+)$", h1_text, re.IGNORECASE)
                if m:
                    clean_h1 = m.group(1).strip()
                    # If front-matter title matches clean_h1 (ignoring case)
                    if fm_title and fm_title.lower() == clean_h1.lower():
                        clean_h1 = fm_title
                    fixed = f"# {clean_h1}"
                    self.fixes.append(FixRecord(
                        line=i + 1, code="E016", rule="TrimTopicPrefixFromH1",
                        original=l, fixed=fixed,
                        description=f"Trimmed 'Topic - ' prefix from H1 to match front-matter title '{clean_h1}'."
                    ))
                    lines[i] = fixed
                    break
        return "\n".join(lines) + ("\n" if text.endswith("\n") else "")

    # ---- 9. Remove obsolete legacy metadata lines under H1
    def _fix_legacy_headers(self, text):
        lines = text.splitlines(keepends=True)
        code_mask = _scan_fences([l.rstrip("\r\n") for l in lines])
        h1_idx = next((i for i, l in enumerate(lines) if not code_mask[i] and l.startswith("# ")), None)
        if h1_idx is None:
            return text

        h2_idx = next((i for i in range(h1_idx + 1, len(lines)) if not code_mask[i] and lines[i].startswith("## ")), len(lines))
        legacy_patterns = [
            re.compile(r"^\s*\*\*(?:Video duration|Estimated time|Document ID|Platform|Difficulty|Last reviewed)\s*:\*\*.*$", re.I)
        ]

        out = []
        for i, line in enumerate(lines):
            if h1_idx < i < h2_idx and not code_mask[i]:
                if any(p.match(line) for p in legacy_patterns):
                    self.fixes.append(FixRecord(
                        line=i + 1, code="E067", rule="RemoveLegacyHeaderLine",
                        original=line.strip(), fixed="",
                        description=f"Removed obsolete legacy header line under H1 ({line.strip()[:35]}...)."
                    ))
                    continue
            out.append(line)
        return "".join(out)

    # ---- 10. Bare code fences (tag with inferred language or text)
    def _fix_bare_code_fences(self, text):
        lines = text.splitlines()
        in_fence = False
        fence_char = None
        fence_len = 0
        start_idx = None
        body = []

        for i, l in enumerate(lines):
            m = re.match(r"^(\s{0,3})(`{3,}|~{3,})(.*)$", l)
            if not in_fence:
                if m:
                    in_fence = True
                    fence_char = m.group(2)[0]
                    fence_len = len(m.group(2))
                    start_idx = i
                    body = []
            else:
                if m and m.group(2)[0] == fence_char and len(m.group(2)) >= fence_len and not m.group(3).strip():
                    # Closing fence found
                    open_line = lines[start_idx]
                    open_match = re.match(r"^(\s{0,3})(`{3,}|~{3,})(.*)$", open_line)
                    lang = open_match.group(3).strip() if open_match else ""
                    if not lang:
                        inferred = self._infer_code_language(body)
                        fixed_open = f"{open_match.group(1)}{open_match.group(2)}{inferred}"
                        self.fixes.append(FixRecord(
                            line=start_idx + 1, code="E031", rule="InferCodeLanguage",
                            original=open_line, fixed=fixed_open,
                            description=f"Added language identifier '{inferred}' to bare code fence."
                        ))
                        lines[start_idx] = fixed_open
                    in_fence = False
                else:
                    body.append(l)

        return "\n".join(lines) + ("\n" if text.endswith("\n") else "")

    def _infer_code_language(self, body_lines):
        joined = "\n".join(body_lines)
        if re.search(r"\b(SELECT|FROM|WHERE|INSERT INTO|CREATE TABLE|ALTER TABLE|JOIN|GROUP BY|ORDER BY)\b", joined, re.I):
            return "sql"
        if re.search(r"\b(import |from \w+ import|def |class |print\(|elif )", joined):
            return "python"
        if re.search(r"^\s*[{[].*\"[\w-]+\"\s*:", joined):
            return "json"
        if re.search(r"\b(sudo |apt-get|npm |pnpm |pip |curl |Get-ChildItem|docker )", joined):
            return "bash"
        if re.search(r"^\s*<(!DOCTYPE|html|div|span|p|table)\b", joined, re.I):
            return "html"
        return "text"

    # ---- 11. FAQ Q&A structure
    def _fix_faq_structure(self, text):
        lines = text.splitlines()
        code_mask = _scan_fences(lines)
        in_faq = False

        for i, l in enumerate(lines):
            if code_mask[i]:
                continue
            if re.match(r"^##\s+.*(?:faq|frequently asked questions|questions)", l, re.I):
                in_faq = True
                continue
            elif re.match(r"^##\s+", l) and in_faq:
                in_faq = False
                continue

            if in_faq and l.startswith("### "):
                heading_content = l[4:].strip()
                # If question doesn't start with Q:
                if not heading_content.startswith("Q: "):
                    # If ends with '?' or starts with question word
                    is_question = heading_content.rstrip().endswith("?") or \
                                  re.match(r"^(How|What|Why|When|Where|Who|Which|Can|Does|Is|Are|Do|Should|Could|Will)\b", heading_content, re.I)
                    if is_question:
                        fixed_h = f"### Q: {heading_content}"
                        if not fixed_h.rstrip().endswith("?"):
                            fixed_h += "?"
                        self.fixes.append(FixRecord(
                            line=i + 1, code="E091", rule="NormalizeFaqQuestionHeading",
                            original=l, fixed=fixed_h,
                            description=f"Prepended 'Q: ' to FAQ question heading '{heading_content}'."
                        ))
                        lines[i] = fixed_h

                        # Find immediate answer paragraph
                        j = i + 1
                        while j < len(lines) and not lines[j].strip():
                            j += 1
                        if j < len(lines) and not lines[j].startswith("###") and not lines[j].startswith("##"):
                            ans_line = lines[j].strip()
                            if not ans_line.startswith("**A:**") and not ans_line.startswith("**A**:"):
                                if not (ans_line.startswith("|") or ans_line.startswith("```") or ans_line.startswith("!") or ans_line.startswith(">")):
                                    fixed_ans = f"**A:** {ans_line}"
                                    self.fixes.append(FixRecord(
                                        line=j + 1, code="E091", rule="PrependFaqAnswerPrefix",
                                        original=lines[j], fixed=fixed_ans,
                                        description="Prepended '**A:** ' to FAQ answer paragraph."
                                    ))
                                    lines[j] = fixed_ans

        return "\n".join(lines) + ("\n" if text.endswith("\n") else "")

    # ---- 12. Blank line padding around headings, tables, fences
    def _fix_blank_line_padding(self, text):
        lines = text.splitlines()
        code_mask = _scan_fences(lines)
        out = []

        for i, line in enumerate(lines):
            # Check heading padding
            if not code_mask[i] and re.match(r"^#{1,6}\s+\S", line):
                # Ensure blank line before heading (unless at file start or right after front matter)
                if out and out[-1].strip() != "" and not out[-1].strip().startswith("---"):
                    out.append("")
                    self.fixes.append(FixRecord(
                        line=i + 1, code="E075", rule="HeadingPrePadding",
                        original=line, fixed="\n" + line,
                        description=f"Injected blank line before heading '{line[:30]}'."
                    ))
                out.append(line)
                # Ensure blank line after heading
                if i + 1 < len(lines) and lines[i + 1].strip() != "" and not lines[i + 1].strip().startswith("#"):
                    out.append("")
                    self.fixes.append(FixRecord(
                        line=i + 1, code="E075", rule="HeadingPostPadding",
                        original=line, fixed=line + "\n",
                        description=f"Injected blank line after heading '{line[:30]}'."
                    ))
                continue

            out.append(line)

        return "\n".join(out) + ("\n" if text.endswith("\n") else "")


def fix_markdown(text, filename=""):
    """Auto-fix mechanical formatting flaws in markdown text.
    Returns: (fixed_text, list_of_fix_records)
    """
    fixer = MarkdownFixer(text, filename)
    return fixer.fix()


def fix_file(path, inplace=False):
    """Auto-fix a markdown file. If inplace is True, writes back to the file.
    Returns: (fixed_text, list_of_fix_records)
    """
    path = Path(path)
    text = path.read_text(encoding="utf-8")
    fixed_text, fixes = fix_markdown(text, path.name)
    if inplace and fixed_text != text:
        path.write_text(fixed_text, encoding="utf-8")
    return fixed_text, fixes
