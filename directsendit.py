#!/usr/bin/env python3
"""DirectSendIt — Microsoft 365 Direct Send CLI for Linux."""

import argparse
import sys
from pathlib import Path


def parse_args(argv=None):
    parser = argparse.ArgumentParser(
        prog="directsendit",
        description="Send email via Microsoft 365 Direct Send (port 25, no auth)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  directsendit -f sender@co.com -t user@co.com -s "Hello" -H body.html -d contoso-com
  directsendit -f sender@co.com -t user@co.com -s "Hello" -T "Hi there, this is the message body." -d contoso-com
  directsendit -f sender@co.com -t user@co.com -s "Hello" -H "<p>Hello <b>world</b></p>" -d contoso-com
  directsendit -f sender@co.com -t recipients.txt -s "Hi" -H body.html -T body.txt -d contoso-com -a report.pdf
  directsendit -f sender@co.com -t user@co.com -s "Test" -H body.html -S mail.protection.outlook.com -r
        """,
    )

    parser.add_argument("-f", "--from", dest="from_addr", required=True,
                        metavar="EMAIL", help="Sender email address")
    parser.add_argument("-t", "--to", required=True,
                        metavar="EMAIL_OR_FILE", help="Recipient email or path to .txt file")
    parser.add_argument("-s", "--subject", required=True,
                        metavar="TEXT", help="Email subject")

    body = parser.add_argument_group("body (at least one required)")
    body.add_argument("-H", "--html", metavar="FILE_OR_TEXT",
                      help="HTML body: path to .html file, or inline HTML string")
    body.add_argument("-T", "--text", metavar="FILE_OR_TEXT",
                      help="Plain text body: path to .txt file, or inline text string")

    server = parser.add_argument_group("server (one required)")
    srv = server.add_mutually_exclusive_group()
    srv.add_argument("-d", "--domain", metavar="SLUG",
                     help="Tenant slug (e.g. contoso-com) — builds SMTP server automatically")
    srv.add_argument("-S", "--server", metavar="HOST",
                     help="Explicit SMTP server hostname")

    parser.add_argument("-a", "--attach", action="append", default=[],
                        metavar="FILE", help="Attachment path (repeatable)")
    parser.add_argument("-l", "--log", metavar="FILE",
                        help="Log file path (default: email_log_YYYYMMDD_HHMMSS.csv)")
    parser.add_argument("-n", "--no-log", dest="no_log", action="store_true",
                        help="Disable logging entirely")
    parser.add_argument("-D", "--delay", type=float, default=0.0, metavar="SECONDS",
                        help="Delay between sends for bulk (default: 0)")
    parser.add_argument("-N", "--dsn", action="store_true",
                        help="Request Delivery Status Notification")
    parser.add_argument("-r", "--dry-run", dest="dry_run", action="store_true",
                        help="Validate inputs and print plan, no emails sent")

    args = parser.parse_args(argv)

    # Validate: must have at least one body
    if not args.html and not args.text:
        parser.error("at least one of --html / -H or --text / -T is required")

    # Validate: must have domain or server
    if not args.domain and not args.server:
        parser.error("one of --domain / -d or --server / -S is required")

    return args

import os
import re
import csv
import smtplib
import socket
import mimetypes
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders


# ---------------------------------------------------------------------------
# Task 3: Recipient list reader
# ---------------------------------------------------------------------------

def parse_recipients(to_arg):
    """Return list of email addresses from a single address or a file path.

    If the argument contains a path separator or ends with a known file
    extension, it is treated as a file path. A missing file raises
    FileNotFoundError. A bare string (no separators) is treated as a
    single email address.
    """
    looks_like_path = os.sep in to_arg or to_arg.endswith(".txt")
    path = Path(to_arg)
    if looks_like_path or path.is_file():
        if not path.exists():
            raise FileNotFoundError(f"Recipients file not found: {to_arg}")
        lines = path.read_text().splitlines()
        recipients = [
            line.strip() for line in lines
            if line.strip() and not line.strip().startswith("#")
        ]
        if not recipients:
            raise ValueError(f"No recipients found in {to_arg}")
        return recipients
    return [to_arg.strip()]


# ---------------------------------------------------------------------------
# Task 4: MIME email builder
# ---------------------------------------------------------------------------

def build_message(from_addr, to, subject, html_content, text_content, attachments, dsn):
    """Build a MIME email message."""
    if html_content and text_content:
        alt = MIMEMultipart("alternative")
        alt.attach(MIMEText(text_content, "plain", "utf-8"))
        alt.attach(MIMEText(html_content, "html", "utf-8"))
        if attachments:
            msg = MIMEMultipart("mixed")
            msg.attach(alt)
        else:
            msg = alt
    elif html_content:
        if attachments:
            msg = MIMEMultipart("mixed")
            msg.attach(MIMEText(html_content, "html", "utf-8"))
        else:
            msg = MIMEText(html_content, "html", "utf-8")
    else:
        if attachments:
            msg = MIMEMultipart("mixed")
            msg.attach(MIMEText(text_content, "plain", "utf-8"))
        else:
            msg = MIMEText(text_content, "plain", "utf-8")

    msg["From"] = from_addr
    msg["To"] = to
    msg["Subject"] = subject

    if dsn:
        msg["Disposition-Notification-To"] = from_addr
        msg["Return-Receipt-To"] = from_addr

    for attach_path in attachments:
        p = Path(attach_path)
        if not p.exists():
            raise FileNotFoundError(f"Attachment not found: {attach_path}")
        ctype, encoding = mimetypes.guess_type(str(p))
        if ctype is None or encoding is not None:
            ctype = "application/octet-stream"
        maintype, subtype = ctype.split("/", 1)
        part = MIMEBase(maintype, subtype)
        part.set_payload(p.read_bytes())
        encoders.encode_base64(part)
        part.add_header("Content-Disposition", "attachment", filename=p.name)
        msg.attach(part)

    return msg


# ---------------------------------------------------------------------------
# Task 5: M365 error classification
# ---------------------------------------------------------------------------

_M365_ERRORS = [
    (
        r"5\.7\.51|RestrictDomainsToIPAddresses",
        "Tenant Rejection",
        "Tenant rejects unauthenticated relay — your M365 connector may require IP allowlisting",
    ),
    (
        r"TenantInboundAttribution",
        "Tenant Rejection",
        "Direct Send blocked — check that your sending IP is permitted for this tenant",
    ),
    (
        r"[Mm]ailbox unavailable",
        "Rejected",
        "Recipient mailbox not found or disabled in this tenant",
    ),
    (
        r"5\.7\.64|TLS required",
        "Rejected",
        "TLS required by tenant — port 25 plain-text rejected",
    ),
]


def classify_smtp_error(error_msg):
    """Return (status, human_readable_detail) for an SMTP error string."""
    for pattern, status, detail in _M365_ERRORS:
        if re.search(pattern, error_msg):
            return status, detail
    if error_msg:
        return "Failed", error_msg
    return "Failed", "Unknown error"


# ---------------------------------------------------------------------------
# Task 6: SMTP sender
# ---------------------------------------------------------------------------

def smtp_send(smtp_server, from_addr, to_addr, msg, timeout=30):
    """
    Send a pre-built MIME message via SMTP port 25 (no auth).
    Returns (status, detail) where status is one of:
        Accepted, Rejected, Tenant Rejection, Connection Error, Failed
    """
    try:
        with smtplib.SMTP(smtp_server, 25, timeout=timeout) as conn:
            conn.sendmail(from_addr, [to_addr], msg.as_string())
        return "Accepted", ""
    except smtplib.SMTPRecipientsRefused as e:
        errors = "; ".join(str(v) for v in e.recipients.values())
        status, detail = classify_smtp_error(errors)
        return status, detail
    except smtplib.SMTPException as e:
        status, detail = classify_smtp_error(str(e))
        return status, detail
    except socket.gaierror:
        # Must be before OSError — socket.gaierror is an OSError subclass
        return "Connection Error", (
            f"Could not resolve SMTP server '{smtp_server}' — check your --domain or --server value"
        )
    except (TimeoutError, socket.timeout):
        # Must be before OSError — TimeoutError is an OSError subclass
        return "Connection Error", (
            "Connection timed out — port 25 may be blocked by your ISP or firewall"
        )
    except (ConnectionRefusedError, OSError):
        return "Connection Error", (
            "Could not reach SMTP server — port 25 may be blocked by your ISP or firewall"
        )
    except Exception as e:
        return "Failed", str(e)


# ---------------------------------------------------------------------------
# Task 7: CSV logger
# ---------------------------------------------------------------------------

class CsvLogger:
    """Write send results to a CSV file. Pass path=None to disable logging."""

    FIELDS = ["From", "To", "Subject", "Status", "Timestamp", "Error"]

    def __init__(self, path):
        self._path = path
        self._fh = None
        self._writer = None
        if path:
            self._fh = open(path, "w", newline="", encoding="utf-8")
            self._writer = csv.DictWriter(self._fh, fieldnames=self.FIELDS)
            self._writer.writeheader()

    def write(self, from_addr, to, subject, status, error):
        if not self._writer:
            return
        self._writer.writerow({
            "From": from_addr,
            "To": to,
            "Subject": subject,
            "Status": status,
            "Timestamp": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
            "Error": error,
        })
        self._fh.flush()

    def close(self):
        if self._fh:
            self._fh.close()


# ---------------------------------------------------------------------------
# Task 8: Dry run
# ---------------------------------------------------------------------------

def dry_run_report(smtp_server, from_addr, recipients, subject,
                   html_path, text_path, attachments, dsn, log_path, delay):
    """Print a dry-run summary — no emails sent."""
    print("\n" + "=" * 60)
    print("  DRY RUN — no emails will be sent")
    print("=" * 60)
    print(f"  SMTP Server : {smtp_server}")
    print(f"  From        : {from_addr}")
    print(f"  Recipients  : {len(recipients)} recipient(s)")
    for r in recipients:
        print(f"                {r}")
    print(f"  Subject     : {subject}")
    def _body_label(val):
        if not val:
            return "(none)"
        return val if Path(val).exists() else "[inline text]"

    print(f"  HTML body   : {_body_label(html_path)}")
    print(f"  Text body   : {_body_label(text_path)}")
    if attachments:
        print(f"  Attachments : {len(attachments)}")
        for a in attachments:
            print(f"                {Path(a).name}")
    else:
        print(f"  Attachments : (none)")
    print(f"  DSN headers : {'yes' if dsn else 'no'}")
    print(f"  Log file    : {log_path or '(disabled)'}")
    print(f"  Delay       : {delay}s between sends")
    print("=" * 60 + "\n")


# ---------------------------------------------------------------------------
# Task 9: Main orchestration
# ---------------------------------------------------------------------------

def resolve_smtp_server(args):
    """Return the SMTP server hostname from --domain or --server.

    Dots in the domain slug are replaced with dashes so that both
    'wolfandco.com' and 'wolfandco-com' produce the correct endpoint
    'wolfandco-com.mail.protection.outlook.com'.
    """
    if args.server:
        return args.server
    slug = args.domain.replace(".", "-")
    return f"{slug}.mail.protection.outlook.com"


def main():
    import time

    args = parse_args()
    smtp_server = resolve_smtp_server(args)

    # Load body — each flag accepts either a file path or inline text
    html_content = None
    text_content = None
    if args.html:
        hp = Path(args.html)
        if hp.exists():
            html_content = hp.read_text(encoding="utf-8")
        else:
            html_content = args.html  # treat as inline HTML
    if args.text:
        tp = Path(args.text)
        if tp.exists():
            text_content = tp.read_text(encoding="utf-8")
        else:
            text_content = args.text  # treat as inline plain text

    # Validate attachments exist
    for attach in args.attach:
        if not Path(attach).exists():
            print(f"ERROR: Attachment not found: {attach}", file=sys.stderr)
            sys.exit(1)

    # Parse recipients
    try:
        recipients = parse_recipients(args.to)
    except (FileNotFoundError, ValueError) as e:
        print(f"ERROR: {e}", file=sys.stderr)
        sys.exit(1)

    # Resolve log path
    if args.no_log:
        log_path = None
    elif args.log:
        log_path = args.log
    else:
        log_path = f"email_log_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"

    # Dry run
    if args.dry_run:
        dry_run_report(
            smtp_server=smtp_server,
            from_addr=args.from_addr,
            recipients=recipients,
            subject=args.subject,
            html_path=args.html,
            text_path=args.text,
            attachments=args.attach,
            dsn=args.dsn,
            log_path=log_path,
            delay=args.delay,
        )
        sys.exit(0)

    logger = CsvLogger(log_path)
    accepted = 0
    failed = 0

    try:
        for i, recipient in enumerate(recipients):
            if i > 0 and args.delay > 0:
                time.sleep(args.delay)

            try:
                msg = build_message(
                    from_addr=args.from_addr,
                    to=recipient,
                    subject=args.subject,
                    html_content=html_content,
                    text_content=text_content,
                    attachments=args.attach,
                    dsn=args.dsn,
                )
            except FileNotFoundError as e:
                print(f"  ERROR: {e}", file=sys.stderr)
                sys.exit(1)

            status, detail = smtp_send(smtp_server, args.from_addr, recipient, msg)
            logger.write(args.from_addr, recipient, args.subject, status, detail)

            if status == "Accepted":
                accepted += 1
                print(f"  [+] Accepted : {args.from_addr} -> {recipient}")
            else:
                failed += 1
                print(f"  [-] {status:18s}: {recipient}")
                print(f"      {detail}")

    finally:
        logger.close()

    print()
    print(f"  Done. {accepted} accepted, {failed} failed.", end="")
    if log_path:
        print(f" Log: {log_path}")
    else:
        print()


if __name__ == "__main__":
    main()
