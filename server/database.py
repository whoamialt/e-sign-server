import sqlite3
import uuid
from datetime import datetime, timedelta
from pathlib import Path
from typing import Optional

from server.config import DB_PATH, SIGNING_EXPIRY_DAYS


def get_connection() -> sqlite3.Connection:
    conn = sqlite3.connect(str(DB_PATH))
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = get_connection()
    conn.executescript("""
        CREATE TABLE IF NOT EXISTS signing_requests (
            id TEXT PRIMARY KEY,
            token TEXT UNIQUE NOT NULL,
            document_name TEXT NOT NULL,
            document_path TEXT NOT NULL,
            signer_name TEXT NOT NULL,
            signer_email TEXT NOT NULL,
            sender_name TEXT DEFAULT 'Sophie Lemieux',
            status TEXT DEFAULT 'pending',
            created_at TEXT DEFAULT (datetime('now')),
            expires_at TEXT,
            signed_at TEXT,
            countersigned_at TEXT,
            signer_ip TEXT,
            signer_user_agent TEXT,
            signature_type TEXT,
            signed_document_path TEXT,
            countersigned_document_path TEXT,
            notes TEXT
        );

        CREATE TABLE IF NOT EXISTS audit_log (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            request_id TEXT,
            action TEXT,
            details TEXT,
            ip_address TEXT,
            timestamp TEXT DEFAULT (datetime('now')),
            FOREIGN KEY (request_id) REFERENCES signing_requests(id)
        );
    """)
    conn.commit()
    conn.close()


def create_signing_request(
    document_name: str,
    document_path: str,
    signer_name: str,
    signer_email: str,
    sender_name: str = "Sophie Lemieux",
    expiry_days: int = SIGNING_EXPIRY_DAYS,
    notes: Optional[str] = None,
) -> dict:
    request_id = str(uuid.uuid4())
    token = str(uuid.uuid4())
    expires_at = (datetime.utcnow() + timedelta(days=expiry_days)).isoformat()

    conn = get_connection()
    conn.execute(
        """INSERT INTO signing_requests
           (id, token, document_name, document_path, signer_name, signer_email,
            sender_name, status, expires_at, notes)
           VALUES (?, ?, ?, ?, ?, ?, ?, 'pending', ?, ?)""",
        (request_id, token, document_name, document_path, signer_name,
         signer_email, sender_name, expires_at, notes),
    )
    conn.execute(
        "INSERT INTO audit_log (request_id, action, details) VALUES (?, ?, ?)",
        (request_id, "created", f"Signing request created for {signer_name}"),
    )
    conn.commit()
    conn.close()

    return {
        "id": request_id,
        "token": token,
        "document_name": document_name,
        "signer_name": signer_name,
        "signer_email": signer_email,
        "status": "pending",
        "expires_at": expires_at,
    }


def get_request_by_token(token: str) -> Optional[dict]:
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM signing_requests WHERE token = ?", (token,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def get_request_by_id(request_id: str) -> Optional[dict]:
    conn = get_connection()
    row = conn.execute(
        "SELECT * FROM signing_requests WHERE id = ?", (request_id,)
    ).fetchone()
    conn.close()
    return dict(row) if row else None


def update_request_signed(
    token: str,
    signature_type: str,
    signed_document_path: str,
    signer_ip: str,
    signer_user_agent: str,
):
    conn = get_connection()
    conn.execute(
        """UPDATE signing_requests
           SET status = 'signed',
               signed_at = datetime('now'),
               signature_type = ?,
               signed_document_path = ?,
               signer_ip = ?,
               signer_user_agent = ?
           WHERE token = ?""",
        (signature_type, signed_document_path, signer_ip, signer_user_agent, token),
    )
    request = get_request_by_token(token)
    if request:
        conn.execute(
            "INSERT INTO audit_log (request_id, action, details, ip_address) VALUES (?, ?, ?, ?)",
            (request["id"], "signed", f"Document signed via {signature_type}", signer_ip),
        )
    conn.commit()
    conn.close()


def update_request_countersigned(request_id: str, countersigned_path: str):
    conn = get_connection()
    conn.execute(
        """UPDATE signing_requests
           SET status = 'countersigned',
               countersigned_at = datetime('now'),
               countersigned_document_path = ?
           WHERE id = ?""",
        (countersigned_path, request_id),
    )
    conn.execute(
        "INSERT INTO audit_log (request_id, action, details) VALUES (?, ?, ?)",
        (request_id, "countersigned", "Owner countersignature applied"),
    )
    conn.commit()
    conn.close()


def get_all_requests(status: Optional[str] = None) -> list:
    conn = get_connection()
    if status:
        rows = conn.execute(
            "SELECT * FROM signing_requests WHERE status = ? ORDER BY created_at DESC",
            (status,),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM signing_requests ORDER BY created_at DESC"
        ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def get_audit_log(request_id: str) -> list:
    conn = get_connection()
    rows = conn.execute(
        "SELECT * FROM audit_log WHERE request_id = ? ORDER BY timestamp",
        (request_id,),
    ).fetchall()
    conn.close()
    return [dict(r) for r in rows]


def cancel_request(request_id: str):
    conn = get_connection()
    conn.execute(
        "UPDATE signing_requests SET status = 'cancelled' WHERE id = ?",
        (request_id,),
    )
    conn.execute(
        "INSERT INTO audit_log (request_id, action, details) VALUES (?, ?, ?)",
        (request_id, "cancelled", "Signing request cancelled"),
    )
    conn.commit()
    conn.close()
