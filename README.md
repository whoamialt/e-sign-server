<p align="center">
  <img src="assets/banner.svg" alt="E-Sign Server" width="600" />
</p>

<h1 align="center">E-Sign Server</h1>

<p align="center">
  <a href="https://github.com/whoamialt/e-sign-server/releases/tag/v1.0.0"><img src="https://img.shields.io/badge/release-v1.0.0-blue?style=for-the-badge" alt="Release" /></a>
  <a href="https://github.com/whoamialt/e-sign-server/blob/main/LICENSE"><img src="https://img.shields.io/badge/license-MIT-green?style=for-the-badge" alt="MIT License" /></a>
  <a href="https://modelcontextprotocol.io"><img src="https://img.shields.io/badge/MCP-compatible-purple?style=for-the-badge" alt="MCP Compatible" /></a>
  <a href="https://github.com/whoamialt"><img src="https://img.shields.io/badge/built%20by-Unsupervised%20HR-black?style=for-the-badge" alt="Built by Unsupervised HR" /></a>
</p>

**Self-hosted document signing server that replaces DocuSign.** Built with [FastAPI](https://fastapi.tiangolo.com/) and the [Model Context Protocol](https://modelcontextprotocol.io), designed to be operated entirely from [Claude Code](https://docs.anthropic.com/en/docs/claude-code) — send documents for signature, track status, countersign, and audit, all without leaving the terminal.

<table>
<tr>
<td><b>MCP-Native Workflow</b></td>
<td>Send, track, remind, countersign, and audit documents using six purpose-built <a href="#-mcp-tools">MCP tools</a> — no web dashboard needed.</td>
</tr>
<tr>
<td><b>Draw or Type Signatures</b></td>
<td>Signers choose between a canvas-based hand-drawn signature or a typed signature with real-time preview, all rendered in the browser.</td>
</tr>
<tr>
<td><b>PDF Processing Pipeline</b></td>
<td>Accepts <code>.pdf</code> and <code>.docx</code> files. DOCX files are auto-converted. Signatures are composited onto the final page using <a href="https://docs.reportlab.com/">ReportLab</a> and <a href="https://pypdf2.readthedocs.io/">PyPDF2</a>.</td>
</tr>
<tr>
<td><b>Zero-Config Public URLs</b></td>
<td>Cloudflare Tunnel generates a public signing link on every startup — no DNS, no nginx, no port forwarding.</td>
</tr>
<tr>
<td><b>Full Audit Trail</b></td>
<td>Every action is logged to SQLite with timestamps, IP addresses, and user agents for compliance reporting.</td>
</tr>
<tr>
<td><b>Automatic Countersigning</b></td>
<td>Owner signature applied programmatically from a saved PNG — one MCP tool call to fully execute a document.</td>
</tr>
</table>

---

## Quick Install

```bash
# Clone the repo
git clone https://github.com/whoamialt/e-sign-server.git
cd e-sign-server

# Install dependencies (requires Python 3.12+ and uv)
uv sync

# Copy environment template
cp .env.example .env
```

> **Requirements:** Python 3.12+, [uv](https://docs.astral.sh/uv/), [cloudflared](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/) (for public URLs)

---

## Getting Started

```bash
# Start the server + tunnel in one command
./start.sh

# Or run the server alone
uv run python run.py                          # Start on http://localhost:8420

# Or start just the MCP server
uv run python -m mcp_server.server            # For Claude Code integration
```

Once running, the server exposes:

| Endpoint | Purpose |
|----------|---------|
| `GET /` | Server status page |
| `GET /health` | Health check (used by scheduled task) |
| `GET /sign/{token}` | Signing page for recipients |
| `GET /document/{token}` | PDF preview for the signing page |
| `POST /api/submit-signature` | Signature submission API |
| `GET /signed/{token}` | Download the signed document |

---

## How It Works

```
 ┌─────────────┐     ┌──────────────┐     ┌──────────────┐
 │ Claude Code  │────▶│  MCP Server  │────▶│  FastAPI App  │
 │  (terminal)  │     │  (e-sign)    │     │  (port 8420)  │
 └─────────────┘     └──────────────┘     └──────┬───────┘
                                                  │
                           ┌──────────────────────┼──────────────────────┐
                           │                      │                      │
                    ┌──────▼──────┐       ┌───────▼──────┐      ┌───────▼───────┐
                    │   SQLite    │       │  PDF Engine   │      │  Cloudflare   │
                    │  (audit +   │       │ (ReportLab +  │      │   Tunnel      │
                    │  requests)  │       │  PyPDF2)      │      │ (public URL)  │
                    └─────────────┘       └──────────────┘      └───────────────┘
```

1. Use `send_for_signature` in Claude Code → generates a signing link + email draft
2. Send the email via Gmail MCP
3. Signer clicks the link, reviews the PDF, and signs (draw or type)
4. Use `check_signatures` to monitor status
5. Use `countersign` to apply your signature automatically
6. Send the fully executed copy back via Gmail

---

## 🔧 MCP Tools

The MCP server (`mcp_server/server.py`) exposes six tools to Claude Code:

| Tool | Description |
|------|-------------|
| `send_for_signature` | Prepare a document, generate a signing link, and draft the email body |
| `check_signatures` | View all requests with stats (pending / signed / countersigned / cancelled) |
| `remind_signer` | Generate a follow-up email for overdue signatures |
| `countersign` | Apply owner's saved signature to complete the document |
| `cancel_signing_request` | Invalidate a pending signing link |
| `get_signing_audit_log` | Full audit trail for any request |

### MCP Configuration

Add to your Claude Code MCP settings:

```json
{
  "mcpServers": {
    "e-sign": {
      "command": "uv",
      "args": ["run", "python", "-m", "mcp_server.server"],
      "cwd": "~/e-sign-server"
    }
  }
}
```

---

## Project Structure

```
e-sign-server/
├── server/
│   ├── app.py              # FastAPI routes and signing page logic
│   ├── config.py           # Environment config and paths
│   ├── database.py         # SQLite operations and audit logging
│   └── pdf_handler.py      # PDF processing, signature overlay, DOCX conversion
├── mcp_server/
│   └── server.py           # MCP tools for Claude Code integration
├── templates/
│   ├── sign.html           # Main signing page
│   ├── already_signed.html # Post-signature confirmation
│   └── expired.html        # Expired link page
├── static/
│   ├── css/style.css       # Signing page styles
│   └── js/sign.js          # Signature pad and submission logic
├── storage/
│   ├── unsigned/           # Source documents awaiting signature
│   ├── signed/             # Recipient-signed documents
│   └── signatures/         # Saved signature images (owner PNG)
├── db/                     # SQLite database (gitignored)
├── run.py                  # Server entry point
├── start.sh                # One-command startup (server + tunnel)
└── pyproject.toml          # Dependencies and project metadata
```

---

## 📦 Stack

| Component | Technology |
|-----------|-----------|
| Server | [FastAPI](https://fastapi.tiangolo.com/) + [Uvicorn](https://www.uvicorn.org/) |
| PDF Processing | [PyPDF2](https://pypdf2.readthedocs.io/), [ReportLab](https://docs.reportlab.com/), [Pillow](https://pillow.readthedocs.io/) |
| Document Conversion | [docx2pdf](https://github.com/AlJohri/docx2pdf) / LibreOffice fallback |
| Database | SQLite3 (WAL mode) |
| MCP Server | [FastMCP](https://github.com/jlowin/fastmcp) (mcp SDK) |
| Tunnel | [Cloudflare `cloudflared`](https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/) |
| Runtime | Python 3.12+ via [uv](https://docs.astral.sh/uv/) |

---

## Environment Variables

| Variable | Default | Description |
|----------|---------|-------------|
| `ESIGN_BASE_URL` | `http://localhost:8420` | Public URL (set automatically by `start.sh`) |
| `ESIGN_PORT` | `8420` | Server port |
| `ESIGN_HOST` | `0.0.0.0` | Server bind address |
| `ESIGN_EXPIRY_DAYS` | `14` | Default signing link expiry |

---

## Contributing

Contributions are welcome. Please open an issue first to discuss what you'd like to change.

```bash
# Fork and clone
git clone https://github.com/your-username/e-sign-server.git
cd e-sign-server

# Install dev dependencies
uv sync

# Run the server locally
uv run python run.py
```

---

## License

[MIT](LICENSE)

---

<p align="center">
  Built by <a href="https://github.com/whoamialt">Sophie Lemieux</a> at <b>Unsupervised HR</b>
</p>
