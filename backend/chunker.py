# backend/chunker.py
# Fetches file content from GitHub and saves chunks to MySQL

from github import Github
from langchain_text_splitters import RecursiveCharacterTextSplitter
from database import SessionLocal, RepoFile, CodeChunk
from dotenv import load_dotenv
import os

load_dotenv()

def chunk_text(text: str, chunk_size: int = 500, overlap: int = 50) -> list:
    """
    Splits text into overlapping chunks using LangChain's text splitter.
    chunk_size and overlap are counted in WORDS (same as before).
    The splitter breaks on lines, then words, so code keeps its line
    structure instead of being flattened into one long line.
    overlap = shared words between chunks for better context
    """
    splitter = RecursiveCharacterTextSplitter(
        chunk_size=chunk_size,
        chunk_overlap=overlap,
        length_function=lambda t: len(t.split()),   # measure size in words
        separators=["\n", " ", ""]                  # lines first -> keeps ~50-word overlap
    )
    return splitter.split_text(text)


def fetch_and_chunk_repo(repo_id: int, repo_url: str):
    """
    1. Gets all files for repo from MySQL
    2. Fetches content from GitHub
    3. Splits into chunks
    4. Saves chunks to MySQL
    """
    print("=" * 50)
    print(f" Starting chunking pipeline for repo_id={repo_id}")
    print("=" * 50)

    # Setup GitHub connection
    token = os.getenv("GITHUB_TOKEN")
    g = Github(token)
    repo_name = repo_url.replace("https://github.com/", "").strip("/")
    repo = g.get_repo(repo_name)

    db = SessionLocal()

    try:
        # Get all files for this repo
        files = db.query(RepoFile).filter(
            RepoFile.repo_id == repo_id
        ).all()

        print(f"\n Processing {len(files)} files...")

        total_chunks = 0
        processed    = 0

        for file in files:
            # Skip if chunks already exist for this file
            existing = db.query(CodeChunk).filter(
                CodeChunk.file_id == file.id
            ).first()
            if existing:
                continue

            try:
                # Fetch content from GitHub
                content_obj = repo.get_contents(file.path)
                content = content_obj.decoded_content.decode(
                    "utf-8", errors="ignore"
                )

                # Skip empty files
                if not content.strip():
                    continue

                # Split into chunks
                chunks = chunk_text(content)

                # Save each chunk to MySQL
                for i, chunk_text_content in enumerate(chunks):
                    chunk = CodeChunk(
                        file_id     = file.id,
                        chunk_index = i,
                        content     = chunk_text_content
                    )
                    db.add(chunk)

                total_chunks += len(chunks)
                processed    += 1

                # Commit every 50 files to avoid memory issues
                if processed % 50 == 0:
                    db.commit()
                    print(f"    Processed {processed}/{len(files)} files...")

            except Exception as e:
                # Skip files that can't be read
                continue

        # Final commit
        db.commit()

        print(f"\n Chunking complete!")
        print(f"   Files processed: {processed}")
        print(f"   Total chunks saved: {total_chunks}")

    finally:
        db.close()


if __name__ == "__main__":
    fetch_and_chunk_repo(
        repo_id  = 2,
        repo_url = "https://github.com/tiangolo/fastapi"
    )