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
