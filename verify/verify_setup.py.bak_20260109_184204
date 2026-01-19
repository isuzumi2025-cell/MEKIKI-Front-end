import sys
import os
import asyncio

# Add project root to path
sys.path.append(os.getcwd())

from app.core.engine import FastEngine
from app.core.parser import URLParser
from app.db.database import engine as db_engine, Base
from app.db import models

async def verify():
    print("🔍 System Check...")
    
    # 1. DB Check
    try:
        print("  - Checking Database...")
        Base.metadata.create_all(bind=db_engine)
        print("  ✅ Database initialized")
    except Exception as e:
        print(f"  ❌ Database Error: {e}")
        return

    # 2. URL Parse Check
    url = "https://example.com/foo/?utm_source=test#frag"
    normalized = URLParser.normalize_url(url)
    expected = "https://example.com/foo/"
    if normalized == expected:
        print(f"  ✅ URL Normalizer: {normalized}")
    else:
        print(f"  ❌ URL Normalizer: Expected {expected}, got {normalized}")

    # 3. Engine Check (Fast)
    print("  - Checking FastEngine...")
    engine = FastEngine()
    data = await engine.fetch("https://example.com")
    if data["status"] == 200:
        print(f"  ✅ FastEngine Fetch: {data['title']}")
    else:
        print(f"  ⚠️ FastEngine Warning: Status {data['status']} - {data.get('error')}")

    print("\n✅ Verification Complete. Ready to run `uvicorn app.main:app --reload`")

if __name__ == "__main__":
    if os.name == 'nt':
        asyncio.set_event_loop_policy(asyncio.WindowsSelectorEventLoopPolicy())
    asyncio.run(verify())
