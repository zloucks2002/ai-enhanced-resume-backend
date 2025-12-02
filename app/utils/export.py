import base64
import tempfile
import subprocess
from weasyprint import HTML

# PDF EXPORT (WeasyPrint)
def export_pdf_bytes(html_string: str) -> bytes:
    # Create temporary HTML file
    with tempfile.NamedTemporaryFile(delete=False, suffix=".html", mode="w", encoding="utf-8") as f:
        f.write(html_string)
        html_path = f.name

    # Render PDF
    pdf_bytes = HTML(html_path).write_pdf()
    return base64.b64encode(pdf_bytes)

# DOCX EXPORT (Pandoc)
def export_docx_bytes(html_string: str) -> bytes:
    # Temporary files
    with tempfile.NamedTemporaryFile(delete=False, suffix=".html", mode="w", encoding="utf-8") as f:
        f.write(html_string)
        html_path = f.name

    docx_path = html_path.replace(".html", ".docx")

    # Pandoc command
    subprocess.run([
        "pandoc",
        html_path,
        "-o",
        docx_path,
        "--standalone"
    ], check=True)

    # Read DOCX file
    with open(docx_path, "rb") as f:
        return base64.b64encode(f.read())
