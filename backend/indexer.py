# backend/indexer.py
# This is the main pipeline for Week 2:
# GitHub repo → fetch files → save to MySQL

from github_loader import fetch_repo_files, get_repo_metadata
from database import SessionLocal, save_repo, save_files, mark_repo_indexed

def index_repo(repo_url: str):
    """
    Full pipeline:
    1. Get repo metadata from GitHub
    2. Save repo to MySQL
    3. Fetch all code files
    4. Save all files to MySQL
    5. Mark repo as indexed
    """
    print("=" * 50)
    print(f" Starting indexing: {repo_url}")
    print("=" * 50)

    db = SessionLocal()

    try:
        # Step 1 — Get repo metadata
        print("\n📡 Step 1: Fetching repo metadata...")
        metadata = get_repo_metadata(repo_url)
        print(f"   Name: {metadata['name']}")
        print(f"   Stars: {metadata['stars']}")
        print(f"   Language: {metadata['language']}")

        # Step 2 — Save repo to MySQL
        print("\n Step 2: Saving repo to MySQL...")
        repo = save_repo(db, metadata)

        # Step 3 — Fetch all code files from GitHub
        print("\n Step 3: Fetching all code files from GitHub...")
        files = fetch_repo_files(repo_url)

        # Step 4 — Save files to MySQL
        print("\n Step 4: Saving files to MySQL...")
        save_files(db, repo.id, files)

        # Step 5 — Mark as indexed
        mark_repo_indexed(db, repo.id)

        print("\n" + "=" * 50)
        print(f" DONE! Repo fully indexed.")
        print(f"   Repo ID: {repo.id}")
        print(f"   Files saved: {len(files)}")
        print("=" * 50)

        return repo.id

    except Exception as e:
        print(f"\n Error during indexing: {e}")
        db.rollback()
        raise e

    finally:
        db.close()


if __name__ == "__main__":
    # Test with a small repo
    index_repo("https://github.com/tiangolo/fastapi")