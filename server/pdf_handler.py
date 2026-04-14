import io
import shutil
import subprocess
from pathlib import Path
from typing import Optional
import base64

from PIL import Image
from PyPDF2 import PdfReader, PdfWriter
from reportlab.lib.pagesizes import letter
from reportlab.lib.units import inch
from reportlab.pdfgen import canvas as rl_canvas

from server.config import UNSIGNED_DIR, SIGNED_DIR, OWNER_SIGNATURE_PATH


def copy_to_unsigned(source_path: str, document_name: str) -> str:
    """Copy a document to the unsigned storage. Convert .docx to PDF if needed."""
    source = Path(source_path)
    if not source.exists():
        raise FileNotFoundError(f"Source document not found: {source_path}")

    if source.suffix.lower() == ".docx":
        pdf_path = UNSIGNED_DIR / f"{Path(document_name).stem}.pdf"
        convert_docx_to_pdf(str(source), str(pdf_path))
        return str(pdf_path)
    elif source.suffix.lower() == ".pdf":
        dest = UNSIGNED_DIR / f"{Path(document_name).stem}.pdf"
        shutil.copy2(str(source), str(dest))
        return str(dest)
    else:
        raise ValueError(f"Unsupported file type: {source.suffix}")


def convert_docx_to_pdf(docx_path: str, pdf_path: str):
    """Convert .docx to .pdf using macOS Word or LibreOffice."""
    try:
        from docx2pdf import convert
        convert(docx_path, pdf_path)
        return
    except Exception:
        pass

    # Fallback: LibreOffice
    try:
        output_dir = str(Path(pdf_path).parent)
        subprocess.run(
            ["soffice", "--headless", "--convert-to", "pdf", "--outdir", output_dir, docx_path],
            check=True, capture_output=True, timeout=30,
        )
        # soffice names the output after the input
        lo_output = Path(output_dir) / (Path(docx_path).stem + ".pdf")
        if str(lo_output) != pdf_path:
            lo_output.rename(pdf_path)
        return
    except Exception:
        pass

    raise RuntimeError(
        "Could not convert .docx to PDF. Install docx2pdf or LibreOffice."
    )


def decode_signature_image(signature_data: str) -> Image.Image:
    """Decode a base64 signature data URI to a PIL Image."""
    if "," in signature_data:
        signature_data = signature_data.split(",", 1)[1]
    img_bytes = base64.b64decode(signature_data)
    return Image.open(io.BytesIO(img_bytes))


def create_signature_overlay(
    signature_image: Image.Image,
    page_width: float,
    page_height: float,
    signer_name: str,
    signature_type: str,
    position: str = "recipient",
) -> bytes:
    """Create a PDF overlay with the signature positioned correctly."""
    packet = io.BytesIO()
    c = rl_canvas.Canvas(packet, pagesize=(page_width, page_height))

    # Save signature image to temp bytes
    sig_buffer = io.BytesIO()
    signature_image.save(sig_buffer, format="PNG")
    sig_buffer.seek(0)

    # Determine position — recipient signs lower, owner signs upper block
    if position == "recipient":
        sig_x = 1.2 * inch
        sig_y = 1.8 * inch  # near bottom of last page
    else:  # owner / countersign
        sig_x = 1.2 * inch
        sig_y = 4.2 * inch  # higher up for owner signature block

    # Draw signature image
    from reportlab.lib.utils import ImageReader
    sig_reader = ImageReader(sig_buffer)
    sig_w = 2.5 * inch
    sig_h = 0.8 * inch
    c.drawImage(sig_reader, sig_x, sig_y, width=sig_w, height=sig_h, mask="auto")

    # Draw date below signature
    from datetime import datetime
    date_str = datetime.utcnow().strftime("%B %d, %Y")
    c.setFont("Helvetica", 10)
    c.drawString(sig_x, sig_y - 0.35 * inch, date_str)

    c.save()
    packet.seek(0)
    return packet.read()


def apply_signature_to_pdf(
    unsigned_pdf_path: str,
    signature_data: str,
    signer_name: str,
    signature_type: str,
    output_name: str,
    position: str = "recipient",
) -> str:
    """Apply a signature image to the last page of a PDF."""
    reader = PdfReader(unsigned_pdf_path)
    writer = PdfWriter()

    last_page_idx = len(reader.pages) - 1

    for i, page in enumerate(reader.pages):
        if i == last_page_idx:
            # Get page dimensions
            media_box = page.mediabox
            page_width = float(media_box.width)
            page_height = float(media_box.height)

            # Decode signature
            sig_image = decode_signature_image(signature_data)

            # Create overlay
            overlay_bytes = create_signature_overlay(
                sig_image, page_width, page_height,
                signer_name, signature_type, position,
            )
            overlay_reader = PdfReader(io.BytesIO(overlay_bytes))
            overlay_page = overlay_reader.pages[0]

            # Merge overlay onto the page
            page.merge_page(overlay_page)

        writer.add_page(page)

    # Save
    output_path = SIGNED_DIR / f"{output_name}.pdf"
    with open(str(output_path), "wb") as f:
        writer.write(f)

    return str(output_path)


def apply_countersignature(
    signed_pdf_path: str,
    output_name: str,
) -> str:
    """Apply the owner's saved signature to the document."""
    if not OWNER_SIGNATURE_PATH.exists():
        raise FileNotFoundError(
            f"Owner signature not found at {OWNER_SIGNATURE_PATH}. "
            "Please save your signature as a PNG file there."
        )

    # Load owner signature as base64
    with open(str(OWNER_SIGNATURE_PATH), "rb") as f:
        sig_b64 = base64.b64encode(f.read()).decode()
    signature_data = f"data:image/png;base64,{sig_b64}"

    return apply_signature_to_pdf(
        signed_pdf_path,
        signature_data,
        "Sophie Lemieux",
        "image",
        output_name,
        position="owner",
    )
