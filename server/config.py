import os
from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent
STORAGE_DIR = BASE_DIR / "storage"
DB_PATH = BASE_DIR / "db" / "esign.db"
TEMPLATES_DIR = BASE_DIR / "templates"
STATIC_DIR = BASE_DIR / "static"

UNSIGNED_DIR = STORAGE_DIR / "unsigned"
SIGNED_DIR = STORAGE_DIR / "signed"
SIGNATURES_DIR = STORAGE_DIR / "signatures"

# Cloudflare tunnel URL — set this after tunnel setup
BASE_URL = os.environ.get("ESIGN_BASE_URL", "http://localhost:8420")

# Signing link expiry in days
SIGNING_EXPIRY_DAYS = int(os.environ.get("ESIGN_EXPIRY_DAYS", "14"))

# Owner signature image for countersigning
OWNER_SIGNATURE_PATH = SIGNATURES_DIR / "sophie_signature.png"
OWNER_NAME = "Sophie Lemieux"
OWNER_TITLE = "Owner, People Advisor, Principal Partner Investor"
COMPANY_NAME = "Unsupervised HR"

# Server
HOST = os.environ.get("ESIGN_HOST", "0.0.0.0")
PORT = int(os.environ.get("ESIGN_PORT", "8420"))
