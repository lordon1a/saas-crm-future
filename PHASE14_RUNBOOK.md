# Phase 14 Runbook

## Scope
Phase 14 covers final integration verification, test hardening, performance checks, UI regression checks, and release operations readiness.

## 1. Integration Verification

### System Health Report
Use the system health endpoint:

- `GET /api/settings/system-health/report?days=30`

Checks included:
- Activity coverage across required event types (`system`, `task`, `email`, `note`)
- Relational integrity (orphan records and cross-workspace mismatches)
- Integration health summary (Google + QuickBooks active connections)
- Workspace stats snapshot

## 2. Test Suite and Coverage

### Full verification command

```bash
python -m unittest \
  tests.test_phase14_system_health \
  tests.test_phase13_collaboration \
  tests.test_phase12_quickbooks \
  tests.test_phase11_email \
  tests.test_phase10_documents \
  tests.test_phase9_security \
  tests.test_phase8_reports \
  tests.test_phase7_sync_utils
```

### Optional coverage run
If coverage is installed in your environment:

```bash
coverage run -m unittest discover tests
coverage report -m
```

Target for critical business modules: >= 80%.

## 3. Performance and Reliability

### Applied hardening
- Added index support for note-heavy queries (`conversation_id`, `user_id`, `created_at`) in the `notes` table model.
- Removed an N+1 query pattern in unified inbox WhatsApp aggregation by preloading customers.
- Added a short-lived cache (`30s`) for dashboard aggregate endpoint to reduce repeated expensive reads.

### Load test (15 concurrent users)

```bash
python scripts/phase14_load_test.py --base-url http://127.0.0.1:5000 --token YOUR_SESSION_COOKIE --requests 150 --workers 15
```

Expected baseline:
- Stable status code distribution (mostly `200`)
- No worker crashes/timeouts
- Acceptable p95 under environment constraints

## 4. Frontend Regression Checklist

Validate on desktop and mobile widths:
- Sidebar navigation consistency across inbox, pipeline, settings, analytics, tasks, documents.
- Notification bell and unread badge behavior in inbox.
- Collaboration follow/unfollow control in deal modal.
- Existing Google/QuickBooks settings interactions still function.
- No broken JS selectors in newly touched screens.

## 5. Deployment and Operations

### Environment variable review
- Security/auth/session variables
- Google OAuth variables
- QuickBooks OAuth variables
- SMTP/email provider variables
- Document storage variables (local/S3)
- Rate limit and logging variables

### Migration workflow
1. Backup current database.
2. Deploy code.
3. Run migration/create-all flow for new fields/tables.
4. Verify health endpoint and smoke tests.
5. Monitor logs and error rates.

### Backup and restore
- Ensure daily DB snapshot policy exists.
- Keep tested restore procedure for staging and production.
- Validate RPO/RTO expectations with team.

### Monitoring
Track:
- HTTP error rates (`4xx/5xx`)
- Background job failures
- QuickBooks/Google integration error logs
- DB connection and latency metrics
- Notification and activity feed endpoint latency
