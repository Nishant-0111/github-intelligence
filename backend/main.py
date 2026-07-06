# backend/main.py
# This is the web server for our entire project.
# It exposes our pipeline as HTTP endpoints.

from fastapi import FastAPI, HTTPException, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from typing import Optional
import time

# Import our pipeline modules
from database import SessionLocal, Repo, RepoFile, CodeChunk, create_tables
from github_loader import fetch_repo_files, get_repo_metadata
from database import save_repo, save_files, mark_repo_indexed, get_all_repos
from embedder import embed_repo, search_code
from rag import ask_codebase

import os

# Get port from environment (Railway sets this automatically)
PORT = int(os.getenv("PORT", 8000))

# ─── APP SETUP ────────────────────────────────────────────

app = FastAPI(
    title="GitHub Codebase Intelligence API",
    description="Ask natural language questions about any GitHub repository",
    version="1.0.0"
)

# Allow frontend (Streamlit) to call this API
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"]
)

# Create DB tables on startup
create_tables()


# ─── REQUEST/RESPONSE MODELS ──────────────────────────────
# Pydantic models define what JSON the API accepts/returns
# FastAPI auto-validates all incoming data against these

class IndexRequest(BaseModel):
    repo_url: str           # e.g. "https://github.com/tiangolo/fastapi"

class QueryRequest(BaseModel):
    question: str           # e.g. "Where is authentication?"
    top_k: Optional[int] = 5  # How many chunks to retrieve

class IndexResponse(BaseModel):
    repo_id: int
    name: str
    status: str
    files_count: int

class QueryResponse(BaseModel):
    question: str
    answer: str
    sources: list
    repo_id: int

class RepoInfo(BaseModel):
    id: int
    name: str
    description: Optional[str]
    stars: int
    is_indexed: bool
    files_count: int


# ─── BACKGROUND TASK ──────────────────────────────────────

# Track indexing status in memory
# In production you'd use Redis for this
indexing_status = {}

def run_indexing(repo_url: str, repo_id: int):
    """
    Runs in the background so the API doesn't block.
    User gets immediate response, indexing happens behind scenes.
    """
    try:
        indexing_status[repo_id] = {
            "status": "fetching_files",
            "progress": 0
        }

        db = SessionLocal()

        # Fetch files from GitHub
        files = fetch_repo_files(repo_url)
        indexing_status[repo_id]["status"] = "saving_to_db"
        indexing_status[repo_id]["progress"] = 30

        # Save to MySQL
        save_files(db, repo_id, files)
        mark_repo_indexed(db, repo_id)
        db.close()

        indexing_status[repo_id]["status"] = "embedding"
        indexing_status[repo_id]["progress"] = 60

        # Create embeddings
        embed_repo(repo_id)

        indexing_status[repo_id]["status"] = "complete"
        indexing_status[repo_id]["progress"] = 100

    except Exception as e:
        indexing_status[repo_id] = {
            "status": "failed",
            "error": str(e)
        }


# ─── ENDPOINTS ────────────────────────────────────────────

@app.get("/")
def root():
    """Health check — confirms API is running."""
    return {
        "message": "GitHub Codebase Intelligence API is running!",
        "docs": "Visit /docs for interactive API documentation"
    }


@app.get("/health")
def health_check():
    """Detailed health check."""
    return {
        "status": "healthy",
        "version": "1.0.0"
    }


@app.post("/repos/index")
def index_repo(request: IndexRequest, background_tasks: BackgroundTasks):
    """
    Index a new GitHub repository.

    This endpoint:
    1. Validates the repo URL
    2. Fetches basic metadata from GitHub
    3. Saves repo to MySQL
    4. Starts background indexing (fetch files + embed)
    5. Returns immediately with repo_id

    The actual indexing happens in background — check
    /repos/{repo_id}/status to see progress.
    """
    db = SessionLocal()
    try:
        # Check if already indexed
        existing = db.query(Repo).filter(
            Repo.github_url == request.repo_url
        ).first()

        if existing:
            files_count = db.query(RepoFile).filter(
                RepoFile.repo_id == existing.id
            ).count()
            return {
                "repo_id"    : existing.id,
                "name"       : existing.name,
                "status"     : "already_indexed",
                "files_count": files_count
            }

        # Get metadata from GitHub
        try:
            metadata = get_repo_metadata(request.repo_url)
        except Exception as e:
            raise HTTPException(
                status_code=400,
                detail=f"Could not access GitHub repo: {str(e)}"
            )

        # Save repo record
        repo = save_repo(db, metadata)

        # Start background indexing
        background_tasks.add_task(run_indexing, request.repo_url, repo.id)

        return {
            "repo_id": repo.id,
            "name"   : repo.name,
            "status" : "indexing_started",
            "message": f"Indexing started! Check /repos/{repo.id}/status"
        }

    finally:
        db.close()


@app.get("/repos/{repo_id}/status")
def get_indexing_status(repo_id: int):
    """
    Check the indexing progress of a repo.
    Poll this endpoint every few seconds while indexing.
    """
    db = SessionLocal()
    try:
        repo = db.query(Repo).filter(Repo.id == repo_id).first()
        if not repo:
            raise HTTPException(status_code=404, detail="Repo not found")

        files_count  = db.query(RepoFile).filter(RepoFile.repo_id == repo_id).count()
        chunks_count = db.query(CodeChunk).filter(
            CodeChunk.file_id.in_(
                db.query(RepoFile.id).filter(RepoFile.repo_id == repo_id)
            )
        ).count()

        # Get background task status
        bg_status = indexing_status.get(repo_id, {})

        return {
            "repo_id"     : repo_id,
            "name"        : repo.name,
            "is_indexed"  : repo.is_indexed,
            "files_count" : files_count,
            "chunks_count": chunks_count,
            "status"      : bg_status.get("status", "complete" if repo.is_indexed else "not_started"),
            "progress"    : bg_status.get("progress", 100 if repo.is_indexed else 0)
        }
    finally:
        db.close()


@app.post("/repos/{repo_id}/query")
def query_repo(repo_id: int, request: QueryRequest):
    """
    Ask a natural language question about a repo.

    This is the core endpoint — it runs the full RAG pipeline:
    1. Embeds the question
    2. Searches ChromaDB for relevant code
    3. Sends context + question to LLM
    4. Returns answer with file citations
    """
    db = SessionLocal()
    try:
        # Check repo exists and is indexed
        repo = db.query(Repo).filter(Repo.id == repo_id).first()
        if not repo:
            raise HTTPException(status_code=404, detail="Repo not found")

        if not repo.is_indexed:
            raise HTTPException(
                status_code=400,
                detail="Repo is not fully indexed yet. Check /repos/{repo_id}/status"
            )

        # Run RAG pipeline
        try:
            result = ask_codebase(
                repo_id  = repo_id,
                question = request.question,
                top_k    = request.top_k
            )
        except Exception as e:
            raise HTTPException(
                status_code=500,
                detail=f"RAG pipeline error: {str(e)}"
            )

        return {
            "question": result["question"],
            "answer"  : result["answer"],
            "sources" : result["sources"],
            "repo_id" : repo_id
        }
    finally:
        db.close()


@app.get("/repos")
def list_repos():
    """List all indexed repositories."""
    db = SessionLocal()
    try:
        repos = db.query(Repo).all()
        result = []
        for repo in repos:
            files_count = db.query(RepoFile).filter(
                RepoFile.repo_id == repo.id
            ).count()
            result.append({
                "id"         : repo.id,
                "name"       : repo.name,
                "description": repo.description,
                "stars"      : repo.stars,
                "is_indexed" : repo.is_indexed,
                "files_count": files_count,
                "created_at" : str(repo.created_at)
            })
        return {"repos": result, "total": len(result)}
    finally:
        db.close()


@app.get("/repos/{repo_id}")
def get_repo(repo_id: int):
    """Get details of a specific repo."""
    db = SessionLocal()
    try:
        repo = db.query(Repo).filter(Repo.id == repo_id).first()
        if not repo:
            raise HTTPException(status_code=404, detail="Repo not found")

        files_count = db.query(RepoFile).filter(
            RepoFile.repo_id == repo_id
        ).count()

        chunks_count = db.query(CodeChunk).filter(
            CodeChunk.file_id.in_(
                db.query(RepoFile.id).filter(RepoFile.repo_id == repo_id)
            )
        ).count()

        return {
            "id"          : repo.id,
            "name"        : repo.name,
            "description" : repo.description,
            "stars"       : repo.stars,
            "language"    : repo.language,
            "github_url"  : repo.github_url,
            "is_indexed"  : repo.is_indexed,
            "files_count" : files_count,
            "chunks_count": chunks_count,
            "created_at"  : str(repo.created_at)
        }
    finally:
        db.close()


@app.delete("/repos/{repo_id}")
def delete_repo(repo_id: int):
    """Delete a repo and all its data."""
    db = SessionLocal()
    try:
        repo = db.query(Repo).filter(Repo.id == repo_id).first()
        if not repo:
            raise HTTPException(status_code=404, detail="Repo not found")

        name = repo.name
        db.delete(repo)
        db.commit()
        return {"message": f"Repo '{name}' deleted successfully"}
    finally:
        db.close()