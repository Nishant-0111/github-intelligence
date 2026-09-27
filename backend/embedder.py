# backend/embedder.py

from langchain_huggingface import HuggingFaceEmbeddings
from langchain_chroma import Chroma
from langchain_core.documents import Document
from database import SessionLocal, RepoFile, CodeChunk
import os

# ─── SETUP ────────────────────────────────────────────────

print(" Loading embedding model (first time downloads ~90MB)...")
EMBEDDING_MODEL = HuggingFaceEmbeddings(
    model_name="all-MiniLM-L6-v2",
    encode_kwargs={"normalize_embeddings": True}
)
print(" Model ready!")

CHROMA_PATH = os.path.join(os.path.dirname(__file__), "..", "chroma_db")


def get_vectorstore(repo_id: int) -> Chroma:
    """
    Returns the LangChain Chroma vector store for one repo.
    One collection per repo (repo_<id>), cosine distance -- same as before.
    """
    return Chroma(
        collection_name=f"repo_{repo_id}",
        embedding_function=EMBEDDING_MODEL,
        persist_directory=CHROMA_PATH,
        collection_metadata={"hnsw:space": "cosine"}
    )


def count_vectors(vectorstore: Chroma) -> int:
    """How many vectors are stored in this collection."""
    return len(vectorstore.get(include=[])["ids"])


# ─── CHUNKING ─────────────────────────────────────────────

def split_into_chunks(content: str, chunk_size=800, overlap=150) -> list:
    """Split code into overlapping chunks."""
    if not content or not content.strip():
        return []

    chunks = []
    current = ""
    lines = content.split("\n")

    for line in lines:
        if len(current) + len(line) < chunk_size:
            current += line + "\n"
        else:
            if current.strip():
                chunks.append(current.strip())
            overlap_text = current[-overlap:] if len(current) > overlap else current
            current = overlap_text + line + "\n"

    if current.strip():
        chunks.append(current.strip())

    return chunks


# ─── MAIN PIPELINE ────────────────────────────────────────

def embed_repo(repo_id: int):
    """
    Full embedding pipeline for a repo:
    1. Load chunks from MySQL (already saved by chunker.py)
    2. Embed each chunk
    3. Store in ChromaDB
    """
    db = SessionLocal()

    try:
        # Get the ChromaDB vector store (one collection per repo)
        collection_name = f"repo_{repo_id}"
        vectorstore = get_vectorstore(repo_id)

        # Check if already embedded
        if count_vectors(vectorstore) > 0:
            print(f"✅ Already embedded {count_vectors(vectorstore)} chunks!")
            return

        # Get all chunks for this repo from MySQL
        chunks = db.query(CodeChunk).join(RepoFile).filter(
            RepoFile.repo_id == repo_id
        ).all()

        print(f"📁 Embedding {len(chunks)} chunks...")

        if len(chunks) == 0:
            print("❌ No chunks found! Run chunker.py first.")
            return

        # Process in batches of 100
        batch_size = 100
        total_embedded = 0

        for i in range(0, len(chunks), batch_size):
            batch = chunks[i:i + batch_size]

            ids       = [f"chunk_{c.id}" for c in batch]
            documents = [Document(
                page_content = c.content,
                metadata     = {
                    "file_path"  : c.file.path,
                    "file_id"    : c.file_id,
                    "chunk_index": c.chunk_index,
                    "extension"  : c.file.extension or ""
                }
            ) for c in batch]

            # Embed batch + store in ChromaDB (LangChain does both steps)
            vectorstore.add_documents(documents, ids=ids)

            total_embedded += len(batch)

            if total_embedded % 500 == 0:
                print(f"   ⚙️  Embedded {total_embedded}/{len(chunks)} chunks...")

        print(f"\n Embedding complete!")
        print(f"   Total chunks embedded: {total_embedded}")
        print(f"   ChromaDB collection: {collection_name}")
        print(f"   Collection size: {count_vectors(vectorstore)} vectors")

    finally:
        db.close()


def search_code(repo_id: int, query: str, top_k: int = 5) -> list:
    """
    Search for relevant code chunks using semantic similarity.
    This is what makes RAG work!
    """
    # Get this repo's vector store
    vectorstore = get_vectorstore(repo_id)

    # Embed the query + search ChromaDB for similar chunks (LangChain does both)
    # Returns (Document, distance) pairs -- cosine distance, lower = closer
    results = vectorstore.similarity_search_with_score(query, k=top_k)

    # Format results
    formatted = []
    for doc, distance in results:
        formatted.append({
            "content"    : doc.page_content,
            "file_path"  : doc.metadata["file_path"],
            "similarity" : round(1 - distance, 3),
            "chunk_index": doc.metadata["chunk_index"]
        })

    return formatted


# ─── TEST ─────────────────────────────────────────────────

if __name__ == "__main__":
    REPO_ID = 2

    # Step 1 — Embed everything
    print("=" * 50)
    print(" Starting embedding pipeline")
    print("=" * 50)
    embed_repo(REPO_ID)

    # Step 2 — Test search
    print("\n" + "=" * 50)
    print(" Testing semantic search")
    print("=" * 50)

    test_queries = [
        "user authentication and login",
        "database connection and queries",
        "error handling and exceptions",
        "API route definitions"
    ]

    for query in test_queries:
        print(f"\n Query: '{query}'")
        results = search_code(REPO_ID, query, top_k=2)
        for r in results:
            print(f"    {r['file_path']} (similarity: {r['similarity']})")
            print(f"    {r['content'][:100].strip()}...")