# backend/embedder.py

import chromadb
from sentence_transformers import SentenceTransformer
from database import SessionLocal, RepoFile, CodeChunk
import os

# ─── SETUP ────────────────────────────────────────────────

print(" Loading embedding model (first time downloads ~90MB)...")
EMBEDDING_MODEL = SentenceTransformer("all-MiniLM-L6-v2")
print(" Model ready!")

CHROMA_PATH = os.path.join(os.path.dirname(__file__), "..", "chroma_db")
chroma_client = chromadb.PersistentClient(path=CHROMA_PATH)


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
        # Get ChromaDB collection
        collection_name = f"repo_{repo_id}"
        collection = chroma_client.get_or_create_collection(
            name=collection_name,
            metadata={"hnsw:space": "cosine"}
        )

        # Check if already embedded
        if collection.count() > 0:
            print(f"✅ Already embedded {collection.count()} chunks!")
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

            texts     = [c.content for c in batch]
            ids       = [f"chunk_{c.id}" for c in batch]
            metadatas = [{
                "file_path"  : c.file.path,
                "file_id"    : c.file_id,
                "chunk_index": c.chunk_index,
                "extension"  : c.file.extension or ""
            } for c in batch]

            # Embed batch
            embeddings = EMBEDDING_MODEL.encode(
                texts,
                normalize_embeddings=True,
                show_progress_bar=False
            ).tolist()

            # Store in ChromaDB
            collection.add(
                ids=ids,
                embeddings=embeddings,
                documents=texts,
                metadatas=metadatas
            )

            total_embedded += len(batch)

            if total_embedded % 500 == 0:
                print(f"   ⚙️  Embedded {total_embedded}/{len(chunks)} chunks...")

        print(f"\n Embedding complete!")
        print(f"   Total chunks embedded: {total_embedded}")
        print(f"   ChromaDB collection: {collection_name}")
        print(f"   Collection size: {collection.count()} vectors")

    finally:
        db.close()


def search_code(repo_id: int, query: str, top_k: int = 5) -> list:
    """
    Search for relevant code chunks using semantic similarity.
    This is what makes RAG work!
    """
    # Get collection
    collection_name = f"repo_{repo_id}"
    collection = chroma_client.get_or_create_collection(
        name=collection_name,
        metadata={"hnsw:space": "cosine"}
    )

    # Embed the search query
    query_embedding = EMBEDDING_MODEL.encode(
        query, normalize_embeddings=True
    ).tolist()

    # Search ChromaDB for similar chunks
    results = collection.query(
        query_embeddings=[query_embedding],
        n_results=top_k,
        include=["documents", "metadatas", "distances"]
    )

    # Format results
    formatted = []
    for j in range(len(results["documents"][0])):
        formatted.append({
            "content"    : results["documents"][0][j],
            "file_path"  : results["metadatas"][0][j]["file_path"],
            "similarity" : round(1 - results["distances"][0][j], 3),
            "chunk_index": results["metadatas"][0][j]["chunk_index"]
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