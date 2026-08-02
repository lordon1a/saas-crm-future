# SaaS CRM Future

A comprehensive, modern, and highly scalable Customer Relationship Management (CRM) SaaS platform built with Python and Flask. This project is designed to provide businesses with powerful tools to manage contacts, pipelines, automations, and third-party integrations, all while offering real-time collaboration and AI-assisted workflows.

## 🚀 Features

- **Robust Authentication & Security**: Secure user login with `Flask-Login`, CSRF protection (`Flask-WTF`), and Rate Limiting to prevent brute-force attacks.
- **Real-time Collaboration**: Built-in real-time features using `Flask-SocketIO` and `gevent` for instant updates and team collaboration.
- **Advanced Integrations**: Seamless connections with:
  - Google Workspace (OAuth, Calendar, Contacts)
  - QuickBooks (Accounting)
  - Telegram (Bot integration)
- **AI-Powered Assistants**: Integrated with leading AI models including Anthropic, Google Generative AI, and Groq for smart CRM automation, content generation, and insights.
- **Workflow & Automations**: Customizable sales pipelines, automated tasks, and webhooks to streamline business processes.
- **Document Generation**: Automated document and presentation generation using `docxtpl` and `python-pptx`.
- **Public API & Webhooks**: Fully documented API (`routes.api_docs`) for external system integrations and developer access.
- **Analytics & Email Tracking**: Built-in analytics dashboard, system health monitoring, and email tracking capabilities.
- **Customer Portal**: A dedicated self-service portal for customers to interact with your business.

## 🛠️ Tech Stack

- **Backend**: Python 3.10+, Flask 3.0
- **Database**: PostgreSQL (Production) / SQLite (Development), using SQLAlchemy ORM and Alembic (`Flask-Migrate`)
- **Real-time**: Flask-SocketIO, Gevent, Gevent-Websocket
- **Security**: Flask-WTF (CSRF), Flask-Limiter, PyJWT, Cryptography, PyOTP
- **Production Server**: Gunicorn
- **Task Scheduling**: APScheduler

## 📦 Installation & Setup

1. **Clone the repository:**
   ```bash
   git clone https://github.com/lordon1a/saas-crm-future.git
   cd saas-crm-future
   ```

2. **Create a virtual environment:**
   ```bash
   python -m venv venv
   source venv/bin/activate  # On Windows use `venv\Scripts\activate`
   ```

3. **Install dependencies:**
   ```bash
   pip install -r requirements.txt
   ```

4. **Environment Variables:**
   Create a `.env` file in the root directory based on the `config.py` structure and configure the necessary environment variables:
   - `SECRET_KEY`
   - `SQLALCHEMY_DATABASE_URI`
   - Integration API Keys (Google, QuickBooks, AI providers)

5. **Initialize the Database:**
   ```bash
   flask db upgrade
   ```

6. **Run the application:**
   ```bash
   # Development mode
   flask run

   # Production mode (Gevent & Gunicorn)
   gunicorn -k geventwebsocket.gunicorn.workers.GeventWebSocketWorker -w 1 app:app
   ```

## 🏗️ Project Structure

- `app.py` - Application factory, Socket.IO initialization, and core configuration
- `config.py` - Environment and application configurations
- `/models*.py` - SQLAlchemy database models (Core CRM, Timeline, Automations, etc.)
- `/routes/` - Application endpoints grouped by feature (API, auth, portal, integrations, etc.)
- `/services/` - Business logic and external API communication layers
- `/static/` & `/templates/` - Frontend static assets and Jinja2 templates
- `/tests/` - Automated test suites
- `/admin_panel/` - Administrative tools and interfaces

## 🤝 Contributing
Contributions, issues, and feature requests are welcome!

## 📝 License
This project is proprietary and confidential. All rights reserved.
