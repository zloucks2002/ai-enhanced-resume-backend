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

async def html_to_docx_bytes(html_content: str, style_choice: str = "corporate"):
    reference_path = REFERENCE_MAP.get(style_choice.lower())

    if not reference_path or not os.path.exists(reference_path):
        raise FileNotFoundError(f"Reference DOCX not found for style: {style_choice}")

    with tempfile.NamedTemporaryFile(delete=False, suffix=".html") as temp_html:
        temp_html.write(html_content.encode("utf-8"))
        temp_html_path = temp_html.name

    with tempfile.NamedTemporaryFile(delete=False, suffix=".docx") as temp_docx:
        temp_docx_path = temp_docx.name

    try:
        subprocess.run(
            [
                "pandoc",
                temp_html_path,
                "--from=html",
                "--to=docx",
                f"--reference-doc={reference_path}",
                "--output", temp_docx_path
            ],
            check=True
        )

        with open(temp_docx_path, "rb") as file:
            return file.read()

    finally:
        os.unlink(temp_html_path)
        os.unlink(temp_docx_path)