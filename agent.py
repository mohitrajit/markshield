"""Folder agent: inbox/ -> verify -> verified/ or failed/ -> email report.

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
from datetime import datetime
from email.message import EmailMessage
from pathlib import Path
from urllib.parse import unquote, urlsplit

import yaml

from verifier import load_rules, to_text, verify_file

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

IMAGE_DEST = re.compile(r"!\[[^\]]*\]\((?:<(?P<bracket>[^>]+)>|(?P<plain>[^\s)]+))")


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
        from openpyxl.styles import Alignment, Font, PatternFill

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

        # 1. Summary sheet
        ws_summary.append(["Document Name", "Status", "Errors", "Warnings", "Sheet Tab", "Processed At"])
        existing_sheet_names = {"Summary"}
        doc_sheets = []

        for r in results:
            sheet_title = _safe_sheet_title(r["file"], existing_sheet_names)
            ws_summary.append([
                r["file"],
                "PASSED" if r["passed"] else "FAILED",
                r["errors"],
                r["warnings"],
                sheet_title,
                display_time
            ])
            status_cell = ws_summary.cell(row=ws_summary.max_row, column=2)
            if r["passed"]:
                status_cell.fill = passed_fill
                status_cell.font = passed_font
            else:
                status_cell.fill = failed_fill
                status_cell.font = failed_font
            doc_sheets.append((r, sheet_title))

        # 2. Individual sheets per document (named by the file)
        all_sheets = [ws_summary]
        for r, sheet_title in doc_sheets:
            ws_doc = wb.create_sheet(title=sheet_title)
            all_sheets.append(ws_doc)
            ws_doc.append(["Line", "Severity", "Rule Code", "Problem Description", "Impact if Uploaded to RAG", "Recommended Fix"])
            issues = r.get("issues", [])
            if issues:
                for i in issues:
                    ws_doc.append([
                        i.get("line", 1),
                        i.get("severity", "error").upper(),
                        i.get("code", ""),
                        i.get("message", ""),
                        i.get("impact", ""),
                        i.get("fix", "")
                    ])
                    sev_cell = ws_doc.cell(row=ws_doc.max_row, column=2)
                    if i.get("severity") == "warning":
                        sev_cell.fill = warn_fill
                        sev_cell.font = warn_font
                    else:
                        sev_cell.fill = failed_fill
                        sev_cell.font = failed_font
            else:
                ws_doc.append(["-", "PASSED", "-", "All checks passed successfully. Conforms to the master template.", "Safe to ingest into RAG.", "None required."])
                passed_cell = ws_doc.cell(row=ws_doc.max_row, column=2)
                passed_cell.fill = passed_fill
                passed_cell.font = passed_font

        # 3. Format and auto-size all sheets
        for ws in all_sheets:
            for cell in ws[1]:
                cell.fill = header_fill
                cell.font = header_font
                cell.alignment = Alignment(horizontal="center", vertical="center")
            ws.freeze_panes = "A2"
            ws.auto_filter.ref = ws.dimensions
            is_summary = (ws == ws_summary)
            for col in ws.columns:
                col_letter = col[0].column_letter
                max_len = max(len(str(c.value or "")) for c in col)
                if not is_summary and col_letter in ("D", "E", "F"):
                    ws.column_dimensions[col_letter].width = min(max(max_len + 3, 25), 65)
                    for c in col[1:]:
                        c.alignment = Alignment(wrap_text=True, vertical="top")
                else:
                    ws.column_dimensions[col_letter].width = min(max(max_len + 4, 12), 40)
                    for c in col[1:]:
                        c.alignment = Alignment(vertical="top")

        wb.save(excel_path)
        return excel_path
    except Exception as e:
        # Fallback to CSV if openpyxl fails
        csv_path = excel_path.with_suffix(".csv")
        import csv
        with open(csv_path, "w", newline="", encoding="utf-8") as f:
            writer = csv.writer(f)
            writer.writerow(["Document", "Line", "Severity", "Rule Code", "Problem Description", "Impact if Uploaded", "Recommended Fix"])
            for r in results:
                for i in r.get("issues", []):
                    writer.writerow([r["file"], i.get("line", 1), i.get("severity", ""), i.get("code", ""),
                                     i.get("message", ""), i.get("impact", ""), i.get("fix", "")])
        return csv_path


def render_html(results, excel_filename=None, processed_at=None):
    p = sum(r["passed"] for r in results)
    total_files = len(results)
    all_passed = p == total_files
    accent = "#1a7f37" if all_passed else "#cf222e"
    status_label = "PASSED" if all_passed else "ERROR"
    display_time = processed_at or datetime.now().strftime("%Y-%m-%d %H:%M:%S")

    rows = [
        "<div style='font-family:-apple-system,BlinkMacSystemFont,Segoe UI,Helvetica,Arial,sans-serif;max-width:850px;margin:auto;'>",
        f"<div style='background:{accent};color:#ffffff;padding:16px 20px;border-radius:6px 6px 0 0;'>",
        f"<h2 style='margin:0;font-size:20px;'>[MD Verification] {status_label}: {p} of {total_files} passed</h2>",
        f"<div style='font-size:12px;opacity:0.95;margin-top:4px;'>Processed at: {display_time}</div>",
        "</div>",
        "<div style='border:1px solid #d0d7de;border-top:none;padding:20px;border-radius:0 0 6px 6px;background:#fafbfc;'>",
    ]

    rows.append("<h3 style='margin-top:0;'>Document Status Summary</h3>")
    rows.append("<table border='1' cellpadding='7' cellspacing='0' style='border-collapse:collapse;width:100%;font-size:13px;background:#ffffff;border-color:#d0d7de;'>")
    rows.append("<tr style='background:#f6f8fa;'><th>Document Name</th><th>Result</th><th>Errors</th><th>Warnings</th><th>Processed At</th></tr>")
    for r in results:
        res_color = "#1a7f37" if r["passed"] else "#cf222e"
        res_text = "PASSED" if r["passed"] else "FAILED"
        rows.append(f"<tr><td><b>{html.escape(r['file'])}</b></td><td style='color:{res_color};font-weight:bold;'>{res_text}</td>"
                    f"<td>{r['errors']}</td><td>{r['warnings']}</td><td>{display_time}</td></tr>")
    rows.append("</table>")

    if excel_filename:
        rows.append(
            f"<div style='background:#eef6fc;border-left:4px solid #0969da;padding:12px 16px;margin:20px 0;border-radius:3px;'>"
            f"<strong>&#128206; Full Report Attached:</strong> <code style='background:#ffffff;padding:2px 6px;border-radius:3px;'>{html.escape(excel_filename)}</code><br>"
            f"<span style='font-size:13px;color:#57606a;'>The attached Excel workbook contains a <b>Summary</b> index tab plus a <b>dedicated sheet tab for each document</b> with line-by-line errors, rule codes, RAG impacts, and actionable fixes.</span>"
            f"</div>"
        )

    rows.append("</div></div>")
    return "\n".join(rows)


def send_email(results, attachment_path=None, processed_at=None):
    host, to = os.getenv("SMTP_HOST"), os.getenv("MAIL_TO")
    if not (host and to):
        print("SMTP_HOST / MAIL_TO not set - skipping email (report saved in reports/).")
        return
    recipients = [x.strip() for x in re.split(r"[,;]", to) if x.strip()]
    if not recipients:
        print("MAIL_TO is empty - skipping email (report saved in reports/).")
        return

    all_passed = all(r["passed"] for r in results)
    status_label = "PASSED" if all_passed else "ERROR"
    display_time = processed_at or datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    if len(results) == 1:
        r0 = results[0]
        if r0["passed"]:
            subject = f"[MD Verify] PASSED: {r0['file']}"
        else:
            subject = f"[MD Verify] ERROR: {r0['file']} ({r0['errors']} errors, {r0['warnings']} warnings)"
    else:
        p = sum(r["passed"] for r in results)
        subject = f"[MD Verify] {status_label}: {p} passed, {len(results) - p} failed"

    attachment_name = attachment_path.name if attachment_path else None
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
        f"MD Verification Report: {status_label}",
        f"Processed at: {display_time}",
        f"Files processed: {len(results)} | Passed: {sum(r['passed'] for r in results)} | Failed: {sum(not r['passed'] for r in results)}",
        ""
    ]
    for r in results:
        res_str = "PASSED" if r["passed"] else f"FAILED ({r['errors']} errors, {r['warnings']} warnings)"
        text_lines.append(f" - {r['file']}: {res_str}  [{display_time}]")
    if attachment_name:
        text_lines.append("")
        text_lines.append(f"Detailed Excel report attached: {attachment_name}")
        text_lines.append("Open the attached spreadsheet to view line numbers, rule codes, RAG impacts, and suggested fixes.")
    msg.set_content("\n".join(text_lines))

    msg.add_alternative(render_html(results, attachment_name, display_time), subtype="html")

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


def run_batch(cfg, inbox=None, verified=None, failed=None, reports=None, settle=None):
    inbox = Path(inbox or INBOX)
    verified = Path(verified or VERIFIED)
    failed = Path(failed or FAILED)
    reports = Path(reports or REPORTS)
    settle = SETTLE if settle is None else settle
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
    for f in files:
        r = verify_file(f, cfg)
        results.append(r)
        if not r["passed"]:  # keep a plain-text report next to the failed file
            failed.mkdir(parents=True, exist_ok=True)
            report_path = _unique_path(failed / f"{f.stem}.report.txt")
            report_path.write_text(to_text(r), encoding="utf-8")
        try:
            move(f, verified if r["passed"] else failed)
        except OSError as e:
            # A routing failure means the document is not safe to release,
            # even when the content checks passed.
            r["passed"] = False
            r["errors"] += 1
            r["issues"].append({
                "line": 1,
                "code": "E002",
                "severity": "error",
                "message": f"Could not move the document to its output folder: {e}",
                "impact": "The verification result was not delivered to the expected folder.",
                "fix": "Resolve the folder or file permission problem and run the batch again.",
            })
            print(to_text(r))
            continue
        print(to_text(r))
    reports.mkdir(parents=True, exist_ok=True)
    stamp_file = datetime.now().strftime("%Y%m%d_%H%M%S_%f")
    display_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    (reports / f"report_{stamp_file}.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    excel_path = generate_excel_report(results, reports, display_time)
    (reports / f"report_{stamp_file}.html").write_text(render_html(results, excel_path.name, display_time), encoding="utf-8")
    try:
        send_email(results, excel_path, display_time)
    except Exception as e:  # never lose the files because mail failed
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
        "passed": True,
        "errors": 0,
        "warnings": 0,
        "issues": []
    }]
    try:
        display_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        test_excel = generate_excel_report(mock_results, REPORTS, display_time)
        send_email(mock_results, test_excel, display_time)
        print(f"SUCCESS: Test email with attachment ({test_excel.name}) sent successfully to: {to}")
        return 0
    except Exception as e:
        print(f"ERROR: SMTP delivery failed: {type(e).__name__}: {e}")
        return 1


def main(argv=None):
    ap = argparse.ArgumentParser()
    ap.add_argument("--once", action="store_true")
    ap.add_argument("--test-email", action="store_true", help="Send a test report email to verify SMTP credentials and exit")
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
        run_batch(cfg, inbox, verified, failed, reports, a.settle)
        return 0

    print(f"Watching {inbox} every {a.poll}s ...")
    try:
        while True:
            run_batch(cfg, inbox, verified, failed, reports, a.settle)
            time.sleep(a.poll)
    except KeyboardInterrupt:
        print("Stopped.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
