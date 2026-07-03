# backend/create_tables.py
# Run this ONCE to create all tables in MySQL

from database import create_tables, engine
from sqlalchemy import text

# Create all tables
create_tables()

# Verify they were created
with engine.connect() as conn:
    result = conn.execute(text("SHOW TABLES"))
    tables = result.fetchall()
    print("\n Tables in github_intel database:")
    for table in tables:
        print(f"   - {table[0]}")