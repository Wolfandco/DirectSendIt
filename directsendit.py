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
