# backend/query_test.py
# Practice querying the database — this is pure SQL learning!

from database import SessionLocal, engine
from database import Repo, RepoFile
from sqlalchemy import text

db = SessionLocal()

print("=" * 50)
print(" Database Query Tests")
print("=" * 50)

# ── Query 1: All repos ──────────────────────────────
repos = db.query(Repo).all()
print(f"\n📦 Total repos indexed: {len(repos)}")
for r in repos:
    print(f"   [{r.id}] {r.name} — ⭐{r.stars} — indexed={r.is_indexed}")

# ── Query 2: File count per repo ────────────────────
print(f"\n Files per repo:")
for r in repos:
    file_count = db.query(RepoFile).filter(
        RepoFile.repo_id == r.id
    ).count()
    print(f"   {r.name}: {file_count} files")

# ── Query 3: Files by extension ─────────────────────
print(f"\n Files by extension (raw SQL):")
with engine.connect() as conn:
    result = conn.execute(text("""
        SELECT extension, COUNT(*) as count
        FROM files
        GROUP BY extension
        ORDER BY count DESC
        LIMIT 10
    """))
    for row in result:
        print(f"   {row[0]}: {row[1]} files")

# ── Query 4: Biggest files ───────────────────────────
print(f"\n Top 5 biggest files:")
big_files = db.query(RepoFile).order_by(
    RepoFile.size.desc()
).limit(5).all()
for f in big_files:
    print(f"   {f.path} ({f.size} bytes)")

# ── Query 5: Raw SQL search ──────────────────────────
print(f"\n🔍 Python files containing 'auth' in path:")
with engine.connect() as conn:
    result = conn.execute(text("""
        SELECT path, size
        FROM files
        WHERE path LIKE '%auth%'
        AND extension = '.py'
    """))
    rows = result.fetchall()
    if rows:
        for row in rows:
            print(f"   {row[0]} ({row[1]} bytes)")
    else:
        print("   None found")

db.close()
print("\n All queries done!")