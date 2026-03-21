"""
Add search_logs table to local SQLite database
"""
import sqlite3

conn = sqlite3.connect('crm.db')
cur = conn.cursor()

# Check if search_logs table exists
cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='search_logs'")
if not cur.fetchone():
    print('Creating search_logs table...')
    cur.execute('''
        CREATE TABLE search_logs (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            workspace_id INTEGER NOT NULL,
            user_id INTEGER NOT NULL,
            search_query VARCHAR(500) NOT NULL,
            search_type VARCHAR(50) NOT NULL,
            entity_type VARCHAR(50),
            results_count INTEGER DEFAULT 0 NOT NULL,
            search_duration_ms INTEGER,
            filters_applied TEXT,
            clicked_result_id INTEGER,
            clicked_result_type VARCHAR(50),
            user_agent VARCHAR(500),
            ip_address VARCHAR(45),
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP NOT NULL,
            FOREIGN KEY (workspace_id) REFERENCES workspaces(id),
            FOREIGN KEY (user_id) REFERENCES users(id)
        )
    ''')
    
    # Create indexes
    cur.execute('CREATE INDEX idx_search_logs_workspace_id ON search_logs(workspace_id)')
    cur.execute('CREATE INDEX idx_search_logs_user_id ON search_logs(user_id)')
    cur.execute('CREATE INDEX idx_search_logs_search_type ON search_logs(search_type)')
    cur.execute('CREATE INDEX idx_search_logs_created_at ON search_logs(created_at)')
    cur.execute('CREATE INDEX idx_search_logs_workspace_user ON search_logs(workspace_id, user_id)')
    
    conn.commit()
    print('✓ search_logs table created successfully')
else:
    print('✓ search_logs table already exists')

conn.close()
