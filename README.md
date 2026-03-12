# DirectSendIt

Send email via Microsoft 365 Direct Send (SMTP port 25, no authentication required).

## Requirements

- Python 3.6+ (stdlib only — no pip install needed)
- Port 25 outbound not blocked by your ISP or firewall
- Microsoft 365 tenant with Direct Send configured

## Install

```sh
git clone https://github.com/Wolfandco/DirectSendIt
cd DirectSendIt
sudo ./install.sh
```

After install, `directsendit` is available system-wide.

OR:

Just run it via python:

`python3 directsendit.py`

## Usage

```sh
# Single recipient, HTML body
directsendit -f sender@company.com -t user@company.com -s "Hello" -H body.html -d company-com

# Multiple recipients from file, with plain text fallback
directsendit -f sender@company.com -t recipients.txt -s "Newsletter" -H body.html -T body.txt -d company-com

# With attachment(s)
directsendit -f sender@company.com -t user@company.com -s "Report" -H body.html -a report.pdf -d company-com

# Multiple attachments
directsendit -f sender@company.com -t user@company.com -s "Files" -H body.html -a file1.pdf -a file2.xlsx -d company-com

# Explicit SMTP server (skip --domain)
directsendit -f sender@company.com -t user@company.com -s "Hi" -H body.html -S company-com.mail.protection.outlook.com

# Dry run — validate everything without sending
directsendit -f sender@company.com -t recipients.txt -s "Test" -H body.html -d company-com -r

# Custom log file path
directsendit -f sender@company.com -t user@company.com -s "Hi" -H body.html -d company-com -l results.csv

# Disable logging
directsendit -f sender@company.com -t user@company.com -s "Hi" -H body.html -d company-com -n

# Request DSN delivery notification
directsendit -f sender@company.com -t user@company.com -s "Hi" -H body.html -d company-com -N

# Bulk send with delay between messages
directsendit -f sender@company.com -t recipients.txt -s "Hi" -H body.html -d company-com -D 2
```

## Flags

| Short | Long | Required | Description |
|-------|------|----------|-------------|
| `-f` | `--from` | Yes | Sender email address |
| `-t` | `--to` | Yes | Recipient email address or path to `.txt` file (one per line) |
| `-s` | `--subject` | Yes | Email subject line |
| `-H` | `--html` | One of -H/-T | Path to HTML body file |
| `-T` | `--text` | One of -H/-T | Path to plain text body file |
| `-a` | `--attach` | No | Attachment file path (repeatable for multiple files) |
| `-d` | `--domain` | One of -d/-S | Tenant slug, e.g. `company-com` — constructs SMTP server automatically |
| `-S` | `--server` | One of -d/-S | Explicit SMTP server hostname |
| `-l` | `--log` | No | CSV log file path (default: `email_log_YYYYMMDD_HHMMSS.csv`) |
| `-n` | `--no-log` | No | Disable logging entirely |
| `-D` | `--delay` | No | Seconds to wait between sends for bulk mode (default: 0) |
| `-N` | `--dsn` | No | Request Delivery Status Notification headers |
| `-r` | `--dry-run` | No | Validate inputs and print send plan without sending |

## Recipients File Format

One email address per line. Blank lines and lines starting with `#` are ignored:

```
# Marketing list
alice@company.com
bob@company.com

# Ops team
charlie@company.com
```

## Log Format

Results are written to a CSV with columns: `From, To, Subject, Status, Timestamp, Error`

| Status | Meaning |
|--------|---------|
| `Accepted` | SMTP server accepted the message for delivery |
| `Rejected` | Server returned a 5xx error |
| `Tenant Rejection` | M365-specific rejection (IP not allowlisted, etc.) |
| `Connection Error` | Could not reach the SMTP server |
| `Failed` | Other error |

> **Note on delivery:** `Accepted` means the M365 server accepted the message for queuing — not that it reached the inbox. Use `--dsn` (`-N`) to request server-side delivery notifications.

## Common Errors and Fixes

| Error | Cause | Fix |
|-------|-------|-----|
| `5.7.51 RestrictDomainsToIPAddresses` | Your IP is not allowlisted on the M365 connector | Add your sending IP to the connector in Exchange Admin Center |
| `TenantInboundAttribution` | Direct Send blocked at tenant level | Check M365 connector configuration for your tenant |
| `Mailbox unavailable` | Recipient doesn't exist or is disabled | Verify the recipient address |
| `TLS required` | Tenant requires TLS on port 25 | Use an authenticated relay (SMTP AUTH) instead |
| Connection refused / timeout | Port 25 is blocked | Check ISP/firewall rules; many ISPs block outbound port 25 |
| DNS resolution failed | Wrong `--domain` slug | Check the slug matches your tenant's MX record |

## How Direct Send Works

Direct Send connects to your Microsoft 365 tenant's inbound SMTP endpoint (`<tenant>.mail.protection.outlook.com`) on port 25 without authentication. It can only deliver to mailboxes within that M365 tenant. Your sending IP must be permitted by the tenant's connector configuration in Exchange Admin Center.
