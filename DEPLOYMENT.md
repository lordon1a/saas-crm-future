# Production Deployment Guide

## 🚀 Quick Start

This guide covers deploying the WhatsApp CRM to production platforms like Render, Heroku, or Railway.

## Prerequisites

- Git repository
- Production database (PostgreSQL)
- Meta WhatsApp Business API credentials
- (Optional) Google Cloud credentials for Gmail/Calendar sync

## Platform-Specific Deployment

### Option 1: Render.com (Recommended)

1. **Create New Web Service**
   - Connect your GitHub/GitLab repository
   - Select branch: `main`

2. **Configure Build Settings**
   ```
   Build Command: pip install -r requirements.txt
   Start Command: gunicorn app:app
   ```

3. **Add Environment Variables**
   ```
   FLASK_ENV=production
   FLASK_DEBUG=0
   SECRET_KEY=<generate-with-secrets-token-hex-32>
   DATABASE_URL=<render-provides-this-automatically>
   WHATSAPP_TOKEN=<your-meta-token>
   WHATSAPP_PHONE_NUMBER_ID=<your-phone-id>
   WEBHOOK_VERIFY_TOKEN=<your-webhook-token>
   CORS_ORIGINS=https://your-domain.com
   ```

4. **Create PostgreSQL Database**
   - In Render dashboard, create a new PostgreSQL database
   - Copy the "Internal Database URL"
   - Add as `DATABASE_URL` environment variable

5. **Deploy**
   - Click "Create Web Service"
   - Wait for build to complete
   - Run migrations (see below)

### Option 2: Heroku

1. **Install Heroku CLI**
   ```bash
   # macOS
   brew tap heroku/brew && brew install heroku
   
   # Windows
   # Download from https://devcenter.heroku.com/articles/heroku-cli
   ```

2. **Login and Create App**
   ```bash
   heroku login
   heroku create your-app-name
   ```

3. **Add PostgreSQL**
   ```bash
   heroku addons:create heroku-postgresql:mini
   ```

4. **Set Environment Variables**
   ```bash
   heroku config:set FLASK_ENV=production
   heroku config:set FLASK_DEBUG=0
   heroku config:set SECRET_KEY=$(python -c "import secrets; print(secrets.token_hex(32))")
   heroku config:set WHATSAPP_TOKEN=your_token
   heroku config:set WHATSAPP_PHONE_NUMBER_ID=your_phone_id
   heroku config:set WEBHOOK_VERIFY_TOKEN=your_webhook_token
   heroku config:set CORS_ORIGINS=https://your-app-name.herokuapp.com
   ```

5. **Deploy**
   ```bash
   git push heroku main
   ```

6. **Run Migrations**
   ```bash
   heroku run python migrate_crm_pipeline.py
   heroku run python migrate_google_sync.py
   ```

### Option 3: Railway.app

1. **Create New Project**
   - Connect GitHub repository
   - Railway auto-detects Python app

2. **Add PostgreSQL**
   - Click "New" → "Database" → "PostgreSQL"
   - Railway automatically sets `DATABASE_URL`

3. **Configure Environment Variables**
   - Go to Variables tab
   - Add all required variables (same as Render)

4. **Deploy**
   - Railway auto-deploys on git push

## Post-Deployment Steps

### 1. Run Database Migrations

**Via Platform CLI:**
```bash
# Render
render run python migrate_crm_pipeline.py
render run python migrate_google_sync.py

# Heroku
heroku run python migrate_crm_pipeline.py
heroku run python migrate_google_sync.py

# Railway
railway run python migrate_crm_pipeline.py
railway run python migrate_google_sync.py
```

**Or via Python Shell:**
```bash
# Open Python shell on platform
python

# Then run:
from app import app, db
with app.app_context():
    db.create_all()
    print("Tables created!")
```

### 2. Create Admin User

```bash
# Via platform CLI
python seed_data.py
```

Or manually via Python shell:
```python
from app import app, db
from models import User, Workspace
import bcrypt

with app.app_context():
    # Create workspace
    workspace = Workspace(company_name='Your Company')
    db.session.add(workspace)
    db.session.flush()
    
    # Create admin user
    password_hash = bcrypt.hashpw('admin123'.encode('utf-8'), bcrypt.gensalt()).decode('utf-8')
    user = User(
        email='admin@yourcompany.com',
        password_hash=password_hash,
        name='Admin User',
        role='admin',
        workspace_id=workspace.id
    )
    db.session.add(user)
    db.session.commit()
    print(f"Admin user created: admin@yourcompany.com / admin123")
```

### 3. Configure Meta WhatsApp Webhook

1. Go to Meta Developer Console
2. Navigate to WhatsApp → Configuration
3. Set Webhook URL: `https://your-domain.com/webhook`
4. Set Verify Token: (same as `WEBHOOK_VERIFY_TOKEN` env var)
5. Subscribe to `messages` event

### 4. Configure Google OAuth (Optional)

1. Update `GOOGLE_REDIRECT_URI`:
   ```
   GOOGLE_REDIRECT_URI=https://your-domain.com/integrations/google/callback
   ```

2. In Google Cloud Console:
   - Add authorized redirect URI
   - Update OAuth consent screen

## Environment Variables Reference

### Required

| Variable | Description | Example |
|----------|-------------|---------|
| `FLASK_ENV` | Environment mode | `production` |
| `SECRET_KEY` | Flask secret key (32+ chars) | Generate with `secrets.token_hex(32)` |
| `DATABASE_URL` | PostgreSQL connection string | Auto-provided by platform |
| `WHATSAPP_TOKEN` | Meta access token | From Meta Developer Console |
| `WHATSAPP_PHONE_NUMBER_ID` | WhatsApp phone number ID | From Meta Developer Console |
| `WEBHOOK_VERIFY_TOKEN` | Webhook verification token | Random secure string |

### Optional

| Variable | Description | Default |
|----------|-------------|---------|
| `FLASK_DEBUG` | Debug mode | `0` |
| `CORS_ORIGINS` | Allowed origins (comma-separated) | `*` |
| `LOG_LEVEL` | Logging level | `INFO` |
| `GOOGLE_CLIENT_ID` | Google OAuth client ID | - |
| `GOOGLE_CLIENT_SECRET` | Google OAuth secret | - |
| `PORTAL_JWT_SECRET` | Customer portal JWT secret | Uses `SECRET_KEY` |

## Health Check

Test your deployment:

```bash
# Check if app is running
curl https://your-domain.com/

# Check webhook endpoint
curl "https://your-domain.com/webhook?hub.mode=subscribe&hub.verify_token=YOUR_TOKEN&hub.challenge=test123"
# Should return: test123

# Check API docs
curl https://your-domain.com/api/docs
```

## Monitoring & Logs

### View Logs

```bash
# Render
render logs

# Heroku
heroku logs --tail

# Railway
railway logs
```

### Common Issues

**Issue: Database connection errors**
- Solution: Ensure `DATABASE_URL` is set correctly
- Check if PostgreSQL addon is provisioned

**Issue: SECRET_KEY not set**
- Solution: Generate and set: `python -c "import secrets; print(secrets.token_hex(32))"`

**Issue: CORS errors**
- Solution: Set `CORS_ORIGINS` to your frontend domain

**Issue: Webhook not receiving messages**
- Solution: Verify webhook URL in Meta Console
- Check `WEBHOOK_VERIFY_TOKEN` matches

## Scaling

### Horizontal Scaling

Increase number of workers:

**Render:**
- Go to Settings → Instance Count

**Heroku:**
```bash
heroku ps:scale web=2
```

**Railway:**
- Go to Settings → Replicas

### Database Connection Pooling

For high traffic, consider:
- PgBouncer (connection pooler)
- Increase `SQLALCHEMY_POOL_SIZE` in config.py

## Backup & Recovery

### Database Backups

**Render:**
- Automatic daily backups included

**Heroku:**
```bash
heroku pg:backups:capture
heroku pg:backups:download
```

**Railway:**
- Automatic backups in dashboard

### Restore from Backup

```bash
# Heroku
heroku pg:backups:restore <backup-url> DATABASE_URL
```

## Security Checklist

- [ ] `SECRET_KEY` is strong (32+ characters)
- [ ] `FLASK_DEBUG=0` in production
- [ ] `CORS_ORIGINS` set to specific domains (not `*`)
- [ ] Database uses SSL connection
- [ ] Environment variables not committed to git
- [ ] HTTPS enabled (automatic on Render/Heroku/Railway)
- [ ] Rate limiting configured
- [ ] Webhook signature verification enabled

## Performance Optimization

1. **Enable Database Connection Pooling**
   - Already configured in `config.py`

2. **Use Redis for Rate Limiting**
   ```bash
   # Add Redis addon
   heroku addons:create heroku-redis:mini
   
   # Set environment variable
   heroku config:set RATELIMIT_STORAGE_URI=<redis-url>
   ```

3. **CDN for Static Assets**
   - Consider CloudFlare or AWS CloudFront

4. **Background Jobs**
   - For Gmail/Calendar sync, consider Celery + Redis

## Support

For issues:
1. Check logs first
2. Verify environment variables
3. Test locally with PostgreSQL
4. Review PHASE1-7_REVIEW.md for feature status

## Next Steps

After successful deployment:
1. Test all features (login, contacts, pipeline, etc.)
2. Configure Google Workspace integration
3. Set up monitoring/alerting
4. Plan for Phase 8-14 features
