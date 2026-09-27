# backend/rag.py
# This is the brain of the entire project.
# It connects ChromaDB search → LLM → final answer
# Built with LangChain: ChatPromptTemplate + ChatGroq + StrOutputParser

from embedder import search_code
from database import SessionLocal, Repo
from dotenv import load_dotenv
import os

load_dotenv()

# ─── SETUP ────────────────────────────────────────────────

from langchain_groq import ChatGroq
from langchain_core.prompts import ChatPromptTemplate
from langchain_core.output_parsers import StrOutputParser

llm = ChatGroq(
    model="qwen/qwen3.8-27b",     # llama-3.1-8b-instant was retired by Groq
    temperature=0,        # 0 = deterministic, no hallucination
    max_tokens=1000,      # Limit response length
    api_key=os.getenv("GROQ_API_KEY")
)

# ─── PROMPT TEMPLATE + CHAIN ──────────────────────────────

prompt_template = ChatPromptTemplate.from_messages([
    ("system", "You are a helpful code assistant. Answer questions about codebases clearly and concisely. Always cite the file names where you found the answer."),
    ("human", """You are an expert code assistant helping developers understand a GitHub codebase.

You have been given relevant code chunks retrieved from the repository.
Use ONLY the provided code context to answer the question.
Always mention which file(s) the answer comes from.
If the answer is not in the provided context, say "I couldn't find that in the indexed code."

CODE CONTEXT:
{context}

QUESTION: {question}

ANSWER:"""),
])

# LangChain chain: fill the prompt -> call the LLM -> return a plain string
rag_chain = prompt_template | llm | StrOutputParser()

# ─── PROMPT BUILDER ───────────────────────────────────────

def build_prompt(question: str, code_chunks: list) -> dict:
    """
    Builds the inputs for the prompt template.

    The prompt has two parts:
    1. The retrieved code context (from ChromaDB)
    2. The user's question

    This is the core of RAG — grounding the LLM in real code.
    """
    # Format each chunk with its file path
    context_parts = []
    for i, chunk in enumerate(code_chunks):
        context_parts.append(
            f"--- File: {chunk['file_path']} "
            f"(similarity: {chunk['similarity']}) ---\n"
            f"{chunk['content']}\n"
        )

    context = "\n".join(context_parts)

    # The template above fills these two variables into the full prompt
    return {"context": context, "question": question}


# ─── MAIN RAG FUNCTION ────────────────────────────────────

def ask_codebase(repo_id: int, question: str, top_k: int = 5) -> dict:
    """
    Full RAG pipeline:
    1. Search for relevant code chunks
    2. Build prompt with context
    3. Send to LLM
    4. Return answer + sources

    This is what gets called when a user asks a question.
    """
    print(f"\n Searching codebase for: '{question}'")

    # Step 1 — Retrieve relevant chunks from ChromaDB
    chunks = search_code(repo_id, question, top_k=top_k)

    if not chunks:
        return {
            "answer": "No relevant code found. Make sure the repo is indexed.",
            "sources": [],
            "question": question
        }

    print(f"   Found {len(chunks)} relevant chunks")
    for c in chunks:
        print(f"    {c['file_path']} (similarity: {c['similarity']})")

    # Step 2 — Build the prompt inputs (context + question)
    prompt_inputs = build_prompt(question, chunks)

    # Step 3 — Send to LLM through the LangChain chain
    print(f"\n Sending to {llm.model_name}...")

    # Step 4 — Extract answer (StrOutputParser already returns a plain string)
    answer = rag_chain.invoke(prompt_inputs)

    # Step 5 — Format sources
    sources = list({c["file_path"] for c in chunks})  # Unique file paths

    return {
        "question": question,
        "answer"  : answer,
        "sources" : sources,
        "chunks_used": len(chunks)
    }


# ─── TEST ─────────────────────────────────────────────────

if __name__ == "__main__":
    REPO_ID = 2  # Use whatever repo_id your fastapi repo has

    print("=" * 60)
    print(" GitHub Codebase Intelligence — RAG Pipeline Test")
    print("=" * 60)

    # Test questions
    questions = [
        "Where is authentication implemented?",
        "How does FastAPI handle errors and exceptions?",
        "How do I define an API route in FastAPI?",
        "How does FastAPI connect to a SQL database?"
    ]

    for question in questions:
        print(f"\n{'='*60}")
        result = ask_codebase(REPO_ID, question)

        print(f"\n QUESTION: {result['question']}")
        print(f"\n ANSWER:\n{result['answer']}")
        print(f"\n SOURCES:")
        for source in result['sources']:
            print(f"   - {source}")