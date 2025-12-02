# app/services/export_service.py

from weasyprint import HTML
import pypandoc

def html_to_pdf(html_path: str, pdf_path: str):
    """
    Convert HTML to PDF using WeasyPrint.
    """
    HTML(html_path).write_pdf(pdf_path)


def html_to_docx(html_path: str, docx_path: str):
    """
    Convert HTML to DOCX using Pandoc.
    """
    pypandoc.convert_file(
        html_path,
        "docx",
        format="html",
        outputfile=docx_path,
        extra_args=["--standalone"]
    )
