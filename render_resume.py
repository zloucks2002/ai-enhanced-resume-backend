# render_resume.py
# Handles template loading and HTML resume generation.
# Clean, stable, production-ready formatting.

import os

# Load template from /templates folder by style name
def load_template(style_choice: str) -> str:
    style_choice = style_choice.lower().strip()
    base_dir = os.path.dirname(os.path.abspath(__file__))
    template_path = os.path.join(base_dir, "templates", f"{style_choice}.html")
    if not os.path.exists(template_path):
        raise FileNotFoundError(f"Template not found: {template_path}")

    with open(template_path, "r", encoding="utf-8") as file:
        return file.read()

# Section Renderers
def render_experience(experience_list):
    if not experience_list:
        return ""

    html = ""
    for job in experience_list:
        bullets = "".join(f"<li>{b}</li>" for b in job.get("description", []))

        html += f"""
        <div class="job">
            <div class="job-header">
                <span>{job.get('job_title', '')}</span>
                <span>{job.get('start_date', '')} – {job.get('end_date', '')}</span>
            </div>
            <div class="company">{job.get('company', '')} — {job.get('location', '')}</div>
            <ul>{bullets}</ul>
        </div>
        """

    return html


def render_education(education_list):
    if not education_list:
        return ""

    html = ""
    for edu in education_list:
        html += f"""
        <div class="edu-item">
            <div class="edu-header">
                <span>{edu.get('degree', '')}</span>
                <span>{edu.get('start_date', '')} – {edu.get('end_date', '')}</span>
            </div>
            <div class="school">{edu.get('school', '')}</div>
        </div>
        """

    return html


def render_skills(skills):
    if not skills:
        return ""

    # Normalize skills if they are in dictionary format
    if isinstance(skills, dict):
        flat = []
        for group in skills.values():
            flat.extend(group)
        skill_text = ", ".join(flat)
    else:
        skill_text = ", ".join(skills)

    return f"""
    <h2>Skills</h2>
    <div>{skill_text}</div>
    """


def render_projects(projects):
    if not projects:
        return ""

    html = "<h2>Projects</h2>"
    for p in projects:
        title = p.get("name", "").strip()
        desc = p.get("description", "").strip()

        html += """<div class="project-item">"""

        if title:
            html += f"""
                <strong>{title}</strong><br>
            """

        html += f"""
                <div>{desc}</div>
            </div>
        """

    return html



def render_certifications(certs):
    if not certs:
        return ""

    html = "<h2>Certifications</h2>"
    for c in certs:
        html += f"""
        <div class="cert-item">{c}</div>
        """
    return html


def render_volunteer(vols):
    if not vols:
        return ""

    html = "<h2>Volunteer Experience</h2>"
    for v in vols:
        html += f"""
        <div class="vol-item">
            <strong>{v.get("organization", "")}</strong> — {v.get("role", "")}<br>
            <div>{v.get("description", "")}</div>
        </div>
        """
    return html


def render_summary(summary_text):
    if not summary_text:
        return ""
    return f"<div class='summary'>{summary_text}</div>"

import json
import re

def total_text_length(resume_json):
    # Dump JSON to a string
    raw = json.dumps(resume_json, ensure_ascii=False)
    
    # Remove JSON keys (everything before :)
    # e.g. "job_title": becomes empty
    cleaned = re.sub(r'"[^"]+"\s*:', '', raw)

    # Remove punctuation that wouldn't appear in the resume
    cleaned = re.sub(r'[{}[\],"]', '', cleaned)

    # Collapse whitespace
    cleaned = " ".join(cleaned.split())

    return len(cleaned)


def should_use_compact_mode(resume_json):
    #Job count
    experience = resume_json.get("experience", [])
    if len(experience) >= 3:
        return True
    
    #Bullet count
    total_bullets = sum(len(job.get("description", [])) for job in experience)
    if total_bullets > 15:
        return True
    
    char_count = total_text_length(resume_json)
    if char_count > 7000:
        return True
    
    return False



# Final HTML Resume Generator
def generate_html_from_template(resume_json, preferences):

    # Template selection
    style_choice = preferences.get("style_choice", "modern").lower()
    template = load_template(style_choice)

    # Render each section
    summary_html = render_summary(resume_json.get("summary", ""))
    experience_html = render_experience(resume_json.get("experience", []))
    education_html = render_education(resume_json.get("education", []))
    skills_html = render_skills(resume_json.get("skills", []))
    projects_html = render_projects(resume_json.get("projects", []))
    certifications_html = render_certifications(resume_json.get("certifications", []))
    volunteer_html = render_volunteer(resume_json.get("volunteer", []))

    # Replace placeholders in the template
    final_html = (
        template
        .replace("{{full_name}}", resume_json.get("full_name", ""))
        .replace("{{email}}", resume_json.get("email", ""))
        .replace("{{phone}}", resume_json.get("phone", ""))
        .replace("{{linkedin}}", resume_json.get("linkedin", ""))

        .replace("{{summary}}", summary_html)
        .replace("{{experience}}", experience_html)
        .replace("{{education}}", education_html)

        .replace("{{skills_section}}", skills_html)
        .replace("{{projects_section}}", projects_html)
        .replace("{{certifications_section}}", certifications_html)
        .replace("{{volunteer_section}}", volunteer_html)
    )

    if should_use_compact_mode(resume_json):
        final_html = final_html.replace("<body>", '<body class="compact">')

    return final_html

