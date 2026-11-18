"""Folder agent: inbox/ -> auto-fix -> verify -> verified/ or failed/ -> email report.

Run once:   python agent.py --once
Run always: python agent.py            (polls every POLL_SECONDS)
"""
import argparse
import html
import json
import os
import re
import shutil
import smtplib
import time
from dataclasses import asdict
from datetime import datetime
from email.message import EmailMessage
from pathlib import Path
from urllib.parse import unquote, urlsplit

import yaml

from fixer import fix_markdown
from verifier import Verifier, load_rules, to_text, verify_file

BASE = Path(__file__).resolve().parent


def load_dotenv(env_path=None):
    """Load key-value pairs from a .env file into os.environ if not already set."""
    env_file = Path(env_path) if env_path else BASE / ".env"
    if not env_file.is_file():
        return
    try:
        for line in env_file.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, val = line.split("=", 1)
            key, val = key.strip(), val.strip()
            if (val.startswith('"') and val.endswith('"')) or (val.startswith("'") and val.endswith("'")):
                val = val[1:-1]
            os.environ.setdefault(key, val)
    except OSError:
        pass


load_dotenv()

INBOX = Path(os.getenv("INBOX", BASE / "inbox"))
VERIFIED = Path(os.getenv("VERIFIED", BASE / "verified"))
FAILED = Path(os.getenv("FAILED", BASE / "failed"))
REPORTS = Path(os.getenv("REPORTS", BASE / "reports"))
POLL = int(os.getenv("POLL_SECONDS", "30"))
SETTLE = int(os.getenv("SETTLE_SECONDS", "5"))  # ignore files still being copied
ATTACH_MD_FILES = os.getenv("ATTACH_MD_FILES", "true").lower() in ("true", "1", "yes")

IMAGE_DEST = re.compile(r"!\[[^\]]*\]\((?:<(?P<bracket>[^>]+)>|(?P<plain>[^\s)]+))")

RULE_IMPACTS = {
    "E001": "Malformed YAML front-matter fails metadata parsing during document indexing.",
    "E011": "Missing required metadata field degrades search filterability.",
    "E012": "Front-matter field type mismatch prevents structured property querying.",
    "E013": "Invalid front-matter property value format.",
    "E015": "Duplicate metadata keys cause nondeterministic parser behavior.",
    "E016": "Extraneous H1 prefix causes semantic discrepancy with document metadata title.",
    "E020": "Missing overview section weakens top-level document summary context.",
    "E021": "Skipping heading level breaks hierarchical outline tree and parent-child chunk associations.",
    "E023": "Multiple H1 headings cause ambiguous document title boundary.",
    "E031": "Bare code fence without language tag breaks syntax highlighting and code AST chunking.",
    "E040": "Broken markdown table separator line corrupts tabular parsing.",
    "E041": "Mismatched table column count misaligns structured data cells.",
    "E042": "Missing blank line before table causes parser to conflate prose and table.",
    "E066": "Legacy document metadata line pollutes document body semantic search.",
    "E068": "Obsolete legacy section duplicates metadata and pollutes document body semantic search.",
    "E072": "Raw HTML tags degrade embedding fidelity and confuse markdown chunkers.",
    "E075": "Missing blank line padding causes markdown parser to coalesce distinct syntax blocks.",
    "E080": "Missing procedure goal degrades instruction retrieval accuracy.",
    "E081": "Non-standard step heading prevents procedural chunking and sequence indexing.",
    "E082": "Malformed video timestamp link breaks multimedia reference retrieval and player jump links.",
    "E083": "Timestamp seconds discrepancy disrupts precise video navigation.",
    "E091": "FAQ question or answer missing prefix prevents RAG Q&A chunker from identifying pairs.",
    "E093": "Invalid Mermaid diagram syntax fails visual diagram rendering.",
    "E094": "Flowchart diagram missing text description makes flowchart opaque to text embeddings.",
    "E095": "Callout box syntax error degrades contextual advisory extraction.",
}
DEFAULT_FIX_IMPACT = "Formatting flaw may disrupt RAG document parser and chunk boundary detection."


def _unique_path(path):
    """Return a path that will not overwrite an existing output file."""
    path = Path(path)
    if not path.exists():
        return path
    stamp = datetime.now().strftime("%Y%m%d%H%M%S%f")
    return path.with_name(f"{path.stem}_{stamp}{path.suffix}")


def _local_images(src):
    """Yield existing image files referenced by *src* and kept beside it."""
    try:
        text = src.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError):
        return
    root = src.parent.resolve()
    seen = set()
    for match in IMAGE_DEST.finditer(text):
        raw = (match.group("bracket") or match.group("plain") or "").strip()
        if not raw or raw.startswith("data:") or raw.startswith("#"):
            continue
        parsed = urlsplit(raw)
        if parsed.scheme or raw.startswith("//"):
            continue
        image = (src.parent / unquote(parsed.path)).resolve()
        try:
            image.relative_to(root)
        except ValueError:
            continue
        if image.is_file() and image not in seen:
            seen.add(image)
            yield image


def _rewrite_image_links(text, source_root, destination_root, replacements):
    """Update image destinations whose output asset had to be renamed."""
    def replace(match):
        group = "bracket" if match.group("bracket") is not None else "plain"
        raw = match.group(group).strip()
        parsed = urlsplit(raw)
        if parsed.scheme or raw.startswith("//"):
            return match.group(0)
        image = (source_root / unquote(parsed.path)).resolve()
        target = replacements.get(image)
        if target is None:
            return match.group(0)
        relative = target.relative_to(destination_root).as_posix()
        if parsed.query:
            relative += f"?{parsed.query}"
        if parsed.fragment:
            relative += f"#{parsed.fragment}"
        replacement = f"<{relative}>" if group == "bracket" else relative
        start, end = match.span(group)
        whole = match.group(0)
        start -= match.start()
        end -= match.start()
        return whole[:start] + replacement + whole[end:]

    return IMAGE_DEST.sub(replace, text)


def move(src, dst_dir):
    src = Path(src)
    dst_dir = Path(dst_dir)
    dst_dir.mkdir(parents=True, exist_ok=True)
    dst = _unique_path(dst_dir / src.name)
    # Copy local image assets before moving the Markdown file. This keeps
    # relative image links usable in verified/ and failed/.
    source_root = src.parent.resolve()
    replacements = {}
    for asset in _local_images(src):
        relative = asset.relative_to(source_root)
        target = dst_dir / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        if target.exists():
            if target.read_bytes() == asset.read_bytes():
                continue
            renamed = _unique_path(target)
            replacements[asset] = renamed
            target = renamed
        shutil.copy2(asset, target)
    rewritten = None
    if replacements:
        rewritten = _rewrite_image_links(
            src.read_text(encoding="utf-8"), source_root, dst_dir, replacements
        )
    shutil.move(str(src), dst)
    if rewritten is not None:
        dst.write_text(rewritten, encoding="utf-8")
    return dst


def _safe_sheet_title(name, existing_titles):
    """Return a valid, unique Excel sheet title (<= 31 chars, no forbidden chars)."""
    stem = Path(name).stem
    clean = re.sub(r'[\\/*?:\[\]]', '_', stem).strip()
    if not clean:
        clean = "Document"
    candidate = clean[:31]
    if candidate not in existing_titles:
        existing_titles.add(candidate)
        return candidate
    counter = 2
    while True:
        candidate = f"{clean[:26]} ({counter})"
        if candidate not in existing_titles:
            existing_titles.add(candidate)
            return candidate
        counter += 1


def to_detailed_text(r):
    """Format plain-text verification and auto-repair report for console and .report.txt."""
    fixed_cnt = r.get("fixed_count", 0)
    user_cnt = r.get("errors", 0)
    warn_cnt = r.get("warnings", 0)
    status_str = "PASSED" if r["passed"] else "FAILED"
    out = [f"{status_str}  {r['file']}  ({fixed_cnt} fixed by agent, {user_cnt} user fix required, {warn_cnt} warnings)"]

    fixes = r.get("fixes", [])
    if fixes:
        out.append("  [AGENT AUTO-REPAIRED]")
        for fix in fixes:
            out.append(f"    line {fix.line:>4}  [{fix.code}] {fix.description}")
            if len(fix.original) < 120 and "\n" not in fix.original:
                out.append(f"               original: {fix.original}")
                out.append(f"               fixed:    {fix.fixed}")

    user_issues = [i for i in r.get("combined_issues", []) if i.get("status") in ("USER FIX REQUIRED", "WARNING")]
    if user_issues:
        out.append("  [ACTION REQUIRED / WARNINGS]")
        for i in user_issues:
            out.append(f"    line {i['line']:>4}  [{i['severity']} {i['code']}] {i['message']}")
            if i.get("impact"):
                out.append(f"               impact: {i['impact']}")
            if i.get("fix"):
                out.append(f"               fix:    {i['fix']}")
    return "\n".join(out)


def generate_excel_report(results, report_dir, processed_at=None):
    """Generate a formatted Excel (.xlsx) report with a Summary sheet and separate sheets per document."""
    report_dir = Path(report_dir)
    report_dir.mkdir(parents=True, exist_ok=True)
    all_passed = all(r["passed"] for r in results)
    status_label = "PASSED" if all_passed else "ERROR"
    file_stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    display_time = processed_at or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if len(results) == 1:
        stem = Path(results[0]["file"]).stem
        filename = f"Verification_Report_{stem}_{status_label}.xlsx"
    else:
        filename = f"Verification_Report_{status_label}_{file_stamp}.xlsx"
    excel_path = _unique_path(report_dir / filename)

    try:
        import openpyxl
        from openpyxl.styles import Alignment, Border, Font, PatternFill, Side

        wb = openpyxl.Workbook()
        ws_summary = wb.active
        ws_summary.title = "Summary"

        header_fill = PatternFill(start_color="1F4E78", end_color="1F4E78", fill_type="solid")
        header_font = Font(name="Calibri", size=11, bold=True, color="FFFFFF")

        passed_fill = PatternFill(start_color="D4EDDA", end_color="D4EDDA", fill_type="solid")
        passed_font = Font(name="Calibri", size=11, color="155724", bold=True)

        failed_fill = PatternFill(start_color="F8D7DA", end_color="F8D7DA", fill_type="solid")
        failed_font = Font(name="Calibri", size=11, color="721C24", bold=True)

        warn_fill = PatternFill(start_color="FFF3CD", end_color="FFF3CD", fill_type="solid")
        warn_font = Font(name="Calibri", size=11, color="856404")

        neutral_font = Font(name="Calibri", size=11, color="495057")

        thin_border = Border(
            left=Side(style="thin", color="D0D7DE"),
            right=Side(style="thin", color="D0D7DE"),
            top=Side(style="thin", color="D0D7DE"),
            bottom=Side(style="thin", color="D0D7DE")
        )

        # 1. Summary sheet
        ws_summary.append([
            "Document Name",
            "Original Status (Pre-Fix)",
            "Final Status",
            "Fixed (Agent Fixed)",
            "Need Update (User Action)",
            "Warnings",
            "Total Detected",
            "Sheet Tab",
            "Processed At"
        ])
        existing_sheet_names = {"Summary"}
        doc_sheets = []

        for r in results:
            sheet_title = _safe_sheet_title(r["file"], existing_sheet_names)
            raw_status_str = r.get("raw_status_str", "UNKNOWN")
            raw_passed = r.get("raw_passed", False)
            fixed_cnt = r.get("fixed_count", 0)
            user_cnt = r.get("errors", 0)
            warn_cnt = r.get("warnings", 0)
            total_cnt = r.get("total_detected", fixed_cnt + user_cnt + warn_cnt)
            status_str = "PASSED" if r["passed"] else "FAILED"

            ws_summary.append([
                r["file"],
                raw_status_str,
                status_str,
                fixed_cnt,
                user_cnt,
                warn_cnt,
                total_cnt,
                sheet_title,
                display_time
            ])
            cur_row = ws_summary.max_row

            # Document name
            ws_summary.cell(row=cur_row, column=1).font = Font(name="Calibri", size=11, bold=True)

            # Original Status (Pre-Fix) cell
            orig_cell = ws_summary.cell(row=cur_row, column=2)
            orig_cell.alignment = Alignment(horizontal="center", vertical="center")
            if raw_passed:
                orig_cell.fill = passed_fill
                orig_cell.font = passed_font
            else:
                orig_cell.fill = failed_fill
                orig_cell.font = failed_font

            # Final Status cell
            status_cell = ws_summary.cell(row=cur_row, column=3)
            status_cell.alignment = Alignment(horizontal="center", vertical="center")
            if r["passed"]:
                status_cell.fill = passed_fill
                status_cell.font = passed_font
            else:
                status_cell.fill = failed_fill
                status_cell.font = failed_font

            # Fixed (Agent Fixed)
            fixed_cell = ws_summary.cell(row=cur_row, column=4)
            fixed_cell.alignment = Alignment(horizontal="center", vertical="center")
            if fixed_cnt > 0:
                fixed_cell.fill = passed_fill
                fixed_cell.font = passed_font
            else:
                fixed_cell.font = neutral_font

            # Need Update (User Action)
            user_cell = ws_summary.cell(row=cur_row, column=5)
            user_cell.alignment = Alignment(horizontal="center", vertical="center")
            if user_cnt > 0:
                user_cell.fill = failed_fill
                user_cell.font = failed_font
            else:
                user_cell.fill = passed_fill
                user_cell.font = passed_font

            # Warnings
            warn_cell = ws_summary.cell(row=cur_row, column=6)
            warn_cell.alignment = Alignment(horizontal="center", vertical="center")
            if warn_cnt > 0:
                warn_cell.fill = warn_fill
                warn_cell.font = warn_font
            else:
                warn_cell.font = neutral_font

            # Total & Sheet Tab & Timestamp
            for col_idx in (7, 8, 9):
                c = ws_summary.cell(row=cur_row, column=col_idx)
                c.alignment = Alignment(horizontal="center", vertical="center")
                c.font = neutral_font

            doc_sheets.append((r, sheet_title))

        # 2. Individual sheets per document (named by the file)
        all_sheets = [ws_summary]
        for r, sheet_title in doc_sheets:
            ws_doc = wb.create_sheet(title=sheet_title)
            all_sheets.append(ws_doc)
            ws_doc.append([
                "Line",
                "Category / Action Status",
                "Severity",
                "Rule Code",
                "Problem Description",
                "Impact if Uploaded to RAG",
                "Resolution / Action Required"
            ])

            combined = r.get("combined_issues", [])
            if combined:
                for item in combined:
                    ws_doc.append([
                        item.get("line", 1),
                        item.get("status", "USER FIX REQUIRED"),
                        item.get("severity", "ERROR"),
                        item.get("code", ""),
                        item.get("message", ""),
                        item.get("impact", ""),
                        item.get("fix", "")
                    ])
                    cur_row = ws_doc.max_row
                    line_cell = ws_doc.cell(row=cur_row, column=1)
                    status_cell = ws_doc.cell(row=cur_row, column=2)
                    sev_cell = ws_doc.cell(row=cur_row, column=3)
                    code_cell = ws_doc.cell(row=cur_row, column=4)

                    line_cell.alignment = Alignment(horizontal="center", vertical="center")
                    status_cell.alignment = Alignment(horizontal="center", vertical="center")
                    sev_cell.alignment = Alignment(horizontal="center", vertical="center")
                    code_cell.alignment = Alignment(horizontal="center", vertical="center")

                    st = item.get("status", "")
                    if st == "AGENT FIXED":
                        status_cell.fill = passed_fill
                        status_cell.font = passed_font
                        sev_cell.fill = passed_fill
                        sev_cell.font = passed_font
                    elif st == "USER FIX REQUIRED":
                        status_cell.fill = failed_fill
                        status_cell.font = failed_font
                        sev_cell.fill = failed_fill
                        sev_cell.font = failed_font
                    elif st == "WARNING":
                        status_cell.fill = warn_fill
                        status_cell.font = warn_font
                        sev_cell.fill = warn_fill
                        sev_cell.font = warn_font
            else:
                ws_doc.append([
                    "-",
                    "PASSED",
                    "INFO",
                    "-",
                    "All checks passed successfully. Conforms to the master template.",
                    "Safe to ingest into RAG.",
                    "None required."
                ])
                cur_row = ws_doc.max_row
                status_cell = ws_doc.cell(row=cur_row, column=2)
                status_cell.fill = passed_fill
                status_cell.font = passed_font
                for col_idx in (1, 2, 3, 4):
                    ws_doc.cell(row=cur_row, column=col_idx).alignment = Alignment(horizontal="center", vertical="center")

        # 3. Format, auto-size and borders for all sheets
        for ws in all_sheets:
            for cell in ws[1]:
                cell.fill = header_fill
                cell.font = header_font
                cell.alignment = Alignment(horizontal="center", vertical="center")
            ws.freeze_panes = "A2"
            ws.auto_filter.ref = ws.dimensions
            is_summary = (ws == ws_summary)

            for row in ws.iter_rows(min_row=1, max_row=ws.max_row, min_col=1, max_col=ws.max_column):
                for cell in row:
                    cell.border = thin_border

            for col in ws.columns:
                col_letter = col[0].column_letter
                max_len = max(len(str(c.value or "")) for c in col)
                if is_summary and col_letter == "B":
                    ws.column_dimensions[col_letter].width = 38
                elif not is_summary and col_letter in ("E", "F", "G"):
                    ws.column_dimensions[col_letter].width = min(max(max_len + 3, 25), 65)
                    for c in col[1:]:
                        c.alignment = Alignment(wrap_text=True, vertical="top")
                elif not is_summary and col_letter == "B":
                    ws.column_dimensions[col_letter].width = 24
                else:
                    ws.column_dimensions[col_letter].width = min(max(max_len + 4, 12), 45)

        wb.save(excel_path)
        return excel_path
    except Exception as e:
        # Fallback to CSV if openpyxl fails
        csv_path = excel_path.with_suffix(".csv")
        import csv
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["Document", "Line", "Category / Action Status", "Severity", "Rule Code", "Problem Description", "Impact if Uploaded", "Resolution / Fix"])
            for r in results:
                for i in r.get("combined_issues", []):
                    writer.writerow([r["file"], i.get("line", 1), i.get("status", ""), i.get("severity", ""),
                                     i.get("code", ""), i.get("message", ""), i.get("impact", ""), i.get("fix", "")])
        return csv_path


def render_html(results, excel_filename=None, processed_at=None, attached_md_files=None):
    """Render an HTML email body with metric cards, summary table, and attachment links."""
    p = sum(r["passed"] for r in results)
    total_files = len(results)
    all_passed = p == total_files
    total_fixed = sum(r.get("fixed_count", 0) for r in results)
    total_user_fix = sum(r.get("errors", 0) for r in results)

    accent = "#1a7f37" if all_passed else "#cf222e"
    status_label = "PASSED" if all_passed else "ACTION REQUIRED"
    display_time = processed_at or datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    rows = [
        "<div style='font-family:-apple-system,BlinkMacSystemFont,Segoe UI,Helvetica,Arial,sans-serif;max-width:920px;margin:auto;'>",
        f"<div style='background:{accent};color:#ffffff;padding:18px 22px;border-radius:6px 6px 0 0;'>",
        f"<h2 style='margin:0;font-size:20px;'>[MarkShield RAG Quality Gate] {status_label}: {p} of {total_files} documents ready</h2>",
        f"<div style='font-size:12px;opacity:0.95;margin-top:4px;'>Batch processed at: {display_time}</div>",
        "</div>",
        "<div style='border:1px solid #d0d7de;border-top:none;padding:22px 24px;border-radius:0 0 6px 6px;background:#fafbfc;'>",
    ]

    # Metric Cards
    rows.append("<div style='display:flex;gap:12px;margin-bottom:22px;flex-wrap:wrap;'>")
    # Card 1: Total Files
    rows.append(
        "<div style='flex:1;min-width:140px;background:#ffffff;border:1px solid #d0d7de;border-radius:6px;padding:12px 14px;text-align:center;'>"
        "<div style='font-size:11px;color:#57606a;text-transform:uppercase;font-weight:600;'>Total Documents</div>"
        f"<div style='font-size:22px;font-weight:bold;color:#24292f;margin-top:4px;'>{total_files}</div>"
        "</div>"
    )
    # Card 2: Auto-Fixed by Agent
    rows.append(
        "<div style='flex:1;min-width:140px;background:#ffffff;border:1px solid #d0d7de;border-top:3px solid #1a7f37;border-radius:6px;padding:12px 14px;text-align:center;'>"
        "<div style='font-size:11px;color:#1a7f37;text-transform:uppercase;font-weight:600;'>Agent Auto-Fixed</div>"
        f"<div style='font-size:22px;font-weight:bold;color:#1a7f37;margin-top:4px;'>{total_fixed}</div>"
        "</div>"
    )
    # Card 3: User Action Required
    user_color = "#cf222e" if total_user_fix > 0 else "#1a7f37"
    rows.append(
        f"<div style='flex:1;min-width:140px;background:#ffffff;border:1px solid #d0d7de;border-top:3px solid {user_color};border-radius:6px;padding:12px 14px;text-align:center;'>"
        f"<div style='font-size:11px;color:{user_color};text-transform:uppercase;font-weight:600;'>User Action Needed</div>"
        f"<div style='font-size:22px;font-weight:bold;color:{user_color};margin-top:4px;'>{total_user_fix}</div>"
        "</div>"
    )
    # Card 4: Ready for RAG
    rows.append(
        "<div style='flex:1;min-width:140px;background:#ffffff;border:1px solid #d0d7de;border-top:3px solid #0969da;border-radius:6px;padding:12px 14px;text-align:center;'>"
        "<div style='font-size:11px;color:#0969da;text-transform:uppercase;font-weight:600;'>Ready for RAG</div>"
        f"<div style='font-size:22px;font-weight:bold;color:#0969da;margin-top:4px;'>{p} / {total_files}</div>"
        "</div>"
    )
    rows.append("</div>")

    # Summary Table
    rows.append("<h3 style='margin-top:0;font-size:15px;color:#24292f;'>Document Processing Summary</h3>")
    rows.append("<table border='1' cellpadding='8' cellspacing='0' style='border-collapse:collapse;width:100%;font-size:13px;background:#ffffff;border-color:#d0d7de;'>")
    rows.append(
        "<tr style='background:#f6f8fa;color:#24292f;text-align:left;'>"
        "<th>Document Name</th>"
        "<th style='text-align:center;'>Original Status (Pre-Fix)</th>"
        "<th style='text-align:center;'>Final Status</th>"
        "<th style='text-align:center;'>Fixed (Agent Fixed)</th>"
        "<th style='text-align:center;'>Need Update (User)</th>"
        "<th style='text-align:center;'>Warnings</th>"
        "<th style='text-align:center;'>Processed At</th>"
        "</tr>"
    )
    for r in results:
        raw_passed = r.get("raw_passed", False)
        orig_color = "#1a7f37" if raw_passed else "#cf222e"
        orig_bg = "#d4edda" if raw_passed else "#f8d7da"
        orig_text = html.escape(r.get("raw_status_str", "UNKNOWN"))

        res_color = "#1a7f37" if r["passed"] else "#cf222e"
        res_bg = "#d4edda" if r["passed"] else "#f8d7da"
        res_text = "PASSED" if r["passed"] else "FAILED"
        fixed_cnt = r.get("fixed_count", 0)
        user_cnt = r.get("errors", 0)
        warn_cnt = r.get("warnings", 0)

        fixed_badge = f"<span style='color:#155724;font-weight:bold;'>{fixed_cnt}</span>" if fixed_cnt > 0 else "<span style='color:#8c959f;'>0</span>"
        user_badge = f"<span style='color:#721C24;font-weight:bold;'>{user_cnt}</span>" if user_cnt > 0 else "<span style='color:#155724;'>0</span>"
        warn_badge = f"<span style='color:#856404;font-weight:bold;'>{warn_cnt}</span>" if warn_cnt > 0 else "<span style='color:#8c959f;'>0</span>"

        rows.append(
            f"<tr>"
            f"<td><b>{html.escape(r['file'])}</b></td>"
            f"<td style='text-align:center;background:{orig_bg};color:{orig_color};font-weight:bold;'>{orig_text}</td>"
            f"<td style='text-align:center;background:{res_bg};color:{res_color};font-weight:bold;'>{res_text}</td>"
            f"<td style='text-align:center;'>{fixed_badge}</td>"
            f"<td style='text-align:center;'>{user_badge}</td>"
            f"<td style='text-align:center;'>{warn_badge}</td>"
            f"<td style='text-align:center;color:#57606a;'>{display_time}</td>"
            f"</tr>"
        )
    rows.append("</table>")

    # Callout boxes
    if excel_filename:
        rows.append(
            f"<div style='background:#eef6fc;border-left:4px solid #0969da;padding:12px 16px;margin:20px 0 10px 0;border-radius:3px;'>"
            f"<strong>&#128206; Excel Workbook Attached:</strong> <code style='background:#ffffff;padding:2px 6px;border-radius:3px;'>{html.escape(excel_filename)}</code><br>"
            f"<span style='font-size:13px;color:#57606a;'>Contains the <b>Summary</b> tab plus a <b>dedicated sheet tab for each document</b> detailing categorized issues (<code>AGENT FIXED</code> vs <code>USER FIX REQUIRED</code>), line numbers, rule codes, RAG impacts, and resolutions.</span>"
            f"</div>"
        )

    if attached_md_files:
        file_list = ", ".join(f"<code>{html.escape(f)}</code>" for f in attached_md_files)
        rows.append(
            f"<div style='background:#f0fff4;border-left:4px solid #2da44e;padding:12px 16px;margin:10px 0;border-radius:3px;'>"
            f"<strong>&#128196; Markdown Files Attached ({len(attached_md_files)}):</strong><br>"
            f"<span style='font-size:13px;color:#24292f;'>{file_list}</span><br>"
            f"<span style='font-size:12px;color:#57606a;'>These files include all automatic repairs applied by the agent and are attached for direct inspection or RAG ingestion.</span>"
            f"</div>"
        )

    rows.append("</div></div>")
    return "\n".join(rows)


def send_email(results, attachment_path=None, processed_at=None, attach_md=True, md_paths=None):
    """Dispatch email report with Excel report and optionally all processed .md files attached."""
    host, to = os.getenv("SMTP_HOST"), os.getenv("MAIL_TO")
    if not (host and to):
        print("SMTP_HOST / MAIL_TO not set - skipping email (report saved in reports/).")
        return
    recipients = [x.strip() for x in re.split(r"[,;]", to) if x.strip()]
    if not recipients:
        print("MAIL_TO is empty - skipping email (report saved in reports/).")
        return

    all_passed = all(r["passed"] for r in results)
    status_label = "PASSED" if all_passed else "ACTION REQUIRED"
    display_time = processed_at or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    total_fixed = sum(r.get("fixed_count", 0) for r in results)
    total_user_fix = sum(r.get("errors", 0) for r in results)

    if len(results) == 1:
        r0 = results[0]
        if r0["passed"]:
            if total_fixed > 0:
                subject = f"[MarkShield] PASSED (Auto-Repaired): {r0['file']} ({total_fixed} fixed)"
            else:
                subject = f"[MarkShield] PASSED: {r0['file']}"
        else:
            subject = f"[MarkShield] ACTION REQUIRED: {r0['file']} ({r0['errors']} errors need user update, {total_fixed} auto-fixed)"
    else:
        p = sum(r["passed"] for r in results)
        if all_passed:
            subject = f"[MarkShield] PASSED: {p}/{len(results)} ready for RAG ({total_fixed} auto-fixed)"
        else:
            subject = f"[MarkShield] ACTION REQUIRED: {p}/{len(results)} passed ({total_fixed} auto-fixed, {total_user_fix} need user update)"

    excel_name = attachment_path.name if attachment_path else None
    attached_md_names = [Path(p).name for p in md_paths if Path(p).is_file()] if (attach_md and md_paths) else []

    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = os.getenv("MAIL_FROM", os.getenv("SMTP_USER", "md-verifier@localhost"))
    msg["To"] = ", ".join(recipients)

    cc = os.getenv("MAIL_CC")
    cc_recipients = [x.strip() for x in re.split(r"[,;]", cc) if x.strip()] if cc else []
    if cc_recipients:
        msg["Cc"] = ", ".join(cc_recipients)

    bcc = os.getenv("MAIL_BCC")
    bcc_recipients = [x.strip() for x in re.split(r"[,;]", bcc) if x.strip()] if bcc else []
    if bcc_recipients:
        msg["Bcc"] = ", ".join(bcc_recipients)

    text_lines = [
        f"MarkShield RAG Quality Gate Report: {status_label}",
        f"Processed at: {display_time}",
        f"Files processed: {len(results)} | Passed: {sum(r['passed'] for r in results)} | Failed: {sum(not r['passed'] for r in results)}",
        f"Agent Auto-Fixed: {total_fixed} | User Action Required: {total_user_fix}",
        ""
    ]
    for r in results:
        fixed_cnt = r.get("fixed_count", 0)
        user_cnt = r.get("errors", 0)
        warn_cnt = r.get("warnings", 0)
        res_str = f"PASSED ({fixed_cnt} auto-fixed)" if r["passed"] else f"FAILED ({user_cnt} errors need user update, {fixed_cnt} auto-fixed, {warn_cnt} warnings)"
        text_lines.append(f" - {r['file']}: {res_str}")

    if excel_name:
        text_lines.append("")
        text_lines.append(f"Detailed Excel workbook attached: {excel_name}")
        text_lines.append("Open the attached workbook to view Sheet 1 Summary and dedicated sheet tabs per document.")

    if attached_md_names:
        text_lines.append("")
        text_lines.append(f"Processed Markdown files attached ({len(attached_md_names)} files):")
        for mdn in attached_md_names:
            text_lines.append(f" - {mdn}")

    msg.set_content("\n".join(text_lines))
    msg.add_alternative(render_html(results, excel_name, display_time, attached_md_names), subtype="html")

    # Attach Excel workbook
    if attachment_path and Path(attachment_path).is_file():
        path_obj = Path(attachment_path)
        content_type = "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet" if path_obj.suffix == ".xlsx" else "text/csv"
        maintype, subtype = content_type.split("/", 1)
        msg.add_attachment(
            path_obj.read_bytes(),
            maintype=maintype,
            subtype=subtype,
            filename=path_obj.name
        )

    # Attach Markdown files if enabled
    if attach_md and md_paths:
        for mdp in md_paths:
            p = Path(mdp)
            if p.is_file():
                msg.add_attachment(
                    p.read_bytes(),
                    maintype="text",
                    subtype="markdown",
                    filename=p.name
                )

    security = os.getenv("SMTP_SECURITY", "starttls").lower()
    port = int(os.getenv("SMTP_PORT", "465" if security == "ssl" else "587"))
    timeout = float(os.getenv("SMTP_TIMEOUT", "30"))
    client = smtplib.SMTP_SSL if security == "ssl" else smtplib.SMTP
    with client(host, port, timeout=timeout) as s:
        if security in {"starttls", "tls"}:
            s.starttls()
        if os.getenv("SMTP_USER"):
            s.login(os.getenv("SMTP_USER"), os.getenv("SMTP_PASS", ""))
        s.send_message(msg)


def run_batch(cfg, inbox=None, verified=None, failed=None, reports=None, settle=None, attach_md=None):
    """Process a batch of incoming markdown files: auto-fix -> verify -> route -> report -> email."""
    inbox = Path(inbox or INBOX)
    verified = Path(verified or VERIFIED)
    failed = Path(failed or FAILED)
    reports = Path(reports or REPORTS)
    settle = SETTLE if settle is None else settle
    if attach_md is None:
        attach_md = os.getenv("ATTACH_MD_FILES", "true").lower() in ("true", "1", "yes")

    now = time.time()
    files = []
    for f in sorted(inbox.glob("*.md")):
        try:
            if f.is_file() and now - f.stat().st_mtime > settle:
                files.append(f)
        except OSError as e:
            print(f"Cannot inspect {f}: {e}")
    if not files:
        return 0

    results = []
    processed_md_paths = []

    for f in files:
        # 1. Read raw text
        try:
            raw_text = f.read_text(encoding="utf-8")
        except Exception as e:
            r = {
                "file": f.name,
                "path": str(f.resolve()),
                "passed": False,
                "errors": 1,
                "warnings": 0,
                "fixed_count": 0,
                "total_detected": 1,
                "raw_passed": False,
                "raw_errors_count": 1,
                "raw_codes": ["E001"],
                "raw_status_str": "FAILED (1 error: E001)",
                "fixes": [],
                "issues": [],
                "combined_issues": [{
                    "line": 1,
                    "status": "USER FIX REQUIRED",
                    "severity": "ERROR",
                    "code": "E001",
                    "message": f"Could not read file as UTF-8: {e}",
                    "impact": "Unreadable file cannot be parsed or indexed into RAG.",
                    "fix": "Ensure file is valid UTF-8 encoded text.",
                }],
            }
            dest = move(f, failed)
            r["destination"] = dest
            processed_md_paths.append(dest)
            results.append(r)
            continue

        # 1b. Inspect raw pre-fix verification status
        try:
            v_raw = Verifier(cfg, f.parent)
            raw_issues = v_raw.run(raw_text)
            raw_errors = [i for i in raw_issues if i.severity == "error"]
            raw_passed = (len(raw_errors) == 0)
            raw_codes = sorted(list({i.code for i in raw_errors}))
        except Exception:
            raw_passed = False
            raw_errors = [1]
            raw_codes = ["E001"]

        if raw_passed:
            raw_status_str = "PASSED (Clean)"
        else:
            codes_str = ", ".join(raw_codes[:4]) + ("..." if len(raw_codes) > 4 else "")
            raw_status_str = f"FAILED ({len(raw_errors)} errors: {codes_str})"

        # 2. Autonomous Auto-Fixer: Heal mechanical formatting flaws
        fixed_text, fixes = fix_markdown(raw_text, f.name)
        if fixed_text != raw_text:
            try:
                f.write_text(fixed_text, encoding="utf-8")
            except OSError as e:
                print(f"Warning: Could not save auto-fixes to {f}: {e}")

        # 3. Verify the fixed file with Verifier
        r = verify_file(f, cfg)

        # 4. Separate fixes, errors, and warnings for clear reporting
        fixed_issues = []
        for fix in fixes:
            impact_desc = RULE_IMPACTS.get(fix.code, DEFAULT_FIX_IMPACT)
            orig_repr = repr(fix.original) if len(fix.original) < 60 else repr(fix.original[:57] + "...")
            fixed_repr = repr(fix.fixed) if len(fix.fixed) < 60 else repr(fix.fixed[:57] + "...")
            fixed_issues.append({
                "line": fix.line,
                "status": "AGENT FIXED",
                "severity": "FIXED",
                "code": fix.code,
                "message": f"{fix.description} (Original: {orig_repr})",
                "impact": impact_desc,
                "fix": f"Auto-repaired by Agent. Changed to: {fixed_repr}",
                "original": fix.original,
                "fixed": fix.fixed,
            })

        user_issues = []
        for issue in r.get("issues", []):
            is_err = (issue.get("severity") == "error")
            user_issues.append({
                "line": issue.get("line", 1),
                "status": "USER FIX REQUIRED" if is_err else "WARNING",
                "severity": issue.get("severity", "error").upper(),
                "code": issue.get("code", ""),
                "message": issue.get("message", ""),
                "impact": issue.get("impact", ""),
                "fix": issue.get("fix", ""),
            })

        def _sort_key(item):
            line = item.get("line", 1)
            try:
                return (int(line), 0 if item.get("status") == "AGENT FIXED" else 1)
            except (ValueError, TypeError):
                return (999999, 1)

        combined_issues = sorted(fixed_issues + user_issues, key=_sort_key)

        r["fixed_count"] = len(fixes)
        r["fixes"] = fixes
        r["total_detected"] = len(fixes) + r["errors"] + r["warnings"]
        r["combined_issues"] = combined_issues
        r["raw_passed"] = raw_passed
        r["raw_errors_count"] = len(raw_errors)
        r["raw_codes"] = raw_codes
        r["raw_status_str"] = raw_status_str

        # 5. Route file to verified/ or failed/
        try:
            dest = move(f, verified if r["passed"] else failed)
            r["destination"] = dest
            processed_md_paths.append(dest)
        except OSError as e:
            r["passed"] = False
            r["errors"] += 1
            r["combined_issues"].append({
                "line": 1,
                "status": "USER FIX REQUIRED",
                "code": "E002",
                "severity": "ERROR",
                "message": f"Could not move document to output folder: {e}",
                "impact": "Verification result was not delivered to expected folder.",
                "fix": "Resolve folder or file permissions and run again.",
            })
            dest = f
            r["destination"] = dest
            processed_md_paths.append(dest)

        # If document has remaining user errors, write .report.txt beside it in failed/
        if not r["passed"]:
            failed.mkdir(parents=True, exist_ok=True)
            report_path = _unique_path(failed / f"{dest.stem}.report.txt")
            report_path.write_text(to_detailed_text(r), encoding="utf-8")

        print(to_detailed_text(r))
        results.append(r)

    # 6. Reporting and Emailing at the end of the batch
    reports.mkdir(parents=True, exist_ok=True)
    stamp_file = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    display_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    # Save JSON report
    json_results = []
    for r in results:
        jr = dict(r)
        jr["destination"] = str(jr.get("destination", ""))
        jr["fixes"] = [asdict(fx) for fx in jr.get("fixes", [])]
        json_results.append(jr)
    (reports / f"report_{stamp_file}.json").write_text(json.dumps(json_results, indent=2), encoding="utf-8")

    # Save Excel report
    excel_path = generate_excel_report(results, reports, display_time)

    # Save HTML report
    attached_md_names = [Path(p).name for p in processed_md_paths] if attach_md else []
    (reports / f"report_{stamp_file}.html").write_text(
        render_html(results, excel_path.name, display_time, attached_md_names), encoding="utf-8"
    )

    # Dispatch email notification
    try:
        send_email(
            results,
            attachment_path=excel_path,
            processed_at=display_time,
            attach_md=attach_md,
            md_paths=processed_md_paths
        )
        print(f"Email sent successfully with Excel report ({excel_path.name})"
              + (f" and {len(attached_md_names)} MD files." if attach_md else " (MD files attachment disabled)."))
    except Exception as e:
        print(f"Email failed: {e}")

    return len(files)


def test_email():
    """Send a diagnostic test email to verify SMTP configuration and attachments."""
    host = os.getenv("SMTP_HOST")
    to = os.getenv("MAIL_TO")
    user = os.getenv("SMTP_USER")
    security = os.getenv("SMTP_SECURITY", "starttls")
    port = os.getenv("SMTP_PORT", "465" if security == "ssl" else "587")
    if not (host and to):
        print("ERROR: SMTP_HOST and MAIL_TO must be configured in .env or environment.")
        return 1
    cc = os.getenv("MAIL_CC")
    bcc = os.getenv("MAIL_BCC")
    print(f"Connecting to SMTP server: {host}:{port} (security={security}, user={user or 'none'})...")
    print(f"To:  {to}")
    if cc:
        print(f"Cc:  {cc}")
    if bcc:
        print(f"Bcc: {bcc}")

    mock_results = [{
        "file": "test_connection.md",
        "raw_passed": False,
        "raw_status_str": "FAILED (1 error: E072)",
        "passed": True,
        "errors": 0,
        "warnings": 0,
        "fixed_count": 1,
        "total_detected": 1,
        "fixes": [],
        "issues": [],
        "combined_issues": [{
            "line": 1,
            "status": "AGENT FIXED",
            "severity": "FIXED",
            "code": "E072",
            "message": "Auto-converted raw <u> tag to markdown bold.",
            "impact": "Raw HTML tags degrade embedding fidelity and confuse markdown chunkers.",
            "fix": "Auto-repaired by Agent. Changed to: '**Text**'",
        }]
    }]
    try:
        display_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        test_excel = generate_excel_report(mock_results, REPORTS, display_time)
        send_email(mock_results, test_excel, display_time, attach_md=False)
        print(f"SUCCESS: Test email with attachment ({test_excel.name}) sent successfully to: {to}")
        return 0
    except Exception as e:
        print(f"ERROR: SMTP delivery failed: {type(e).__name__}: {e}")
        return 1


def main(argv=None):
    ap = argparse.ArgumentParser(description="MarkShield Folder Agent: Auto-fix, verify, route, and report.")
    ap.add_argument("--once", action="store_true", help="Process pending files in inbox once and exit")
    ap.add_argument("--test-email", action="store_true", help="Send a test report email to verify SMTP credentials and exit")
    ap.add_argument("--attach-md", dest="attach_md", action="store_true", default=None,
                    help="Attach processed Markdown files to the notification email")
    ap.add_argument("--no-attach-md", dest="attach_md", action="store_false",
                    help="Do not attach Markdown files to the notification email")
    ap.add_argument("--env", default=None, help="Path to custom .env file")
    ap.add_argument("--rules", default=str(BASE / "rules.yaml"))
    ap.add_argument("--inbox", default=str(INBOX))
    ap.add_argument("--verified", default=str(VERIFIED))
    ap.add_argument("--failed", default=str(FAILED))
    ap.add_argument("--reports", default=str(REPORTS))
    ap.add_argument("--poll", type=int, default=POLL, help="Polling interval in seconds")
    ap.add_argument("--settle", type=int, default=SETTLE,
                    help="Ignore files modified within this many seconds")
    a = ap.parse_args(argv)

    if a.env:
        load_dotenv(a.env)

    if a.test_email:
        return test_email()
    try:
        cfg = load_rules(a.rules)
    except (OSError, KeyError, ValueError, yaml.YAMLError) as e:
        ap.error(str(e))

    inbox = Path(a.inbox)
    verified = Path(a.verified)
    failed = Path(a.failed)
    reports = Path(a.reports)
    inbox.mkdir(parents=True, exist_ok=True)

    if a.once:
        run_batch(cfg, inbox, verified, failed, reports, a.settle, attach_md=a.attach_md)
        return 0

    print(f"Watching {inbox} every {a.poll}s ...")
    try:
        while True:
            run_batch(cfg, inbox, verified, failed, reports, a.settle, attach_md=a.attach_md)
            time.sleep(a.poll)
    except KeyboardInterrupt:
        print("Stopped.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
