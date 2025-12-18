from app.utils.openai_client import get_openai
import base64
import json
import fitz


def convert_pdf_to_images_web(pdf_path):
    # Convert each page of the PDF to a base64-encoded PNG image for analysis
    doc = fitz.open(pdf_path)
    images = []
    for i, page in enumerate(doc):
        pix = page.get_pixmap(dpi=150)
        img_bytes = pix.tobytes("png")
        b64 = base64.b64encode(img_bytes).decode("utf-8")
        images.append(b64)
    doc.close()
    return images

def analyze_resume_text_only(parsed_resume, target_job):
    # Analyze resume based solely on parsed text JSON and target job
    client = get_openai()
    prompt = f"""
    Provide a structured, expert resume analysis using ONLY the parsed JSON below.

    Since the original file is not a PDF, visual layout analysis cannot be performed.
    Focus on:
    - content quality
    - clarity
    - measurable impact
    - completeness
    - industry alignment
    - section order

    Target job: {target_job}

    Parsed resume JSON:
    {json.dumps(parsed_resume, indent=2)}

    Return your response in these sections:
    1. Industry Summary
        - Summarize what top resumes in this field look like (structure, tone, design).
        - Mention 2024–2025 hiring trends that influence expectations.
    2. Evaluation (Content Strengths / Weaknesses)
        - Content Strengths & Weaknesses: point to specific lines, bullets, or sections.
        - Only recommend a summary section if STRONGLY required by targeted job title or industry
        - Redundancy Check: only flag if wording is nearly identical and adds no new context.
        - Do not penalize consistent themes like communication or teamwork.
    3. Actionable Recommendations (label each as High / Moderate / Optional)
        - Provide only as many improvements as are truly necessary.
        - Label each as **High**, **Moderate**, or **Optional**.
        - Focus on edits that meaningfully improve clarity, impact, or ATS-readability.
        - Include structural or visual fixes only if they affect one-page fit or readability.
        - Never propose changes just to reach a number.
        - Each recommendation should specify whether it is Content, Formatting, or Structural and briefly explain *why*.
    """

    response = client.chat.completions.create(
        model="gpt-4o",
        messages=[
            {"role": "system", "content": "You are a professional resume reviewer with expertise in ATS optimization."},
            {"role": "user", "content": prompt}
        ],
        temperature=0.3
    )

    analysis = response.choices[0].message.content.strip()
    return {
        "analysis": analysis,
        "target_job": target_job
    }


def analyze_resume_with_context_web(file_bytes, parsed_resume, target_job, ext):
    #Conduct analysis based on file type and target job

    ext = ext.lower()
    
    if ext == ".pdf":
        temp_path = "temp_uploaded.pdf"
        with open(temp_path, "wb") as f:
            f.write(file_bytes)

        # Convert PDF pages to base64 images
        image_b64_list = convert_pdf_to_images_web(temp_path)

        
        client = get_openai()

        visual_inputs = [
            {
                "type": "text",
                "text": f"""Provide a unified assessment with 3 sections:
                    1. **Industry Summary**
                - Summarize what top resumes in this field look like (structure, tone, design).
                - Mention 2024–2025 hiring trends that influence expectations.

                2. **Evaluation**
                - **Content Strengths & Weaknesses:** point to specific lines, bullets, or sections.
                    - Only recommend a summary section if STRONGLY required by targeted job title or industry
                - **Formatting & Layout Audit:** check margins, spacing, alignment, section order, and one-page compliance.
                    If layout already meets best practices, explicitly state “No formatting/structural changes needed.”
                - **Redundancy Check:** only flag if wording is nearly identical and adds no new context.
                    Do not penalize consistent themes like communication or teamwork.

                3. **Actionable Recommendations**
                - Provide only as many improvements as are truly necessary.
                - Label each as **High**, **Moderate**, or **Optional**.
                - Focus on edits that meaningfully improve clarity, impact, or ATS-readability.
                - Include structural or visual fixes only if they affect one-page fit or readability.
                - Never propose changes just to reach a number.
                - Each recommendation should specify whether it is Content, Formatting, or Structural and briefly explain *why*.
                """
            }
        ]

        # Add each PDF page image
        for b64 in image_b64_list:
            visual_inputs.append({
                "type": "image_url",
                "image_url": {"url": f"data:image/png;base64,{b64}"}
            })

        # Add parsed JSON text
        visual_inputs.append({
            "type": "text",
            "text": f"Here is the parsed resume text:\n{json.dumps(parsed_resume, indent=2)}"
        })

        # Add target job context
        visual_inputs.append({
            "type": "text",
            "text": f"Target job: {target_job}"
        })

        try:
            response = client.chat.completions.create(
                model="gpt-4o",
                messages=[
                    {
                        "role": "system",
                        "content": "You are a professional resume reviewer with expertise..."
                    },
                    {
                        "role": "user",
                        "content": visual_inputs
                    }
                ],
                temperature=0.3
            )
            analysis = response.choices[0].message.content.strip()
            return {
                "analysis": analysis,
                "target_job": target_job
            }
        except Exception as e:
            return {"error": str(e)}
    
    else:
        return analyze_resume_text_only(parsed_resume, target_job)

def analyze_resume_service(file_bytes, parsed_resume, target_job, file_ext):
    return analyze_resume_with_context_web(file_bytes, parsed_resume, target_job, file_ext)    