# frontend/app.py
# Streamlit UI for GitHub Codebase Intelligence Platform

import streamlit as st
import requests
import time

# ─── CONFIG ───────────────────────────────────────────────
import os

API_URL = os.getenv("API_URL", "http://localhost:8000")

st.set_page_config(
    page_title="GitHub Codebase Intelligence",
    page_icon="",
    layout="wide"
)

# ─── CUSTOM STYLES ────────────────────────────────────────

st.markdown("""
<style>
    .main-header {
        font-size: 2.5rem;
        font-weight: 700;
        color: #00BFFF;
        margin-bottom: 0;
    }
    .sub-header {
        font-size: 1rem;
        color: #888;
        margin-bottom: 2rem;
    }
    .source-badge {
        background: #1e1e2e;
        border: 1px solid #333;
        border-radius: 6px;
        padding: 4px 10px;
        font-size: 0.75rem;
        font-family: monospace;
        color: #00BFFF;
        margin: 2px;
        display: inline-block;
    }
    .stat-box {
        background: #1e1e2e;
        border-radius: 10px;
        padding: 1rem;
        text-align: center;
    }
</style>
""", unsafe_allow_html=True)


# ─── SESSION STATE ────────────────────────────────────────
# Session state persists data between Streamlit reruns

if "messages"     not in st.session_state:
    st.session_state.messages = []      # Chat history

if "current_repo" not in st.session_state:
    st.session_state.current_repo = None  # Currently selected repo

if "repos"        not in st.session_state:
    st.session_state.repos = []           # All indexed repos


# ─── HELPER FUNCTIONS ─────────────────────────────────────

def fetch_repos():
    """Get all indexed repos from the API."""
    try:
        response = requests.get(f"{API_URL}/repos", timeout=5)
        if response.status_code == 200:
            return response.json().get("repos", [])
    except:
        pass
    return []


def index_new_repo(repo_url: str):
    """Send index request to API and show progress."""
    try:
        # Start indexing
        response = requests.post(
            f"{API_URL}/repos/index",
            json={"repo_url": repo_url},
            timeout=30
        )

        if response.status_code != 200:
            st.error(f"Error: {response.json().get('detail', 'Unknown error')}")
            return None

        data = response.json()
        repo_id = data["repo_id"]

        # If already indexed, just return it
        if data["status"] == "already_indexed":
            st.success(f" Repo already indexed: {data['name']}")
            return repo_id

        # Poll for progress
        st.info(f" Indexing started for **{data['name']}** — this takes 2-5 minutes for large repos...")

        progress_bar = st.progress(0)
        status_text  = st.empty()

        while True:
            time.sleep(3)
            status_resp = requests.get(
                f"{API_URL}/repos/{repo_id}/status",
                timeout=5
            )
            status_data = status_resp.json()
            progress    = status_data.get("progress", 0)
            status      = status_data.get("status", "")

            progress_bar.progress(progress / 100)
            status_text.text(
                f"Status: {status} | "
                f"Files: {status_data.get('files_count', 0)} | "
                f"Chunks: {status_data.get('chunks_count', 0)}"
            )

            if status in ["complete", "failed"]:
                break

        if status == "complete":
            progress_bar.progress(1.0)
            st.success(f" Repo indexed successfully!")
            return repo_id
        else:
            st.error(" Indexing failed. Check terminal for errors.")
            return None

    except requests.exceptions.ConnectionError:
        st.error(" Cannot connect to API. Make sure FastAPI server is running!")
        return None
    except Exception as e:
        st.error(f" Error: {str(e)}")
        return None


def ask_question(repo_id: int, question: str) -> dict:
    """Send question to RAG API and get answer."""
    try:
        response = requests.post(
            f"{API_URL}/repos/{repo_id}/query",
            json={"question": question, "top_k": 5},
            timeout=60
        )
        if response.status_code == 200:
            return response.json()
        else:
            return {
                "answer" : f"Error: {response.json().get('detail', 'Unknown error')}",
                "sources": []
            }
    except requests.exceptions.ConnectionError:
        return {
            "answer" : " Cannot connect to API. Make sure FastAPI server is running!",
            "sources": []
        }
    except Exception as e:
        return {"answer": f" Error: {str(e)}", "sources": []}


# ─── SIDEBAR ──────────────────────────────────────────────

with st.sidebar:
    st.markdown("##  Codebase Intelligence")
    st.markdown("---")

    # Index new repo section
    st.markdown("###  Index a Repo")
    repo_url = st.text_input(
        "GitHub URL",
        placeholder="https://github.com/user/repo",
        label_visibility="collapsed"
    )

    if st.button("🚀 Index Repo", use_container_width=True):
        if repo_url:
            with st.spinner("Connecting to GitHub..."):
                repo_id = index_new_repo(repo_url)
                if repo_id:
                    st.session_state.repos = fetch_repos()
                    # Auto-select the new repo
                    for r in st.session_state.repos:
                        if r["id"] == repo_id:
                            st.session_state.current_repo = r
                            st.session_state.messages = []
                            break
                    st.rerun()
        else:
            st.warning("Please enter a GitHub URL")

    st.markdown("---")

    # List indexed repos
    st.markdown("###  Indexed Repos")

    if not st.session_state.repos:
        st.session_state.repos = fetch_repos()

    if st.session_state.repos:
        for repo in st.session_state.repos:
            is_selected = (
                st.session_state.current_repo and
                st.session_state.current_repo["id"] == repo["id"]
            )
            btn_label = f"{' ' if is_selected else ''}{repo['name'].split('/')[-1]}"

            if st.button(btn_label, key=f"repo_{repo['id']}",
                         use_container_width=True):
                st.session_state.current_repo = repo
                st.session_state.messages = []
                st.rerun()
    else:
        st.info("No repos indexed yet.\nPaste a GitHub URL above!")

    st.markdown("---")

    # Refresh button
    if st.button(" Refresh", use_container_width=True):
        st.session_state.repos = fetch_repos()
        st.rerun()


# ─── MAIN CONTENT ─────────────────────────────────────────

if not st.session_state.current_repo:
    # Welcome screen
    st.markdown('<p class="main-header"> GitHub Codebase Intelligence</p>',
                unsafe_allow_html=True)
    st.markdown('<p class="sub-header">Ask natural language questions about any GitHub repository</p>',
                unsafe_allow_html=True)

    st.markdown("---")

    col1, col2, col3 = st.columns(3)
    with col1:
        st.markdown("###  Semantic Search")
        st.write("Finds relevant code by **meaning**, not just keywords.")
    with col2:
        st.markdown("###  AI Answers")
        st.write("Get plain English explanations with **file citations**.")
    with col3:
        st.markdown("###  Any Repo")
        st.write("Works on **any public GitHub repo** in minutes.")

    st.markdown("---")
    st.markdown("###  Example Questions You Can Ask")

    examples = [
        "Where is authentication implemented?",
        "How does error handling work?",
        "How do I define an API route?",
        "How does the database connection work?",
        "What are the main classes in this project?",
        "How is middleware configured?"
    ]

    cols = st.columns(2)
    for i, ex in enumerate(examples):
        cols[i % 2].markdown(f"- *{ex}*")

    st.markdown("---")
    st.info(" Paste a GitHub URL in the sidebar to get started!")

else:
    # Chat interface
    repo = st.session_state.current_repo

    # Repo header
    col1, col2, col3, col4 = st.columns([3, 1, 1, 1])
    with col1:
        st.markdown(f"##  {repo['name']}")
    with col2:
        st.metric("Files", repo.get("files_count", "—"))
    with col3:
        st.metric("Stars", f" {repo.get('stars', 0):,}")
    with col4:
        st.metric("Status", " Ready" if repo.get("is_indexed") else "⏳ Indexing")

    st.markdown("---")

    # Suggested questions
    st.markdown("** Try asking:**")
    suggested = [
        "Where is authentication implemented?",
        "How does error handling work?",
        "How do I define an API route?",
        "Explain the main application structure"
    ]

    cols = st.columns(4)
    for i, suggestion in enumerate(suggested):
        if cols[i].button(suggestion, key=f"sug_{i}"):
            st.session_state.messages.append({
                "role": "user",
                "content": suggestion
            })
            with st.spinner(" Thinking..."):
                result = ask_question(repo["id"], suggestion)
            st.session_state.messages.append({
                "role"   : "assistant",
                "content": result["answer"],
                "sources": result.get("sources", [])
            })
            st.rerun()

    st.markdown("---")

    # Chat history
    for message in st.session_state.messages:
        if message["role"] == "user":
            with st.chat_message("user"):
                st.write(message["content"])
        else:
            with st.chat_message("assistant"):
                st.write(message["content"])
                if message.get("sources"):
                    st.markdown("** Sources:**")
                    sources_html = " ".join([
                        f'<span class="source-badge">{s}</span>'
                        for s in message["sources"]
                    ])
                    st.markdown(sources_html, unsafe_allow_html=True)

    # Chat input
    if question := st.chat_input("Ask anything about this codebase..."):
        # Add user message
        st.session_state.messages.append({
            "role": "user",
            "content": question
        })

        # Get answer
        with st.chat_message("assistant"):
            with st.spinner(" Searching codebase and generating answer..."):
                result = ask_question(repo["id"], question)

            st.write(result["answer"])

            if result.get("sources"):
                st.markdown("** Sources:**")
                sources_html = " ".join([
                    f'<span class="source-badge">{s}</span>'
                    for s in result["sources"]
                ])
                st.markdown(sources_html, unsafe_allow_html=True)

        # Save to history
        st.session_state.messages.append({
            "role"   : "assistant",
            "content": result["answer"],
            "sources": result.get("sources", [])
        })

        st.rerun()