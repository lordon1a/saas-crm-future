from app import app, db
from migrations.add_company_email import upgrade

with app.app_context():
    upgrade(db)
