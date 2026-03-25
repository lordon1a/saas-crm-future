# AGENTS.md

## Must-follow Constraints

- **Auth required**: All new endpoints must use `@login_required` decorator
- **DB rollback**: All `db.session.commit()` must be wrapped in try/except with rollback
- **No new HTML**: Do not create new HTML pages unless explicitly requested
- **No breaking changes**: Never delete or modify existing API routes
- **Migration required**: Schema changes require migration script in `migrations/` folder

## Validation Before Finishing

- Run syntax check on modified Python files
- Test the affected endpoint/page if possible

## Repo-specific Conventions

- Service layer: Put business logic in `services/` not routes
- Use existing service functions before writing new DB code
- Tailwind CSS only - do not add custom CSS unless necessary
- Global JS in `static/app.js` or `static/topbar-global.js`

## Important Locations

- Models: `models_crm.py`, `models_automation.py`, `models_contact_timeline.py`
- Key routes: `routes/api.py`, `routes/contacts.py`, `routes/automation.py`, `routes/pipeline.py`, `routes/tasks.py`
- Key services: `services/automation_engine.py`, `services/contact_service.py`, `services/pipeline_service.py`, `services/task_service.py`

## Change Safety Rules

- **to_dict() Rule**: ALWAYS update the `to_dict()` or schema serializers if you add or rely on new database columns. Silent failures in JS formatting occur when properties are missing from the API JSON response due to incomplete `to_dict()` methods.
- Never modify model relationships without checking cascade/orphan effects
- Never expose sensitive data (passwords, tokens, API keys) in logs or responses
- Never store passwords in plain text - use hashed passwords
- Never add unauthenticated API endpoints

## Known Gotchas

- Sidebar icon order is fixed: Inbox → Analytics → Contacts → Companies → Broadcast → Automation → Pipeline → Tasks → Documents → Channels → Settings → Logout
- Topbar must stay fixed at top - do not make it scrollable
- Custom field updates require both `models_crm.py` and `routes/custom_fields.py` changes
- Pipeline stage changes affect `services/pipeline_service.py` logic
- WhatsApp webhook processing is in `services/webhook_service.py`
