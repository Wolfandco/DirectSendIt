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


# ---------------------------------------------------------------------------
# Task 3: Recipient list reader tests
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Task 4: MIME email builder tests
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Task 5: M365 error classification tests
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Task 6: SMTP sender tests
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Task 7: CSV logger tests
# ---------------------------------------------------------------------------

import csv


class TestLogger:
    def test_logger_creates_file_with_header(self, mod, tmp_path):
        log_path = tmp_path / "log.csv"
        logger = mod.CsvLogger(str(log_path))
        logger.close()
        rows = list(csv.DictReader(log_path.open()))
        assert rows == []
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


# ---------------------------------------------------------------------------
# Task 8: Dry run tests
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Task 9: resolve_smtp_server tests
# ---------------------------------------------------------------------------

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


# ---------------------------------------------------------------------------
# Inline body text tests
# ---------------------------------------------------------------------------

class TestInlineBody:
    def test_inline_text_body_used_directly(self, mod, tmp_path):
        """--text with a non-file string is used as inline content."""
        args = mod.parse_args([
            "-f", "a@b.com", "-t", "c@d.com", "-s", "Hi",
            "-T", "Hello, this is the message body.",
            "-d", "contoso-com",
        ])
        # Value passes through — main() will detect it's not a file
        assert args.text == "Hello, this is the message body."

    def test_inline_html_body_used_directly(self, mod, tmp_path):
        """--html with a non-file string is used as inline HTML."""
        args = mod.parse_args([
            "-f", "a@b.com", "-t", "c@d.com", "-s", "Hi",
            "-H", "<p>Hello <b>world</b></p>",
            "-d", "contoso-com",
        ])
        assert args.html == "<p>Hello <b>world</b></p>"

    def test_file_body_still_read_from_disk(self, mod, tmp_path):
        """--text with an existing file path still reads the file."""
        body = tmp_path / "body.txt"
        body.write_text("File content here")
        args = mod.parse_args([
            "-f", "a@b.com", "-t", "c@d.com", "-s", "Hi",
            "-T", str(body),
            "-d", "contoso-com",
        ])
        assert args.text == str(body)

    def test_inline_text_builds_valid_message(self, mod):
        """Inline text string produces a valid MIME message."""
        msg = mod.build_message(
            from_addr="a@b.com",
            to="c@d.com",
            subject="Test",
            html_content=None,
            text_content="Hello, this is plain text.",
            attachments=[],
            dsn=False,
        )
        assert msg["Subject"] == "Test"
        assert "Hello, this is plain text." in msg.get_payload(decode=True).decode()

    def test_inline_html_builds_valid_message(self, mod):
        """Inline HTML string produces a valid MIME message."""
        msg = mod.build_message(
            from_addr="a@b.com",
            to="c@d.com",
            subject="Test",
            html_content="<p>Hello <b>world</b></p>",
            text_content=None,
            attachments=[],
            dsn=False,
        )
        assert "<p>Hello <b>world</b></p>" in msg.get_payload(decode=True).decode()

    def test_dry_run_shows_inline_label(self, mod, tmp_path, capsys):
        """dry_run_report shows [inline text] when body value is not a file."""
        mod.dry_run_report(
            smtp_server="x.mail.protection.outlook.com",
            from_addr="a@b.com",
            recipients=["c@d.com"],
            subject="Hi",
            html_path="<p>inline html</p>",
            text_path=None,
            attachments=[],
            dsn=False,
            log_path=None,
            delay=0,
        )
        out = capsys.readouterr().out
        assert "[inline text]" in out

    def test_dry_run_shows_filename_for_file(self, mod, tmp_path, capsys):
        """dry_run_report shows file path when body value is an existing file."""
        html = tmp_path / "body.html"
        html.write_text("<p>x</p>")
        mod.dry_run_report(
            smtp_server="x.mail.protection.outlook.com",
            from_addr="a@b.com",
            recipients=["c@d.com"],
            subject="Hi",
            html_path=str(html),
            text_path=None,
            attachments=[],
            dsn=False,
            log_path=None,
            delay=0,
        )
        out = capsys.readouterr().out
        assert "body.html" in out
        assert "[inline text]" not in out
