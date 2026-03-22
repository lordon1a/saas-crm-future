# Database Migrations

This folder contains database migration scripts for schema changes.

## Running Migrations

### Local (SQLite)
```bash
python migrations/add_pipeline_stage_config_columns.py
```

### Production (PostgreSQL on Render)
```bash
python migrations/add_rotting_days_postgres.py
```

### Rollback Migration
```bash
python migrations/add_rotting_days_postgres.py downgrade
```

## Migration History

- `add_deal_version_column.py` - Adds version column to Deal model for optimistic locking (2026-03-18)
- `add_deal_contact_id.py` - Adds optional primary contact link to Deal model (2026-03-22)
- `add_deal_contacts_table.py` - Adds deal stakeholder relationship table (2026-03-22)
- `add_pipeline_stage_config_columns.py` - Adds rotting_days, is_active columns to deal_stages (SQLite)
- `add_rotting_days_postgres.py` - Adds rotting_days, is_active columns to deal_stages (PostgreSQL) (2026-03-18)

## Creating New Migrations

1. Create a new Python file with descriptive name
2. Implement `migrate()` and `downgrade()` functions
3. Test both upgrade and downgrade paths
4. Document the migration in this README

## Notes

- SQLite migrations use `sqlite3` module
- PostgreSQL migrations use `psycopg2` module
- Always check if columns exist before adding them (idempotent migrations)
