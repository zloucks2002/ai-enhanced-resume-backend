from fastapi import APIRouter, UploadFile, File, Form
from fastapi.responses import FileResponse
from app.services.resume_service import generate_html_resume_service, parse_resume_file
from app.services.analysis_service import analyze_resume_service
from app.services.export_service import html_to_pdf, html_to_docx
import json
import uuid

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

@router.post("/export/pdf")
async def export_pdf(file: UploadFile = File(...)):
    html_bytes = await file.read()

    temp_html = f"/tmp/{uuid.uuid4()}.html"
    temp_pdf = f"/tmp/{uuid.uuid4()}.pdf"

    with open(temp_html, "wb") as f:
        f.write(html_bytes)

    # Convert HTML → PDF
    html_to_pdf(temp_html, temp_pdf)

    return FileResponse(
        temp_pdf,
        media_type="application/pdf",
        filename="resume.pdf"
    )


@router.post("/export/docx")
async def export_docx(file: UploadFile = File(...)):
    html_bytes = await file.read()

    temp_html = f"/tmp/{uuid.uuid4()}.html"
    temp_docx = f"/tmp/{uuid.uuid4()}.docx"

    with open(temp_html, "wb") as f:
        f.write(html_bytes)

    # Convert HTML → DOCX
    html_to_docx(temp_html, temp_docx)

    return FileResponse(
        temp_docx,
        media_type="application/vnd.openxmlformats-officedocument.wordprocessingml.document",
        filename="resume.docx"
    )