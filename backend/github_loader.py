from github import Github
from dotenv import load_dotenv
import os

load_dotenv()


def get_repo_metadata(repo_url: str) -> dict:
    """
    Fetches repo metadata — name, description, stars, language.
    """
    token = os.getenv("GITHUB_TOKEN")
    g = Github(token)

    repo_name = repo_url.replace("https://github.com/", "").strip("/")
    repo = g.get_repo(repo_name)

    return {
        "url":         repo_url,
        "name":        repo.full_name,
        "description": repo.description or "",
        "stars":       repo.stargazers_count,
        "language":    repo.language or "Unknown"
    }


def fetch_repo_files(repo_url: str) -> list:
    token = os.getenv("GITHUB_TOKEN")
    g = Github(token)

    repo_name = repo_url.replace("https://github.com/", "").strip("/")
    print(f"🔍 Connecting to: {repo_name}")

    repo = g.get_repo(repo_name)
    print(f" Found: {repo.full_name}")
    print(f"    Stars: {repo.stargazers_count}")
    print(f"    {repo.description}")

    CODE_EXTENSIONS = {
        ".py", ".js", ".ts", ".java",
        ".cpp", ".go", ".html", ".css",
        ".md", ".yaml", ".json"
    }

    files = []
    tree = repo.get_git_tree("HEAD", recursive=True).tree
    print(f"\n Scanning {len(tree)} items...")

    for item in tree:
        if item.type != "blob":
            continue
        ext = os.path.splitext(item.path)[1].lower()
        if ext not in CODE_EXTENSIONS:
            continue
        if item.size > 500_000:
            continue
        try:
            content = repo.get_contents(item.path)
            decoded = content.decoded_content.decode("utf-8", errors="ignore")
            files.append({
                "path":      item.path,
                "content":   decoded,
                "size":      item.size,
                "extension": ext
            })
        except Exception as e:
            continue

    print(f" Found {len(files)} code files")
    return files


if __name__ == "__main__":
    files = fetch_repo_files("https://github.com/tiangolo/fastapi")

    print("\n First 5 files:")
    for f in files[:5]:
        print(f"   {f['path']} ({f['size']} bytes)")