"""
Migration: Add pipeline week-3 features
Date: 2026-03-22
Description:
- Extends deals and deal_contacts with advanced CRM fields
- Creates CPQ and taxonomy tables (products, deal_line_items, quotes, quote_line_items, win_loss_reasons)
- Creates deal_merge_history table
"""

import os
import sys

from sqlalchemy import text

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))


def _add_column_if_missing(conn, inspector, table_name, column_name, ddl_sql):
    columns = [col['name'] for col in inspector.get_columns(table_name)]
    if column_name not in columns:
        conn.execute(text(ddl_sql))
        print(f"OK: Added {table_name}.{column_name}")
    else:
        print(f"OK: Column exists {table_name}.{column_name}")


def upgrade(db):
    print("Applying week-3 pipeline feature migration...")
    inspector = db.inspect(db.engine)

    with db.engine.connect() as conn:
        # ---------------------------------------------------------------------
        # deals table extensions
        # ---------------------------------------------------------------------
        _add_column_if_missing(conn, inspector, 'deals', 'revenue_type', "ALTER TABLE deals ADD COLUMN revenue_type VARCHAR(20) NOT NULL DEFAULT 'one_time'")
        _add_column_if_missing(conn, inspector, 'deals', 'mrr', "ALTER TABLE deals ADD COLUMN mrr NUMERIC(12,2) NOT NULL DEFAULT 0")
        _add_column_if_missing(conn, inspector, 'deals', 'arr', "ALTER TABLE deals ADD COLUMN arr NUMERIC(12,2) NOT NULL DEFAULT 0")
        _add_column_if_missing(conn, inspector, 'deals', 'renewal_date', "ALTER TABLE deals ADD COLUMN renewal_date DATE")
        _add_column_if_missing(conn, inspector, 'deals', 'churn_risk', "ALTER TABLE deals ADD COLUMN churn_risk VARCHAR(20) NOT NULL DEFAULT 'low'")
        _add_column_if_missing(conn, inspector, 'deals', 'next_step', "ALTER TABLE deals ADD COLUMN next_step VARCHAR(500)")
        _add_column_if_missing(conn, inspector, 'deals', 'next_step_due_at', "ALTER TABLE deals ADD COLUMN next_step_due_at DATETIME")
        _add_column_if_missing(conn, inspector, 'deals', 'last_activity_at', "ALTER TABLE deals ADD COLUMN last_activity_at DATETIME")
        _add_column_if_missing(conn, inspector, 'deals', 'forecast_category', "ALTER TABLE deals ADD COLUMN forecast_category VARCHAR(20) NOT NULL DEFAULT 'pipeline'")
        _add_column_if_missing(conn, inspector, 'deals', 'win_loss_reason_id', "ALTER TABLE deals ADD COLUMN win_loss_reason_id INTEGER")

        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_deals_revenue_type ON deals(revenue_type)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_deals_renewal_date ON deals(renewal_date)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_deals_churn_risk ON deals(churn_risk)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_deals_next_step_due_at ON deals(next_step_due_at)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_deals_last_activity_at ON deals(last_activity_at)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_deals_forecast_category ON deals(forecast_category)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_deals_win_loss_reason_id ON deals(win_loss_reason_id)"))

        # ---------------------------------------------------------------------
        # deal_contacts table extensions
        # ---------------------------------------------------------------------
        _add_column_if_missing(conn, inspector, 'deal_contacts', 'influence_score', "ALTER TABLE deal_contacts ADD COLUMN influence_score INTEGER NOT NULL DEFAULT 50")
        _add_column_if_missing(conn, inspector, 'deal_contacts', 'decision_weight', "ALTER TABLE deal_contacts ADD COLUMN decision_weight INTEGER NOT NULL DEFAULT 50")

        # ---------------------------------------------------------------------
        # taxonomy / CPQ tables
        # ---------------------------------------------------------------------
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS win_loss_reasons (
                id INTEGER PRIMARY KEY,
                workspace_id INTEGER NOT NULL,
                category VARCHAR(20) NOT NULL,
                code VARCHAR(100) NOT NULL,
                label VARCHAR(200) NOT NULL,
                is_active BOOLEAN NOT NULL DEFAULT 1,
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                CONSTRAINT uix_workspace_reason_code UNIQUE (workspace_id, category, code)
            )
        """))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_win_loss_reasons_workspace ON win_loss_reasons(workspace_id)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_win_loss_reasons_category ON win_loss_reasons(category)"))

        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS products (
                id INTEGER PRIMARY KEY,
                workspace_id INTEGER NOT NULL,
                sku VARCHAR(100),
                name VARCHAR(200) NOT NULL,
                description TEXT,
                currency VARCHAR(10) NOT NULL DEFAULT 'TRY',
                unit_price NUMERIC(12,2) NOT NULL DEFAULT 0,
                is_active BOOLEAN NOT NULL DEFAULT 1,
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME,
                CONSTRAINT uix_workspace_product_sku UNIQUE (workspace_id, sku)
            )
        """))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_products_workspace ON products(workspace_id)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_products_is_active ON products(is_active)"))

        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS deal_line_items (
                id INTEGER PRIMARY KEY,
                workspace_id INTEGER NOT NULL,
                deal_id INTEGER NOT NULL,
                product_id INTEGER,
                item_name VARCHAR(200) NOT NULL,
                quantity NUMERIC(12,2) NOT NULL DEFAULT 1,
                unit_price NUMERIC(12,2) NOT NULL DEFAULT 0,
                discount_pct NUMERIC(5,2) NOT NULL DEFAULT 0,
                tax_pct NUMERIC(5,2) NOT NULL DEFAULT 0,
                total_amount NUMERIC(12,2) NOT NULL DEFAULT 0,
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME
            )
        """))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_deal_line_items_workspace ON deal_line_items(workspace_id)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_deal_line_items_deal ON deal_line_items(deal_id)"))

        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS quotes (
                id INTEGER PRIMARY KEY,
                workspace_id INTEGER NOT NULL,
                deal_id INTEGER NOT NULL,
                quote_number VARCHAR(100) NOT NULL,
                status VARCHAR(20) NOT NULL DEFAULT 'draft',
                valid_until DATE,
                currency VARCHAR(10) NOT NULL DEFAULT 'TRY',
                subtotal NUMERIC(12,2) NOT NULL DEFAULT 0,
                discount_total NUMERIC(12,2) NOT NULL DEFAULT 0,
                tax_total NUMERIC(12,2) NOT NULL DEFAULT 0,
                grand_total NUMERIC(12,2) NOT NULL DEFAULT 0,
                notes TEXT,
                created_by INTEGER,
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME,
                CONSTRAINT uix_workspace_quote_number UNIQUE (workspace_id, quote_number)
            )
        """))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_quotes_workspace ON quotes(workspace_id)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_quotes_deal ON quotes(deal_id)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_quotes_status ON quotes(status)"))

        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS quote_line_items (
                id INTEGER PRIMARY KEY,
                workspace_id INTEGER NOT NULL,
                quote_id INTEGER NOT NULL,
                product_id INTEGER,
                item_name VARCHAR(200) NOT NULL,
                quantity NUMERIC(12,2) NOT NULL DEFAULT 1,
                unit_price NUMERIC(12,2) NOT NULL DEFAULT 0,
                discount_pct NUMERIC(5,2) NOT NULL DEFAULT 0,
                tax_pct NUMERIC(5,2) NOT NULL DEFAULT 0,
                total_amount NUMERIC(12,2) NOT NULL DEFAULT 0,
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP,
                updated_at DATETIME
            )
        """))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_quote_line_items_workspace ON quote_line_items(workspace_id)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_quote_line_items_quote ON quote_line_items(quote_id)"))

        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS deal_merge_history (
                id INTEGER PRIMARY KEY,
                workspace_id INTEGER NOT NULL,
                primary_deal_id INTEGER NOT NULL,
                merged_deal_id INTEGER NOT NULL,
                merged_data_json TEXT NOT NULL,
                merged_by INTEGER NOT NULL,
                created_at DATETIME NOT NULL DEFAULT CURRENT_TIMESTAMP
            )
        """))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_deal_merge_history_workspace ON deal_merge_history(workspace_id)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_deal_merge_history_primary ON deal_merge_history(primary_deal_id)"))
        conn.execute(text("CREATE INDEX IF NOT EXISTS idx_deal_merge_history_merged ON deal_merge_history(merged_deal_id)"))

        conn.commit()
    print("Week-3 pipeline feature migration complete")


def downgrade(db):
    print("Downgrade not supported for add_pipeline_week3_features.py")


if __name__ == '__main__':
    from app import app, db
    with app.app_context():
        upgrade(db)
