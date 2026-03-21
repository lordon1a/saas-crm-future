import sqlite3

conn = sqlite3.connect('crm.db')
cur = conn.cursor()

cur.execute('SELECT id, search_query, search_type, results_count, created_at FROM search_logs ORDER BY id DESC LIMIT 10')

print('=== SON 10 ARAMA ===')
for r in cur.fetchall():
    print(f'ID: {r[0]}, Query: "{r[1]}", Type: {r[2]}, Results: {r[3]}, Date: {r[4]}')

conn.close()
