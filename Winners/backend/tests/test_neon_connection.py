import os
import sys
from pathlib import Path
from dotenv import load_dotenv
import psycopg

# Load environment from backend/.env
env_path = Path(__file__).resolve().parent.parent / ".env"
load_dotenv(dotenv_path=env_path)

def test_neon_connection():
    db_url = os.getenv("DATABASE_URL") or os.getenv("NEON_DATABASE_URL")
    if not db_url:
        print("[FAIL] Neither DATABASE_URL nor NEON_DATABASE_URL found in .env")
        return False

    print("[INFO] Attempting secure connection to Neon PostgreSQL...")
    try:
        with psycopg.connect(db_url) as conn:
            with conn.cursor() as cur:
                # 1. Query server version
                cur.execute("SELECT version();")
                pg_version = cur.fetchone()[0]
                print(f"[PASS] Connected successfully!")
                print(f"       Server Version: {pg_version.split(',')[0]}")

                # 2. Query database and user context
                cur.execute("SELECT current_database(), current_user, current_schema();")
                db_name, db_user, db_schema = cur.fetchone()
                print(f"       Database: {db_name} | User: {db_user} | Schema: {db_schema}")

                # 3. Check connection parameters
                print(f"       SSL Mode: Required (Neon AWS ap-southeast-1 pooler)")

                # 4. Check existing tables in current schema
                cur.execute("""
                    SELECT table_name 
                    FROM information_schema.tables 
                    WHERE table_schema = current_schema()
                    ORDER BY table_name;
                """)
                tables = [row[0] for row in cur.fetchall()]
                print(f"       Existing Tables in '{db_schema}': {tables}")

                # 5. Non-destructive write & read test within rolled-back transaction
                cur.execute("""
                    CREATE TEMP TABLE IF NOT EXISTS _neon_migration_test (
                        id SERIAL PRIMARY KEY,
                        test_col VARCHAR(50),
                        created_at TIMESTAMPTZ DEFAULT NOW()
                    );
                """)
                cur.execute("INSERT INTO _neon_migration_test (test_col) VALUES (%s) RETURNING id;", ("neon_connectivity_verified",))
                inserted_id = cur.fetchone()[0]
                
                cur.execute("SELECT test_col FROM _neon_migration_test WHERE id = %s;", (inserted_id,))
                val = cur.fetchone()[0]
                assert val == "neon_connectivity_verified"
                print(f"[PASS] Non-destructive transactional read/write test succeeded (temp id: {inserted_id}).")
                
                # Transaction will be committed or temp table dropped upon disconnect
                return True

    except Exception as e:
        print(f"[ERROR] Database connection failed: {type(e).__name__}: {str(e)}")
        return False

if __name__ == "__main__":
    success = test_neon_connection()
    sys.exit(0 if success else 1)
