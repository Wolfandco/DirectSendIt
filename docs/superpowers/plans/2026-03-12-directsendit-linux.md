# DirectSendIt Linux Port Implementation Plan

> **For agentic workers:** REQUIRED: Use superpowers:subagent-driven-development (if subagents available) or superpowers:executing-plans to implement this plan. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Port the PowerShell DirectSendIt tool to a Python CLI for Linux that sends emails via Microsoft 365 Direct Send (SMTP port 25, no auth).

**Architecture:** Single Python script (`directsendit.py`) with a shell wrapper (`directsendit`) for clean invocation. All logic lives in the Python file — argument parsing, MIME building, recipient handling, SMTP sending, error classification, and CSV logging. Tests live in `tests/test_directsendit.py` using pytest + unittest.mock.

**Tech Stack:** Python 3 stdlib only — `argparse`, `smtplib`, `email.mime.*`, `socket`, `csv`, `re`, `pathlib`

**Spec:** `docs/superpowers/specs/2026-03-12-directsendit-linux-design.md`

---

## File Map

| File | Action | Responsibility |
|---|---|---|
| `directsendit.py` | Create | All CLI logic, email building, SMTP, logging |
| `directsendit` | Create | Shell wrapper (`exec python3 /abs/path/directsendit.py "$@"`) |
| `install.sh` | Create | Copies wrapper to `/usr/local/bin`, sets +x |
| `README.md` | Create | Usage examples |
| `tests/test_directsendit.py` | Create | pytest test suite |
| `tests/__init__.py` | Create | Empty, makes tests a package |
| `directsendit.ps1` | Delete | Replaced by Python version |

---

## Chunk 1: Scaffold, Shell Wrapper, and CLI Parsing

### Task 1: Project scaffold

**Files:**
- Create: `directsendit.py`
- Create: `directsendit`
- Create: `install.sh`
- Create: `tests/__init__.py`

- [ ] **Step 1: Create the shell wrapper**

```sh
# directsendit
#!/bin/sh
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
exec python3 "$SCRIPT_DIR/directsendit.py" "$@"
```

- [ ] **Step 2: Create install.sh**

```sh
#!/bin/sh
set -e
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
WRAPPER="$SCRIPT_DIR/directsendit"
TARGET="/usr/local/bin/directsendit"

if [ ! -f "$WRAPPER" ]; then
    echo "ERROR: '$WRAPPER' not found. Run install.sh from the repo directory."
    exit 1
fi

chmod +x "$WRAPPER"
chmod +x "$SCRIPT_DIR/directsendit.py"

if cp "$WRAPPER" "$TARGET" 2>/dev/null; then
    echo "Installed to $TARGET"
else
    echo "Permission denied. Try: sudo ./install.sh"
    exit 1
fi
```

- [ ] **Step 3: Create empty Python stub and tests init**

```python
# directsendit.py
#!/usr/bin/env python3
"""DirectSendIt — Microsoft 365 Direct Send CLI for Linux."""
```

```python
# tests/__init__.py
```

- [ ] **Step 4: Make files executable**

```bash
chmod +x directsendit directsendit.py install.sh
```

- [ ] **Step 5: Commit scaffold**

```bash
git add directsendit.py directsendit install.sh tests/__init__.py
git commit -m "feat: add project scaffold and shell wrapper"
```

---

### Task 2: CLI argument parsing

**Files:**
- Modify: `directsendit.py`
- Create: `tests/test_directsendit.py`

- [ ] **Step 1: Write failing tests for argument parsing**

```python
# tests/test_directsendit.py
import pytest
import sys
from unittest.mock import patch
from pathlib import Path


def import_module():
    import importlib.util
    spec = importlib.util.spec_from_file_location(
        "directsendit",
        Path(__file__).parent.parent / "directsendit.py"
    )
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


@pytest.fixture
def mod():
    return import_module()


class TestArgParsing:
    def test_minimal_flags_with_domain(self, mod, tmp_path):
        html = tmp_path / "body.html"
        html.write_text("<p>Hello</p>")
        args = mod.parse_args([
            "-f", "sender@co.com",
            "-t", "recipient@co.com",
            "-s", "Test Subject",
            "-H", str(html),
            "-d", "contoso-com",
        ])
        assert args.from_addr == "sender@co.com"
        assert args.to == "recipient@co.com"
        assert args.subject == "Test Subject"
        assert args.domain == "contoso-com"
        assert args.server is None

    def test_server_flag_overrides_domain(self, mod, tmp_path):
        txt = tmp_path / "body.txt"
        txt.write_text("Hello")
        args = mod.parse_args([
            "-f", "a@b.com",
            "-t", "c@d.com",
            "-s", "Hi",
            "-T", str(txt),
            "-S", "custom.smtp.server",
        ])
        assert args.server == "custom.smtp.server"

    def test_missing_from_raises(self, mod, tmp_path):
        html = tmp_path / "b.html"
        html.write_text("<p>x</p>")
        with pytest.raises(SystemExit):
            mod.parse_args(["-t", "a@b.com", "-s", "Hi", "-H", str(html), "-d", "x"])

    def test_missing_body_raises(self, mod):
        with pytest.raises(SystemExit):
            mod.parse_args(["-f", "a@b.com", "-t", "b@c.com", "-s", "Hi", "-d", "x"])

    def test_no_log_flag(self, mod, tmp_path):
        html = tmp_path / "b.html"
        html.write_text("<p>x</p>")
        args = mod.parse_args([
            "-f", "a@b.com", "-t", "b@c.com", "-s", "Hi",
            "-H", str(html), "-d", "x", "-n"
        ])
        assert args.no_log is True

    def test_delay_flag(self, mod, tmp_path):
        html = tmp_path / "b.html"
        html.write_text("<p>x</p>")
        args = mod.parse_args([
            "-f", "a@b.com", "-t", "b@c.com", "-s", "Hi",
            "-H", str(html), "-d", "x", "-D", "2.5"
        ])
        assert args.delay == 2.5

    def test_dry_run_flag(self, mod, tmp_path):
        html = tmp_path / "b.html"
        html.write_text("<p>x</p>")
        args = mod.parse_args([
            "-f", "a@b.com", "-t", "b@c.com", "-s", "Hi",
            "-H", str(html), "-d", "x", "-r"
        ])
        assert args.dry_run is True

    def test_dsn_flag(self, mod, tmp_path):
        html = tmp_path / "b.html"
        html.write_text("<p>x</p>")
        args = mod.parse_args([
            "-f", "a@b.com", "-t", "b@c.com", "-s", "Hi",
            "-H", str(html), "-d", "x", "-N"
        ])
        assert args.dsn is True

    def test_multiple_attach_flags(self, mod, tmp_path):
        html = tmp_path / "b.html"
        html.write_text("<p>x</p>")
        f1 = tmp_path / "a.pdf"
        f2 = tmp_path / "b.pdf"
        f1.write_bytes(b"pdf1")
        f2.write_bytes(b"pdf2")
        args = mod.parse_args([
            "-f", "a@b.com", "-t", "b@c.com", "-s", "Hi",
            "-H", str(html), "-d", "x",
            "-a", str(f1), "-a", str(f2),
        ])
        assert len(args.attach) == 2
```

- [ ] **Step 2: Run tests — verify they fail**

```bash
cd /root/directsendit && python3 -m pytest tests/test_directsendit.py::TestArgParsing -v 2>&1 | head -30
```

Expected: errors about missing `parse_args`

- [ ] **Step 3: Implement `parse_args` in directsendit.py**

```python
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
    body.add_argument("-H", "--html", metavar="FILE", help="Path to HTML body file")
    body.add_argument("-T", "--text", metavar="FILE", help="Path to plain text body file")

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
```

- [ ] **Step 4: Run tests — verify they pass**

```bash
python3 -m pytest tests/test_directsendit.py::TestArgParsing -v
```

Expected: all 8 tests PASS

- [ ] **Step 5: Commit**

```bash
git add directsendit.py tests/test_directsendit.py
git commit -m "feat: add CLI argument parsing with full flag set"
```

---

## Chunk 2: Email Building and Recipient Parsing

### Task 3: Recipient list reader

**Files:**
- Modify: `directsendit.py`
- Modify: `tests/test_directsendit.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_directsendit.py`:

```python
class TestRecipientParsing:
    def test_single_email_string(self, mod):
        result = mod.parse_recipients("user@example.com")
        assert result == ["user@example.com"]

    def test_file_with_multiple_emails(self, mod, tmp_path):
        f = tmp_path / "recipients.txt"
        f.write_text("a@b.com\nb@c.com\nc@d.com\n")
        result = mod.parse_recipients(str(f))
        assert result == ["a@b.com", "b@c.com", "c@d.com"]

    def test_file_skips_blank_lines(self, mod, tmp_path):
        f = tmp_path / "r.txt"
        f.write_text("a@b.com\n\nb@c.com\n\n")
        result = mod.parse_recipients(str(f))
        assert result == ["a@b.com", "b@c.com"]

    def test_file_skips_comment_lines(self, mod, tmp_path):
        f = tmp_path / "r.txt"
        f.write_text("# This is a comment\na@b.com\n# another\nb@c.com\n")
        result = mod.parse_recipients(str(f))
        assert result == ["a@b.com", "b@c.com"]

    def test_missing_file_raises(self, mod):
        with pytest.raises(FileNotFoundError):
            mod.parse_recipients("/nonexistent/path/r.txt")

    def test_empty_file_raises(self, mod, tmp_path):
        f = tmp_path / "empty.txt"
        f.write_text("# just comments\n\n")
        with pytest.raises(ValueError, match="No recipients"):
            mod.parse_recipients(str(f))
```

- [ ] **Step 2: Run tests — verify they fail**

```bash
python3 -m pytest tests/test_directsendit.py::TestRecipientParsing -v 2>&1 | head -20
```

Expected: FAIL — `parse_recipients` not defined

- [ ] **Step 3: Implement `parse_recipients`**

Add to `directsendit.py`:

```python
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
    # No path separator — treat as a single email address
    return [to_arg.strip()]
```

Add `import os` to the top-level imports in `directsendit.py`.

- [ ] **Step 4: Run tests — verify they pass**

```bash
python3 -m pytest tests/test_directsendit.py::TestRecipientParsing -v
```

Expected: all 6 tests PASS

- [ ] **Step 5: Commit**

```bash
git add directsendit.py tests/test_directsendit.py
git commit -m "feat: add recipient list parser"
```

---

### Task 4: MIME email builder

**Files:**
- Modify: `directsendit.py`
- Modify: `tests/test_directsendit.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_directsendit.py`:

```python
class TestEmailBuilder:
    def test_html_only_message(self, mod):
        msg = mod.build_message(
            from_addr="a@b.com",
            to="c@d.com",
            subject="Hello",
            html_content="<p>Hi</p>",
            text_content=None,
            attachments=[],
            dsn=False,
        )
        assert msg["From"] == "a@b.com"
        assert msg["To"] == "c@d.com"
        assert msg["Subject"] == "Hello"
        assert msg.get_content_type() in ("text/html", "multipart/alternative", "multipart/mixed")

    def test_text_only_message(self, mod):
        msg = mod.build_message(
            from_addr="a@b.com",
            to="c@d.com",
            subject="Hello",
            html_content=None,
            text_content="Hi there",
            attachments=[],
            dsn=False,
        )
        assert msg["Subject"] == "Hello"

    def test_multipart_with_both(self, mod):
        msg = mod.build_message(
            from_addr="a@b.com",
            to="c@d.com",
            subject="Hello",
            html_content="<p>Hi</p>",
            text_content="Hi",
            attachments=[],
            dsn=False,
        )
        assert "multipart" in msg.get_content_type()

    def test_attachment_included(self, mod, tmp_path):
        attach = tmp_path / "report.pdf"
        attach.write_bytes(b"%PDF-fake")
        msg = mod.build_message(
            from_addr="a@b.com",
            to="c@d.com",
            subject="Hello",
            html_content="<p>Hi</p>",
            text_content=None,
            attachments=[str(attach)],
            dsn=False,
        )
        payloads = msg.get_payload()
        assert isinstance(payloads, list)
        assert len(payloads) >= 2

    def test_dsn_headers_added(self, mod):
        msg = mod.build_message(
            from_addr="a@b.com",
            to="c@d.com",
            subject="Hello",
            html_content="<p>Hi</p>",
            text_content=None,
            attachments=[],
            dsn=True,
        )
        assert msg["Disposition-Notification-To"] == "a@b.com"
        assert msg["Return-Receipt-To"] == "a@b.com"

    def test_missing_attachment_raises(self, mod):
        with pytest.raises(FileNotFoundError):
            mod.build_message(
                from_addr="a@b.com",
                to="c@d.com",
                subject="Hello",
                html_content="<p>Hi</p>",
                text_content=None,
                attachments=["/nonexistent/file.pdf"],
                dsn=False,
            )
```

- [ ] **Step 2: Run tests — verify they fail**

```bash
python3 -m pytest tests/test_directsendit.py::TestEmailBuilder -v 2>&1 | head -20
```

Expected: FAIL — `build_message` not defined

- [ ] **Step 3: Implement `build_message`**

Add to `directsendit.py`:

```python
import mimetypes
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders


def build_message(from_addr, to, subject, html_content, text_content, attachments, dsn):
    """Build a MIME email message."""
    # Choose structure based on content
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
```

- [ ] **Step 4: Run tests — verify they pass**

```bash
python3 -m pytest tests/test_directsendit.py::TestEmailBuilder -v
```

Expected: all 6 tests PASS

- [ ] **Step 5: Commit**

```bash
git add directsendit.py tests/test_directsendit.py
git commit -m "feat: add MIME email builder with attachments and DSN headers"
```

---

## Chunk 3: SMTP Sending, Error Classification, and Logging

### Task 5: M365 error classification

**Files:**
- Modify: `directsendit.py`
- Modify: `tests/test_directsendit.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_directsendit.py`:

```python
class TestErrorClassification:
    def test_tenant_rejection_5751(self, mod):
        status, detail = mod.classify_smtp_error("550 5.7.51 RestrictDomainsToIPAddresses")
        assert status == "Tenant Rejection"
        assert "IP allowlisting" in detail

    def test_tenant_attribution(self, mod):
        status, detail = mod.classify_smtp_error("550 TenantInboundAttribution")
        assert status == "Tenant Rejection"
        assert "sending IP" in detail

    def test_mailbox_unavailable(self, mod):
        status, detail = mod.classify_smtp_error("550 Mailbox unavailable")
        assert status == "Rejected"
        assert "mailbox" in detail.lower()

    def test_tls_required(self, mod):
        status, detail = mod.classify_smtp_error("530 5.7.64 TLS required")
        assert status == "Rejected"
        assert "TLS" in detail

    def test_generic_error(self, mod):
        status, detail = mod.classify_smtp_error("500 Something went wrong")
        assert status == "Failed"
        assert "500 Something went wrong" in detail

    def test_empty_error(self, mod):
        status, detail = mod.classify_smtp_error("")
        assert status == "Failed"
```

- [ ] **Step 2: Run tests — verify they fail**

```bash
python3 -m pytest tests/test_directsendit.py::TestErrorClassification -v 2>&1 | head -20
```

- [ ] **Step 3: Implement `classify_smtp_error`**

Add to `directsendit.py`:

```python
import re


# M365 error patterns: (regex, status, human message)
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
```

- [ ] **Step 4: Run tests — verify they pass**

```bash
python3 -m pytest tests/test_directsendit.py::TestErrorClassification -v
```

Expected: all 6 tests PASS

- [ ] **Step 5: Commit**

```bash
git add directsendit.py tests/test_directsendit.py
git commit -m "feat: add M365-specific SMTP error classification"
```

---

### Task 6: SMTP sender

**Files:**
- Modify: `directsendit.py`
- Modify: `tests/test_directsendit.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_directsendit.py`:

```python
from unittest.mock import patch, MagicMock
import smtplib


class TestSmtpSender:
    def _make_msg(self, mod):
        return mod.build_message(
            from_addr="a@b.com",
            to="c@d.com",
            subject="Test",
            html_content="<p>Hi</p>",
            text_content=None,
            attachments=[],
            dsn=False,
        )

    def test_successful_send_returns_accepted(self, mod):
        msg = self._make_msg(mod)
        with patch("smtplib.SMTP") as mock_smtp:
            instance = mock_smtp.return_value.__enter__.return_value
            instance.sendmail.return_value = {}
            status, detail = mod.smtp_send("mail.server.com", "a@b.com", "c@d.com", msg)
        assert status == "Accepted"
        assert detail == ""

    def test_smtp_exception_classified(self, mod):
        msg = self._make_msg(mod)
        with patch("smtplib.SMTP") as mock_smtp:
            mock_smtp.return_value.__enter__.side_effect = smtplib.SMTPException(
                "550 5.7.51 RestrictDomainsToIPAddresses"
            )
            status, detail = mod.smtp_send("mail.server.com", "a@b.com", "c@d.com", msg)
        assert status == "Tenant Rejection"
        assert "IP allowlisting" in detail

    def test_connection_refused_gives_clear_message(self, mod):
        msg = self._make_msg(mod)
        with patch("smtplib.SMTP") as mock_smtp:
            mock_smtp.return_value.__enter__.side_effect = ConnectionRefusedError()
            status, detail = mod.smtp_send("mail.server.com", "a@b.com", "c@d.com", msg)
        assert status == "Connection Error"
        assert "port 25" in detail

    def test_dns_failure_gives_clear_message(self, mod):
        msg = self._make_msg(mod)
        import socket
        with patch("smtplib.SMTP") as mock_smtp:
            mock_smtp.return_value.__enter__.side_effect = socket.gaierror("Name or service not known")
            status, detail = mod.smtp_send("badhost.invalid", "a@b.com", "c@d.com", msg)
        assert status == "Connection Error"
        assert "resolve" in detail.lower() or "DNS" in detail

    def test_timeout_gives_clear_message(self, mod):
        msg = self._make_msg(mod)
        with patch("smtplib.SMTP") as mock_smtp:
            mock_smtp.return_value.__enter__.side_effect = TimeoutError()
            status, detail = mod.smtp_send("mail.server.com", "a@b.com", "c@d.com", msg)
        assert status == "Connection Error"
        assert "timeout" in detail.lower() or "port 25" in detail
```

- [ ] **Step 2: Run tests — verify they fail**

```bash
python3 -m pytest tests/test_directsendit.py::TestSmtpSender -v 2>&1 | head -20
```

- [ ] **Step 3: Implement `smtp_send`**

Add to `directsendit.py`:

```python
import smtplib
import socket


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
    except (ConnectionRefusedError, OSError) as e:
        return "Connection Error", (
            "Could not reach SMTP server — port 25 may be blocked by your ISP or firewall"
        )
    except Exception as e:
        return "Failed", str(e)
```

- [ ] **Step 4: Run tests — verify they pass**

```bash
python3 -m pytest tests/test_directsendit.py::TestSmtpSender -v
```

Expected: all 5 tests PASS

- [ ] **Step 5: Commit**

```bash
git add directsendit.py tests/test_directsendit.py
git commit -m "feat: add SMTP sender with connection and M365 error handling"
```

---

### Task 7: CSV logger

**Files:**
- Modify: `directsendit.py`
- Modify: `tests/test_directsendit.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_directsendit.py`:

```python
import csv


class TestLogger:
    def test_logger_creates_file_with_header(self, mod, tmp_path):
        log_path = tmp_path / "log.csv"
        logger = mod.CsvLogger(str(log_path))
        logger.close()
        rows = list(csv.DictReader(log_path.open()))
        assert rows == []  # header written, no data rows yet
        header = log_path.read_text().splitlines()[0]
        assert "From" in header and "Status" in header

    def test_logger_writes_row(self, mod, tmp_path):
        log_path = tmp_path / "log.csv"
        logger = mod.CsvLogger(str(log_path))
        logger.write("a@b.com", "c@d.com", "Hello", "Accepted", "")
        logger.close()
        rows = list(csv.DictReader(log_path.open()))
        assert len(rows) == 1
        assert rows[0]["Status"] == "Accepted"
        assert rows[0]["From"] == "a@b.com"

    def test_logger_writes_error_detail(self, mod, tmp_path):
        log_path = tmp_path / "log.csv"
        logger = mod.CsvLogger(str(log_path))
        logger.write("a@b.com", "c@d.com", "Hello", "Tenant Rejection", "IP allowlisting")
        logger.close()
        rows = list(csv.DictReader(log_path.open()))
        assert rows[0]["Error"] == "IP allowlisting"

    def test_null_logger_does_not_write(self, mod, tmp_path):
        logger = mod.CsvLogger(None)
        logger.write("a@b.com", "c@d.com", "Hello", "Accepted", "")
        logger.close()
        # No file created, no error
```

- [ ] **Step 2: Run tests — verify they fail**

```bash
python3 -m pytest tests/test_directsendit.py::TestLogger -v 2>&1 | head -20
```

- [ ] **Step 3: Implement `CsvLogger`**

Add to `directsendit.py`:

```python
import csv
from datetime import datetime


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
```

- [ ] **Step 4: Run tests — verify they pass**

```bash
python3 -m pytest tests/test_directsendit.py::TestLogger -v
```

Expected: all 4 tests PASS

- [ ] **Step 5: Commit**

```bash
git add directsendit.py tests/test_directsendit.py
git commit -m "feat: add CSV logger with null-logger support"
```

---

## Chunk 4: Dry Run, Main Orchestration, Cleanup, and Push

### Task 8: Dry run validation

**Files:**
- Modify: `directsendit.py`
- Modify: `tests/test_directsendit.py`

- [ ] **Step 1: Write failing tests**

Append to `tests/test_directsendit.py`:

```python
import io


class TestDryRun:
    def test_dry_run_prints_plan(self, mod, tmp_path, capsys):
        html = tmp_path / "b.html"
        html.write_text("<p>Hello</p>")
        recipients = tmp_path / "r.txt"
        recipients.write_text("a@b.com\nb@c.com\n")
        mod.dry_run_report(
            smtp_server="contoso-com.mail.protection.outlook.com",
            from_addr="sender@co.com",
            recipients=["a@b.com", "b@c.com"],
            subject="Hello World",
            html_path=str(html),
            text_path=None,
            attachments=[],
            dsn=False,
            log_path="email_log.csv",
            delay=0,
        )
        out = capsys.readouterr().out
        assert "DRY RUN" in out
        assert "contoso-com.mail.protection.outlook.com" in out
        assert "sender@co.com" in out
        assert "2 recipient" in out
        assert "Hello World" in out

    def test_dry_run_shows_attachments(self, mod, tmp_path, capsys):
        html = tmp_path / "b.html"
        html.write_text("<p>x</p>")
        attach = tmp_path / "file.pdf"
        attach.write_bytes(b"pdf")
        mod.dry_run_report(
            smtp_server="x.mail.protection.outlook.com",
            from_addr="a@b.com",
            recipients=["c@d.com"],
            subject="Hi",
            html_path=str(html),
            text_path=None,
            attachments=[str(attach)],
            dsn=False,
            log_path=None,
            delay=0,
        )
        out = capsys.readouterr().out
        assert "file.pdf" in out
```

- [ ] **Step 2: Run tests — verify they fail**

```bash
python3 -m pytest tests/test_directsendit.py::TestDryRun -v 2>&1 | head -20
```

- [ ] **Step 3: Implement `dry_run_report`**

Add to `directsendit.py`:

```python
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
    print(f"  HTML body   : {html_path or '(none)'}")
    print(f"  Text body   : {text_path or '(none)'}")
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
```

- [ ] **Step 4: Run tests — verify they pass**

```bash
python3 -m pytest tests/test_directsendit.py::TestDryRun -v
```

Expected: both tests PASS

- [ ] **Step 5: Commit**

```bash
git add directsendit.py tests/test_directsendit.py
git commit -m "feat: add dry-run report function"
```

---

### Task 9: Main orchestration

**Files:**
- Modify: `directsendit.py`

- [ ] **Step 1: Add imports, `resolve_smtp_server` helper, and tests**

Ensure these imports are at the top of `directsendit.py` (add any missing):

```python
import os
import sys
import re
import csv
import smtplib
import socket
import mimetypes
import argparse
from pathlib import Path
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from email.mime.base import MIMEBase
from email import encoders
```

Add a test for `resolve_smtp_server` to `tests/test_directsendit.py`:

```python
class TestResolveSmtpServer:
    def test_domain_builds_server(self, mod):
        class FakeArgs:
            domain = "contoso-com"
            server = None
        assert mod.resolve_smtp_server(FakeArgs()) == "contoso-com.mail.protection.outlook.com"

    def test_server_overrides_domain(self, mod):
        class FakeArgs:
            domain = "contoso-com"
            server = "custom.server.com"
        assert mod.resolve_smtp_server(FakeArgs()) == "custom.server.com"
```

The full final version of `directsendit.py` adds `main()` and `resolve_smtp_server()`:

```python
def resolve_smtp_server(args):
    """Return the SMTP server hostname from --domain or --server."""
    if args.server:
        return args.server
    return f"{args.domain}.mail.protection.outlook.com"


def main():
    import time

    args = parse_args()
    smtp_server = resolve_smtp_server(args)

    # Validate body files exist
    html_content = None
    text_content = None
    if args.html:
        hp = Path(args.html)
        if not hp.exists():
            print(f"ERROR: HTML file not found: {args.html}", file=sys.stderr)
            sys.exit(1)
        html_content = hp.read_text(encoding="utf-8")
    if args.text:
        tp = Path(args.text)
        if not tp.exists():
            print(f"ERROR: Text file not found: {args.text}", file=sys.stderr)
            sys.exit(1)
        text_content = tp.read_text(encoding="utf-8")

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
```

- [ ] **Step 2: Run full test suite — all tests should pass**

```bash
python3 -m pytest tests/ -v
```

Expected: all tests PASS

- [ ] **Step 3: Smoke test dry run**

```bash
python3 directsendit.py -f test@example.com -t test@example.com -s "Test" -H /dev/stdin -d contoso-com -r <<< "<p>Hello</p>"
```

Expected: prints DRY RUN summary, exits 0

- [ ] **Step 4: Commit**

```bash
git add directsendit.py
git commit -m "feat: add main orchestration loop"
```

---

### Task 10: README and cleanup

**Files:**
- Create: `README.md`
- Delete: `directsendit.ps1`

- [ ] **Step 1: Write README.md**

```markdown
# DirectSendIt

Send emails via Microsoft 365 Direct Send (SMTP port 25, no authentication).

## Install

```sh
git clone https://github.com/Wolfandco/DirectSendIt
cd DirectSendIt
sudo ./install.sh
```

## Usage

```sh
# Single recipient, HTML only
directsendit -f sender@company.com -t user@company.com -s "Hello" -H body.html -d company-com

# Multiple recipients from file, with plain text fallback
directsendit -f sender@company.com -t recipients.txt -s "Newsletter" -H body.html -T body.txt -d company-com

# With attachments
directsendit -f sender@company.com -t user@company.com -s "Report" -H body.html -a report.pdf -d company-com

# Explicit SMTP server
directsendit -f sender@company.com -t user@company.com -s "Hi" -H body.html -S company-com.mail.protection.outlook.com

# Dry run (validate without sending)
directsendit -f sender@company.com -t recipients.txt -s "Test" -H body.html -d company-com -r

# Custom log file
directsendit -f sender@company.com -t user@company.com -s "Hi" -H body.html -d company-com -l results.csv

# Request DSN delivery notification
directsendit -f sender@company.com -t user@company.com -s "Hi" -H body.html -d company-com -N
```

## Flags

| Short | Long | Description |
|---|---|---|
| `-f` | `--from` | Sender email (required) |
| `-t` | `--to` | Recipient email or `.txt` file (one per line) |
| `-s` | `--subject` | Subject line |
| `-H` | `--html` | HTML body file |
| `-T` | `--text` | Plain text body file |
| `-a` | `--attach` | Attachment (repeatable) |
| `-d` | `--domain` | Tenant slug (e.g. `company-com`) |
| `-S` | `--server` | Explicit SMTP server |
| `-l` | `--log` | Log CSV path |
| `-n` | `--no-log` | Disable logging |
| `-D` | `--delay` | Seconds between sends |
| `-N` | `--dsn` | Request delivery notification |
| `-r` | `--dry-run` | Preview only, no sends |

## Note on Delivery Confirmation

`Accepted` in the log means the M365 server accepted the message for queuing — not that it reached the inbox. Use `--dsn` to request server-side delivery notifications. Silent rejections by M365 are detected where possible and logged as `Tenant Rejection`.

## Requirements

- Python 3.6+ (stdlib only)
- Port 25 outbound access (not blocked by your ISP/firewall)
- A Microsoft 365 tenant with Direct Send configured
```

- [ ] **Step 2: Remove the PowerShell script**

```bash
git rm directsendit.ps1
```

- [ ] **Step 3: Commit README and removal**

```bash
git add README.md
git commit -m "docs: add README, remove deprecated PS1 script"
```

---

### Task 11: Configure remote and push

- [ ] **Step 1: Set remote origin with PAT**

```bash
git remote add origin https://<PAT>@github.com/Wolfandco/DirectSendIt.git
```

- [ ] **Step 2: Rename branch to main and push**

```bash
git branch -m master main
git ls-remote origin  # Verify what's on remote before force-pushing
git push -u origin main --force  # Force required: local history replaces remote
```

> **Note:** `--force` is intentional here — the local history is the authoritative new version (PS1 removed, all new Python files). The remote only has the old PS1. Verify `git ls-remote` output before proceeding.

- [ ] **Step 3: Verify on GitHub**

```bash
gh repo view Wolfandco/DirectSendIt --web
```

---

### Task 12: Run full test suite one final time

- [ ] **Step 1: Run all tests**

```bash
python3 -m pytest tests/ -v
```

Expected: all tests PASS, zero failures

- [ ] **Step 2: Test install script**

```bash
sudo ./install.sh
directsendit --help
```

Expected: help output with all flags listed
