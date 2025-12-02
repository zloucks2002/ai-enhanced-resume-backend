from fastapi import APIRouter, UploadFile, File, Form
from app.services.resume_service import generate_html_resume_service, parse_resume_file
from app.services.analysis_service import analyze_resume_service
from app.utils.export import export_pdf_bytes, export_docx_bytes
import json

router = APIRouter()


# Generate HTML resume
@router.post("/generate")
async def generate_resume(body: dict):
    return generate_html_resume_service(body)

# Parse uploaded PDF/DOCX
@router.post("/parse")
async def parse_resume(file: UploadFile = File(...)):
    return parse_resume_file(file)

# Analyze with context
@router.post("/analyze-with-context")
async def analyze_with_context(
    file: UploadFile = File(...),
    parsed_json: str = Form(...),
    target_job: str = Form(...),
):
    parsed = json.loads(parsed_json)
    pdf_bytes = await file.read()
    return analyze_resume_service(pdf_bytes, parsed, target_job)

# Export PDF
@router.post("/export/pdf")
async def export_pdf(body: dict):
    html = body.get("html")
    if not html:
        return {"error": "Missing HTML data"}
    pdf_bytes = export_pdf_bytes(html)
    return {
        "pdf_base64": pdf_bytes.decode("utf-8")
    }

# Export DOCX
@router.post("/export/docx")
async def export_docx(body: dict):
    html = body.get("html")
    if not html:
        return {"error": "Missing HTML data"}
    docx_bytes = export_docx_bytes(html)
    return {
        "docx_base64": docx_bytes.decode("utf-8")
    }
