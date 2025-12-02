
from openai import OpenAI
import json
import re
import os
import time
import logging
from datetime import datetime
import shutil
import base64
import pypandoc
from render_resume import generate_html_from_template

#Setup logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - [%(levelname)s] %(message)s",
    handlers=[    
        logging.StreamHandler(),
        logging.FileHandler("resume_backend.log")
    ]
)
#Create OpenAI client
def create_openai_client():
    from dotenv import load_dotenv
    load_dotenv()
    api_key = os.getenv("OPENAI_API_KEY")
    if not api_key:
        raise ValueError("OPENAI_API_KEY is not set in environment")
    return OpenAI(api_key=api_key)


def init_conversation():
    # Return data structure for conversation history and instruct the AI on it's role
    today = datetime.today().strftime("%B %Y")
    system_template = f"""
        Today's date is {today}. When interpreting employment dates or the word "present", treat "{today}" as the current point in time. 
        If someone lists their end date as present, leave it as present.

        You are a semi-friendly but professional resume assistant chatbot. 
        Your job is to collect information from the user to create a professional, ATS-friendly resume. 
        Ask one question at a time in a clear and conversational tone, while internally maintaining a structured resume state.

        ------------------------------------
        Always follow this sequence of topics:
        1. Collect user information in this order:
        - Full name
        - Email address
        - Phone number
        - LinkedIn or portfolio URL
        - Target job title or industry
            - When the user provides their target job title/industry, immediately internally research relevant resume norms for that field, but do NOT explain them to the user. Use that research only to guide tone, structure, and section inclusion.
        - Most recent/relevant job - (ask these as separate questions):
                    - What was your job title?
                    - What was the name of the company?
                    - Where was this company located? (City, State or City, Country)
                    - What were the start and end dates? 
                    - What were your key responsibilities or accomplishments?
            - Ask if they want to add another job. If yes, repeat the above job flow.
        - Education (ask for degree, school, and dates)
            * Gather one detail at a time.
            * After one education entry is entered, ask if the user wants to add another.
            * If they are still enrolled, don't forget to ask for the start date, and for the end date, ask if they have a expected graduation date or if not, just say "present".
        - Key skills (ask if they'd like to add any; allow multiple)
            - Ask what skills they would like to add to their resume
            - After an entry, ask if they want to add any other skills before moving on.
        - Certifications or awards
            -After an entry, ask if they want to add another.
        - Projects (ask separately; projects must not go under skills)
            -After an entry, ask if they want to add another.
        - Volunteer work or unpaid internships 
            -After an entry, ask if they want to add another.
        - Preferred visual style (corporate, modern, minimalist, creative)
                - Corporate style resumes are traditional, formal, and strictly professional. Use standard fonts, black text, and clear hierarchical structure with minimal styling. Avoid color or creative layout.
                - Modern style resumes balance professionalism with visual clarity. They may use a subtle accent color for headings or lines, clean sans-serif fonts, and distinct section spacing.
                - Minimalist resumes are entirely black and white, with simple typography, strong alignment, and balanced whitespace. They rely on clean structure instead of color or design elements.
                - Creative style resumes use color, visual structure, and typography for expression. They are ideal for creative industries and may deviate from traditional layouts while remaining readable and ATS-compatible.
            - Offer a suggestion for style based on your research of the user's target job/industry standards, as well as to best highlight the user's strengths based on their content they provided, and explain why
        - Preferred resume format (chronological, functional, combination, targeted)
            - Offer a suggestion for format based on your research of the user's target job/industry standards, as well as to best highlight the user's strengths based on their content they provided, and explain why
        - If a professional summary is STRONGLY encouraged based on your research: 
            - After the volunteer work or unpaid internships section, ask if the user has a summary they would like to include, or if not, write a short professional summary that highlights the user's key skills and experiences relevant to the target role to your best ability.
        - If summaries are discouraged or overall not necessary optional, do not include one and proceed.

        2. At the end:
        - Ask if everything looks correct and if they are ready to generate the resume.
        - Do NOT print or summarize the collected resume data when asking for final confirmation; simply ask if everything looks good.
        - When the user confirms, respond with:
            "Sounds good! I'm ready to generate the resume."
        Then stop. Do not continue speaking, and do not offer summaries or JSON unless asked.
            When prompted:
            1. Return the complete resume data you've collected as a JSON object using the schema below.
                Hidden Resume State Management:
                - Here is the data schema you will follow for storing and structuring the user's resume information internally:
                {{
                "full_name": "",
                "email": "",
                "phone": "",
                "linkedin": "",
                "summary": "",
                "experience": [
                    {{
                    "job_title": "",
                    "company": "",
                    "location": "",
                    "start_date": "",
                    "end_date": "",
                    "description": []
                    }}
                ],
                "education": [
                    {{
                    "degree": "",
                    "school": "",
                    "start_date": "",
                    "end_date": ""
                    }}
                ],
                "skills": {{}},   # grouped categories if strongly recommended by industry standards 
                "certifications": [],
                "projects": [],
                "volunteer": []
                }}

        IMPORTANT: Immediately update the internal JSON state after EVERY user message that provides ANY resume-related data, even if it is only contact information or basic details that go into a JSON field. Do this from the very beginning of the conversation.
        - If the user input is unrelated (clarifications, general chat), do not modify the JSON.
        - Never display this JSON in the conversation. It is for backend preview only.
        - Always keep the JSON state up to date and retrievable by the backend.
            2. Then, when asked, return the preferences JSON:
            ```json
            {{
            "target_role": "...",
            "style_choice": "...",
            "structure_type": "..."
            "summary_required": true/false,
            "page_limit": 1 by default, 2 or more if standards suggest it, or based on amount of content (stay strict to industry standards)
            "industry_notes": "Explanation of resume standards for this industry"
            }}
            ```
            - Do not provide any of the JSON to the user at all
            3. Then wait for a follow-up prompt to generate the HTML resume, this will be the same where the backend will request it, don't provide it to the user through the chat.

        ------------------------------------
        Behavioral Guidelines:
        - Start the conversation by greeting the user and asking for their full name.
        - Ask only one question at a time, do not request multiple details in one message.
        - Allow multiple entries for each section before moving on (e.g., multiple projects)
        - Do not assume multiple details from a single answer. Confirm and clarify one field at a time.
        - After a section is complete, do not return to it unless the user explicitly asks.
        - If the user provides clarifications or corrections, update the stored values accordingly.
        - Never fabricate content. Only store what the user explicitly says.
        - Omit any sections that were not filled out or skipped.
        - Do not leave out the entire job description if the user provides it.
            - NEVER remove or omit ANY user-provided content.
            - Every bullet, sentence, and detail must be preserved unless the user asks otherwise.
        - Format the dates as needed yourself, do not make the user meet your format.
        - Ask clarifying questions as needed if the user provides incomplete or incorrect information.
        - NEVER rewrite, shorten, merge, or omit user-provided details without checking with the user first. If you decide to ask the user, explain why this change should be made and give them the choice to let you change it or not.
        - Only fix grammar and typos while keeping EVERY detail exactly intact.
        - If they’re unsure on any of the previous questions, guide them based on their experience and your research on industry norms, and offer recommendations as needed
        - Preserve the exact company/organization name as the user provides it. Do not shorten (e.g., keep "University Information Technology Services, Indiana University" as is). )
        - If the user input is unrelated to resume data (clarifying questions, side discussion), do not change the resume state.
        - Keep the conversation helpful, concise, and focused on building a strong resume.
        - Offer suggestions for resume style and structure one at a time, not together, and provide the alternative options for styles/structures after explaining the reasoning for your suggestion.

        ------------------------------------
        Resume Writing Standards:
        - After collecting target job/industry, first do some deep research on industry-specific resume standards for the target job/industry provided by the user.
        - Make sure to review reputable sources on industry resume standards, and gather the general consensus for how to build the resume, especially as ATS-friendly. 
            - If a professional summary is STRONGLY encouraged based on your research: 
                - After the volunteer work or unpaid internships section, ask if the user has a summary they would like to include, or if not, write a short professional summary that highlights the user's key skills and experiences relevant to the target role to your best ability.
                - If summaries are discouraged or overall not necessary/strongly encouraged, do not include one.
            - Always start with strong action verbs.
            - If measurable outcomes (numbers, percentages, scope) are provided, include them.
            - If not, emphasize scope, tools/technologies used, and value delivered to the best of your ability without changing the truth of the user's input.
            - Do NOT remove, merge, or shorten bullets automatically.
            - Only group skills into logical categories if industry standards strongly recommend it; otherwise, list them inline or as bullets.
            - Projects must include a title, brief description, and if relevant, include any methods, tools, or outcomes.
            - Certificates should go under Certifications unless they are academic minors (which stay in Education).
            - Keep the resume ATS-friendly: no graphics, text boxes, or unusual formatting.
            - Default to one page unless industry standards (e.g., academia, senior leadership) allow longer.
            - Provide a recommendation for both visual style and structure type based on industry norms and the user's target role, as well as based on their strengths to best highlight them.
        - During your deep research, please internally store the following information in JSON format based on the user's target role/industry. 
            - This information will be later requested by the backend, so do not provide it to the user at all, only the backend when the preferences JSON is requested.
            - This will be a detailed JSON object with resume preferences and reasoning for this user, including:
                - target_role (string): The job or industry type the user is applying for.
                - style_choice (string): The most appropriate visual style based on user preference and industry norms ("corporate", "modern", "minimalist", or "creative").
                - structure_type (string): The best resume structure for this field ("chronological", "functional", "combination", or "targeted").
                - summary_required (boolean): True if summaries are strongly standard/encouraged in this industry, false if neutral or discouraged.
                - page_limit (integer): Typical page length (1 for most industries, 2 for academia, research, or senior leadership).
                - industry_notes (object): A structured breakdown of industry-specific standards, including:
                    {{
                        "overview": "Brief explanation of resume tone and priorities for this field (e.g., metrics-driven, creative storytelling, academic focus).",
                        "formatting": {{
                            "alignment": "Describe alignment conventions (e.g., centered header, left-aligned body).",
                            "font": "List typical font families used in this field.",
                            "spacing": "Common margin and line spacing standards.",
                            "section_order": "Recommended section order based on importance (e.g., Experience → Education → Skills)."
                        }},
                        "design_advice": "Explain visual recommendations (use of color, icons, layout complexity, etc.)"
                    }}

        The goal is to capture both the content strategy and visual formatting expectations for the industry.
        Make sure `industry_notes.formatting.alignment` reflects typical alignment rules for this field.
        Use all the information gathered through research to guide your chatbot interaction with the user, as well as your suggestions for the user.

        Do not provide any of the JSON to the user at all, only to the backend when prompted.
        """

    return [{
        "role": "system",
        "content": system_template
    }]


#Initiates the generate resume chatbot loop
def run_chatbot(messages, client):
    while True:
        try:
            completion = client.chat.completions.create(
                model="gpt-4o", 
                messages=messages,
                temperature=0.5
            )
            assistant_reply = completion.choices[0].message.content
            logging.info("AI: %s", assistant_reply)
        except Exception as e:
            logging.error("Error during chatbot interaction: %s", e)
            return False, messages

        # Stop if AI says it's ready to generate the resume
        if "i'm ready to generate the resume." in assistant_reply.lower():
            return True, messages

        # User replies
        user_input = input("You: ")
        if user_input.lower() in ["stop", "exit", "quit"]:
            return False, messages

        # Append messages to conversation history
        messages.append({"role": "assistant", "content": assistant_reply})
        messages.append({"role": "user", "content": user_input})


#Requests the complete current resume JSON state from the AI
def get_resume_json(messages, client):

    tmp_messages = messages + [{
        "role": "user",
        "content": "Please return the complete current resume JSON state (according to the schema). Return only JSON."
    }]

    try:
        completion = client.chat.completions.create(
            model="gpt-4o",
            messages=tmp_messages,
            temperature=0
        )
        reply = completion.choices[0].message.content.strip()
        match = re.search(r'{.*}', reply, re.DOTALL)
        if match:
            return json.loads(match.group(0))
        else:
            logging.warning("AI did not return valid JSON for resume state.")
            return {}
    except Exception as e:
        logging.error("AI failed to extract resume JSON: %s", e)
        return {}




#Retrieves the resume preferences JSON from the AI
def get_resume_preferences(messages, client):
    messages.append({
        "role": "user",
        "content": """Please provide the detailed JSON object with resume preferences and reasoning for this user that you have kept internal, which should include:

        - target_role (string): The job or industry type the user is applying for.
        - style_choice (string): The most appropriate visual style based on user preference and industry norms ("corporate", "modern", "minimalist", or "creative").
        - structure_type (string): The best resume structure for this field ("chronological", "functional", "combination", or "targeted").
        - summary_required (boolean): True if summaries are strongly standard/encouraged in this industry, false if neutral or discouraged.
        - page_limit (integer): Typical page length (1 for most industries, 2 for academia, research, or senior leadership).
        - industry_notes (object): A structured breakdown of industry-specific standards, including:
            {
                "overview": "Brief explanation of resume tone and priorities for this field (e.g., metrics-driven, creative storytelling, academic focus).",
                "formatting": {
                    "alignment": "Describe alignment conventions (e.g., centered header, left-aligned body).",
                    "font": "List typical font families used in this field.",
                    "spacing": "Common margin and line spacing standards.",
                    "section_order": "Recommended section order based on importance (e.g., Experience → Education → Skills)."
                },
                "design_advice": "Explain visual recommendations (use of color, icons, layout complexity, etc.)"
            }
        Return only the JSON object — no commentary or explanation outside the JSON."""
    })

    try:
        completion = client.chat.completions.create(
            model="gpt-4o",
            messages=messages,
            temperature=0
        )
        reply = completion.choices[0].message.content.strip()
        match = re.search(r'{.*}', reply, re.DOTALL)
        if match:
            return json.loads(match.group(0))
    except Exception as e:
        logging.error("AI failed to extract preferences: %s", e)

    # Default fallback if parsing fails
    return {
        "target_role": "professional role",
        "style_choice": "modern",
        "structure_type": "chronological",
        "summary_required": False,
        "page_limit": 1,
        "industry_notes": {
            "overview": "General professional resumes emphasize clarity, conciseness, and relevance to the target role.",
            "formatting": {
                "alignment": "Centered name and contact info; left-aligned body text for all other sections.",
                "font": "Sans-serif fonts like Helvetica, Arial, or Calibri are preferred for readability.",
                "spacing": "0.5–0.75 inch margins, 1.3 line spacing, compact section spacing.",
                "section_order": "Experience → Education → Skills → Projects → Certifications"
            },
            "design_advice": "Keep the design simple and ATS-friendly. Avoid graphics, icons, or excessive color use."
        }
    }


"""
def generate_html_resume(client, resume_json, preferences):
    target_role = preferences.get("target_role", "professional role")
    style_choice = preferences.get("style_choice", "modern")
    structure_type = preferences.get("structure_type", "chronological")
    page_limit = preferences.get("page_limit", 1)

    # Handle structured or legacy industry_notes
    notes = preferences.get("industry_notes", {})
    if isinstance(notes, dict):
        formatting = notes.get("formatting", {})
        design_advice = notes.get("design_advice", "")
        ai_css = notes.get("custom_css", "")
    else:
        formatting = {}
        design_advice = notes
        ai_css = ""

    # --- Extract default fallback values ---
    alignment = formatting.get("alignment", "Centered name/contact; left-aligned body text.")
    font = formatting.get("font", "Inter, Arial, sans-serif")
    spacing = formatting.get("spacing", "0.6 inch margins, 1.3 line spacing")

    # --- Fallback defaults 
    if page_limit == 1:
        margin_in = "0.5in"
    else:
        margin_in = "0.75in"
        if "0.5" in spacing:
            margin_in = "0.5in"
        elif "0.75" in spacing:
            margin_in = "0.75in"
        elif "1" in spacing:
            margin_in = "1in"
    if page_limit == 1:
        line_height = "1.25"
    else:
        if "1.5" in spacing:
            line_height = "1.5"
        elif "1.2" in spacing:
            line_height = "1.2"
        else:
            line_height = "1.3"

    header_alignment = "center" if "center" in alignment.lower() else "left"
    body_alignment = "left" if "left" in alignment.lower() else "justify"
    if "creative" in style_choice.lower():
        body_alignment = "justify"

    #Base CSS
    base_css = 
    @page {{
        size: A4;
        margin: {margin_in};
    }}
    @font-face {{
        font-family: 'Inter';
        src: url('https://fonts.gstatic.com/s/inter/v12/UcCO3FwrK9z1Vdl3iK5W.woff2') format('woff2');
    }}
    body {{
        font-family: 'Inter', Arial, sans-serif;
        font-size: 11pt;
        line-height: {line_height};
        letter-spacing: 0.01em;
        color: #111;
        margin: 0;
        padding: 0;
    }}
    .header {{
        text-align: {header_alignment};
        margin-bottom: 0.3in;
    }}
    .header h1 {{
        font-size: 20pt;
        margin-bottom: 4px;
    }}
    .header p {{
        font-size: 10.5pt;
        margin: 2px 0;
        color: #333;
    }}
    .section {{
        text-align: {body_alignment};
        margin-top: 0.15in;
        margin-bottom: 0.2in;
    }}
    h2 {{
        font-size: 13pt;
        border-bottom: 1px solid #ddd;
        padding-bottom: 2px;
        margin-bottom: 6px;
    }}
    ul {{
        margin: 4px 0 0 16px;
    }}
    p, li {{
        margin: 2px 0;
        line-height: 1.25;
    }}
    * {{
        page-break-inside: avoid;
    }}
    ul {{
        margin-top: 0;
        margin-bottom: 0;
        padding-left: 14px;
    }}

    li {{
        margin-top: 0;
        margin-bottom: 0;
        line-height: 1.20;
    }}

    .section {{
        margin-top: 0.10in;
        margin-bottom: 0.12in;
    }}
    

    # --- Combine base and AI CSS ---
    if ai_css and isinstance(ai_css, str):
        combined_css = f"<style>\n{base_css}\n/* --- AI Custom CSS --- */\n{ai_css}\n</style>"
    else:
        combined_css = f"<style>\n{base_css}\n</style>"

    # --- AI Prompt: Adaptive layout authority ---
    html_prompt = f
    You are now responsible for designing the final HTML resume layout.

    Use your best professional judgment to balance readability, visual harmony, and
    information density. The resume must fit within exactly {page_limit} page(s) of A4 paper.


    Design rules:
    - You MUST use the base CSS EXACTLY as provided.
    - Do NOT override margins, font size, or section spacing unless strictly required to fit the page limit.
    - Do NOT remove or summarize content.
    - Do NOT add filler or extra text.
    - Never exceed the page limit.
    - Optimize the look and readability for professional review.
    - Use modern, ATS-friendly HTML and CSS.
    - Include <!DOCTYPE html>, <html>, <head>, and <body> tags.
    - Do NOT output markdown, comments, or explanations — only final HTML.
    - You may override the base CSS inline if needed.
    - Never include a "Target Role" or "Target Job" section line in the visible output.
        - Use that information only to influence tone, layout, and section relevance.
    - Render all skills as comma-separated inline lines (never vertical bullets)

    The resume should look handcrafted by a professional designer.

    Target Role: {target_role}
    Visual Style: {style_choice}
    Structure: {structure_type}
    Design Advice: {design_advice}

    Base CSS:
    {combined_css}

    Resume JSON for resume content:
    {json.dumps(resume_json, indent=2)}
    

    try:
        completion = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {
                    "role": "system",
                    "content": "You convert structured resume JSON into a single, self-contained HTML resume document."
                },
                {
                    "role": "user",
                    "content": html_prompt
                }
            ],
            temperature=0
        )
        full_output = completion.choices[0].message.content.strip()

        # Remove markdown fences if present
        html_resume = re.sub(r"^```(?:html)?", "", full_output.strip(), flags=re.MULTILINE)
        html_resume = re.sub(r"```$", "", html_resume.strip(), flags=re.MULTILINE)

        # Validate HTML start
        html_start = html_resume.lower().find("<!doctype html>")
        if html_start != -1:
            html_resume = html_resume[html_start:].strip()
        else:
            logging.warning("AI response did not include valid HTML.")
            html_resume = html_resume

        # Ensure CSS present
        if "<style>" not in html_resume:
            html_resume = html_resume.replace("<head>", f"<head>{combined_css}")

        return html_resume

    except Exception as e:
        logging.error("Failed to generate adaptive HTML resume: %s", e)
        return None
"""





#Supabase section
from supabase import create_client, Client

def create_supabase_client():
    from dotenv import load_dotenv
    load_dotenv()
    supabase_key = os.getenv("SUPABASE_KEY")
    if not supabase_key:
        raise ValueError("SUPABASE_KEY is not set in environment")
    supabase_url = os.getenv("SUPABASE_URL")
    if not supabase_url:
        raise ValueError("SUPABASE_URL is not set in environment")
    return create_client(
        supabase_url,
        supabase_key
    )

#Signup user
def signup_user(supabase, email, password):
    try:
        response = supabase.auth.sign_up({
            "email": email,
            "password": password
        })
        if response.user:
            logging.info("Signup request successful")
            return response.user
        else:
            logging.info("Signup failed: %s", response)
    except Exception as e:
        logging.error("Error during signup: %s", e)
    return None
    

#Login user
def login_user(supabase, email, password):
    try:
        response = supabase.auth.sign_in_with_password({"email": email, "password": password})
        if response.user:
            logging.info("Login successful")
            return response.user
        else:
            logging.info("Login failed: Response: %s", response)
    except Exception as e:
        logging.error("Error during login: %s", e)
    return None



#Insert the resume data into the Supabase database
def insert_resume_to_supabase(supabase, resume_name, resume_data, user_id=None, html_content=None, preferences=None, original_file_path=None, source_type="upload"):
    record = {
        "user_id": user_id,
        "resume_json": resume_data,
        "resume_name": resume_name,
        "resume_html": html_content or "",
        "preferences": preferences or {},
        "source_type": source_type,
    }
    if original_file_path:
        record['original_file_path'] = original_file_path

    try:
        response = supabase.table("resumes").insert(record).execute()
        if not response.data:
            logging.info("Insert failed. Response: %s", response.model_dump())
            return None
        logging.info("Resume inserted to Supabase successfully.")
        return response.data[0]["id"]
    #Checks for duplicate names and appends timestamp if needed
    except Exception as e:
        text = str(e).lower()
        if "duplicate key" in text:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            resume_name = f"{resume_name}_{timestamp}"
            logging.info(f"Duplicate name. Saving as {resume_name}")
            response = supabase.table("resumes").insert({
                **record,
                "resume_name": resume_name
            }).execute()
            return response.data[0]["id"]
        logging.error("Error inserting resume: %s", e)
        return None

#Generic function to retrieve text from either PDF or DOCX resume files
def extract_resume_text(file_path):
    extension = os.path.splitext(file_path)[1].lower()
    if extension == ".pdf":
        return extract_pdf_text(file_path)
    elif extension == ".docx":
        return extract_doc_text(file_path)
    else:
        raise ValueError("Unsupported file type. Only PDF and DOCX are supported.")



def extract_doc_text(doc_path):
    #Given a Word document, parse it and extract the text
    from docx import Document
    document = Document(doc_path)

    #Put the text from the document into a list, removing empty lines
    resume_text = []
    for para in document.paragraphs:
        if para.text.strip():
            resume_text.append(para.text.strip())

    #Combine the list into a single string
    resume_string = "\n".join(resume_text)
    return resume_string

#Extract text from a PDF file
import fitz

def extract_pdf_text(pdf_path):
    doc = fitz.open(pdf_path)
    text = ""

    for page in doc:
        text += page.get_text()

    doc.close()
    return text.strip()

#Retrieves all resumes for a given user
def get_resumes_for_user(supabase, user_id):
    try:
        response = supabase.table("resumes").select("id", "resume_name", "created_at").eq("user_id", user_id).order("created_at", desc=True).execute()
        return response.data if response.data else []
    except Exception as e:
        logging.error("Failed fetching resumes for user: %s", e)
        return []

#Retrieves a specific resume of a user by ID
def get_resume_by_id(supabase, resume_id, user_id):
    try:
        response = supabase.table("resumes").select("*").eq("id", resume_id).eq("user_id", user_id).limit(1).execute()
        return response.data[0] if response.data else None
    except Exception as e:
        logging.error("Failed to fetch resume: %s", e)
        return None
    
#Allows user to select a resume by name
def select_resume_by_name(supabase, user_id):
    resumes = get_resumes_for_user(supabase, user_id)
    if not resumes:
        print("No resumes found.")
        return None

    print("\nAvailable Resumes:")

    for i in resumes:
        print(f"- {i['resume_name']} (Created: {i['created_at']})")
    
    selected_resume = input("Enter the name of the resume you'd like to select: ").strip()
    for resume in resumes:
        if resume["resume_name"].strip().lower() == selected_resume.lower():
            return get_resume_by_id(supabase, resume["id"], user_id)
    
    print("No matching resume found.")
    return None
    
#Rename a user's resume
def rename_resume(supabase, resume_id, new_name, user_id):
    #Core rename function, single attempt
    try:
        response = supabase.table("resumes").update({"resume_name": new_name}).eq("id", resume_id).eq("user_id", user_id).execute()
        return bool(response.data)
    #Checks for duplicate names
    except Exception as e:
        text = str(e).lower()
        if "23505" in text or "duplicate key" in text or "unique constraint" in text: 
            raise ValueError("Another resume already has this name.")
        logging.error("Failed to rename resume: %s", e)
        raise

#Account deletion with all associated data
def delete_user(supabase, user_id):
    try:
        supabase.table("resumes").delete().eq("user_id", user_id).execute()
        supabase.auth.admin.delete_user(user_id)
        print("User and associated data deleted successfully.")
    except Exception as e:
        logging.error("Error deleting account: %s", e)

#Adding indexes for each resume in list to help user select
def pick_resume_by_index(supabase, user_id):
    resumes = get_resumes_for_user(supabase, user_id)
    if not resumes:
        print("No resumes found.")
        return None
    print("\nYour Resumes:")
    for i, r in enumerate(resumes, start=1):
        print(f"{i}. {r['resume_name']} (Created: {r['created_at']})")
    
    choice = input("\nEnter a number to select a resume, or press Enter to go back: ").strip()
    if not choice:
        return None
    if not choice.isdigit():
        print("Invalid input. Please enter a number.")
    
    idx = int(choice)
    if 1 <= idx <= len(resumes):
        resume_id = resumes[idx - 1]["id"]
        return get_resume_by_id(supabase, resume_id, user_id)
    else:
        print("Invalid number.")
        return None
        

#Delete a user's resume
def delete_resume(supabase, resume_id, user_id=None):
    #Single attempt to delete. No prompts
    try:
        q = supabase.table("resumes").delete().eq("id", resume_id)
        if user_id:
            q = q.eq("user_id", user_id)
        response = q.execute()
        return bool(response.data)
    except Exception as e:
        logging.error("Failed to delete resume: %s", e)
        return False
    
def safe_rename_resume(supabase, user_id, resume_record):
    #Prompt user for new name, retry on duplicate, and allow cancel
    while True:
        new_name = input("Enter a new name (or type 'cancel' to stop): ").strip()
        if new_name.lower() == "cancel":
            print("Rename canceled")
            return False
        if not new_name:
            print("Name cannot be empty. Please try again.")
            continue
        try:
            rename = rename_resume(supabase, resume_record["id"], new_name, user_id)
            if rename:
                print("Resume renamed successfully.")
                return True
            print("Rename failed (no matching record).")
            return False
        except ValueError as ve:
            print(str(ve))
            continue
        except Exception as e:
            print(f"Unexpected error renaming: {e}")
            return False
        
def safe_delete_resume(supabase, user_id, resume_record):
    #Confirm deletion with user or allow cancel
    confirm = input(f"Type 'delete' to permanently delete '{resume_record['resume_name']}': ").strip()
    if not confirm:
        print("Deletion canceled")
        return False
    if confirm.lower() != "delete":
        print("Deletion canceled")
        return False
    delete = delete_resume(supabase, resume_record["id"], user_id)
    if delete:
        print("Resume deleted.")
        return True
    print("Delete failed.")
    return False


#Parses resume text into structured JSON using AI
def parse_doc_text(resume_string, client):
    messages = [{
        "role": "system",
        "content": """Your job is to parse the text from a Word or PDF document which is a professional resume, 
            and extract ALL information relevant to a resume to create a JSON object that follows this schema (the values are examples):
            {
            "full_name": "Zach Loucks",
            "email": "zach@example.com",
            "phone": "123-456-7890",
            "linkedin": "https://linkedin.com/in/zloucks",
            "summary": "...",
            "experience": [
            {
            "job_title": "Data Analyst",
            "company": "XYZ Corp",
            "start_date": "2022-01",
            "end_date": "2023-12",
            "description": "Worked on analytics..."
            }
            ],
            "education": [
            {
            "degree": "BS Informatics",
            "school": "IUPUI",
            "start_date": "2020-08",
            "end_date": "2024-05"
            }
            ],
            "skills": ["Python", "SQL", "Data Analysis"],
            "certifications": [],
            "projects": [],
            "volunteer": []
            }
            Additionally, you must return only the JSON object"""},
        {
            "role": "user",
            "content": f"Here is the resume text: \n\n{resume_string}\n\nPlease parse this text and extract the relevant information to create a JSON object that follows the schema provided in the system message."
    }]
    
    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=messages,
            temperature=0.0
        )
        parsed_json = response.choices[0].message.content.strip()
        #Validate the JSON output from Grok
        match = re.search(r'\{.*\}', parsed_json, re.DOTALL)
        if match:
            return json.loads(match.group(0))
        logging.info("No valid JSON found in AI's response.")
    except Exception as e:
        logging.error("Error during AI parsing: %s", e)
    return None
#Normalize descriptions in experience to be lists of bullet points rather than one string
def normalize_descriptions(resume_json):
    for job in resume_json.get("experience", []):
        desc = job.get("description")

        if isinstance(desc, str):
            bullets = [s.strip() for s in desc.split(".") if s.strip()]
            job["description"] = bullets

    return resume_json


#Analyze the resume provided by user for improvements
def analyze_resume(client, resume_json):
    prompt = f"""
    You are a professional resume reviewer.
    Evaluate the following resume data (in JSON format) for content quality, clarity, completeness, and impact.
    Identify any missing information, vague language, or sections that could be improved.

    Give structured feedback in this format:
    1. Summary Feedback (1-2 sentences)
    2. Section-by-Section Feedback (experience, education, skills, etc.)
    3. Recommendations to improve overall impact

    Resume JSON:
    {json.dumps(resume_json, indent=2)}
    """

    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You are an expert resume coach helping improve professional resumes"},
                {"role": "user", "content": prompt}
            ],
            temperature=0.5
        )
        return response.choices[0].message.content.strip()
    
    except Exception as e:
        return f"Error analyzing resume: {e}"

#Takes images of each page in the PDF for later visual analysis and returns a list of image file paths.
def convert_pdf_to_images(pdf_path, output_folder="resume_pages"):
    os.makedirs(output_folder, exist_ok=True)
    doc = fitz.open(pdf_path)
    image_paths = []
    for i, page in enumerate(doc):
        pix = page.get_pixmap(dpi=150)
        img_path = os.path.join(output_folder, f"page_{i+1}.png")
        pix.save(img_path)
        image_paths.append(img_path)
    doc.close()
    return image_paths

#Unified resume analysis with visual layout and industry context
def analyze_resume_with_industry_context(client, pdf_path, parsed_resume):

    target_job = input("What job title or industry are you targeting? ").strip()

    logging.info("Converting resume pages to images for visual analysis...")
    image_paths = convert_pdf_to_images(pdf_path)

    # Build the message content for GPT-4o
    visual_inputs = [
        {"type": "text", "text": f"""Provide a unified assessment with 3 sections:
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
        """}
    ]


    # Attach images of resume pages
    for img in image_paths:
        with open(img, "rb") as f:
            image_bytes = f.read()
            image_b64 = base64.b64encode(image_bytes).decode("utf-8")

            visual_inputs.append({
                "type": "image_url",
                "image_url": {
                    "url": f"data:image/png;base64,{image_b64}"
                }
            })

    # Include parsed text so GPT can reference specific content
    visual_inputs.append({
        "type": "text",
        "text": f"Here is the parsed resume text for content reference:\n{json.dumps(parsed_resume, indent=2)}"
    })

    logging.info("Sending combined visual + text + context analysis to GPT-4o...")

    try:
        response = client.chat.completions.create(
            model="gpt-4o",
            messages=[
                {"role": "system", "content": "You are a professional resume and career coach with expertise in ATS optimization, design, and hiring standards across industries."},
                {"role": "user", "content": visual_inputs}
            ],
            temperature=0.3
        )
        analysis = response.choices[0].message.content.strip()
        print("\n===== Unified Resume Analysis =====\n")
        print(analysis)
        print("\n===================================\n")
        return analysis, target_job

    except Exception as e:
        logging.error("Error during unified resume analysis: %s", e)
        return "Analysis failed.", target_job

#Gathers the resume HTML from Supabase
def retrieve_resume_html(supabase, resume_id, user_id):
    try:
        response = supabase.table("resumes").select("resume_name, resume_html").eq("id", resume_id).eq("user_id", user_id).single().execute()
        if not response.data:
            logging.warning(f"No HTML found for resume ID {resume_id}")
            return None
        
        return response.data
    except Exception as e:
        logging.error(f"Failed to retrieve resume HTML: {e}")
        return None

    
#Uploads the original file to Supabase Storage for reference, and returns the storage path
def upload_original_file_to_supabase(supabase, file_path, user_id, resume_name):
    try:
        bucket_name = "resumes"  # must match your Supabase Storage bucket name
        ext = os.path.splitext(file_path)[1].lower()
        if ext not in [".pdf", ".docx"]:
            logging.warning(f"Unsupported file type for upload: {ext}")
            return None
        # Sanitize name for safe storage path
        safe_name = re.sub(r'[<>:"/\\|?*]', '-', resume_name).replace(" ", "_")
        storage_path = f"originals/{user_id}/{safe_name}{ext}"

        with open(file_path, "rb") as f:
            file_bytes = f.read()

        # Upload file to Supabase Storage (upsert = replace if same name exists)
        response = supabase.storage.from_(bucket_name).upload(
            storage_path,
            file_bytes
        )

        if hasattr(response, "error") and response.error:
            logging.error(f"Error uploading PDF: {response.error}")
            return None

        logging.info(f"Original file uploaded to Supabase Storage: {storage_path}")
        return storage_path

    except Exception as e:
        logging.error(f"Failed to upload original PDF: {e}")
        return None



def main():

    supabase = create_supabase_client()
    client = create_openai_client()

    logging.info("AI Resume Assistant Backend")
    logging.info("Type 1 to sign up for an account")
    logging.info("Type 2 to login to an existing account")
    logging.info("Type 3 to continue as a guest (no account required)")

    choice = input("Choose an option (1-3): ").strip()
    user = None
    user_id = None

    if choice == "1":
        email = input("Email: ").strip()
        password = input("Password: ").strip()
        user = signup_user(supabase, email, password)
    elif choice == "2":
        email = input("Email: ").strip()
        password = input("Password: ").strip()
        user = login_user(supabase, email, password)
    
    if user:
        user_id = user.id
        logging.info(f"Logged in as {user.email}")
    else:
        logging.info("Continuing as guest (resume data will not be linked to an account)")
    
    while True:
        logging.info("What would you like to do?")
        logging.info("1. Upload and parse resume (PDF/DOCX)")
        logging.info("2. View my resumes")
        logging.info("3. Start chatbot and build/generate a new resume")
        logging.info("4. Analyze your parsed resume for improvements")
        logging.info("5. Upload resume and analyze for improvements, and implement improvements in chat session")
        logging.info("6. Exit")
        logging.info("7. Developer HTML generation test (skip chatbot)")

        action = input("Choose an action (1-7): ").strip()

        if action == "1":
            path = input("Enter path to resume file: ").strip()
            try:
                resume_text = extract_resume_text(path)
                parsed_resume = parse_doc_text(resume_text, client)
                if not parsed_resume:
                    logging.info("Failed to parse resume")
                    continue

                while True:
                    name = input("Enter a name for this resume (or type 'cancel' to stop): ").strip()
                    if name.lower() == "cancel":
                        logging.info("Cancelled resume upload")
                        break
                    if not name:
                        print("Name cannot be empty. Please try again")
                        continue

                    #Upload original PDF file to Supabase Storage
                    storagePath = None
                    if user_id:
                        storage_path = upload_original_file_to_supabase(supabase, path, user_id, name)
                    else:
                        logging.info("Guest mode: skipping storage upload (no user_id)")
                    
                    #Insert parsed resume JSON record (no HTML for uploaded files)
                    insert_resume_to_supabase(
                        supabase,
                        name,
                        parsed_resume,
                        user_id,
                        html_content="",
                        preferences=None,
                        original_file_path=storage_path,
                        source_type="upload"
                    )

                    logging.info("Resume uploaded, parsed, and saved successfully.")
                    break
            except Exception as e:
                logging.error(f"Error during resume upload: {e}")
        elif action == "2":
            record = pick_resume_by_index(supabase, user_id)
            if not record:
                logging.info("Returning to main menu")
                continue
            while True:
                logging.info(f"\nSelected Resume: {record['resume_name']}")
                print("1) Rename resume")
                print("2) Delete resume")
                print("3) Download resume as PDF")
                print("4) Download resume as DOCX")
                print("5) Back to main menu")
                option = input("Choose an option (1-5): ").strip()
                if option == "1":
                    safe_rename_resume(supabase, user_id, record)
                    record = get_resume_by_id(supabase, record["id"], user_id) or record
                elif option == "2":
                    if safe_delete_resume(supabase, user_id, record):
                        break
                elif option == "3":
                    record = get_resume_by_id(supabase, record["id"], user_id)
                    if not record:
                        logging.info("Could not fetch record.")
                        continue

                    source_type = record.get("source_type")
                    html_content = record.get("resume_html")
                    original_path = record.get("original_file_path")

                    # Case 1: Chatbot resume → render HTML to PDF
                    if source_type == "chatbot" and html_content:
                        html_path = f"{record['resume_name']}.html"
                        with open(html_path, "w", encoding="utf-8") as f:
                            f.write(html_content)
                        export_resume_to_pdf(html_path, f"{record['resume_name']}.pdf")

                    # Case 2: Uploaded PDF → download original
                    elif source_type == "upload" and original_path and original_path.endswith(".pdf"):
                        try:
                            bucket = "resumes"
                            response = supabase.storage.from_(bucket).download(original_path)
                            if response:
                                local_name = f"{record['resume_name']}_original.pdf"
                                with open(local_name, "wb") as f:
                                    f.write(response)
                                logging.info(f"Original uploaded PDF downloaded as {local_name}")
                            else:
                                logging.warning("Failed to download original PDF from Supabase.")
                        except Exception as e:
                            logging.error(f"Error downloading original PDF: {e}")

                    # Case 3: Uploaded DOCX → warn user
                    elif source_type == "upload" and original_path and original_path.endswith(".docx"):
                        logging.warning("Cannot convert uploaded DOCX to PDF — no HTML version exists. Download the DOCX instead.")
                        print("This resume was uploaded as a Word document. PDF format is unavailable because no HTML version exists.")
                        print("Please use 'Download as DOCX' instead.")

                    else:
                        logging.warning("No valid data for PDF export.")
                        print("This resume does not have an HTML or PDF version available.")

                elif option == "4":
                    record = get_resume_by_id(supabase, record["id"], user_id)
                    if not record:
                        logging.info("Could not fetch record.")
                        continue

                    source_type = record.get("source_type")
                    html_content = record.get("resume_html")
                    original_path = record.get("original_file_path")

                    # Case 1: Chatbot resume → generate DOCX from HTML
                    if source_type == "chatbot" and html_content:
                        html_path = f"{record['resume_name']}.html"
                        with open(html_path, "w", encoding="utf-8") as f:
                            f.write(html_content)
                        export_resume_to_docx(html_path, f"{record['resume_name']}.docx")

                    # Case 2: Uploaded DOCX → download original
                    elif source_type == "upload" and original_path and original_path.endswith(".docx"):
                        try:
                            bucket = "resumes"
                            response = supabase.storage.from_(bucket).download(original_path)
                            if response:
                                local_name = f"{record['resume_name']}_original.docx"
                                with open(local_name, "wb") as f:
                                    f.write(response)
                                logging.info(f"Original uploaded DOCX downloaded as {local_name}")
                            else:
                                logging.warning("Failed to download original DOCX from Supabase.")
                        except Exception as e:
                            logging.error(f"Error downloading original DOCX: {e}")

                    # Case 3: Uploaded PDF → warn user
                    elif source_type == "upload" and original_path and original_path.endswith(".pdf"):
                        logging.warning("Cannot convert uploaded PDF to DOCX — no HTML version exists. Download the PDF instead.")
                        print("This resume was uploaded as a PDF. Word format is unavailable because no HTML version exists.")
                        print("Please use 'Download as PDF' instead.")

                    else:
                        logging.warning("No valid data for DOCX export.")
                        print("This resume does not have an HTML or DOCX version available.")


                elif option == "5":
                    break
                else:
                    logging.info("Invalid option. Try again")
                    continue
            

        elif action == "3":
            messages = init_conversation()
            start, updated_messages = run_chatbot(messages, client)
            if start:
                resume_json = get_resume_json(updated_messages, client)
                preferences = get_resume_preferences(updated_messages, client)
                html_resume = generate_html_from_template(resume_json, preferences)
                if html_resume:
                    with open("resume_preview.html", "w", encoding="utf-8") as f:
                        f.write(html_resume)
                    logging.info("HTML resume generated: resume_preview.html")
                    resume_name = input("Enter a name for this resume: ").strip() or "New Resume"
                
                    try:
                        insert_resume_to_supabase(supabase, resume_name, resume_json, user_id, html_resume, preferences, source_type="chatbot")
                    except Exception as e:
                        logging.error("Failed saving resume: %s", e)
                else:
                    logging.info("Failed to generate HTML")
        elif action == "4":
            selected_resume = select_resume_by_name(supabase, user_id)
            if selected_resume and selected_resume.get("resume_json"):
                analysis = analyze_resume(client, selected_resume["resume_json"])
                logging.info("Resume Analysis:")
                logging.info(analysis)
            else:
                logging.info("No resume found or resume data is empty.")
        elif action == "5":
            path = input("Enter path to your resume file: ").strip()
            try:
                resume_text = extract_resume_text(path)
                parsed_resume = parse_doc_text(resume_text, client)
                if not parsed_resume:
                    logging.info("Failed to parse resume.")
                    continue
                print("Parsed Resume JSON:", json.dumps(parsed_resume, indent=2))

                # Run unified analysis
                analysis, target_job = analyze_resume_with_industry_context(client, path, parsed_resume)

                # Begin improvement chatbot session
                today = datetime.today().strftime("%B %Y")
                system_context = f"""
                Today's date is {today}.
                You are a resume improvement assistant.
                The user is targeting a role in: {target_job}.
                You have already analyzed their resume and provided the following feedback:
                {analysis}

                You will work with this resume data in JSON format, following the schema below and starting with the user's parsed resume data below in JSON format.
                
                Schema:
                    {{
                    "full_name": "",
                    "email": "",
                    "phone": "",
                    "linkedin": "",
                    "summary": "",
                    "experience": [
                        {{
                            "job_title": "",
                            "company": "",
                            "location": "",
                            "start_date": "",
                            "end_date": "",
                            "description": []
                        }}
                    ],
                    "education": [...],
                    "skills": [...],
                    "certifications": [...],
                    "projects": [...],
                    "volunteer": [...]
                    }}

                Here is the current parsed resume data in JSON format to start with:
                {json.dumps(parsed_resume, indent=2)}

                Rules:
                - Keep this JSON updated internally whenever the user approves a change.
                    - Never mention to the user that you are updating the internal JSON, just do so silently after they confirm.
                -After completing an improvement, you MUST propose the next most impactful improvement remaining.
                    - Do NOT wait for the user to guess what to improve next.
                    - Always say what the next potential improvement is (e.g., “Next, we could improve X, Y, or Z.”).
                    - Present improvements one at a time in priority order: High → Moderate → Optional.
                    - After each improvement, ask: “Would you like to apply this change?” 
                    - Only move on when the user says “yes” or “no,” but ALWAYS tell them the next available improvement.
                    - Continue until there are no more improvements left.
                    - When no improvements remain, say: “All improvements are complete. I’m ready to generate the resume.”
                - Modify only existing fields; never invent new keys or reorder sections arbitrarily.
                - When suggesting edits, quote the original bullet, explain the rationale, and apply the edit only if the user confirms.
                    - After confirmation, update your internal JSON immediately.
                    - NEVER provide the JSON to the user unless they specifically request it, it should be kept internal and the backend may prompt for it at any time.
                - Do not lose prior changes — this JSON must always stay current.
                - If the user asks to view or generate the resume, return only the latest JSON.
                - Never insist on adding a professional summary unless it is STRONGLY encouraged for this industry/job type.
                - NEVER suggest bold, italics, underlining, or any selective highlighting of specific skills or keywords.
                - The resume must remain fully ATS-friendly and uniform with no emphasis styles.
                - If recommending the user include specific metrics, provide an example of how it could be phrased, but ask the user if they have any metrics they can provide.
                    - Do not invent metrics for them, only help them phrase real metrics they provide if they have any. 
                    - If they do not have metrics, try to help them strengthen impact in other ways if necessary.
                    - Never use the example metrics if the user claims they do not have any relevant metrics.
                - If the industry/job type typically skips summaries, do not prompt the user for one.
                - Use the resume content already provided to inform your guidance - only ask for details that are clearly missing.
                - When suggesting improvements, focus on relevance, impact, and ATS optimization, not unnecessary sections.
                - Using this context, help the user improve their resume step by step.
                - Ask one focused question at a time.
                - Keep all context in memory.
                - When suggesting changes, explain why they matter from a recruiter's perspective.
                - Prioritize sections that have the highest impact for this industry first.
                - If a user refuses to implement a change, move on to the next suggestion without argument.
                - When finished, offer to generate an improved resume for this industry.
                - When the user confirms that all changes are complete or says "yes" to proceed with generation,
                    respond only with the phrase: "Sounds good! I'm ready to generate the resume."
                    Do not include any other text or explanation.
                """

                messages = [{"role": "system", "content": system_context},
                            {
                                "role": "user",
                                "content": f"Here is the user's parsed resume data for reference:\n{json.dumps(parsed_resume, indent=2)}"
                            }]
                messages.append({
                    "role": "assistant",
                    "content": f"Let's start improving your resume for a {target_job} position. Ready to begin?"
                })
                print(f"\nAI: Let's start improving your resume for a {target_job} position. Ready to begin?\n")

                while True:
                    user_input = input("You: ")
                    if user_input.lower() in ["exit", "quit", "stop"]:
                        print("Session ended.")
                        break

                    messages.append({"role": "user", "content": user_input})

                    completion = client.chat.completions.create(
                        model="gpt-4o",
                        messages=messages,
                        temperature=0.5
                    )
                    reply = completion.choices[0].message.content.strip()
                    print("\nAI:", reply, "\n")

                    messages.append({"role": "assistant", "content": reply})

                    if "i'm ready to generate the resume." in reply.lower():
                        confirm = input("Generate the improved resume now? (y/n): ").strip().lower()
                        if confirm == "y":
                            resume_json = get_resume_json(messages, client)
                            resume_json = normalize_descriptions(resume_json)
                            preferences = get_resume_preferences(messages, client)
                            print(json.dumps(resume_json, indent=2))
                            html_resume = generate_html_from_template(resume_json, preferences)
                            if html_resume:
                                with open("improved_resume.html", "w", encoding="utf-8") as f:
                                    f.write(html_resume)
                                logging.info("Improved resume saved as improved_resume.html")
                                 
                            else:
                                logging.info("Failed to generate improved HTML resume.")
                        break

            except Exception as e:
                logging.error("Error during unified resume improvement flow: %s", e)

        elif action == "6":
            logging.info("Goodbye!")
            break

        elif action == "7":
            print("Developer HTML Generation Test Mode")

            resume_json_path = "resume.json"
            prefs_json_path = "preferences.json"

            #Load JSON data
            try:
                with open(resume_json_path, "r", encoding="utf-8") as f:
                    resume_json = json.load(f)
                with open(prefs_json_path, "r", encoding="utf-8") as f:
                    preferences = json.load(f)
            except Exception as e:
                logging.error(f"Failed to load JSON files: {e}")
                print("Invalid file paths or JSON format.")
                continue

            print("Generating HTML resume...")
            html_resume = generate_html_from_template(resume_json, preferences)

            if not html_resume:
                logging.info("Failed to generate HTML resume.")
                continue

            #Save HTML
            with open("developer_test.html", "w", encoding="utf-8") as f:
                f.write(html_resume)
            
            print("Saved developer_test.html")
            doc_choice = input("Export to PDF or DOCX? (pdf/docx/skip): ").strip().lower()
            if doc_choice == "pdf":
                export_resume_to_pdf("developer_test.html", "developer_test.pdf")
                print("Saved developer_test.pdf")
            elif doc_choice == "docx":
                export_resume_to_docx("developer_test.html", "developer_test.docx")
                print("Saved developer_test.docx")
            else:
                logging.info("Export skipped.")
            
            break
            
        
    
        else:
            logging.info("Invalid option. Try again")
            
    
    

if __name__ == "__main__":
    main()






