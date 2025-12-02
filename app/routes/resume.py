from fastapi import APIRouter, UploadFile, File, Form
from app.services.resume_service import generate_html_resume_service
from app.services.analysis_service import analyze_resume_service
from app.services.resume_service import parse_resume_file
import json
import tempfile
from fastapi.responses import FileResponse
from app.utils.export import export_resume_to_pdf_file, export_resume_to_docx_file

router = APIRouter()

@router.post("/generate")
async def generate_resume(body: dict):
    return generate_html_resume_service(body)

@router.post("/parse")
async def parse_resume(file: UploadFile = File(...)):
    return parse_resume_file(file)

@router.post("/analyze-with-context")
async def analyze_with_context(
    file: UploadFile = File(...),
    parsed_json: str = Form(...),
    target_job: str = Form(...),
):
    parsed_resume = json.loads(parsed_json)
    pdf_bytes = await file.read()
    return analyze_resume_service(pdf_bytes, parsed_resume, target_job)

@router.post("/export/pdf")
async def export_pdf(file: UploadFile = File(...)):
    #Save uploaded HTML temporarily
    temp_html = tempfile.NamedTemporaryFile(delete=False, suffix=".html")
    temp_html.write(await file.read())
    temp_html.close()

    #Output PDF path
    output_path = temp_html.name.replace(".html", ".pdf")
    #Convert HTML to PDF
    export_resume_to_pdf_file(temp_html.name, output_path)

    return FileResponse(output_path, filename="resume.pdf")

@router.post("/export/docx")
async def export_docx(file: UploadFile = File(...)):
    #Save uploaded HTML temporarily
    temp_html = tempfile.NamedTemporaryFile(delete=False, suffix=".html")
    temp_html.write(await file.read())
    temp_html.close()

    #Output DOCX path
    output_path = temp_html.name.replace(".html", ".docx")

    #Convert
    export_resume_to_docx_file(temp_html.name, output_path)

    return FileResponse(output_path, filename="resume.docx")


