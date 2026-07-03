# backend/database.py
# This file does 3 things:
# 1. Connects to MySQL
# 2. Defines our tables as Python classes (Models)
# 3. Provides helper functions to save/read data

from sqlalchemy import (
    create_engine, Column, Integer, String,
    Text, Boolean, DateTime, ForeignKey, BigInteger
)
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, relationship
from datetime import datetime
from dotenv import load_dotenv
import os

load_dotenv()

# ─── 1. DATABASE CONNECTION ────────────────────────────────

DATABASE_URL = os.getenv("DATABASE_URL")

# Engine = the actual connection to MySQL
engine = create_engine(
    DATABASE_URL,
    echo=False,       # Set True if you want to see SQL queries printed
    pool_pre_ping=True  # Auto-reconnect if connection drops
)

# SessionLocal = factory for database sessions
# A session = one conversation with the database
SessionLocal = sessionmaker(bind=engine)

# Base = parent class for all our models
Base = declarative_base()


# ─── 2. TABLE MODELS ──────────────────────────────────────

class Repo(Base):
    """
    Stores one row per GitHub repository.
    Example row:
        id=1, name="tiangolo/fastapi", stars=74000, is_indexed=True
    """
    __tablename__ = "repos"

    id          = Column(Integer, primary_key=True, autoincrement=True)
    github_url  = Column(String(500), unique=True, nullable=False)
    name        = Column(String(200))
    description = Column(Text)
    stars       = Column(Integer, default=0)
    language    = Column(String(100))
    is_indexed  = Column(Boolean, default=False)
    created_at  = Column(DateTime, default=datetime.utcnow)

    # Relationship — lets you do repo.files to get all files
    files = relationship("RepoFile", back_populates="repo",
                         cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Repo {self.name}>"


class RepoFile(Base):
    __tablename__ = "files"

    id          = Column(Integer, primary_key=True, autoincrement=True)
    repo_id     = Column(Integer, ForeignKey("repos.id"), nullable=False)
    path        = Column(String(1000), nullable=False)
    extension   = Column(String(20))
    size        = Column(BigInteger, default=0)
    content     = Column(Text)           # ← ADD THIS LINE
    created_at  = Column(DateTime, default=datetime.utcnow)

    repo   = relationship("Repo", back_populates="files")
    chunks = relationship("CodeChunk", back_populates="file",
                          cascade="all, delete-orphan")

    def __repr__(self):
        return f"<RepoFile {self.path}>"


class CodeChunk(Base):
    """
    Stores one row per code chunk (piece of a file).
    We'll fill this in Week 3 when we do embeddings.
    Example row:
        id=1, file_id=1, chunk_index=0, content="def login():..."
    """
    __tablename__ = "chunks"

    id            = Column(Integer, primary_key=True, autoincrement=True)
    file_id       = Column(Integer, ForeignKey("files.id"), nullable=False)
    chunk_index   = Column(Integer, default=0)
    content       = Column(Text, nullable=False)
    embedding_id  = Column(String(200))  # Links to ChromaDB (Week 3)
    created_at    = Column(DateTime, default=datetime.utcnow)

    # Relationship — back to parent file
    file = relationship("RepoFile", back_populates="chunks")

    def __repr__(self):
        return f"<CodeChunk file_id={self.file_id} chunk={self.chunk_index}>"


# ─── 3. HELPER FUNCTIONS ──────────────────────────────────

def get_db():
    """
    Returns a database session.
    Always close it after use — that's what the try/finally does.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def create_tables():
    """
    Creates all tables in MySQL if they don't exist yet.
    Safe to run multiple times — won't delete existing data.
    """
    Base.metadata.create_all(bind=engine)
    print(" Tables created successfully!")


def save_repo(db, repo_data: dict):
    """
    Saves a repo to the database.
    If it already exists (same URL), returns the existing one.
    """
    # Check if repo already exists
    existing = db.query(Repo).filter(
        Repo.github_url == repo_data["url"]
    ).first()

    if existing:
        print(f" Repo already exists: {existing.name}")
        return existing

    # Create new repo record
    repo = Repo(
        github_url  = repo_data["url"],
        name        = repo_data["name"],
        description = repo_data["description"],
        stars       = repo_data["stars"],
        language    = repo_data["language"],
        is_indexed  = False
    )
    db.add(repo)
    db.commit()
    db.refresh(repo)  # Get the auto-generated ID
    print(f" Saved repo: {repo.name} (id={repo.id})")
    return repo


def save_files(db, repo_id: int, files: list):
    """Saves all files of a repo to the database."""
    saved = 0
    for file_data in files:
        existing = db.query(RepoFile).filter(
            RepoFile.repo_id == repo_id,
            RepoFile.path == file_data["path"]
        ).first()

        if existing:
            # Update content if missing
            if not existing.content and file_data.get("content"):
                existing.content = file_data["content"]
                db.commit()
            continue

        file = RepoFile(
            repo_id   = repo_id,
            path      = file_data["path"],
            extension = file_data["extension"],
            size      = file_data["size"],
            content   = file_data.get("content", "")  # ← Save content
        )
        db.add(file)
        saved += 1

    db.commit()
    print(f" Saved {saved} files to database")

def mark_repo_indexed(db, repo_id: int):
    """Marks a repo as fully indexed."""
    repo = db.query(Repo).filter(Repo.id == repo_id).first()
    if repo:
        repo.is_indexed = True
        db.commit()
        print(f" Repo {repo.name} marked as indexed")


def get_all_repos(db):
    """Returns all repos in the database."""
    return db.query(Repo).all()


def get_repo_files(db, repo_id: int):
    """Returns all files for a given repo."""
    return db.query(RepoFile).filter(
        RepoFile.repo_id == repo_id
    ).all()