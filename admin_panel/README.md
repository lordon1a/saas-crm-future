# Super Admin Panel

Platform-level administration interface for managing all workspaces.

## Features

- **Authentication**: JWT-based login with 24-hour token expiry
- **Dashboard**: Overview of platform metrics (DAU, MAU, messages, workspaces)
- **Tenant Management**: View all workspaces with statistics
- **Tenant Details**: Deep dive into individual workspace data
- **Impersonation**: Generate 1-hour tokens to access workspaces as super admin
- **Activity Tracking**: All impersonation sessions logged to database

## File Structure

```
admin_panel/
├── index.html          # Login page
├── dashboard.html      # Main dashboard with tenant list
├── tenant.html         # Single tenant detail page
├── static/
│   └── admin.js        # Shared API utilities
└── README.md           # This file
```

## Setup

### 1. Create Super Admin User

First, create a super admin account in the database:

```python
from werkzeug.security import generate_password_hash
from models import db, SuperAdmin
from app import app

with app.app_context():
    admin = SuperAdmin(
        email='admin@example.com',
        password_hash=generate_password_hash('your-secure-password'),
        name='Super Admin',
        is_active=True
    )
    db.session.add(admin)
    db.session.commit()
    print(f"Super admin created: {admin.email}")
```

### 2. Configure Environment Variables

Add to your `.env` file:

```bash
# JWT Secret for Super Admin authentication (defaults to SECRET_KEY if not set)
JWT_SECRET=your-jwt-secret-key-here
```

### 3. Access the Panel

Navigate to: `http://your-domain.com/admin_panel/index.html`

Login with the super admin credentials you created.

## API Endpoints

All endpoints are prefixed with `/api/super` and require JWT authentication.

### Authentication
- `POST /auth/login` - Login and get JWT token

### Tenant Management
- `GET /tenants` - List all workspaces
- `GET /tenants/<id>` - Get single workspace details
- `POST /tenants/<id>/suspend` - Suspend workspace (not implemented)
- `POST /tenants/<id>/activate` - Activate workspace (not implemented)
- `PATCH /tenants/<id>/plan` - Update plan (not implemented)

### Analytics
- `GET /analytics/overview` - Platform-wide DAU, MAU, message counts
- `GET /analytics/revenue` - Revenue analytics (not implemented)

### Impersonation
- `POST /impersonate/<workspace_id>` - Generate impersonation token (1h expiry)
- `DELETE /impersonate` - End impersonation session

## Security Notes

- All API calls require JWT token in `Authorization: Bearer <token>` header
- Tokens expire after 24 hours (login) or 1 hour (impersonation)
- All impersonation sessions are logged with IP address and timestamps
- Unauthorized access attempts are logged

## Technology Stack

- **Frontend**: Vanilla JavaScript + TailwindCSS CDN
- **Backend**: Flask + SQLAlchemy
- **Auth**: JWT (PyJWT)
- **Database**: PostgreSQL

## Development

To modify the API base URL for local development, set the `SUPER_ADMIN_API_URL` variable:

```html
<script>
    window.SUPER_ADMIN_API_URL = 'http://localhost:5000/api/super';
</script>
<script src="static/admin.js"></script>
```

## TODO

- [ ] Implement tenant suspension/activation
- [ ] Implement plan management (free/starter/pro)
- [ ] Implement revenue analytics
- [ ] Add audit log viewer
- [ ] Add bulk operations
- [ ] Add export functionality
