import streamlit as st
import fitz  # PyMuPDF
import spacy
import re
import base64
import matplotlib.pyplot as plt

try:
    from fuzzywuzzy import fuzz
except ImportError:
    st.error("Please install 'fuzzywuzzy'")
    st.stop()

try:
    nlp = spacy.load("en_core_web_sm")
except OSError:
    # This command downloads the model directly into the environment
    from spacy.cli import download
    download("en_core_web_sm")
    nlp = spacy.load("en_core_web_sm")

# -------- Background (Login page only) --------
def set_bg_image(image_path):
    try:
        with open(image_path, "rb") as img:
            encoded = base64.b64encode(img.read()).decode()
        st.markdown(f"""
            <style>
            .stApp {{
                background-image: url("data:image/png;base64,{encoded}");
                background-size: cover;
                background-position: center;
            }}
            .login-box {{
                background-color: rgba(255,255,255,0.85);
                padding: 3rem;
                border-radius: 10px;
                max-width: 400px;
                margin: 10vh auto;
                box-shadow: 0 4px 20px rgba(0,0,0,0.3);
            }}
            </style>
        """, unsafe_allow_html=True)
    except Exception as e:
        st.warning(f"Background image not found or failed to load: {e}")


# -------- Helper Functions --------
def extract_text_from_pdf(pdf_file):
    text = ""
    try:
        with fitz.open(stream=pdf_file.read(), filetype="pdf") as doc:
            for page in doc:
                text += page.get_text()
    except Exception as e:
        st.error(f"PDF extract failed: {e}")
    return text


def extract_contact_info(text):
    phone = re.findall(r'\b\d{10}\b', text)
    email = re.findall(r'\S+@\S+', text)
    return email[0] if email else "Not found", phone[0] if phone else "Not found"


def extract_jd_keywords(jd_text):
    doc = nlp(jd_text.lower())
    keywords = set()	
    for chunk in doc.noun_chunks:
        keywords.add(chunk.text.strip())
    for ent in doc.ents:
        if ent.label_ in ["ORG", "PRODUCT", "LOC"]:
            keywords.add(ent.text.strip())
    for token in doc:
        if token.pos_ in ["NOUN", "PROPN"] and not token.is_stop:
            keywords.add(token.text.strip())
    tech_terms = ["python", "java", "sql", "c++", "aws", "azure"]
    for t in tech_terms:
        if t in jd_text.lower():
            keywords.add(t)
    return list(keywords)


def find_skills_in_resume(resume_text, jd_keywords):
    resume_lower = resume_text.lower()
    found = set()
    for key in jd_keywords:
        if key in resume_lower:
            found.add(key)
        else:
            for line in resume_lower.split('\n'):
                if fuzz.partial_ratio(key, line) > 90:
                    found.add(key)
                    break
    return list(found)


def extract_sections(text):
    lines = text.splitlines()
    sections = {"education": "", "projects": "", "certifications": ""}
    current = None
    buffer = []

    headers = {
        "education": ["education", "academic background", "qualification"],
        "projects": ["project", "projects", "portfolio"],
        "certifications": ["certification", "certifications", "certified", "course", "training"]
    }

    def match_header(line):
        for sec, keys in headers.items():
            for key in keys:
                if re.search(rf"\b{key}\b", line.lower()):
                    return sec
        return None

    def clean_lines(lines):
        return [re.sub(r"^[•\-*●▪▶❖]+\s*", "", l.strip()) for l in lines if l.strip()]

    for line in lines:
        matched = match_header(line)
        if matched:
            if current and buffer:
                sections[current] += "\n".join(clean_lines(buffer)).strip() + "\n"
            current = matched
            buffer = [line]
        elif current:
            buffer.append(line)

    if current and buffer:
        sections[current] += "\n".join(clean_lines(buffer)).strip()

    # Education
    edu_keywords = ["bca", "b.sc", "mca", "msc", "engineering", "university", "college", "degree", "cgpa", "gpa"]
    edu_lines = [line for line in lines if any(k in line.lower() for k in edu_keywords)]
    sections["education"] = "\n".join(clean_lines(edu_lines[:4])) if edu_lines else "Not found"

    # Projects
    project_lines = [line for line in lines if any(k in line.lower() for k in ["project", "developed", "built", "implemented"])]
    sections["projects"] = "\n".join(f"- {l}" for l in clean_lines(project_lines[:6])) if project_lines else "Not found"

    # Certifications
    cert_keywords = ["certified", "aws", "python", "coursera", "udemy", "training", "course", "workshop"]
    cert_lines = [line for line in lines if any(k in line.lower() for k in cert_keywords)]
    sections["certifications"] = "\n".join(clean_lines(cert_lines[:5])) if cert_lines else "Not found"

    return sections


def generate_feedback(resume_keywords, jd_keywords):
    jd_set = set(jd_keywords)
    res_set = set(resume_keywords)
    common = jd_set & res_set
    score = round((len(common) / len(jd_set)) * 100) if jd_set else 0
    feedback = []
    if score < 50:
        feedback.append("Low match. Tailor your resume to the JD.")
    elif score < 80:
        feedback.append("Decent match. Add more JD-relevant skills.")
    else:
        feedback.append("Excellent match!")
    missing = jd_set - res_set
    if missing:
        feedback.append("Missing keywords: " + ", ".join(list(missing)[:5]))
    return score, feedback, list(common)


# --------- App Logic ---------
st.set_page_config(page_title="Resume Profiler", layout="wide")

if "page" not in st.session_state:
    st.session_state.page = "login"

if st.session_state.page == "login":
    set_bg_image("login_bg.jpg")
    st.markdown("<div class='login-box'>", unsafe_allow_html=True)
    st.markdown("## 🔐 Login to Resume Profiler")
    user = st.text_input("Username")
    pwd = st.text_input("Password", type="password")
    if st.button("Login"):
        if user == "admin" and pwd == "admin":
            st.session_state.page = "upload"
            st.rerun()
        else:
            st.error("❌ Invalid credentials")
    st.markdown("</div>", unsafe_allow_html=True)

elif st.session_state.page == "upload":
    st.header("📄 Upload Job Description and Resumes")
    if st.button("🔙 Back to Login"):
        st.session_state.page = "login"
        st.rerun()

    jd_text = st.text_area("📌 Paste Job Description Here", height=180)
    resumes = st.file_uploader("📂 Upload Resumes (PDF)", type="pdf", accept_multiple_files=True)

    if st.button("📊 Analyze Resumes"):
        if not jd_text or not resumes:
            st.warning("Upload resumes and paste JD to proceed.")
            st.stop()
        st.session_state.jd_text = jd_text
        st.session_state.resumes = resumes
        st.session_state.page = "results"
        st.rerun()

elif st.session_state.page == "results":
    st.header("📋 Resume Analysis Results")
    jd_keywords = extract_jd_keywords(st.session_state.jd_text)
    results = []

    for resume in st.session_state.resumes:
        text = extract_text_from_pdf(resume)
        email, phone = extract_contact_info(text)
        sections = extract_sections(text)
        found_skills = find_skills_in_resume(text, jd_keywords)
        score, feedback, matched = generate_feedback(found_skills, jd_keywords)

        results.append({
            "name": resume.name,
            "email": email,
            "phone": phone,
            "education": sections.get("education", "Not found"),
            "projects": sections.get("projects", "Not found"),
            "certifications": sections.get("certifications", "Not found"),
            "skills": found_skills,
            "common_skills": matched,
            "jd_score": score,
            "feedback": feedback
        })

    # Sort by JD score descending
    results.sort(key=lambda x: x["jd_score"], reverse=True)

    for r in results:
        with st.expander(f"📂 {r['name']} — 🎯 JD Match Score: {r['jd_score']}%", expanded=False):
            st.write(f"📧 **Email:** {r['email']} &nbsp;&nbsp;&nbsp;&nbsp; 📞 **Phone:** {r['phone']}")
            st.markdown("### 🎓 Education")
            st.write(r["education"])
            st.markdown("### 💻 Projects")
            st.write(r["projects"])
            st.markdown("### 🏅 Certifications")
            st.write(r["certifications"])

            st.markdown("### 🧠 Skills Found")
            st.info(", ".join(r["skills"]) if r["skills"] else "None found.")
            st.success("**Common with JD:** " + ", ".join(r["common_skills"]) if r["common_skills"] else "None")

            st.markdown("### 💬 Feedback")
            for fb in r["feedback"]:
                st.write("- " + fb)

    # ---- JD Match Score Comparison Graph ----
    st.subheader("📊 Comparison of Resumes Based on JD Match Score")
    names = [r["name"] for r in results]
    scores = [r["jd_score"] for r in results]

    fig, ax = plt.subplots(figsize=(8, 6))
    ax.barh(names, scores, color="skyblue")
    ax.set_xlabel("JD Match Score (%)")
    ax.set_ylabel("Resume")
    ax.set_title("Comparison of Resumes Based on JD Match Score")
    ax.invert_yaxis()  # Highest score on top
    for i, v in enumerate(scores):
        ax.text(v + 1, i, f"{v}%", va="center")
    st.pyplot(fig)

    if st.button("🔙 Back"):
        st.session_state.page = "upload"
        st.rerun()

