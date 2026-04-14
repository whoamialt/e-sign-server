"""
MCP Server for Unsupervised HR E-Sign.

Provides tools for sending documents for signature, checking status,
sending reminders, and countersigning.
"""

import json
import sys
import os
from pathlib import Path
from typing import Optional

# Add project root to path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from mcp.server.fastmcp import FastMCP
from server.config import BASE_URL, COMPANY_NAME, OWNER_NAME
from server.database import (
    init_db,
    create_signing_request,
    get_all_requests,
    get_request_by_id,
    get_audit_log,
    cancel_request,
    update_request_countersigned,
)
from server.pdf_handler import copy_to_unsigned, apply_countersignature

# Initialize
init_db()

mcp = FastMCP(
    "e-sign",
    version="1.0.0",
    description="Unsupervised HR document signing tools",
)


@mcp.tool()
def send_for_signature(
    document_path: str,
    signer_name: str,
    signer_email: str,
    document_name: Optional[str] = None,
    notes: Optional[str] = None,
    expiry_days: int = 14,
) -> str:
    """
    Prepare a document for signing and generate a signing link.

    Args:
        document_path: Absolute path to the .docx or .pdf file to be signed
        signer_name: Full name of the person who needs to sign
        signer_email: Email address of the signer
        document_name: Display name for the document (defaults to filename)
        notes: Optional notes about this signing request
        expiry_days: Number of days before the signing link expires (default 14)

    Returns:
        JSON with the signing link, email subject, and suggested email body.
        Use the Gmail tool to send the email with this content.
    """
    path = Path(document_path)
    if not path.exists():
        return json.dumps({"error": f"File not found: {document_path}"})

    doc_name = document_name or path.name

    try:
        # Copy/convert document to unsigned storage
        pdf_path = copy_to_unsigned(document_path, doc_name)
    except Exception as e:
        return json.dumps({"error": f"Failed to process document: {str(e)}"})

    # Create signing request
    request = create_signing_request(
        document_name=doc_name,
        document_path=pdf_path,
        signer_name=signer_name,
        signer_email=signer_email,
        sender_name=OWNER_NAME,
        expiry_days=expiry_days,
        notes=notes,
    )

    signing_link = f"{BASE_URL}/sign/{request['token']}"

    # Prepare email content
    email_subject = f"Signature Required: {doc_name} - {COMPANY_NAME}"
    email_body = f"""Hi {signer_name.split()[0]},

I've prepared a document for your review and signature:

Document: {doc_name}

Please review and sign the document using the secure link below:

{signing_link}

This link will expire on {request['expires_at'][:10]}.

If you have any questions, feel free to reply to this email.

Best,
{OWNER_NAME}
{COMPANY_NAME}"""

    return json.dumps({
        "status": "success",
        "request_id": request["id"],
        "signing_link": signing_link,
        "signer_name": signer_name,
        "signer_email": signer_email,
        "document_name": doc_name,
        "expires_at": request["expires_at"],
        "email_subject": email_subject,
        "email_body": email_body,
        "instruction": "Use the Gmail MCP tool to send this email to the signer.",
    })


@mcp.tool()
def check_signatures(status: Optional[str] = None) -> str:
    """
    Check the status of all signing requests.

    Args:
        status: Filter by status - 'pending', 'signed', 'countersigned', 'cancelled', or None for all

    Returns:
        Summary of all signing requests and their statuses.
    """
    requests = get_all_requests(status)

    if not requests:
        filter_msg = f" with status '{status}'" if status else ""
        return json.dumps({"message": f"No signing requests found{filter_msg}.", "requests": []})

    summary = []
    for r in requests:
        summary.append({
            "id": r["id"],
            "document": r["document_name"],
            "signer": r["signer_name"],
            "email": r["signer_email"],
            "status": r["status"],
            "created": r["created_at"],
            "signed_at": r["signed_at"],
            "expires_at": r["expires_at"],
            "signing_link": f"{BASE_URL}/sign/{r['token']}",
        })

    # Stats
    statuses = [r["status"] for r in requests]
    stats = {
        "total": len(requests),
        "pending": statuses.count("pending"),
        "signed": statuses.count("signed"),
        "countersigned": statuses.count("countersigned"),
        "cancelled": statuses.count("cancelled"),
    }

    return json.dumps({"stats": stats, "requests": summary}, indent=2)


@mcp.tool()
def remind_signer(request_id: str) -> str:
    """
    Generate a reminder email for a pending signing request.

    Args:
        request_id: The ID of the signing request to send a reminder for

    Returns:
        Email content for the reminder. Use Gmail MCP to send it.
    """
    request = get_request_by_id(request_id)
    if not request:
        return json.dumps({"error": "Signing request not found."})

    if request["status"] != "pending":
        return json.dumps({"error": f"Request is already {request['status']}, no reminder needed."})

    signing_link = f"{BASE_URL}/sign/{request['token']}"
    first_name = request["signer_name"].split()[0]

    email_subject = f"Reminder: Signature Required - {request['document_name']}"
    email_body = f"""Hi {first_name},

Just a friendly reminder that the following document is awaiting your signature:

Document: {request['document_name']}

You can review and sign it here:

{signing_link}

This link expires on {request['expires_at'][:10]}.

Let me know if you have any questions.

Best,
{OWNER_NAME}
{COMPANY_NAME}"""

    return json.dumps({
        "status": "reminder_ready",
        "signer_email": request["signer_email"],
        "email_subject": email_subject,
        "email_body": email_body,
        "instruction": "Use the Gmail MCP tool to send this reminder email.",
    })


@mcp.tool()
def countersign(request_id: str) -> str:
    """
    Apply Sophie's saved signature to a document that has been signed by the recipient.
    This completes the signing process.

    Args:
        request_id: The ID of the signing request to countersign

    Returns:
        Status of the countersigning and path to the fully executed document.
    """
    request = get_request_by_id(request_id)
    if not request:
        return json.dumps({"error": "Signing request not found."})

    if request["status"] != "signed":
        return json.dumps({
            "error": f"Cannot countersign. Current status: {request['status']}. "
                     "Document must be signed by recipient first."
        })

    signed_path = request["signed_document_path"]
    if not signed_path or not Path(signed_path).exists():
        return json.dumps({"error": "Signed document file not found."})

    try:
        doc_stem = Path(request["document_name"]).stem
        output_name = f"{doc_stem}_fully_executed"
        countersigned_path = apply_countersignature(signed_path, output_name)
    except FileNotFoundError as e:
        return json.dumps({"error": str(e)})
    except Exception as e:
        return json.dumps({"error": f"Failed to countersign: {str(e)}"})

    update_request_countersigned(request_id, countersigned_path)

    return json.dumps({
        "status": "success",
        "message": "Document has been countersigned. Fully executed copy is ready.",
        "document": request["document_name"],
        "signer": request["signer_name"],
        "countersigned_document": countersigned_path,
        "instruction": "You can now send the fully executed copy to the signer via Gmail if needed.",
    })


@mcp.tool()
def cancel_signing_request(request_id: str) -> str:
    """
    Cancel a pending signing request. The signing link will no longer work.

    Args:
        request_id: The ID of the signing request to cancel
    """
    request = get_request_by_id(request_id)
    if not request:
        return json.dumps({"error": "Signing request not found."})

    if request["status"] != "pending":
        return json.dumps({"error": f"Cannot cancel. Current status: {request['status']}"})

    cancel_request(request_id)
    return json.dumps({
        "status": "cancelled",
        "document": request["document_name"],
        "signer": request["signer_name"],
    })


@mcp.tool()
def get_signing_audit_log(request_id: str) -> str:
    """
    Get the full audit trail for a signing request.

    Args:
        request_id: The ID of the signing request
    """
    request = get_request_by_id(request_id)
    if not request:
        return json.dumps({"error": "Signing request not found."})

    log = get_audit_log(request_id)

    return json.dumps({
        "document": request["document_name"],
        "signer": request["signer_name"],
        "current_status": request["status"],
        "audit_trail": log,
    }, indent=2)


if __name__ == "__main__":
    mcp.run()
