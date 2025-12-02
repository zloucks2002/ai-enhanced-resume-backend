import os
import tempfile
from io import BytesIO

from playwright.async_api import async_playwright
import pypandoc


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


def html_to_docx_bytes(html: str) -> bytes:
    """
    Convert HTML string → DOCX via Pandoc.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        html_path = os.path.join(tmpdir, "resume.html")
        docx_path = os.path.join(tmpdir, "resume.docx")

        with open(html_path, "w", encoding="utf-8") as f:
            f.write(html)

        pypandoc.convert_file(
            html_path,
            "docx",
            format="html",
            outputfile=docx_path,
            extra_args=["--standalone"],
        )

        with open(docx_path, "rb") as f:
            return f.read()
