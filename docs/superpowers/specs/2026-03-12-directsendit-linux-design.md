# DirectSendIt Linux Port — Design Spec
**Date:** 2026-03-12

## Overview

Port the existing PowerShell `directsendit.ps1` to a Python-based CLI tool for Linux. The tool uses Microsoft 365 Direct Send (SMTP, port 25, no authentication) to deliver emails directly via the tenant's MX endpoint. The PS1 file will be removed upon completion.

---

## Architecture

```
directsendit/
├── directsendit.py     # Main Python script (all logic)
├── directsendit        # Shell wrapper: exec python3 ./directsendit.py "$@"
├── install.sh          # Copies wrapper to /usr/local/bin, sets +x
└── README.md           # Usage examples
```

The shell wrapper enables calling `directsendit` as a plain command after install. No pip, no venv — only Python 3 stdlib required.

---

## CLI Flags

| Short | Long | Required | Description |
|---|---|---|---|
| `-f` | `--from` | Yes | Sender email address |
| `-t` | `--to` | Yes | Single email OR path to `.txt` file (one email per line) |
| `-s` | `--subject` | Yes | Email subject line |
| `-H` | `--html` | One of -H/-T | Path to HTML body file |
| `-T` | `--text` | One of -H/-T | Path to plain text body file |
| `-a` | `--attach` | No | Attachment path (repeatable) |
| `-d` | `--domain` | One of -d/-S | Tenant slug (e.g. `contoso-com`) — builds SMTP server automatically |
| `-S` | `--server` | One of -d/-S | Explicit SMTP server override |
| `-l` | `--log` | No | Log file path (default: `email_log_YYYYMMDD_HHMMSS.csv`) |
| `-n` | `--no-log` | No | Disable logging entirely |
| `-D` | `--delay` | No | Seconds between sends for bulk (default: 0) |
| `-N` | `--dsn` | No | Request Delivery Status Notification from server |
| `-r` | `--dry-run` | No | Validate inputs and print plan, no emails sent |

---

## Email Building

Every email is built as proper MIME:

- `multipart/mixed` (outer, when attachments present)
  - `multipart/alternative` (inner)
    - `text/plain` (from `--text`)
    - `text/html` (from `--html`)
  - attachments (from `--attach`)

When only one of `--html` or `--text` is provided, the structure is simplified accordingly.

When `--dsn` is set, the `Return-Receipt-To` and `Disposition-Notification-To` headers are added requesting server-side delivery confirmation.

---

## Recipient Handling

`--to` accepts either:
- A single email address (e.g. `user@example.com`)
- A path to a plain text file with one email per line (blank lines and lines starting with `#` are skipped)

No per-recipient variable substitution. Email body is the same for all recipients.

---

## Delivery Status & Logging

**Important:** SMTP `250 OK` only confirms the server *accepted* the message for queuing — not that it was delivered. Status values reflect this:

| Status | Meaning |
|---|---|
| `Accepted` | Server returned 250 OK |
| `Rejected` | Server returned 5xx error |
| `Tenant Rejection` | M365-specific rejection codes detected |
| `Connection Error` | Could not reach SMTP server |
| `Failed` | Other SMTP or runtime error |

### CSV Log Format

```
From,To,Subject,Status,Timestamp,Error
sender@co.com,user@co.com,"Hello",Accepted,2026-03-12 09:30:00,
sender@co.com,bad@co.com,"Hello",Tenant Rejection,2026-03-12 09:30:01,"5.7.51 ..."
```

Log defaults to `email_log_YYYYMMDD_HHMMSS.csv` in current directory. Use `--log <path>` to specify. Use `--no-log` to suppress entirely.

---

## M365-Specific Error Handling

| Pattern | Human-readable message |
|---|---|
| `5.7.51` / `RestrictDomainsToIPAddresses` | Tenant rejects unauthenticated relay — your M365 connector may require IP allowlisting |
| `TenantInboundAttribution` | Direct Send blocked — check that your sending IP is permitted for this tenant |
| `Mailbox unavailable` | Recipient mailbox not found or disabled in this tenant |
| `5.7.64` | TLS required by tenant — port 25 plain-text rejected |
| Connection refused / timeout | Could not reach SMTP server — port 25 may be blocked by your ISP or firewall |
| DNS resolution failure | Could not resolve SMTP server — check your --domain or --server value |

---

## Dry Run

`--dry-run` / `-r` will:
- Validate all file paths exist
- Validate email address formats
- Print the full send plan (server, sender, recipients, attachments, body files)
- Exit without sending or writing a log

---

## Install

```sh
chmod +x install.sh
sudo ./install.sh
```

Copies `directsendit` shell wrapper to `/usr/local/bin/directsendit`. The Python script stays in its original directory, referenced by absolute path in the wrapper.

---

## Removal of PS1

`directsendit.ps1` will be deleted from the repository as part of this implementation.
