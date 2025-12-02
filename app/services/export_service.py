# app/services/export_service.py

import os
import tempfile
from io import BytesIO

from playwright.async_api import async_playwright
import pypandoc


async def html_to_pdf_bytes(html: str) -> bytes:
    """
    Render the given HTML string to a PDF using Playwright/Chromium.

    This mirrors your previous CLI flow that wrote an HTML file and used
    page.pdf() so the CSS and layout should match your current templates.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        html_path = os.path.join(tmpdir, "resume.html")
        pdf_path = os.path.join(tmpdir, "resume.pdf")

        # Write HTML to a temp file
        with open(html_path, "w", encoding="utf-8") as f:
            f.write(html)

        # Use Playwright to render HTML -> PDF (same config you used before)
        async with async_playwright() as p:
            browser = await p.chromium.launch()
            context = await browser.new_context()
            page = await context.new_page()

            # Use file:// so it behaves like your old export_resume_to_pdf()
            page.goto(f"file://{html_path}")

            page.pdf(
                path=pdf_path,
                format="Letter",
                margin={"top": "0", "bottom": "0", "left": "0", "right": "0"},
                print_background=True,
                prefer_css_page_size=True,
                scale=1.0,
            )

            await browser.close()

        # Read the resulting PDF and return as bytes
        with open(pdf_path, "rb") as f:
            return f.read()


def html_to_docx_bytes(html: str) -> bytes:
    """
    Convert the given HTML string to DOCX using pandoc via pypandoc.
    Layout won't be 100% identical (Word is Word), but structure & text
    will be preserved.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        html_path = os.path.join(tmpdir, "resume.html")
        docx_path = os.path.join(tmpdir, "resume.docx")

        with open(html_path, "w", encoding="utf-8") as f:
            f.write(html)

        # Use pandoc via pypandoc
        pypandoc.convert_file(
            html_path,
            "docx",
            format="html",
            outputfile=docx_path,
            extra_args=["--standalone"],
        )

        with open(docx_path, "rb") as f:
            return f.read()
