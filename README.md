# 🧠 GitHub Codebase Intelligence Platform

> Ask natural language questions about any GitHub repository using AI.

![Python](https://img.shields.io/badge/Python-3.11-blue)
![FastAPI](https://img.shields.io/badge/FastAPI-0.111-green)
![Streamlit](https://img.shields.io/badge/Streamlit-1.36-red)
![MySQL](https://img.shields.io/badge/MySQL-8.0-orange)
![ChromaDB](https://img.shields.io/badge/ChromaDB-0.5-purple)
![Groq](https://img.shields.io/badge/Groq-LLaMA3-yellow)

## 🎯 What It Does

Developers joining a new project spend **weeks** understanding the codebase.
This tool lets you ask plain English questions and get instant, accurate answers:

- *"Where is authentication implemented?"*
- *"How does error handling work?"*
- *"Explain the payment flow"*
- *"How do I define an API route?"*

## 🏗️ Architecture

```
User (Streamlit UI)
        ↓
FastAPI Backend
        ↓
┌─────────────────────────────────────┐
│  GitHub API  │  MySQL   │  ChromaDB │
│  (fetch code)│(metadata)│ (vectors) │
└─────────────────────────────────────┘
        ↓
   RAG Pipeline
        ↓
Groq (llama-3.1-8b-instant)
        ↓
Answer + File Citations
```

## 🛠️ Tech Stack

| Layer | Technology | Purpose |
|---|---|---|
| Frontend | Streamlit | Chat UI |
| Backend | FastAPI | REST API |
| Database | MySQL + SQLAlchemy | Repo & file metadata |
| Vector Store | ChromaDB | Code embeddings |
| Embeddings | sentence-transformers | Free local model |
| LLM | Groq (llama-3.1-8b-instant) | Answer generation |
| GitHub | PyGithub | Repo fetching |

## 🚀 Quick Start

### 1. Clone the repo
```bash
git clone https://github.com/YOUR_USERNAME/github-intelligence.git
cd github-intelligence
```

### 2. Create virtual environment
```bash
python -m venv venv
venv\Scripts\activate  # Windows
source venv/bin/activate  # Mac/Linux
```

### 3. Install dependencies
```bash
pip install -r requirements.txt
```

### 4. Set up environment variables
```bash
cp .env.example .env
# Edit .env with your actual API keys
```

### 5. Create MySQL database
```sql
CREATE DATABASE github_intel;
```

### 6. Run the backend
```bash
cd backend
uvicorn main:app --reload --port 8000
```

### 7. Run the frontend
```bash
cd frontend
streamlit run app.py
```

### 8. Open your browser
- **Frontend:** http://localhost:8501
- **API Docs:** http://localhost:8000/docs

## 📖 How It Works

1. **Index** — Paste any GitHub URL → app fetches all code files via GitHub API
2. **Chunk** — File content split into overlapping chunks for better context
3. **Embed** — Each chunk converted to a vector using sentence-transformers
4. **Search** — User question converted to vector, ChromaDB finds similar chunks
5. **Answer** — Groq LLM reads relevant chunks → generates accurate answer with citations

## 🔑 Environment Variables

| Variable | Description |
|---|---|
| `GITHUB_TOKEN` | GitHub Personal Access Token |
| `GROQ_API_KEY` | Groq API Key (free at console.groq.com) |
| `DATABASE_URL` | MySQL connection string |

## 📁 Project Structure

```
github-intelligence/
├── backend/
│   ├── main.py            # FastAPI server
│   ├── github_loader.py   # GitHub API fetching
│   ├── database.py        # MySQL models + queries
│   ├── indexer.py         # Repo indexing pipeline
│   ├── chunker.py         # File content chunking
│   ├── embedder.py        # Embeddings + ChromaDB
│   └── rag.py             # RAG pipeline
├── frontend/
│   └── app.py             # Streamlit UI
├── .env.example           # Environment template
├── requirements.txt       # Dependencies
└── README.md
```

## 🎓 Skills Demonstrated

- **RAG Pipeline** — Retrieval Augmented Generation from scratch
- **Vector Embeddings** — Semantic code search with ChromaDB
- **REST API Design** — FastAPI with async background tasks
- **SQL Database** — MySQL schema design with SQLAlchemy ORM
- **API Integration** — GitHub API with pagination + rate limiting
- **Full Stack** — End-to-end Python ML application

## 📄 License

MIT License — feel free to use this for your own projects!