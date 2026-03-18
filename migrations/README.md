# Database Migrations

This folder contains database migration scripts for schema changes.

## Running Migrations

### Apply Migration
```bash
python migrations/add_deal_version_column.py
```

### Rollback Migration
```bash
python migrations/add_deal_version_column.py downgrade
```

## Migration History

- `add_deal_version_column.py` - Adds version column to Deal model for optimistic locking (2026-03-18)

## Creating New Migrations

1. Create a new Python file with descriptive name
2. Implement `upgrade()` and `downgrade()` functions
3. Test both upgrade and downgrade paths
4. Document the migration in this README
