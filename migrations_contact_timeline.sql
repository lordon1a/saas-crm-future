-- ============================================================================
-- Contact Timeline Tables Migration
-- Enterprise Grade: Notes & Activity Logs for Contact Detail Page
-- ============================================================================

-- Contact Notes Table
CREATE TABLE IF NOT EXISTS contact_notes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    workspace_id INTEGER NOT NULL,
    contact_id INTEGER NOT NULL,
    user_id INTEGER NOT NULL,
    content TEXT NOT NULL,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (workspace_id) REFERENCES workspaces(id) ON DELETE CASCADE,
    FOREIGN KEY (contact_id) REFERENCES contacts(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE CASCADE
);

CREATE INDEX IF NOT EXISTS idx_contact_notes_workspace ON contact_notes(workspace_id);
CREATE INDEX IF NOT EXISTS idx_contact_notes_contact ON contact_notes(contact_id);
CREATE INDEX IF NOT EXISTS idx_contact_notes_user ON contact_notes(user_id);
CREATE INDEX IF NOT EXISTS idx_contact_notes_created ON contact_notes(created_at);

-- Contact Activity Logs Table
CREATE TABLE IF NOT EXISTS contact_activity_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    workspace_id INTEGER NOT NULL,
    contact_id INTEGER NOT NULL,
    action_type VARCHAR(50) NOT NULL,
    description TEXT NOT NULL,
    metadata_json TEXT,
    user_id INTEGER,
    created_at TIMESTAMP NOT NULL DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (workspace_id) REFERENCES workspaces(id) ON DELETE CASCADE,
    FOREIGN KEY (contact_id) REFERENCES contacts(id) ON DELETE CASCADE,
    FOREIGN KEY (user_id) REFERENCES users(id) ON DELETE SET NULL
);

CREATE INDEX IF NOT EXISTS idx_contact_activity_workspace ON contact_activity_logs(workspace_id);
CREATE INDEX IF NOT EXISTS idx_contact_activity_contact ON contact_activity_logs(contact_id);
CREATE INDEX IF NOT EXISTS idx_contact_activity_type ON contact_activity_logs(action_type);
CREATE INDEX IF NOT EXISTS idx_contact_activity_user ON contact_activity_logs(user_id);
CREATE INDEX IF NOT EXISTS idx_contact_activity_created ON contact_activity_logs(created_at);

-- Insert sample activity log for existing contacts
INSERT INTO contact_activity_logs (workspace_id, contact_id, action_type, description, created_at)
SELECT 
    c.workspace_id,
    c.id,
    'contact_created',
    'Oluşturulan kişi: ' || c.first_name || ' ' || COALESCE(c.last_name, ''),
    c.created_at
FROM contacts c
WHERE NOT EXISTS (
    SELECT 1 FROM contact_activity_logs cal 
    WHERE cal.contact_id = c.id AND cal.action_type = 'contact_created'
);
