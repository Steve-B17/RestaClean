from core.database import engine
from core.redis_client import redis_client, test_connection
from config import settings

print("Testing Postgres...")
try:
    with engine.connect() as conn:
        result = conn.execute("SELECT 1")
        print("✅ Postgres OK:", result.scalar())
except Exception as e:
    print("❌ Postgres FAIL:", e)

print("\nTesting Redis...")
if test_connection():
    print("✅ Redis OK")
else:
    print("❌ Redis FAIL")

print("\nSettings check:")
print("DB URL:", settings.database_url)
print("Redis URL:", settings.redis_url)
