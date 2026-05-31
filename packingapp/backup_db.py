import os
import json
import psycopg2
from psycopg2.extras import RealDictCursor
from datetime import datetime
from urllib.parse import urlparse

DATABASE_URL = os.environ.get('DATABASE_URL')

def get_db():
    result = urlparse(DATABASE_URL)
    return psycopg2.connect(
        host=result.hostname,
        port=result.port,
        database=result.path[1:],
        user=result.username,
        password=result.password,
        sslmode='require'
    )

def backup():
    conn = get_db()
    cur = conn.cursor(cursor_factory=RealDictCursor)

    # Discover all user tables dynamically
    cur.execute("""
        SELECT table_name
        FROM information_schema.tables
        WHERE table_schema = 'public'
        AND table_type = 'BASE TABLE'
        ORDER BY table_name
    """)
    tables = [row['table_name'] for row in cur.fetchall()]
    print(f"Found tables: {tables}")

    backup_data = {
        'timestamp': datetime.utcnow().isoformat(),
        'tables': {}
    }

    for table in tables:
        cur.execute(f'SELECT * FROM "{table}"')
        rows = [dict(r) for r in cur.fetchall()]
        backup_data['tables'][table] = rows
        print(f"  {table}: {len(rows)} rows")

    cur.close()
    conn.close()

    os.makedirs('backups', exist_ok=True)
    filename = f"backups/backup_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}.json"
    with open(filename, 'w') as f:
        json.dump(backup_data, f, indent=2, default=str)

    print(f"Backup saved to {filename}")

if __name__ == '__main__':
    backup()
