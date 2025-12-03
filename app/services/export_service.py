import os
import tempfile
from io import BytesIO
import subprocess
from playwright.async_api import async_playwright
import pypandoc
from fastapi import HTTPException


async def html_to_pdf_bytes(html: str) -> bytes:
    """
    Render the given HTML string to a PDF using Playwright/Chromium.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        html_path = os.path.join(tmpdir, "resume.html")
        pdf_path = os.path.join(tmpdir, "resume.pdf")

        # Write HTML to a temp file
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(html)

        # Playwright async API
        async with async_playwright() as p:
            browser = await p.chromium.launch(args=["--no-sandbox"])
            context = await browser.new_context()
            page = await context.new_page()

            await page.goto(f"file://{html_path}")

            # THIS WAS YOUR ERROR — page.pdf MUST BE AWAITED
            await page.pdf(
                path=pdf_path,
                format="Letter",
                margin={"top": "0", "bottom": "0", "left": "0", "right": "0"},
                print_background=True,
                prefer_css_page_size=True,
                scale=1.0,
            )

            await browser.close()

        if not os.path.exists(pdf_path):
            raise Exception("PDF was not generated.")

        # Read the resulting PDF
        with open(pdf_path, "rb") as f:
            return f.read()


REFERENCE_DIR = "/app/reference-docx"

REFERENCE_MAP = {
    "corporate": f"{REFERENCE_DIR}/corporate-reference.docx",
    "modern": f"{REFERENCE_DIR}/modern-reference.docx",
    "minimalist": f"{REFERENCE_DIR}/minimalist-reference.docx",
    "creative": f"{REFERENCE_DIR}/creative-reference.docx",
}

async def generate_docx_with_playwright(html: str) -> bytes:
    # 1. Generate PDF using Playwright
    pdf_bytes = await html_to_pdf_bytes(html)

    # 2. Write PDF to temp file
    with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as pdf_file:
        pdf_file.write(pdf_bytes)
        pdf_path = pdf_file.name

    # 3. Convert PDF → DOCX with pandoc
    docx_path = pdf_path.replace(".pdf", ".docx")

    try:
        subprocess.run(
            ["pandoc", pdf_path, "-o", docx_path],
            check=True
        )
    except subprocess.CalledProcessError as e:
        raise HTTPException(status_code=500, detail=f"Pandoc failed: {str(e)}")

    # 4. Read DOCX
    try:
        with open(docx_path, "rb") as f:
            return f.read()
    except FileNotFoundError:
        raise HTTPException(status_code=500, detail="DOCX was not generated.")

