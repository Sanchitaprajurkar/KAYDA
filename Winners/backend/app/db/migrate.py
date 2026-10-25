import sys
from pathlib import Path

# Add backend directory to path
backend_dir = Path(__file__).resolve().parent.parent.parent
sys.path.insert(0, str(backend_dir))

from app.db.schema import init_db

if __name__ == "__main__":
    print("[Neon Migration] Executing schema initialization...")
    success = init_db()
    if success:
        print("[Neon Migration] All tables verified/created in Neon PostgreSQL successfully!")
        sys.exit(0)
    else:
        print("[Neon Migration] Schema migration failed!")
        sys.exit(1)
