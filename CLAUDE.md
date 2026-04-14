# E-Sign Server — Unsupervised HR

Self-hosted document signing tool that replaces DocuSign.

## Architecture
- `server/` — FastAPI web app serving the signing pages
- `mcp_server/` — MCP server providing tools to Claude Code
- `templates/` — HTML templates for the signing experience
- `static/` — CSS and JS assets
- `storage/` — Document and signature storage

## How it works
1. Use the `send_for_signature` tool → generates a signing link + email content
2. Send the email using Gmail MCP
3. Signer clicks the link, reviews the PDF, and signs (type or draw)
4. Use `check_signatures` to monitor status
5. Use `countersign` to apply Sophie's signature automatically
6. Send the fully executed copy back via Gmail

## Running the server
```bash
cd ~/e-sign-server
python run.py
```

## Cloudflare Tunnel
```bash
cloudflared tunnel run esign
```

## Key env vars
- `ESIGN_BASE_URL` — public URL from Cloudflare tunnel
- `ESIGN_PORT` — server port (default 8420)
- `ESIGN_EXPIRY_DAYS` — signing link expiry (default 14)
