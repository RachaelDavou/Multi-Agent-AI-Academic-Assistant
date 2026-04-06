# Multi-Agent AI Academic Assistant — Streamlit Application
import os
import re
import sys
from pathlib import Path

import streamlit as st
from dotenv import load_dotenv
import plotly.graph_objects as go
import plotly.express as px

sys.path.insert(0, os.path.dirname(__file__))
load_dotenv()


from utils.session import StudentSession
from agents.orchestrator import OrchestratorAgent
from rag.document_loader import load_file
from rag.vector_store import (
    get_catalogue_store as _get_catalogue_store,
    get_upload_store as _get_upload_store,
    add_documents,
    clear_upload_store,
    get_retriever,
)


# Cache the vector stores so ChromaDB and OpenAI Embeddings are only initialised once
@st.cache_resource
def get_catalogue_store():
    return _get_catalogue_store()


@st.cache_resource
def get_upload_store():
    return _get_upload_store()


# Page config
st.set_page_config(
    page_title="AI Academic Assistant",
    page_icon="🎓",
    layout="wide",
    initial_sidebar_state="expanded",
)

COURSE_CATALOGUE_DIR = os.path.join(os.path.dirname(__file__), "data", "course_catalogue")
UPLOADS_DIR = os.path.join(os.path.dirname(__file__), "data", "uploads")


# Function to inject the CSS stylesheet
def load_css():
    css_path = os.path.join(os.path.dirname(__file__), "style.css")
    with open(css_path, encoding="utf-8") as f:
        st.markdown(f"<style>{f.read()}</style>", unsafe_allow_html=True)


# Function to initialise all session state keys with defaults
def init_session():
    defaults = {
        "student_session": StudentSession("Student"),
        "orchestrator": None,
        "messages": [],
        "catalogue_indexed": False,
        "available_courses": [],
        "quiz_state": None,
        "quiz_answers": {},
        "quiz_submitted": False,
    }
    for key, val in defaults.items():
        if key not in st.session_state:
            st.session_state[key] = val


# Function to return the orchestrator, recreating it if the code version has changed
def get_orchestrator() -> OrchestratorAgent:
    cached = st.session_state.orchestrator
    if cached is None or getattr(cached, "_version", 0) < OrchestratorAgent._version:
        st.session_state.orchestrator = OrchestratorAgent(
            session=st.session_state.student_session,
            openai_api_key=os.getenv("OPENAI_API_KEY", ""),
        )
    return st.session_state.orchestrator


# Function to index all catalogue docs into ChromaDB once per session.
# On Streamlit Cloud (detected via /mount/src path), skips auto-embedding
# because the ephemeral filesystem resets on every cold start and embedding
# large PDFs blocks the health check. Users can upload files instead.
def ensure_catalogue_indexed():
    if st.session_state.catalogue_indexed:
        return

    catalogue_files = sorted([
        f for f in Path(COURSE_CATALOGUE_DIR).iterdir()
        if f.suffix.lower() in {".pdf", ".txt", ".docx"}
    ])
    st.session_state.available_courses = [f.stem for f in catalogue_files]

    # Detect Streamlit Cloud by checking the mount path
    on_cloud = Path("/mount/src").exists()

    if catalogue_files and not on_cloud:
        store = get_catalogue_store()
        # Only embed if the collection is empty — skips re-embedding on restart
        if store._collection.count() == 0:
            docs = []
            for f in catalogue_files:
                docs.extend(load_file(str(f), source_label=f.stem))
            if docs:
                add_documents(store, docs)

    st.session_state.catalogue_indexed = True
    _rebuild_retriever()


# Function to rebuild the tutor retriever based on what materials are active
def _rebuild_retriever():
    orch = get_orchestrator()
    selected = st.session_state.student_session.selected_courses
    uploads = st.session_state.student_session.uploaded_files

    if uploads:
        retriever = get_retriever(get_upload_store(), k=5)
    elif selected:
        # Filter the catalogue store to only the selected course documents
        filter_dict = {"source": {"$in": selected}}
        retriever = get_retriever(get_catalogue_store(), k=5, filter=filter_dict)
    else:
        retriever = get_retriever(get_catalogue_store(), k=5)

    orch.set_retriever(retriever)


# Function to render the sidebar and return the selected page
def render_sidebar():
    with st.sidebar:
        # Brand header
        st.markdown(
            """
            <div style="padding: 0.25rem 0.5rem 1.2rem 0.5rem; display:flex; align-items:center; gap:10px;">
                <div style="background:#22C55E; border-radius:8px; width:32px; height:32px; display:flex; align-items:center; justify-content:center; flex-shrink:0;">
                    <svg width="18" height="18" viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2.5" stroke-linecap="round" stroke-linejoin="round">
                        <path d="M22 10v6M2 10l10-5 10 5-10 5z"/><path d="M6 12v5c3 3 9 3 12 0v-5"/>
                    </svg>
                </div>
                <div>
                    <div style="font-size:1.1rem; font-weight:800; color:#F1F5F9; letter-spacing:-0.3px;">Academic Assistant</div>
                    <div style="font-size:0.72rem; color:#64748B; margin-top:1px;">Multi-Agent AI Tutor</div>
                </div>
            </div>
            """,
            unsafe_allow_html=True,
        )

        # Student name input
        name = st.text_input(
            "Your name",
            value=st.session_state.student_session.student_name,
            label_visibility="collapsed",
            placeholder="Enter your name...",
        )
        if name != st.session_state.student_session.student_name:
            st.session_state.student_session.student_name = name

        st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

        # Navigation radio — clicking switches the main page
        page = st.radio(
            "Navigation",
            options=["Chat", "Course Catalogue", "Quiz", "Analytics", "Summarizer"],
            label_visibility="collapsed",
            key="active_page",
        )

        st.markdown("<div style='margin:12px 0; border-top:1px solid rgba(255,255,255,0.07)'></div>", unsafe_allow_html=True)

        # Show which courses and uploads are currently active
        selected = st.session_state.student_session.selected_courses
        uploads = st.session_state.student_session.uploaded_files
        if selected or uploads:
            st.markdown("<div style='font-size:0.72rem;font-weight:600;letter-spacing:0.6px;text-transform:uppercase;color:#475569;margin-bottom:6px'>Active Context</div>", unsafe_allow_html=True)
            for c in selected:
                st.markdown(f"<div style='font-size:0.8rem;color:#86EFAC;padding:2px 0;display:flex;align-items:center;gap:6px'><svg width='12' height='12' viewBox='0 0 24 24' fill='none' stroke='#86EFAC' stroke-width='2.5' stroke-linecap='round' stroke-linejoin='round'><path d='M4 19.5A2.5 2.5 0 0 1 6.5 17H20'/><path d='M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z'/></svg>{c}</div>", unsafe_allow_html=True)
            for u in uploads:
                st.markdown(f"<div style='font-size:0.8rem;color:#93C5FD;padding:2px 0;display:flex;align-items:center;gap:6px'><svg width='12' height='12' viewBox='0 0 24 24' fill='none' stroke='#93C5FD' stroke-width='2.5' stroke-linecap='round' stroke-linejoin='round'><path d='M21.44 11.05l-9.19 9.19a6 6 0 0 1-8.49-8.49l9.19-9.19a4 4 0 0 1 5.66 5.66l-9.2 9.19a2 2 0 0 1-2.83-2.83l8.49-8.48'/></svg>{u}</div>", unsafe_allow_html=True)
            st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
        else:
            st.markdown("<div style='font-size:0.78rem;color:#475569;padding:2px 0'>No materials selected — using general knowledge</div>", unsafe_allow_html=True)
            st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)

        # Reset button wipes all session state and restarts
        if st.button("Reset Session", use_container_width=True):
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.rerun()

    return page

# Function to convert common LLM LaTeX delimiters to Streamlit-compatible $...$ notation
def format_math(text: str) -> str:
    # \[ ... \] → display math
    text = re.sub(
        r'\\\[\s*(.+?)\s*\\\]',
        lambda m: f'\n$$\n{m.group(1).strip()}\n$$\n',
        text, flags=re.DOTALL,
    )
    # \( ... \) → inline math
    text = re.sub(
        r'\\\(\s*(.+?)\s*\\\)',
        lambda m: f'${m.group(1).strip()}$',
        text, flags=re.DOTALL,
    )
    # [ LaTeX ] → display math when the content contains backslash commands
    def _sq(m):
        c = m.group(1).strip()
        return f'\n$$\n{c}\n$$\n' if '\\' in c else m.group(0)
    text = re.sub(r'(?<!\[)\[([^\[\]]{4,})\](?!\])', _sq, text)
    # ( LaTeX ) → inline math when the content contains backslash commands
    def _par(m):
        c = m.group(1).strip()
        return f'${c}$' if '\\' in c else m.group(0)
    text = re.sub(r'\(([^()]{4,})\)', _par, text)
    return text


# Function to render the Chat page
def render_chat():
    st.markdown(
        """
        <div class="hero-section">
            <div class="hero-badge">Multi-Agent AI System</div>
            <div class="hero-title">Academic Assistant</div>
            <div class="hero-subtitle">
                Powered by <span class="tech-tag">LangChain</span> ·
                <span class="tech-tag">AutoGen</span> ·
                <span class="tech-tag">GPT-4o-mini</span>
            </div>
            <div class="feature-cards">
                <div class="feature-card" style="background:#5B8DB8;">
                    <div class="feature-card-icon">
                        <svg viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                            <circle cx="12" cy="12" r="10"/><path d="M12 8v4l3 3"/>
                        </svg>
                    </div>
                    <div class="feature-card-label">4 AI Agents</div>
                </div>
                <div class="feature-card" style="background:#6BAA8C;">
                    <div class="feature-card-icon">
                        <svg viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                            <path d="M4 19.5A2.5 2.5 0 0 1 6.5 17H20"/><path d="M6.5 2H20v20H6.5A2.5 2.5 0 0 1 4 19.5v-15A2.5 2.5 0 0 1 6.5 2z"/>
                        </svg>
                    </div>
                    <div class="feature-card-label">RAG Pipeline</div>
                </div>
                <div class="feature-card" style="background:#B8956A;">
                    <div class="feature-card-icon">
                        <svg viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                            <line x1="18" y1="20" x2="18" y2="10"/><line x1="12" y1="20" x2="12" y2="4"/><line x1="6" y1="20" x2="6" y2="14"/>
                        </svg>
                    </div>
                    <div class="feature-card-label">Analytics</div>
                </div>
                <div class="feature-card" style="background:#8B7BB8;">
                    <div class="feature-card-icon">
                        <svg viewBox="0 0 24 24" fill="none" stroke="white" stroke-width="2" stroke-linecap="round" stroke-linejoin="round">
                            <path d="M9 11l3 3L22 4"/><path d="M21 12v7a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h11"/>
                        </svg>
                    </div>
                    <div class="feature-card-label">Quizzes</div>
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    # Map agent names to emoji avatars for chat bubbles
    agent_colors = {
        "TutorAgent": "🔵",
        "AnalyticsAgent": "🟢",
        "SupportAgent": "🟡",
        "Collaboration (TutorBot + AnalyticsBot)": "🟣",
    }

    # Display existing message history
    for msg in st.session_state.messages:
        if msg["role"] == "user":
            with st.chat_message("user"):
                st.markdown(msg["content"])
        else:
            agent = msg.get("agent", "Assistant")
            icon = agent_colors.get(agent, "🤖")
            with st.chat_message("assistant", avatar=icon):
                st.caption(f"**{agent}**")
                st.markdown(format_math(msg["content"]))
                if msg.get("sources"):
                    st.caption(f"Sources: {', '.join(msg['sources'])}")

    # Web search toggle sits just above the chat input
    web_col, _ = st.columns([1, 5])
    with web_col:
        web_search = st.toggle("🌐 Web Search", key="web_search_enabled", value=False,
                               help="Supplement answers with live DuckDuckGo results")

    if prompt := st.chat_input("Ask anything — tutoring, analytics, or support..."):
        st.session_state.messages.append({"role": "user", "content": prompt})
        with st.chat_message("user"):
            st.markdown(prompt)

        orch = get_orchestrator()
        web_search = st.session_state.get("web_search_enabled", False)

        with st.chat_message("assistant", avatar="🤖"):
            with st.spinner("Thinking..."):
                result = orch.route(prompt, web_search=web_search)

            agent = result.get("agent", "Assistant")
            icon = agent_colors.get(agent, "🤖")
            st.caption(f"**{agent}**")
            answer = result.get("answer", result.get("analysis", ""))
            st.markdown(format_math(answer))
            if result.get("sources"):
                st.caption(f"Sources: {', '.join(result['sources'])}")

        st.session_state.messages.append({
            "role": "assistant",
            "content": answer,
            "agent": agent,
            "sources": result.get("sources", []),
        })


# Function to render the Course Catalogue page (includes upload section)
def render_catalogue():
    st.markdown("## Course Catalogue")

    # Pre-loaded course materials section
    st.markdown("### Pre-loaded Course Materials")
    st.markdown("<p style='color:#64748B;font-size:0.9rem'>Select which courses the AI should focus on. Unselected courses are still searchable but deprioritized.</p>", unsafe_allow_html=True)

    # On Streamlit Cloud, auto-embedding is disabled to prevent startup timeouts.
    # Show a notice so users know to upload files for RAG-grounded answers.
    if Path("/mount/src").exists():
        st.info("ℹ️ Running on Streamlit Cloud — pre-loaded course materials are listed below but not auto-indexed. Upload a PDF below to enable RAG-grounded answers for this session.")

    catalogue_files = sorted([
        f for f in Path(COURSE_CATALOGUE_DIR).iterdir()
        if f.suffix.lower() in {".pdf", ".txt", ".docx"}
    ])
    if not catalogue_files:
        st.info("No course catalogue files found in `data/course_catalogue/`.")
    else:
        selected = list(st.session_state.student_session.selected_courses)
        changed = False

        cols = st.columns(2)
        for i, f in enumerate(catalogue_files):
            name = f.stem
            is_active = name in selected
            with cols[i % 2]:
                col_left, col_right = st.columns([4, 1])
                with col_left:
                    st.markdown(
                        f"""<div class="catalogue-card{'--active' if is_active else ''}">
                            <div class="cat-icon">📗</div>
                            <div>
                                <div class="cat-name">{name.replace('_', ' ').title()}</div>
                                <div class="cat-file">{f.name}</div>
                            </div>
                        </div>""",
                        unsafe_allow_html=True,
                    )
                with col_right:
                    st.markdown("<div style='height:8px'></div>", unsafe_allow_html=True)
                    label = "Remove" if is_active else "Add"
                    if st.button(label, key=f"cat_{name}"):
                        if is_active:
                            selected.remove(name)
                        else:
                            selected.append(name)
                            # Embed this PDF on demand if not already in the store
                            store = get_catalogue_store()
                            already_indexed = store._collection.count() > 0 and any(
                                m.get("source") == name
                                for m in (store._collection.get(where={"source": name}, limit=1).get("metadatas") or [])
                            )
                            if not already_indexed:
                                with st.spinner(f"Indexing {name}..."):
                                    docs = load_file(str(f), source_label=name)
                                    if docs:
                                        add_documents(store, docs)
                        changed = True

        if changed:
            st.session_state.student_session.selected_courses = selected
            _rebuild_retriever()
            st.rerun()

        if selected:
            st.success(f"**Active courses ({len(selected)}):** {', '.join(selected)}")
        else:
            st.info("No courses selected — AI will search across all catalogue materials.")

    st.markdown("---")

    # Upload your own files section
    st.markdown("### 📤 Upload Your Own Files")
    st.markdown("<p style='color:#64748B;font-size:0.9rem'>Upload your own study materials (PDF, DOCX, TXT). The AI will prioritise these for your session.</p>", unsafe_allow_html=True)

    uploaded = st.file_uploader(
        "Drop files here",
        type=["pdf", "docx", "txt"],
        accept_multiple_files=True,
        label_visibility="collapsed",
    )

    if uploaded and st.button("Index Files", use_container_width=True):
        with st.spinner("Processing files..."):
            _process_uploads(uploaded)

    uploads_active = st.session_state.student_session.uploaded_files
    if uploads_active:
        st.markdown("#### Indexed Uploads")
        for name in uploads_active:
            st.markdown(
                f"<div class='catalogue-card--active'><span style='margin-right:8px'>📎</span><span style='color:#1E293B;font-weight:500'>{name}</span></div>",
                unsafe_allow_html=True,
            )
        if st.button("Clear All Uploads", use_container_width=True):
            clear_upload_store()
            st.session_state.student_session.uploaded_files = []
            _rebuild_retriever()
            st.rerun()




# Function to save and index user-uploaded files into the upload vector store
def _process_uploads(uploaded_files):
    os.makedirs(UPLOADS_DIR, exist_ok=True)
    upload_store = get_upload_store()
    names = []
    for uf in uploaded_files:
        tmp_path = os.path.join(UPLOADS_DIR, uf.name)
        with open(tmp_path, "wb") as f:
            f.write(uf.read())
        try:
            docs = load_file(tmp_path, source_label=uf.name)
            add_documents(upload_store, docs)
            names.append(uf.name)
        except Exception as e:
            st.error(f"Failed to process {uf.name}: {e}")

    if names:
        st.session_state.student_session.uploaded_files.extend(names)
        _rebuild_retriever()
        st.success(f"Indexed: {', '.join(names)}")
        st.rerun()


# Function to parse the LLM's quiz text into structured question dicts.
# Handles two LLM output formats:
#   Format A (preferred): Q: / Correct: / Wrong1: / Wrong2: / Wrong3:
#   Format B (fallback):  Q: / A) B) C) D) / Answer: X
# Options are shuffled after parsing so the correct answer position varies each run.
def parse_quiz(quiz_text: str) -> list:
    import random
    questions = []
    blocks = re.split(r'\n(?=Q\d*[:.]\s)', quiz_text.strip())
    for block in blocks:
        if not block.strip():
            continue
        lines = [l.strip() for l in block.strip().split('\n') if l.strip()]
        q_text = None
        correct_text = None
        wrong_texts = []
        letter_options = {}   # for Format B
        answer_letter = None  # for Format B

        for line in lines:
            if re.match(r'^Q\d*[:.]\s', line):
                q_text = re.sub(r'^Q\d*[:.]\s*', '', line).strip()
            # Primary format: RIGHT / FAKE (no letters involved)
            elif re.match(r'^RIGHT:\s', line, re.IGNORECASE):
                correct_text = re.sub(r'^RIGHT:\s*', '', line, flags=re.IGNORECASE).strip()
            elif re.match(r'^FAKE:\s', line, re.IGNORECASE):
                w = re.sub(r'^FAKE:\s*', '', line, flags=re.IGNORECASE).strip()
                if w:
                    wrong_texts.append(w)
            # Legacy formats: Correct/Wrong or A/B/C/D+Answer — kept as fallback
            elif re.match(r'^Correct:\s', line, re.IGNORECASE):
                correct_text = re.sub(r'^Correct:\s*', '', line, flags=re.IGNORECASE).strip()
            elif re.match(r'^Wrong\d*:\s', line, re.IGNORECASE):
                w = re.sub(r'^Wrong\d*:\s*', '', line, flags=re.IGNORECASE).strip()
                if w:
                    wrong_texts.append(w)
            elif re.match(r'^[A-D][):.]\s', line):
                letter = line[0].upper()
                letter_options[letter] = re.sub(r'^[A-D][):.\s]+', '', line).strip()
            elif re.match(r'^Answer:\s*[A-D]', line, re.IGNORECASE):
                m = re.search(r'[A-D]', line, re.IGNORECASE)
                if m:
                    answer_letter = m.group().upper()

        if not q_text:
            continue

        # Resolve correct + wrongs — prefer letter-free formats
        if correct_text and wrong_texts:
            pass  # RIGHT/FAKE or Correct/Wrong format — already resolved
        elif letter_options and answer_letter and answer_letter in letter_options:
            # Last resort: A/B/C/D+Answer — trust the letter but it may be wrong
            correct_text = letter_options[answer_letter]
            wrong_texts = [v for k, v in letter_options.items() if k != answer_letter]
        else:
            continue  # unparseable block

        # Shuffle all options and assign A/B/C/D randomly
        all_options = [correct_text] + wrong_texts[:3]
        random.shuffle(all_options)
        letters = ["A", "B", "C", "D"]
        options = {letters[i]: all_options[i] for i in range(len(all_options))}
        answer = next(l for l, v in options.items() if v == correct_text)
        questions.append({"question": q_text, "options": options, "answer": answer})

    random.shuffle(questions)
    return questions


# Function to render the Quiz page
def render_quiz():
    st.markdown("## Quiz Generator")

    col1, col2 = st.columns([3, 1])
    with col1:
        topic = st.text_input("Topic to quiz on", placeholder="e.g. Machine Learning, Python, Calculus")
    with col2:
        num_q = st.number_input("Number of questions", min_value=1, max_value=20, value=5, step=1)

    if st.button("Generate Quiz", use_container_width=True) and topic:
        orch = get_orchestrator()
        with st.spinner("Generating quiz..."):
            # handle_quiz now returns a ready-to-use list — no text parsing needed
            questions = orch.handle_quiz(topic, num_questions=num_q)
        st.session_state.quiz_state = {"topic": topic, "questions": questions}
        st.session_state.quiz_answers = {}
        st.session_state.quiz_submitted = False
        st.rerun()

    if st.session_state.quiz_state:
        qstate = st.session_state.quiz_state
        questions = qstate["questions"]
        st.markdown("---")

        if not st.session_state.quiz_submitted:
            # Active quiz — show each question as a radio group
            st.markdown(f"### Quiz: {qstate['topic']}")
            st.caption(f"{len(questions)} questions — select one answer per question")

            for i, q in enumerate(questions):
                st.markdown(
                    f'<div class="quiz-question-card"><div class="quiz-q-label">Question {i + 1} of {len(questions)}</div>',
                    unsafe_allow_html=True,
                )
                opts = list(q["options"].keys())
                labels = [f"{k})  {q['options'][k]}" for k in opts]
                choice = st.radio(
                    q["question"],
                    options=opts,
                    format_func=lambda k, opts=opts, labels=labels: labels[opts.index(k)],
                    key=f"quiz_q_{i}",
                    index=None,
                )
                st.session_state.quiz_answers[i] = choice
                st.markdown('</div>', unsafe_allow_html=True)

            answered = sum(1 for v in st.session_state.quiz_answers.values() if v is not None)
            st.caption(f"{answered}/{len(questions)} answered")

            # Submit button stays disabled until all questions are answered
            if st.button("Submit Quiz ✓", use_container_width=True, disabled=(answered < len(questions))):
                score = sum(
                    1 for i, q in enumerate(questions)
                    if st.session_state.quiz_answers.get(i) == q["answer"]
                )
                get_orchestrator().record_quiz_score(qstate["topic"], score, len(questions))
                st.session_state.quiz_state["score"] = score
                st.session_state.quiz_submitted = True
                st.rerun()

        else:
            # Results screen — show score card and per-question review
            score = qstate.get("score", 0)
            total = len(questions)
            pct = round(score / total * 100)
            grade = "pass" if pct >= 80 else "warn" if pct >= 60 else "fail"
            emoji = "🎉" if pct >= 80 else "💪" if pct >= 60 else "📖"
            label = "Excellent work!" if pct >= 80 else "Good effort — review weak areas." if pct >= 60 else "Keep studying — you've got this."

            st.markdown(
                f'<div class="quiz-results-card {grade}">'
                f'<div class="quiz-score-big {grade}">{pct}%</div>'
                f'<div class="quiz-score-label">{emoji} {score}/{total} correct &nbsp;·&nbsp; {label}</div>'
                f'</div>',
                unsafe_allow_html=True,
            )

            st.markdown("#### Review")
            for i, q in enumerate(questions):
                user = st.session_state.quiz_answers.get(i)
                correct = user == q["answer"]
                row_cls = "correct" if correct else "wrong"
                icon = "✅" if correct else "❌"
                correct_text = q["options"].get(q["answer"], q["answer"])
                user_text = q["options"].get(user, user) if user else "No answer"
                detail = (
                    f'<div class="answer-correct-reveal">Correct! {q["answer"]}) {correct_text}</div>'
                    if correct else
                    f'<div class="answer-your-pick">Your answer: {user}) {user_text}</div>'
                    f'<div class="answer-correct-reveal">Correct: {q["answer"]}) {correct_text}</div>'
                )
                st.markdown(
                    f'<div class="answer-row {row_cls}">'
                    f'<span class="answer-icon">{icon}</span>'
                    f'<div class="answer-text"><strong>Q{i+1}:</strong> {q["question"]}{detail}</div>'
                    f'</div>',
                    unsafe_allow_html=True,
                )

            if st.button("Take Another Quiz", use_container_width=True):
                st.session_state.quiz_state = None
                st.session_state.quiz_answers = {}
                st.session_state.quiz_submitted = False
                st.rerun()


# Function to render the Analytics dashboard
def render_analytics():
    st.markdown("## Learning Analytics")

    session = st.session_state.student_session
    orch = get_orchestrator()
    data = orch.analytics.get_progress_data(session)

    # Summary metric cards at the top
    col1, col2, col3, col4 = st.columns(4)
    col1.metric("Topics Studied", len(data["topics_studied"]))
    col2.metric("Quizzes Taken", len(data["quiz_scores"]))
    col3.metric("Avg Quiz Score", f"{data['average_score']}%")
    col4.metric("Session Time", f"{data['session_duration']} min")

    if data["quiz_scores"]:
        st.markdown("#### Quiz Performance")
        fig = go.Figure(go.Bar(
            x=data["quiz_topics"],
            y=data["quiz_scores"],
            # Green for pass, amber for average, red for fail
            marker_color=["#22C55E" if s >= 80 else "#F59E0B" if s >= 60 else "#EF4444"
                          for s in data["quiz_scores"]],
            text=[f"{s}%" for s in data["quiz_scores"]],
            textposition="outside",
        ))
        fig.update_layout(
            yaxis_title="Score (%)", xaxis_title="Topic",
            yaxis_range=[0, 115],
            plot_bgcolor="#1E293B",
            paper_bgcolor="#1E293B",
            font=dict(color="#FFFFFF", size=13),
            xaxis=dict(tickfont=dict(color="#FFFFFF", size=12), title_font=dict(color="#FFFFFF")),
            yaxis=dict(tickfont=dict(color="#FFFFFF", size=12), title_font=dict(color="#FFFFFF"),
                       gridcolor="#334155"),
        )
        st.plotly_chart(fig, use_container_width=True)

    if data["topics_studied"]:
        st.markdown("#### Topics Coverage")
        fig2 = px.pie(names=data["topics_studied"], title="Topics Studied", hole=0.3)
        fig2.update_traces(
            textposition="auto",
            textinfo="label+percent",
            textfont_size=14,
            textfont_color="#FFFFFF",
            pull=[0.03] * len(data["topics_studied"]),
        )
        fig2.update_layout(
            paper_bgcolor="#1E293B",
            plot_bgcolor="#1E293B",
            font=dict(color="#FFFFFF", size=13),
            title=dict(text="Topics Studied", font=dict(color="#FFFFFF", size=16)),
            legend=dict(
                font=dict(color="#FFFFFF", size=13),
                bgcolor="rgba(0,0,0,0)",
            ),
            margin=dict(t=60, b=40, l=20, r=20),
        )
        st.plotly_chart(fig2, use_container_width=True)

    if data["weak_areas"]:
        st.markdown("#### Weak Areas")
        for area in data["weak_areas"]:
            st.error(area)

    st.markdown("---")
    st.markdown("#### AI Performance Analysis")
    if st.button("Generate Analysis"):
        with st.spinner("Analyzing..."):
            result = orch.analytics.analyze(session)
        st.info(result["analysis"])

    st.markdown("#### Study Plan Generator")
    hours = st.slider("Available study hours", 1.0, 8.0, 2.0, 0.5)
    if st.button("Generate Study Plan"):
        if data["weak_areas"]:
            with st.spinner("Creating your study plan..."):
                plan = orch.analytics.suggest_study_plan(data["weak_areas"], hours)
            st.markdown(plan)
        else:
            st.info("No weak areas identified yet. Take some quizzes first!")


# Function to render the Summarizer page
def render_summarizer():
    st.markdown("## Document Summarizer")

    # Choose the source to summarize
    source_mode = st.radio(
        "What would you like to summarize?",
        options=["Paste text", "Course material", "Uploaded file"],
        horizontal=True,
    )

    orch = get_orchestrator()
    text_to_summarize = None
    source_label = ""

    if source_mode == "Paste text":
        text_to_summarize = st.text_area(
            "Paste your text",
            height=220,
            label_visibility="collapsed",
            placeholder="Paste any text here — lecture notes, an article, a textbook excerpt...",
        )
        source_label = "Pasted text"

    elif source_mode == "Course material":
        catalogue_files = sorted([
        f for f in Path(COURSE_CATALOGUE_DIR).iterdir()
        if f.suffix.lower() in {".pdf", ".txt", ".docx"}
    ])
        if not catalogue_files:
            st.info("No course materials found. Add .txt files to data/course_catalogue/")
        else:
            names = [f.stem for f in catalogue_files]
            chosen = st.selectbox("Select a course document", names)
            if chosen:
                chosen_path = next(f for f in catalogue_files if f.stem == chosen)
                text_to_summarize = chosen_path.read_text(encoding="utf-8", errors="replace")
                source_label = chosen

    elif source_mode == "Uploaded file":
        uploads = st.session_state.student_session.uploaded_files
        if not uploads:
            st.info("No uploaded files yet. Go to Course Catalogue to upload your files.")
        else:
            chosen = st.selectbox("Select an uploaded file", uploads)
            if chosen:
                file_path = os.path.join(UPLOADS_DIR, chosen)
                try:
                    # Read raw text; for non-txt files use the document loader
                    if chosen.endswith(".txt"):
                        text_to_summarize = Path(file_path).read_text(encoding="utf-8")
                    else:
                        from rag.document_loader import load_file as _load
                        docs = _load(file_path)
                        text_to_summarize = "\n\n".join(d.page_content for d in docs)
                    source_label = chosen
                except Exception as e:
                    st.error(f"Could not read {chosen}: {e}")

    st.markdown("---")

    if text_to_summarize and st.button("Generate Summary", use_container_width=True):
        with st.spinner("Summarizing..."):
            summary = orch.tutor.summarize(text_to_summarize)
        if source_label:
            st.markdown(f"<div style='font-size:0.78rem;color:#64748B;margin-bottom:8px'>Source: {source_label}</div>", unsafe_allow_html=True)
        st.markdown("### Summary")
        st.markdown(format_math(summary))


# Main entry point
def main():
    init_session()
    load_css()

    if not os.getenv("OPENAI_API_KEY"):
        st.error("⚠️ OPENAI_API_KEY not found. Please add it to your .env file.")
        st.stop()

    page = render_sidebar()

    if page == "Chat":
        ensure_catalogue_indexed()
        render_chat()
    elif page == "Course Catalogue":
        ensure_catalogue_indexed()
        render_catalogue()
    elif page == "Quiz":
        ensure_catalogue_indexed()
        render_quiz()
    elif page == "Analytics":
        render_analytics()
    elif page == "Summarizer":
        ensure_catalogue_indexed()
        render_summarizer()


if __name__ == "__main__":
    main()
