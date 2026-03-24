"""
Add AI scoring and insight fields to deals, contacts, and conversations tables.
- deals: ai_score, ai_score_label, ai_insight, ai_scored_at
- contacts: ai_insight, ai_scored_at
- conversations: ai_summary, ai_summary_at, ai_sentiment, ai_sentiment_score
"""
import logging

logger = logging.getLogger(__name__)


def _col_exists(cur, table, column):
    cur.execute("""
        SELECT 1 FROM information_schema.columns
        WHERE table_name=%s AND column_name=%s
    """, (table, column))
    return cur.fetchone() is not None


def upgrade(conn, cur):
    changed = False

    # --- deals table ---
    for col, ddl in [
        ('ai_score',       'INTEGER DEFAULT NULL'),
        ('ai_score_label', 'VARCHAR(20) DEFAULT NULL'),
        ('ai_insight',     'TEXT DEFAULT NULL'),
        ('ai_scored_at',   'TIMESTAMP DEFAULT NULL'),
    ]:
        if not _col_exists(cur, 'deals', col):
            cur.execute(f'ALTER TABLE deals ADD COLUMN {col} {ddl}')
            logger.info(f"Added deals.{col}")
            changed = True

    # --- contacts table ---
    for col, ddl in [
        ('ai_insight',   'TEXT DEFAULT NULL'),
        ('ai_scored_at', 'TIMESTAMP DEFAULT NULL'),
    ]:
        if not _col_exists(cur, 'contacts', col):
            cur.execute(f'ALTER TABLE contacts ADD COLUMN {col} {ddl}')
            logger.info(f"Added contacts.{col}")
            changed = True

    # --- conversations table ---
    for col, ddl in [
        ('ai_summary',         'TEXT DEFAULT NULL'),
        ('ai_summary_at',      'TIMESTAMP DEFAULT NULL'),
        ('ai_sentiment',       'VARCHAR(20) DEFAULT NULL'),
        ('ai_sentiment_score', 'REAL DEFAULT NULL'),
    ]:
        if not _col_exists(cur, 'conversations', col):
            cur.execute(f'ALTER TABLE conversations ADD COLUMN {col} {ddl}')
            logger.info(f"Added conversations.{col}")
            changed = True

    if changed:
        conn.commit()
        logger.info("AI scoring fields migration completed")
    else:
        logger.info("AI scoring fields already exist, skipping")
