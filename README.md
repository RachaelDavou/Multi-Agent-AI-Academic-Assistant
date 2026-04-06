# Multi-Agent AI Academic Assistant

A conversational academic assistant powered by four specialised AI agents that work together to tutor students, track their performance, and support their wellbeing all in one Streamlit app.

## Requirements

Install the dependencies:

```
pip install -r requirements.txt
```

You will also need an OpenAI API key. Get one at https://platform.openai.com/api-keys

## How to Run

### Option 1 — Live App (deployed)

Visit the deployed app at: [Add Streamlit Cloud URL here]

No setup needed. The app runs on Streamlit Community Cloud. ChromaDB is built on the server from the course catalogue PDFs the first time the app starts.

### Option 2 — Run locally

1. Create a `.env` file in the project root and add your API key:

```
OPENAI_API_KEY=sk-...
```

2. Run the app:

```
streamlit run app.py
```

ChromaDB will be created automatically in `data/chroma_db/` on first run.

## How It Works

Every message goes through the OrchestratorAgent, which reads the query and decides which specialist should handle it.

1. **Student sends a message** — through the chat, quiz, or support tab
2. **Intent classification** — the Orchestrator sends the message to the LLM with a prompt listing four categories (TUTOR, ANALYTICS, SUPPORT, COLLABORATION) and reads the single-word reply
3. **Routing** — the message is forwarded to the right agent
4. **RAG retrieval** — if the TutorAgent is handling it, it fetches the five most relevant chunks from ChromaDB before generating an answer
5. **Response** — the agent's answer is returned to the student

For COLLABORATION queries, both TutorBot and AnalyticsBot contribute to a single combined answer using an AutoGen group chat.

## Agents

| Agent | What it does |
|---|---|
| **OrchestratorAgent** | Classifies every query and routes it to the right agent. Launches AutoGen group chats for complex queries that need more than one specialist. |
| **TutorAgent** | Answers academic questions using RAG over the course catalogue and any uploaded files. Also generates multiple-choice quizzes on any topic. |
| **AnalyticsAgent** | Tracks quiz scores across the session, identifies weak areas, and generates a personalised study plan. |
| **SupportAgent** | Handles motivation, stress, study strategies, and general student wellbeing. |

## Features

- **Chat** — ask any academic question and get an answer grounded in course materials
- **Quiz** — generate multiple-choice questions on any topic; scores are tracked automatically
- **Analytics dashboard** — Plotly charts showing quiz performance per topic, colour-coded by score tier
- **Document upload** — upload your own PDF, DOCX, or TXT files to make them searchable in the same RAG pipeline
- **Summariser** — summarise any course document, uploaded file, or pasted text
- **Web search toggle** — optionally enrich tutor answers with live web context via DuckDuckGo
- **Multi-agent collaboration** — AutoGen group chats for queries that need both tutoring depth and performance data

## Tech Stack

| Layer | Technology |
|---|---|
| Language | Python 3.10 |
| LLM | OpenAI GPT-4o-mini |
| LLM Framework | LangChain + LangChain-OpenAI |
| Multi-Agent | AutoGen (`pyautogen`) |
| Embeddings | OpenAI text-embedding-3-small |
| Vector Store | ChromaDB (persistent) |
| UI | Streamlit |
| Visualisation | Plotly |
| Document Loaders | PyPDF, python-docx, LangChain TextLoader |

## Project Structure

```
Project_claude/
├── app.py                          # Streamlit app entry point
├── agents/
│   ├── orchestrator.py             # Routing + AutoGen collaboration
│   ├── tutor.py                    # RAG-powered tutoring + quiz generation
│   ├── analytics.py                # Performance tracking + study plans
│   └── support.py                  # Wellbeing + study strategies
├── rag/
│   ├── document_loader.py          # PDF/DOCX/TXT loader and chunker
│   └── vector_store.py             # ChromaDB vector store management
├── utils/
│   └── session.py                  # Student session and analytics tracking
├── data/
│   ├── course_catalogue/           # Pre-loaded OpenStax textbooks
│   ├── uploads/                    # Student-uploaded files (runtime only)
│   └── chroma_db/                  # ChromaDB embeddings (generated on first run)
├── notebooks/
│   └── academic_assistant_demo.ipynb
├── requirements.txt
├── .env.example
└── README.md
```

## Dataset

### Raw Dataset

Two open-access OpenStax textbooks in `data/course_catalogue/` (PDF format, CC BY 4.0):

| File | Title | Source | URL |
|------|-------|--------|-----|
| `Introduction to Computer Science.pdf` | Introduction to Computer Science | OpenStax | https://assets.openstax.org/oscms-prodcms/media/documents/Introduction_To_Computer_Science_-_WEB.pdf |
| `Introductory Statistics 2e.pdf` | Introductory Statistics, 2nd Edition | OpenStax | https://assets.openstax.org/oscms-prodcms/media/documents/Introductory_Statistics_2e_-_WEB.pdf |

All materials are licensed under [Creative Commons Attribution 4.0](https://creativecommons.org/licenses/by/4.0/).
© 1999–2026 Rice University. See [`SOURCES.md`](SOURCES.md) for full citations.

Students can also upload their own documents at runtime — these are embedded and searchable within that session.

### Cleaned Dataset

The raw PDFs are processed through a cleaning pipeline before being stored in ChromaDB:

1. Loaded with `PyPDFLoader` (LangChain)
2. Split into 800-character chunks with 100-character overlap using `RecursiveCharacterTextSplitter`
3. Embedded with OpenAI `text-embedding-3-small` (1536 dimensions)
4. Stored persistently in ChromaDB at `data/chroma_db/` with a `source` metadata tag per document

**Cleaning assumptions:**
- UTF-8 encoding with error replacement for non-standard characters
- Section headers serve as natural semantic boundaries
- Chunk overlap preserves context across split boundaries
- Only `.pdf`, `.docx`, and `.txt` files are indexed — other file types are ignored

See `notebooks/academic_assistant_demo.ipynb` for a full walkthrough of the pipeline.

## Submission Links

- **Live App:** (https://multi-agent-ai-academic-assistant-gc3etkh6nrr6yhutnh3pgz.streamlit.app/)
- **GitHub Repo:** (https://github.com/RachaelDavou/Multi-Agent-AI-Academic-Assistant)
- **Raw Dataset:** [data/course_catalogue/](data/course_catalogue/)
- **Cleaned Dataset:** `data/chroma_db/` (generated on first run from the PDFs)
- **Presentation Slides (PDF):** (https://raw.githubusercontent.com/RachaelDavou/Multi-Agent-AI-Academic-Assistant/main/Presentation.pdf)
