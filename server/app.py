"""FastAPI web app — serves the signing page and handles signature submission."""

from datetime import datetime
from pathlib import Path

from fastapi import FastAPI, Request, HTTPException, Form, UploadFile
from fastapi.responses import HTMLResponse, FileResponse, JSONResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

from server.config import STATIC_DIR, TEMPLATES_DIR, BASE_URL, COMPANY_NAME
from server.database import (
    init_db,
    get_request_by_token,
    update_request_signed,
)
from server.pdf_handler import apply_signature_to_pdf

app = FastAPI(title="Unsupervised HR E-Sign", version="1.0.0")
app.mount("/static", StaticFiles(directory=str(STATIC_DIR)), name="static")
templates = Jinja2Templates(directory=str(TEMPLATES_DIR))


@app.on_event("startup")
async def startup():
    init_db()


@app.get("/", response_class=HTMLResponse)
async def home():
    return HTMLResponse("<h1>Unsupervised HR E-Sign</h1><p>Server is running.</p>")


@app.get("/health")
async def health():
    return {"status": "ok", "service": "e-sign"}


@app.get("/sign/{token}", response_class=HTMLResponse)
async def signing_page(request: Request, token: str):
    """Render the signing page for a given token."""
    signing_request = get_request_by_token(token)

    if not signing_request:
        raise HTTPException(status_code=404, detail="Signing request not found.")

    if signing_request["status"] != "pending":
        return templates.TemplateResponse(
            request=request,
            name="already_signed.html",
            context={
                "signing_request": signing_request,
                "company_name": COMPANY_NAME,
            },
        )

    # Check expiry
    if signing_request["expires_at"]:
        expires = datetime.fromisoformat(signing_request["expires_at"])
        if datetime.utcnow() > expires:
            return templates.TemplateResponse(
                request=request,
                name="expired.html",
                context={
                    "signing_request": signing_request,
                    "company_name": COMPANY_NAME,
                },
            )

    return templates.TemplateResponse(
        request=request,
        name="sign.html",
        context={
            "signing_request": signing_request,
            "company_name": COMPANY_NAME,
            "base_url": BASE_URL,
        },
    )


@app.get("/document/{token}")
async def serve_document(token: str):
    """Serve the unsigned PDF for preview in the signing page."""
    signing_request = get_request_by_token(token)
    if not signing_request:
        raise HTTPException(status_code=404, detail="Not found.")

    doc_path = Path(signing_request["document_path"])
    if not doc_path.exists():
        raise HTTPException(status_code=404, detail="Document not found.")

    return FileResponse(
        str(doc_path),
        media_type="application/pdf",
        filename=signing_request["document_name"],
    )


@app.post("/api/submit-signature")
async def submit_signature(request: Request):
    """Receive the signer's signature and apply it to the document."""
    body = await request.json()

    token = body.get("token")
    signature_data = body.get("signature_data")  # base64 PNG
    signature_type = body.get("signature_type")  # 'typed' or 'drawn'
    signer_name_confirmed = body.get("signer_name")

    if not all([token, signature_data, signature_type]):
        raise HTTPException(status_code=400, detail="Missing required fields.")

    signing_request = get_request_by_token(token)
    if not signing_request:
        raise HTTPException(status_code=404, detail="Signing request not found.")

    if signing_request["status"] != "pending":
        raise HTTPException(status_code=400, detail="Document has already been signed.")

    # Get signer metadata
    signer_ip = request.client.host if request.client else "unknown"
    signer_ua = request.headers.get("user-agent", "unknown")

    # Apply signature to PDF
    doc_stem = Path(signing_request["document_name"]).stem
    output_name = f"{doc_stem}_signed_{signing_request['signer_name'].replace(' ', '_')}"

    try:
        signed_path = apply_signature_to_pdf(
            unsigned_pdf_path=signing_request["document_path"],
            signature_data=signature_data,
            signer_name=signing_request["signer_name"],
            signature_type=signature_type,
            output_name=output_name,
            position="recipient",
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Error applying signature: {str(e)}")

    # Update database
    update_request_signed(
        token=token,
        signature_type=signature_type,
        signed_document_path=signed_path,
        signer_ip=signer_ip,
        signer_user_agent=signer_ua,
    )

    return JSONResponse({
        "status": "success",
        "message": "Document signed successfully.",
        "signer_name": signing_request["signer_name"],
        "signed_at": datetime.utcnow().isoformat(),
    })


@app.get("/signed/{token}")
async def download_signed(token: str):
    """Download the signed document."""
    signing_request = get_request_by_token(token)
    if not signing_request:
        raise HTTPException(status_code=404, detail="Not found.")

    if signing_request["status"] not in ("signed", "countersigned"):
        raise HTTPException(status_code=400, detail="Document not yet signed.")

    path = signing_request.get("countersigned_document_path") or signing_request.get("signed_document_path")
    if not path or not Path(path).exists():
        raise HTTPException(status_code=404, detail="Signed document not found.")

    return FileResponse(str(path), media_type="application/pdf")
